"""Deterministic absolute and peer-relative supplier scoring."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from src.database import EvaluationCriterion, validate_active_criteria_weights


class ScoringError(ValueError):
	"""Raised when supplier evaluations cannot be scored unambiguously."""


def score_suppliers(
	evaluations: Sequence[Mapping[str, object] | Any],
	active_criteria: Sequence[EvaluationCriterion],
) -> list[dict[str, object]]:
	"""Calculate absolute weighted scores and peer-relative performance.

	Criterion weights use percentage points (for example, 30 means 30%). Scores
	are normalized by each criterion's maximum before applying that weight, so
	the absolute weighted score is on a 0-100 scale. Relative performance is
	also a percentage on a 0-100 scale before the weighted average produces PPI.
	Missing or invalid scores contribute zero and are not used to set benchmarks.
	"""
	if not evaluations:
		raise ScoringError("At least one supplier evaluation is required.")
	if not active_criteria:
		raise ScoringError("At least one active criterion is required.")
	try:
		validate_active_criteria_weights(active_criteria)
	except ValueError as error:
		raise ScoringError(str(error)) from error

	criteria_by_id = {criterion.id: criterion for criterion in active_criteria}
	if len(criteria_by_id) != len(active_criteria):
		raise ScoringError("Active criteria contain duplicate criterion IDs.")
	if any(criterion.max_score <= 0 for criterion in active_criteria):
		raise ScoringError("Every active criterion must have a positive maximum score.")

	prepared: list[tuple[dict[str, object], dict[int, float | None], list[str]]] = []
	benchmarks: dict[int, float] = {criterion.id: 0.0 for criterion in active_criteria}
	for evaluation in evaluations:
		if not isinstance(evaluation, Mapping):
			model_dump = getattr(evaluation, "model_dump", None)
			if not callable(model_dump):
				raise ScoringError("Each supplier evaluation must be a mapping or Pydantic model.")
			evaluation = model_dump(mode="python")
		if not isinstance(evaluation, Mapping):
			raise ScoringError("Each supplier evaluation must be an object.")
		result = dict(evaluation)
		supplier_name = result.get("supplier_name")
		if not isinstance(supplier_name, str) or not supplier_name.strip():
			raise ScoringError("Each supplier evaluation needs a non-empty supplier_name.")
		raw_criteria = result.get("criteria")
		if not isinstance(raw_criteria, list):
			raise ScoringError(f"Supplier {supplier_name!r} has no criterion results array.")

		warnings_value = result.get("warnings", [])
		if not isinstance(warnings_value, list) or not all(
			isinstance(warning, str) for warning in warnings_value
		):
			raise ScoringError(f"Supplier {supplier_name!r} has malformed warnings.")
		warnings = list(warnings_value)
		scores: dict[int, float | None] = {}
		for result_index, item in enumerate(raw_criteria):
			if not isinstance(item, Mapping):
				warnings.append(
					f"Ignored malformed criterion result at index {result_index} for "
					f"{supplier_name}; no benchmark score was recorded."
				)
				continue
			criterion_id = item.get("criterion_id")
			if isinstance(criterion_id, bool) or not isinstance(criterion_id, int):
				warnings.append(
					f"Ignored criterion result at index {result_index} for {supplier_name}; "
					"criterion_id was not an integer."
				)
				continue
			if criterion_id not in criteria_by_id:
				warnings.append(
					f"Ignored unknown criterion_id {criterion_id} for {supplier_name}."
				)
				continue
			if criterion_id in scores:
				warnings.append(
					f"Ignored duplicate criterion_id {criterion_id} for {supplier_name}; "
					"the first result was kept."
				)
				continue

			score = item.get("score")
			criterion = criteria_by_id[criterion_id]
			if (
				isinstance(score, bool)
				or not isinstance(score, (int, float))
				or not math.isfinite(score)
				or not 0 <= score <= criterion.max_score
			):
				scores[criterion_id] = None
				warnings.append(
					f"Supplier {supplier_name} has no valid score for criterion "
					f"{criterion_id}; it contributes zero and is excluded from the benchmark."
				)
				continue
			scores[criterion_id] = float(score)
			benchmarks[criterion_id] = max(benchmarks[criterion_id], float(score))

		for criterion in active_criteria:
			if criterion.id not in scores:
				scores[criterion.id] = None
				warnings.append(
					f"Supplier {supplier_name} is missing criterion {criterion.id}; "
					"it contributes zero and is excluded from the benchmark."
				)
		prepared.append((result, scores, warnings))

	total_weight = sum(criterion.weight for criterion in active_criteria)
	output: list[dict[str, object]] = []
	for result, scores, warnings in prepared:
		criterion_results: list[dict[str, object]] = []
		absolute_weighted_score = 0.0
		weighted_relative_total = 0.0
		for criterion in active_criteria:
			score = scores[criterion.id]
			benchmark = benchmarks[criterion.id]
			valid_score = score is not None
			supplier_score = score if valid_score else 0.0
			weighted_contribution = supplier_score / criterion.max_score * criterion.weight
			absolute_weighted_score += weighted_contribution

			# With a zero benchmark, a valid zero ties the batch leader (100%); a
			# missing score is not a leader and receives 0% relative performance.
			if benchmark == 0.0:
				relative_performance = 100.0 if valid_score else 0.0
			else:
				relative_performance = supplier_score / benchmark * 100.0
			weighted_relative_total += relative_performance * criterion.weight
			criterion_results.append(
				{
					"criterion_id": criterion.id,
					"name": criterion.name,
					"score": supplier_score,
					"score_valid": valid_score,
					"max_score": criterion.max_score,
					"weight": criterion.weight,
					"benchmark": benchmark,
					"gap": supplier_score - benchmark,
					"relative_performance_percentage": relative_performance,
					"weighted_contribution": weighted_contribution,
				}
			)

		supplier_result = dict(result)
		supplier_result["absolute_weighted_score"] = absolute_weighted_score
		supplier_result["total_score"] = absolute_weighted_score
		supplier_result["criterion_results"] = criterion_results
		supplier_result["ppi"] = weighted_relative_total / total_weight
		supplier_result["warnings"] = warnings
		output.append(supplier_result)
	return output
