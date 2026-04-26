from __future__ import annotations

import json

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.application.access import AccessResolver
from app.application.owner import OwnerAnalyticsService
from app.common.i18n import I18nService
from app.domain.access_identity.models import RoleCode
from app.interfaces.bots.common import build_role_router, guard_roles, resolve_locale


def make_router(
    i18n: I18nService,
    access_resolver: AccessResolver,
    analytics: OwnerAnalyticsService,
    *,
    default_locale: str,
) -> Router:
    router = build_role_router(
        role_key="owner",
        i18n=i18n,
        locale=default_locale,
        access_resolver=access_resolver,
        required_role=RoleCode.OWNER,
    )

    async def _guard_owner(message: Message) -> tuple[bool, str]:
        allowed = await guard_roles(
            message,
            i18n=i18n,
            access_resolver=access_resolver,
            allowed_roles={RoleCode.OWNER},
            fallback_locale=default_locale,
        )
        locale = await resolve_locale(message, access_resolver=access_resolver, fallback_locale=default_locale)
        return allowed, locale



    def _parse_window_days(raw_text: str | None) -> int | None:
        if not raw_text:
            return 7
        parts = raw_text.strip().split(maxsplit=1)
        if len(parts) == 1:
            return 7
        try:
            days = int(parts[1])
        except ValueError:
            return None
        if days < 1 or days > 90:
            return None
        return days

    def _parse_staff_limit(raw_text: str | None) -> int | None:
        if not raw_text:
            return 30
        parts = raw_text.strip().split(maxsplit=1)
        if len(parts) == 1:
            return 30
        try:
            limit = int(parts[1])
        except ValueError:
            return None
        if limit < 1 or limit > 100:
            return None
        return limit

    def _compact_id(value: str) -> str:
        if len(value) <= 12:
            return value
        return f"{value[:6]}…{value[-4:]}"
    @router.message(Command("owner_today"))
    async def owner_today(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        snap = await analytics.get_today_snapshot(clinic_id=actor.clinic_id)
        await message.answer(
            i18n.t("owner.today.card", locale).format(
                date=snap.local_date.isoformat(),
                bookings=snap.bookings_today,
                pending=snap.pending_confirmations_today,
                completed=snap.completed_today,
                canceled=snap.canceled_today,
                no_show=snap.no_show_today,
                charts=snap.charts_opened_today,
                reminder_failures=snap.reminder_failures_today,
                open_alerts=snap.open_alerts_count,
            )
        )

    @router.message(Command("owner_digest"))
    async def owner_digest(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        digest = await analytics.get_latest_digest(clinic_id=actor.clinic_id)
        if digest is None:
            await message.answer(i18n.t("owner.digest.empty", locale))
            return
        await message.answer(
            i18n.t("owner.digest.card", locale).format(
                date=digest.metrics_date.isoformat(),
                created=digest.bookings_created_count,
                confirmed=digest.bookings_confirmed_count,
                completed=digest.bookings_completed_count,
                canceled=digest.bookings_canceled_count,
                no_show=digest.bookings_no_show_count,
                reminder_failures=digest.reminders_failed_count,
                open_alerts=digest.open_alerts_count,
            )
        )

    @router.message(Command("owner_alerts"))
    async def owner_alerts(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        alerts = await analytics.list_open_alerts(clinic_id=actor.clinic_id)
        if not alerts:
            await message.answer(i18n.t("owner.alerts.empty", locale))
            return
        lines = [i18n.t("owner.alerts.title", locale)]
        for row in alerts:
            lines.append(
                i18n.t("owner.alerts.item", locale).format(
                    owner_alert_id=row.owner_alert_id,
                    alert_date=row.alert_date.isoformat(),
                    alert_type=row.alert_type,
                    severity=row.severity,
                    summary=row.summary_text,
                )
            )
        lines.append(i18n.t("owner.alerts.hint", locale))
        await message.answer("\n".join(lines))

    @router.message(Command("owner_alert_open"))
    async def owner_alert_open(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user or not message.text:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) != 2:
            await message.answer(i18n.t("owner.alert.open.usage", locale))
            return
        row = await analytics.get_alert(clinic_id=actor.clinic_id, owner_alert_id=parts[1])
        if row is None:
            await message.answer(i18n.t("owner.alert.open.missing", locale))
            return
        details = json.dumps(row.details_json, ensure_ascii=False) if row.details_json else "-"
        await message.answer(
            i18n.t("owner.alert.open.card", locale).format(
                owner_alert_id=row.owner_alert_id,
                alert_type=row.alert_type,
                severity=row.severity,
                status=row.status,
                alert_date=row.alert_date.isoformat(),
                summary=row.summary_text,
                details=details,
            )
        )



    @router.message(Command("owner_doctors"))
    async def owner_doctors(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        days = _parse_window_days(message.text)
        if days is None:
            await message.answer(i18n.t("owner.metrics.invalid_window", locale))
            await message.answer(i18n.t("owner.doctors.usage", locale))
            return
        summary = await analytics.get_doctor_metrics(clinic_id=actor.clinic_id, days=days)
        if not summary.rows:
            await message.answer(i18n.t("owner.doctors.empty", locale).format(days=days))
            return
        lines = [i18n.t("owner.doctors.title", locale).format(days=days)]
        for row in summary.rows:
            lines.append(
                i18n.t("owner.doctors.item", locale).format(
                    doctor_id=row.doctor_id,
                    created=row.bookings_created_count,
                    confirmed=row.bookings_confirmed_count,
                    completed=row.bookings_completed_count,
                    no_show=row.bookings_no_show_count,
                    reschedule=row.bookings_reschedule_requested_count,
                    reminders_sent=row.reminders_sent_count,
                    reminders_failed=row.reminders_failed_count,
                    encounters=row.encounters_created_count,
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("owner_services"))
    async def owner_services(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        days = _parse_window_days(message.text)
        if days is None:
            await message.answer(i18n.t("owner.metrics.invalid_window", locale))
            await message.answer(i18n.t("owner.services.usage", locale))
            return
        summary = await analytics.get_service_metrics(clinic_id=actor.clinic_id, days=days)
        if not summary.rows:
            await message.answer(i18n.t("owner.services.empty", locale).format(days=days))
            return
        lines = [i18n.t("owner.services.title", locale).format(days=days)]
        for row in summary.rows:
            lines.append(
                i18n.t("owner.services.item", locale).format(
                    service_id=row.service_id,
                    created=row.bookings_created_count,
                    confirmed=row.bookings_confirmed_count,
                    completed=row.bookings_completed_count,
                    no_show=row.bookings_no_show_count,
                    reschedule=row.bookings_reschedule_requested_count,
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("owner_branches"))
    async def owner_branches(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        days = _parse_window_days(message.text)
        if days is None:
            await message.answer(i18n.t("owner.metrics.invalid_window", locale))
            await message.answer(i18n.t("owner.branches.usage", locale))
            return
        summary = await analytics.get_branch_metrics(clinic_id=actor.clinic_id, days=days)
        if not summary.rows:
            await message.answer(i18n.t("owner.branches.empty", locale).format(days=days))
            return
        lines = [i18n.t("owner.branches.title", locale).format(days=days)]
        for row in summary.rows:
            lines.append(
                i18n.t("owner.branches.item", locale).format(
                    branch=row.branch_label or row.branch_id,
                    created=row.bookings_created_count,
                    confirmed=row.bookings_confirmed_count,
                    completed=row.bookings_completed_count,
                    canceled=row.bookings_canceled_count,
                    no_show=row.bookings_no_show_count,
                    reschedule=row.bookings_reschedule_requested_count,
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("owner_care"))
    async def owner_care(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        days = _parse_window_days(message.text)
        if days is None:
            await message.answer(i18n.t("owner.metrics.invalid_window", locale))
            await message.answer(i18n.t("owner.care.usage", locale))
            return
        summary = await analytics.get_care_metrics(clinic_id=actor.clinic_id, days=days)
        has_activity = any(
            [
                summary.orders_created_count,
                summary.orders_confirmed_count,
                summary.orders_ready_for_pickup_count,
                summary.orders_issued_count,
                summary.orders_fulfilled_count,
                summary.orders_canceled_count,
                summary.orders_expired_count,
                summary.active_orders_count,
                summary.active_reservations_count,
            ]
        )
        if not has_activity:
            await message.answer(i18n.t("owner.care.empty", locale).format(days=days))
            return
        await message.answer(
            i18n.t("owner.care.card", locale).format(
                days=days,
                created=summary.orders_created_count,
                confirmed=summary.orders_confirmed_count,
                ready=summary.orders_ready_for_pickup_count,
                issued=summary.orders_issued_count,
                fulfilled=summary.orders_fulfilled_count,
                canceled=summary.orders_canceled_count,
                expired=summary.orders_expired_count,
                active_orders=summary.active_orders_count,
                active_reservations=summary.active_reservations_count,
            )
        )

    @router.message(Command("owner_staff"))
    async def owner_staff(message: Message) -> None:
        allowed, locale = await _guard_owner(message)
        if not allowed or not message.from_user:
            return
        actor = access_resolver.resolve_actor_context(message.from_user.id)
        if actor is None:
            return
        limit = _parse_staff_limit(message.text)
        if limit is None:
            await message.answer(i18n.t("owner.staff.invalid_limit", locale))
            await message.answer(i18n.t("owner.staff.usage", locale))
            return
        try:
            overview = await analytics.get_staff_access_overview(clinic_id=actor.clinic_id, limit=limit)
        except Exception:
            await message.answer(i18n.t("owner.staff.unavailable", locale))
            return
        if not overview.rows:
            await message.answer(i18n.t("owner.staff.empty", locale).format(limit=limit))
            return
        lines = [
            i18n.t("owner.staff.title", locale).format(shown=len(overview.rows), limit=limit),
        ]
        for row in overview.rows:
            name = row.display_name or _compact_id(row.actor_id)
            role = row.role_label or row.role_code or i18n.t("owner.staff.unknown", locale)
            tg_state = i18n.t(f"owner.staff.telegram.{row.telegram_binding_state}", locale)
            active_state = i18n.t(f"owner.staff.active.{row.active_state}", locale)
            lines.append(
                i18n.t("owner.staff.item", locale).format(
                    name=name,
                    role=role,
                    staff_kind=row.staff_kind,
                    telegram=tg_state,
                    active=active_state,
                    doctor_id=row.doctor_id or "-",
                    branch=row.branch_label or row.branch_id or "-",
                )
            )
        await message.answer("\n".join(lines))
    return router
