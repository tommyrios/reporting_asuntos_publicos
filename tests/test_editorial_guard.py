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
from scripts.political_analyzer import generate_political_report
from scripts.editorial_guard import contains_media_reference, sanitize_final_text


class EditorialGuardTests(unittest.TestCase):
    def test_sanitizes_media_sources_from_text(self):
        text = "La reforma electoral suma reparos - La Gaceta. La oposición presiona Infobae y TN."
        cleaned = sanitize_final_text(text, max_chars=300)
        self.assertNotIn("La Gaceta", cleaned)
        self.assertNotIn("Infobae", cleaned)
        self.assertNotIn("TN", cleaned)
        self.assertFalse(contains_media_reference(cleaned))

    def test_fallback_report_has_no_media_and_complete_sentences(self):
        end = datetime(2026, 5, 6, 12, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
        period = {
            "start": "2026-05-01T00:00:00-03:00",
            "end": end.isoformat(),
            "issue_reference_date": end.isoformat(),
            "slot_label": "Primera quincena de mayo de 2026",
            "date_label": "6 de Mayo de 2026",
        }
        items = [
            NewsItem(title="La reforma electoral de Milei suma reparos entre gobernadores - La Gaceta", url="https://lagaceta.com.ar/1", source="La Gaceta", summary="Gobernadores condicionan el avance legislativo de la reforma."),
            NewsItem(title="La oposición presiona por Ficha Limpia Infobae", url="https://infobae.com/2", source="Infobae", summary="Bloques opositores buscan imponer agenda en Diputados."),
            NewsItem(title="La CGT prepara una movilización nacional El Litoral", url="https://ellitoral.com/3", source="El Litoral", summary="La protesta sindical recupera visibilidad por salarios."),
            NewsItem(title="Encuestas muestran caída de imagen presidencial MDZ Online", url="https://mdzol.com/4", source="MDZ Online", summary="La opinión pública acusa desgaste por factores económicos."),
        ]
        clusters = select_top_clusters(cluster_news(items, reference=end), min_clusters=4, max_clusters=8)
        report = generate_political_report(clusters, period, disable_gemini=True)
        full_text = " ".join([
            report["title"], report["lead"],
            *[d["headline"] + " " + d["analysis"] for d in report["developments"]],
            *report["prospective_keys"],
        ])
        for forbidden in ["La Gaceta", "Infobae", "TN", "MDZ Online", "El Litoral", "http", ".com"]:
            self.assertNotIn(forbidden, full_text)
        for dev in report["developments"]:
            self.assertTrue(dev["analysis"].endswith((".", "?", "!")))
        self.assertEqual(report["title"], "Insumos para apuntes políticos #8")


if __name__ == "__main__":
    unittest.main()
