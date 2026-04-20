from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.application.access import AccessResolver, InMemoryAccessRepository
from app.common.i18n import I18nService
from app.domain.access_identity.models import (
    ActorIdentity,
    ActorStatus,
    ActorType,
    ClinicRoleAssignment,
    DoctorProfile,
    RoleCode,
    StaffMember,
    StaffStatus,
    TelegramBinding,
)
from app.domain.care_commerce.models import CareOrder, CareOrderItem, CareProduct, CareReservation
from app.domain.recommendations.models import Recommendation
from app.interfaces.bots.admin.router import make_router as make_admin_router
from app.interfaces.bots.doctor.router import make_router as make_doctor_router
from app.interfaces.cards import CardAction, CardCallback, CardCallbackCodec, CardMode, CardProfile, CardRuntimeCoordinator, CardRuntimeStateStore, EntityType, SourceContext
from app.interfaces.cards.runtime_state import InMemoryRedis


class _CallbackMessage:
    def __init__(self) -> None:
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None) -> None:
        self.edits.append((text, reply_markup))


class _Callback:
    def __init__(self, data: str, *, user_id: int) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id)
        self.message = _CallbackMessage()
        self.answers: list[str] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answers.append(text)


class _AdminReference:
    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en")

    def get_service(self, clinic_id: str, service_id: str):
        return SimpleNamespace(code="CONS", title_key="Consultation")

    def list_branches(self, clinic_id: str):
        return [SimpleNamespace(branch_id="br1", display_name="Main", timezone="UTC")]


class _DoctorReference(_AdminReference):
    def get_doctor(self, clinic_id: str, doctor_id: str):
        return SimpleNamespace(doctor_id=doctor_id, branch_id="br1")

    def list_services(self, clinic_id: str):
        return [SimpleNamespace(service_id="s1", code="CONS", title_key="Consultation")]


class _BookingFlow:
    def __init__(self) -> None:
        self.reads = self
        self.orchestration = SimpleNamespace(
            confirm_booking=self._ok,
            request_booking_reschedule=self._ok,
            cancel_booking=self._ok,
            booking_state_service=SimpleNamespace(transition_booking=self._ok),
        )

    async def _ok(self, **kwargs):
        return SimpleNamespace(kind="success", entity=self._booking())

    async def get_booking(self, booking_id: str):
        return self._booking()

    def build_booking_snapshot(self, **kwargs):
        booking = kwargs["booking"]
        return SimpleNamespace(
            doctor_label="Dr A",
            service_label="Consultation",
            branch_label="Main",
            next_step_note_key="patient.booking.card.next.default",
            booking_id=booking.booking_id,
            state_token=booking.booking_id,
            role_variant="admin",
            scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
            timezone_name="UTC",
            patient_label="Jane Roe",
            status=booking.status,
            source_channel="telegram",
            patient_contact=None,
            compact_flags=(),
            reminder_summary=None,
            reschedule_summary=None,
            recommendation_summary="linked",
            care_order_summary="linked",
            chart_summary_entry=None,
        )

    def _booking(self):
        return SimpleNamespace(
            booking_id="b1",
            patient_id="p1",
            doctor_id="d1",
            service_id="s1",
            clinic_id="c1",
            branch_id="br1",
            status="confirmed",
            source_channel="telegram",
            scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        )


class _RecommendationService:
    def __init__(self, rows: list[Recommendation]) -> None:
        self.rows = rows

    async def list_for_booking(self, *, booking_id: str):
        return [row for row in self.rows if row.booking_id == booking_id]


class _CareRepo:
    def __init__(self, orders: list[CareOrder], items: list[CareOrderItem], products: list[CareProduct], reservations: list[CareReservation]) -> None:
        self.orders = orders
        self.items = items
        self.products = {p.care_product_id: p for p in products}
        self.reservations = reservations

    async def list_order_items(self, care_order_id: str):
        return [row for row in self.items if row.care_order_id == care_order_id]

    async def get_product(self, care_product_id: str):
        return self.products.get(care_product_id)

    async def list_reservations_for_order(self, *, care_order_id: str):
        return [row for row in self.reservations if row.care_order_id == care_order_id]


class _CareService:
    def __init__(self, repo: _CareRepo) -> None:
        self.repository = repo
        self._repo = repo

    async def list_patient_orders(self, *, clinic_id: str, patient_id: str):
        return [row for row in self._repo.orders if row.clinic_id == clinic_id and row.patient_id == patient_id]

    async def resolve_product_content(self, *, clinic_id: str, product: CareProduct, locale: str):
        return SimpleNamespace(title=product.sku, short_label=None)


class _DoctorBookingService:
    async def load_booking(self, booking_id: str):
        return SimpleNamespace(
            booking_id="b1",
            patient_id="p1",
            clinic_id="c1",
            doctor_id="d1",
            branch_id="br1",
            service_id="s1",
            status="confirmed",
            source_channel="telegram",
            scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        )

    async def list_by_patient(self, *, patient_id: str):
        if patient_id != "p1":
            return []
        return [
            SimpleNamespace(
                booking_id="b1",
                doctor_id="d1",
                scheduled_start_at=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
                status="confirmed",
            )
        ]


class _PatientReader:
    async def read_snapshot(self, *, patient_id: str):
        return SimpleNamespace(
            patient_id="p1",
            display_name="Jane Roe",
            patient_number="1001",
            phone_raw="+15551234567",
            has_photo=False,
            active_flags_summary=None,
        )


class _BookingState:
    async def transition_booking(self, *, booking_id: str, to_status: str, reason_code: str):
        return SimpleNamespace(entity=SimpleNamespace(booking_id=booking_id, status=to_status))


class _Orchestration:
    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None):
        return SimpleNamespace(kind="success", entity=SimpleNamespace(booking_id=booking_id, status="completed"))


def _access(role: RoleCode, *, user_id: int) -> AccessResolver:
    repo = InMemoryAccessRepository()
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    actor_id = f"a_{role.value}"
    staff_id = f"s_{role.value}"
    repo.upsert_actor_identity(ActorIdentity(actor_id=actor_id, actor_type=ActorType.STAFF, display_name="User", status=ActorStatus.ACTIVE, locale="en"))
    repo.upsert_telegram_binding(TelegramBinding(telegram_binding_id=f"tb_{role.value}", actor_id=actor_id, telegram_user_id=user_id))
    repo.upsert_staff_member(StaffMember(staff_id=staff_id, actor_id=actor_id, clinic_id="c1", full_name="User", display_name="User", staff_status=StaffStatus.ACTIVE))
    repo.upsert_role_assignment(ClinicRoleAssignment(role_assignment_id=f"ra_{role.value}", staff_id=staff_id, clinic_id="c1", role_code=role, granted_at=now))
    if role == RoleCode.DOCTOR:
        repo.upsert_doctor_profile(DoctorProfile(doctor_profile_id="dp1", staff_id=staff_id, clinic_id="c1", doctor_id="d1", specialty_code="general", active_for_clinical_work=True))
    return AccessResolver(repo)


def _handler(router, name: str, *, kind: str = "callback"):
    handlers = router.callback_query.handlers if kind == "callback" else router.message.handlers
    for row in handlers:
        if row.callback.__name__ == name:
            return row.callback
    raise AssertionError(name)


def _build_recommendation_rows() -> list[Recommendation]:
    base = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
    return [
        Recommendation(
            recommendation_id="rec_old",
            clinic_id="c1",
            patient_id="p1",
            booking_id="b1",
            encounter_id=None,
            chart_id=None,
            issued_by_actor_id=None,
            source_kind="doctor_manual",
            recommendation_type="aftercare",
            title="Old recommendation",
            body_text="Old body",
            rationale_text="Old rationale",
            status="prepared",
            issued_at=None,
            viewed_at=None,
            acknowledged_at=None,
            accepted_at=None,
            declined_at=None,
            expired_at=None,
            withdrawn_at=None,
            created_at=base,
            updated_at=base,
        ),
        Recommendation(
            recommendation_id="rec_new",
            clinic_id="c1",
            patient_id="p1",
            booking_id="b1",
            encounter_id=None,
            chart_id=None,
            issued_by_actor_id=None,
            source_kind="doctor_manual",
            recommendation_type="follow_up",
            title="New recommendation",
            body_text="New body",
            rationale_text="Newest rationale text",
            status="issued",
            issued_at=base,
            viewed_at=None,
            acknowledged_at=None,
            accepted_at=None,
            declined_at=None,
            expired_at=None,
            withdrawn_at=None,
            created_at=base,
            updated_at=base.replace(hour=9),
        ),
    ]


def _build_care_service() -> _CareService:
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    orders = [
        CareOrder(
            care_order_id="co_new",
            clinic_id="c1",
            patient_id="p1",
            booking_id="b1",
            recommendation_id=None,
            status="ready_for_pickup",
            payment_mode="cash",
            pickup_branch_id="br1",
            total_amount=250,
            currency_code="USD",
            created_at=now,
            updated_at=now,
            confirmed_at=None,
            paid_at=None,
            ready_for_pickup_at=now,
            issued_at=None,
            fulfilled_at=None,
            canceled_at=None,
            expired_at=None,
        )
    ]
    items = [
        CareOrderItem(
            care_order_item_id="coi1",
            care_order_id="co_new",
            care_product_id="cp1",
            quantity=2,
            unit_price=125,
            line_total=250,
            created_at=now,
        )
    ]
    products = [
        CareProduct(
            care_product_id="cp1",
            clinic_id="c1",
            sku="Post-op gel",
            title_key="title",
            description_key=None,
            category="hygiene",
            use_case_tag=None,
            price_amount=125,
            currency_code="USD",
            status="active",
            pickup_supported=True,
            delivery_supported=False,
            sort_order=None,
            available_qty=10,
            created_at=now,
            updated_at=now,
        )
    ]
    reservations = [
        CareReservation(
            care_reservation_id="cr1",
            care_order_id="co_new",
            care_product_id="cp1",
            branch_id="br1",
            status="active",
            reserved_qty=2,
            expires_at=None,
            created_at=now,
            updated_at=now,
            released_at=None,
            consumed_at=None,
        )
    ]
    return _CareService(_CareRepo(orders, items, products, reservations))


def _admin_router(*, recommendation_rows: list[Recommendation], care_service: _CareService):
    i18n = I18nService(Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    router = make_admin_router(
        i18n=i18n,
        access_resolver=_access(RoleCode.ADMIN, user_id=701),
        reference_service=_AdminReference(),
        booking_flow=_BookingFlow(),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        care_commerce_service=care_service,
        recommendation_service=_RecommendationService(recommendation_rows),
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, codec


def _doctor_router(*, recommendation_rows: list[Recommendation], care_service: _CareService):
    i18n = I18nService(Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    router = make_doctor_router(
        i18n=i18n,
        access_resolver=_access(RoleCode.DOCTOR, user_id=702),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        booking_service=_DoctorBookingService(),
        booking_state_service=_BookingState(),
        booking_orchestration=_Orchestration(),
        reference_service=_DoctorReference(),
        patient_reader=_PatientReader(),
        clinical_service=SimpleNamespace(),
        recommendation_service=_RecommendationService(recommendation_rows),
        care_commerce_service=care_service,
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, codec


def _booking_callback_payload(*, page_or_index: str, booking_id: str, source_context: SourceContext) -> CardCallback:
    return CardCallback(
        profile=CardProfile.BOOKING,
        entity_type=EntityType.BOOKING,
        entity_id=booking_id,
        action=CardAction.OPEN,
        mode=CardMode.EXPANDED,
        source_context=source_context,
        source_ref="test",
        page_or_index=page_or_index,
        state_token=booking_id,
    )


def test_admin_linked_opens_render_panels_and_back_navigation() -> None:
    router, codec = _admin_router(recommendation_rows=_build_recommendation_rows(), care_service=_build_care_service())
    callback_handler = _handler(router, "admin_runtime_card_callback")
    rec_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_recommendation", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    rec_callback = _Callback(rec_data, user_id=701)
    asyncio.run(callback_handler(rec_callback))
    rec_text, rec_kb = rec_callback.message.edits[-1]
    assert "Recommendation rec_new" in rec_text
    assert "Type: Follow-up" in rec_text
    assert "recommendation :: patient=" not in rec_text
    assert rec_kb.inline_keyboard[0][0].text == "Back"

    order_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    order_callback = _Callback(order_data, user_id=701)
    asyncio.run(callback_handler(order_callback))
    order_text, order_kb = order_callback.message.edits[-1]
    assert "Order co_new" in order_text
    assert "Post-op gel ×2" in order_text
    assert "care_order :: patient=" not in order_text
    assert order_kb.inline_keyboard[0][0].text == "Back"


def test_doctor_linked_opens_render_panels_and_missing_state() -> None:
    router, codec = _doctor_router(recommendation_rows=[], care_service=_build_care_service())
    callback_handler = _handler(router, "doctor_runtime_booking_callback")
    rec_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_recommendation", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    rec_callback = _Callback(rec_data, user_id=702)
    asyncio.run(callback_handler(rec_callback))
    rec_text, rec_kb = rec_callback.message.edits[-1]
    assert "No booking-linked recommendation found for this booking." in rec_text
    assert rec_kb.inline_keyboard[0][0].text == "Back"
    assert rec_text.strip() != "-"

    empty_care = _CareService(_CareRepo(orders=[], items=[], products=[], reservations=[]))
    router2, codec2 = _doctor_router(recommendation_rows=_build_recommendation_rows(), care_service=empty_care)
    callback_handler2 = _handler(router2, "doctor_runtime_booking_callback")
    order_data = asyncio.run(codec2.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    order_callback = _Callback(order_data, user_id=702)
    asyncio.run(callback_handler2(order_callback))
    order_text, order_kb = order_callback.message.edits[-1]
    assert "No booking-linked care order found for this booking." in order_text
    assert "care_order :: patient=" not in order_text
    assert order_kb.inline_keyboard[0][0].text == "Back"
