from __future__ import annotations

import argparse
import os
from datetime import date
from zoneinfo import ZoneInfo

from utils import parse_bool


def should_run(today: date, anchor: date, every_days: int) -> bool:
    if every_days <= 0:
        return True
    delta = (today - anchor).days
    return delta >= 0 and delta % every_days == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", default=os.getenv("FORCE_RUN", "false"))
    parser.add_argument("--timezone", default=os.getenv("REPORT_TIMEZONE", "America/Argentina/Buenos_Aires"))
    parser.add_argument("--anchor-date", default=os.getenv("SCHEDULE_ANCHOR_DATE", "2026-05-06"))
    parser.add_argument("--every-days", type=int, default=int(os.getenv("RUN_EVERY_DAYS", "14")))
    args = parser.parse_args()

    if parse_bool(args.force, False):
        print("true")
        return
    tz = ZoneInfo(args.timezone)
    current = date.today() if args.timezone.upper() == "UTC" else __import__("datetime").datetime.now(tz).date()
    anchor = date.fromisoformat(args.anchor_date)
    print("true" if should_run(current, anchor, args.every_days) else "false")


if __name__ == "__main__":
    main()
