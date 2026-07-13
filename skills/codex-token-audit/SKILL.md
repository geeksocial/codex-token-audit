---
name: codex-token-audit
description: Audit Codex context and token overhead. Use only when the user explicitly invokes $codex-token-audit.
---

# Codex Token Audit

1. Run `python scripts/audit.py --project <workspace>`; pass `--ignore-skill <name>` for accepted exceptions.
2. Report totals, exact offenders, and at most three high-value fixes. Token counts are estimates.
3. Ask once before changing anything. Installation and audit must never edit `AGENTS.md` or configuration.
4. After approval, back up each touched file, apply only the listed changes, then rerun the audit.
5. Never replace an existing `AGENTS.md` wholesale unless the approved diff explicitly does so.
6. For periodic checks, use `--save-baseline <file>` once and `--compare <file>` later.
