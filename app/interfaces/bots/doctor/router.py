import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.access import AccessResolver
from app.application.booking import BookingOrchestrationService, BookingService, BookingStateService
from app.application.clinic_reference import ClinicReferenceService
from app.application.clinical import ClinicalChartService
from app.application.care_commerce import CareCommerceService
from app.application.doctor import DOCTOR_ALLOWED_ACTIONS, DoctorOperationsService, DoctorPatientReader
from app.application.export import (
    DocumentExportApplicationService,
    ExportAssemblyRequest,
    GeneratedArtifactDeliveryService,
    GeneratedDocumentRegistryService,
    MediaAssetRegistryService,
)
from app.application.export.services import TemplateResolutionError
from app.application.recommendation import PatientRecommendationDeliveryService, RecommendationService
from app.application.search.service import HybridSearchService
from app.application.voice import SpeechToTextService, VoiceSearchModeStore
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import build_role_router, guard_roles, resolve_locale
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search
from app.interfaces.bots.voice_search import attach_voice_search_handlers
from app.interfaces.cards import (
    BookingCardAdapter,
    BookingRuntimeSnapshot,
    BookingRuntimeViewBuilder,
    CareOrderCardAdapter,
    CareOrderRuntimeSnapshot,
    CareOrderRuntimeViewBuilder,
    CardAction,
    CardCallback,
    CardCallbackCodec,
    CardCallbackError,
    CardMode,
    CardProfile,
    CardRuntimeCoordinator,
    CardShellRenderer,
    EntityType,
    SourceContext,
    SourceRef,
)


def make_router(
    i18n: I18nService,
    access_resolver: AccessResolver,
    search_service: HybridSearchService,
    stt_service: SpeechToTextService,
    voice_mode_store: VoiceSearchModeStore,
    booking_service: BookingService | None = None,
    booking_state_service: BookingStateService | None = None,
    booking_orchestration: BookingOrchestrationService | None = None,
    reference_service: ClinicReferenceService | None = None,
    patient_reader: DoctorPatientReader | None = None,
    clinical_service: ClinicalChartService | None = None,
    recommendation_service: RecommendationService | None = None,
    recommendation_delivery_service: PatientRecommendationDeliveryService | None = None,
    care_commerce_service: CareCommerceService | None = None,
    document_export_service: DocumentExportApplicationService | None = None,
    generated_document_registry: GeneratedDocumentRegistryService | None = None,
    media_asset_registry: MediaAssetRegistryService | None = None,
    artifact_delivery: GeneratedArtifactDeliveryService | None = None,
    *,
    default_locale: str,
    max_voice_duration_sec: int,
    max_voice_file_size_bytes: int,
    voice_mode_ttl_sec: int,
    card_runtime: CardRuntimeCoordinator | None = None,
    card_callback_codec: CardCallbackCodec | None = None,
) -> Router:
    @dataclass(slots=True)
    class _PendingEncounterNote:
        doctor_id: str
        encounter_id: str
        note_type: str
        booking_id: str | None
        patient_id: str | None
        created_at: datetime

    @dataclass(slots=True)
    class _PendingEncounterRecommendation:
        doctor_id: str
        clinic_id: str
        patient_id: str
        encounter_id: str
        booking_id: str | None
        recommendation_type: str
        target_kind: str | None
        target_code: str | None
        awaiting_target_code: bool
        created_at: datetime

    search_backend = search_service
    router = build_role_router(
        role_key="doctor",
        i18n=i18n,
        locale=default_locale,
        access_resolver=access_resolver,
        required_role=RoleCode.DOCTOR,
    )

    attach_voice_search_handlers(
        router,
        i18n=i18n,
        access_resolver=access_resolver,
        search_service=search_service,
        stt_service=stt_service,
        mode_store=voice_mode_store,
        default_locale=default_locale,
        allowed_roles={RoleCode.DOCTOR},
        max_voice_duration_sec=max_voice_duration_sec,
        max_voice_file_size_bytes=max_voice_file_size_bytes,
        mode_ttl_sec=voice_mode_ttl_sec,
    )

    operations = (
        DoctorOperationsService(
            access_resolver=access_resolver,
            booking_service=booking_service,
            booking_state_service=booking_state_service,
            booking_orchestration=booking_orchestration,
            reference_service=reference_service,
            patient_reader=patient_reader,
            clinical_service=clinical_service,
            recommendation_service=recommendation_service,
            recommendation_delivery_service=recommendation_delivery_service,
            care_commerce_service=care_commerce_service,
            i18n=i18n,
        )
        if booking_service and booking_state_service and booking_orchestration and reference_service and patient_reader
        else None
    )
    booking_builder = BookingRuntimeViewBuilder()
    care_order_builder = CareOrderRuntimeViewBuilder()
    export_document_type = "043_card_export"
    delivery_service = artifact_delivery or GeneratedArtifactDeliveryService()
    pending_notes_by_user: dict[int, _PendingEncounterNote] = {}
    pending_recommendations_by_user: dict[int, _PendingEncounterRecommendation] = {}
    pending_note_ttl = timedelta(minutes=10)
    pending_recommendation_ttl = timedelta(minutes=10)
    allowed_quick_note_types = ("observation", "treatment", "follow_up", "other")
    allowed_recommendation_types = ("hygiene", "aftercare", "follow_up", "medication", "other")
    recommendation_type_map = {
        "hygiene": "hygiene_support",
        "aftercare": "aftercare",
        "follow_up": "follow_up",
        "medication": "next_step",
        "other": "general_guidance",
    }
    encounter_terminal_statuses = {"closed", "completed"}

    def _encounter_is_active(*, status: str) -> bool:
        return status not in encounter_terminal_statuses

    def _doc_status_label(*, status: str, locale: str) -> str:
        translated = i18n.t(f"document.status.{status}", locale)
        return translated if translated != f"document.status.{status}" else status

    def _doc_failure_hint(*, failure: str | None, locale: str) -> str:
        if not failure:
            return "-"
        lowered = failure.lower()
        if "template" in lowered:
            return i18n.t("document.error.template_resolution_failed", locale)
        return i18n.t("document.error.generation_failed", locale)

    def _resolve_booking_timezone(*, clinic_id: str, branch_id: str | None) -> str:
        if reference_service is None:
            return "UTC"
        if branch_id:
            branch = next((row for row in reference_service.list_branches(clinic_id) if row.branch_id == branch_id), None)
            if branch and branch.timezone:
                return branch.timezone
        clinic = reference_service.get_clinic(clinic_id)
        if clinic and clinic.timezone:
            return clinic.timezone
        return "UTC"

    async def _encode_booking_callback(*, booking_id: str, action: CardAction, page_or_index: str) -> str:
        if card_callback_codec is None:
            return f"doctorbk:{page_or_index}:{booking_id}"
        return await card_callback_codec.encode(
            CardCallback(
                profile=CardProfile.BOOKING,
                entity_type=EntityType.BOOKING,
                entity_id=booking_id,
                action=action,
                mode=CardMode.EXPANDED,
                source_context=SourceContext.DOCTOR_QUEUE,
                source_ref="doctor.booking.card",
                page_or_index=page_or_index,
                state_token=booking_id,
            )
        )

    async def _doctor_booking_shell(*, detail, locale: str):
        booking = await booking_service.load_booking(detail.booking_id) if booking_service else None
        if booking is None:
            return None
        seed = booking_builder.build_seed(
            snapshot=BookingRuntimeSnapshot(
                booking_id=detail.booking_id,
                state_token=detail.booking_id,
                role_variant="doctor",
                scheduled_start_at=booking.scheduled_start_at,
                timezone_name=_resolve_booking_timezone(clinic_id=booking.clinic_id, branch_id=booking.branch_id),
                patient_label=detail.patient_card.display_name,
                doctor_label=booking.doctor_id,
                service_label=detail.service_label,
                branch_label=detail.branch_label,
                status=detail.booking_status,
                source_channel=booking.source_channel,
                patient_contact=detail.patient_card.phone_hint,
                chart_summary_entry=detail.patient_card.active_flags_summary,
            ),
            i18n=i18n,
            locale=locale,
        )
        return BookingCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.DOCTOR_QUEUE, source_ref="doctor_queue"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.EXPANDED,
        )

    async def _doctor_booking_keyboard(*, detail, locale: str) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = []
        if detail.booking_status in {"checked_in", "confirmed"}:
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.in_service", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.IN_SERVICE, page_or_index="in_service"))])
        if detail.booking_status == "in_service":
            rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.complete", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.COMPLETE, page_or_index="complete"))])
            rows.append([InlineKeyboardButton(text=i18n.t("doctor.encounter.quick_note.add", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.OPEN, page_or_index="add_quick_note"))])
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.issue", locale),
                        callback_data=await _encode_booking_callback(
                            booking_id=detail.booking_id,
                            action=CardAction.OPEN,
                            page_or_index="add_recommendation",
                        ),
                    )
                ]
            )
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.patient", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.OPEN_PATIENT, page_or_index="open_patient"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.chart", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.OPEN_CHART, page_or_index="open_chart"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.recommendation", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.OPEN_RECOMMENDATION, page_or_index="open_recommendation"))])
        rows.append([InlineKeyboardButton(text=i18n.t("card.booking.action.care_order", locale), callback_data=await _encode_booking_callback(booking_id=detail.booking_id, action=CardAction.OPEN_CARE_ORDER, page_or_index="open_care_order"))])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def _doctor_linked_back_keyboard(*, booking_id: str, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("common.back", locale),
                        callback_data=await _encode_booking_callback(
                            booking_id=booking_id,
                            action=CardAction.OPEN,
                            page_or_index="open_booking",
                        ),
                    )
                ]
            ]
        )

    async def _doctor_encounter_keyboard(*, encounter, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        encounter_id = encounter.encounter_id
        rows: list[list[InlineKeyboardButton]] = []
        if _encounter_is_active(status=encounter.status):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.encounter.complete.cta", locale),
                        callback_data=f"denc:complete:{encounter_id}:{booking_id or '-'}",
                    )
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.issue", locale),
                        callback_data=f"drec:start:{encounter_id}:{booking_id or '-'}",
                    )
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.encounter.quick_note.add", locale),
                        callback_data=f"dnote:start:{encounter_id}:{booking_id or '-'}",
                    )
                ]
            )
        if booking_id:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.encounter.back_to_booking", locale),
                        callback_data=await _encode_booking_callback(
                            booking_id=booking_id,
                            action=CardAction.OPEN,
                            page_or_index="open_booking",
                        ),
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _doctor_encounter_complete_confirm_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        booking_token = booking_id or "-"
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.encounter.complete.confirm.cta", locale),
                        callback_data=f"denc:complete_confirm:{encounter_id}:{booking_token}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.encounter.complete.abort.cta", locale),
                        callback_data=f"denc:complete_abort:{encounter_id}:{booking_token}",
                    )
                ],
            ]
        )

    def _pop_pending_note(*, user_id: int) -> _PendingEncounterNote | None:
        ctx = pending_notes_by_user.get(user_id)
        if ctx is None:
            return None
        if datetime.now(timezone.utc) - ctx.created_at > pending_note_ttl:
            pending_notes_by_user.pop(user_id, None)
            return None
        return ctx

    def _clear_pending_note(*, user_id: int) -> None:
        pending_notes_by_user.pop(user_id, None)

    def _pop_pending_recommendation(*, user_id: int) -> _PendingEncounterRecommendation | None:
        ctx = pending_recommendations_by_user.get(user_id)
        if ctx is None:
            return None
        if datetime.now(timezone.utc) - ctx.created_at > pending_recommendation_ttl:
            pending_recommendations_by_user.pop(user_id, None)
            return None
        return ctx

    def _clear_pending_recommendation(*, user_id: int) -> None:
        pending_recommendations_by_user.pop(user_id, None)

    async def _resolve_owned_encounter(*, doctor_id: str, encounter_id: str):
        if operations is None or operations.clinical_service is None:
            return None
        encounter = await operations.clinical_service.repository.get_encounter(encounter_id)
        if encounter is None or encounter.doctor_id != doctor_id:
            return None
        return encounter

    def _quick_note_type_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        booking_token = booking_id or "-"
        rows = [
            [
                InlineKeyboardButton(
                    text=i18n.t(f"doctor.encounter.quick_note.type.{note_type}", locale),
                    callback_data=f"dnote:type:{encounter_id}:{note_type}:{booking_token}",
                )
            ]
            for note_type in allowed_quick_note_types
        ]
        rows.append([InlineKeyboardButton(text=i18n.t("doctor.encounter.quick_note.cancel", locale), callback_data=f"dnote:cancel:{encounter_id}:{booking_token}")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _recommendation_type_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        booking_token = booking_id or "-"
        rows = [
            [
                InlineKeyboardButton(
                    text=i18n.t(f"doctor.recommend.context.type.{recommendation_type}", locale),
                    callback_data=f"drec:type:{encounter_id}:{recommendation_type}:{booking_token}",
                )
            ]
            for recommendation_type in allowed_recommendation_types
        ]
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t("doctor.recommend.context.cancel", locale),
                    callback_data=f"drec:cancel:{encounter_id}:{booking_token}",
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _recommendation_target_mode_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        booking_token = booking_id or "-"
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.target.none", locale),
                        callback_data=f"drec:target:none:{encounter_id}:{booking_token}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.target.link", locale),
                        callback_data=f"drec:target:link:{encounter_id}:{booking_token}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.cancel", locale),
                        callback_data=f"drec:cancel:{encounter_id}:{booking_token}",
                    )
                ],
            ]
        )

    def _recommendation_target_capture_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        booking_token = booking_id or "-"
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.target.none", locale),
                        callback_data=f"drec:target:none:{encounter_id}:{booking_token}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.cancel", locale),
                        callback_data=f"drec:cancel:{encounter_id}:{booking_token}",
                    )
                ],
            ]
        )

    def _recommendation_capture_keyboard(*, encounter_id: str, booking_id: str | None, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.recommend.context.cancel", locale),
                        callback_data=f"drec:cancel:{encounter_id}:{booking_id or '-'}",
                    )
                ]
            ]
        )

    async def _validate_recommendation_target(
        *,
        clinic_id: str,
        raw_target: str,
    ) -> tuple[str, str] | None:
        care_service = operations.care_commerce_service if operations else None
        if care_service is None:
            return None
        payload = raw_target.strip()
        if ":" not in payload:
            return None
        raw_kind, raw_code = [piece.strip() for piece in payload.split(":", 1)]
        if not raw_kind or not raw_code:
            return None
        kind = raw_kind.lower()
        if kind == "product":
            product = await care_service.repository.get_product_by_code(clinic_id=clinic_id, target_code=raw_code)
            if product is None or product.status != "active":
                return None
            return ("product", raw_code)
        if kind == "category":
            products = await care_service.list_catalog_products_by_category(clinic_id=clinic_id, category=raw_code)
            active = [row for row in products if row.status == "active"]
            if not active:
                return None
            return ("category", raw_code)
        return None

    async def _render_doctor_encounter_panel(
        *,
        doctor_id: str,
        patient_id: str,
        encounter,
        locale: str,
        booking_detail=None,
    ) -> str:
        detail = booking_detail
        if detail is None:
            bookings = await booking_service.list_by_patient(patient_id=patient_id) if booking_service else []
            for row in sorted(bookings, key=lambda item: item.scheduled_start_at, reverse=True):
                if row.doctor_id != doctor_id:
                    continue
                detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=row.booking_id)
                if detail is not None:
                    break
        patient_display = patient_id
        booking_context = i18n.t("doctor.encounter.panel.booking_context.missing", locale)
        if detail is not None:
            patient_display = detail.patient_card.display_name
            booking_context = i18n.t("doctor.encounter.panel.booking_context", locale).format(
                booking_id=detail.booking_id,
                booking_time=detail.scheduled_label,
            )
        else:
            patient_card = await operations.build_patient_quick_card(patient_id=patient_id, doctor_id=doctor_id)
            if patient_card is not None:
                patient_display = patient_card.display_name
        return i18n.t("doctor.encounter.panel", locale).format(
            encounter_id=encounter.encounter_id,
            encounter_status=encounter.status,
            patient_display=patient_display,
            booking_context=booking_context,
        )

    async def _doctor_queue_keyboard(*, rows, locale: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=i18n.t("doctor.queue.open_booking_cta", locale).format(
                            time=row.scheduled_label,
                            patient=row.patient_display_name,
                        ),
                        callback_data=await _encode_booking_callback(
                            booking_id=row.booking_id,
                            action=CardAction.OPEN,
                            page_or_index="open_booking",
                        ),
                    )
                ]
                for row in rows
            ]
        )

    def _select_latest_recommendation(rows: list[object]) -> object | None:
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                getattr(row, "updated_at", None) or getattr(row, "created_at", None),
                getattr(row, "created_at", None),
                getattr(row, "recommendation_id", ""),
            ),
        )

    async def _render_linked_recommendation_panel(*, booking_id: str, locale: str) -> str:
        if recommendation_service is None:
            return i18n.t("staff.linked.recommendation.missing", locale)
        rows = await recommendation_service.list_for_booking(booking_id=booking_id)
        recommendation = _select_latest_recommendation(rows)
        if recommendation is None:
            return i18n.t("staff.linked.recommendation.missing", locale)
        recommendation_type_key = f"recommendation.type.{recommendation.recommendation_type}"
        recommendation_type = i18n.t(recommendation_type_key, locale)
        if recommendation_type == recommendation_type_key:
            recommendation_type = recommendation.recommendation_type
        recommendation_status_key = f"recommendation.status.{recommendation.status}"
        recommendation_status = i18n.t(recommendation_status_key, locale)
        if recommendation_status == recommendation_status_key:
            recommendation_status = recommendation.status
        body_or_rationale = recommendation.rationale_text or recommendation.body_text
        if body_or_rationale:
            body_or_rationale = str(body_or_rationale).strip()
        snippet = (body_or_rationale or "-")[:240]
        return i18n.t("staff.linked.recommendation.panel", locale).format(
            recommendation_id=recommendation.recommendation_id,
            title=recommendation.title,
            recommendation_type=recommendation_type,
            status=recommendation_status,
            snippet=snippet,
        )

    def _select_latest_care_order(rows: list[object], *, booking_id: str) -> object | None:
        linked = [row for row in rows if getattr(row, "booking_id", None) == booking_id]
        if not linked:
            return None
        return max(
            linked,
            key=lambda row: (
                getattr(row, "updated_at", None) or getattr(row, "created_at", None),
                getattr(row, "created_at", None),
                getattr(row, "care_order_id", ""),
            ),
        )

    async def _build_care_order_item_summary(*, order, locale: str) -> str:
        if care_commerce_service is None:
            return "-"
        items = await care_commerce_service.repository.list_order_items(order.care_order_id)
        if not items:
            return "-"
        labels: list[str] = []
        for item in items[:2]:
            product = await care_commerce_service.repository.get_product(item.care_product_id)
            if product is None:
                continue
            content = await care_commerce_service.resolve_product_content(
                clinic_id=order.clinic_id,
                product=product,
                locale=locale,
            )
            title = content.title or content.short_label or product.sku or product.care_product_id
            labels.append(f"{title} ×{item.quantity}")
        if not labels:
            return str(len(items))
        if len(items) > 2:
            labels.append(i18n.t("staff.linked.care_order.more_items", locale).format(count=len(items) - 2))
        return ", ".join(labels)

    async def _render_linked_care_order_panel(*, clinic_id: str, patient_id: str, booking_id: str, locale: str) -> str:
        if care_commerce_service is None:
            return i18n.t("staff.linked.care_order.missing", locale)
        orders = await care_commerce_service.list_patient_orders(clinic_id=clinic_id, patient_id=patient_id)
        care_order = _select_latest_care_order(orders, booking_id=booking_id)
        if care_order is None:
            return i18n.t("staff.linked.care_order.missing", locale)
        branch_label = "-"
        if care_order.pickup_branch_id and reference_service is not None:
            branch = next((row for row in reference_service.list_branches(clinic_id) if row.branch_id == care_order.pickup_branch_id), None)
            branch_label = branch.display_name if branch is not None else care_order.pickup_branch_id
        elif care_order.pickup_branch_id:
            branch_label = care_order.pickup_branch_id
        reservations = await care_commerce_service.repository.list_reservations_for_order(care_order_id=care_order.care_order_id)
        active_reservation = next((row for row in reservations if row.status == "active"), None)
        reservation_hint = (
            i18n.t("staff.linked.care_order.reservation.active", locale)
            if active_reservation
            else i18n.t("staff.linked.care_order.reservation.none", locale)
        )
        seed = care_order_builder.build_seed(
            snapshot=CareOrderRuntimeSnapshot(
                care_order_id=care_order.care_order_id,
                status=care_order.status,
                total_amount=care_order.total_amount,
                currency_code=care_order.currency_code,
                state_token=care_order.care_order_id,
                item_summary=await _build_care_order_item_summary(order=care_order, locale=locale),
                branch_label=branch_label,
                pickup_ready=care_order.status in {"ready_for_pickup", "issued", "fulfilled"},
                reservation_hint=reservation_hint,
                issued=care_order.status in {"issued", "fulfilled"},
                fulfilled=care_order.status == "fulfilled",
            ),
            i18n=i18n,
            locale=locale,
        )
        shell = CareOrderCardAdapter.build(
            seed=seed,
            source=SourceRef(context=SourceContext.DOCTOR_QUEUE, source_ref="doctor.booking.linked.care_order"),
            i18n=i18n,
            locale=locale,
            mode=CardMode.EXPANDED,
        )
        return CardShellRenderer.to_panel(shell).text

    async def _resolve_doctor_context(message: Message) -> tuple[str | None, str, str | None]:
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        if not message.from_user:
            return None, locale, None
        doctor_id, reason = access_resolver.resolve_doctor_id(message.from_user.id)
        if doctor_id is None:
            await message.answer(i18n.t(reason or "doctor.identity.unavailable", locale))
            return None, locale, None
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        return doctor_id, locale, actor.clinic_id if actor else None

    async def _guard_doctor(message: Message) -> bool:
        return await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.DOCTOR},
            fallback_locale=default_locale,
        )

    @router.message(Command("doctor_home"))
    async def doctor_home(message: Message) -> None:
        if not await _guard_doctor(message):
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        await message.answer(
            i18n.t("doctor.home.panel", locale).format(
                doctor_id=doctor_id,
                actions="/today_queue · /next_patient · /booking_open · /patient_open · /chart_open · /encounter_open · /recommend_issue",
            )
        )

    @router.message(Command("doc_generate"))
    async def doc_generate(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        actor = access_resolver.resolve_actor_context(message.from_user.id) if message.from_user else None
        if (
            doctor_id is None
            or clinic_id is None
            or actor is None
            or operations is None
            or booking_service is None
            or clinical_service is None
            or document_export_service is None
        ):
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split()
        if len(parts) not in {3, 4}:
            await message.answer(i18n.t("doctor.doc.generate.usage", locale))
            return
        patient_id = parts[1].strip()
        booking_id = parts[2].strip()
        template_locale = parts[3].strip().lower() if len(parts) == 4 else locale
        booking = await booking_service.load_booking(booking_id)
        if booking is None or booking.clinic_id != clinic_id or booking.doctor_id != doctor_id or booking.patient_id != patient_id:
            await message.answer(i18n.t("doctor.doc.generate.denied_or_missing", locale))
            return
        visible = await operations.build_patient_quick_card(patient_id=patient_id, doctor_id=doctor_id, require_visibility_guard=True)
        if visible is None:
            await message.answer(i18n.t("doctor.doc.generate.denied_or_missing", locale))
            return
        chart = await clinical_service.open_or_get_chart(patient_id=patient_id, clinic_id=clinic_id, primary_doctor_id=doctor_id)
        try:
            result = await document_export_service.generate_043_export(
                ExportAssemblyRequest(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    chart_id=chart.chart_id,
                    booking_id=booking_id,
                    template_type=export_document_type,
                    template_locale=template_locale,
                    assembled_by_actor_id=actor.actor_id,
                )
            )
        except TemplateResolutionError:
            await message.answer(i18n.t("document.error.template_resolution_failed", locale))
            return
        except Exception:
            await message.answer(i18n.t("document.error.generation_failed", locale))
            return
        await message.answer(
            i18n.t("doctor.doc.generate.ok", locale).format(
                generated_document_id=result.generated_document_id,
                booking_id=booking_id,
            )
        )

    @router.message(Command("doc_registry_booking"))
    async def doc_registry_booking(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or booking_service is None or generated_document_registry is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.doc.registry.booking.usage", locale))
            return
        booking_id = parts[1].strip()
        booking = await booking_service.load_booking(booking_id)
        if booking is None or booking.clinic_id != clinic_id or booking.doctor_id != doctor_id:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        rows = await generated_document_registry.list_for_booking(booking_id=booking_id)
        if not rows:
            await message.answer(i18n.t("doctor.doc.registry.empty", locale))
            return
        lines = [i18n.t("doctor.doc.registry.title", locale).format(scope=f"booking {booking_id}")]
        for row in rows[:10]:
            lines.append(
                i18n.t("doctor.doc.registry.row", locale).format(
                    generated_document_id=row.generated_document_id,
                    status=_doc_status_label(status=row.generation_status, locale=locale),
                    created_at=row.created_at.strftime("%Y-%m-%d %H:%M"),
                    failure=_doc_failure_hint(failure=row.generation_error_text, locale=locale),
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("doc_open"))
    async def doc_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None or generated_document_registry is None or media_asset_registry is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.doc.open.usage", locale))
            return
        generated_document_id = parts[1].strip()
        row = await generated_document_registry.get_generated_document(generated_document_id)
        if row is None or row.clinic_id != clinic_id:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        visible = await operations.build_patient_quick_card(patient_id=row.patient_id, doctor_id=doctor_id, require_visibility_guard=True)
        if visible is None:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        artifact_hint = i18n.t("doctor.doc.open.artifact_unavailable", locale)
        if row.generated_file_asset_id:
            asset = await media_asset_registry.get_media_asset(row.generated_file_asset_id)
            if asset:
                delivery = delivery_service.resolve(asset)
                if delivery.mode == "local_file":
                    artifact_hint = i18n.t("doctor.doc.open.download_hint", locale).format(generated_document_id=row.generated_document_id)
                elif delivery.mode == "unsupported_provider":
                    artifact_hint = i18n.t("document.delivery.unsupported_provider", locale)
        elif row.generation_status == "generated":
            artifact_hint = i18n.t("document.error.generated_missing_artifact", locale)
        await message.answer(
            i18n.t("doctor.doc.open.card", locale).format(
                generated_document_id=row.generated_document_id,
                document_type=row.document_type,
                status=_doc_status_label(status=row.generation_status, locale=locale),
                failure=_doc_failure_hint(failure=row.generation_error_text, locale=locale),
                artifact=artifact_hint,
            )
        )

    @router.message(Command("doc_download"))
    async def doc_download(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None or generated_document_registry is None or media_asset_registry is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.doc.download.usage", locale))
            return
        row = await generated_document_registry.get_generated_document(parts[1].strip())
        if row is None or row.clinic_id != clinic_id:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        visible = await operations.build_patient_quick_card(patient_id=row.patient_id, doctor_id=doctor_id, require_visibility_guard=True)
        if visible is None:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        if not row.generated_file_asset_id:
            await message.answer(i18n.t("doctor.doc.open.artifact_unavailable", locale))
            return
        asset = await media_asset_registry.get_media_asset(row.generated_file_asset_id)
        if asset is None:
            await message.answer(i18n.t("doctor.doc.open.artifact_unavailable", locale))
            return
        delivery = delivery_service.resolve(asset)
        if delivery.mode == "local_file" and delivery.path is not None:
            await message.answer_document(
                FSInputFile(path=str(delivery.path), filename=delivery.path.name),
                caption=i18n.t("doctor.doc.download.ok", locale).format(generated_document_id=row.generated_document_id),
            )
            return
        if delivery.mode == "unsupported_provider":
            await message.answer(i18n.t("document.delivery.unsupported_provider", locale))
            return
        await message.answer(i18n.t("doctor.doc.open.artifact_unavailable", locale))

    @router.message(Command("doc_regenerate"))
    async def doc_regenerate(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        actor = access_resolver.resolve_actor_context(message.from_user.id) if message.from_user else None
        if doctor_id is None or clinic_id is None or actor is None or operations is None or generated_document_registry is None or document_export_service is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.doc.regenerate.usage", locale))
            return
        source = await generated_document_registry.get_generated_document(parts[1].strip())
        if source is None or source.clinic_id != clinic_id:
            await message.answer(i18n.t("doctor.doc.registry.denied_or_missing", locale))
            return
        visible = await operations.build_patient_quick_card(patient_id=source.patient_id, doctor_id=doctor_id, require_visibility_guard=True)
        if visible is None or source.chart_id is None:
            await message.answer(i18n.t("doctor.doc.regenerate.not_supported", locale))
            return
        try:
            result = await document_export_service.generate_043_export(
                ExportAssemblyRequest(
                    clinic_id=source.clinic_id,
                    patient_id=source.patient_id,
                    chart_id=source.chart_id,
                    booking_id=source.booking_id,
                    encounter_id=source.encounter_id,
                    template_type=source.document_type,
                    template_locale=locale,
                    assembled_by_actor_id=actor.actor_id,
                )
            )
        except TemplateResolutionError:
            await message.answer(i18n.t("document.error.template_resolution_failed", locale))
            return
        except Exception:
            await message.answer(i18n.t("document.error.generation_failed", locale))
            return
        await message.answer(i18n.t("doctor.doc.regenerate.ok", locale).format(generated_document_id=result.generated_document_id))

    @router.message(Command("recommend_issue"))
    async def recommend_issue(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=5)
        if len(parts) < 5 or "|" not in parts[4]:
            await message.answer(i18n.t("doctor.recommend.issue.usage", locale))
            return
        patient_id = parts[1].strip()
        recommendation_type = parts[2].strip()
        booking_token = parts[3].strip()
        title, body = [x.strip() for x in parts[4].split("|", 1)]
        target_kind = None
        target_code = None
        if len(parts) > 5 and ":" in parts[5]:
            target_kind, target_code = [x.strip() for x in parts[5].split(":", 1)]
        booking_id = None if booking_token == "-" else booking_token
        try:
            recommendation = await operations.issue_recommendation(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=patient_id,
                recommendation_type=recommendation_type,
                title=title,
                body_text=body,
                booking_id=booking_id,
                target_kind=target_kind,
                target_code=target_code,
            )
        except ValueError:
            await message.answer(i18n.t("doctor.recommend.issue.invalid_type", locale))
            return
        if recommendation is None:
            await message.answer(i18n.t("doctor.recommend.issue.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.recommend.issue.ok", locale).format(recommendation_id=recommendation.recommendation_id))

    @router.message(Command("chart_open"))
    async def chart_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.chart.open.usage", locale))
            return
        card = await operations.open_chart_summary(doctor_id=doctor_id, clinic_id=clinic_id, patient_id=parts[1].strip())
        if card is None:
            await message.answer(i18n.t("doctor.chart.open.denied_or_missing", locale))
            return
        await message.answer(
            i18n.t("doctor.chart.summary.card", locale).format(
                chart_id=card.chart_id,
                patient_id=card.patient_id,
                status=card.status,
                diagnosis=card.latest_diagnosis_text or "-",
                plan=card.latest_treatment_plan_text or "-",
                note=card.latest_note_snippet or "-",
                note_count=card.note_count,
                imaging_count=card.imaging_count,
                updated_at=card.updated_at_label,
            )
        )

    @router.message(Command("encounter_open"))
    async def encounter_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.answer(i18n.t("doctor.encounter.open.usage", locale))
            return
        patient_id = parts[1].strip()
        booking_id = parts[2].strip() if len(parts) == 3 else None
        encounter = await operations.open_or_get_encounter(doctor_id=doctor_id, clinic_id=clinic_id, patient_id=patient_id, booking_id=booking_id)
        if encounter is None:
            await message.answer(i18n.t("doctor.encounter.open.denied_or_missing", locale))
            return
        booking_detail = None
        if booking_id:
            booking_detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=booking_id)
        await message.answer(
            await _render_doctor_encounter_panel(
                doctor_id=doctor_id,
                patient_id=patient_id,
                encounter=encounter,
                locale=locale,
                booking_detail=booking_detail,
            ),
            reply_markup=await _doctor_encounter_keyboard(encounter=encounter, booking_id=booking_id, locale=locale),
        )

    @router.message(Command("encounter_note"))
    async def encounter_note(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) != 4:
            await message.answer(i18n.t("doctor.encounter.note.usage", locale))
            return
        note = await operations.add_encounter_note(doctor_id=doctor_id, encounter_id=parts[1].strip(), note_type=parts[2].strip(), note_text=parts[3].strip())
        if note is None:
            await message.answer(i18n.t("doctor.encounter.note.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.encounter.note.ok", locale).format(note_id=note.encounter_note_id))

    @router.message(Command("diagnosis_set"))
    async def diagnosis_set(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            await message.answer(i18n.t("doctor.diagnosis.set.usage", locale))
            return
        result_id = await operations.set_chart_diagnosis(doctor_id=doctor_id, clinic_id=clinic_id, patient_id=parts[1].strip(), diagnosis_text=parts[2].strip())
        if result_id is None:
            await message.answer(i18n.t("doctor.chart.open.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.diagnosis.set.ok", locale).format(diagnosis_id=result_id))

    @router.message(Command("treatment_set"))
    async def treatment_set(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3 or "|" not in parts[2]:
            await message.answer(i18n.t("doctor.treatment.set.usage", locale))
            return
        title, plan_text = [x.strip() for x in parts[2].split("|", 1)]
        plan_id = await operations.set_chart_treatment_plan(
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            patient_id=parts[1].strip(),
            title=title,
            plan_text=plan_text,
        )
        if plan_id is None:
            await message.answer(i18n.t("doctor.chart.open.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.treatment.set.ok", locale).format(treatment_plan_id=plan_id))

    @router.message(Command("imaging_attach"))
    async def imaging_attach(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=3)
        if len(parts) < 4:
            await message.answer(i18n.t("doctor.imaging.attach.usage", locale))
            return
        patient_id = parts[1].strip()
        imaging_type = parts[2].strip()
        ref_token = parts[3].strip()
        media_asset_id = None
        external_url = None
        if ref_token.startswith("media:"):
            media_asset_id = ref_token.split("media:", 1)[1].strip()
        elif ref_token.startswith("url:"):
            external_url = ref_token.split("url:", 1)[1].strip()
        else:
            await message.answer(i18n.t("doctor.imaging.attach.usage", locale))
            return
        try:
            ref = await operations.attach_chart_imaging(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=patient_id,
                imaging_type=imaging_type,
                media_asset_id=media_asset_id,
                external_url=external_url,
            )
        except ValueError:
            await message.answer(i18n.t("doctor.imaging.attach.invalid", locale))
            return
        if ref is None:
            await message.answer(i18n.t("doctor.chart.open.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.imaging.attach.ok", locale).format(imaging_ref_id=ref.imaging_ref_id))

    @router.message(Command("odontogram_save"))
    async def odontogram_save(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, clinic_id = await _resolve_doctor_context(message)
        if doctor_id is None or clinic_id is None or operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            await message.answer(i18n.t("doctor.odontogram.save.usage", locale))
            return
        try:
            payload = json.loads(parts[2])
            if not isinstance(payload, dict):
                raise ValueError("payload")
        except (json.JSONDecodeError, ValueError):
            await message.answer(i18n.t("doctor.odontogram.save.invalid", locale))
            return
        snapshot = await operations.save_chart_odontogram(
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            patient_id=parts[1].strip(),
            snapshot_payload_json=payload,
        )
        if snapshot is None:
            await message.answer(i18n.t("doctor.chart.open.denied_or_missing", locale))
            return
        await message.answer(i18n.t("doctor.odontogram.save.ok", locale).format(snapshot_id=snapshot.odontogram_snapshot_id))

    @router.message(Command("today_queue"))
    async def today_queue(message: Message) -> None:
        if not await _guard_doctor(message):
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        if operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        rows = await operations.list_today_queue(doctor_id=doctor_id)
        if not rows:
            await message.answer(i18n.t("doctor.queue.empty", locale))
            return
        lines = [i18n.t("doctor.queue.title", locale)]
        for row in rows:
            lines.append(f"• {row.scheduled_label} · {row.patient_display_name} · {row.service_label}")
            lines.append(f"  {i18n.t(f'booking.status.{row.booking_status}', locale)}")
        await message.answer("\n".join(lines), reply_markup=await _doctor_queue_keyboard(rows=rows, locale=locale))

    @router.message(Command("next_patient"))
    async def next_patient(message: Message) -> None:
        if not await _guard_doctor(message):
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        if operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        row = await operations.get_next_patient(doctor_id=doctor_id)
        if row is None:
            await message.answer(i18n.t("doctor.next.empty", locale))
            return
        await message.answer(
            i18n.t("doctor.next.card", locale).format(
                time=row.scheduled_label,
                patient=row.patient_display_name,
                service=row.service_label,
                status=i18n.t(f"booking.status.{row.booking_status}", locale),
                booking_id=row.booking_id,
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=i18n.t("card.doctor.action.open", locale),
                            callback_data=await _encode_booking_callback(booking_id=row.booking_id, action=CardAction.OPEN, page_or_index="open_booking"),
                        )
                    ]
                ]
            ),
        )

    @router.message(Command("booking_open"))
    async def booking_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        if operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.booking.open.usage", locale))
            return
        detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=parts[1].strip())
        if detail is None:
            await message.answer(i18n.t("doctor.booking.open.missing", locale))
            return
        shell = await _doctor_booking_shell(detail=detail, locale=locale)
        if shell is None:
            await message.answer(i18n.t("doctor.booking.open.missing", locale))
            return
        await message.answer(CardShellRenderer.to_panel(shell).text, reply_markup=await _doctor_booking_keyboard(detail=detail, locale=locale))

    @router.callback_query(F.data.startswith("c2|"))
    async def doctor_runtime_booking_callback(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        if card_callback_codec is None:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, clinic_id = await _resolve_doctor_context(callback)
        if doctor_id is None or clinic_id is None or operations is None:
            return
        try:
            decoded = await card_callback_codec.decode(callback.data)
        except CardCallbackError:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        if decoded.source_context != SourceContext.DOCTOR_QUEUE or decoded.profile != CardProfile.BOOKING:
            return
        detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=decoded.entity_id)
        if detail is None:
            await callback.answer(i18n.t("doctor.booking.open.missing", locale), show_alert=True)
            return
        if decoded.page_or_index == "in_service":
            result = await operations.apply_booking_action(doctor_id=doctor_id, booking_id=detail.booking_id, action="in_service")
            if result.kind != "success":
                await callback.answer(i18n.t("doctor.booking.action.invalid", locale), show_alert=True)
                return
            encounter = await operations.open_or_get_encounter(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=detail.patient_card.patient_id,
                booking_id=detail.booking_id,
            )
            if encounter is None:
                await callback.answer(i18n.t("doctor.encounter.handoff.unavailable", locale), show_alert=True)
            else:
                await callback.message.edit_text(
                    await _render_doctor_encounter_panel(
                        doctor_id=doctor_id,
                        patient_id=detail.patient_card.patient_id,
                        encounter=encounter,
                        locale=locale,
                        booking_detail=detail,
                    ),
                    reply_markup=await _doctor_encounter_keyboard(encounter=encounter, booking_id=detail.booking_id, locale=locale),
                )
                return
            detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=detail.booking_id)
        elif decoded.page_or_index == "complete":
            await operations.apply_booking_action(doctor_id=doctor_id, booking_id=detail.booking_id, action="completed")
            detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=detail.booking_id)
        elif decoded.page_or_index == "open_patient":
            card = await operations.build_patient_quick_card(patient_id=detail.patient_card.patient_id, doctor_id=doctor_id)
            if card:
                await callback.message.edit_text(
                    i18n.t("doctor.patient.quick.card", locale).format(
                        patient_id=card.patient_id,
                        display_name=card.display_name,
                        patient_number=card.patient_number or "-",
                        phone_hint=card.phone_hint or "-",
                        has_photo=i18n.t("common.yes", locale) if card.has_photo else i18n.t("common.no", locale),
                        flags=card.active_flags_summary or "-",
                        next_booking=card.upcoming_booking_snippet or "-",
                    ),
                    reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
                )
            return
        elif decoded.page_or_index == "open_chart":
            chart = await operations.open_chart_summary(doctor_id=doctor_id, clinic_id=clinic_id, patient_id=detail.patient_card.patient_id)
            if chart:
                await callback.message.edit_text(
                    i18n.t("doctor.chart.summary.card", locale).format(
                        chart_id=chart.chart_id,
                        patient_id=chart.patient_id,
                        status=chart.status,
                        diagnosis=chart.latest_diagnosis_text or "-",
                        plan=chart.latest_treatment_plan_text or "-",
                        note=chart.latest_note_snippet or "-",
                        note_count=chart.note_count,
                        imaging_count=chart.imaging_count,
                        updated_at=chart.updated_at_label,
                    ),
                    reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
                )
            return
        elif decoded.page_or_index == "open_recommendation":
            await callback.message.edit_text(
                await _render_linked_recommendation_panel(booking_id=detail.booking_id, locale=locale),
                reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "open_care_order":
            await callback.message.edit_text(
                await _render_linked_care_order_panel(
                    clinic_id=clinic_id,
                    patient_id=detail.patient_card.patient_id,
                    booking_id=detail.booking_id,
                    locale=locale,
                ),
                reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "add_quick_note":
            if detail.booking_status != "in_service":
                await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
                return
            encounter = await operations.open_or_get_encounter(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=detail.patient_card.patient_id,
                booking_id=detail.booking_id,
            )
            if encounter is None:
                await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
                return
            await callback.message.edit_text(
                i18n.t("doctor.encounter.quick_note.choose_type", locale),
                reply_markup=_quick_note_type_keyboard(encounter_id=encounter.encounter_id, booking_id=detail.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "add_recommendation":
            if detail.booking_status != "in_service":
                await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
                return
            encounter = await operations.open_or_get_encounter(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=detail.patient_card.patient_id,
                booking_id=detail.booking_id,
            )
            if encounter is None:
                await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
                return
            await callback.message.edit_text(
                i18n.t("doctor.recommend.context.choose_type", locale),
                reply_markup=_recommendation_type_keyboard(encounter_id=encounter.encounter_id, booking_id=detail.booking_id, locale=locale),
            )
            return
        if detail is None:
            await callback.answer(i18n.t("doctor.booking.open.missing", locale), show_alert=True)
            return
        shell = await _doctor_booking_shell(detail=detail, locale=locale)
        if shell is None:
            return
        await callback.message.edit_text(CardShellRenderer.to_panel(shell).text, reply_markup=await _doctor_booking_keyboard(detail=detail, locale=locale))

    @router.callback_query(F.data.startswith("doctorbk:"))
    async def doctor_runtime_booking_callback_legacy(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, clinic_id = await _resolve_doctor_context(callback)
        if doctor_id is None or clinic_id is None or operations is None:
            return
        parts = callback.data.split(":", maxsplit=2)
        if len(parts) != 3:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        _, page_or_index, booking_id = parts
        if page_or_index not in {"open_booking", "in_service", "complete", "open_patient", "open_chart", "open_recommendation", "open_care_order", "add_quick_note", "add_recommendation"}:
            await callback.answer(i18n.t("common.card.callback.stale", locale), show_alert=True)
            return
        shell = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=booking_id)
        if shell is None:
            await callback.answer(i18n.t("doctor.booking.open.missing", locale), show_alert=True)
            return
        if page_or_index == "add_quick_note":
            if shell.booking_status != "in_service":
                await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
                return
            encounter = await operations.open_or_get_encounter(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=shell.patient_card.patient_id,
                booking_id=shell.booking_id,
            )
            if encounter is None:
                await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
                return
            await callback.message.edit_text(
                i18n.t("doctor.encounter.quick_note.choose_type", locale),
                reply_markup=_quick_note_type_keyboard(encounter_id=encounter.encounter_id, booking_id=shell.booking_id, locale=locale),
            )
            return
        if page_or_index == "add_recommendation":
            if shell.booking_status != "in_service":
                await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
                return
            encounter = await operations.open_or_get_encounter(
                doctor_id=doctor_id,
                clinic_id=clinic_id,
                patient_id=shell.patient_card.patient_id,
                booking_id=shell.booking_id,
            )
            if encounter is None:
                await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
                return
            await callback.message.edit_text(
                i18n.t("doctor.recommend.context.choose_type", locale),
                reply_markup=_recommendation_type_keyboard(encounter_id=encounter.encounter_id, booking_id=shell.booking_id, locale=locale),
            )
            return
        card = await _doctor_booking_shell(detail=shell, locale=locale)
        if card is None:
            await callback.answer(i18n.t("doctor.booking.open.missing", locale), show_alert=True)
            return
        await callback.message.edit_text(
            CardShellRenderer.to_panel(card).text,
            reply_markup=await _doctor_booking_keyboard(detail=shell, locale=locale),
        )

    @router.callback_query(F.data.startswith("denc:complete:"))
    async def doctor_encounter_complete_start(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None:
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        booking_id = None if parts[3].strip() in {"", "-"} else parts[3].strip()
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        await callback.message.edit_text(
            i18n.t("doctor.encounter.complete.confirm.prompt", locale),
            reply_markup=_doctor_encounter_complete_confirm_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("denc:complete_abort:"))
    async def doctor_encounter_complete_abort(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None:
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        booking_id = None if parts[3].strip() in {"", "-"} else parts[3].strip()
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None:
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        await callback.message.edit_text(
            await _render_doctor_encounter_panel(
                doctor_id=doctor_id,
                patient_id=getattr(encounter, "patient_id", ""),
                encounter=encounter,
                locale=locale,
            ),
            reply_markup=await _doctor_encounter_keyboard(encounter=encounter, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("denc:complete_confirm:"))
    async def doctor_encounter_complete_confirm(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None or operations is None:
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        booking_id = None if parts[3].strip() in {"", "-"} else parts[3].strip()
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        completed = await operations.complete_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if completed is None or _encounter_is_active(status=completed.status):
            await callback.answer(i18n.t("doctor.encounter.complete.unavailable", locale), show_alert=True)
            return
        if booking_id:
            detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=booking_id)
            if detail is not None:
                shell = await _doctor_booking_shell(detail=detail, locale=locale)
                if shell is not None:
                    await callback.message.edit_text(
                        f"{i18n.t('doctor.encounter.complete.success', locale)}\n\n{CardShellRenderer.to_panel(shell).text}",
                        reply_markup=await _doctor_booking_keyboard(detail=detail, locale=locale),
                    )
                    return
        await callback.message.edit_text(
            f"{i18n.t('doctor.encounter.complete.success', locale)}\n\n"
            + await _render_doctor_encounter_panel(
                doctor_id=doctor_id,
                patient_id=getattr(completed, "patient_id", ""),
                encounter=completed,
                locale=locale,
            ),
            reply_markup=await _doctor_encounter_keyboard(encounter=completed, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("dnote:start:"))
    async def doctor_encounter_quick_note_start(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None:
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        booking_id = None if parts[3].strip() in {"", "-"} else parts[3].strip()
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            _clear_pending_note(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
            return
        await callback.message.edit_text(
            i18n.t("doctor.encounter.quick_note.choose_type", locale),
            reply_markup=_quick_note_type_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("dnote:type:"))
    async def doctor_encounter_quick_note_type(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None:
            return
        parts = callback.data.split(":", maxsplit=4)
        if len(parts) != 5:
            await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        note_type = parts[3].strip()
        booking_id = None if parts[4].strip() in {"", "-"} else parts[4].strip()
        if note_type not in allowed_quick_note_types:
            await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
            return
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            _clear_pending_note(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale), show_alert=True)
            return
        pending_notes_by_user[callback.from_user.id] = _PendingEncounterNote(
            doctor_id=doctor_id,
            encounter_id=encounter_id,
            note_type=note_type,
            booking_id=booking_id,
            patient_id=getattr(encounter, "patient_id", None),
            created_at=datetime.now(timezone.utc),
        )
        await callback.message.edit_text(
            i18n.t("doctor.encounter.quick_note.send_text", locale),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=i18n.t("doctor.encounter.quick_note.cancel", locale),
                            callback_data=f"dnote:cancel:{encounter_id}:{booking_id or '-'}",
                        )
                    ]
                ]
            ),
        )

    @router.callback_query(F.data.startswith("dnote:cancel:"))
    async def doctor_encounter_quick_note_cancel(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        _clear_pending_note(user_id=callback.from_user.id)
        await callback.answer(i18n.t("doctor.encounter.quick_note.canceled", locale), show_alert=True)

    @router.callback_query(F.data.startswith("drec:start:"))
    async def doctor_encounter_recommendation_start(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, _ = await _resolve_doctor_context(callback)
        if doctor_id is None:
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        booking_id = None if parts[3].strip() in {"", "-"} else parts[3].strip()
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            _clear_pending_recommendation(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        await callback.message.edit_text(
            i18n.t("doctor.recommend.context.choose_type", locale),
            reply_markup=_recommendation_type_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("drec:type:"))
    async def doctor_encounter_recommendation_type(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        doctor_id, _, clinic_id = await _resolve_doctor_context(callback)
        if doctor_id is None or clinic_id is None:
            return
        parts = callback.data.split(":", maxsplit=4)
        if len(parts) != 5:
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        encounter_id = parts[2].strip()
        recommendation_type = parts[3].strip()
        booking_id = None if parts[4].strip() in {"", "-"} else parts[4].strip()
        if recommendation_type not in allowed_recommendation_types:
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        encounter = await _resolve_owned_encounter(doctor_id=doctor_id, encounter_id=encounter_id)
        if encounter is None or not _encounter_is_active(status=encounter.status):
            _clear_pending_recommendation(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        pending_recommendations_by_user[callback.from_user.id] = _PendingEncounterRecommendation(
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            patient_id=getattr(encounter, "patient_id", ""),
            encounter_id=encounter_id,
            booking_id=booking_id,
            recommendation_type=recommendation_type_map[recommendation_type],
            target_kind=None,
            target_code=None,
            awaiting_target_code=False,
            created_at=datetime.now(timezone.utc),
        )
        await callback.message.edit_text(
            i18n.t("doctor.recommend.context.target.choose", locale),
            reply_markup=_recommendation_target_mode_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
        )

    @router.callback_query(F.data.startswith("drec:target:"))
    async def doctor_encounter_recommendation_target_mode(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.data:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        parts = callback.data.split(":", maxsplit=4)
        if len(parts) != 5:
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        mode = parts[2].strip()
        encounter_id = parts[3].strip()
        booking_id = None if parts[4].strip() in {"", "-"} else parts[4].strip()
        pending = _pop_pending_recommendation(user_id=callback.from_user.id)
        if pending is None or pending.encounter_id != encounter_id or pending.booking_id != booking_id:
            _clear_pending_recommendation(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        if mode == "none":
            pending.awaiting_target_code = False
            pending.target_kind = None
            pending.target_code = None
            await callback.message.edit_text(
                i18n.t("doctor.recommend.context.send_text", locale),
                reply_markup=_recommendation_capture_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
            )
            return
        if mode == "link":
            pending.awaiting_target_code = True
            pending.target_kind = None
            pending.target_code = None
            await callback.message.edit_text(
                i18n.t("doctor.recommend.context.target.enter", locale),
                reply_markup=_recommendation_target_capture_keyboard(encounter_id=encounter_id, booking_id=booking_id, locale=locale),
            )
            return
        _clear_pending_recommendation(user_id=callback.from_user.id)
        await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
        return

    @router.callback_query(F.data.startswith("drec:cancel:"))
    async def doctor_encounter_recommendation_cancel(callback: CallbackQuery) -> None:
        if not callback.from_user:
            return
        locale = await resolve_locale(callback, access_resolver=access_resolver, fallback_locale=default_locale)
        if not callback.data:
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        parts = callback.data.split(":", maxsplit=3)
        if len(parts) != 4:
            _clear_pending_recommendation(user_id=callback.from_user.id)
            await callback.answer(i18n.t("doctor.recommend.context.unavailable", locale), show_alert=True)
            return
        _clear_pending_recommendation(user_id=callback.from_user.id)
        await callback.answer(i18n.t("doctor.recommend.context.canceled", locale), show_alert=True)

    @router.message(Command("patient_open"))
    async def patient_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        if operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("doctor.patient.open.usage", locale))
            return
        card = await operations.build_patient_quick_card(patient_id=parts[1].strip(), doctor_id=doctor_id)
        if card is None:
            await message.answer(i18n.t("doctor.patient.open.denied_or_missing", locale))
            return
        await message.answer(
            i18n.t("doctor.patient.quick.card", locale).format(
                patient_id=card.patient_id,
                display_name=card.display_name,
                patient_number=card.patient_number or "-",
                phone_hint=card.phone_hint or "-",
                has_photo=i18n.t("common.yes", locale) if card.has_photo else i18n.t("common.no", locale),
                flags=card.active_flags_summary or "-",
                next_booking=card.upcoming_booking_snippet or "-",
            )
        )

    @router.message(Command("booking_action"))
    async def booking_action(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale, _ = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        if operations is None:
            await message.answer(i18n.t("doctor.surface.unavailable", locale))
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) != 3:
            await message.answer(i18n.t("doctor.booking.action.usage", locale))
            return
        result = await operations.apply_booking_action(doctor_id=doctor_id, booking_id=parts[1].strip(), action=parts[2].strip())
        if result.kind != "success":
            await message.answer(i18n.t("doctor.booking.action.invalid", locale))
            return
        detail = await operations.get_booking_detail(doctor_id=doctor_id, booking_id=parts[1].strip())
        if detail is None:
            await message.answer(i18n.t("doctor.booking.open.missing", locale))
            return
        await message.answer(
            i18n.t("doctor.booking.action.ok", locale).format(
                booking_id=parts[1].strip(),
                status=i18n.t(f"booking.status.{detail.booking_status}", locale),
            )
        )

    @router.message(Command("search_patient"))
    async def search_patient(message: Message) -> None:
        if not await _guard_doctor(message) or not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        query = message.text.replace("/search_patient", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.patient", locale))
            return
        await message.answer(
            await run_patient_search(
                service=search_backend,
                i18n=i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=query,
            )
        )
        if query.startswith("id:") and operations:
            doctor_id, _, _ = await _resolve_doctor_context(message)
            patient_id = query.split("id:", 1)[1].strip()
            if doctor_id and patient_id:
                card = await operations.build_patient_quick_card(patient_id=patient_id, doctor_id=doctor_id)
                if card:
                    await message.answer(
                        i18n.t("doctor.search.patient.quick_hint", locale).format(
                            patient_id=card.patient_id,
                            display_name=card.display_name,
                            open_cmd=f"/patient_open {card.patient_id}",
                        )
                    )

    @router.message(Command("search_doctor"))
    async def search_doctor(message: Message) -> None:
        if not await _guard_doctor(message) or not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        query = message.text.replace("/search_doctor", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.doctor", locale))
            return
        await message.answer(
            await run_doctor_search(
                service=search_backend,
                i18n=i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=query,
            )
        )

    @router.message(Command("search_service"))
    async def search_service(message: Message) -> None:
        if not await _guard_doctor(message) or not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if not actor:
            return
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        query = message.text.replace("/search_service", "", 1).strip()
        if not query:
            await message.answer(i18n.t("search.usage.service", locale))
            return
        await message.answer(
            await run_service_search(
                service=search_backend,
                i18n=i18n,
                locale=locale,
                clinic_id=actor.clinic_id,
                query=query,
            )
        )

    async def _capture_pending_quick_note_text(*, message: Message, locale: str, pending: _PendingEncounterNote) -> None:
        if operations is None:
            _clear_pending_note(user_id=message.from_user.id)
            await message.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale))
            return
        note = await operations.add_encounter_note(
            doctor_id=pending.doctor_id,
            encounter_id=pending.encounter_id,
            note_type=pending.note_type,
            note_text=message.text.strip(),
        )
        _clear_pending_note(user_id=message.from_user.id)
        if note is None:
            await message.answer(i18n.t("doctor.encounter.quick_note.unavailable", locale))
            return
        encounter = await _resolve_owned_encounter(doctor_id=pending.doctor_id, encounter_id=pending.encounter_id)
        if encounter is None:
            await message.answer(i18n.t("doctor.encounter.quick_note.saved", locale))
            return
        booking_detail = None
        if pending.booking_id:
            booking_detail = await operations.get_booking_detail(doctor_id=pending.doctor_id, booking_id=pending.booking_id)
        panel = await _render_doctor_encounter_panel(
            doctor_id=pending.doctor_id,
            patient_id=pending.patient_id or getattr(encounter, "patient_id", ""),
            encounter=encounter,
            locale=locale,
            booking_detail=booking_detail,
        )
        await message.answer(
            f"{i18n.t('doctor.encounter.quick_note.saved', locale)}\n\n{panel}",
            reply_markup=await _doctor_encounter_keyboard(encounter=encounter, booking_id=pending.booking_id, locale=locale),
        )

    async def _capture_pending_recommendation_text(*, message: Message, locale: str, pending: _PendingEncounterRecommendation) -> None:
        if operations is None:
            _clear_pending_recommendation(user_id=message.from_user.id)
            await message.answer(i18n.t("doctor.recommend.context.unavailable", locale))
            return
        if pending.awaiting_target_code:
            validated_target = await _validate_recommendation_target(clinic_id=pending.clinic_id, raw_target=message.text)
            if validated_target is None:
                await message.answer(
                    i18n.t("doctor.recommend.context.target.invalid", locale),
                    reply_markup=_recommendation_target_capture_keyboard(
                        encounter_id=pending.encounter_id,
                        booking_id=pending.booking_id,
                        locale=locale,
                    ),
                )
                return
            pending.target_kind, pending.target_code = validated_target
            pending.awaiting_target_code = False
            await message.answer(
                i18n.t("doctor.recommend.context.target.saved", locale).format(
                    target_kind=pending.target_kind,
                    target_code=pending.target_code,
                )
            )
            await message.answer(
                i18n.t("doctor.recommend.context.send_text", locale),
                reply_markup=_recommendation_capture_keyboard(
                    encounter_id=pending.encounter_id,
                    booking_id=pending.booking_id,
                    locale=locale,
                ),
            )
            return
        if "|" not in message.text:
            await message.answer(i18n.t("doctor.recommend.context.invalid_format", locale))
            return
        title, body = [part.strip() for part in message.text.split("|", 1)]
        if not title or not body:
            await message.answer(i18n.t("doctor.recommend.context.invalid_format", locale))
            return
        try:
            recommendation = await operations.issue_recommendation(
                doctor_id=pending.doctor_id,
                clinic_id=pending.clinic_id,
                patient_id=pending.patient_id,
                recommendation_type=pending.recommendation_type,
                title=title,
                body_text=body,
                booking_id=pending.booking_id,
                encounter_id=pending.encounter_id,
                target_kind=pending.target_kind,
                target_code=pending.target_code,
            )
        except ValueError:
            _clear_pending_recommendation(user_id=message.from_user.id)
            await message.answer(i18n.t("doctor.recommend.context.unavailable", locale))
            return
        _clear_pending_recommendation(user_id=message.from_user.id)
        if recommendation is None:
            await message.answer(i18n.t("doctor.recommend.context.unavailable", locale))
            return
        encounter = await _resolve_owned_encounter(doctor_id=pending.doctor_id, encounter_id=pending.encounter_id)
        if encounter is None:
            await message.answer(i18n.t("doctor.recommend.context.saved", locale))
            return
        booking_detail = None
        if pending.booking_id:
            booking_detail = await operations.get_booking_detail(doctor_id=pending.doctor_id, booking_id=pending.booking_id)
        panel = await _render_doctor_encounter_panel(
            doctor_id=pending.doctor_id,
            patient_id=pending.patient_id or getattr(encounter, "patient_id", ""),
            encounter=encounter,
            locale=locale,
            booking_detail=booking_detail,
        )
        await message.answer(
            f"{i18n.t('doctor.recommend.context.saved', locale)}\n\n{panel}",
            reply_markup=await _doctor_encounter_keyboard(encounter=encounter, booking_id=pending.booking_id, locale=locale),
        )

    @router.message(F.text)
    async def doctor_pending_text_capture(message: Message) -> None:
        if not message.from_user or not message.text or message.text.startswith("/"):
            return
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        pending = _pop_pending_note(user_id=message.from_user.id)
        pending_recommendation = _pop_pending_recommendation(user_id=message.from_user.id)
        if pending and pending_recommendation:
            if pending_recommendation.created_at > pending.created_at:
                _clear_pending_note(user_id=message.from_user.id)
                pending = None
            else:
                _clear_pending_recommendation(user_id=message.from_user.id)
                pending_recommendation = None
        if pending:
            await _capture_pending_quick_note_text(message=message, locale=locale, pending=pending)
            return
        if pending_recommendation:
            await _capture_pending_recommendation_text(message=message, locale=locale, pending=pending_recommendation)
            return

    return router
