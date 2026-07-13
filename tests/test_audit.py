import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "codex-token-audit"
SCRIPT = SKILL_ROOT / "scripts" / "audit.py"
SPEC = importlib.util.spec_from_file_location("audit", SCRIPT)
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def write_skill(root: Path, name: str, description: str, explicit=False):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n",
        encoding="utf-8",
    )
    if explicit:
        agents = folder / "agents"
        agents.mkdir()
        (agents / "openai.yaml").write_text(
            "policy:\n  allow_implicit_invocation: false\n",
            encoding="utf-8",
        )


class AuditTests(unittest.TestCase):
    def test_active_scope_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / ".codex"
            project = Path(temp) / "project"
            project.mkdir(parents=True)
            agents = home / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            agents.write_text("- Keep changes small.\n", encoding="utf-8")
            write_skill(home / "skills", "broad", "Use on every coding task.")
            write_skill(home / "skills", "manual", "Manual audit.", explicit=True)
            plugin = home / "plugins" / "cache" / "market" / "active" / "1" / "skills"
            write_skill(plugin, "plugin-skill", "Active plugin skill.")
            disabled = home / "plugins" / "cache" / "market" / "off" / "1" / "skills"
            write_skill(disabled, "off-skill", "Disabled plugin skill.")
            (home / "config.toml").write_text(
                '[plugins."active@market"]\nenabled = true\n'
                '[plugins."off@market"]\nenabled = false\n',
                encoding="utf-8",
            )
            before = hashlib.sha256(agents.read_bytes()).hexdigest()
            config_before = hashlib.sha256((home / "config.toml").read_bytes()).hexdigest()
            result = audit_module.audit(home, project)
            after = hashlib.sha256(agents.read_bytes()).hexdigest()
            config_after = hashlib.sha256((home / "config.toml").read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(config_before, config_after)
            self.assertEqual(result["skills"]["total"], 2)
            self.assertEqual(result["skills"]["explicit_only"], 1)
            self.assertEqual(result["skills"]["broad_triggers"], ["broad"])
            self.assertEqual(result["plugins"]["disabled_cache_skill_files"], 1)
            ignored = audit_module.audit(home, project, {"broad"})
            self.assertEqual(ignored["skills"]["broad_triggers"], [])
            self.assertEqual(ignored["skills"]["total"], 2)

    def test_frontmatter_multiline_and_link_deduplication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skill"
            skill.mkdir()
            path = skill / "SKILL.md"
            path.write_text(
                "---\nname: sample\ndescription: >\n  First line.\n  Second line.\n---\nbody\n",
                encoding="utf-8",
            )
            self.assertEqual(
                audit_module.frontmatter(path),
                ("sample", "First line. Second line."),
            )

    def test_baseline_and_redaction(self):
        result = {
            "codex_home": "C:/Users/name/.codex",
            "project": "C:/secret/project",
            "persistent_files": [
                {"path": "global", "exists": True, "tokens": 100},
                {"path": "project", "exists": True, "tokens": 50},
            ],
            "skills": {"total": 3, "metadata_tokens": 200},
            "plugins": {"enabled": ["one"]},
        }
        snapshot = audit_module.snapshot(result)
        self.assertEqual(snapshot["agents_tokens"], 150)
        redacted = audit_module.redact_paths(result)
        self.assertEqual(redacted["codex_home"], "<CODEX_HOME>")
        self.assertNotIn("secret", json.dumps(redacted))

    def test_package_has_no_automatic_mutation_surfaces(self):
        self.assertFalse((SKILL_ROOT / "AGENTS.md").exists())
        self.assertFalse((SKILL_ROOT / "hooks").exists())
        self.assertFalse((SKILL_ROOT / ".codex-plugin").exists())
        source = SCRIPT.read_text(encoding="utf-8")
        for token in ("unlink(", "rmtree(", "os.remove("):
            self.assertNotIn(token, source)
        yaml = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("allow_implicit_invocation: false", yaml)


if __name__ == "__main__":
    unittest.main()
