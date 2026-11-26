"""As-of boundary validation for FINCEPT research backtest window payloads.

Pure, dependency-free validation of a backtest window declaration. The module
performs no I/O, no data download and no backtest execution; it only inspects
an in-memory payload and returns a new dict of validated values.

Ordering invariant enforced::

    train_end <= data_asof <= decision_at < evaluation_start <= evaluation_end

which guarantees that no evaluation period overlaps the training period and
that every record used for a decision was already available (as-of) at the
moment the decision was made.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

__all__ = ["validate_backtest_window", "REQUIRED_KEYS"]

REQUIRED_KEYS = (
    "decision_at",
    "data_asof",
    "train_end",
    "evaluation_start",
    "evaluation_end",
)

_TIMESTAMP_KEYS = (
    "decision_at",
    "data_asof",
    "train_end",
    "evaluation_start",
    "evaluation_end",
)

_NON_TIMESTAMP_KEYS = ("provider", "dataset_sha256")

_UTC_ZULU_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_PROVIDER_RE = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _require_mapping(payload: object) -> Mapping:
    if isinstance(payload, bool) or not isinstance(payload, Mapping):
        raise TypeError(
            "payload must be a mapping, got " + type(payload).__name__
        )
    return payload


def _require_exact_keys(payload: Mapping) -> None:
    required = set(REQUIRED_KEYS) | set(_NON_TIMESTAMP_KEYS)
    present = set(payload.keys())
    missing = sorted(required - present)
    extra = sorted(present - required)
    if missing:
        raise ValueError("missing required key(s): " + ", ".join(missing))
    if extra:
        raise ValueError("unexpected extra key(s): " + ", ".join(extra))


def _parse_utc_timestamp(key: str, value: object) -> tuple[str, datetime]:
    if isinstance(value, bool) or not isinstance(value, str):
        raise TypeError(
            key + " must be an ISO-8601 UTC string, got " + type(value).__name__
        )
    if not value.isascii():
        raise ValueError(key + " must contain ASCII characters only")
    if _UTC_ZULU_RE.fullmatch(value) is None:
        raise ValueError(
            key + " must match YYYY-MM-DDTHH:MM:SSZ, got " + repr(value)
        )
    try:
        parsed = datetime.strptime(value, _UTC_FORMAT)
    except ValueError as exc:
        raise ValueError(key + " is not a valid UTC timestamp: " + str(exc)) from exc
    return value, parsed


def _validate_provider(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise TypeError("provider must be a string, got " + type(value).__name__)
    if not value.isascii() or _PROVIDER_RE.fullmatch(value) is None:
        raise ValueError(
            "provider must be 1-80 characters of [A-Za-z0-9_.:-], got " + repr(value)
        )
    return value


def _validate_dataset_sha256(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise TypeError(
            "dataset_sha256 must be a string, got " + type(value).__name__
        )
    if not value.isascii() or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(
            "dataset_sha256 must be exactly 64 lowercase hex characters, got "
            + repr(value)
        )
    return value


def validate_backtest_window(payload: object) -> dict:
    """Validate a backtest window declaration and return a new dict.

    Args:
        payload: Mapping with exactly the keys ``decision_at``, ``data_asof``,
            ``train_end``, ``evaluation_start``, ``evaluation_end``,
            ``provider`` and ``dataset_sha256``. Timestamps are strict ISO UTC
            strings of the form ``YYYY-MM-DDTHH:MM:SSZ``.

    Returns:
        A newly constructed dict holding the validated values.

    Raises:
        TypeError: If the payload is not a mapping, or a value has the wrong
            Python type (including booleans where strings are required).
        ValueError: If keys are missing or extra, timestamps are malformed,
            the as-of ordering is violated (future data or an evaluation
            window overlapping training), or ``provider`` /
            ``dataset_sha256`` do not match their required shapes.
    """
    mapping = _require_mapping(payload)
    _require_exact_keys(mapping)

    timestamps: dict[str, str] = {}
    moments: dict[str, datetime] = {}
    for key in _TIMESTAMP_KEYS:
        raw, parsed = _parse_utc_timestamp(key, mapping[key])
        timestamps[key] = raw
        moments[key] = parsed

    provider = _validate_provider(mapping["provider"])
    dataset_sha256 = _validate_dataset_sha256(mapping["dataset_sha256"])

    train_end = moments["train_end"]
    data_asof = moments["data_asof"]
    decision_at = moments["decision_at"]
    evaluation_start = moments["evaluation_start"]
    evaluation_end = moments["evaluation_end"]

    if train_end > data_asof:
        raise ValueError(
            "train_end must be <= data_asof (training data must be available "
            "as of the data snapshot)"
        )
    if data_asof > decision_at:
        raise ValueError(
            "data_asof must be <= decision_at (no future data may be used at "
            "decision time)"
        )
    if decision_at >= evaluation_start:
        raise ValueError(
            "decision_at must be strictly earlier than evaluation_start "
            "(training/decision window must not overlap evaluation)"
        )
    if evaluation_start > evaluation_end:
        raise ValueError("evaluation_start must be <= evaluation_end")

    return {
        "decision_at": timestamps["decision_at"],
        "data_asof": timestamps["data_asof"],
        "train_end": timestamps["train_end"],
        "evaluation_start": timestamps["evaluation_start"],
        "evaluation_end": timestamps["evaluation_end"],
        "provider": provider,
        "dataset_sha256": dataset_sha256,
    }
