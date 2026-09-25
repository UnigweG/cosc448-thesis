"""Shared helpers: project paths, .env loading, git and a SonarQube API session."""
import os
import subprocess
from pathlib import Path

import pandas as pd
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


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def select(items, only):
    """Items matching --only (repo name or org/repo); stop if there are none."""
    items = [i for i in items if only in (i[1], f"{i[0]}/{i[1]}")]
    if not items:
        raise SystemExit(f"{only} is not in config/repo_selection.txt")
    return items


# metric columns that can hold fractions; every other sq_/py_ metric is a count or a rating
FRACTIONAL = ("_density", "_ratio", "_avg", "_pct", "_pct_pdf", "_per_function",
              "_per_kloc", "_score", "_score_excl_fatal")


def counts_as_int(df):
    """Write counts and ratings as 7298 rather than 7298.0 (pandas turns an integer
    column with any NA into floats). Columns with non-numeric or fractional values
    are left as they are."""
    for c in df.columns:
        if not (c.startswith(("sq_", "py_")) or c == "python_file_count") or c.endswith(FRACTIONAL):
            continue
        v = pd.to_numeric(df[c], errors="coerce")
        if v.notna().sum() == df[c].notna().sum() and (v.dropna() % 1 == 0).all():
            df[c] = v.astype("Int64")
    return df
