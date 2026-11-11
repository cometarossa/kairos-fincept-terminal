"""Fincept-first additive regression guard: protects existing source-level UI surface.

No Qt imports, no app launch, no network, no broker, no mutation. The pinned
baseline is a machine-readable snapshot of *main*, not runtime proof. Additions
are permitted, edits/removals of original factories/widgets/templates fail.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

DEFAULT_BASELINE = Path(__file__).with_name("fincept_source_baseline_v1.json")
FILES = {
    "routes": "fincept-qt/src/app/WindowFrame_Setup.cpp",
    "widgets": "fincept-qt/src/screens/dashboard/canvas/WidgetRegistry.cpp",
    "templates": "fincept-qt/src/screens/dashboard/canvas/DashboardTemplates.cpp",
}
ROUTE = re.compile(r'dock_router_->register_factory\(\s*"([a-z0-9_]+)"')
WIDGET = re.compile(r'register_widget\(\s*\{\s*"([a-z0-9_]+)"')
TEMPLATE = re.compile(r'^ {8}\{"([a-z0-9_]+)",\s*$', re.M)
REF = re.compile(r'\bgi\("([a-z0-9_]+)"')
END_WIDGET = re.compile(r'\}\s*\);')
END_TEMPLATE = re.compile(r'^ {9}\}\},\s*$', re.M)
FACTORY_TARGET = re.compile(r'\bnew\s+([A-Za-z_][\w:]*)\b')


class BaselineError(ValueError):
    pass


def _text(root: Path, key: str) -> str:
    path = root / FILES[key]
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def _unique_map(matches, name):
    obj = {}
    for key, value in matches:
        if key in obj:
            raise BaselineError("DUPLICATE_" + name + ":" + key)
        obj[key] = value
    return obj


def source_inventory(root: Path) -> dict:
    """Snapshot only original factory signatures and template/widget definitions."""
    routes_text = _text(root, "routes")
    widgets_text = _text(root, "widgets")
    templates_text = _text(root, "templates")
    route_matches = list(ROUTE.finditer(routes_text))
    widget_matches = list(WIDGET.finditer(widgets_text))
    template_matches = list(TEMPLATE.finditer(templates_text))
    if not route_matches or not widget_matches or not template_matches:
        raise BaselineError("INCOMPLETE_SOURCE_INVENTORY")

    routes = []
    for i, hit in enumerate(route_matches):
        # All existing factories construct an explicit QWidget; one may contain
        # multiple nested lambda bodies (file_manager), but the first new is
        # the original routed screen.
        end = route_matches[i + 1].start() if i + 1 < len(route_matches) else len(routes_text)
        body = routes_text[hit.start():end]
        target = FACTORY_TARGET.search(body)
        if target is None:
            raise BaselineError("NO_FACTORY_TARGET:" + hit.group(1))
        routes.append((hit.group(1), target.group(1)))

    widgets = []
    for hit in widget_matches:
        end = END_WIDGET.search(widgets_text, hit.end())
        if end is None:
            raise BaselineError("UNCLOSED_WIDGET:" + hit.group(1))
        snippet = widgets_text[hit.start():end.end()]
        widgets.append((hit.group(1), sha256(snippet.encode()).hexdigest()))

    templates = []
    template_widgets = {}
    for hit in template_matches:
        end = END_TEMPLATE.search(templates_text, hit.end())
        if end is None:
            raise BaselineError("UNCLOSED_TEMPLATE:" + hit.group(1))
        snippet = templates_text[hit.start():end.end()]
        template_id = hit.group(1)
        templates.append((template_id, sha256(snippet.encode()).hexdigest()))
        template_widgets[template_id] = REF.findall(snippet)

    return {
        "schema": "fincept_original_functional_source_baseline_v1",
        "source_kind": "STATIC_SOURCE_ONLY_NOT_RUNTIME_PROOF",
        "routes": _unique_map(routes, "ROUTE"),
        "route_order": [x[0] for x in routes],
        "widgets": _unique_map(widgets, "WIDGET"),
        "widget_order": [x[0] for x in widgets],
        "templates": _unique_map(templates, "TEMPLATE"),
        "template_order": [x[0] for x in templates],
        "template_widgets": template_widgets,
    }


def _subsequence(items, expected) -> bool:
    it = iter(items)
    return all(any(x == v for x in it) for v in expected)


def compare_to_baseline(now: dict, baseline: dict) -> list[str]:
    """Return precise regression findings. Added routes, widgets and presets OK."""
    if baseline.get("schema") != "fincept_original_functional_source_baseline_v1":
        raise BaselineError("UNKNOWN_BASELINE_SCHEMA")
    # A truncated baseline must never silently redefine "original".
    # Source integrity is not evidence of working GUI functionality.
    expected_counts = {"routes": 52, "widgets": 35, "templates": 6}
    for name, count in expected_counts.items():
        keys = baseline.get(name)
        order_name = {"routes": "route_order", "widgets": "widget_order", "templates": "template_order"}[name]
        order = baseline.get(order_name)
        if not isinstance(keys, dict) or len(keys) != count:
            raise BaselineError("INVALID_BASELINE_COUNT:" + name)
        if not isinstance(order, list) or len(order) != count or set(order) != set(keys):
            raise BaselineError("INVALID_BASELINE_ORDER:" + name)
    if baseline.get("source_kind") != "STATIC_SOURCE_ONLY_NOT_RUNTIME_PROOF":
        raise BaselineError("INVALID_BASELINE_SOURCE_KIND")
    errors: list[str] = []
    for name in ("routes", "widgets", "templates"):
        for key, expected in baseline[name].items():
            if key not in now[name]:
                errors.append("REMOVED_" + name.upper() + ":" + key)
            elif now[name][key] != expected:
                errors.append("CHANGED_" + name.upper() + ":" + key)
    for name in ("route_order", "widget_order", "template_order"):
        if not _subsequence(now[name], baseline[name]):
            errors.append("REORDERED_" + name.upper())
    for template_id, refs in now["template_widgets"].items():
        for key in refs:
            if key not in now["widgets"]:
                errors.append("UNKNOWN_TEMPLATE_WIDGET:" + template_id + ":" + key)
    # Built-in template geometry and widget composition are protected by
    # exact per-definition hashes; a new preset can be added opt-in.
    return errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Static Fincept original function preservation guard")
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    p.add_argument("--emit", action="store_true",
                   help="Emit baseline JSON for one PINNED original source only; do NOT use on hybrid candidate")
    args = p.parse_args(argv)
    try:
        result = source_inventory(args.source_root)
        if args.emit:
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        errors = compare_to_baseline(result, baseline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("FINCEPT_BASELINE_NOT_VERIFIED:" + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "source_kind": "STATIC_SOURCE_ONLY_NOT_RUNTIME_PROOF",
        "route_count": len(result["routes"]),
        "widget_count": len(result["widgets"]),
        "preset_count": len(result["templates"]),
        "status": "PASS_STATIC_INVARIANTS" if not errors else "FAIL_REGRESSION",
        "errors": errors,
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
