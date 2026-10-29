"""File-level AI-code detectors: Binoculars-style (Qwen2.5-Coder pair) and DroidDetect.

Every candidate source file of every repo (2022, 2026, 2025, 2024, 2023) is listed in
results/detect/file_inventory.csv with whether it is scored and why not. Included files are
split into chunks (<= 512 tokens, cut at line ends when possible), every chunk is scored by
both detectors, and the file value is the token-weighted mean of its chunks. Raw per-chunk
and per-file outputs go to a SQLite store (data/detect/detect.sqlite, git-ignored), so a rerun
skips finished files. No threshold is applied to the Binoculars score.

    scripts/20_file_detect.py --inventory          # write the inventory and print token totals
    scripts/20_file_detect.py --only 2022/database # one repo (year/repo), supervised run
    scripts/20_file_detect.py                      # everything, in order 2022, 2026, 2025, 2024, 2023
    scripts/20_file_detect.py --db PATH            # use another store (smoke tests)

The default mode supervises a worker process and restarts it after a hang (a file taking longer than
the hang guard) or a kill signal; the file that was in flight is recorded in the failures table.
"""
import argparse
import gc
import hashlib
import math
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, RESULTS, ROOT, git, read_selection  # noqa: E402
from ai_detect.units import GENERATED_MARK, TEST_PATH  # noqa: E402

import importlib.util  # noqa: E402


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OBSERVER = "Qwen/Qwen2.5-Coder-1.5B"
PERFORMER = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
DROID = "project-droid/DroidDetect-Large-Binary"
CHUNK_TOKENS = 512          # Binoculars chunk size in Qwen tokens
DROID_CONTENT_TOKENS = 510  # + [CLS] and [SEP] = the 512 DroidDetect is run at
MIN_TAIL = 32               # a last chunk shorter than this borrows tokens from the one before it
MIN_TOKENS = 8              # fewer Qwen tokens than this cannot be scored by Binoculars
HANG_SECONDS = 1800         # per-file hang guard (not a time cap on the run)
HANG_EXIT = 75              # exit code of the hang guard; the supervisor restarts on it and on signals
HANG_PER_CHUNK = 5          # seconds allowed per chunk before the guard applies on very large files

DETECT_DIR = RESULTS / "detect"
INVENTORY = DETECT_DIR / "file_inventory.csv"
DB_DEFAULT = ROOT / "data" / "detect" / "detect.sqlite"
YEAR_ORDER = [2022, 2026, 2025, 2024, 2023]

EXT_LANG = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".java": "java", ".c": "c", ".cc": "cpp", ".cpp": "cpp",
            ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".go": "go", ".php": "php", ".rb": "ruby",
            ".rs": "rust", ".kt": "kotlin", ".swift": "swift", ".m": "matlab", ".sql": "sql",
            ".html": "html", ".css": "css"}
# languages outside what DroidDetect / the Qwen coder pair are mainly trained and evaluated on
UNSUPPORTED = {"matlab", "sql", "html", "css"}

# 2022 / 2026 repos (see 03b_sonar_extra.py) and the other clones are all under data/repos/<year>/
EXTRA_REPOS = {2022: ["api-development-and-testing-project1-helpya-services-inc", "database",
                      "hot-desking-deploy", "matlab-to-python-application-translation-project2-nrc"],
               2026: ["capstone-project-team-11"]}


def repos_by_year():
    out = {y: [] for y in YEAR_ORDER}
    for _, repo, year in read_selection():
        out[year].append(repo)
    for y, repos in EXTRA_REPOS.items():
        out[y] = list(repos)
    return {y: sorted(out[y]) for y in YEAR_ORDER}


# ----------------------------------------------------------------------------- inventory

def _sonar_rules():
    scan = _load("sonar_scan", "03_sonar_scan.py")
    extra = _load("sonar_extra", "03b_sonar_extra.py")
    dirs = set(re.findall(r"\*\*/([^/*]+)/\*\*", scan.EXCLUSIONS))
    return dirs, scan.KEEP_BUILD, extra.VENDORED


DETECTOR_ONLY_DIRS = re.compile(r"(^|/)(vendor|bower_components|third_party)/")
# third-party library committed into a repo: a "/*! name vX.Y.Z" banner or a well-known library name + version
VENDORED_BANNER = re.compile(r"^\s*/\*!|\b(Bootstrap|jQuery|p5\.js|Font Awesome)\s+v?\d+\.\d+", re.I)
GENERATED_HTML = re.compile(r"doxygen|<meta name=\"generator\"|LCOV - code coverage report", re.I)
DECLARATION_OR_GENERATED = re.compile(
    r"\.min\.(js|css)$|\.d\.ts$|_pb2(_grpc)?\.py$|\.designer\.cs$|\.g\.dart$")


def exclusion_reason(repo, path, text, sonar_dirs, keep_build, vendored):
    """(reason or '', ...) in a fixed order: SonarQube's own exclusions first."""
    parts = path.split("/")[:-1]
    dirs = sonar_dirs - ({"build"} if repo in keep_build else set())
    for d in parts:
        if d in dirs:
            return f"sonar_exclusion:dir={d}"
    if path.endswith(".min.js"):
        return "sonar_exclusion:*.min.js"
    if repo in vendored and f"/{vendored[repo].strip('*').strip('/')}/" in f"/{path}":
        return "vendored_packages (excluded from the Sonar scan too)"
    if DETECTOR_ONLY_DIRS.search(path):
        return "vendored_dir (vendor/bower_components/third_party)"
    if DECLARATION_OR_GENERATED.search(path):
        return "generated_or_declaration_file"
    if "\0" in text:
        return "binary_nul_bytes"
    if GENERATED_MARK.search(text[:500]):
        return "generated_marker_in_header"
    if VENDORED_BANNER.search(text[:400]):
        return "vendored_library_banner"
    if path.endswith(".gcov.html") or GENERATED_HTML.search(text[:3000]):
        return "generated_report_html(gcov/doxygen/generator meta)"
    lines = text.splitlines() or [""]
    if sum(map(len, lines)) / len(lines) > 200:
        return "minified_or_data(avg_line_length>200)"
    if not any(l.strip() for l in lines):
        return "empty"
    return ""


def ls_tree(repo_path, sha):
    out = subprocess.run(["git", "-C", str(repo_path), "ls-tree", "-r", "-z", "-l", sha],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    rows = []
    for rec in out.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        _, typ, h, size = meta.split()
        if typ == "blob":
            rows.append((path, h, int(size) if size != "-" else 0))
    return rows


class BlobReader:
    """Reads blobs of one repo by hash through one `git cat-file --batch` process."""

    def __init__(self, repo_path):
        self.p = subprocess.Popen(["git", "-C", str(repo_path), "cat-file", "--batch"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, h):
        self.p.stdin.write(h.encode() + b"\n")
        self.p.stdin.flush()
        header = self.p.stdout.readline().split()
        if len(header) < 3:
            raise FileNotFoundError(h)
        data = self.p.stdout.read(int(header[2]))
        self.p.stdout.read(1)
        return data.decode("utf-8", errors="replace")

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def build_inventory(years_repos):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(OBSERVER)
    tok.model_max_length = 10 ** 9
    sonar_dirs, keep_build, vendored = _sonar_rules()
    rows = []
    for year, repo in years_repos:
        path = DATA / str(year) / repo
        sha = git(path, "rev-parse", "HEAD")
        cands = [(p, h, s) for p, h, s in ls_tree(path, sha)
                 if "." in p.rsplit("/", 1)[-1] and "." + p.rsplit(".", 1)[-1].lower() in EXT_LANG]
        reader = BlobReader(path)
        for p, h, size in cands:
            ext = "." + p.rsplit(".", 1)[-1].lower()
            text = reader.read(h)
            lines = text.splitlines()
            reason = exclusion_reason(repo, p, text, sonar_dirs, keep_build, vendored)
            ntok = ""
            if not reason:
                ntok = len(tok(text, add_special_tokens=False)["input_ids"])
                if ntok < MIN_TOKENS:
                    reason = f"too_short(<{MIN_TOKENS} tokens)"
            lang = EXT_LANG[ext]
            rows.append({
                "year": year, "repo": repo, "path": p, "sha": sha, "content_hash": h,
                "language": lang, "ext": ext, "bytes": size, "lines": len(lines),
                "sloc": sum(1 for l in lines if l.strip()), "qwen_tokens": ntok,
                "is_test": bool(TEST_PATH.search(p)),
                "detector_language_supported": "no" if lang in UNSUPPORTED else "yes",
                "included": "no" if reason else "yes", "reason": reason})
        reader.close()
        n_inc = sum(r["included"] == "yes" for r in rows if r["repo"] == repo and r["year"] == year)
        print(f"inventory {year}/{repo}: {len(cands)} candidates, {n_inc} included", flush=True)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- chunking

def split_tokens(text, tok, limit, add_special_tokens=False):
    """Token-aligned chunks of at most `limit` tokens: [(i, j, char_start, char_end)], ids.

    A chunk ends at the last line end in its final quarter when there is one, else exactly at the
    limit. A last chunk shorter than MIN_TAIL borrows tokens from the one before it."""
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    ids, offs = enc["input_ids"], enc["offset_mapping"]
    n = len(ids)
    bounds, i = [], 0
    while i < n:
        j = min(i + limit, n)
        if j < n:
            for k in range(j, i + int(limit * 0.75), -1):
                e = offs[k - 1][1]
                if text[e - 1:e] == "\n":
                    j = k
                    break
        bounds.append([i, j])
        i = j
    if len(bounds) > 1 and bounds[-1][1] - bounds[-1][0] < MIN_TAIL:
        shift = MIN_TAIL - (bounds[-1][1] - bounds[-1][0])
        bounds[-2][1] -= shift
        bounds[-1][0] -= shift
    return [(i, j, offs[i][0], offs[j - 1][1]) for i, j in bounds], ids


# ----------------------------------------------------------------------------- store

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  year INT, repo TEXT, path TEXT, content_hash TEXT, sha TEXT, language TEXT, ext TEXT,
  bytes INT, lines INT, sloc INT, is_test INT, detector_language_supported TEXT,
  qwen_tokens INT, bino_chunks INT, bino_tokens_scored INT,
  bino_score REAL, bino_score_min REAL, bino_score_max REAL,
  obs_logppl REAL, perf_logppl REAL, xppl REAL,
  droid_chunks INT, droid_tokens INT, droid_logit_human REAL, droid_logit_ai REAL,
  droid_p_ai REAL, droid_label TEXT, droid_ai_chunk_share REAL,
  device TEXT, dtype TEXT, observer TEXT, performer TEXT, droid_model TEXT,
  seconds REAL, scored_at TEXT,
  PRIMARY KEY (year, repo, path, content_hash));
CREATE TABLE IF NOT EXISTS bino_chunks (
  year INT, repo TEXT, path TEXT, content_hash TEXT, chunk INT, start_char INT, end_char INT,
  n_tokens INT, n_scored INT, obs_logppl REAL, perf_logppl REAL, xppl REAL, score REAL,
  PRIMARY KEY (year, repo, path, content_hash, chunk));
CREATE TABLE IF NOT EXISTS droid_chunks (
  year INT, repo TEXT, path TEXT, content_hash TEXT, chunk INT, start_char INT, end_char INT,
  n_tokens INT, logit_human REAL, logit_ai REAL, p_ai REAL, label TEXT,
  PRIMARY KEY (year, repo, path, content_hash, chunk));
CREATE TABLE IF NOT EXISTS failures (
  year INT, repo TEXT, path TEXT, content_hash TEXT, stage TEXT, error TEXT, attempts INT,
  last_at TEXT, PRIMARY KEY (year, repo, path, content_hash));
CREATE TABLE IF NOT EXISTS inflight (
  year INT, repo TEXT, path TEXT, content_hash TEXT, started REAL, note TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=60, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def record_failure(db, key, stage, error):
    old = db.execute("SELECT attempts FROM failures WHERE year=? AND repo=? AND path=? AND content_hash=?",
                     key).fetchone()
    db.execute("INSERT OR REPLACE INTO failures VALUES (?,?,?,?,?,?,?,?)",
               (*key, stage, error[:500], (old[0] if old else 0) + 1, now()))
    db.commit()


def recover_inflight(db):
    """A file still marked in flight means the previous worker died on it."""
    for year, repo, path, h, started, note in db.execute("SELECT * FROM inflight").fetchall():
        record_failure(db, (year, repo, path, h), "worker",
                       note or "worker process died while scoring this file (crash or kill)")
    db.execute("DELETE FROM inflight")
    db.commit()


# ----------------------------------------------------------------------------- scoring

class Scorer:
    def __init__(self):
        import torch
        from transformers import AutoTokenizer
        from ai_detect.device import pick_device, pick_dtype
        from ai_detect.supervised import DroidDetect
        from ai_detect.zero_shot import CausalLM
        self.torch = torch
        self.device = pick_device(torch)
        self.dtype = str(pick_dtype(torch, self.device)).replace("torch.", "")
        self.qtok = AutoTokenizer.from_pretrained(OBSERVER)
        self.qtok.model_max_length = 10 ** 9
        self.obs = CausalLM(name=OBSERVER, device=self.device)
        self.perf = CausalLM(name=PERFORMER, device=self.device)
        self.droid = DroidDetect(DROID, device=self.device)
        self.droid.tok.model_max_length = 10 ** 9

    def empty_cache(self):
        gc.collect()
        if self.device == "mps":
            self.torch.mps.empty_cache()

    def bino(self, text):
        from ai_detect.zero_shot import binoculars_components
        spans, ids = split_tokens(text, self.qtok, CHUNK_TOKENS)
        out = []
        for c, (i, j, cs, ce) in enumerate(spans):
            t = self.torch.tensor([ids[i:j]], device=self.device)
            lo, tgt = self.obs.logits(t)
            lp, _ = self.perf.logits(t)
            r = binoculars_components(lo, lp, tgt)
            if not all(math.isfinite(r[k]) for k in ("obs_logppl", "perf_logppl", "xppl", "score")):
                raise FloatingPointError(f"non-finite Binoculars values in chunk {c}: {r}")
            out.append({"chunk": c, "start_char": cs, "end_char": ce, "n_tokens": j - i, **r})
        return out

    def droid_chunks(self, text):
        spans, _ = split_tokens(text, self.droid.tok, DROID_CONTENT_TOKENS)
        out = []
        for c, (i, j, cs, ce) in enumerate(spans):
            logits, counts = self.droid.predict_logits([text[cs:ce]])
            lg = logits[0].astype(float)
            if not np.isfinite(lg).all():
                raise FloatingPointError(f"non-finite DroidDetect logits in chunk {c}")
            p = np.exp(lg - lg.max())
            p /= p.sum()
            out.append({"chunk": c, "start_char": cs, "end_char": ce, "n_tokens": counts[0],
                        "logit_human": lg[0], "logit_ai": lg[1], "p_ai": float(p[1]),
                        "label": "MACHINE_GENERATED" if p[1] >= 0.5 else "HUMAN_GENERATED"})
        return out


def wmean(rows, key, wkey):
    w = np.array([r[wkey] for r in rows], float)
    return float(np.average([r[key] for r in rows], weights=w))


def score_file(scorer, db, meta, text):
    key = (meta["year"], meta["repo"], meta["path"], meta["content_hash"])
    t0 = time.time()
    b = scorer.bino(text)
    d = scorer.droid_chunks(text)
    p_ai = wmean(d, "p_ai", "n_tokens")
    row = {
        "year": meta["year"], "repo": meta["repo"], "path": meta["path"],
        "content_hash": meta["content_hash"], "sha": meta["sha"], "language": meta["language"],
        "ext": meta["ext"], "bytes": meta["bytes"], "lines": meta["lines"], "sloc": meta["sloc"],
        "is_test": int(meta["is_test"]), "detector_language_supported": meta["detector_language_supported"],
        "qwen_tokens": meta["qwen_tokens"], "bino_chunks": len(b),
        "bino_tokens_scored": sum(r["n_scored"] for r in b),
        "bino_score": wmean(b, "score", "n_scored"), "bino_score_min": min(r["score"] for r in b),
        "bino_score_max": max(r["score"] for r in b),
        "obs_logppl": wmean(b, "obs_logppl", "n_scored"), "perf_logppl": wmean(b, "perf_logppl", "n_scored"),
        "xppl": wmean(b, "xppl", "n_scored"),
        "droid_chunks": len(d), "droid_tokens": sum(r["n_tokens"] for r in d),
        "droid_logit_human": wmean(d, "logit_human", "n_tokens"), "droid_logit_ai": wmean(d, "logit_ai", "n_tokens"),
        "droid_p_ai": p_ai, "droid_label": "MACHINE_GENERATED" if p_ai >= 0.5 else "HUMAN_GENERATED",
        "droid_ai_chunk_share": float(np.mean([r["label"] == "MACHINE_GENERATED" for r in d])),
        "device": scorer.device, "dtype": scorer.dtype, "observer": OBSERVER, "performer": PERFORMER,
        "droid_model": DROID, "seconds": round(time.time() - t0, 2), "scored_at": now()}
    with db:  # one transaction per file: chunks and file row appear together
        db.executemany("INSERT OR REPLACE INTO bino_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       [(*key, r["chunk"], r["start_char"], r["end_char"], r["n_tokens"], r["n_scored"],
                         r["obs_logppl"], r["perf_logppl"], r["xppl"], r["score"]) for r in b])
        db.executemany("INSERT OR REPLACE INTO droid_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       [(*key, r["chunk"], r["start_char"], r["end_char"], r["n_tokens"], r["logit_human"],
                         r["logit_ai"], r["p_ai"], r["label"]) for r in d])
        cols = list(row)
        db.execute(f"INSERT OR REPLACE INTO files ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                   list(row.values()))
        db.execute("DELETE FROM failures WHERE year=? AND repo=? AND path=? AND content_hash=?", key)
    return row


# ----------------------------------------------------------------------------- run

def write_progress(db, inv, scope, t_start, tokens_at_start, current=None):
    done_keys = {tuple(r) for r in db.execute("SELECT year, repo, path, content_hash FROM files")}
    fail_keys = {tuple(r[:4]) for r in db.execute("SELECT year, repo, path, content_hash FROM failures")}
    inc = inv[inv.included == "yes"]
    keys = list(zip(inc.year, inc.repo, inc.path, inc.content_hash))
    inc = inc.assign(done=[k in done_keys for k in keys], failed=[k in fail_keys for k in keys])
    repos_total = len(scope)
    settled = (inc.done | inc.failed).groupby([inc.year, inc.repo]).all()
    repos_done = sum(bool(settled.get(yr, True)) for yr in scope)
    tok_total = int(inc.qwen_tokens.sum())
    tok_done = int(inc[inc.done].qwen_tokens.sum())
    elapsed = time.time() - t_start
    rate = (tok_done - tokens_at_start) / elapsed if elapsed > 0 and tok_done > tokens_at_start else 0
    remaining = (tok_total - tok_done - int(inc[inc.failed].qwen_tokens.sum())) / rate if rate else float("nan")
    text = f"""# Detector run progress

Updated {now()}{f' - working on {current}' if current else ''}

| | |
|---|---|
| Repos done | {repos_done} / {repos_total} |
| Files done | {int(inc.done.sum())} / {len(inc)} |
| Files failed (recorded) | {int(inc.failed.sum())} |
| Qwen tokens done | {tok_done:,} / {tok_total:,} |
| Elapsed this session | {elapsed / 3600:.2f} h |
| Estimated remaining | {remaining / 3600:.2f} h (at {rate:,.0f} tokens/s this session) |
"""
    (DETECT_DIR / "PROGRESS.md").write_text(text)
    print(text.replace("\n\n", "\n"), flush=True)


def watchdog(db_path, state):
    """If one file runs past its guard, mark it and kill the worker; the supervisor restarts it."""
    db = sqlite3.connect(db_path, timeout=60)
    while True:
        time.sleep(15)
        cur = state.get("current")
        if cur and time.time() - cur["start"] > cur["limit"]:
            db.execute("UPDATE inflight SET note=?", (f"hang guard: over {int(cur['limit'])}s on this file",))
            db.commit()
            print(f"HANG GUARD: {cur['key']} over {cur['limit']}s, restarting worker", flush=True)
            os._exit(HANG_EXIT)


def worker(args):
    DETECT_DIR.mkdir(parents=True, exist_ok=True)
    if not INVENTORY.exists():
        raise SystemExit("run --inventory first")
    inv = pd.read_csv(INVENTORY, keep_default_na=False)
    inv["is_test"] = inv.is_test.astype(str) == "True"
    inv["qwen_tokens"] = pd.to_numeric(inv.qwen_tokens, errors="coerce").fillna(0).astype(int)
    db_path = Path(args.db)
    db = open_db(db_path)
    recover_inflight(db)
    ry = repos_by_year()
    scope = [(y, r) for y in YEAR_ORDER for r in ry[y]]
    if args.only:
        y, r = args.only.split("/", 1)
        scope = [(int(y), r)]
    wanted = set(scope)
    inv = inv[[(y, r) in wanted for y, r in zip(inv.year, inv.repo)]]
    scorer = Scorer()
    state = {}
    threading.Thread(target=watchdog, args=(db_path, state), daemon=True).start()
    t_start = time.time()
    done_tok0 = int(inv[inv.included == "yes"].merge(
        pd.read_sql("SELECT year, repo, path, content_hash FROM files", db),
        on=["year", "repo", "path", "content_hash"]).qwen_tokens.sum())

    def run_pass(retry):
        for year, repo in scope:
            sub = inv[(inv.year == year) & (inv.repo == repo) & (inv.included == "yes")]
            done = {tuple(r) for r in db.execute(
                "SELECT path, content_hash FROM files WHERE year=? AND repo=?", (year, repo))}
            failed = {tuple(r[:2]): r[2] for r in db.execute(
                "SELECT path, content_hash, attempts FROM failures WHERE year=? AND repo=?", (year, repo))}
            todo = []
            for m in sub.to_dict("records"):
                k = (m["path"], m["content_hash"])
                if k in done:
                    continue
                if retry and k in failed and failed[k] < 2:
                    todo.append(m)
                elif not retry and k not in failed:
                    todo.append(m)
            if not todo:
                continue
            reader = BlobReader(DATA / str(year) / repo)
            for n, m in enumerate(todo, 1):
                key = (m["year"], m["repo"], m["path"], m["content_hash"])
                limit = max(HANG_SECONDS, HANG_PER_CHUNK * (m["qwen_tokens"] / CHUNK_TOKENS))
                db.execute("DELETE FROM inflight")
                db.execute("INSERT INTO inflight VALUES (?,?,?,?,?,NULL)", (*key, time.time()))
                db.commit()
                state["current"] = {"key": key, "start": time.time(), "limit": limit}
                try:
                    row = score_file(scorer, db, m, reader.read(m["content_hash"]))
                    if n % 25 == 0 or n == len(todo):
                        print(f"{year}/{repo} {n}/{len(todo)} {m['path']} {row['seconds']}s", flush=True)
                except Exception as e:  # recorded, never dropped
                    record_failure(db, key, "retry" if retry else "score", f"{type(e).__name__}: {e}")
                    print(f"FAILED {key[:3]}: {type(e).__name__}: {e}", flush=True)
                    scorer.empty_cache()
                finally:
                    state["current"] = None
                    db.execute("DELETE FROM inflight")
                    db.commit()
            reader.close()
            scorer.empty_cache()
            write_progress(db, inv, scope, t_start, done_tok0, current=f"{year}/{repo} finished")

    run_pass(retry=False)
    run_pass(retry=True)
    write_progress(db, inv, scope, t_start, done_tok0)
    export_failed(db, inv)


def export_failed(db, inv):
    df = pd.read_sql("SELECT * FROM failures ORDER BY year, repo, path", db)
    df.to_csv(DETECT_DIR / "failed.csv", index=False)
    print(f"failed.csv: {len(df)} file(s)", flush=True)


def supervise(args):
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", "--db", args.db]
    if args.only:
        cmd += ["--only", args.only]
    for restart in range(100):
        rc = subprocess.run(cmd).returncode
        if rc == 0:
            return
        if rc > 0 and rc != HANG_EXIT:  # a config error or an uncaught exception would only repeat
            raise SystemExit(f"worker exited with {rc}; not restarting")
        print(f"worker exited with {rc}; restart {restart + 1}", flush=True)
        time.sleep(5)
    raise SystemExit("too many worker restarts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", action="store_true", help="only (re)build file_inventory.csv")
    ap.add_argument("--only", help="year/repo")
    ap.add_argument("--db", default=str(DB_DEFAULT))
    ap.add_argument("--worker", action="store_true", help="internal: scoring process")
    args = ap.parse_args()
    if args.inventory:
        ry = repos_by_year()
        todo = [(y, r) for y in YEAR_ORDER for r in ry[y]]
        df = build_inventory(todo)
        DETECT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(INVENTORY, index=False)
        inc = df[df.included == "yes"]
        print(f"{len(df)} candidate files, {len(inc)} included, {int(inc.qwen_tokens.astype(int).sum()):,} Qwen tokens")
        return
    if args.worker:
        worker(args)
    else:
        supervise(args)


if __name__ == "__main__":
    main()
