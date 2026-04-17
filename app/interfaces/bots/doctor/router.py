from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.application.access import AccessResolver
from app.application.booking import BookingOrchestrationService, BookingService, BookingStateService
from app.application.clinic_reference import ClinicReferenceService
from app.application.doctor import DOCTOR_ALLOWED_ACTIONS, DoctorOperationsService, DoctorPatientReader
from app.application.search.service import HybridSearchService
from app.application.voice import SpeechToTextService, VoiceSearchModeStore
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import build_role_router, guard_roles, resolve_locale
from app.interfaces.bots.search_handlers import run_doctor_search, run_patient_search, run_service_search
from app.interfaces.bots.voice_search import attach_voice_search_handlers


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
    *,
    default_locale: str,
    max_voice_duration_sec: int,
    max_voice_file_size_bytes: int,
    voice_mode_ttl_sec: int,
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
        )
        if booking_service and booking_state_service and booking_orchestration and reference_service and patient_reader
        else None
    )

    async def _resolve_doctor_context(message: Message) -> tuple[str | None, str]:
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        if not message.from_user:
            return None, locale
        doctor_id, reason = access_resolver.resolve_doctor_id(message.from_user.id)
        if doctor_id is None:
            await message.answer(i18n.t(reason or "doctor.identity.unavailable", locale))
            return None, locale
        return doctor_id, locale

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
        doctor_id, locale = await _resolve_doctor_context(message)
        if doctor_id is None:
            return
        await message.answer(
            i18n.t("doctor.home.panel", locale).format(
                doctor_id=doctor_id,
                actions="/today_queue · /next_patient · /search_patient · /search_doctor · /search_service · /voice_find_patient",
            )
        )

    @router.message(Command("today_queue"))
    async def today_queue(message: Message) -> None:
        if not await _guard_doctor(message):
            return
        doctor_id, locale = await _resolve_doctor_context(message)
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
        doctor_id, locale = await _resolve_doctor_context(message)
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
            )
        )

    @router.message(Command("booking_open"))
    async def booking_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale = await _resolve_doctor_context(message)
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
        await message.answer(
            i18n.t("doctor.booking.open.card", locale).format(
                booking_id=detail.booking_id,
                patient=detail.patient_card.display_name,
                patient_number=detail.patient_card.patient_number or "-",
                phone_hint=detail.patient_card.phone_hint or "-",
                service=detail.service_label,
                datetime=detail.scheduled_label,
                branch=detail.branch_label,
                status=i18n.t(f"booking.status.{detail.booking_status}", locale),
                flags=detail.patient_card.active_flags_summary or "-",
                actions=f"/booking_action {detail.booking_id} <{'|'.join(sorted(DOCTOR_ALLOWED_ACTIONS))}>",
            )
        )

    @router.message(Command("patient_open"))
    async def patient_open(message: Message) -> None:
        if not await _guard_doctor(message) or not message.text:
            return
        doctor_id, locale = await _resolve_doctor_context(message)
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
        doctor_id, locale = await _resolve_doctor_context(message)
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
            doctor_id, _ = await _resolve_doctor_context(message)
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
