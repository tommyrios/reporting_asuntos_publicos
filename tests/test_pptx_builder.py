import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from pptx import Presentation
from pptx_builder import create_aapp_pptx


class PptxBuilderTest(unittest.TestCase):
    def test_creates_three_slide_deck(self):
        report = {
            "period": {"label": "01/01/2026 al 15/01/2026"},
            "analysis": {
                "headline": "Contexto político",
                "executive_vision": "Visión ejecutiva de prueba.",
                "key_developments": ["Hito 1", "Hito 2"],
                "bbva_implications": ["Implicancia 1"],
                "watchlist": ["Foco 1"],
                "risk_level": "medio",
            },
            "stats": {"raw_news_count": 5, "selected_news_count": 3},
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.pptx"
            create_aapp_pptx(report, out)
            prs = Presentation(str(out))
            self.assertEqual(len(prs.slides), 3)


if __name__ == "__main__":
    unittest.main()
