from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import os
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.report_numbering import resolve_issue_number, resolve_period


class ReportNumberingTests(unittest.TestCase):
    def setUp(self):
        for key in [
            "REPORT_ISSUE_NUMBER",
            "REPORT_BASE_ISSUE_NUMBER",
            "REPORT_BASE_PERIOD_YEAR",
            "REPORT_BASE_PERIOD_MONTH",
            "REPORT_BASE_PERIOD_HALF",
        ]:
            os.environ.pop(key, None)

    def test_manual_baseline_second_half_april_is_issue_7(self):
        period = {"end": "2026-04-30T23:59:00-03:00"}
        self.assertEqual(resolve_issue_number(period), "7")

    def test_first_half_may_is_issue_8(self):
        period = {"end": "2026-05-06T12:00:00-03:00"}
        self.assertEqual(resolve_issue_number(period), "8")

    def test_second_half_may_is_issue_9(self):
        period = {"end": "2026-05-20T12:00:00-03:00"}
        self.assertEqual(resolve_issue_number(period), "9")

    def test_half_month_current_period(self):
        now = datetime(2026, 5, 6, 12, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
        period, start, end = resolve_period(now, 15, "half_month_current")
        self.assertEqual(start.day, 1)
        self.assertEqual(period["slot_label"], "Primera quincena de mayo de 2026")
        self.assertEqual(resolve_issue_number(period), "8")


if __name__ == "__main__":
    unittest.main()
