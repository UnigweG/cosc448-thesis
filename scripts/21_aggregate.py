"""Build the file-level, repo-level and manual-check outputs from the detector store.

    scripts/21_aggregate.py [--db PATH] [--out DIR]

Writes (default DIR = results/detect):
  file_level.csv, file_level_<year>.csv   one row per scored file: detectors + inventory + SonarQube per-file measures
  repo_level.csv, repo_level_<year>.csv   derived from the file-level table only (never scored separately)
  DATA_DICTIONARY.md                      every column of both tables
  manual_kit/                             <year>/<repo>/file_N.txt + manual_kit.csv for ZeroGPT / GPTZero (by hand)
  chunks/chunk_*.csv.gz                   raw per-chunk outputs (large, git-ignored)
"""
import argparse
import importlib.util
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from common import DATA, RESULTS, ROOT


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KIT_FILES, KIT_CHARS = 5, 4500
BINO_METRICS = ["bino_score", "obs_logppl", "perf_logppl", "xppl"]
DROID_METRICS = ["droid_p_ai", "droid_logit_ai"]
# Sonar counts: a file the analyser read but that has no issue of a kind has no measure; that is 0
SQ_COUNTS = ["sq_bugs", "sq_vulnerabilities", "sq_code_smells", "sq_security_hotspots", "sq_violations",
             "sq_sqale_index", "sq_duplicated_lines", "sq_duplicated_blocks",
             "sq_software_quality_maintainability_issues", "sq_software_quality_reliability_issues",
             "sq_software_quality_security_issues"]

FILE_DOC = {
    "year": "Cohort year: 2022 = pre-AI baseline, 2023-2025 = AI years, 2026 = the user's capstone.",
    "repo": "Repository (directory under data/repos/<year>/).",
    "path": "File path inside the repo at the scanned commit.",
    "content_hash": "Git blob SHA of the file content (with year/repo/path it is the key).",
    "sha": "Commit (HEAD) the repo was scanned at.",
    "language": "Language from the file extension (.m is read as MATLAB).",
    "ext": "Lower-case file extension.",
    "bytes": "Size in bytes (git blob size).",
    "lines": "Number of lines.",
    "sloc": "Non-blank lines (includes comment lines; differs from SonarQube ncloc).",
    "is_test": "1 if the path looks like a test file (tests/, test_*, *_test.*, *.test.*, *.spec.*).",
    "detector_language_supported": "yes/no. 'no' = MATLAB, SQL, HTML, CSS: probably outside the detectors' training data; scored anyway.",
    "qwen_tokens": "Tokens of the whole file under the Qwen2.5-Coder tokenizer.",
    "bino_chunks": "Number of Binoculars chunks (<= 512 Qwen tokens each, cut at line ends where possible).",
    "bino_tokens_scored": "Tokens that had a prediction (chunk tokens minus the first token of each chunk); the Binoculars weights.",
    "bino_score": "Binoculars statistic = performer log-perplexity / cross-perplexity, token-weighted mean over chunks. LOWER = more AI-like (original orientation). No calibrated threshold exists for this Qwen pair.",
    "bino_score_min": "Lowest chunk Binoculars score in the file.",
    "bino_score_max": "Highest chunk Binoculars score in the file.",
    "obs_logppl": "Observer (Qwen2.5-Coder-1.5B) log-perplexity, nats/token, token-weighted mean over chunks.",
    "perf_logppl": "Performer (Qwen2.5-Coder-1.5B-Instruct) log-perplexity, nats/token, token-weighted mean over chunks.",
    "xppl": "Cross-perplexity (observer next-token distribution scored by the performer), nats/token, token-weighted mean.",
    "droid_chunks": "Number of DroidDetect chunks (<= 510 content tokens + [CLS]/[SEP] = 512).",
    "droid_tokens": "DroidDetect tokens scored (specials included); the DroidDetect weights.",
    "droid_logit_human": "DroidDetect class-0 (HUMAN_GENERATED) logit, token-weighted mean over chunks.",
    "droid_logit_ai": "DroidDetect class-1 (MACHINE_GENERATED) logit, token-weighted mean over chunks.",
    "droid_p_ai": "DroidDetect probability(AI) (softmax of the class logits per chunk), token-weighted mean over chunks.",
    "droid_label": "DroidDetect's own binary label for the file: MACHINE_GENERATED if droid_p_ai >= 0.5 else HUMAN_GENERATED.",
    "droid_ai_chunk_share": "Share of the file's chunks that DroidDetect labels MACHINE_GENERATED.",
    "device": "Torch device used.",
    "dtype": "Model dtype used (float16 on mps).",
    "observer": "Observer model id.",
    "performer": "Performer model id.",
    "droid_model": "DroidDetect checkpoint id.",
    "seconds": "Seconds spent scoring the file.",
    "scored_at": "UTC timestamp when the file was scored.",
    "bino_score_percentile": "Percentile (0-100) of bino_score among all scored files of the run. Low = more AI-like. A rank, not a threshold.",
    "droid_p_ai_percentile": "Percentile (0-100) of droid_p_ai among all scored files of the run. High = more AI-like.",
    "sonar_analysed": "yes if SonarQube reported measures for this file (it has a language analyser), else no.",
    "sq_language": "SonarQube's language key for the file (empty when no analyser).",
    "sq_qualifier": "SonarQube component qualifier: FIL = source file, UTS = test file.",
    "sq_ncloc": "SonarQube lines of code (non-comment, non-blank).",
    "sq_lines": "SonarQube total lines.",
    "sq_statements": "SonarQube statements.",
    "sq_functions": "SonarQube functions.",
    "sq_classes": "SonarQube classes.",
    "sq_comment_lines": "SonarQube comment lines.",
    "sq_comment_lines_density": "SonarQube comment lines / (ncloc + comment lines) * 100.",
    "sq_complexity": "SonarQube cyclomatic complexity.",
    "sq_cognitive_complexity": "SonarQube cognitive complexity.",
    "sq_duplicated_lines": "SonarQube duplicated lines.",
    "sq_duplicated_lines_density": "SonarQube duplicated lines in % of lines.",
    "sq_duplicated_blocks": "SonarQube duplicated blocks.",
    "sq_bugs": "SonarQube bugs (reliability issues); 0 for an analysed file with none.",
    "sq_vulnerabilities": "SonarQube vulnerabilities; 0 for an analysed file with none.",
    "sq_code_smells": "SonarQube code smells (maintainability issues); 0 for an analysed file with none.",
    "sq_security_hotspots": "SonarQube security hotspots; 0 for an analysed file with none.",
    "sq_violations": "SonarQube open issues of all kinds; 0 for an analysed file with none.",
    "sq_sqale_index": "SonarQube technical debt in minutes.",
    "sq_sqale_debt_ratio": "SonarQube technical debt ratio (%).",
    "sq_sqale_rating": "SonarQube maintainability rating, 1 (A) to 5 (E).",
    "sq_reliability_rating": "SonarQube reliability rating, 1 (A) to 5 (E).",
    "sq_security_rating": "SonarQube security rating, 1 (A) to 5 (E).",
    "sq_software_quality_maintainability_rating": "SonarQube maintainability rating (new-model key), 1 (A) to 5 (E).",
    "sq_software_quality_maintainability_issues": "SonarQube maintainability issues (new model).",
    "sq_software_quality_reliability_issues": "SonarQube reliability issues (new model).",
    "sq_software_quality_security_issues": "SonarQube security issues (new model).",
    "sq_software_quality_maintainability_debt_ratio": "SonarQube maintainability debt ratio (new model).",
    "sq_dead_unused": "Open SonarQube issues for unused code: rules S1481, S1172, S1854, S1128, S1068, S1144, S5603, S3985, S4487, S1065, S2326 (any language prefix).",
    "sq_dead_commented": "Open SonarQube issues for commented-out code: S125, Web:AvoidCommentedOutCodeCheck.",
    "sq_dead_unreachable": "Open SonarQube issues for unreachable code: S1763, S2583.",
    "sq_dead_total": "sq_dead_unused + sq_dead_commented + sq_dead_unreachable.",
}
STAT_DOC = {"wmean": "token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns)",
            "median": "median over files", "std": "standard deviation over files (unweighted, ddof=1)",
            "min": "minimum over files", "max": "maximum over files"}
REPO_DOC = {
    "year": "Cohort year.", "repo": "Repository.",
    "files_candidate": "Source-extension files tracked at HEAD (file_inventory.csv rows).",
    "files_excluded": "Candidate files not scored (vendored, generated, SonarQube-excluded dirs, empty, too short...), see file_inventory.csv.",
    "files_included": "Candidate files that were meant to be scored.",
    "files_scored": "Included files with a result.",
    "files_failed": "Included files without a result (listed in failed.csv with the error).",
    "sloc_scored": "Sum of sloc over scored files.",
    "tokens_scored": "Sum of qwen_tokens over scored files.",
    "droid_ai_file_share": "Share of scored files that DroidDetect labels MACHINE_GENERATED (droid_p_ai >= 0.5).",
    "droid_ai_sloc_share": "Share of scored sloc in files labelled MACHINE_GENERATED.",
    "droid_ai_token_share": "Share of scored Qwen tokens in files labelled MACHINE_GENERATED.",
    "unsupported_language_file_share": "Share of scored files in MATLAB/SQL/HTML/CSS (outside the detectors' training languages).",
    "bino_score_pct_below_p10": "Share of scored files whose bino_score is in the lowest 10% of the whole run (a rank, not a threshold).",
    "sonar_status": "Scan status from results/sonar_scan_status*.csv.",
    "sonar_notes": "Notes from the scan: languages SonarQube cannot analyse, exclusions.",
}


def percentile(s):
    return (s.rank(method="average") - 1) / max(len(s) - 1, 1) * 100


def wavg(g, col, wcol):
    d = g[[col, wcol]].dropna()
    return float(np.average(d[col], weights=d[wcol])) if len(d) and d[wcol].sum() > 0 else np.nan


def repo_table(f, inv, sonar_repo):
    rows = []
    keys = inv[["year", "repo"]].drop_duplicates()
    for year, repo in zip(keys.year, keys.repo):
        i = inv[(inv.year == year) & (inv.repo == repo)]
        g = f[(f.year == year) & (f.repo == repo)]
        inc = i[i.included == "yes"]
        r = {"year": year, "repo": repo, "files_candidate": len(i), "files_excluded": int((i.included == "no").sum()),
             "files_included": len(inc), "files_scored": len(g), "files_failed": len(inc) - len(g),
             "sloc_scored": int(g.sloc.sum()), "tokens_scored": int(g.qwen_tokens.sum())}
        for m in BINO_METRICS + DROID_METRICS:
            w = "bino_tokens_scored" if m in BINO_METRICS else "droid_tokens"
            r[f"{m}_wmean"] = wavg(g, m, w)
            r[f"{m}_median"] = g[m].median() if len(g) else np.nan
            r[f"{m}_std"] = g[m].std() if len(g) > 1 else np.nan
            r[f"{m}_min"] = g[m].min() if len(g) else np.nan
            r[f"{m}_max"] = g[m].max() if len(g) else np.nan
        flag = g.droid_label == "MACHINE_GENERATED"
        r["droid_ai_file_share"] = flag.mean() if len(g) else np.nan
        r["droid_ai_sloc_share"] = g.sloc[flag].sum() / g.sloc.sum() if g.sloc.sum() else np.nan
        r["droid_ai_token_share"] = g.qwen_tokens[flag].sum() / g.qwen_tokens.sum() if g.qwen_tokens.sum() else np.nan
        r["unsupported_language_file_share"] = (g.detector_language_supported == "no").mean() if len(g) else np.nan
        r["bino_score_pct_below_p10"] = (g.bino_score_percentile < 10).mean() if len(g) else np.nan
        rows.append(r)
    out = pd.DataFrame(rows).merge(sonar_repo, on=["year", "repo"], how="left")
    return out.sort_values(["year", "repo"]).reset_index(drop=True)


def sonar_repo_table():
    parts = [pd.read_csv(RESULTS / n) for n in ("sonarqube_metrics.csv", "sonar_2022.csv", "sonar_2026.csv")]
    s = pd.concat(parts, ignore_index=True).rename(columns={"cohort_year": "year"})
    status = pd.concat([pd.read_csv(RESULTS / "sonar_scan_status.csv"),
                        pd.read_csv(RESULTS / "sonar_scan_status_2022_2026.csv")])
    status = status.rename(columns={"cohort_year": "year", "status": "sonar_status", "notes": "sonar_notes"})
    s = s.drop(columns=["org", "project_key"]).merge(status[["year", "repo", "sonar_status", "sonar_notes"]],
                                                       on=["year", "repo"], how="left")
    return s


def write_kit(f, out):
    from importlib import import_module  # noqa: F401
    det = _load("file_detect", "20_file_detect.py")
    kit_dir = out / "manual_kit"
    rows = []
    for (year, repo), g in f.groupby(["year", "repo"]):
        top = g.sort_values(["sloc", "path"], ascending=[False, True]).head(KIT_FILES)
        reader = det.BlobReader(DATA / str(year) / repo)
        for n, (_, r) in enumerate(top.iterrows(), 1):
            text = reader.read(r.content_hash)
            cut = text
            if len(text) > KIT_CHARS:
                cut = text[:KIT_CHARS]
                nl = cut.rfind("\n")
                cut = cut[:nl] if nl > 0 else cut
            rel = Path(str(year)) / repo / f"file_{n}.txt"
            (kit_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (kit_dir / rel).write_text(cut)
            rows.append({"year": year, "repo": repo, "file_n": n, "path": r.path, "language": r.language,
                         "sloc": r.sloc, "chars_full": len(text), "chars_in_kit": len(cut),
                         "truncated": "yes" if len(cut) < len(text) else "no", "kit_file": str(rel),
                         "zerogpt_ai_percent": "", "zerogpt_label": "", "gptzero_ai_probability": "",
                         "gptzero_label": "", "notes": ""})
        reader.close()
    pd.DataFrame(rows).to_csv(kit_dir / "manual_kit.csv", index=False)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "detect" / "detect.sqlite"))
    ap.add_argument("--out", default=str(RESULTS / "detect"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.db)

    f = pd.read_sql("SELECT * FROM files", db)
    inv = pd.read_csv(RESULTS / "detect" / "file_inventory.csv", keep_default_na=False)
    f["bino_score_percentile"] = percentile(f.bino_score)
    f["droid_p_ai_percentile"] = percentile(f.droid_p_ai)
    sq = pd.read_csv(RESULTS / "detect" / "sonar_file_measures.csv").drop(columns=["project_key"])
    f = f.merge(sq, on=["year", "repo", "path"], how="left")
    f["sonar_analysed"] = np.where(f.sq_language.notna() & f.sq_ncloc.notna(), "yes", "no")
    for c in SQ_COUNTS:
        if c in f:
            f.loc[f.sonar_analysed == "yes", c] = f.loc[f.sonar_analysed == "yes", c].fillna(0)
    f = f.sort_values(["year", "repo", "path"]).reset_index(drop=True)
    f.to_csv(out / "file_level.csv", index=False)
    for y, g in f.groupby("year"):
        g.to_csv(out / f"file_level_{y}.csv", index=False)

    repo = repo_table(f, inv, sonar_repo_table())
    repo.to_csv(out / "repo_level.csv", index=False)
    for y, g in repo.groupby("year"):
        g.to_csv(out / f"repo_level_{y}.csv", index=False)

    # data dictionary: every column must be described, so the doc cannot drift from the CSVs
    stat_cols = {f"{m}_{s}": f"{m} - {d}" for m in BINO_METRICS + DROID_METRICS for s, d in STAT_DOC.items()}
    miss_f = [c for c in f.columns if c not in FILE_DOC]
    miss_r = [c for c in repo.columns if c not in REPO_DOC and c not in stat_cols and not c.startswith("sq_")]
    if miss_f or miss_r:
        raise SystemExit(f"undocumented columns: file={miss_f} repo={miss_r}")
    lines = ["# Data dictionary", "", "Detector outputs are raw: no calibrated threshold exists for the Qwen-based "
             "Binoculars score. `*_percentile` columns are ranks within this run only.", "",
             "## file_level.csv (one row per scored file)", "", "| column | meaning |", "|---|---|"]
    lines += [f"| `{c}` | {FILE_DOC[c]} |" for c in f.columns]
    lines += ["", "## repo_level.csv (derived from file_level.csv)", "", "| column | meaning |", "|---|---|"]
    for c in repo.columns:
        if c in REPO_DOC:
            d = REPO_DOC[c]
        elif c in stat_cols:
            d = stat_cols[c]
        else:
            d = (f"Repo-level SonarQube measure `{c[3:]}` for the whole repo (same columns as results/sonarqube_metrics.csv; "
                 "see docs/metrics_mapping.md). Empty where the metric does not apply.")
        lines.append(f"| `{c}` | {d} |")
    (out / "DATA_DICTIONARY.md").write_text("\n".join(lines) + "\n")

    n = write_kit(f, out)
    chunks = out / "chunks"
    chunks.mkdir(exist_ok=True)
    for t in ("bino_chunks", "droid_chunks"):
        pd.read_sql(f"SELECT * FROM {t}", db).to_csv(chunks / f"{t}.csv.gz", index=False)
    print(f"file_level {len(f)} rows, repo_level {len(repo)} rows, manual kit {n} files")


if __name__ == "__main__":
    main()
