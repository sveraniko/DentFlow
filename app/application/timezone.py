from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.application.clinic_reference import ClinicReferenceService


@dataclass(slots=True)
class DoctorTimezoneFormatter:
    reference_service: ClinicReferenceService
    app_default_timezone: str = "UTC"

    def format_booking_time(self, *, clinic_id: str, branch_id: str | None, when: datetime, fmt: str) -> str:
        tz_name = self._resolve_timezone(clinic_id=clinic_id, branch_id=branch_id)
        return when.astimezone(self._zone_or_utc(tz_name)).strftime(fmt)

    def format_clinic_time(self, *, clinic_id: str, when: datetime, fmt: str) -> str:
        tz_name = self._resolve_timezone(clinic_id=clinic_id, branch_id=None)
        return when.astimezone(self._zone_or_utc(tz_name)).strftime(fmt)

    def local_day_utc_window(self, *, clinic_id: str, branch_id: str | None, point: datetime) -> tuple[datetime, datetime]:
        tz_name = self._resolve_timezone(clinic_id=clinic_id, branch_id=branch_id)
        zone = self._zone_or_utc(tz_name)
        local_point = point.astimezone(zone)
        local_day_start = datetime(local_point.year, local_point.month, local_point.day, tzinfo=zone)
        local_day_end = local_day_start + timedelta(days=1)
        return local_day_start.astimezone(timezone.utc), local_day_end.astimezone(timezone.utc)

    def _resolve_timezone(self, *, clinic_id: str, branch_id: str | None) -> str:
        if branch_id:
            branches = {row.branch_id: row for row in self.reference_service.list_branches(clinic_id)}
            branch = branches.get(branch_id)
            if branch and branch.timezone:
                return branch.timezone
        clinic = self.reference_service.get_clinic(clinic_id)
        if clinic and clinic.timezone:
            return clinic.timezone
        return self.app_default_timezone

    def _zone_or_utc(self, tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")
