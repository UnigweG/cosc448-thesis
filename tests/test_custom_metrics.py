"""05 on a tiny git repo: exclusions, an unparsable file, the pylint fatal path, bandit."""
import subprocess

import pytest

GOOD = '''"""Module."""


def check(x):
    """Return a label."""
    assert x is not None
    if x > 1:
        return "big"  # comment
    return "small"
'''


@pytest.fixture
def m(scripts):
    return scripts("05_custom_metrics.py")


@pytest.fixture
def repo(tmp_path):
    files = {"good.py": GOOD,
             "py2.py": 'print "python 2"\n',
             "node_modules/pkg/vendored.py": "x = 1\n",
             "notes.ipynb": "{}\n"}
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    # a Latin-1 byte without an encoding line: pylint's F0010, as in W2025 team 6
    (tmp_path / "latin1.py").write_bytes(b"def f(a):\n    # O(n\xb2)\n    return a\n")
    (tmp_path / "untracked.py").write_text("y = 2\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", *files, "latin1.py"], check=True)
    return tmp_path


def test_file_set_excludes_vendored_untracked_and_notebooks(m, repo):
    assert m.python_files(repo) == (["good.py", "latin1.py", "py2.py"], 1)


def test_radon_counts_unparsable_file_and_asserts(m, repo):
    r = m.radon_metrics(repo, ["good.py", "py2.py"])
    assert r["py_parse_errors"] == 1
    assert r["py_cc_blocks"] == 1 and r["py_cc_max"] == 3  # if + assert
    assert r["py_sloc"] == 5 and r["py_comments"] == 1  # radon sloc skips docstrings


def test_pylint_fatal_file_gives_zero_and_rerun_score(m, repo):
    score, excl, fatal, note = m.pylint_score(repo, ["good.py", "latin1.py"])
    assert score == 0.0 and fatal == 1 and excl > 0
    assert note == "pylint fatal in 1 file(s): latin1.py"


def test_pylint_rerun_timeout_keeps_first_score(m, monkeypatch):
    calls = []

    def run(path, files):
        calls.append(files)
        if len(calls) == 2:
            raise subprocess.TimeoutExpired("pylint", 1)
        return 0.0, ["bad.py"], ""
    monkeypatch.setattr(m, "run_pylint", run)
    assert m.pylint_score("p", ["a.py", "bad.py"]) == (
        0.0, None, 1, "pylint fatal in 1 file(s): bad.py; pylint timeout on rerun")


def test_pylint_no_score_note_has_no_local_path(m, repo, monkeypatch):
    out = subprocess.CompletedProcess([], 32, "", f"Error: {repo}/good.py broke\n")
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **kw: out)
    _, _, note = m.run_pylint(repo, ["good.py"])
    assert str(repo) not in note and "good.py broke" in note


def test_bandit_counts_by_severity(m, repo):
    counts, _ = m.bandit_counts(repo, ["good.py"])
    assert counts == {"py_bandit_high": 0, "py_bandit_medium": 0, "py_bandit_low": 1}


def test_only_rejects_unknown_repo(m, monkeypatch):
    monkeypatch.setattr(m.sys, "argv", ["05", "--only", "no-such-repo"])
    with pytest.raises(SystemExit, match="not in config/repo_selection.txt"):
        m.main()
