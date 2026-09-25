"""Export SonarQube measures for every selected repo to results/sonarqube_metrics.csv."""
import csv

import pandas as pd

from common import (DOCS, RESULTS, counts_as_int, project_key, read_selection, sonar_get,
                    sonar_session)

# keys marked usable in docs/metrics_mapping.md, plus ncloc and comment_lines for the
# derived PDF comment %
KEYS = [
    "ncloc", "lines", "statements", "functions", "classes", "files",
    "comment_lines", "comment_lines_density",
    "complexity", "cognitive_complexity",
    "duplicated_lines_density", "duplicated_blocks",
    "bugs", "vulnerabilities", "security_hotspots", "code_smells", "violations",
    "sqale_index", "sqale_debt_ratio", "sqale_rating", "reliability_rating", "security_rating",
    "software_quality_maintainability_issues", "software_quality_reliability_issues",
    "software_quality_security_issues",
    "software_quality_blocker_issues", "software_quality_high_issues",
    "software_quality_medium_issues", "software_quality_low_issues",
    "software_quality_info_issues",
    "software_quality_maintainability_rating", "software_quality_maintainability_debt_ratio",
    "ncloc_language_distribution",
]
FILE_KEYS = ["ncloc", "comment_lines", "complexity", "functions", "classes"]


def available_keys():
    with open(DOCS / "sonarqube_metrics_available.csv") as f:
        return {row["key"] for row in csv.DictReader(f)}


def file_measures(session, key):
    comps, page = [], 1
    while True:
        data = sonar_get(session, "/api/measures/component_tree", component=key,
                         metricKeys=",".join(FILE_KEYS), qualifiers="FIL,UTS", ps=500, p=page)
        comps += data["components"]
        if len(comps) >= data["paging"]["total"] or not data["components"]:
            return comps
        page += 1


def python_totals(comps):
    out = {"sq_py_files": 0, "sq_py_file_complexity_max": None}
    for k in FILE_KEYS:
        out[f"sq_py_{k}"] = 0
    for c in comps:
        if c.get("language") != "py":
            continue
        out["sq_py_files"] += 1
        vals = {m["metric"]: float(m["value"]) for m in c["measures"] if "value" in m}
        for k in FILE_KEYS:
            out[f"sq_py_{k}"] += vals.get(k, 0)
        cx = vals.get("complexity")
        if cx is not None:
            cur = out["sq_py_file_complexity_max"]
            out["sq_py_file_complexity_max"] = cx if cur is None else max(cur, cx)
    if out["sq_py_files"] == 0:
        return {k: None for k in out} | {"sq_py_files": 0}
    return out


def issue_facets(session, key):
    data = sonar_get(session, "/api/issues/search", componentKeys=key, ps=1,
                     issueStatuses="OPEN,CONFIRMED",
                     facets="severities,impactSeverities")
    out = {}
    for facet in data["facets"]:
        prefix = "sq_issues_sev_" if facet["property"] == "severities" else "sq_issues_impact_"
        for v in facet["values"]:
            out[prefix + v["val"].lower()] = v["count"]
    return out


def main():
    session = sonar_session()
    avail = available_keys()
    keys = [k for k in KEYS if k in avail]
    missing_everywhere = [k for k in KEYS if k not in avail]
    not_returned = {}

    status = pd.read_csv(RESULTS / "sonar_scan_status.csv", dtype=str)
    ok = set(status[status.status == "ok"].project_key)

    rows = []
    for org, repo, year in read_selection():
        key = project_key(year, repo)
        row = {"cohort_year": year, "org": org, "repo": repo, "project_key": key}
        if key not in ok:
            rows.append(row)
            continue
        comp = sonar_get(session, "/api/measures/component", component=key,
                         metricKeys=",".join(keys))["component"]
        got = {m["metric"]: m.get("value") for m in comp["measures"]}
        for k in keys:
            if k not in got:
                not_returned.setdefault(k, []).append(key)
            row[f"sq_{k}"] = got.get(k)
        analyses = sonar_get(session, "/api/project_analyses/search", project=key, ps=1)["analyses"]
        row["sq_analysis_date"] = analyses[0]["date"] if analyses else None
        row.update(python_totals(file_measures(session, key)))
        row.update(issue_facets(session, key))
        rows.append(row)
        print(f"exported {key}", flush=True)

    df = pd.DataFrame(rows)
    # a facet value the server omits means 0 issues, but only for projects that were exported
    exported = df.project_key.isin(ok)
    for c in [c for c in df.columns if c.startswith("sq_issues_")]:
        df.loc[exported, c] = df.loc[exported, c].fillna(0)
    counts_as_int(df).to_csv(RESULTS / "sonarqube_metrics.csv", index=False)
    print(f"wrote results/sonarqube_metrics.csv ({len(df)} rows, {df.sq_ncloc.notna().sum()} with data)")

    lines = ["", "### Export run: keys not returned", ""]
    if missing_everywhere:
        lines.append("Not defined on this server: " + ", ".join(missing_everywhere))
    if not_returned:
        for k, projects in sorted(not_returned.items()):
            lines.append(f"- `{k}` missing for {len(projects)} project(s): " + ", ".join(projects))
    else:
        lines.append("All requested keys were returned for every exported project.")
    env = DOCS / "environment.md"
    text = env.read_text()
    marker = "\n### Export run: keys not returned"
    if marker in text:
        text = text[:text.index(marker)]
    env.write_text(text.rstrip("\n") + "\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
