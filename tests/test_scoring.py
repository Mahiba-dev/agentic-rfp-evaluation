"""Tests for absolute and relative supplier scoring."""

from __future__ import annotations

import unittest

from src.database import EvaluationCriterion
from src.scoring import score_suppliers


class ScoringTests(unittest.TestCase):
	def setUp(self) -> None:
		self.criteria = [
			EvaluationCriterion(1, "Technical", 60.0, 10, True),
			EvaluationCriterion(2, "Support", 40.0, 10, True),
		]

	def evaluation(self, name: str, scores: dict[int, int | float | None]) -> dict[str, object]:
		return {
			"supplier_name": name,
			"criteria": [
				{
					"criterion_id": criterion.id,
					"score": scores[criterion.id],
				}
				for criterion in self.criteria
				if criterion.id in scores
			],
			"warnings": [],
		}

	def test_benchmarks_are_highest_valid_peer_scores(self) -> None:
		results = score_suppliers(
			[
				self.evaluation("Leader", {1: 10, 2: 5}),
				self.evaluation("Other", {1: 5, 2: 10}),
			],
			self.criteria,
		)

		leader, other = results
		self.assertEqual(leader["absolute_weighted_score"], 80.0)
		self.assertEqual(leader["ppi"], 80.0)
		self.assertEqual(leader["criterion_results"][0]["benchmark"], 10.0)
		self.assertEqual(leader["criterion_results"][0]["gap"], 0.0)
		self.assertEqual(other["criterion_results"][0]["gap"], -5.0)
		self.assertEqual(other["ppi"], 70.0)

	def test_tied_benchmark_leaders_receive_one_hundred_percent(self) -> None:
		results = score_suppliers(
			[
				self.evaluation("One", {1: 8, 2: 0}),
				self.evaluation("Two", {1: 8, 2: 0}),
			],
			self.criteria,
		)

		for result in results:
			self.assertEqual(result["criterion_results"][0]["relative_performance_percentage"], 100.0)
			self.assertEqual(result["ppi"], 100.0)

	def test_zero_benchmark_handles_valid_zero_and_missing_score(self) -> None:
		criteria = [EvaluationCriterion(1, "Technical", 100.0, 10, True)]
		results = score_suppliers(
			[
				{"supplier_name": "Valid Zero", "criteria": [{"criterion_id": 1, "score": 0}]},
				{"supplier_name": "Missing", "criteria": []},
			],
			criteria,
		)

		valid_zero, missing = results
		self.assertEqual(valid_zero["ppi"], 100.0)
		self.assertEqual(valid_zero["criterion_results"][0]["relative_performance_percentage"], 100.0)
		self.assertEqual(missing["ppi"], 0.0)
		self.assertEqual(missing["criterion_results"][0]["relative_performance_percentage"], 0.0)
		self.assertTrue(missing["warnings"])

	def test_missing_scores_contribute_zero_and_do_not_lead_benchmark(self) -> None:
		results = score_suppliers(
			[
				self.evaluation("Scored", {1: 6, 2: 8}),
				self.evaluation("Partial", {1: 10}),
			],
			self.criteria,
		)

		partial = results[1]
		self.assertEqual(partial["absolute_weighted_score"], 60.0)
		self.assertEqual(partial["criterion_results"][1]["benchmark"], 8.0)
		self.assertFalse(partial["criterion_results"][1]["score_valid"])
		self.assertTrue(any("missing criterion 2" in warning for warning in partial["warnings"]))


if __name__ == "__main__":
	unittest.main()
