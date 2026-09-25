"""06 merge: commit mismatches stop the run, old snapshots are kept, dropped repos go."""
import pandas as pd
import pytest

KEY = {"cohort_year": 2024, "org": "COSC-499-W2024"}
SEL = [("COSC-499-W2024", "a", 2024), ("COSC-499-W2024", "b", 2024)]


@pytest.fixture
def m(scripts, tmp_path, monkeypatch):
    m = scripts("06_build_results.py")
    monkeypatch.setattr(m, "RESULTS", tmp_path)
    monkeypatch.setattr(m, "read_selection", lambda: SEL)
    monkeypatch.setattr(m, "commit_date", lambda y, r, s: "2025-04-01T00:00:00Z")
    rows = [dict(KEY, repo=r) for r in ("a", "b")]
    pd.DataFrame([dict(x, section="", team_key="", head_sha="s_" + x["repo"]) for x in rows]
                 ).to_csv(tmp_path / "repo_inventory.csv", index=False)
    pd.DataFrame([dict(x, project_key="k_" + x["repo"], sq_ncloc=n, sq_comment_lines=10,
                       sq_complexity=5, sq_functions=f, sq_violations=2,
                       sq_py_ncloc=n, sq_py_comment_lines=10)
                  for x, n, f in zip(rows, [1000, 0], [5, 0])]
                 ).to_csv(tmp_path / "sonarqube_metrics.csv", index=False)
    pd.DataFrame([dict(x, project_key="k_" + x["repo"], head_sha="s_" + x["repo"],
                       status="ok", notes="") for x in rows]
                 ).to_csv(tmp_path / "sonar_scan_status.csv", index=False)
    pd.DataFrame([dict(x, commit_sha="s_" + x["repo"], python_file_count=1, py_sloc=10)
                  for x in rows]).to_csv(tmp_path / "custom_metrics.csv", index=False)
    return m


def test_ratios_and_zero_denominators(m, tmp_path):
    m.main()
    df = pd.read_csv(tmp_path / "results.csv").set_index("repo")
    assert df.loc["a", "sq_comment_pct_pdf"] == 1.0 and df.loc["a", "sq_issues_per_kloc"] == 2.0
    assert pd.isna(df.loc["b", "sq_comment_pct_pdf"])
    assert pd.isna(df.loc["b", "sq_complexity_per_function"])


@pytest.mark.parametrize("name,col", [("custom_metrics.csv", "commit_sha"),
                                      ("sonar_scan_status.csv", "head_sha")])
def test_commit_mismatch_stops(m, tmp_path, name, col):
    df = pd.read_csv(tmp_path / name)
    df.loc[0, col] = "other"
    df.to_csv(tmp_path / name, index=False)
    with pytest.raises(SystemExit, match="different commit"):
        m.main()


def test_keeps_other_snapshots_and_drops_unselected_repos(m, tmp_path, capsys):
    m.main()
    df = pd.read_csv(tmp_path / "results.csv")
    old = df.iloc[[0, 0]].reset_index(drop=True)
    old["commit_sha"] = ["s_old", "s_gone"]
    old.loc[old.index[1], "repo"] = "gone"
    pd.concat([df, old]).to_csv(tmp_path / "results.csv", index=False)
    m.main()
    df = pd.read_csv(tmp_path / "results.csv")
    assert sorted(df.commit_sha) == ["s_a", "s_b", "s_old"]
    assert "kept 1 row(s)" in capsys.readouterr().out
