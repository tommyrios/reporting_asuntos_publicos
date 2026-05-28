from __future__ import annotations

import sys
from pathlib import Path
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.should_run import should_run, week_of_month


class ShouldRunTests(unittest.TestCase):
    def test_second_wednesday_runs(self):
        self.assertTrue(should_run(date(2026, 5, 13)))

    def test_fourth_wednesday_runs(self):
        self.assertTrue(should_run(date(2026, 5, 27)))

    def test_first_wednesday_does_not_run(self):
        self.assertFalse(should_run(date(2026, 5, 6)))

    def test_third_wednesday_does_not_run(self):
        self.assertFalse(should_run(date(2026, 5, 20)))

    def test_non_wednesday_does_not_run(self):
        self.assertFalse(should_run(date(2026, 5, 28)))

    def test_week_of_month(self):
        self.assertEqual(week_of_month(date(2026, 5, 1)), 1)
        self.assertEqual(week_of_month(date(2026, 5, 13)), 2)
        self.assertEqual(week_of_month(date(2026, 5, 27)), 4)


if __name__ == "__main__":
    unittest.main()