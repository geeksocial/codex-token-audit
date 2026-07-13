#!/usr/bin/env python3
"""Measure Codex context surfaces without reading skill bodies."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback
    tomllib = None


BROAD_TRIGGER = re.compile(
    r"\b(any|every|all)\s+(coding\s+)?(task|conversation|response|feature|bugfix)\b"
    r"|\balways\s+(use|active|invoke|run)\b"
    r"|\bstarting\s+(any|every)\b",
    re.IGNORECASE,
)


def estimate_tokens(text: str) -> int:
    ascii_chars = sum(ord(char) < 128 for char in text)
    return math.ceil(ascii_chars / 4 + len(text) - ascii_chars)


def read_text(path: Path, limit: int | None = None) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read() if limit is None else handle.read(limit)


def frontmatter(path: Path) -> tuple[str, str]:
    text = read_text(path, 32768).replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return "", ""
    end = text.find("\n---", 4)
    if end < 0:
        return "", ""
    lines = text[4:end].splitlines()
    name = ""
    description = ""
    for index, line in enumerate(lines):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip().strip('"\'')
        if key == "name":
            name = value
        elif value in {">", "|", ">-", "|-"}:
            parts = []
            for following in lines[index + 1 :]:
                if following and not following[0].isspace():
                    break
                parts.append(following.strip())
            description = " ".join(part for part in parts if part)
        else:
            description = value
    return name, description


def scan_skills(codex_home: Path) -> list[dict[str, object]]:
    roots = [
        (codex_home / "skills", "local"),
        (codex_home / "plugins" / "cache", "plugin-cache"),
    ]
    rows = []
    seen = set()
    for root, source in roots:
        if not root.exists():
            continue
        for path in root.rglob("SKILL.md"):
            resolved = str(path.resolve()).casefold()
            if resolved in seen:
                continue
            seen.add(resolved)
            name, description = frontmatter(path)
            openai_yaml = path.parent / "agents" / "openai.yaml"
            advertised = True
            if openai_yaml.exists():
                advertised = not re.search(
                    r"(?m)^\s*allow_implicit_invocation:\s*false\s*$",
                    read_text(openai_yaml, 8192),
                    re.IGNORECASE,
                )
            actual_source = source
            if source == "local" and ".system" in path.relative_to(root).parts:
                actual_source = "system"
            plugin_id = ""
            if source == "plugin-cache":
                parts = path.relative_to(root).parts
                if len(parts) >= 2:
                    plugin_id = f"{parts[1]}@{parts[0]}"
            rows.append(
                {
                    "name": name or path.parent.name,
                    "description": description,
                    "source": actual_source,
                    "plugin_id": plugin_id,
                    "path": str(path),
                    "metadata_tokens": estimate_tokens(f"{name} {description}"),
                    "advertised": advertised,
                }
            )
    return rows


def load_plugins(config_path: Path) -> dict[str, bool]:
    if not config_path.exists() or tomllib is None:
        return {}
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    return {
        plugin_id: bool(settings.get("enabled"))
        for plugin_id, settings in config.get("plugins", {}).items()
    }


def measure_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False, "bytes": 0, "tokens": 0}
    text = read_text(path)
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "tokens": estimate_tokens(text),
    }


def audit(
    codex_home: Path,
    project: Path,
    ignored_skills: set[str] | None = None,
) -> dict[str, object]:
    skills = scan_skills(codex_home)
    plugins = load_plugins(codex_home / "config.toml")
    ignored_skills = ignored_skills or set()
    active_skills = [
        row
        for row in skills
        if row["advertised"]
        and (row["source"] != "plugin-cache" or plugins.get(str(row["plugin_id"])) is True)
    ]
    review_skills = [row for row in active_skills if row["name"] not in ignored_skills]
    names = Counter(row["name"] for row in review_skills if row["name"])
    duplicates = sorted(name for name, count in names.items() if count > 1)
    broad = sorted(
        row["name"] for row in review_skills if BROAD_TRIGGER.search(str(row["description"]))
    )
    long_descriptions = sorted(
        row["name"] for row in review_skills if len(str(row["description"])) > 400
    )
    disabled_cache = [
        row for row in skills if row["plugin_id"] and plugins.get(str(row["plugin_id"])) is False
    ]
    unconfigured_cache = [
        row
        for row in skills
        if row["plugin_id"] and str(row["plugin_id"]) not in plugins
    ]
    source_counts = Counter(str(row["source"]) for row in active_skills)
    global_agents = measure_file(codex_home / "AGENTS.md")
    project_agents = measure_file(project / "AGENTS.md")
    metadata_tokens = sum(int(row["metadata_tokens"]) for row in active_skills)
    top_metadata = [
        {
            "name": row["name"],
            "source": row["source"],
            "tokens": row["metadata_tokens"],
        }
        for row in sorted(
            review_skills,
            key=lambda row: int(row["metadata_tokens"]),
            reverse=True,
        )[:5]
    ]

    findings = []
    recommendations = []
    if int(global_agents["tokens"]) > 1000:
        findings.append("HIGH: global AGENTS.md exceeds ~1,000 tokens")
        recommendations.append(
            f"Compress global AGENTS.md; estimated saving: ~{int(global_agents['tokens']) - 500}+ tokens"
        )
    if metadata_tokens > 3000 or len(active_skills) > 50:
        findings.append("HIGH: skill discovery metadata is large")
    elif metadata_tokens > 1500 or len(active_skills) > 25:
        findings.append("MEDIUM: review skill count and descriptions")
    if duplicates:
        findings.append(f"MEDIUM: {len(duplicates)} duplicate skill names")
        recommendations.append(f"Remove or rename duplicates: {', '.join(duplicates[:5])}")
    if broad:
        findings.append(f"MEDIUM: {len(broad)} broad auto-trigger descriptions")
        recommendations.append(
            "Make broad skills explicit-only: " + ", ".join(broad[:5])
        )
    if disabled_cache:
        findings.append(f"LOW: {len(disabled_cache)} disabled-plugin skill files remain cached")
    if sum(plugins.values()) > 8:
        findings.append("MEDIUM: more than 8 plugins are enabled")
        recommendations.append("Disable plugins not used by current projects")
    if metadata_tokens > 1500:
        names = ", ".join(str(item["name"]) for item in top_metadata)
        recommendations.append(f"Review largest skill metadata: {names}")

    return {
        "codex_home": str(codex_home),
        "project": str(project),
        "persistent_files": [global_agents, project_agents],
        "skills": {
            "total": len(active_skills),
            "physical_files": len(skills),
            "explicit_only": sum(not bool(row["advertised"]) for row in skills),
            "by_source": dict(sorted(source_counts.items())),
            "metadata_tokens": metadata_tokens,
            "duplicates": duplicates,
            "broad_triggers": broad,
            "long_descriptions": long_descriptions,
            "top_metadata": top_metadata,
        },
        "plugins": {
            "enabled": sorted(key for key, value in plugins.items() if value),
            "disabled": sorted(key for key, value in plugins.items() if not value),
            "disabled_cache_skill_files": len(disabled_cache),
            "unconfigured_cache_skill_files": len(unconfigured_cache),
        },
        "findings": findings,
        "recommendations": recommendations[:3],
    }


def snapshot(result: dict[str, object]) -> dict[str, int]:
    persistent = result["persistent_files"]
    return {
        "agents_tokens": sum(int(item["tokens"]) for item in persistent if item["exists"]),
        "active_skills": int(result["skills"]["total"]),
        "skill_metadata_tokens": int(result["skills"]["metadata_tokens"]),
        "enabled_plugins": len(result["plugins"]["enabled"]),
    }


def compare_snapshot(result: dict[str, object], baseline_path: Path) -> dict[str, int]:
    baseline = json.loads(read_text(baseline_path))
    current = snapshot(result)
    return {key: current[key] - int(baseline.get(key, 0)) for key in current}


def redact_paths(result: dict[str, object]) -> dict[str, object]:
    redacted = copy.deepcopy(result)
    redacted["codex_home"] = "<CODEX_HOME>"
    redacted["project"] = "<PROJECT>"
    for index, item in enumerate(redacted["persistent_files"]):
        item["path"] = "<GLOBAL_AGENTS>" if index == 0 else "<PROJECT_AGENTS>"
    return redacted


def print_text(result: dict[str, object]) -> None:
    skills = result["skills"]
    plugins = result["plugins"]
    print("Codex token audit")
    for item in result["persistent_files"]:
        if item["exists"]:
            print(f"- {item['path']}: ~{item['tokens']} tokens")
    print(
        f"- skills: {skills['total']} active of {skills['physical_files']} physical files, "
        f"~{skills['metadata_tokens']} metadata tokens, "
        f"sources={skills['by_source']}"
    )
    print(f"- plugins: {len(plugins['enabled'])} enabled, {len(plugins['disabled'])} disabled")
    top = skills["top_metadata"]
    if top:
        print("- largest metadata: " + ", ".join(f"{item['name']} (~{item['tokens']})" for item in top))
    if result["findings"]:
        print("Findings:")
        for finding in result["findings"]:
            print(f"- {finding}")
    else:
        print("Findings: none above thresholds")
    if result["recommendations"]:
        print("Recommended:")
        for recommendation in result["recommendations"]:
            print(f"- {recommendation}")
    if "comparison" in result:
        print("Change vs baseline: " + ", ".join(f"{key}={value:+d}" for key, value in result["comparison"].items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--redact-paths", action="store_true")
    parser.add_argument("--save-baseline", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--ignore-skill", action="append", default=[])
    args = parser.parse_args()
    result = audit(
        args.codex_home.resolve(),
        args.project.resolve(),
        set(args.ignore_skill),
    )
    if args.compare:
        result["comparison"] = compare_snapshot(result, args.compare)
    if args.save_baseline:
        args.save_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.save_baseline.write_text(
            json.dumps(snapshot(result), indent=2) + "\n",
            encoding="utf-8",
        )
    if args.redact_paths:
        result = redact_paths(result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_text(result)


if __name__ == "__main__":
    main()
