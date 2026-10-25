"""Tests for end-to-end RFP orchestration without calling an LLM."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.database import connect_db, initialize_database
from src.evaluation_agent import EvaluationError
from src.orchestrator import (
	RFPOrchestrationError,
	SupplierSubmission,
	run_rfp_evaluation,
)


class OrchestratorTests(unittest.TestCase):
	def setUp(self) -> None:
		self.temp_dir = tempfile.TemporaryDirectory()
		self.db_path = Path(self.temp_dir.name) / "rfp.db"
		initialize_database(self.db_path)

	def tearDown(self) -> None:
		self.temp_dir.cleanup()

	def submissions(self) -> list[SupplierSubmission]:
		return [
			SupplierSubmission(
				supplier_name="Apex Systems",
				pdf_file="apex.pdf",
				submission_date="2026-10-20",
				historical_experience_rating=4.0,
			),
			SupplierSubmission(
				supplier_name="BrightPath Tech",
				pdf_file="brightpath.pdf",
				submission_date="2026-10-21",
				historical_experience_rating=2.0,
			),
		]

	def evaluation_for(self, supplier_name: str, proposal_text: str, criteria, llm_client, *, model=None):
		return {
			"supplier_name": supplier_name,
			"criteria": [
				{
					"criterion_id": criterion.id,
					"score": 7,
					"max_score": criterion.max_score,
					"justification": f"Evidence assessed for {criterion.name}.",
					"evidence": ["Extracted text evidence."],
				}
				for criterion in criteria
			],
			"risks": [],
			"overall_summary": "Completed mock evaluation.",
			"warnings": ["A mock validation warning."],
		}

	def test_success_uses_extracted_text_metadata_and_persists_complete_result(self) -> None:
		with patch("src.orchestrator.extract_pdf_text", side_effect=["Apex text", "BrightPath text"]) as extract:
			with patch("src.orchestrator.evaluate_supplier", side_effect=self.evaluation_for) as evaluate:
				result = run_rfp_evaluation(
					self.submissions(),
					llm_client=object(),
					db_path=self.db_path,
				)

		self.assertEqual(extract.call_count, 2)
		self.assertEqual(evaluate.call_args_list[0].args[1], "Apex text")
		self.assertEqual(evaluate.call_args_list[1].args[1], "BrightPath text")
		self.assertEqual(result["status"], "completed")
		self.assertEqual(len(result["rfp_run_id"]), 36)
		self.assertEqual(len(result["supplier_results"]), 2)
		self.assertEqual(result["supplier_results"][0]["submission_date"], "2026-10-20")
		self.assertEqual(result["supplier_results"][0]["historical_experience_rating"], 4.0)
		self.assertEqual(len(result["warnings"]), 2)

		connection = connect_db(self.db_path)
		try:
			stored = connection.execute("SELECT result_json FROM rfp_runs").fetchone()
			self.assertIsNotNone(stored)
			self.assertIn(result["rfp_run_id"], stored["result_json"])
			self.assertEqual(
				connection.execute("SELECT COUNT(*) FROM supplier_results").fetchone()[0],
				2,
			)
		finally:
			connection.close()

	def test_supplier_failure_does_not_persist_successful_partial_run(self) -> None:
		def evaluate_then_fail(
			supplier_name: str,
			proposal_text: str,
			criteria,
			llm_client,
			*,
			model=None,
		):
			if supplier_name == "BrightPath Tech":
				raise EvaluationError("provider unavailable")
			return self.evaluation_for(
				supplier_name,
				proposal_text,
				criteria,
				llm_client,
				model=model,
			)

		with patch("src.orchestrator.extract_pdf_text", side_effect=["Apex text", "BrightPath text"]):
			with patch(
				"src.orchestrator.evaluate_supplier",
				side_effect=evaluate_then_fail,
			):
				with self.assertRaisesRegex(RFPOrchestrationError, "no run was saved") as error:
					run_rfp_evaluation(
						self.submissions(),
						llm_client=object(),
						db_path=self.db_path,
					)

		self.assertEqual(len(error.exception.rfp_run_id), 36)
		connection = connect_db(self.db_path)
		try:
			self.assertEqual(connection.execute("SELECT COUNT(*) FROM rfp_runs").fetchone()[0], 0)
		finally:
			connection.close()

	def test_invalid_criteria_weights_abort_before_llm_call(self) -> None:
		connection = connect_db(self.db_path)
		try:
			connection.execute(
				"UPDATE evaluation_criteria SET weight = 31 WHERE name = ?",
				("Technical Capability",),
			)
			connection.commit()
		finally:
			connection.close()

		with patch("src.orchestrator.evaluate_supplier") as evaluate:
			with self.assertRaisesRegex(RFPOrchestrationError, "weights total"):
				run_rfp_evaluation(
					self.submissions(),
					llm_client=object(),
					db_path=self.db_path,
				)
		evaluate.assert_not_called()


if __name__ == "__main__":
	unittest.main()