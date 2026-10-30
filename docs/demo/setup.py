#!/usr/bin/env python3
"""Build an isolated, fictional fixture for the README demo recording.

Everything lives under DEMO_ROOT (default /tmp/claude-park-demo): a fake
HOME, a Claude config dir, throwaway git repos and worktrees, and stand-ins
for `claude` and `gh`. Nothing reads or writes the real ~/.claude, and no
real Claude process or iTerm2 tab is touched.

    python3 docs/demo/setup.py [DEMO_ROOT]

Writes DEMO_ROOT/env.sh, which the tape sources before recording.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLAUDE_PARK = REPO / "bin" / "claude-park"
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-park-demo").resolve()
if not ROOT.name.startswith("claude-park-demo"):
    sys.exit(f"refusing to use {ROOT}: the directory name must start with claude-park-demo")

HOME = ROOT / "home"
CONFIG = ROOT / "claude"
BIN = ROOT / "bin"
CANNED = ROOT / "canned"
VERSION = "2.1.40"
LIVE_SID = "5b0d2c71-94e8-4f3a-b6c2-8e1f0a7d3c55"

# A clean environment: nothing from the caller's Claude Code or iTerm2 session.
ENV = {
    "HOME": str(HOME),
    "PATH": f"{BIN}:{REPO / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "en_US.UTF-8",
    "TERM": os.environ.get("TERM", "xterm-256color"),
    "CLAUDE_CONFIG_DIR": str(CONFIG),
    "CLAUDE_PARK_DIR": str(CONFIG / "parked"),
    "CLAUDE_PARK_CLAUDE": str(BIN / "claude"),
    "CLAUDE_PARK_NO_CLOSE": "1",
    "DEMO_CANNED": str(CANNED),
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Demo Dev", "GIT_AUTHOR_EMAIL": "dev@example.com",
    "GIT_COMMITTER_NAME": "Demo Dev", "GIT_COMMITTER_EMAIL": "dev@example.com",
}

FAKE_CLAUDE = r'''#!/usr/bin/env python3
"""Stand-in for the claude CLI. Prints canned output; never calls a model."""
import json, os, re, sys
from pathlib import Path
canned = Path(os.environ["DEMO_CANNED"])
args = sys.argv[1:]
if args[:1] == ["-p"]:
    prompt = sys.stdin.read()
    if "<park_card>" in prompt:
        branch = re.search(r"^branch: (\S+)", prompt, re.M).group(1)
        print((canned / "briefs" / f"{branch}.json").read_text())
    else:
        print((canned / "summary.md").read_text())
    sys.exit(0)
if "--resume" in args:
    sid = args[args.index("--resume") + 1]
    rec = json.loads((Path(os.environ["CLAUDE_PARK_DIR"]) / "archive" / f"{sid}.json").read_text())
    title = (rec.get("brief") or {}).get("title") or rec["title"]
    print(f"\n\x1b[2m[demo stand-in for claude]\x1b[0m claude --resume {sid[:8]}…")
    print(f"  cwd      {os.getcwd()}")
    print(f"  session  {title}")
    print(f"  history  {rec['turn_count']} turns\n")
else:
    print("\n\x1b[2m[demo stand-in for claude]\x1b[0m new session seeded with the park card\n")
'''

FAKE_GH = r'''#!/usr/bin/env python3
"""Stand-in for gh: answers `gh pr view` from canned data, offline."""
import os, subprocess, sys
from pathlib import Path
if sys.argv[1:3] != ["pr", "view"]:
    sys.exit("demo gh only supports `pr view`")
branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
pr = Path(os.environ["DEMO_CANNED"]) / "prs" / f"{branch}.json"
if not pr.exists():
    sys.exit(f'no pull requests found for branch "{branch}"')
print(pr.read_text())
'''


def card(goal, done, nxt, gotchas):
    def bullets(items):
        return "\n".join(f"- {i}" for i in items)
    return (f"**Goal** — {goal}\n\n**Done**\n{bullets(done)}\n\n"
            f"**Next**\n{bullets(nxt)}\n\n**Gotchas**\n{bullets(gotchas)}\n")


# Parked earlier. "days" is how long ago; the rest shapes the git state.
SESSIONS = [
    dict(
        sid="7c1e9a42-3b5d-4e8f-a1c6-2d9b7f04e613", repo="api-server", branch="rate-limit-search",
        days=3.2, ahead=4, dirty=0, build={"target": 1_310_000_000},
        pr=dict(number=482, state="OPEN", title="Add token-bucket rate limiting to /search"),
        ai_title="Add rate limiting to search endpoint",
        first="The public /search endpoint gets hammered by a few API keys. Add per-key rate limiting.",
        last="ok, reply to the review comments and push",
        brief=dict(title="Rate limiter for the public search API", phase="review",
                   status="Token-bucket limiter is up in PR #482; one reviewer wants per-key overrides before merge.",
                   next=["Add per-API-key limit overrides", "Answer the Redis failover question on the PR",
                         "Load test at 2x peak traffic"]),
        card=card("Rate-limit the public `/search` endpoint per API key so a few heavy callers can't starve everyone else.",
                  ["Token-bucket middleware in `src/middleware/rate_limit.rs`, backed by Redis `INCR` + `EXPIRE`",
                   "`429` responses carry `Retry-After`; covered by `tests/rate_limit.rs`",
                   "Opened PR #482; CI green"],
                  ["Add per-key overrides (`rate_limits` table) as requested in review",
                   "Reply to the question about Redis failover: currently fails open",
                   "Load test with `k6 run load/search.js` at 2x peak"],
                  ["Limits are per process until the Redis key prefix change lands; don't deploy with `REDIS_URL` unset",
                   "Staging has a lower default (20 req/s) set in `config/staging.toml`"])),
    dict(
        sid="a93f0e17-6c2b-4d1a-8f5e-b47c19d2e8a0", repo="billing-service", branch="proration-rounding",
        days=5.4, ahead=3, dirty=1, build={".venv": 286_000_000, ".pytest_cache": 2_400_000},
        pr=None, ai_title="Investigate off-by-one-cent proration",
        first="Customers who switch plans mid-cycle are sometimes charged one cent too much. Find out why.",
        last="write the migration for the existing invoices next",
        brief=dict(title="Fix proration rounding on plan changes", phase="build",
                   status="Root cause found (float math in proration); Decimal fix is committed, backfill for old invoices not started.",
                   next=["Write migration to correct affected open invoices", "Add property test for proration totals",
                         "Open the PR"]),
        card=card("Stop mid-cycle plan changes from over-charging by one cent.",
                  ["Traced it to float arithmetic in `proration.py::prorate()`",
                   "Switched to `Decimal` with `ROUND_HALF_EVEN`; 3 commits on `proration-rounding`"],
                  ["Migration to fix open invoices created since March",
                   "Property test: prorated parts always sum to the plan price",
                   "Open the PR and tag finance for sign-off"],
                  ["`tests/fixtures/invoices.json` is hand-edited and uncommitted",
                   "Closed invoices must not be touched; only `status = 'open'`"])),
    dict(
        sid="2e6d48b0-c19a-47f3-9d02-58ab3e7f61c4", repo="web-app", branch="settings-form-migration",
        days=9.1, ahead=0, dirty=2, build={"node_modules": 512_000_000},
        pr=None, ai_title="Plan settings page form migration",
        first="The settings page still uses the old form helpers. Plan the move to the new form library.",
        last="compare the two validation approaches before we commit to one",
        brief=dict(title="Migrate settings page to new form library", phase="design",
                   status="Field inventory is done; still choosing between schema-first and per-field validation.",
                   next=["Pick a validation approach and note why", "Prototype the profile section",
                         "List fields that need custom widgets"]),
        card=card("Move `pages/settings` off the legacy form helpers onto the new form library without changing behavior.",
                  ["Inventory of all 41 fields and their validators in `docs/settings-fields.md` (uncommitted)",
                   "Spike branch shows the library handles nested address fields"],
                  ["Decide schema-first (zod) vs per-field validation",
                   "Prototype the Profile section behind `?newForms=1`",
                   "Flag fields that need custom widgets (timezone, avatar upload)"],
                  ["The legacy helpers swallow server errors on the Billing tab; keep that visible in the new version"])),
    dict(
        sid="d4b81c3e-0f7a-4e62-b9d5-1a6c8e2f9047", repo="api-server", branch="webhook-retries",
        days=12.3, ahead=6, dirty=0, build={"target": 980_000_000},
        pr=None, ai_title="Webhook retries and dead letters",
        first="Webhook deliveries are fire-and-forget. Add retries with backoff and a dead-letter queue.",
        last="next: the admin endpoint to replay dead letters",
        brief=dict(title="Webhook retries with dead-letter queue", phase="build",
                   status="Exponential backoff and the dead-letter table work locally; replay endpoint and metrics remain.",
                   next=["Add admin endpoint to replay dead letters", "Emit retry and dead-letter metrics",
                         "Open the PR"]),
        card=card("Retry failed webhook deliveries with backoff and park permanent failures in a dead-letter queue.",
                  ["Retry worker with jittered exponential backoff (max 8 attempts)",
                   "`webhook_dead_letters` table and migration", "6 commits, tests pass"],
                  ["`POST /admin/webhooks/dead-letters/:id/replay`",
                   "Counters for retries and dead letters", "Open the PR"],
                  ["Backoff schedule is in `config/webhooks.toml`; product wants it customer-visible later"])),
    dict(
        sid="f05a7d92-8e3c-41b6-a7f4-c3d0e19b5826", repo="sync-engine", branch="offline-conflicts",
        days=16.7, ahead=0, dirty=0, build={},
        pr=None, ai_title="Research offline conflict handling",
        first="Users editing the same note offline lose changes on sync. Research conflict resolution options.",
        last="summarize the CRDT vs last-writer-wins tradeoffs",
        brief=dict(title="Offline edit conflict resolution", phase="research",
                   status="Compared last-writer-wins, three-way merge, and CRDTs; leaning toward per-field merge.",
                   next=["Measure how often real conflicts happen", "Write up the per-field merge proposal",
                         "Check sync payload size impact"]),
        card=card("Pick a conflict strategy so offline edits to the same note stop overwriting each other.",
                  ["Reproduced the data loss with two offline clients",
                   "Notes on last-writer-wins, three-way merge, and CRDT libraries"],
                  ["Add a counter for conflicting syncs to size the problem",
                   "Draft the per-field merge proposal",
                   "Estimate payload growth from per-field timestamps"],
                  ["None"])),
    dict(
        sid="8b2c6f14-5d9e-4a07-b3e1-9f7a2c4d0b68", repo="ci-config", branch="cache-deps",
        days=38.5, ahead=0, dirty=0, build={},
        pr=dict(number=213, state="MERGED", title="Cache dependencies between CI runs"),
        ai_title="Speed up CI with dependency caching",
        first="CI spends 6 minutes installing dependencies on every run. Cache them.",
        last="note the follow-ups and we can call this done",
        brief=dict(title="Cache dependencies between CI runs", phase="wrap-up",
                   status="PR #213 merged; CI runs dropped from 14 to 8 minutes. Only follow-ups remain.",
                   next=["Cache the Docker layer builds too", "Delete the old warm-up job"]),
        card=card("Cut CI time by caching dependency installs between runs.",
                  ["Cache keyed on lockfile hashes; PR #213 merged", "Median CI run 14m → 8m"],
                  ["Cache Docker layers with `--cache-from`", "Remove the nightly warm-up job"],
                  ["Cache is invalidated by any lockfile change, including comments"])),
]

LIVE = dict(
    sid=LIVE_SID, repo="web-app", branch="csv-export", ahead=2, dirty=3,
    build={"node_modules": 431_000_000, ".next": 97_000_000},
    ai_title="Export dashboard reports as CSV",
    brief=dict(title="Export dashboard reports as CSV", phase="build",
               status="Streaming CSV endpoint works for small reports; large exports still time out behind the proxy.",
               next=["Move large exports to a background job", "Add the Export button to the reports toolbar",
                     "Test with a 1M-row report"]),
    summary=card("Let users download any dashboard report as CSV.",
                 ["`GET /reports/:id/export.csv` streams rows with the existing query builder",
                  "Column headers follow the report's display names", "2 commits on `csv-export`"],
                 ["Queue exports over 50k rows and email a link", "Export button in `ReportToolbar.tsx`",
                  "Test with a 1M-row report"],
                 ["The proxy cuts responses after 60s; streaming alone won't fix big reports",
                  "3 files uncommitted: toolbar WIP"]),
)


def run(*argv, cwd=None, check=True, **kw):
    return subprocess.run(argv, cwd=cwd, env=ENV, check=check, capture_output=True, text=True, **kw)


def git(cwd, *args):
    return run("git", "-C", str(cwd), *args).stdout


def write_exec(path, text):
    path.write_text(text)
    path.chmod(0o755)


def make_repo(name):
    origin = ROOT / "origin" / f"{name}.git"
    main = ROOT / "code" / name
    if main.exists():
        return main
    run("git", "init", "-q", "--bare", "-b", "main", str(origin))
    seed = ROOT / "seed" / name
    seed.mkdir(parents=True)
    git(seed, "init", "-q", "-b", "main")
    (seed / ".gitignore").write_text("node_modules/\n.next/\ntarget/\n.venv/\n.pytest_cache/\n")
    (seed / "README.md").write_text(f"# {name}\n")
    (seed / "src").mkdir()
    (seed / "src" / "main.txt").write_text("v1\n")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "initial commit")
    git(seed, "remote", "add", "origin", str(origin))
    git(seed, "push", "-q", "origin", "main")
    run("git", "clone", "-q", str(origin), str(main))
    shutil.rmtree(seed)
    return main


COMMITS = [
    "add {b} scaffolding", "wire up {b} config", "cover {b} edge cases",
    "handle errors in {b}", "tidy {b} naming", "document {b}",
]


def make_worktree(s):
    main = make_repo(s["repo"])
    wt = ROOT / "wt" / f"{s['repo']}-{s['branch']}"
    git(main, "worktree", "add", "-q", "-b", s["branch"], str(wt), "origin/main")
    for i in range(s["ahead"]):
        (wt / "src" / f"{s['branch']}-{i}.txt").write_text(f"change {i}\n")
        git(wt, "add", ".")
        git(wt, "commit", "-qm", COMMITS[i % len(COMMITS)].format(b=s["branch"].replace("-", " ")))
    for i in range(s["dirty"]):
        (wt / "src" / f"wip-{i}.txt").write_text("work in progress\n")
    for d, size in s["build"].items():
        (wt / d).mkdir()
        with open(wt / d / "blob", "wb") as f:
            f.truncate(size)  # sparse: reports the size without using the disk
    if s.get("pr"):
        pr = dict(s["pr"], url=f"https://github.com/example/{s['repo']}/pull/{s['pr']['number']}")
        (CANNED / "prs" / f"{s['branch']}.json").write_text(json.dumps(pr))
    (CANNED / "briefs" / f"{s['branch']}.json").write_text(json.dumps(s["brief"]))
    return wt


def entry(kind, text, wt, branch):
    content = text if kind == "user" else [{"type": "text", "text": text}]
    return {"type": kind, "message": {"role": kind, "content": content},
            "cwd": str(wt), "gitBranch": branch, "version": VERSION}


def write_transcript(sid, wt, branch, title, turns, last):
    project = CONFIG / "projects" / str(wt).replace("/", "-")
    project.mkdir(parents=True, exist_ok=True)
    lines = [{"type": "ai-title", "aiTitle": title}]
    for kind, text in turns:
        lines.append(entry(kind, text, wt, branch))
    lines.append({"type": "last-prompt", "lastPrompt": last})
    (project / f"{sid}.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def wait_for_briefs(sids, timeout=30):
    deadline = time.time() + timeout
    pending = set(sids)
    while pending and time.time() < deadline:
        for sid in list(pending):
            r = json.loads((CONFIG / "parked" / f"{sid}.json").read_text())
            if r.get("brief_status") != "pending":
                if r.get("brief_status") != "done":
                    sys.exit(f"brief failed for {sid}: {r.get('brief_error')}")
                pending.discard(sid)
        time.sleep(0.1)
    if pending:
        sys.exit(f"briefs still pending: {pending}")


def main():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for d in (HOME, CONFIG, BIN, CANNED / "briefs", CANNED / "prs"):
        d.mkdir(parents=True)
    write_exec(BIN / "claude", FAKE_CLAUDE)
    write_exec(BIN / "gh", FAKE_GH)
    (CANNED / "summary.md").write_text(LIVE["summary"])

    for s in SESSIONS:
        wt = make_worktree(s)
        write_transcript(s["sid"], wt, s["branch"], s["ai_title"],
                         [("user", s["first"]), ("assistant", "On it.")] * 20, s["last"])
        cardfile = ROOT / "card.md"
        cardfile.write_text(s["card"])
        run(sys.executable, str(CLAUDE_PARK), "park", "--session", s["sid"],
            "--summary-file", str(cardfile), cwd=wt)
        cardfile.unlink()
    wait_for_briefs([s["sid"] for s in SESSIONS])

    # Backdate the earlier parks so the list shows realistic ages.
    for s in SESSIONS:
        path = CONFIG / "parked" / f"{s['sid']}.json"
        r = json.loads(path.read_text())
        when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=s["days"])
        r["parked_at"] = when.isoformat(timespec="seconds")
        path.write_text(json.dumps(r, indent=2) + "\n")

    # The session parked on camera: a worktree with a live-looking transcript.
    wt = make_worktree(LIVE)
    turns = [
        ("user", "Add CSV export for dashboard reports."),
        ("assistant", "Added a streaming GET /reports/:id/export.csv endpoint."),
    ] * 30 + [
        ("user", "The 2M-row report times out after 60s."),
        ("assistant", "The proxy cuts responses at 60s. Large exports need a background job."),
    ]
    write_transcript(LIVE_SID, wt, LIVE["branch"], LIVE["ai_title"], turns,
                     "let's move big exports to a background job")

    env_sh = ROOT / "env.sh"
    lines = [
        "# Generated by docs/demo/setup.py. Scrub the caller's session, then isolate.",
        'for v in $(compgen -e); do case "$v" in CLAUDE*|ITERM*|FZF*|GIT_*) unset "$v";; esac; done',
        "unset CLAUDECODE CLAUDE_PID CLAUDE_CODE_SESSION_ID ITERM_SESSION_ID",
    ]
    lines += [f"export {k}='{v}'" for k, v in ENV.items()]
    lines += [
        f"export CLAUDE_CODE_SESSION_ID='{LIVE_SID}'  # fictional; its transcript is in the demo dir",
        f"export DEMO_SESSION_UI='{REPO / 'docs' / 'demo' / 'fake_session.py'}'",
        f"cd '{wt}'",
        "export HISTFILE=/dev/null",
        # A fresh terminal for the second half of the demo.
        "newtab() { cd ~; PS1='\\[\\e[1;32m\\]~\\[\\e[0m\\] \\$ '; clear; }",
        "export PS1='\\[\\e[1;32m\\]web-app-csv-export\\[\\e[0m\\] \\$ '",
    ]
    env_sh.write_text("\n".join(lines) + "\n")
    print(f"demo fixture ready: {ROOT}")


if __name__ == "__main__":
    main()
