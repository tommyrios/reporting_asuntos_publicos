from __future__ import annotations

import argparse
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

from utils import parse_bool


def week_of_month(day: date) -> int:
    return ((day.day - 1) // 7) + 1


def should_run(today: date) -> bool:
    is_wednesday = today.weekday() == 2
    is_second_or_fourth = week_of_month(today) in (2, 4)
    return is_wednesday and is_second_or_fourth


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", default=os.getenv("FORCE_RUN", "false"))
    parser.add_argument("--timezone", default=os.getenv("REPORT_TIMEZONE", "America/Argentina/Buenos_Aires"))
    args = parser.parse_args()

    if parse_bool(args.force, False):
        print("true")
        return

    tz = ZoneInfo(args.timezone)
    current = datetime.now(tz).date()

    print("true" if should_run(current) else "false")


if __name__ == "__main__":
    main()