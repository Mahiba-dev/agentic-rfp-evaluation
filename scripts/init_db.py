"""Initialize the local RFP evaluation database."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (  # noqa: E402
	connect_db,
	get_active_criteria,
	initialize_database,
	validate_active_criteria_weights,
)


def main() -> None:
	db_path = initialize_database()
	with connect_db(db_path) as connection:
		criteria = get_active_criteria(connection)
		total_weight = validate_active_criteria_weights(criteria)

	print(f"Initialized database: {db_path}")
	print(f"Active criteria: {len(criteria)} (weights total {total_weight:g}%)")


if __name__ == "__main__":
	main()
