from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scripts.news_clusterer import cluster_news, select_top_clusters
from scripts.news_models import NewsItem
from scripts.political_analyzer import generate_political_report
from scripts.utils import format_spanish_date


class AnalyzerFallbackTests(unittest.TestCase):
    def test_generates_report_without_gemini(self):
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        end = datetime(2026, 5, 1, 20, tzinfo=tz)
        start = end - timedelta(days=15)
        period = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": "16/04/2026 al 01/05/2026",
            "date_label": format_spanish_date(end),
        }
        items = [
            NewsItem(title="El Congreso debate la agenda del oficialismo", url="https://a.com/1", summary="Diputados y Senado vuelven al centro de la escena política."),
            NewsItem(title="La CGT convoca una movilización nacional", url="https://b.com/2", summary="La protesta sindical gana visibilidad en la calle."),
            NewsItem(title="Encuestas muestran deterioro de la imagen presidencial", url="https://c.com/3", summary="La opinión pública acusa desgaste por motivos económicos."),
            NewsItem(title="La oposición busca reordenarse", url="https://d.com/4", summary="El peronismo muestra señales de reorganización."),
        ]
        clusters = select_top_clusters(cluster_news(items, reference=end), min_clusters=4, max_clusters=8)
        report = generate_political_report(clusters, period, disable_gemini=True)
        self.assertIn("lead", report)
        self.assertGreaterEqual(len(report["developments"]), 4)
        self.assertGreaterEqual(len(report["prospective_keys"]), 4)


if __name__ == "__main__":
    unittest.main()
