"""Focused tests for the SQLite database module."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.database import (
    connect_db,
    get_active_criteria,
    get_run_result,
    get_supplier_results,
    initialize_database,
    save_run_result,
    update_criterion,
    validate_active_criteria_weights,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path)
        self.connection = connect_db(self.db_path)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def test_default_criteria_and_weight_validation(self) -> None:
        criteria = get_active_criteria(self.connection)
        self.assertEqual(len(criteria), 5)
        self.assertEqual(validate_active_criteria_weights(criteria), 100.0)
        self.assertTrue(all(criterion.max_score == 10 for criterion in criteria))

    def test_criteria_can_be_changed_and_reinitialized_without_reset(self) -> None:
        update_criterion(self.connection, "Technical Capability", 25.0, active=False)
        initialize_database(self.db_path)

        active_names = {criterion.name for criterion in get_active_criteria(self.connection)}
        self.assertNotIn("Technical Capability", active_names)
        with self.assertRaisesRegex(ValueError, "not 100%"):
            validate_active_criteria_weights(get_active_criteria(self.connection))

    def test_run_and_supplier_results_round_trip_as_json(self) -> None:
        complete_result = {
            "request_id": "rfp-001",
            "supplier_results": [{"supplier_name": "Apex Systems", "total_score": 87.5}],
        }
        suppliers = [
            {
                "supplier_name": "Apex Systems",
                "total_score": 87.5,
                "rank": 1,
                "criteria": {"Technical Capability": 9},
            }
        ]

        run_id = save_run_result(self.connection, complete_result, suppliers)

        self.assertEqual(get_run_result(self.connection, run_id)["result"], complete_result)
        saved_suppliers = get_supplier_results(self.connection, run_id)
        self.assertEqual(saved_suppliers[0]["result"], suppliers[0])
        stored_json = self.connection.execute(
            "SELECT result_json FROM rfp_runs WHERE id = ?", (run_id,)
        ).fetchone()["result_json"]
        self.assertEqual(json.loads(stored_json), complete_result)

    def test_insert_failure_rolls_back_run_and_supplier_rows(self) -> None:
        suppliers = [
            {"supplier_name": "Apex", "total_score": 80, "rank": 1},
            {"supplier_name": "Apex", "total_score": 78, "rank": 2},
        ]
        with self.assertRaises(sqlite3.IntegrityError):
            save_run_result(self.connection, {"run": "invalid"}, suppliers)

        run_count = self.connection.execute("SELECT COUNT(*) FROM rfp_runs").fetchone()[0]
        supplier_count = self.connection.execute(
            "SELECT COUNT(*) FROM supplier_results"
        ).fetchone()[0]
        self.assertEqual(run_count, 0)
        self.assertEqual(supplier_count, 0)


if __name__ == "__main__":
    unittest.main()