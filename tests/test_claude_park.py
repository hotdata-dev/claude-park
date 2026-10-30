import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "bin" / "claude-park"
cp = SourceFileLoader("claude_park", str(SCRIPT)).load_module()

FAKE_CLAUDE = """#!/bin/sh
log="$FAKE_CLAUDE_LOG"
if [ "$1" = "-p" ]; then
  echo call >> "$log.calls"
  printf '%s\\n' "$@" > "$log.args"
  cat > "$log.stdin"
  if [ -n "$FAKE_CLAUDE_FAIL" ]; then echo "boom" >&2; exit 3; fi
  printf '**Goal** — ship the widget\\n**Done**\\n- parser\\n'
  exit 0
fi
pwd -P > "$log.cwd"
printf '%s\\n' "$@" > "$log.args"
"""


def entry(kind, content, **extra):
    e = {"type": kind, "message": {"role": kind, "content": content},
         "cwd": extra.pop("cwd", None), "gitBranch": "feature", "version": "2.1.314"}
    e.update(extra)
    return e


class Env:
    """An isolated Claude config dir, git repo with a linked worktree, and fake claude."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.config = base / "claude"
        self.repo = base / "repo"
        self.worktree = base / "wt"
        self.fake_log = base / "fake"
        self.fake_claude = base / "fake-claude"
        self.fake_claude.write_text(FAKE_CLAUDE)
        self.fake_claude.chmod(self.fake_claude.stat().st_mode | stat.S_IEXEC)

        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("CLAUDE", "ITERM", "GIT_"))}
        self.env.update({
            "CLAUDE_CONFIG_DIR": str(self.config),
            "CLAUDE_PARK_CLAUDE": str(self.fake_claude),
            "CLAUDE_PARK_NO_CLOSE": "1",
            "FAKE_CLAUDE_LOG": str(self.fake_log),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        })
        self.repo.mkdir()
        self.git(self.repo, "init", "-q", "-b", "main")
        (self.repo / ".gitignore").write_text("node_modules/\ntarget/\ncache/\n")
        (self.repo / "README").write_text("hi\n")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "init")
        self.git(self.repo, "worktree", "add", "-q", "-b", "feature", str(self.worktree))

    def git(self, cwd, *args):
        return subprocess.run(["git", "-C", str(cwd), *args], env=self.env,
                              check=True, capture_output=True, text=True).stdout

    def transcript(self, session_id, cwd, entries=None):
        project = self.config / "projects" / "proj"
        project.mkdir(parents=True, exist_ok=True)
        entries = entries or [
            {"type": "ai-title", "aiTitle": "Build the widget"},
            entry("user", "please build the widget parser", cwd=str(cwd)),
            entry("assistant", [{"type": "text", "text": "Parser done, tests next."}], cwd=str(cwd)),
            {"type": "last-prompt", "lastPrompt": "now write the tests"},
        ]
        path = project / f"{session_id}.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        return path

    def run(self, *args, cwd=None, extra_env=None, prog="claude-park"):
        env = dict(self.env, **(extra_env or {}))
        return subprocess.run([sys.executable, str(ROOT / "bin" / prog), *args],
                              cwd=str(cwd or self.worktree), env=env,
                              capture_output=True, text=True)

    def record(self, session_id):
        path = self.config / "parked" / f"{session_id}.json"
        return json.loads(path.read_text())

    def wait_summary(self, session_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.record(session_id)
            if r["summary_status"] != "pending":
                return r
            time.sleep(0.1)
        self.fail_reason = "summary still pending"
        return self.record(session_id)

    def lock_reason(self):
        out = self.git(self.repo, "worktree", "list", "--porcelain")
        block = out.split(f"worktree {self.worktree.resolve()}")[-1].split("\n\n")[0]
        for line in block.splitlines():
            if line.startswith("locked"):
                return line[len("locked"):].strip()
        return None

    def cleanup(self):
        self.tmp.cleanup()


class TranscriptTests(unittest.TestCase):
    def test_extracts_prompts_and_skips_noise(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.jsonl"
            entries = [
                {"type": "ai-title", "aiTitle": "AI title"},
                {"type": "custom-title", "customTitle": "my-name"},
                entry("user", "<command-name>/clear</command-name>", cwd="/w"),
                entry("user", "fix the flaky test<system-reminder>ignore me</system-reminder>", cwd="/w"),
                entry("user", "meta stuff", isMeta=True),
                entry("user", "side quest", isSidechain=True),
                entry("user", [{"type": "tool_result", "content": "lots of output"}]),
                entry("assistant", [{"type": "thinking", "thinking": "hmm"},
                                    {"type": "text", "text": "Found the race."}]),
                entry("user", "summary of earlier work", isCompactSummary=True),
                "not json",
                {"type": "last-prompt", "lastPrompt": "ship it"},
            ]
            path.write_text("\n".join(e if isinstance(e, str) else json.dumps(e) for e in entries))
            info = cp.read_transcript(path)

        self.assertEqual(info["custom_title"], "my-name")
        self.assertEqual(info["ai_title"], "AI title")
        self.assertEqual(info["first_prompt"], "fix the flaky test")
        self.assertEqual(info["compact_summary"], "summary of earlier work")
        self.assertEqual(info["last_prompt"], "ship it")
        self.assertEqual(info["cwd"], "/w")
        self.assertEqual(info["turns"], [("user", "fix the flaky test"),
                                         ("assistant", "Found the race.")])

    def test_excerpt_keeps_opening_and_most_recent_turns_within_budget(self):
        info = {
            "first_prompt": "OPENING",
            "compact_summary": "COMPACT",
            "turns": [("user", f"turn-{i} " + "x" * 500) for i in range(100)],
        }
        excerpt = cp.build_excerpt(info, budget=5_000)
        self.assertLessEqual(len(excerpt), 5_200)
        self.assertIn("OPENING", excerpt)
        self.assertIn("COMPACT", excerpt)
        self.assertIn("turn-99", excerpt)
        self.assertNotIn("turn-0 ", excerpt)
        self.assertLess(excerpt.index("turn-98"), excerpt.index("turn-99"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.addCleanup(self.e.cleanup)

    def park(self, session_id, *args, cwd=None, extra_env=None):
        return self.e.run("park", "--no-pr", "--session", session_id, *args,
                          cwd=cwd, extra_env=extra_env)

    def append_turns(self, path, *texts):
        with open(path, "a") as f:
            for text in texts:
                f.write(json.dumps(entry("user", text, cwd=str(self.e.worktree))) + "\n")
                f.write(json.dumps(entry("assistant", [{"type": "text", "text": "ok: " + text}],
                                         cwd=str(self.e.worktree))) + "\n")

    def summary_calls(self):
        calls = Path(f"{self.e.fake_log}.calls")
        return len(calls.read_text().splitlines()) if calls.exists() else 0

    def park_and_resume(self, sid):
        self.assertEqual(self.park(sid).returncode, 0)
        self.assertEqual(self.e.wait_summary(sid)["summary_status"], "done")
        self.assertEqual(self.e.run("resume", sid).returncode, 0)

    def test_park_locks_worktree_and_generates_haiku_summary(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000001"
        self.e.transcript(sid, self.e.worktree)
        res = self.park(sid)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("parked: Build the widget", res.stdout)

        reason = self.e.lock_reason()
        self.assertIsNotNone(reason)
        self.assertTrue(reason.startswith("claude-park:"))
        self.assertIn(sid, reason)

        r = self.e.wait_summary(sid)
        self.assertEqual(r["summary_status"], "done", r.get("summary_error"))
        self.assertIn("ship the widget", r["summary"])
        self.assertTrue(r["locked_by_park"])
        self.assertEqual(r["git"]["branch"], "feature")
        self.assertTrue(r["git"]["linked_worktree"])

        args = Path(f"{self.e.fake_log}.args").read_text().split("\n")
        self.assertIn("haiku", args)
        self.assertIn("--no-session-persistence", args)
        prompt = Path(f"{self.e.fake_log}.stdin").read_text()
        self.assertIn("please build the widget parser", prompt)
        self.assertIn("Parser done, tests next.", prompt)

    def test_park_uses_session_id_from_environment(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000002"
        self.e.transcript(sid, self.e.worktree)
        res = self.e.run("--no-summary", "--no-pr", prog="park",
                         extra_env={"CLAUDE_CODE_SESSION_ID": sid})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.e.record(sid)["summary_status"], "skipped")

    def test_park_without_session_fails_clearly(self):
        res = self.e.run("park")
        self.assertEqual(res.returncode, 1)
        self.assertIn("no session id", res.stderr)

    def test_park_in_main_checkout_does_not_lock(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000003"
        self.e.transcript(sid, self.e.repo)
        res = self.park(sid, "--no-summary", cwd=self.e.repo)
        self.assertEqual(res.returncode, 0, res.stderr)
        r = self.e.record(sid)
        self.assertFalse(r["git"]["linked_worktree"])
        self.assertFalse(r["locked_by_park"])

    def test_existing_foreign_lock_is_left_alone(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000004"
        self.e.transcript(sid, self.e.worktree)
        self.e.git(self.e.repo, "worktree", "lock", "--reason", "someone else", str(self.e.worktree))
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        self.assertFalse(self.e.record(sid)["locked_by_park"])
        self.assertEqual(self.e.run("drop", sid).returncode, 0)
        self.assertEqual(self.e.lock_reason(), "someone else")

    def test_clean_removes_only_ignored_rebuildable_dirs(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000005"
        self.e.transcript(sid, self.e.worktree)
        wt = self.e.worktree
        (wt / "node_modules" / "pkg").mkdir(parents=True)
        (wt / "node_modules" / "pkg" / "index.js").write_text("x" * 2048)
        (wt / "crates" / "a" / "target" / "debug").mkdir(parents=True)
        (wt / "crates" / "a" / "target" / "debug" / "bin").write_text("y" * 100)
        (wt / "cache").mkdir()
        (wt / "cache" / "keep").write_text("ignored but not rebuildable")
        (wt / "build").mkdir()
        (wt / "build" / "keep").write_text("untracked, not ignored")

        res = self.park(sid, "--no-summary", "--clean")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse((wt / "node_modules").exists())
        self.assertFalse((wt / "crates" / "a" / "target").exists())
        self.assertTrue((wt / "cache" / "keep").exists())
        self.assertTrue((wt / "build" / "keep").exists())
        cleaned = {c["path"]: c["bytes"] for c in self.e.record(sid)["cleaned"]}
        self.assertEqual(cleaned, {"node_modules": 2048, "crates/a/target": 100})
        self.assertIn("freed", res.stdout)

    def test_summary_failure_is_recorded(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000006"
        self.e.transcript(sid, self.e.worktree)
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        res = self.e.run("summarize", sid, extra_env={"FAKE_CLAUDE_FAIL": "1"})
        self.assertEqual(res.returncode, 1)
        r = self.e.record(sid)
        self.assertEqual(r["summary_status"], "failed")
        self.assertIn("boom", r["summary_error"])
        self.assertIn("Summary failed", self.e.run("show", sid).stdout)

    def test_summary_file_is_used_verbatim(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000007"
        self.e.transcript(sid, self.e.worktree)
        env = dict(self.e.env)
        res = subprocess.run([sys.executable, str(SCRIPT), "park", "--no-pr", "--session", sid,
                              "--summary-file", "-"], input="**Goal** — from the model\n",
                             cwd=str(self.e.worktree), env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        r = self.e.record(sid)
        self.assertEqual((r["summary_status"], r["summary"]), ("done", "**Goal** — from the model"))
        self.assertFalse(Path(f"{self.e.fake_log}.stdin").exists())

    def test_resume_unlocks_archives_and_execs_claude_in_worktree(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000008"
        self.e.transcript(sid, self.e.worktree)
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        res = self.e.run("resume", sid[:8], cwd=self.e.repo, prog="parked")
        self.assertEqual(res.returncode, 0, res.stderr)

        self.assertEqual(Path(f"{self.e.fake_log}.cwd").read_text().strip(),
                         str(self.e.worktree.resolve()))
        self.assertEqual(Path(f"{self.e.fake_log}.args").read_text().split(),
                         ["--resume", sid])
        self.assertIsNone(self.e.lock_reason())
        self.assertFalse((self.e.config / "parked" / f"{sid}.json").exists())
        self.assertTrue((self.e.config / "parked" / "archive" / f"{sid}.json").exists())

    def test_resume_fresh_seeds_new_session_with_card(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000009"
        self.e.transcript(sid, self.e.worktree)
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        res = self.e.run("resume", "--fresh", "widget")
        self.assertEqual(res.returncode, 0, res.stderr)
        args = Path(f"{self.e.fake_log}.args").read_text()
        self.assertNotIn("--resume", args)
        self.assertIn("# Build the widget", args)
        self.assertIn(sid, args)

    def test_resume_missing_worktree_keeps_session_parked(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000010"
        self.e.transcript(sid, self.e.worktree)
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        r = self.e.record(sid)
        r["cwd"] = "/nonexistent/worktree"
        (self.e.config / "parked" / f"{sid}.json").write_text(json.dumps(r))
        res = self.e.run("resume", sid, cwd=self.e.repo)
        self.assertEqual(res.returncode, 1)
        self.assertIn("no longer exists", res.stderr)
        self.assertTrue((self.e.config / "parked" / f"{sid}.json").exists())

    def test_repark_without_new_turns_reuses_card(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000011"
        path = self.e.transcript(sid, self.e.worktree)
        self.park_and_resume(sid)
        # Resuming appends metadata but no conversation turns.
        with open(path, "a") as f:
            f.write(json.dumps({"type": "last-prompt", "lastPrompt": "now write the tests"}) + "\n")
            f.write(json.dumps(entry("user", "<command-name>/clear</command-name>")) + "\n")

        res = self.park(sid)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("reusing previous card", res.stdout)
        r = self.e.record(sid)
        self.assertEqual(r["summary_status"], "done")
        self.assertIn("ship the widget", r["summary"])
        self.assertEqual(self.summary_calls(), 1)

    def test_repark_with_new_turns_updates_card_from_new_turns_only(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000012"
        path = self.e.transcript(sid, self.e.worktree)
        self.park_and_resume(sid)
        self.append_turns(path, "add the CSV exporter")

        self.assertEqual(self.park(sid).returncode, 0)
        r = self.e.wait_summary(sid)
        self.assertEqual(r["summary_status"], "done", r.get("summary_error"))
        self.assertEqual(self.summary_calls(), 2)
        prompt = Path(f"{self.e.fake_log}.stdin").read_text()
        self.assertIn("<previous_card>", prompt)
        self.assertIn("ship the widget", prompt)
        self.assertIn("add the CSV exporter", prompt)
        self.assertNotIn("please build the widget parser", prompt)
        self.assertEqual(r["turn_count"], 4)
        self.assertNotIn("summary_base", r)

    def test_failed_update_keeps_stale_card_and_next_park_retries(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000013"
        path = self.e.transcript(sid, self.e.worktree)
        self.park_and_resume(sid)
        self.append_turns(path, "add the CSV exporter")

        self.assertEqual(self.park(sid, extra_env={"FAKE_CLAUDE_FAIL": "1"}).returncode, 0)
        r = self.e.wait_summary(sid)
        self.assertEqual(r["summary_status"], "stale")
        self.assertIn("ship the widget", r["summary"])
        self.assertIn("predates the latest turns", self.e.run("show", sid).stdout)

        # Re-parking must retry the update, not treat the stale card as current.
        res = self.park(sid)
        self.assertNotIn("reusing", res.stdout)
        r = self.e.wait_summary(sid)
        self.assertEqual(r["summary_status"], "done", r.get("summary_error"))
        self.assertIn("add the CSV exporter", Path(f"{self.e.fake_log}.stdin").read_text())

    def unrecognized_transcript(self, sid):
        # Plausible future format: message entries renamed and restructured.
        return self.e.transcript(sid, self.e.worktree, [
            {"type": "ai-title", "aiTitle": "Build the widget"},
            {"type": "human", "version": "9.0.0", "cwd": str(self.e.worktree),
             "payload": {"parts": [{"text": "please build the widget parser"}]}},
            {"type": "model", "version": "9.0.0", "cwd": str(self.e.worktree),
             "payload": {"parts": [{"text": "Parser done."}]}},
        ])

    def test_unrecognized_transcript_fails_loudly_without_calling_model(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000014"
        self.unrecognized_transcript(sid)
        res = self.park(sid)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("transcript format not recognized", res.stderr)
        r = self.e.record(sid)
        self.assertEqual(r["summary_status"], "failed")
        self.assertIn("not recognized", r["summary_error"])
        self.assertIn("9.0.0", r["summary_error"])
        self.assertEqual(self.summary_calls(), 0)
        self.assertEqual(self.e.run("summarize", sid).returncode, 1)
        self.assertEqual(self.summary_calls(), 0)

    def test_unrecognized_transcript_does_not_reuse_previous_card(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000015"
        self.e.transcript(sid, self.e.worktree)
        self.park_and_resume(sid)
        self.unrecognized_transcript(sid)
        self.park(sid)
        r = self.e.record(sid)
        self.assertEqual(r["summary_status"], "failed")

    def test_card_records_claude_code_version(self):
        sid = "11111111-aaaa-bbbb-cccc-000000000016"
        self.e.transcript(sid, self.e.worktree)
        self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        self.assertEqual(self.e.record(sid)["claude_version"], "2.1.314")
        self.assertIn("Claude Code 2.1.314", self.e.run("show", sid).stdout)

    def test_doctor_reports_recognized_fields(self):
        self.e.transcript("11111111-aaaa-bbbb-cccc-000000000017", self.e.worktree)
        res = self.e.run("doctor")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("11111111-aaaa-bbbb-cccc-000000000017", res.stdout)
        self.assertRegex(res.stdout, r"ok\s+turns\s+2")
        self.assertRegex(res.stdout, r"ok\s+title\s+Build the widget")
        self.assertRegex(res.stdout, r"--\s+compaction summary")

    def test_doctor_fails_on_unrecognized_format(self):
        self.unrecognized_transcript("11111111-aaaa-bbbb-cccc-000000000018")
        res = self.e.run("doctor")
        self.assertEqual(res.returncode, 1)
        self.assertRegex(res.stdout, r"FAIL\s+turns\s+0")
        self.assertIn("not recognized", res.stdout)

    def test_list_and_ambiguous_lookup(self):
        for n, title in (("11", "Widget parser"), ("12", "Widget docs")):
            sid = f"{n}111111-aaaa-bbbb-cccc-000000000000"
            self.e.transcript(sid, self.e.worktree, [
                {"type": "custom-title", "customTitle": title},
                entry("user", "do it", cwd=str(self.e.worktree)),
            ])
            self.assertEqual(self.park(sid, "--no-summary").returncode, 0)
        out = self.e.run("list").stdout
        self.assertIn("Widget parser", out)
        self.assertIn("repo:feature", out)
        res = self.e.run("show", "widget")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ambiguous", res.stderr)
        self.assertIn("# Widget docs", self.e.run("show", "docs").stdout)


if __name__ == "__main__":
    unittest.main()
