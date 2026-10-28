"""Export per-file SonarQube measures for every year (2022-2026) to results/detect/sonar_file_measures.csv.

One row per file the server analysed: the component-tree measures (the API allows 15 metric
keys per call, so two calls are merged) plus counts of open issues for dead-code rules:

  sq_dead_unused        unused variables/params/imports/assignments/private members
  sq_dead_commented     commented-out code
  sq_dead_unreachable   unreachable or never-executed code
  sq_dead_total         sum of the three

Rule keys are listed in DEAD_RULES and in results/detect/DATA_DICTIONARY.md.
    scripts/04b_sonar_file_measures.py
"""
import csv

import pandas as pd

from common import DOCS, RESULTS, sonar_get, sonar_session

PREFIXES = ["python", "javascript", "typescript", "java", "php", "css", "kotlin", "ruby", "go", "Web"]
DEAD_RULES = {
    "unused": ["S1481", "S1172", "S1854", "S1128", "S1068", "S1144", "S5603", "S3985", "S4487",
               "S1065", "S2326"],
    "commented": ["S125", "AvoidCommentedOutCodeCheck"],
    "unreachable": ["S1763", "S2583"],
}
METRICS = [
    "ncloc", "lines", "statements", "functions", "classes", "comment_lines", "comment_lines_density",
    "complexity", "cognitive_complexity", "duplicated_lines", "duplicated_lines_density",
    "duplicated_blocks", "bugs", "vulnerabilities", "code_smells", "security_hotspots", "violations",
    "sqale_index", "sqale_debt_ratio", "sqale_rating", "reliability_rating", "security_rating",
    "software_quality_maintainability_rating", "software_quality_maintainability_issues",
    "software_quality_reliability_issues", "software_quality_security_issues",
    "software_quality_maintainability_debt_ratio",
]


def rule_keys(names):
    return ",".join(f"{p}:{n}" for p in PREFIXES for n in names)


def tree(session, project, keys):
    comps, page = [], 1
    while True:
        data = sonar_get(session, "/api/measures/component_tree", component=project,
                         metricKeys=",".join(keys), qualifiers="FIL,UTS", ps=500, p=page)
        comps += data["components"]
        if len(comps) >= data["paging"]["total"] or not data["components"]:
            return comps
        page += 1


def dead_counts(session, project, names):
    """{file component key: open issue count} for the given rules."""
    counts, page = {}, 1
    while True:
        data = sonar_get(session, "/api/issues/search", componentKeys=project, ps=500, p=page,
                         rules=rule_keys(names), issueStatuses="OPEN,CONFIRMED")
        for i in data["issues"]:
            counts[i["component"]] = counts.get(i["component"], 0) + 1
        total = data["paging"]["total"]
        if total > 10000:
            print(f"WARNING {project}: {total} dead-code issues, API caps at 10000", flush=True)
        if page * 500 >= min(total, 10000) or not data["issues"]:
            return counts
        page += 1


def main():
    session = sonar_session()
    with open(DOCS / "sonarqube_metrics_available.csv") as f:
        avail = {r["key"] for r in csv.DictReader(f)}
    keys = [k for k in METRICS if k in avail]
    projects = pd.concat([pd.read_csv(RESULTS / "sonar_scan_status.csv", dtype=str),
                          pd.read_csv(RESULTS / "sonar_scan_status_2022_2026.csv", dtype=str)])
    projects = projects[projects.status == "ok"]
    rows = []
    for _, p in projects.iterrows():
        by_file = {}
        for i in range(0, len(keys), 15):
            for c in tree(session, p.project_key, keys[i:i + 15]):
                row = by_file.setdefault(c["key"], {
                    "year": int(p.cohort_year), "repo": p.repo, "project_key": p.project_key,
                    "path": c.get("path"), "sq_language": c.get("language"),
                    "sq_qualifier": c["qualifier"]})
                for m in c["measures"]:
                    row["sq_" + m["metric"]] = m.get("value")
        dead = {cat: dead_counts(session, p.project_key, names) for cat, names in DEAD_RULES.items()}
        for ck, row in by_file.items():
            for cat in DEAD_RULES:
                row[f"sq_dead_{cat}"] = dead[cat].get(ck, 0)
            row["sq_dead_total"] = sum(row[f"sq_dead_{cat}"] for cat in DEAD_RULES)
        rows += by_file.values()
        print(f"{p.project_key}: {len(by_file)} files", flush=True)
    df = pd.DataFrame(rows)
    out = RESULTS / "detect" / "sonar_file_measures.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")


if __name__ == "__main__":
    main()
