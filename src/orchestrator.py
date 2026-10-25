"""Coordinate PDF evaluation, deterministic scoring, ranking, and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import BinaryIO, Mapping, Sequence
from uuid import uuid4

from src.database import (
	DEFAULT_DB_PATH,
	EvaluationCriterion,
	connect_db,
	get_active_criteria,
	save_run_result,
	validate_active_criteria_weights,
)
from src.document_reader import extract_pdf_text
from src.evaluation_agent import LLMClient, evaluate_supplier
from src.ranking import rank_suppliers
from src.scoring import score_suppliers


@dataclass(frozen=True)
class SupplierSubmission:
	"""One uploaded supplier proposal and explicitly supplied tie-break metadata."""

	supplier_name: str
	pdf_file: str | Path | BinaryIO
	submission_date: str | date | datetime | None = None
	historical_experience_rating: int | float | None = None


class RFPOrchestrationError(RuntimeError):
	"""Raised when an RFP run fails before a complete result can be published."""

	def __init__(self, rfp_run_id: str, message: str) -> None:
		super().__init__(f"RFP run {rfp_run_id} failed: {message}")
		self.rfp_run_id = rfp_run_id


def run_rfp_evaluation(
	suppliers: Sequence[SupplierSubmission],
	llm_client: LLMClient,
	*,
	model: str | None = None,
	db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, object]:
	"""Run a complete RFP evaluation and return a JSON-exportable result.

	Supplier names, dates, and historical experience ratings come from the
	submissions supplied by the caller. Proposal text is extracted from each PDF
	and is the only source passed to the evaluation agent for criterion evidence.
	No incomplete run is persisted as successful: the existing SQLite schema
	stores completed runs atomically, so any supplier failure aborts the batch.
	"""
	rfp_run_id = str(uuid4())
	if not suppliers:
		raise RFPOrchestrationError(rfp_run_id, "at least one supplier PDF is required")

	names: set[str] = set()
	for supplier in suppliers:
		name = supplier.supplier_name.strip()
		if not name:
			raise RFPOrchestrationError(rfp_run_id, "a supplier name is empty")
		if name.casefold() in names:
			raise RFPOrchestrationError(
				rfp_run_id,
				f"duplicate supplier name {name!r}; each supplier must be unique",
			)
		names.add(name.casefold())

	connection = connect_db(db_path)
	try:
		try:
			active_criteria = get_active_criteria(connection)
			validate_active_criteria_weights(active_criteria)
		except Exception as error:
			raise RFPOrchestrationError(
				rfp_run_id,
				f"could not load valid active criteria from SQLite: {error}",
			) from error

		# The in-memory record remains running until all supplier work succeeds.
		run_record: dict[str, object] = {
			"rfp_run_id": rfp_run_id,
			"status": "running",
			"created_at": datetime.now(timezone.utc).isoformat(),
		}
		evaluations: list[dict[str, object]] = []
		for supplier in suppliers:
			name = supplier.supplier_name.strip()
			try:
				proposal_text = extract_pdf_text(supplier.pdf_file)
				evaluation = evaluate_supplier(
					name,
					proposal_text,
					active_criteria,
					llm_client,
					model=model,
				)
			except Exception as error:
				raise RFPOrchestrationError(
					rfp_run_id,
					f"supplier {name!r} could not be processed; no run was saved: {error}",
				) from error

			evaluation_result = dict(evaluation)
			evaluation_result["submission_date"] = _json_date(supplier.submission_date)
			evaluation_result["historical_experience_rating"] = (
				supplier.historical_experience_rating
			)
			evaluations.append(evaluation_result)

		try:
			scored_suppliers = score_suppliers(evaluations, active_criteria)
			ranked_suppliers = rank_suppliers(scored_suppliers)
		except Exception as error:
			raise RFPOrchestrationError(
				rfp_run_id,
				f"scoring or ranking failed; no run was saved: {error}",
			) from error

		warnings = [
			{"supplier_name": supplier["supplier_name"], "message": warning}
			for supplier in ranked_suppliers
			for warning in supplier.get("warnings", [])
			if isinstance(warning, str)
		]
		complete_result: dict[str, object] = {
			**run_record,
			"status": "completed",
			"criteria": [_criterion_snapshot(criterion) for criterion in active_criteria],
			"supplier_results": ranked_suppliers,
			"warnings": warnings,
		}
		try:
			database_run_id = save_run_result(connection, complete_result, ranked_suppliers)
		except Exception as error:
			raise RFPOrchestrationError(
				rfp_run_id,
				f"completed results could not be persisted; no successful result was returned: {error}",
			) from error

		complete_result["database_run_id"] = database_run_id
		return complete_result
	finally:
		connection.close()


def _criterion_snapshot(criterion: EvaluationCriterion) -> dict[str, object]:
	return {
		"criterion_id": criterion.id,
		"name": criterion.name,
		"weight": criterion.weight,
		"max_score": criterion.max_score,
		"active": criterion.active,
	}


def _json_date(value: str | date | datetime | None) -> str | None:
	if isinstance(value, datetime):
		return value.isoformat()
	if isinstance(value, date):
		return value.isoformat()
	return value
