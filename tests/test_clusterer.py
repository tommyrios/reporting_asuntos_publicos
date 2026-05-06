from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.news_clusterer import cluster_news, select_top_clusters
from scripts.news_models import NewsItem


class ClustererTests(unittest.TestCase):
    def test_clusters_same_information_piece(self):
        items = [
            NewsItem(title="El Jefe de Gabinete expuso en Diputados en una sesión tensa", url="https://a.com/1", source="A", summary="La oposición cuestionó al oficialismo en el Congreso."),
            NewsItem(title="Diputados fue escenario de una exposición tensa del Jefe de Gabinete", url="https://b.com/2", source="B", summary="El oficialismo sostuvo la sesión ante críticas opositoras."),
            NewsItem(title="La CGT convocó una marcha por salarios", url="https://c.com/3", source="C", summary="La protesta sindical vuelve a la calle."),
        ]
        clusters = cluster_news(items, reference=datetime(2026, 5, 1, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")))
        self.assertLessEqual(len(clusters), 3)
        self.assertTrue(any(cluster.article_count >= 2 for cluster in clusters))

    def test_select_top_clusters_bounds(self):
        items = [NewsItem(title=f"Congreso debate tema politico {i}", url=f"https://a.com/{i}", source="A") for i in range(10)]
        clusters = cluster_news(items)
        selected = select_top_clusters(clusters, min_clusters=4, max_clusters=8)
        self.assertLessEqual(len(selected), 8)


if __name__ == "__main__":
    unittest.main()
