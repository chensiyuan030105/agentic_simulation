from __future__ import annotations

from pathlib import Path
from typing import Any


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""
    try:
        import yaml
    except Exception as exc:  # noqa: BLE001
        raise ImportError("PyYAML is required. Install with: pip install pyyaml") from exc

    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}, got {type(data)!r}")
    return data


def require_number_pair(data: dict[str, Any], key: str) -> tuple[float, float]:
    value = data.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"'{key}' must be a length-2 list")
    return float(value[0]), float(value[1])


def require_color(data: dict[str, Any], key: str) -> tuple[float, float, float]:
    value = data.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"'{key}' must be a length-3 RGB list")
    return tuple(max(0.0, min(1.0, float(v))) for v in value)  # type: ignore[return-value]
