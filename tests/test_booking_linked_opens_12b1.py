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
from app.application.search.models import PatientSearchResponse, PatientSearchResult, SearchResultOrigin


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


class _CommandMessage:
    def __init__(self, text: str, *, user_id: int) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _AdminReference:
    def get_clinic(self, clinic_id: str):
        return SimpleNamespace(default_locale="en")

    def get_service(self, clinic_id: str, service_id: str):
        return SimpleNamespace(code="CONS", title_key="Consultation")

    def list_branches(self, clinic_id: str):
        return [SimpleNamespace(branch_id="br1", display_name="Main", timezone="UTC")]


class _Search:
    async def search_patients(self, query):
        row = PatientSearchResult(
            patient_id="p1",
            clinic_id=query.clinic_id,
            display_name="Jane Roe",
            patient_number="1001",
            primary_phone_normalized="+15551234567",
            active_flags_summary=None,
            status="active",
            origin=SearchResultOrigin.POSTGRES_STRICT,
        )
        return PatientSearchResponse(exact_matches=[row], suggestions=[])


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
        self.created: list[dict[str, object]] = []
        self.issued: list[str] = []

    async def list_for_booking(self, *, booking_id: str):
        return [row for row in self.rows if row.booking_id == booking_id]

    async def create_recommendation(
        self,
        *,
        clinic_id: str,
        patient_id: str,
        recommendation_type: str,
        source_kind: str,
        title: str,
        body_text: str,
        rationale_text: str | None = None,
        booking_id: str | None = None,
        encounter_id: str | None = None,
        chart_id: str | None = None,
        issued_by_actor_id: str | None = None,
        prepared: bool = True,
    ):
        recommendation_id = f"rec_created_{len(self.created) + 1}"
        self.created.append(
            {
                "clinic_id": clinic_id,
                "patient_id": patient_id,
                "recommendation_type": recommendation_type,
                "title": title,
                "body_text": body_text,
                "booking_id": booking_id,
                "encounter_id": encounter_id,
                "source_kind": source_kind,
            }
        )
        return SimpleNamespace(recommendation_id=recommendation_id)

    async def issue(self, *, recommendation_id: str, issued_by_actor_id: str | None = None):
        self.issued.append(recommendation_id)
        return SimpleNamespace(recommendation_id=recommendation_id)


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

    async def get_order(self, care_order_id: str):
        return next((row for row in self.orders if row.care_order_id == care_order_id), None)

    async def get_product_by_code(self, *, clinic_id: str, target_code: str):
        if clinic_id != "c1":
            return None
        for row in self.products.values():
            if row.sku == target_code:
                return row
        return None


class _CareService:
    def __init__(self, repo: _CareRepo) -> None:
        self.repository = repo
        self._repo = repo
        self.manual_targets: list[dict[str, str]] = []

    async def list_patient_orders(self, *, clinic_id: str, patient_id: str):
        return [row for row in self._repo.orders if row.clinic_id == clinic_id and row.patient_id == patient_id]

    async def resolve_product_content(self, *, clinic_id: str, product: CareProduct, locale: str):
        return SimpleNamespace(title=product.sku, short_label=None)

    async def get_order(self, care_order_id: str):
        return await self._repo.get_order(care_order_id)

    async def list_catalog_products_by_category(self, *, clinic_id: str, category: str):
        if clinic_id != "c1":
            return []
        return [row for row in self._repo.products.values() if row.category == category and row.status == "active"]

    async def set_manual_recommendation_target(
        self,
        *,
        recommendation_id: str,
        target_kind: str,
        target_code: str,
        justification_text: str | None = None,
    ) -> None:
        self.manual_targets.append(
            {
                "recommendation_id": recommendation_id,
                "target_kind": target_kind,
                "target_code": target_code,
            }
        )


class _DoctorBookingService:
    def __init__(self, *, status: str = "confirmed") -> None:
        self.status_by_booking: dict[str, str] = {"b1": status}

    async def load_booking(self, booking_id: str):
        status = self.status_by_booking.get(booking_id, "confirmed")
        return SimpleNamespace(
            booking_id=booking_id,
            patient_id="p1",
            clinic_id="c1",
            doctor_id="d1",
            branch_id="br1",
            service_id="s1",
            status=status,
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
                status=self.status_by_booking.get("b1", "confirmed"),
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
    def __init__(self, booking_service: _DoctorBookingService) -> None:
        self.booking_service = booking_service

    async def complete_booking(self, *, booking_id: str, reason_code: str | None = None):
        status = self.booking_service.status_by_booking.get(booking_id)
        if status != "in_service":
            return SimpleNamespace(kind="invalid_state", reason="cannot_complete")
        self.booking_service.status_by_booking[booking_id] = "completed"
        return SimpleNamespace(kind="success", entity=SimpleNamespace(booking_id=booking_id, status="completed"))


class _ClinicalService:
    class _Repo:
        def __init__(self, status: str) -> None:
            self.status_by_encounter: dict[str, str] = {}
            self.default_status = status

        async def get_encounter(self, encounter_id: str):
            booking_id = encounter_id.replace("enc_", "", 1)
            status = self.status_by_encounter.get(encounter_id, self.default_status)
            return SimpleNamespace(encounter_id=encounter_id, doctor_id="d1", patient_id="p1", booking_id=booking_id, status=status)

    def __init__(self, *, encounter_status: str = "in_progress") -> None:
        self.repository = self._Repo(encounter_status)
        self.encounter_status = encounter_status
        self.saved_notes: list[tuple[str, str, str]] = []
        self.closed_encounters: list[str] = []

    async def open_or_get_chart(self, *, patient_id: str, clinic_id: str, primary_doctor_id: str):
        return SimpleNamespace(chart_id=f"chart_{patient_id}")

    async def open_or_get_encounter(self, *, chart_id: str, doctor_id: str, booking_id: str | None = None):
        return SimpleNamespace(encounter_id=f"enc_{booking_id or chart_id}", status=self.encounter_status, doctor_id=doctor_id, patient_id="p1")

    async def add_encounter_note(self, *, encounter_id: str, note_type: str, note_text: str):
        self.saved_notes.append((encounter_id, note_type, note_text))
        return SimpleNamespace(encounter_note_id=f"note_{len(self.saved_notes)}")

    async def close_encounter(self, encounter_id: str):
        self.closed_encounters.append(encounter_id)
        self.repository.status_by_encounter[encounter_id] = "closed"
        return SimpleNamespace(encounter_id=encounter_id, doctor_id="d1", patient_id="p1", booking_id="b1", status="closed")


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


def _build_care_service(*, status: str = "ready_for_pickup") -> _CareService:
    now = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    orders = [
        CareOrder(
            care_order_id="co_new",
            clinic_id="c1",
            patient_id="p1",
            booking_id="b1",
            recommendation_id=None,
            status=status,
            payment_mode="cash",
            pickup_branch_id="br1",
            total_amount=250,
            currency_code="USD",
            created_at=now,
            updated_at=now,
            confirmed_at=None,
            paid_at=None,
            ready_for_pickup_at=now if status in {"ready_for_pickup", "issued", "fulfilled"} else None,
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


def _build_empty_care_service() -> _CareService:
    return _CareService(_CareRepo(orders=[], items=[], products=[], reservations=[]))


def _admin_router(*, recommendation_rows: list[Recommendation], care_service: _CareService):
    i18n = I18nService(Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    router = make_admin_router(
        i18n=i18n,
        access_resolver=_access(RoleCode.ADMIN, user_id=701),
        reference_service=_AdminReference(),
        booking_flow=_BookingFlow(),
        search_service=_Search(),
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


def _doctor_router(
    *,
    recommendation_rows: list[Recommendation],
    care_service: _CareService,
    clinical_service: _ClinicalService | None = None,
    booking_status: str = "confirmed",
):
    i18n = I18nService(Path("locales"), default_locale="en")
    runtime = CardRuntimeCoordinator(store=CardRuntimeStateStore(redis_client=InMemoryRedis()))
    codec = CardCallbackCodec(runtime=runtime)
    clinical = clinical_service or _ClinicalService()
    recommendation_service = _RecommendationService(recommendation_rows)
    booking_service = _DoctorBookingService(status=booking_status)
    router = make_doctor_router(
        i18n=i18n,
        access_resolver=_access(RoleCode.DOCTOR, user_id=702),
        search_service=SimpleNamespace(),
        stt_service=SimpleNamespace(),
        voice_mode_store=SimpleNamespace(),
        booking_service=booking_service,
        booking_state_service=_BookingState(),
        booking_orchestration=_Orchestration(booking_service),
        reference_service=_DoctorReference(),
        patient_reader=_PatientReader(),
        clinical_service=clinical,
        recommendation_service=recommendation_service,
        care_commerce_service=care_service,
        default_locale="en",
        max_voice_duration_sec=60,
        max_voice_file_size_bytes=1024,
        voice_mode_ttl_sec=30,
        card_runtime=runtime,
        card_callback_codec=codec,
    )
    return router, codec, clinical, recommendation_service


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
    rec_actions = [row[0].text for row in rec_kb.inline_keyboard]
    assert rec_actions == ["Patient", "Care", "Back"]

    open_patient_data = rec_kb.inline_keyboard[0][0].callback_data
    open_patient_callback = _Callback(open_patient_data, user_id=701)
    asyncio.run(callback_handler(open_patient_callback))
    patient_text, _ = open_patient_callback.message.edits[-1]
    assert "Jane Roe" in patient_text
    assert "Open active booking" in patient_text

    order_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    order_callback = _Callback(order_data, user_id=701)
    asyncio.run(callback_handler(order_callback))
    order_text, order_kb = order_callback.message.edits[-1]
    assert "Order co_new" in order_text
    assert "Post-op gel ×2" in order_text
    assert "care_order :: patient=" not in order_text
    order_actions = [row[0].text for row in order_kb.inline_keyboard]
    assert order_actions == ["Patient", "Open pickup handling", "Back"]

    open_order_data = rec_kb.inline_keyboard[1][0].callback_data
    open_order_callback = _Callback(open_order_data, user_id=701)
    asyncio.run(callback_handler(open_order_callback))
    order_from_recommendation_text, _ = open_order_callback.message.edits[-1]
    assert "Order co_new" in order_from_recommendation_text

    open_pickup_data = order_kb.inline_keyboard[1][0].callback_data
    open_pickup_callback = _Callback(open_pickup_data, user_id=701)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(open_pickup_callback))
    pickup_text, _ = open_pickup_callback.message.edits[-1]
    assert "Care order co_new" in pickup_text


def test_admin_linked_care_order_hides_pickup_cta_when_not_applicable() -> None:
    router, codec = _admin_router(recommendation_rows=_build_recommendation_rows(), care_service=_build_care_service(status="created"))
    callback_handler = _handler(router, "admin_runtime_card_callback")
    order_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    order_callback = _Callback(order_data, user_id=701)
    asyncio.run(callback_handler(order_callback))
    _, order_kb = order_callback.message.edits[-1]
    order_actions = [row[0].text for row in order_kb.inline_keyboard]
    assert order_actions == ["Patient", "Back"]


def test_admin_linked_recommendation_hides_care_order_cta_when_absent_and_manual_open_is_bounded() -> None:
    router, codec = _admin_router(recommendation_rows=_build_recommendation_rows(), care_service=_build_empty_care_service())
    callback_handler = _handler(router, "admin_runtime_card_callback")
    rec_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_recommendation", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    rec_callback = _Callback(rec_data, user_id=701)
    asyncio.run(callback_handler(rec_callback))
    _, rec_kb = rec_callback.message.edits[-1]
    rec_actions = [row[0].text for row in rec_kb.inline_keyboard]
    assert rec_actions == ["Patient", "Back"]

    manual_open_order_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.BOOKING_LIST)))
    manual_open_order_callback = _Callback(manual_open_order_data, user_id=701)
    asyncio.run(callback_handler(manual_open_order_callback))
    manual_text, manual_kb = manual_open_order_callback.message.edits[-1]
    assert "No booking-linked care order found for this booking." in manual_text
    manual_actions = [row[0].text for row in manual_kb.inline_keyboard]
    assert manual_actions == ["Patient", "Back"]

    manual_open_pickup_callback = _Callback("aw4cp:open:co_missing:na", user_id=701)
    asyncio.run(_handler(router, "admin_care_pickups_callback", kind="callback")(manual_open_pickup_callback))
    assert manual_open_pickup_callback.answers


def test_doctor_linked_opens_render_panels_and_missing_state() -> None:
    router, codec, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_care_service())
    callback_handler = _handler(router, "doctor_runtime_booking_callback")
    rec_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_recommendation", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    rec_callback = _Callback(rec_data, user_id=702)
    asyncio.run(callback_handler(rec_callback))
    rec_text, rec_kb = rec_callback.message.edits[-1]
    assert "No booking-linked recommendation found for this booking." in rec_text
    assert rec_kb.inline_keyboard[0][0].text == "Back"
    assert rec_text.strip() != "-"

    router2, codec2, _, _ = _doctor_router(recommendation_rows=_build_recommendation_rows(), care_service=_build_empty_care_service())
    callback_handler2 = _handler(router2, "doctor_runtime_booking_callback")
    order_data = asyncio.run(codec2.encode(_booking_callback_payload(page_or_index="open_care_order", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    order_callback = _Callback(order_data, user_id=702)
    asyncio.run(callback_handler2(order_callback))
    order_text, order_kb = order_callback.message.edits[-1]
    assert "No booking-linked care order found for this booking." in order_text
    assert "care_order :: patient=" not in order_text
    assert order_kb.inline_keyboard[0][0].text == "Back"


def test_doctor_in_service_hands_off_into_encounter_context() -> None:
    router, codec, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service())
    callback_handler = _handler(router, "doctor_runtime_booking_callback")
    in_service_data = asyncio.run(
        codec.encode(_booking_callback_payload(page_or_index="in_service", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE))
    )
    in_service_callback = _Callback(in_service_data, user_id=702)
    asyncio.run(callback_handler(in_service_callback))
    text, kb = in_service_callback.message.edits[-1]
    assert "Encounter context" in text
    assert "Encounter: enc_b1" in text
    assert "Patient: Jane Roe" in text
    assert "Booking: b1 ·" in text
    assert [row[0].text for row in kb.inline_keyboard] == ["Complete encounter", "Issue recommendation", "Add quick note", "Back to booking"]


def test_doctor_legacy_booking_callback_is_bounded() -> None:
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service())
    callback_handler = _handler(router, "doctor_runtime_booking_callback_legacy")
    stale_callback = _Callback("doctorbk:unknown:b1", user_id=702)
    asyncio.run(callback_handler(stale_callback))
    assert stale_callback.answers and "outdated" in stale_callback.answers[0].lower()


def test_encounter_open_command_uses_canonical_encounter_panel() -> None:
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service())
    handler = _handler(router, "encounter_open", kind="message")
    message = _CommandMessage("/encounter_open p1 b1", user_id=702)
    asyncio.run(handler(message))
    text, kb = message.answers[-1]
    assert "Encounter context" in text
    assert "Encounter: enc_b1" in text
    assert "Patient: Jane Roe" in text
    assert "Booking: b1 ·" in text
    assert [row[0].text for row in kb.inline_keyboard] == ["Complete encounter", "Issue recommendation", "Add quick note", "Back to booking"]


def test_completed_encounter_hides_completion_and_contextual_actions() -> None:
    clinical = _ClinicalService(encounter_status="closed")
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), clinical_service=clinical)
    handler = _handler(router, "encounter_open", kind="message")
    message = _CommandMessage("/encounter_open p1 b1", user_id=702)
    asyncio.run(handler(message))
    _, kb = message.answers[-1]
    assert [row[0].text for row in kb.inline_keyboard] == ["Back to booking"]


def test_encounter_complete_click_shows_confirmation_prompt() -> None:
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), booking_status="in_service")
    handler = _handler(router, "doctor_encounter_complete_start")
    callback = _Callback("denc:complete:enc_b1:b1", user_id=702)
    asyncio.run(handler(callback))
    text, kb = callback.message.edits[-1]
    assert "Complete this encounter?" in text
    assert [row[0].text for row in kb.inline_keyboard] == ["Confirm", "Back"]


def test_encounter_complete_confirm_closes_and_returns_to_booking_continuity() -> None:
    clinical = _ClinicalService()
    router, _, clinical_service, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="in_service",
    )
    handler = _handler(router, "doctor_encounter_complete_confirm")
    callback = _Callback("denc:complete_confirm:enc_b1:b1", user_id=702)
    asyncio.run(handler(callback))
    assert clinical_service.closed_encounters == ["enc_b1"]
    text, kb = callback.message.edits[-1]
    assert "Encounter and booking completed." in text
    assert "[Completed]" in text
    actions = [row[0].text for row in kb.inline_keyboard]
    assert "Add quick note" not in actions
    assert "Issue recommendation" not in actions


def test_encounter_complete_confirm_keeps_terminal_booking_unchanged() -> None:
    clinical = _ClinicalService()
    router, _, clinical_service, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="canceled",
    )
    handler = _handler(router, "doctor_encounter_complete_confirm")
    callback = _Callback("denc:complete_confirm:enc_b1:b1", user_id=702)
    asyncio.run(handler(callback))
    assert clinical_service.closed_encounters == ["enc_b1"]
    text, _ = callback.message.edits[-1]
    assert "Booking stayed unchanged." in text
    assert "[Canceled]" in text


def test_encounter_complete_confirm_without_booking_keeps_encounter_only_path() -> None:
    clinical = _ClinicalService()
    router, _, clinical_service, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
    )
    handler = _handler(router, "doctor_encounter_complete_confirm")
    callback = _Callback("denc:complete_confirm:enc_b1:-", user_id=702)
    asyncio.run(handler(callback))
    assert clinical_service.closed_encounters == ["enc_b1"]
    text, _ = callback.message.edits[-1]
    assert "Encounter completed." in text
    assert "Encounter context" in text


def test_encounter_complete_confirm_invalid_booking_completion_is_bounded() -> None:
    clinical = _ClinicalService()
    router, _, clinical_service, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="confirmed",
    )
    handler = _handler(router, "doctor_encounter_complete_confirm")
    callback = _Callback("denc:complete_confirm:enc_b1:b1", user_id=702)
    asyncio.run(handler(callback))
    assert clinical_service.closed_encounters == ["enc_b1"]
    text, _ = callback.message.edits[-1]
    assert "Booking completion unavailable." in text
    assert "[Confirmed]" in text


def test_encounter_complete_abort_returns_to_encounter_context_without_mutation() -> None:
    clinical = _ClinicalService()
    router, _, clinical_service, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="in_service",
    )
    handler = _handler(router, "doctor_encounter_complete_abort")
    callback = _Callback("denc:complete_abort:enc_b1:b1", user_id=702)
    asyncio.run(handler(callback))
    assert clinical_service.closed_encounters == []
    text, kb = callback.message.edits[-1]
    assert "Encounter context" in text
    assert [row[0].text for row in kb.inline_keyboard] == ["Complete encounter", "Issue recommendation", "Add quick note", "Back to booking"]


def test_encounter_complete_stale_or_terminal_callbacks_are_bounded() -> None:
    clinical = _ClinicalService(encounter_status="closed")
    router, _, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="in_service",
    )
    confirm_handler = _handler(router, "doctor_encounter_complete_confirm")
    malformed_handler = _handler(router, "doctor_encounter_complete_start")
    terminal_callback = _Callback("denc:complete_confirm:enc_b1:b1", user_id=702)
    asyncio.run(confirm_handler(terminal_callback))
    assert terminal_callback.answers and "unavailable" in terminal_callback.answers[0].lower()
    malformed_callback = _Callback("denc:complete:oops", user_id=702)
    asyncio.run(malformed_handler(malformed_callback))
    assert malformed_callback.answers and "unavailable" in malformed_callback.answers[0].lower()


def test_doctor_booking_panel_add_quick_note_cta_only_for_in_service() -> None:
    router_in_service, codec, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    callback_handler = _handler(router_in_service, "doctor_runtime_booking_callback")
    open_data = asyncio.run(codec.encode(_booking_callback_payload(page_or_index="open_booking", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    open_callback = _Callback(open_data, user_id=702)
    asyncio.run(callback_handler(open_callback))
    _, kb = open_callback.message.edits[-1]
    actions = [row[0].text for row in kb.inline_keyboard]
    assert "Add quick note" in actions
    assert "Issue recommendation" in actions

    router_confirmed, codec2, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="confirmed",
    )
    callback_handler2 = _handler(router_confirmed, "doctor_runtime_booking_callback")
    open_data2 = asyncio.run(codec2.encode(_booking_callback_payload(page_or_index="open_booking", booking_id="b1", source_context=SourceContext.DOCTOR_QUEUE)))
    open_callback2 = _Callback(open_data2, user_id=702)
    asyncio.run(callback_handler2(open_callback2))
    _, kb2 = open_callback2.message.edits[-1]
    actions2 = [row[0].text for row in kb2.inline_keyboard]
    assert "Add quick note" not in actions2
    assert "Issue recommendation" not in actions2


def test_doctor_quick_note_type_and_capture_flow_calls_add_note_and_returns_context() -> None:
    clinical = _ClinicalService()
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), clinical_service=clinical, booking_status="in_service")
    start_handler = _handler(router, "doctor_encounter_quick_note_start")
    type_handler = _handler(router, "doctor_encounter_quick_note_type")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    start_callback = _Callback("dnote:start:enc_b1:b1", user_id=702)
    asyncio.run(start_handler(start_callback))
    start_text, _ = start_callback.message.edits[-1]
    assert "Choose note type" in start_text

    type_callback = _Callback("dnote:type:enc_b1:treatment:b1", user_id=702)
    asyncio.run(type_handler(type_callback))
    type_text, _ = type_callback.message.edits[-1]
    assert "Send note text" in type_text

    text_message = _CommandMessage("Patient is stable after treatment.", user_id=702)
    asyncio.run(capture_handler(text_message))
    assert clinical.saved_notes == [("enc_b1", "treatment", "Patient is stable after treatment.")]
    final_text, final_kb = text_message.answers[-1]
    assert "Note saved." in final_text
    assert "Encounter context" in final_text
    assert [row[0].text for row in final_kb.inline_keyboard] == ["Complete encounter", "Issue recommendation", "Add quick note", "Back to booking"]


def test_doctor_quick_note_text_without_pending_context_is_not_captured() -> None:
    clinical = _ClinicalService()
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), clinical_service=clinical, booking_status="in_service")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")
    message = _CommandMessage("Random plain message", user_id=702)
    asyncio.run(capture_handler(message))
    assert clinical.saved_notes == []
    assert message.answers == []


def test_doctor_pending_text_dispatcher_ignores_slash_commands() -> None:
    clinical = _ClinicalService()
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        clinical_service=clinical,
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_quick_note_type")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    asyncio.run(type_handler(_Callback("dnote:type:enc_b1:treatment:b1", user_id=702)))
    asyncio.run(capture_handler(_CommandMessage("/recommend_issue p1 aftercare b1 title|body", user_id=702)))
    assert clinical.saved_notes == []
    assert recommendation_service.created == []


def test_doctor_quick_note_malformed_type_callback_is_bounded() -> None:
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), booking_status="in_service")
    handler = _handler(router, "doctor_encounter_quick_note_type")
    callback = _Callback("dnote:type:enc_b1:badtype:b1", user_id=702)
    asyncio.run(handler(callback))
    assert callback.answers and "unavailable" in callback.answers[0].lower()


def test_doctor_recommendation_type_and_capture_flow_calls_issue_and_returns_context() -> None:
    clinical = _ClinicalService()
    care_service = _build_care_service()
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=care_service,
        clinical_service=clinical,
        booking_status="in_service",
    )
    start_handler = _handler(router, "doctor_encounter_recommendation_start")
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    start_callback = _Callback("drec:start:enc_b1:b1", user_id=702)
    asyncio.run(start_handler(start_callback))
    start_text, _ = start_callback.message.edits[-1]
    assert "Choose recommendation type" in start_text

    type_callback = _Callback("drec:type:enc_b1:aftercare:b1", user_id=702)
    asyncio.run(type_handler(type_callback))
    type_text, _ = type_callback.message.edits[-1]
    assert "Choose recommendation target option" in type_text

    target_none_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    target_none_callback = _Callback("drec:target:none:enc_b1:b1", user_id=702)
    asyncio.run(target_none_handler(target_none_callback))
    target_none_text, _ = target_none_callback.message.edits[-1]
    assert "Send recommendation as" in target_none_text

    text_message = _CommandMessage("Aftercare | Use a soft brush and avoid hard food for 48h.", user_id=702)
    asyncio.run(capture_handler(text_message))
    assert recommendation_service.created
    issued_payload = recommendation_service.created[-1]
    assert issued_payload["patient_id"] == "p1"
    assert issued_payload["recommendation_type"] == "aftercare"
    assert issued_payload["title"] == "Aftercare"
    assert issued_payload["body_text"] == "Use a soft brush and avoid hard food for 48h."
    assert issued_payload["booking_id"] == "b1"
    assert issued_payload["encounter_id"] == "enc_b1"
    assert care_service.manual_targets == []
    final_text, final_kb = text_message.answers[-1]
    assert "Recommendation saved." in final_text
    assert "Encounter context" in final_text
    assert [row[0].text for row in final_kb.inline_keyboard] == ["Complete encounter", "Issue recommendation", "Add quick note", "Back to booking"]


def test_doctor_recommendation_target_path_accepts_valid_product_target_and_persists_target() -> None:
    clinical = _ClinicalService()
    care_service = _build_care_service()
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=care_service,
        clinical_service=clinical,
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    target_mode_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    type_callback = _Callback("drec:type:enc_b1:aftercare:b1", user_id=702)
    asyncio.run(type_handler(type_callback))
    target_mode_callback = _Callback("drec:target:link:enc_b1:b1", user_id=702)
    asyncio.run(target_mode_handler(target_mode_callback))
    target_prompt_text, _ = target_mode_callback.message.edits[-1]
    assert "product:<code> or category:<code>" in target_prompt_text

    target_message = _CommandMessage("product:Post-op gel", user_id=702)
    asyncio.run(capture_handler(target_message))
    assert "Target saved: product:Post-op gel" in target_message.answers[0][0]

    text_message = _CommandMessage("Aftercare | Product-targeted body.", user_id=702)
    asyncio.run(capture_handler(text_message))
    assert recommendation_service.created
    assert care_service.manual_targets
    assert care_service.manual_targets[-1]["target_kind"] == "product"
    assert care_service.manual_targets[-1]["target_code"] == "Post-op gel"


def test_doctor_recommendation_target_path_accepts_valid_category_target() -> None:
    care_service = _build_care_service()
    router, _, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=care_service,
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    target_mode_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    asyncio.run(type_handler(_Callback("drec:type:enc_b1:aftercare:b1", user_id=702)))
    asyncio.run(target_mode_handler(_Callback("drec:target:link:enc_b1:b1", user_id=702)))
    target_message = _CommandMessage("category:hygiene", user_id=702)
    asyncio.run(capture_handler(target_message))
    assert "Target saved: category:hygiene" in target_message.answers[0][0]


def test_doctor_recommendation_target_invalid_is_bounded_and_does_not_crash() -> None:
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    target_mode_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    asyncio.run(type_handler(_Callback("drec:type:enc_b1:aftercare:b1", user_id=702)))
    asyncio.run(target_mode_handler(_Callback("drec:target:link:enc_b1:b1", user_id=702)))
    bad_target = _CommandMessage("product:missing", user_id=702)
    asyncio.run(capture_handler(bad_target))
    assert recommendation_service.created == []
    assert "Target not found." in bad_target.answers[-1][0]


def test_doctor_recommendation_malformed_target_callback_is_bounded() -> None:
    router, _, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    callback = _Callback("drec:target:oops", user_id=702)
    asyncio.run(handler(callback))
    assert callback.answers and "unavailable" in callback.answers[0].lower()


def test_doctor_recommendation_malformed_type_callback_is_bounded() -> None:
    router, _, _, _ = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    handler = _handler(router, "doctor_encounter_recommendation_type")
    callback = _Callback("drec:type:enc_b1:badtype:b1", user_id=702)
    asyncio.run(handler(callback))
    assert callback.answers and "unavailable" in callback.answers[0].lower()


def test_doctor_recommendation_cancel_clears_pending_context() -> None:
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    cancel_handler = _handler(router, "doctor_encounter_recommendation_cancel")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    asyncio.run(type_handler(_Callback("drec:type:enc_b1:aftercare:b1", user_id=702)))
    asyncio.run(cancel_handler(_Callback("drec:cancel:enc_b1:b1", user_id=702)))
    asyncio.run(capture_handler(_CommandMessage("Aftercare | should not capture", user_id=702)))
    assert recommendation_service.created == []


def test_doctor_recommendation_text_without_pending_context_is_not_captured() -> None:
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")
    message = _CommandMessage("Some free text message", user_id=702)
    asyncio.run(capture_handler(message))
    assert recommendation_service.created == []
    assert message.answers == []


def test_doctor_pending_text_dispatcher_handles_ambiguous_pending_state_by_newest_context() -> None:
    clinical = _ClinicalService()
    care_service = _build_care_service()
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=care_service,
        clinical_service=clinical,
        booking_status="in_service",
    )
    note_type_handler = _handler(router, "doctor_encounter_quick_note_type")
    recommendation_type_handler = _handler(router, "doctor_encounter_recommendation_type")
    target_mode_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")

    asyncio.run(note_type_handler(_Callback("dnote:type:enc_b1:treatment:b1", user_id=702)))
    asyncio.run(recommendation_type_handler(_Callback("drec:type:enc_b1:aftercare:b1", user_id=702)))
    asyncio.run(target_mode_handler(_Callback("drec:target:none:enc_b1:b1", user_id=702)))
    asyncio.run(capture_handler(_CommandMessage("Aftercare | Newer recommendation wins.", user_id=702)))

    assert clinical.saved_notes == []
    assert recommendation_service.created
    assert recommendation_service.created[-1]["title"] == "Aftercare"


def test_doctor_recommendation_capture_rejects_malformed_title_body() -> None:
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    type_handler = _handler(router, "doctor_encounter_recommendation_type")
    target_mode_handler = _handler(router, "doctor_encounter_recommendation_target_mode")
    capture_handler = _handler(router, "doctor_pending_text_capture", kind="message")
    type_callback = _Callback("drec:type:enc_b1:aftercare:b1", user_id=702)
    asyncio.run(type_handler(type_callback))
    asyncio.run(target_mode_handler(_Callback("drec:target:none:enc_b1:b1", user_id=702)))
    malformed = _CommandMessage("bad format without separator", user_id=702)
    asyncio.run(capture_handler(malformed))
    assert recommendation_service.created == []
    assert "Use format: Title | Body." in malformed.answers[-1][0]


def test_doctor_recommend_issue_command_fallback_still_works() -> None:
    router, _, _, recommendation_service = _doctor_router(
        recommendation_rows=[],
        care_service=_build_empty_care_service(),
        booking_status="in_service",
    )
    handler = _handler(router, "recommend_issue", kind="message")
    message = _CommandMessage("/recommend_issue p1 aftercare b1 Legacy|Legacy body", user_id=702)
    asyncio.run(handler(message))
    assert recommendation_service.created
    assert recommendation_service.created[-1]["recommendation_type"] == "aftercare"
    assert "Recommendation issued:" in message.answers[-1][0]


def test_doctor_encounter_note_command_fallback_still_works() -> None:
    clinical = _ClinicalService()
    router, _, _, _ = _doctor_router(recommendation_rows=[], care_service=_build_empty_care_service(), clinical_service=clinical)
    handler = _handler(router, "encounter_note", kind="message")
    message = _CommandMessage("/encounter_note enc_b1 other legacy command note", user_id=702)
    asyncio.run(handler(message))
    assert clinical.saved_notes == [("enc_b1", "other", "legacy command note")]
    assert "Encounter note saved" in message.answers[-1][0]


def test_doc_a2c_contains_no_new_migration_artifacts() -> None:
    migrations_root = Path("migrations")
    if not migrations_root.exists():
        return
    assert not any("doc_a2c" in path.name.lower() for path in migrations_root.rglob("*"))


def test_doc_a3a_contains_no_new_migration_artifacts() -> None:
    migrations_root = Path("migrations")
    if not migrations_root.exists():
        return
    assert not any("doc_a3a" in path.name.lower() for path in migrations_root.rglob("*"))
