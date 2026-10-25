"""Tests for deterministic supplier tie-breaking and sequential rank assignment."""

from __future__ import annotations

import unittest

from src.ranking import RankingError, rank_suppliers


class RankingTests(unittest.TestCase):
	def test_equal_ppi_uses_date_then_experience_then_name(self) -> None:
		suppliers = [
			{
				"supplier_name": "Zulu",
				"ppi": 90.0,
				"submission_date": "2025-03-01",
				"historical_experience_rating": 8,
			},
			{
				"supplier_name": "Bravo",
				"ppi": 90.0,
				"submission_date": "2025-02-01",
				"historical_experience_rating": 5,
			},
			{
				"supplier_name": "Alpha",
				"ppi": 90.0,
				"submission_date": "2025-02-01",
				"historical_experience_rating": 5,
			},
			{
				"supplier_name": "Charlie",
				"ppi": 90.0,
				"submission_date": "2025-02-01",
				"historical_experience_rating": 9,
			},
		]

		ranked = rank_suppliers(suppliers)

		self.assertEqual([supplier["supplier_name"] for supplier in ranked], [
			"Charlie", "Alpha", "Bravo", "Zulu"
		])
		self.assertEqual([supplier["rank"] for supplier in ranked], [1, 2, 3, 4])

	def test_higher_ppi_precedes_earlier_date(self) -> None:
		ranked = rank_suppliers(
			[
				{
					"supplier_name": "Earlier",
					"ppi": 85.0,
					"submission_date": "2025-01-01",
					"historical_experience_rating": 10,
				},
				{
					"supplier_name": "Higher PPI",
					"ppi": 86.0,
					"submission_date": "2025-02-01",
					"historical_experience_rating": 1,
				},
			]
		)
		self.assertEqual(ranked[0]["supplier_name"], "Higher PPI")

	def test_missing_tie_break_metadata_sorts_after_known_values(self) -> None:
		ranked = rank_suppliers(
			[
				{"supplier_name": "Missing metadata", "ppi": 75.0},
				{
					"supplier_name": "Known metadata",
					"ppi": 75.0,
					"submission_date": "2025-01-01",
					"historical_experience_rating": 2,
				},
			]
		)
		self.assertEqual(ranked[0]["supplier_name"], "Known metadata")

	def test_duplicate_names_and_invalid_ppi_are_rejected(self) -> None:
		with self.assertRaisesRegex(RankingError, "Duplicate supplier name"):
			rank_suppliers(
				[
					{"supplier_name": "Acme", "ppi": 70},
					{"supplier_name": "acme", "ppi": 70},
				]
			)
		with self.assertRaisesRegex(RankingError, "finite numeric PPI"):
			rank_suppliers([{"supplier_name": "Acme", "ppi": float("nan")}])


if __name__ == "__main__":
	unittest.main()
