import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from news_models import NewsItem
from relevance_scorer import score_news_item


class RelevanceScorerTest(unittest.TestCase):
    def test_financial_regulatory_item_scores_high(self):
        item = NewsItem(
            title="BCRA actualiza regulación para bancos y fintech",
            url="https://example.com/bcra",
            summary="La normativa impacta en el sistema financiero.",
        )
        scored = score_news_item(item)
        self.assertIn("regulatorio_financiero", scored.topics)
        self.assertGreaterEqual(scored.relevance_score, 35)

    def test_congress_item_detects_actor(self):
        item = NewsItem(title="El Congreso trata un proyecto de ley económica", url="https://example.com/congreso")
        scored = score_news_item(item)
        self.assertIn("congreso", scored.topics)
        self.assertIn("Congreso", scored.actors)


if __name__ == "__main__":
    unittest.main()
