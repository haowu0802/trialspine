from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse


def task_id_from_referer(referer: str | None) -> str:
    if not referer:
        return "tmb:unknown"
    path = urlparse(referer).path
    # Prefer /TMB_Tests/TMB_<Name>/ so we don't latch onto the folder "TMB_Tests"
    m = re.search(r"/TMB_Tests/TMB_([^/]+)/", path)
    if m:
        return f"tmb:{m.group(1)}"
    m = re.search(r"/TMB_([^/]+)/", path)
    if m and m.group(1).lower() != "tests":
        return f"tmb:{m.group(1)}"
    m = re.search(r"/([^/]+)_Main", path)
    if m:
        return f"tmb:{m.group(1)}"
    return "tmb:unknown"


def extract_rt_ms(obj: dict[str, Any]) -> float | None:
    for key in ("rt", "rt_ms", "RT", "response_time_duration_ms"):
        if key in obj and obj[key] is not None:
            try:
                return float(obj[key])
            except (TypeError, ValueError):
                pass
    return None


def extract_correct(obj: dict[str, Any]) -> bool | None:
    for key in ("correct", "user_response_correct"):
        if key in obj and obj[key] is not None:
            v = obj[key]
            if isinstance(v, bool):
                return v
            if v in (0, 1, "0", "1"):
                return bool(int(v))
    return None


def extract_response(obj: dict[str, Any]) -> str | None:
    for key in ("response", "user_response"):
        if key in obj and obj[key] is not None:
            return str(obj[key])[:64]
    return None


def extract_trial_type(obj: dict[str, Any]) -> str:
    t = obj.get("type") or obj.get("trialType") or obj.get("trial_type") or "test"
    t = str(t).lower()
    if "practice" in t:
        return "practice"
    return "test"


def flatten_tmb_trials(data: Any) -> list[dict[str, Any]]:
    """Best-effort flatten of TMB trial arrays into trial columns."""
    if not isinstance(data, list):
        return []

    rows: list[dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            rows.append(
                {
                    "trial_index": i,
                    "trial_type": "test",
                    "stimulus_id": "tmb_item",
                    "response": None,
                    "correct": None,
                    "rt_ms": None,
                    "raw_json": json.dumps(item, ensure_ascii=False),
                }
            )
            continue

        # Skip summary-like rows sometimes appended for local save
        if item.get("type") == "summaryScores":
            continue

        rows.append(
            {
                "trial_index": int(item.get("trialId") or item.get("trial_index") or i),
                "trial_type": extract_trial_type(item),
                "stimulus_id": str(
                    item.get("stimulus_id")
                    or item.get("probe")
                    or item.get("word")
                    or item.get("target")
                    or "tmb_item"
                )[:64],
                "response": extract_response(item),
                "correct": extract_correct(item),
                "rt_ms": extract_rt_ms(item),
                "raw_json": json.dumps(item, ensure_ascii=False),
            }
        )
    return rows
