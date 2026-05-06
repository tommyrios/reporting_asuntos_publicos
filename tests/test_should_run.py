from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import unittest
from datetime import date

from scripts.should_run import should_run


class ShouldRunTests(unittest.TestCase):
    def test_anchor_runs(self):
        self.assertTrue(should_run(date(2026, 5, 6), date(2026, 5, 6), 14))

    def test_next_week_does_not_run(self):
        self.assertFalse(should_run(date(2026, 5, 13), date(2026, 5, 6), 14))

    def test_next_fortnight_runs(self):
        self.assertTrue(should_run(date(2026, 5, 20), date(2026, 5, 6), 14))


if __name__ == "__main__":
    unittest.main()
