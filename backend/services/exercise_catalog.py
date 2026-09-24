"""
Exercise catalog loader backed by a CSV file.

The CSV is the authoritative list of exercises offered to users. Schema (exact
column order):

    exercise_id,exercise_name,target_joint,side,rom_min_deg,rom_max_deg,target_reps

Catalog ids are mapped to existing rehabilitation registry keys so the analysis
pipeline keeps working. The registry itself is never pruned here; entries
without a catalog mapping (e.g. shoulder_abduction, knee_flexion) remain
available to other callers but are simply not offered by this catalog.

The path is overridable via the EXERCISE_CATALOG_PATH environment variable.
"""
import csv
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

REQUIRED_COLUMNS = (
    "exercise_id",
    "exercise_name",
    "target_joint",
    "side",
    "rom_min_deg",
    "rom_max_deg",
    "target_reps",
)
VALID_SIDES = {"left", "right", "both"}

# Catalog id -> rehabilitation.exercises registry key
REGISTRY_KEY_MAP: Dict[str, str] = {
    "ELBOW_FLEX": "elbow_flexion",
    "SHOULDER_FLEX": "shoulder_flexion",
}

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "exercises" / "exercises.csv"


class ExerciseCatalogError(ValueError):
    """Raised when the exercise catalog is missing, malformed, or invalid."""


def catalog_path() -> Path:
    """Resolve the catalog path (env override wins over the repo default)."""
    override = os.getenv("EXERCISE_CATALOG_PATH")
    return Path(override) if override else _DEFAULT_PATH


def _require(raw: Dict[str, Any], name: str, line_no: int) -> str:
    value = (raw.get(name) or "").strip()
    if not value:
        raise ExerciseCatalogError(f"Row {line_no}: '{name}' must not be empty.")
    return value


def _parse_row(raw: Dict[str, Any], line_no: int) -> Dict[str, Any]:
    exercise_id = _require(raw, "exercise_id", line_no)
    exercise_name = _require(raw, "exercise_name", line_no)
    target_joint = _require(raw, "target_joint", line_no)
    side = _require(raw, "side", line_no).lower()
    if side not in VALID_SIDES:
        raise ExerciseCatalogError(
            f"Row {line_no}: invalid side '{side}'. Must be one of {sorted(VALID_SIDES)}."
        )

    def _number(name: str) -> float:
        value = _require(raw, name, line_no)
        try:
            return float(value)
        except ValueError:
            raise ExerciseCatalogError(
                f"Row {line_no}: '{name}' must be numeric (got '{value}')."
            )

    rom_min_deg = _number("rom_min_deg")
    rom_max_deg = _number("rom_max_deg")

    reps_raw = _require(raw, "target_reps", line_no)
    try:
        target_reps = int(float(reps_raw))
    except ValueError:
        raise ExerciseCatalogError(
            f"Row {line_no}: 'target_reps' must be an integer (got '{reps_raw}')."
        )

    return {
        "exercise_id": exercise_id,
        "exercise_name": exercise_name,
        "target_joint": target_joint,
        "side": side,
        "rom_min_deg": rom_min_deg,
        "rom_max_deg": rom_max_deg,
        "target_reps": target_reps,
        "registry_key": REGISTRY_KEY_MAP.get(exercise_id),
    }


@lru_cache(maxsize=16)
def _load_cached(path_str: str) -> tuple:
    path = Path(path_str)
    if not path.is_file():
        raise ExerciseCatalogError(f"Exercise catalog not found: {path}")

    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
            if missing:
                raise ExerciseCatalogError(
                    "Exercise catalog missing required columns: " + ", ".join(missing)
                )
            for line_no, raw in enumerate(reader, start=2):
                if raw is None or all((value or "").strip() == "" for value in raw.values()):
                    continue
                rows.append(_parse_row(raw, line_no))
    except ExerciseCatalogError:
        raise
    except OSError as exc:
        raise ExerciseCatalogError(f"Failed to read exercise catalog '{path}': {exc}") from exc

    if not rows:
        raise ExerciseCatalogError(f"Exercise catalog '{path}' contains no data rows.")
    return tuple(rows)


def load_catalog(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load and validate the catalog, returning a list of parsed row dicts."""
    target = Path(path) if path else catalog_path()
    return [dict(row) for row in _load_cached(str(target))]


def clear_catalog_cache() -> None:
    """Clear the cached catalog (used by tests and reload tooling)."""
    _load_cached.cache_clear()


def catalog_row_for_registry_key(registry_key: str) -> Optional[Dict[str, Any]]:
    """Return the catalog row mapped to a registry key, or None."""
    for row in load_catalog():
        if row["registry_key"] == registry_key:
            return row
    return None
