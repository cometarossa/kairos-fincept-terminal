"""Fincept source-only Qt screen-smoke safety contract. Does NOT execute Qt.

This deliberately reports the original harness's known empty-registry blind
spot; a source guard is NOT GUI runtime proof. No broker or environment calls.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

RELATIVE_SOURCE = "fincept-qt/src/app/ScreenSmokeTest.cpp"
SCHEMA = "fincept_qt_smoke_source_contract_v1"


def analyze(text: str) -> dict:
    if not isinstance(text, str):
        raise TypeError("source text required")
    start = text.find("int run_screen_smoke_test(")
    s = text[start:] if start >= 0 else ""
    positions = {
        "null": s.find("if (!router)"),
        "pin": s.find("if (auth::InactivityGuard::instance().is_terminal_locked())"),
        "inventory": s.find("router->all_screen_ids()"),
        "loop": s.find("for (const QString& id : ids)"),
        "breadcrumb": s.find("[Smoke] >>> constructing"),
        "navigate": s.find("router->navigate(id, /*exclusive=*/true)"),
        "wait": s.find("wait_for_construction(router, id)"),
        "failure": s.find("failures << id;"),
        "settle": s.find("spin(kSettleMs)"),
        "terminal": s.find("if (failures.isEmpty())"),
    }
    violations = []

    if start < 0:
        violations.append("MISSING_ORIGINAL_SMOKE_ENTRYPOINT")
    if any(positions[x] < 0 for x in ("null", "pin", "inventory", "loop")):
        violations.append("MISSING_NULL_OR_PIN_OR_FULL_REGISTRY_ITERATION")
    elif not (positions["null"] < positions["pin"] < positions["inventory"] < positions["loop"]):
        violations.append("UNSAFE_GUARD_ORDER")
    else:
        if "return 2;" not in s[positions["null"]:positions["pin"]]:
            violations.append("NULL_ROUTER_NOT_REJECTED")
        if "return 3;" not in s[positions["pin"]:positions["inventory"]]:
            violations.append("PIN_LOCK_NOT_REJECTED")

    if any(positions[x] < 0 for x in ("breadcrumb", "navigate", "wait", "failure", "settle")):
        violations.append("MISSING_CONSTRUCTION_BREADCRUMB_OR_RESULT_CHECK")
    elif not (positions["loop"] < positions["breadcrumb"] < positions["navigate"] <
              positions["wait"] < positions["failure"] < positions["settle"]):
        violations.append("UNSAFE_SCREEN_CONSTRUCTION_ORDER")

    if "kConstructDeadlineMs = 8000" not in text or "if (!router->screen_widget(id))" not in s:
        violations.append("MISSING_BOUNDED_CONSTRUCTION_VERDICT")

    tail = s[positions["terminal"]:] if positions["terminal"] >= 0 else ""
    if positions["terminal"] < 0 or "return 0;" not in tail or "return 1;" not in tail or (
        tail.find("return 0;") >= tail.find("return 1;")
    ):
        violations.append("MISSING_NONZERO_SCREEN_FAILURE_RETURN")

    if any(term in s for term in ("set_terminal_locked(false)", "clear_pin(", "unlock_terminal(")):
        violations.append("PIN_BYPASS_PRESENT_IN_SMOKE")

    # A zero-sized registry currently falls through the loop and returns 0.
    # This is a release-test gap, NOT grounds to mutate the original application.
    gaps = []
    if "if (ids.isEmpty())" not in s:
        gaps.append("EMPTY_REGISTRY_CAN_FALSE_PASS")
    gaps.append("NATIVE_QT_GUI_AND_SHOWEVENT_SIDE_EFFECTS_NOT_TESTED")

    return {
        "schema": SCHEMA,
        "source_kind": "STATIC_SOURCE_ONLY_NOT_RUNTIME_PROOF",
        "source_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "safety_guard_status": "PASS_SOURCE_CHECKS" if not violations else "FAIL_SOURCE_CHECKS",
        "violations": violations,
        "runtime_gaps": gaps,
        "native_gui_compiled": False,
        "runtime_gui_pass": False,
        "broker_authority": False,
        "release_ready": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only original Qt smoke harness audit")
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        file = args.source_root / RELATIVE_SOURCE
        if file.is_symlink() or not file.is_file():
            raise ValueError("MISSING_OR_SYMLINK_SOURCE")
        result = analyze(file.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "NOT_VERIFIED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

