"""Shared helpers: project paths, .env loading and a SonarQube API session."""
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
LOGS = ROOT / "logs"
DATA = ROOT / "data" / "repos"
SELECTION = ROOT / "config" / "repo_selection.txt"

ORGS = {
    "COSC-499-W2023": 2023,
    "COSC-499-W2024": 2024,
    "COSC-499-W2025": 2025,
}


def load_env():
    """Read KEY=VALUE pairs from .env into os.environ (without overriding)."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    os.environ.setdefault("SONAR_HOST_URL", "http://localhost:9000")


def sonar_session():
    load_env()
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        raise SystemExit("SONAR_TOKEN missing (put it in .env)")
    s = requests.Session()
    s.auth = (token, "")  # token as username, empty password
    s.base_url = os.environ["SONAR_HOST_URL"].rstrip("/")
    return s


def sonar_get(session, path, **params):
    r = session.get(session.base_url + path, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def project_key(year, repo):
    safe = "".join(c if c.isalnum() or c in "-_.:" else "_" for c in repo)
    return f"cosc448_{year}_{safe}"


def read_selection():
    """Return [(org, repo, year)] from config/repo_selection.txt."""
    rows = []
    for line in SELECTION.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            org, repo = line.split("/", 1)
            rows.append((org, repo, ORGS[org]))
    return rows


def repo_dir(year, repo):
    return DATA / str(year) / repo
