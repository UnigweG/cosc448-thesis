"""03 and 04 against a mocked SonarQube API (no server needed)."""
import csv
import json
import sys
from unittest import mock

import pandas as pd
import pytest
import requests

ITEMS = [("COSC-499-W2024", "a", 2024), ("COSC-499-W2024", "b", 2024)]


@pytest.fixture
def s03(scripts, tmp_path, monkeypatch):
    m = scripts("03_sonar_scan.py")
    monkeypatch.setattr(m, "RESULTS", tmp_path)
    monkeypatch.setattr(m, "LOG_DIR", tmp_path / "sonar")
    monkeypatch.setattr(m, "EMPTY_SETTINGS", tmp_path / "sonar" / "empty.properties")
    monkeypatch.setattr(m, "read_selection", lambda: ITEMS)
    monkeypatch.setattr(m, "sonar_session", lambda: None)
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    monkeypatch.setattr(m, "scan", lambda item: {
        "cohort_year": item[2], "org": item[0], "repo": item[1], "project_key": f"k_{item[1]}",
        "status": "ok", "notes": "", "head_sha": "sha"})
    monkeypatch.setattr(sys, "argv", ["03"])
    return m


def status(tmp_path):
    with open(tmp_path / "sonar_scan_status.csv") as f:
        return {r["repo"]: r for r in csv.DictReader(f)}


def http_error(code):
    r = requests.Response()
    r.status_code, r.url = code, "http://localhost:9000/api/ce/activity?component=k"
    return requests.HTTPError(response=r)


def test_403_exits_with_token_hint_after_writing_status(s03, tmp_path, monkeypatch):
    monkeypatch.setattr(s03, "sonar_get", mock.Mock(side_effect=http_error(403)))
    with pytest.raises(SystemExit, match="user token"):
        s03.main()
    assert [r["status"] for r in status(tmp_path).values()] == ["ok", "ok"]


def test_other_http_errors_propagate(s03, monkeypatch):
    monkeypatch.setattr(s03, "sonar_get", mock.Mock(side_effect=http_error(500)))
    with pytest.raises(requests.HTTPError):
        s03.main()


def test_queue_timeout_marks_pending_without_reading_tasks(s03, tmp_path, monkeypatch):
    get = mock.Mock()
    monkeypatch.setattr(s03, "sonar_get", get)
    monkeypatch.setattr(s03, "wait_for_queue", lambda session: False)
    s03.main()
    rows = status(tmp_path)
    assert {r["status"] for r in rows.values()} == {"pending"}
    assert rows["a"]["notes"] == "queue timeout, task status not checked"
    get.assert_not_called()


def test_failed_server_task_is_recorded(s03, tmp_path, monkeypatch):
    def get(session, path, **kw):
        if path == "/api/ce/activity" and "status" in kw:  # queue check
            return {"tasks": []}
        if path == "/api/ce/activity":
            ok = kw["component"] == "k_a"
            return {"tasks": [{"status": "SUCCESS" if ok else "FAILED", "errorMessage": "boom"}]}
        if path == "/api/project_analyses/search":
            return {"analyses": [{"date": "d"}]}
        raise AssertionError(path)
    monkeypatch.setattr(s03, "sonar_get", get)
    s03.main()
    rows = status(tmp_path)
    assert rows["a"]["status"] == "ok"
    assert rows["b"]["status"] == "failed" and "server task FAILED: boom" in rows["b"]["notes"]
    assert b"\r" not in (tmp_path / "sonar_scan_status.csv").read_bytes()


def test_language_flags_notes_unanalysed_languages(s03, tmp_path):
    langs = {"JavaScript": 600, "EJS": 165, "SCSS": 100, "Vue": 100, "Dart": 35}
    pd.DataFrame([{"org": "o", "repo": "r", "language_bytes": json.dumps(langs)}]).to_csv(
        tmp_path / "repo_inventory.csv", index=False)
    notes = s03.language_flags("o", "r")
    assert any(n.startswith("EJS 16% not analysed") for n in notes)
    assert not any("SCSS" in n or "Vue" in n for n in notes)


def test_scanner_ignores_team_sonar_settings(s03, tmp_path, monkeypatch):
    run = mock.Mock(return_value=mock.Mock(returncode=0))
    monkeypatch.setattr(s03.subprocess, "run", run)
    monkeypatch.setenv("SONAR_HOST_URL", "http://h")
    s03.run_scanner(tmp_path, "k", "n", tmp_path / "log.txt")
    assert f"-Dproject.settings={s03.EMPTY_SETTINGS}" in run.call_args.args[0]


def test_export_zero_fills_issues_only_for_exported_projects(scripts, tmp_path, monkeypatch):
    m = scripts("04_sonar_export.py")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "environment.md").write_text("# Environment\n")
    monkeypatch.setattr(m, "RESULTS", tmp_path)
    monkeypatch.setattr(m, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(m, "available_keys", lambda: set(m.KEYS))
    monkeypatch.setattr(m, "read_selection", lambda: ITEMS)
    monkeypatch.setattr(m, "sonar_session", lambda: None)
    pd.DataFrame([{"project_key": m.project_key(2024, "a"), "status": "ok"},
                  {"project_key": m.project_key(2024, "b"), "status": "failed"}]).to_csv(
        tmp_path / "sonar_scan_status.csv", index=False)

    def get(session, path, **kw):
        if path == "/api/measures/component":
            return {"component": {"measures": [{"metric": "ncloc", "value": "100"},
                                               {"metric": "sqale_rating", "value": "1.0"}]}}
        if path == "/api/project_analyses/search":
            return {"analyses": [{"date": "d"}]}
        if path == "/api/measures/component_tree":
            return {"components": [], "paging": {"total": 0}}
        if path == "/api/issues/search":
            return {"facets": [
                {"property": "severities", "values": [{"val": "MAJOR", "count": 3},
                                                      {"val": "INFO", "count": 0}]},
                {"property": "impactSeverities", "values": [{"val": "HIGH", "count": 2}]}]}
        raise AssertionError(path)
    monkeypatch.setattr(m, "sonar_get", get)
    m.main()

    lines = (tmp_path / "sonarqube_metrics.csv").read_text().splitlines()
    df = pd.read_csv(tmp_path / "sonarqube_metrics.csv")
    issues = [c for c in df if c.startswith("sq_issues_")]
    assert df.loc[0, "sq_issues_sev_major"] == 3 and df.loc[0, "sq_issues_impact_high"] == 2
    assert df.loc[1, issues].isna().all()
    assert ",1," in lines[1] and "3.0" not in lines[1]
