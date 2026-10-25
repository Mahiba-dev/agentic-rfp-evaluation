"""Pydantic validation and explicit normalization for LLM evaluations."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import (
	BaseModel,
	ConfigDict,
	Field,
	StrictInt,
	ValidationError as PydanticValidationError,
	field_validator,
)

from src.database import EvaluationCriterion

FALLBACK_SCORE = 0
FALLBACK_JUSTIFICATION = "No usable justification was returned by the model."


class EvaluationValidationError(ValueError):
	"""Raised when an LLM response cannot be safely normalized."""

	def __init__(self, message: str, warnings: Sequence[str] = ()) -> None:
		super().__init__(message)
		self.warnings = tuple(warnings)


class CriterionEvaluation(BaseModel):
	"""Validated assessment for one active criterion."""

	model_config = ConfigDict(extra="forbid", strict=True)

	criterion_id: int
	score: int | float
	max_score: int
	justification: str
	evidence: list[str]


class ValidatedEvaluation(BaseModel):
	"""Validated evaluation plus warnings for every normalization made."""

	model_config = ConfigDict(extra="forbid", strict=True)

	supplier_name: str
	criteria: list[CriterionEvaluation]
	risks: list[str]
	overall_summary: str
	warnings: list[str] = Field(default_factory=list)


class _RawEvaluation(BaseModel):
	model_config = ConfigDict(extra="forbid", strict=True)

	supplier_name: str
	criteria: list[Any]
	risks: list[str]
	overall_summary: str

	@field_validator("supplier_name", "overall_summary")
	@classmethod
	def require_non_empty_text(cls, value: str) -> str:
		if not value.strip():
			raise ValueError("must not be empty")
		return value


class _RawCriterion(BaseModel):
	model_config = ConfigDict(extra="allow", strict=True)

	criterion_id: StrictInt | None = None
	score: Any = None
	max_score: Any = None
	justification: Any = None
	evidence: Any = None


def validate_evaluation_response(
	response: str | bytes | Mapping[str, object],
	active_criteria: Sequence[EvaluationCriterion],
	*,
	expected_supplier_name: str | None = None,
) -> ValidatedEvaluation:
	"""Validate JSON against active criteria and report any safe repairs.

	Normalization rules:
	- Invalid or missing scores become zero; numeric scores outside the allowed
	  interval are clipped to its nearest endpoint.
	- Missing criterion assessments are synthesized with score zero, empty
	  evidence, and an explanatory justification.
	- Missing or malformed justifications use ``FALLBACK_JUSTIFICATION``;
	  missing or malformed evidence becomes an empty list.
	- Unknown IDs and duplicate IDs are ignored (the first known occurrence
	  wins). Malformed criterion entries are ignored.

	Every normalization appends a warning. The response is rejected if its
	top-level shape is invalid, it has no criterion entries, or none of those
	entries can be tied to an active criterion.
	"""
	criteria_by_id = {criterion.id: criterion for criterion in active_criteria}
	if not criteria_by_id:
		raise EvaluationValidationError("At least one active criterion is required.")
	if len(criteria_by_id) != len(active_criteria):
		raise EvaluationValidationError("Active criteria contain duplicate criterion IDs.")
	if any(not criterion.active for criterion in active_criteria):
		raise EvaluationValidationError("Only active database criteria may be validated.")

	decoded = _decode_response(response)
	try:
		raw = _RawEvaluation.model_validate(decoded)
	except PydanticValidationError as error:
		issues = "; ".join(
			f"{'.'.join(str(part) for part in item['loc']) or 'response'}: {item['msg']}"
			for item in error.errors()
		)
		raise EvaluationValidationError(f"Invalid evaluation response: {issues}") from error

	if expected_supplier_name is not None and raw.supplier_name != expected_supplier_name.strip():
		raise EvaluationValidationError(
			"The response supplier_name does not match the requested supplier."
		)
	if not raw.criteria:
		raise EvaluationValidationError(
			"The response contains no criterion assessments and is unusable."
		)

	warnings: list[str] = []
	assessments_by_id: dict[int, CriterionEvaluation] = {}
	for index, entry in enumerate(raw.criteria):
		if not isinstance(entry, Mapping):
			warnings.append(f"Ignored malformed criterion entry at index {index}; expected an object.")
			continue
		try:
			item = _RawCriterion.model_validate(entry)
		except PydanticValidationError:
			warnings.append(
				f"Ignored malformed criterion entry at index {index}; criterion_id was missing "
				"or was not an integer."
			)
			continue

		if item.model_extra:
			warnings.append(
				f"Ignored unsupported fields for criterion entry {index}: "
				f"{', '.join(sorted(item.model_extra))}."
			)
		criterion_id = item.criterion_id
		if criterion_id is None:
			warnings.append(f"Ignored criterion entry at index {index} with no criterion_id.")
			continue
		criterion = criteria_by_id.get(criterion_id)
		if criterion is None:
			warnings.append(f"Ignored unknown criterion_id {criterion_id}.")
			continue
		if criterion_id in assessments_by_id:
			warnings.append(
				f"Ignored duplicate criterion_id {criterion_id}; the first assessment was kept."
			)
			continue

		max_score = item.max_score
		if isinstance(max_score, bool) or not isinstance(max_score, int) or max_score != criterion.max_score:
			warnings.append(
				f"Criterion {criterion_id} max_score was set to the database value "
				f"{criterion.max_score}."
			)

		score = _normalize_score(item.score, criterion, warnings)
		justification = item.justification
		if not isinstance(justification, str) or not justification.strip():
			justification = FALLBACK_JUSTIFICATION
			warnings.append(
				f"Criterion {criterion_id} justification was missing or malformed; "
				"a fallback was used."
			)

		evidence = item.evidence
		if not isinstance(evidence, list) or not all(
			isinstance(evidence_item, str) for evidence_item in evidence
		):
			evidence = []
			warnings.append(
				f"Criterion {criterion_id} evidence was missing or malformed; "
				"an empty list was used."
			)

		assessments_by_id[criterion_id] = CriterionEvaluation(
			criterion_id=criterion_id,
			score=score,
			max_score=criterion.max_score,
			justification=justification,
			evidence=evidence,
		)

	if not assessments_by_id:
		raise EvaluationValidationError(
			"No criterion assessments matched active database criteria; response is unusable.",
			warnings,
		)

	for criterion in active_criteria:
		if criterion.id not in assessments_by_id:
			assessments_by_id[criterion.id] = CriterionEvaluation(
				criterion_id=criterion.id,
				score=FALLBACK_SCORE,
				max_score=criterion.max_score,
				justification="No assessment was returned for this active criterion.",
				evidence=[],
			)
			warnings.append(
				f"Missing active criterion {criterion.id} ({criterion.name}); "
				f"assigned fallback score {FALLBACK_SCORE}."
			)

	return ValidatedEvaluation(
		supplier_name=raw.supplier_name,
		criteria=[assessments_by_id[criterion.id] for criterion in active_criteria],
		risks=raw.risks,
		overall_summary=raw.overall_summary,
		warnings=warnings,
	)


def _decode_response(response: str | bytes | Mapping[str, object]) -> object:
	if isinstance(response, Mapping):
		return dict(response)
	if not isinstance(response, (str, bytes)):
		raise EvaluationValidationError("Evaluation response must be a JSON string or object.")
	try:
		return json.loads(response, parse_constant=_reject_nonstandard_constant)
	except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
		raise EvaluationValidationError(f"Invalid JSON evaluation response: {error}") from error


def _reject_nonstandard_constant(value: str) -> None:
	raise ValueError(f"{value} is not a valid JSON number")


def _normalize_score(
	value: object,
	criterion: EvaluationCriterion,
	warnings: list[str],
) -> int | float:
	if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
		warnings.append(
			f"Criterion {criterion.id} score was missing or malformed; "
			f"assigned fallback score {FALLBACK_SCORE}."
		)
		return FALLBACK_SCORE

	clipped = min(max(value, 0), criterion.max_score)
	if clipped != value:
		warnings.append(
			f"Criterion {criterion.id} score {value} was clipped to {clipped}, "
			f"the permitted range 0-{criterion.max_score}."
		)
	return clipped
