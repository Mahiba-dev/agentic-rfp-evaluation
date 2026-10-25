"""Streamlit interface for the Agentic RFP Evaluation and Supplier Ranking app."""

from __future__ import annotations

import json
import os
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import streamlit as st

st.set_page_config(
	page_title="Agentic RFP Evaluation",
	page_icon="📑",
	layout="wide",
)

IMPORT_ERROR: Exception | None = None
try:
	from src.database import (
		DEFAULT_DB_PATH,
		connect_db,
		get_active_criteria,
		initialize_database,
		validate_active_criteria_weights,
	)
	from src.evaluation_agent import create_llm_client
	from src.orchestrator import (
		RFPOrchestrationError,
		SupplierSubmission,
		run_rfp_evaluation,
	)
except Exception as error:
	IMPORT_ERROR = error


def _safe_message(message: str) -> str:
	"""Redact configured credentials before any exception is shown in the UI."""
	for variable_name in ("LLM_API_KEY", "OPENAI_API_KEY"):
		secret = os.getenv(variable_name)
		if secret:
			message = message.replace(secret, "[redacted]")
	return message


def _load_criteria() -> tuple[list[Any], str | None, str | None]:
	if IMPORT_ERROR is not None:
		return [], None, f"Application imports failed: {_safe_message(str(IMPORT_ERROR))}"
	try:
		db_path = initialize_database(DEFAULT_DB_PATH)
		connection = connect_db(db_path)
		try:
			criteria = get_active_criteria(connection)
		finally:
			connection.close()
		weight_total = validate_active_criteria_weights(criteria)
		return criteria, f"{db_path}", None if weight_total == 100.0 else "Invalid criteria weights."
	except Exception as error:
		return [], None, f"Could not load active criteria from SQLite: {_safe_message(str(error))}"


def _supplier_key(index: int, filename: str, file_bytes: bytes) -> str:
	file_digest = sha256(file_bytes).hexdigest()[:12]
	return f"supplier_{index}_{Path(filename).name}_{file_digest}"


def _render_results(result: dict[str, object]) -> None:
	st.header("4. Leaderboard")
	suppliers = result.get("supplier_results", [])
	if not isinstance(suppliers, list) or not suppliers:
		st.warning("The completed run contains no supplier results.")
		return

	leaderboard = [
		{
			"Rank": supplier.get("rank"),
			"Supplier": supplier.get("supplier_name"),
			"Absolute score": supplier.get("absolute_weighted_score"),
			"PPI": supplier.get("ppi"),
			"Submission date": supplier.get("submission_date"),
			"Experience rating": supplier.get("historical_experience_rating"),
		}
		for supplier in suppliers
		if isinstance(supplier, dict)
	]
	st.dataframe(leaderboard, hide_index=True, use_container_width=True)

	st.header("5. Detailed scorecard")
	supplier_names = [str(supplier.get("supplier_name", "Unknown")) for supplier in suppliers]
	selected_name = st.selectbox("Supplier", supplier_names, key="scorecard_supplier")
	selected_supplier = next(
		(
			supplier
			for supplier in suppliers
			if supplier.get("supplier_name") == selected_name
		),
		{},
	)
	metric_by_id = {
		item.get("criterion_id"): item
		for item in selected_supplier.get("criterion_results", [])
		if isinstance(item, dict)
	}
	evaluation_by_id = {
		item.get("criterion_id"): item
		for item in selected_supplier.get("criteria", [])
		if isinstance(item, dict)
	}
	scorecard: list[dict[str, object]] = []
	for criterion in result.get("criteria", []):
		if not isinstance(criterion, dict):
			continue
		criterion_id = criterion.get("criterion_id")
		metric = metric_by_id.get(criterion_id, {})
		evaluation = evaluation_by_id.get(criterion_id, {})
		scorecard.append(
			{
				"Criterion": criterion.get("name"),
				"Score": evaluation.get("score", metric.get("score")),
				"Maximum": criterion.get("max_score"),
				"Benchmark": metric.get("benchmark"),
				"Gap": metric.get("gap"),
				"Relative %": metric.get("relative_performance_percentage"),
				"Weight %": criterion.get("weight"),
				"Evidence": "; ".join(evaluation.get("evidence", [])),
				"Justification": evaluation.get("justification", ""),
			}
		)
	st.dataframe(scorecard, hide_index=True, use_container_width=True)

	st.header("6. Run details")
	st.write(f"**RFP_RUN_ID:** `{result.get('rfp_run_id', 'Unknown')}`")
	st.write(f"**Status:** {result.get('status', 'Unknown')}")
	st.write(f"**Created:** {result.get('created_at', 'Unknown')}")
	st.caption(
		"Tie-break order: higher PPI, earlier submission date, higher historical "
		"experience rating, then supplier name alphabetically."
	)
	warnings = result.get("warnings", [])
	with st.expander(f"Warnings ({len(warnings)})", expanded=bool(warnings)):
		if warnings:
			for warning in warnings:
				if isinstance(warning, dict):
					st.warning(f"{warning.get('supplier_name', 'Run')}: {warning.get('message', '')}")
				else:
					st.warning(str(warning))
		else:
			st.write("No validation or scoring warnings.")

	st.download_button(
		"Download complete JSON",
		data=json.dumps(result, indent=2, ensure_ascii=False),
		file_name=f"{result.get('rfp_run_id', 'rfp-run')}.json",
		mime="application/json",
		key="download_rfp_json",
	)


criteria, database_path, criteria_error = _load_criteria()

st.title("Agentic RFP Evaluation")
st.caption("Evidence-led proposal review with deterministic scoring and supplier ranking.")

st.header("1. Criteria")
if criteria_error:
	st.error(criteria_error)
elif criteria:
	st.caption(f"Active criteria from `{database_path}`")
	st.dataframe(
		[
			{
				"Criterion": criterion.name,
				"Weight %": criterion.weight,
				"Maximum score": criterion.max_score,
			}
			for criterion in criteria
		],
		hide_index=True,
		use_container_width=True,
	)
else:
	st.warning("No active criteria are configured. The supplier inputs remain available.")

st.header("2. Supplier input")
uploaded_files = st.file_uploader(
	"Upload supplier proposals (PDF)",
	type=["pdf"],
	accept_multiple_files=True,
	help="Select one PDF per supplier. Text must be selectable; scanned PDFs need OCR first.",
	key="supplier_pdf_uploader",
)
if uploaded_files:
	st.caption(f"{len(uploaded_files)} PDF(s) selected.")
else:
	st.caption("No PDFs selected yet. Supplier metadata and evaluation controls are available below.")

metadata_values: list[tuple[str, date | None, int | float | None]] = []
with st.form("supplier_evaluation_form", clear_on_submit=False):
	if uploaded_files:
		for index, uploaded_file in enumerate(uploaded_files):
			file_bytes = uploaded_file.getvalue()
			key = _supplier_key(index, uploaded_file.name, file_bytes)
			default_name = Path(uploaded_file.name).stem.replace("_", " ").title()
			st.subheader(f"Supplier {index + 1}: {uploaded_file.name}")
			name_col, date_col, experience_col = st.columns([1.3, 1, 1])
			with name_col:
				supplier_name = st.text_input(
					"Supplier name",
					value=default_name,
					key=f"{key}_name",
				)
			with date_col:
				submission_date = st.date_input(
					"Submission date",
					value=None,
					key=f"{key}_date",
				)
			with experience_col:
				experience_rating = st.number_input(
					"Historical experience rating",
					min_value=0.0,
					value=None,
					step=0.1,
					key=f"{key}_experience",
					help="Use the same numeric scale for every supplier; higher values rank first.",
				)
			metadata_values.append((supplier_name, submission_date, experience_rating))
	else:
		st.subheader("Supplier metadata (ready for the first PDF)")
		name_col, date_col, experience_col = st.columns([1.3, 1, 1])
		with name_col:
			st.text_input("Supplier name", value="", key="empty_supplier_name")
		with date_col:
			st.date_input("Submission date", value=None, key="empty_submission_date")
		with experience_col:
			st.number_input(
				"Historical experience rating",
				min_value=0.0,
				value=None,
				step=0.1,
				key="empty_experience_rating",
				help="Use the same numeric scale for every supplier; higher values rank first.",
			)

	submit_evaluation = st.form_submit_button(
		"Evaluate suppliers",
		type="primary",
		use_container_width=True,
	)

if "rfp_evaluation_result" not in st.session_state:
	st.session_state["rfp_evaluation_result"] = None

if submit_evaluation:
	st.session_state["rfp_evaluation_result"] = None
	input_errors: list[str] = []
	if not uploaded_files:
		input_errors.append("Upload at least one supplier PDF before evaluation.")
	if not criteria or criteria_error:
		input_errors.append("Evaluation cannot start until active criteria load and total 100%.")
	for index, (supplier_name, submission_date, experience_rating) in enumerate(metadata_values):
		if not supplier_name.strip():
			input_errors.append(f"Supplier {index + 1}: enter a supplier name.")
		if submission_date is None:
			input_errors.append(f"Supplier {index + 1}: enter a submission date.")
		if experience_rating is None:
			input_errors.append(f"Supplier {index + 1}: enter a historical experience rating.")

	if input_errors:
		for message in input_errors:
			st.error(message)
	elif IMPORT_ERROR is not None:
		st.error("The application modules are unavailable; no evaluation was started.")
	else:
		submissions = [
			SupplierSubmission(
				supplier_name=supplier_name,
				pdf_file=uploaded_file,
				submission_date=submission_date,
				historical_experience_rating=experience_rating,
			)
			for uploaded_file, (supplier_name, submission_date, experience_rating)
			in zip(uploaded_files, metadata_values, strict=True)
		]
		try:
			with st.spinner("Extracting proposal text and evaluating suppliers…"):
				llm_client = create_llm_client()
				result = run_rfp_evaluation(submissions, llm_client)
			st.session_state["rfp_evaluation_result"] = result
			st.success("Evaluation completed and saved.")
		except RFPOrchestrationError as error:
			st.error(_safe_message(str(error)))
		except Exception as error:
			st.error(
				"Evaluation could not be completed. Check the configured LLM provider, "
				f"credentials, and application dependencies. ({type(error).__name__})"
			)

result = st.session_state.get("rfp_evaluation_result")
if isinstance(result, dict):
	_render_results(result)
