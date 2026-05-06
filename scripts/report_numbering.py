from __future__ import annotations

import os
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils import SPANISH_MONTHS, parse_datetime


@dataclass(frozen=True)
class HalfMonthSlot:
    year: int
    month: int
    half: int  # 1 = days 1-15, 2 = day 16-end

    @property
    def start_day(self) -> int:
        return 1 if self.half == 1 else 16

    @property
    def end_day(self) -> int:
        if self.half == 1:
            return 15
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def index(self) -> int:
        return self.year * 24 + (self.month - 1) * 2 + (self.half - 1)

    @property
    def label(self) -> str:
        quincena = "Primera quincena" if self.half == 1 else "Segunda quincena"
        return f"{quincena} de {SPANISH_MONTHS[self.month]} de {self.year}"


def _slot_from_date(dt: datetime) -> HalfMonthSlot:
    return HalfMonthSlot(dt.year, dt.month, 1 if dt.day <= 15 else 2)


def _slot_from_env(prefix: str, fallback: HalfMonthSlot) -> HalfMonthSlot:
    return HalfMonthSlot(
        int(os.getenv(f"{prefix}_YEAR", fallback.year)),
        int(os.getenv(f"{prefix}_MONTH", fallback.month)),
        int(os.getenv(f"{prefix}_HALF", fallback.half)),
    )


def resolve_issue_number(period: dict[str, str]) -> str:
    """Resolve the report issue number from the half-month political report calendar.

    Baseline agreed with AAPP:
    - Apuntes políticos #7 = segunda quincena de abril 2026.
    Therefore:
    - primera quincena de mayo 2026 = #8
    - segunda quincena de mayo 2026 = #9

    REPORT_ISSUE_NUMBER remains a manual override for exceptional cases.
    """
    override = os.getenv("REPORT_ISSUE_NUMBER", "").strip()
    if override:
        return override

    reference_raw = period.get("issue_reference_date") or period.get("end") or ""
    reference_dt = parse_datetime(reference_raw)
    if not reference_dt:
        return ""

    base_slot = _slot_from_env("REPORT_BASE_PERIOD", HalfMonthSlot(2026, 4, 2))
    base_issue = int(os.getenv("REPORT_BASE_ISSUE_NUMBER", "7"))
    current_slot = _slot_from_date(reference_dt)
    return str(base_issue + (current_slot.index - base_slot.index))


def current_half_month_period(now: datetime) -> tuple[datetime, datetime, HalfMonthSlot]:
    """Return current half-month period from slot start to now.

    Useful for manual/forced executions inside a live fortnight. Example: running on
    2026-05-06 produces 2026-05-01 to 2026-05-06 and issue #8.
    """
    slot = _slot_from_date(now)
    start = now.replace(day=slot.start_day, hour=0, minute=0, second=0, microsecond=0)
    return start, now, slot


def completed_half_month_period(now: datetime) -> tuple[datetime, datetime, HalfMonthSlot]:
    """Return the most recently completed half-month period.

    Useful when the workflow runs after a period closes. Example: running on
    2026-05-16 produces 2026-05-01 to 2026-05-15 and issue #8.
    """
    if now.day > 15:
        slot = HalfMonthSlot(now.year, now.month, 1)
    else:
        previous_month = now.month - 1
        year = now.year
        if previous_month == 0:
            previous_month = 12
            year -= 1
        slot = HalfMonthSlot(year, previous_month, 2)

    start = now.replace(year=slot.year, month=slot.month, day=slot.start_day, hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(year=slot.year, month=slot.month, day=slot.end_day, hour=23, minute=59, second=59, microsecond=0)
    return start, end, slot


def sliding_period(now: datetime, period_days: int) -> tuple[datetime, datetime, HalfMonthSlot]:
    start = now - timedelta(days=period_days)
    return start, now, _slot_from_date(now)


def resolve_period(now: datetime, period_days: int, mode: str) -> tuple[dict[str, str], datetime, datetime]:
    mode = (mode or "half_month_current").strip().lower()
    if mode in {"half_month", "current_half_month", "half_month_current"}:
        start, end, slot = current_half_month_period(now)
    elif mode in {"completed_half_month", "half_month_completed"}:
        start, end, slot = completed_half_month_period(now)
    else:
        start, end, slot = sliding_period(now, period_days)

    return (
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": f"{start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}",
            "slot_label": slot.label,
            "issue_reference_date": end.isoformat(),
            "timezone": getattr(now.tzinfo, "key", ""),
            "period_days": str(period_days),
            "period_mode": mode,
        },
        start,
        end,
    )
