import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.access import AccessResolver
from app.application.booking import BookingOrchestrationService, BookingService, BookingStateService
from app.application.clinic_reference import ClinicReferenceService
from app.application.clinical import ClinicalChartService
from app.application.doctor import DOCTOR_ALLOWED_ACTIONS, DoctorOperationsService, DoctorPatientReader
from app.application.recommendation import RecommendationService
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
    *,
    default_locale: str,
    max_voice_duration_sec: int,
    max_voice_file_size_bytes: int,
    voice_mode_ttl_sec: int,
    card_runtime: CardRuntimeCoordinator | None = None,
    card_callback_codec: CardCallbackCodec | None = None,
) -> Router:
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
            i18n=i18n,
        )
        if booking_service and booking_state_service and booking_orchestration and reference_service and patient_reader
        else None
    )
    booking_builder = BookingRuntimeViewBuilder()

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
        await message.answer(i18n.t("doctor.encounter.open.ok", locale).format(encounter_id=encounter.encounter_id, status=encounter.status))

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
            lines.append(f"  {i18n.t(f'booking.status.{row.booking_status}', locale)} · /booking_open {row.booking_id}")
        await message.answer("\n".join(lines))

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
            await operations.apply_booking_action(doctor_id=doctor_id, booking_id=detail.booking_id, action="in_service")
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
            if recommendation_service is None:
                return
            recs = await recommendation_service.list_for_patient(patient_id=detail.patient_card.patient_id, include_terminal=False)
            await callback.message.edit_text(
                recs[0].title if recs else "-",
                reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
            )
            return
        elif decoded.page_or_index == "open_care_order":
            await callback.message.edit_text(
                f"care_order :: patient={detail.patient_card.patient_id}",
                reply_markup=await _doctor_linked_back_keyboard(booking_id=detail.booking_id, locale=locale),
            )
            return
        if detail is None:
            await callback.answer(i18n.t("doctor.booking.open.missing", locale), show_alert=True)
            return
        shell = await _doctor_booking_shell(detail=detail, locale=locale)
        if shell is None:
            return
        await callback.message.edit_text(CardShellRenderer.to_panel(shell).text, reply_markup=await _doctor_booking_keyboard(detail=detail, locale=locale))

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

    return router
