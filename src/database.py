"""SQLite persistence for criteria and supplier evaluation runs."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "rfp_evaluation.db"
WEIGHT_TOLERANCE = 1e-6

DEFAULT_CRITERIA: tuple[tuple[str, float], ...] = (
	("Technical Capability", 30.0),
	("Implementation Plan", 20.0),
	("Commercial Value", 20.0),
	("Security & Compliance", 20.0),
	("Support & Experience", 10.0),
)


@dataclass(frozen=True)
class EvaluationCriterion:
	id: int
	name: str
	weight: float
	max_score: int
	active: bool


def connect_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
	"""Open a connection with foreign-key enforcement enabled."""
	path = str(db_path)
	if path != ":memory:":
		Path(path).parent.mkdir(parents=True, exist_ok=True)

	connection = sqlite3.connect(path)
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA foreign_keys = ON")
	return connection


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
	"""Create the schema and add default criteria without replacing edits."""
	path = Path(db_path)
	connection = connect_db(db_path)
	try:
		connection.execute("BEGIN IMMEDIATE")
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS evaluation_criteria (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 100),
				max_score INTEGER NOT NULL DEFAULT 10 CHECK (max_score > 0),
				active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
				updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
			)
			"""
		)
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS rfp_runs (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
				result_json TEXT NOT NULL CHECK (json_valid(result_json))
			)
			"""
		)
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS supplier_results (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				run_id INTEGER NOT NULL REFERENCES rfp_runs(id) ON DELETE CASCADE,
				supplier_name TEXT NOT NULL,
				total_score REAL NOT NULL,
				rank INTEGER NOT NULL CHECK (rank > 0),
				result_json TEXT NOT NULL CHECK (json_valid(result_json)),
				UNIQUE (run_id, supplier_name)
			)
			"""
		)
		connection.executemany(
			"""
			INSERT OR IGNORE INTO evaluation_criteria
				(name, weight, max_score, active)
			VALUES (?, ?, 10, 1)
			""",
			DEFAULT_CRITERIA,
		)
		connection.commit()
	except Exception:
		connection.rollback()
		raise
	finally:
		connection.close()

	return path


def get_active_criteria(connection: sqlite3.Connection) -> list[EvaluationCriterion]:
	"""Return active criteria in their insertion order."""
	rows = connection.execute(
		"""
		SELECT id, name, weight, max_score, active
		FROM evaluation_criteria
		WHERE active = ?
		ORDER BY id
		""",
		(1,),
	).fetchall()
	return [
		EvaluationCriterion(
			id=row["id"],
			name=row["name"],
			weight=row["weight"],
			max_score=row["max_score"],
			active=bool(row["active"]),
		)
		for row in rows
	]


def validate_active_criteria_weights(
	criteria: Sequence[EvaluationCriterion],
) -> float:
	"""Return the active weight total, raising unless it equals 100%."""
	if not criteria:
		raise ValueError("At least one active evaluation criterion is required.")

	total = sum(criterion.weight for criterion in criteria)
	if not math.isclose(total, 100.0, rel_tol=0.0, abs_tol=WEIGHT_TOLERANCE):
		raise ValueError(f"Active criterion weights total {total:g}%, not 100%.")
	return total


def update_criterion(
	connection: sqlite3.Connection,
	name: str,
	weight: float,
	max_score: int = 10,
	active: bool = True,
) -> None:
	"""Create or update one criterion while preserving other criteria."""
	if not name.strip():
		raise ValueError("Criterion name cannot be empty.")
	if not math.isfinite(weight) or not 0 <= weight <= 100:
		raise ValueError("Criterion weight must be between 0 and 100.")
	if max_score <= 0:
		raise ValueError("Criterion maximum score must be positive.")

	with connection:
		connection.execute(
			"""
			INSERT INTO evaluation_criteria (name, weight, max_score, active)
			VALUES (?, ?, ?, ?)
			ON CONFLICT(name) DO UPDATE SET
				weight = excluded.weight,
				max_score = excluded.max_score,
				active = excluded.active,
				updated_at = CURRENT_TIMESTAMP
			""",
			(name.strip(), weight, max_score, int(active)),
		)


def save_run_result(
	connection: sqlite3.Connection,
	complete_result: Mapping[str, object],
	suppliers: Sequence[Mapping[str, object]],
) -> int:
	"""Persist a complete run payload and its supplier rows atomically.

	Each supplier mapping must contain ``supplier_name``, ``total_score``, and
	``rank``. The full mapping is stored as JSON in ``supplier_results``.
	"""
	run_json = _to_json(complete_result)
	prepared_suppliers: list[tuple[str, float, int, str]] = []

	for supplier in suppliers:
		name = supplier.get("supplier_name")
		score = supplier.get("total_score")
		rank = supplier.get("rank")
		if not isinstance(name, str) or not name.strip():
			raise ValueError("Each supplier result needs a non-empty supplier_name.")
		if isinstance(score, bool) or not isinstance(score, (int, float)):
			raise ValueError(f"Supplier {name!r} needs a numeric total_score.")
		if not math.isfinite(score):
			raise ValueError(f"Supplier {name!r} total_score must be finite.")
		if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
			raise ValueError(f"Supplier {name!r} needs a positive integer rank.")
		prepared_suppliers.append((name.strip(), float(score), rank, _to_json(supplier)))

	with connection:
		cursor = connection.execute(
			"INSERT INTO rfp_runs (result_json) VALUES (?)",
			(run_json,),
		)
		run_id = cursor.lastrowid
		if run_id is None:
			raise RuntimeError("SQLite did not return an ID for the new RFP run.")
		connection.executemany(
			"""
			INSERT INTO supplier_results
				(run_id, supplier_name, total_score, rank, result_json)
			VALUES (?, ?, ?, ?, ?)
			""",
			[
				(run_id, name, score, rank, result_json)
				for name, score, rank, result_json in prepared_suppliers
			],
		)
	return run_id


def get_run_result(connection: sqlite3.Connection, run_id: int) -> dict[str, object] | None:
	"""Return a run row with its complete result decoded from JSON."""
	row = connection.execute(
		"SELECT id, created_at, result_json FROM rfp_runs WHERE id = ?",
		(run_id,),
	).fetchone()
	if row is None:
		return None
	return {
		"id": row["id"],
		"created_at": row["created_at"],
		"result": json.loads(row["result_json"]),
	}


def get_supplier_results(
	connection: sqlite3.Connection,
	run_id: int,
) -> list[dict[str, object]]:
	"""Return decoded supplier result rows for one run."""
	rows = connection.execute(
		"""
		SELECT id, supplier_name, total_score, rank, result_json
		FROM supplier_results
		WHERE run_id = ?
		ORDER BY rank, id
		""",
		(run_id,),
	).fetchall()
	return [
		{
			"id": row["id"],
			"supplier_name": row["supplier_name"],
			"total_score": row["total_score"],
			"rank": row["rank"],
			"result": json.loads(row["result_json"]),
		}
		for row in rows
	]


def _to_json(value: Mapping[str, object]) -> str:
	try:
		return json.dumps(value, ensure_ascii=False, allow_nan=False)
	except (TypeError, ValueError) as error:
		raise ValueError("Result data must be JSON serializable.") from error
