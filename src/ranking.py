"""Deterministic peer ranking using the specified tie-break order."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime


class RankingError(ValueError):
	"""Raised when a supplier cannot be ranked from its result metadata."""


def rank_suppliers(
	suppliers: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
	"""Sort suppliers by PPI, date, experience, then name; assign sequential ranks."""
	prepared: list[tuple[dict[str, object], float, date | None, float | None, str, str]] = []
	seen_names: set[str] = set()
	for supplier in suppliers:
		result = dict(supplier)
		name = result.get("supplier_name")
		if not isinstance(name, str) or not name.strip():
			raise RankingError("Every ranked supplier needs a non-empty supplier_name.")
		name = name.strip()
		name_key = name.casefold()
		if name_key in seen_names:
			raise RankingError(f"Duplicate supplier name {name!r} cannot be ranked uniquely.")
		seen_names.add(name_key)

		ppi = result.get("ppi")
		if isinstance(ppi, bool) or not isinstance(ppi, (int, float)) or not math.isfinite(ppi):
			raise RankingError(f"Supplier {name!r} needs a finite numeric PPI.")

		submission_date = _parse_submission_date(result.get("submission_date"), name)
		experience = _parse_experience(result.get("historical_experience_rating"), name)
		result["supplier_name"] = name
		prepared.append((result, float(ppi), submission_date, experience, name_key, name))

	prepared.sort(
		key=lambda entry: (
			-entry[1],
			entry[2] is None,
			entry[2] or date.max,
			entry[3] is None,
			-(entry[3] if entry[3] is not None else 0.0),
			entry[4],
			entry[5],
		)
	)

	ranked: list[dict[str, object]] = []
	for rank, (supplier, _, _, _, _, _) in enumerate(prepared, start=1):
		supplier["rank"] = rank
		ranked.append(supplier)
	return ranked


def _parse_submission_date(value: object, supplier_name: str) -> date | None:
	if value is None or value == "":
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	if isinstance(value, str):
		try:
			return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
		except ValueError as error:
			raise RankingError(
				f"Supplier {supplier_name!r} has invalid submission_date {value!r}; "
			"use an ISO date or datetime."
			) from error
	raise RankingError(
			f"Supplier {supplier_name!r} submission_date must be an ISO string, "
			"date, or datetime."
		)


def _parse_experience(value: object, supplier_name: str) -> float | None:
	if value is None or value == "":
		return None
	if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
		raise RankingError(
			f"Supplier {supplier_name!r} historical_experience_rating must be finite and numeric."
		)
	return float(value)
