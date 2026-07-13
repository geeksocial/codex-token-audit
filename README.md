# Codex Token Audit

Read-only audit for persistent Codex context overhead.

[中文说明](README.zh-CN.md)

## What it checks

- Global and project `AGENTS.md` size
- Active Skill metadata
- Duplicate and broad-trigger Skills
- Enabled and disabled plugins
- Physical cache versus active configuration

## Install

Ask Codex Skill Installer to install:

```text
https://github.com/geeksocial/codex-token-audit/tree/main/skills/codex-token-audit
```

Then restart Codex.

## Use

```text
$codex-token-audit
```

The audit reports at most three high-value fixes. Nothing changes until the user approves the exact scope. After approval, Codex backs up touched files, applies only approved changes, and reruns the audit.

Periodic comparison:

```bash
python scripts/audit.py --save-baseline token-baseline.json
python scripts/audit.py --compare token-baseline.json
```

Use `--redact-paths` before sharing output.
Use `--ignore-skill <name>` for an accepted exception that should still count toward totals but not appear in recommendations.

## Safety

- Installation does not modify `AGENTS.md` or Codex configuration.
- Default audit is read-only.
- No hooks, post-install scripts, telemetry, network calls, or automatic cleanup.
- Token counts are static estimates, not billing totals.

## Requirements

Python 3.11 or later. Standard library only.

## License

MIT
