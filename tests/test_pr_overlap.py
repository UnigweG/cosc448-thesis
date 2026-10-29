"""23: files per PR from git, hygiene, bot exclusion, the overlap window and the truncation flag."""
import json
import subprocess
from datetime import datetime, timezone

import pytest

DAY = 86400
T0 = 1_700_000_000


@pytest.fixture
def m(scripts):
    return scripts("23_pr_overlap.py")


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class Repo:
    def __init__(self, path):
        self.path = path
        path.mkdir(parents=True)
        git(path, "init", "-q", "-b", "main")

    def commit(self, files, message="c"):
        for name, text in files.items():
            f = self.path / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text)
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "-m", message)
        return git(self.path, "rev-parse", "HEAD")


def pr(number, merged_day, oids, author="amy", total=None, base="main", head=None):
    merged = None if merged_day is None else \
        datetime.fromtimestamp(T0 + merged_day * DAY, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"number": number, "mergedAt": merged, "createdAt": merged, "state": "MERGED" if merged else "OPEN",
            "author": {"login": author}, "baseRefName": base, "headRefName": head or f"feat-{number}",
            "changedFiles": 0,
            "commits": {"totalCount": len(oids) if total is None else total,
                        "nodes": [{"commit": {"oid": o}} for o in oids]}}


@pytest.fixture
def world(m, tmp_path, monkeypatch):
    """A fixture repo under data/repos/2023/r with its prs.json under data/github/2023/r."""
    repo = Repo(tmp_path / "repos" / "r")
    gh = tmp_path / "github" / "2023" / "r"
    gh.mkdir(parents=True)
    (gh / "meta.json").write_text(json.dumps({"default_branch": "main"}))
    monkeypatch.setattr(m, "GITHUB", tmp_path / "github")
    monkeypatch.setattr(m, "repo_dir", lambda year, folder: tmp_path / "repos" / folder)

    def run(prs):
        (gh / "prs.json").write_text(json.dumps(prs))
        rows, val, excl = m.measure(2023, "r")
        return {r["pr_number"]: r for r in rows}, val, excl
    return repo, run


def test_overlap_inside_and_outside_the_window(m):
    items = [(T0, 1, {"a.py"}), (T0 + 10 * DAY, 2, {"a.py", "b.py"}), (T0 + 40 * DAY, 3, {"a.py"})]
    r14, r28 = m.overlap(items, 14), m.overlap(items, 28)
    assert r14[1] == (None, None, 0, 0)               # nothing before the first PR: undefined, not 0
    assert r14[2] == (0.5, 1, 1, 1)                   # a.py was touched 10 days earlier
    assert r14[3] == (None, None, 0, 0) and r28[3] == (None, None, 0, 0)  # 30 days after #2: outside both windows
    assert m.overlap(items, 45)[3] == (1.0, 1, 2, 2)


def test_window_is_open_at_both_ends(m):
    items = [(T0, 1, {"a.py"}), (T0 + 14 * DAY, 2, {"a.py"}), (T0 + 14 * DAY - 1, 3, {"a.py"})]
    out = m.overlap(items, 14)
    assert out[2][2] == 1  # PR 1 is exactly 14 days back (outside); PR 3, one second earlier, is inside
    assert out[3][2] == 1  # PR 1 is 14 days minus 1 s back: inside


def test_same_instant_prs_count_by_number(m):
    out = m.overlap([(T0, 2, {"a.py"}), (T0, 1, {"a.py"})], 14)
    assert out[1][2] == 0 and out[2][:3] == (1.0, 1, 1)  # the lower number is the earlier one


@pytest.mark.parametrize("path, drop", [
    ("package-lock.json", True), ("web/yarn.lock", True), ("Pipfile.lock", True), ("go.sum", True),
    ("web/node_modules/x/index.js", True), ("frontend/dist/app.js", True), ("src/app.min.js", True),
    ("pkg/types.d.ts", True), ("vendor/lib/a.php", True), ("src/a.js.map", True),
    ("src/build/ok.py", True), ("src/main.py", False), ("README.md", False), ("src/lock.py", False),
])
def test_hygiene(m, path, drop):
    assert m.excluded("some-repo", path) is drop


def test_build_dir_is_kept_for_the_team_that_keeps_source_there(m):
    assert m.excluded("capstone-project-team-2-003-1", "build/app.py") is False


def test_code_extensions(m):
    assert m.is_code("src/a.PY") and m.is_code("x/y.tsx") and m.is_code("s.html")
    assert not (m.is_code("README.md") or m.is_code("Makefile") or m.is_code("img/logo.png"))


def test_bot_rules(m):
    assert m.is_bot_login("dependabot[bot]") and m.is_bot_login("github-classroom")
    assert m.is_bot_spec("renovate[bot]") and m.is_bot_spec("my-dependabot")
    assert not m.is_bot_login("amy") and not m.is_bot_login(None)


def test_commit_files_skips_merges_and_reports_missing(m, tmp_path):
    repo = Repo(tmp_path / "g")
    base = repo.commit({"a.py": "1"})
    git(repo.path, "checkout", "-q", "-b", "feat")
    f1 = repo.commit({"b.py": "1", "sub/c.py": "1"})
    git(repo.path, "checkout", "-q", "main")
    main2 = repo.commit({"a.py": "2"})
    git(repo.path, "checkout", "-q", "feat")
    git(repo.path, "merge", "-q", "--no-edit", "main")
    merge = git(repo.path, "rev-parse", "HEAD")
    files, missing, merges = m.commit_files(repo.path, [base, f1, main2, merge, "0" * 40])
    assert files[f1] == {"b.py", "sub/c.py"} and files[base] == {"a.py"}
    assert merge not in files and merges == {merge}
    assert missing == {"0" * 40}


def test_bots_lockfiles_and_unmerged_prs_do_not_count(world):
    repo, run = world
    c1 = repo.commit({"src/a.py": "1"})
    c2 = repo.commit({"src/a.py": "2"})
    c3 = repo.commit({"src/a.py": "3", "package-lock.json": "x", "node_modules/m/i.js": "x", "README.md": "x"})
    c4 = repo.commit({"package-lock.json": "y"})
    c5 = repo.commit({"src/a.py": "4"})
    rows, val, excl = run([pr(1, 0, [c1]), pr(2, 1, [c2], author="dependabot[bot]"),
                           pr(3, 2, [c3]), pr(4, 3, [c4]), pr(5, 4, [c5], author="amy"), pr(6, None, [c5])])
    assert set(rows) == {1, 3, 5}                       # bot, lockfile-only and unmerged PRs are out
    assert excl == {"bot": 1, "bot_beyond_spec": 0, "no_files": 1}
    assert rows[3]["n_files_raw"] == 4 and rows[3]["n_files_all"] == 2 and rows[3]["n_files_code"] == 1
    # PR 3: its code file src/a.py was touched by PR 1; the bot's PR 2 is not a reference
    assert rows[3]["ref_prs_code_14"] == 1
    assert rows[3]["overlap_share_code_14"] == 1.0 and rows[3]["overlap_share_all_14"] == 0.5
    assert rows[1]["overlap_share_code_14"] is None and rows[1]["ref_prs_code_14"] == 0  # no history
    assert rows[5]["ref_prs_code_28"] == 2
    assert len(val) == 6  # validation covers every PR, merged or not


def test_prs_without_code_files_have_no_code_overlap(world):
    repo, run = world
    c1 = repo.commit({"src/a.py": "1"})
    c2 = repo.commit({"docs/notes.md": "1"})
    rows, _, _ = run([pr(1, 0, [c1]), pr(2, 1, [c2])])
    assert rows[2]["n_files_code"] == 0 and rows[2]["overlap_share_code_14"] is None
    assert rows[2]["overlap_share_all_14"] == 0.0


def test_truncated_and_missing_commit_lists_are_flagged(world):
    repo, run = world
    c1 = repo.commit({"a.py": "1"})
    c2 = repo.commit({"b.py": "1"})
    rows, val, _ = run([pr(1, 0, [c1, c2], total=150),           # GitHub lists only the first 100 commits
                        pr(2, 1, [c2, "f" * 40]),                # one commit is not in the clone
                        pr(3, 2, [c1], base="release")])         # stacked on a non-default branch
    assert rows[1]["files_complete"] is False and rows[1]["commits_total"] == 150 and rows[1]["commits_listed"] == 2
    assert "files_incomplete" in rows[1]["flags"]
    assert rows[2]["commits_missing_locally"] == 1 and rows[2]["files_complete"] is False
    assert rows[3]["files_complete"] is True and rows[3]["flags"] == "non_default_base"
    assert rows[3]["is_default_branch"] is False and rows[1]["is_default_branch"] is True
    assert [v["files_complete"] for v in val] == [False, False, True]


def test_validation_table_ignores_incomplete_lists(m):
    val = [{"year": 2023, "repo": "r", "pr_number": i, "merged": True, "files_complete": c,
            "n_files_raw": raw, "changed_files": ch}
           for i, (c, raw, ch) in enumerate([(True, 3, 3), (True, 4, 3), (True, 2, 3), (False, 99, 1)])]
    row = m.validation_table(val).query("scope == 'all_prs' and repo == 'ALL' and year == 2023").iloc[0]
    assert row.n_prs_total == 4 and row.n_compared == 3 and row.share_incomplete == 0.25
    assert row.share_exact == pytest.approx(1 / 3) and row.share_within_1 == 1.0
    assert row.share_union_larger == pytest.approx(1 / 3) and row.median_ratio == 1.0


def test_release_prs_from_a_branch_that_other_prs_target_are_flagged(world):
    repo, run = world
    c1 = repo.commit({"a.py": "1"})
    c2 = repo.commit({"a.py": "2"})
    rows, _, _ = run([pr(1, 0, [c1], base="dev"), pr(2, 5, [c1, c2], base="main", head="dev")])
    assert rows[1]["flags"] == "non_default_base" and rows[2]["flags"] == "integration_pr"
    assert rows[2]["overlap_share_code_14"] == 1.0  # the release PR re-contains PR 1's files


def test_a_pr_with_no_history_is_undefined_not_zero(m):
    out = m.overlap([(T0, 1, {"a.py"}), (T0 + 40 * DAY, 2, {"a.py"})], 28)
    assert out[1][:2] == (None, None) and out[2][:2] == (None, None)  # PR 1 is 40 days back: outside the window


def test_release_prs_are_not_reference_for_the_sensitivity_columns(world):
    repo, run = world
    c1 = repo.commit({"a.py": "1"})
    c2 = repo.commit({"b.py": "1"})
    c3 = repo.commit({"a.py": "2"})
    # PR 1 (day 0) into dev; release PR 2 (day 20) re-contains a.py and b.py; PR 3 (day 30) touches a.py
    rows, _, _ = run([pr(1, 0, [c1], base="dev"), pr(2, 20, [c1, c2], base="main", head="dev"),
                      pr(3, 30, [c3], base="main")])
    assert rows[3]["overlap_share_code_14"] == 1.0                       # the release PR (day 20) is in the window
    assert rows[3]["overlap_share_code_14_excl_integration"] is None     # without it PR 3 has no history
    assert rows[2]["overlap_share_code_14_excl_integration"] is None     # the release PR is not measured


def test_year_comparison_pools_prs_and_resamples_repos(m):
    import pandas as pd
    rows = [{"year": 2022, "repo": "a", "overlap_share_code_14": x, "overlap_share_code_28": x,
             "overlap_share_code_14_excl_integration": x, "overlap_share_code_28_excl_integration": x,
             "overlap_share_all_14": x, "overlap_share_all_28": x,
             "overlap_share_all_14_excl_integration": x, "overlap_share_all_28_excl_integration": x}
            for x in (1.0, 1.0, 1.0, None)]
    rows += [dict(rows[0], repo="b", overlap_share_code_28=0.0)]
    rows += [dict(rows[0], year=2026, repo="c")]
    out = m.year_comparison(pd.DataFrame(rows), draws=200)
    r = out.query("year == 2022 and variant == 'code' and window_days == 28 and basis == 'all_kept'").iloc[0]
    assert r.n_repos == 2 and r.n_prs_defined == 4          # the empty share (no history) is not counted
    assert r.pooled_mean == pytest.approx(0.75) and r.repo_median == pytest.approx(0.5)
    assert r.ci95_low <= r.pooled_mean <= r.ci95_high
    one = out.query("year == 2026 and variant == 'code' and window_days == 28 and basis == 'all_kept'").iloc[0]
    assert pd.isna(one.ci95_low) and pd.isna(one.ci95_high)  # one repo: no interval
