"""Semantic document diffing keyed by stable layer IDs."""

from __future__ import annotations

from typing import Any


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(_flatten(value[key], child_prefix))
        return result
    if isinstance(value, list):
        # Layers are identity-bearing collections. This prevents reordering from
        # making every field look changed and makes AI review much clearer.
        if prefix == "layers" or prefix.endswith(".layers"):
            result = {}
            for layer in value:
                if isinstance(layer, dict) and isinstance(layer.get("id"), str):
                    result.update(_flatten(layer, f"{prefix}.{layer['id']}"))
                else:
                    result.update(_flatten(layer, f"{prefix}[{len(result)}]"))
            return result
        return {prefix: value}
    return {prefix: value}


def semantic_diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    before = _flatten(old)
    after = _flatten(new)
    changes: list[dict[str, Any]] = []
    for path in sorted(set(before) | set(after)):
        if path not in before:
            changes.append({"path": path, "kind": "added", "old": None, "new": after[path]})
        elif path not in after:
            changes.append({"path": path, "kind": "removed", "old": before[path], "new": None})
        elif before[path] != after[path]:
            changes.append({"path": path, "kind": "changed", "old": before[path], "new": after[path]})
    return changes


def format_change(change: dict[str, Any]) -> str:
    path = change["path"]
    kind = change["kind"]
    if kind == "added":
        return f"{path}: <missing> -> {change['new']!r}"
    if kind == "removed":
        return f"{path}: {change['old']!r} -> <missing>"
    return f"{path}: {change['old']!r} -> {change['new']!r}"
