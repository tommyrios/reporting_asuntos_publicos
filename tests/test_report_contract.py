import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from news_models import NewsItem
from report_contract import build_report_contract, validate_report_contract


class ReportContractTest(unittest.TestCase):
    def test_contract_validates(self):
        period = {"label": "01/01/2026 al 15/01/2026"}
        analysis = {
            "headline": "Contexto político",
            "executive_vision": "Texto",
            "key_developments": ["Uno"],
            "bbva_implications": ["Dos"],
            "watchlist": ["Tres"],
        }
        report = build_report_contract("test", period, [NewsItem(title="A", url="https://example.com")], analysis, {})
        validated = validate_report_contract(report)
        self.assertTrue(validated["validation"]["valid"])


if __name__ == "__main__":
    unittest.main()
