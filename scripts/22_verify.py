"""Consistency checks on the detector outputs; writes results/detect/verification.md.

    scripts/22_verify.py [--db PATH] [--rescore]

--rescore re-runs the models on the first chunk of 3 random files and compares with the stored
chunk values (loads the models, so run it when nothing else is using the GPU).
"""
import argparse
import importlib.util
import sqlite3

import numpy as np
import pandas as pd

from common import RESULTS, ROOT, DATA

DETECT = RESULTS / "detect"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "detect" / "detect.sqlite"))
    ap.add_argument("--rescore", action="store_true")
    args = ap.parse_args()
    det = _load("file_detect", "20_file_detect.py")
    db = sqlite3.connect(args.db)
    out = ["# Verification", ""]

    inv = pd.read_csv(DETECT / "file_inventory.csv", keep_default_na=False)
    f = pd.read_csv(DETECT / "file_level.csv")
    repo = pd.read_csv(DETECT / "repo_level.csv")
    failed = pd.read_sql("SELECT * FROM failures", db)

    expected = det.repos_by_year()
    out += ["## Every repo present for every year", "", "| year | expected | in repo_level | with >=1 scored file |", "|---|---|---|---|"]
    ok = True
    for y, repos in expected.items():
        r = repo[repo.year == y]
        have = set(r.repo)
        scored = set(r[r.files_scored > 0].repo)
        ok &= have == set(repos)
        out.append(f"| {y} | {len(repos)} | {len(have)} | {len(scored)} |")
        for miss in sorted(set(repos) - scored):
            out.append(f"|  | no scored file: `{miss}` | | |")
    out.append(f"\nAll expected repos present: **{ok}**\n")

    inc = inv[inv.included == "yes"]
    out += ["## Row counts", "",
            f"- inventory candidates: {len(inv)}", f"- included in inventory: {len(inc)}",
            f"- recorded failures: {len(failed)}", f"- file_level rows: {len(f)}",
            f"- included minus failures: {len(inc) - len(failed)}",
            f"- **match: {len(f) == len(inc) - len(failed)}**", ""]

    key = ["year", "repo", "path"]
    out += ["## Duplicate keys", "", f"- file_level duplicates on (year, repo, path): {int(f.duplicated(key).sum())}",
            f"- file_level duplicates on (year, repo, path, content_hash): {int(f.duplicated(key + ['content_hash']).sum())}",
            f"- repo_level duplicates on (year, repo): {int(repo.duplicated(['year', 'repo']).sum())}", ""]

    nan = f.isna().mean().mul(100).round(2)
    out += ["## Null rate per file_level column (%)", "", "Detector columns and keys must be 0; Sonar columns are empty "
            "for files SonarQube did not analyse (no analyser for the language, or excluded from the scan).", "",
            "| column | % empty |", "|---|---|"]
    out += [f"| {c} | {v} |" for c, v in nan.items() if v > 0] or ["| (none) | 0 |"]
    det_cols = ["bino_score", "obs_logppl", "perf_logppl", "xppl", "droid_p_ai", "droid_logit_ai", "droid_label"]
    out += ["", f"Detector columns all complete: **{bool((nan[det_cols] == 0).all())}**; "
            f"all finite: **{bool(np.isfinite(f[det_cols[:-1]]).all().all())}**", ""]

    agg = f"SELECT year, repo, path, content_hash, bino_score, droid_p_ai FROM files"
    sample = pd.read_sql(agg, db).sample(min(3, len(f)), random_state=448)
    out += ["## Spot check: file value vs its chunk rows", "", "| file | chunks | stored bino_score | recomputed | stored droid_p_ai | recomputed |", "|---|---|---|---|---|---|"]
    scorer = det.Scorer() if args.rescore else None
    notes = []
    for _, r in sample.iterrows():
        k = (int(r.year), r.repo, r.path, r.content_hash)
        b = pd.read_sql("SELECT * FROM bino_chunks WHERE year=? AND repo=? AND path=? AND content_hash=? ORDER BY chunk", db, params=k)
        d = pd.read_sql("SELECT * FROM droid_chunks WHERE year=? AND repo=? AND path=? AND content_hash=? ORDER BY chunk", db, params=k)
        rb = np.average(b.score, weights=b.n_scored)
        rd = np.average(d.p_ai, weights=d.n_tokens)
        out.append(f"| {k[0]}/{k[1]}/{k[2]} | {len(b)}/{len(d)} | {r.bino_score:.6f} | {rb:.6f} | {r.droid_p_ai:.6f} | {rd:.6f} |")
        if scorer:
            text = det.BlobReader(DATA / str(k[0]) / k[1])
            t = text.read(k[3])
            text.close()
            fresh_b = scorer.bino(t)[0]
            fresh_d = scorer.droid_chunks(t)[0]
            notes.append(f"- `{k[2]}` chunk 0 rescored: bino {fresh_b['score']:.6f} (stored {b.score[0]:.6f}), "
                         f"droid p_ai {fresh_d['p_ai']:.6f} (stored {d.p_ai[0]:.6f})")
    if notes:
        out += ["", "Fresh re-run of the models on chunk 0:", ""] + notes
    (DETECT / "verification.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
