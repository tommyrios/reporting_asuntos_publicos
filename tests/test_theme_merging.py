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
from scripts.political_analyzer import _sanitize_report


class ThemeMergingTests(unittest.TestCase):
    def test_repeated_reforma_electoral_coverage_becomes_one_theme(self):
        items = [
            NewsItem(
                title="Milei impulsa eliminar las PASO y la oposición denuncia una maniobra electoral",
                url="https://a.com/1",
                source="A",
                summary="La discusión por las PASO volvió a abrir una pulseada en el Congreso.",
            ),
            NewsItem(
                title="Ficha Limpia suma presión legislativa dentro de la reforma electoral",
                url="https://b.com/2",
                source="B",
                summary="La oposición busca tratar Ficha Limpia y tensiona la estrategia oficialista.",
            ),
            NewsItem(
                title="La reforma electoral reordena el tablero entre oficialismo y oposición",
                url="https://c.com/3",
                source="C",
                summary="El debate electoral concentra negociaciones entre bloques legislativos.",
            ),
            NewsItem(
                title="La CGT prepara una movilización por salarios",
                url="https://d.com/4",
                source="D",
                summary="La protesta sindical vuelve a la calle como presión social.",
            ),
        ]
        clusters = cluster_news(items, reference=datetime(2026, 5, 6, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")))
        selected = select_top_clusters(clusters, min_clusters=2, max_clusters=4)

        reforma_clusters = [c for c in selected if any(term in " ".join([c.title, c.summary]).lower() for term in ["paso", "ficha limpia", "reforma electoral"])]
        self.assertEqual(len(reforma_clusters), 1)
        self.assertGreaterEqual(reforma_clusters[0].article_count, 3)
        self.assertEqual(selected[0].cluster_id, reforma_clusters[0].cluster_id)

    def test_final_report_merges_duplicate_headlines_from_llm(self):
        payload = {
            "title": "Insumos para apuntes políticos #8",
            "date_label": "6 de Mayo de 2026",
            "lead": "La quincena estuvo marcada por una mayor disputa política y legislativa.",
            "developments": [
                {
                    "headline": "La reforma electoral abre una nueva pulseada entre el oficialismo y la oposición",
                    "analysis": "La eliminación de las PASO volvió a ordenar la discusión legislativa y tensó la relación entre bloques.",
                    "cluster_id": "a",
                },
                {
                    "headline": "La reforma electoral abre una nueva pulseada entre el oficialismo y la oposición",
                    "analysis": "Ficha Limpia agregó presión y obligó al oficialismo a recalibrar su estrategia parlamentaria.",
                    "cluster_id": "b",
                },
                {
                    "headline": "La opinión pública introduce un límite más exigente para el oficialismo",
                    "analysis": "Las encuestas mostraron un mayor deterioro de imagen y consolidaron el malestar social.",
                    "cluster_id": "c",
                },
                {
                    "headline": "La conflictividad social recupera visibilidad como factor de presión",
                    "analysis": "La agenda sindical volvió a instalar presión en la calle y amplió los costos políticos del Gobierno.",
                    "cluster_id": "d",
                },
                {
                    "headline": "La economía sigue ordenando el clima político de la quincena",
                    "analysis": "El debate económico combinó inflación, ingresos y consumo como variables de evaluación política.",
                    "cluster_id": "e",
                },
            ],
            "prospective_keys": ["Evolución del Congreso.", "Trayectoria de la opinión pública.", "Nivel de conflictividad social.", "Capacidad de iniciativa oficial."],
            "editorial_notes": "",
        }
        report = _sanitize_report(payload, [], {"issue_number": "8", "date_label": "6 de Mayo de 2026"})
        headlines = [item["headline"] for item in report["developments"]]
        self.assertEqual(headlines.count("La reforma electoral abre una nueva pulseada entre el oficialismo y la oposición"), 1)
        reforma = next(item for item in report["developments"] if item["headline"].startswith("La reforma electoral"))
        self.assertIn("Ficha Limpia", reforma["analysis"])


if __name__ == "__main__":
    unittest.main()
