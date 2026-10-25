"""Tests for Pydantic evaluation response validation and normalization."""

from __future__ import annotations

import json
import unittest

from src.database import EvaluationCriterion
from src.validation import (
	EvaluationValidationError,
	FALLBACK_JUSTIFICATION,
	validate_evaluation_response,
)


class EvaluationValidationTests(unittest.TestCase):
	def setUp(self) -> None:
		self.criteria = [
			EvaluationCriterion(11, "Technical", 50.0, 5, True),
			EvaluationCriterion(12, "Schedule", 30.0, 10, True),
			EvaluationCriterion(13, "Support", 20.0, 4, True),
		]

	def make_response(self, assessments: list[object]) -> dict[str, object]:
		return {
			"supplier_name": "Northstar Ltd",
			"criteria": assessments,
			"risks": [],
			"overall_summary": "The proposal is assessable.",
		}

	def make_assessment(self, criterion_id: int, score: int | float) -> dict[str, object]:
		criterion = next(item for item in self.criteria if item.id == criterion_id)
		return {
			"criterion_id": criterion_id,
			"score": score,
			"max_score": criterion.max_score,
			"justification": "Supported by the proposal.",
			"evidence": ["Proposal detail."],
		}

	def test_valid_json_string_returns_all_active_criteria(self) -> None:
		response = self.make_response(
			[self.make_assessment(item.id, 2) for item in self.criteria]
		)

		validated = validate_evaluation_response(
			json.dumps(response),
			self.criteria,
			expected_supplier_name="Northstar Ltd",
		)

		self.assertEqual([item.criterion_id for item in validated.criteria], [11, 12, 13])
		self.assertEqual(validated.warnings, [])

	def test_valid_zero_score_is_not_treated_as_a_validation_failure(self) -> None:
		response = self.make_response(
			[self.make_assessment(item.id, 0) for item in self.criteria]
		)

		validated = validate_evaluation_response(response, self.criteria)

		self.assertTrue(all(item.score == 0 for item in validated.criteria))
		self.assertEqual(validated.warnings, [])

	def test_normalizes_scores_criteria_duplicates_and_missing_fields_with_warnings(self) -> None:
		first = self.make_assessment(11, 9)
		first["max_score"] = 99
		first["justification"] = None
		first["evidence"] = "not a list"
		malformed_score = self.make_assessment(12, 3)
		malformed_score["score"] = "three"
		response = self.make_response(
			[
				first,
				self.make_assessment(11, 4),
				malformed_score,
				{"criterion_id": 999, "score": 1},
				"not an object",
			]
		)

		validated = validate_evaluation_response(response, self.criteria)

		self.assertEqual([item.score for item in validated.criteria], [5, 0, 0])
		self.assertEqual(validated.criteria[0].justification, FALLBACK_JUSTIFICATION)
		self.assertEqual(validated.criteria[0].evidence, [])
		self.assertGreaterEqual(len(validated.warnings), 8)
		self.assertTrue(any("clipped to 5" in warning for warning in validated.warnings))
		self.assertTrue(any("duplicate criterion_id 11" in warning for warning in validated.warnings))
		self.assertTrue(any("unknown criterion_id 999" in warning for warning in validated.warnings))
		self.assertTrue(any("Missing active criterion 13" in warning for warning in validated.warnings))

	def test_rejects_invalid_json(self) -> None:
		with self.assertRaisesRegex(EvaluationValidationError, "Invalid JSON"):
			validate_evaluation_response("{not json", self.criteria)

	def test_rejects_wrong_top_level_field_types(self) -> None:
		response = self.make_response(
			[self.make_assessment(item.id, 2) for item in self.criteria]
		)
		response["risks"] = "not a list"
		with self.assertRaisesRegex(EvaluationValidationError, "risks"):
			validate_evaluation_response(response, self.criteria)

	def test_rejects_missing_criteria_and_fully_unusable_criteria(self) -> None:
		response = self.make_response([])
		with self.assertRaisesRegex(EvaluationValidationError, "no criterion assessments"):
			validate_evaluation_response(response, self.criteria)

		response["criteria"] = [{"criterion_id": 999, "score": 2}]
		with self.assertRaisesRegex(EvaluationValidationError, "No criterion assessments matched") as error:
			validate_evaluation_response(response, self.criteria)
		self.assertTrue(any("unknown criterion_id 999" in warning for warning in error.exception.warnings))

	def test_rejects_supplier_mismatch_and_ranking_fields(self) -> None:
		response = self.make_response(
			[self.make_assessment(item.id, 2) for item in self.criteria]
		)
		with self.assertRaisesRegex(EvaluationValidationError, "does not match"):
			validate_evaluation_response(
				response,
				self.criteria,
				expected_supplier_name="Another Supplier",
			)

		response["rank"] = 1
		with self.assertRaisesRegex(EvaluationValidationError, "rank"):
			validate_evaluation_response(response, self.criteria)


if __name__ == "__main__":
	unittest.main()
