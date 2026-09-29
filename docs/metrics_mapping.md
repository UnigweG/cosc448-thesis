# PDF Metrics vs SonarQube 26.9

**Server:** SonarQube 26.9.0.129388, Community Edition.

The full list of metric keys on this server is in `docs/sonarqube_metrics_available.csv` (159 keys, from `/api/metrics/search`). We only relied on keys confirmed in that list. A machine-readable version of the summary table is in `docs/metrics_mapping.csv`.

## Contents

- [Summary](#summary)
- [Notes per metric](#notes-per-metric)
- [First scan check](#first-scan-check)
- [ncloc vs Radon SLOC, comment_lines vs Radon comments](#ncloc-vs-radon-sloc-comment_lines-vs-radon-comments)
- [Which source each reported number comes from](#which-source-each-reported-number-comes-from)
- [UI check](#ui-check)

---

## Summary

| PDF metric | SonarQube keys in 26.9 | Match | How the PDF version is computed | Source |
|---|---|:---:|---|---|
| CCavg | `complexity`, `functions` (also `cognitive_complexity`) | different | Radon per-block CC pooled over files, mean | Radon |
| CCmax | `complexity` (per file via `component_tree`) | none | Radon per-block CC, max | Radon |
| MI | `sqale_index`, `sqale_debt_ratio`, `sqale_rating`, `software_quality_maintainability_*` | none | Radon MI per file, mean over files | Radon |
| Pylint score | `violations`, `code_smells` (proxy only) | none | Pylint, one run over all files, 4 import checks off | Pylint |
| SLOC | `ncloc` | close | Radon `sloc`, summed | Radon |
| Comment % | `comment_lines`, `ncloc`, `comment_lines_density` | different | Radon `comments / sloc * 100`; SonarQube version derived as `comment_lines / ncloc * 100` | Radon (SonarQube derived alongside) |
| Bandit high / medium / low | `vulnerabilities`, `security_hotspots`, `software_quality_security_issues`, `software_quality_{high,medium,low}_issues` | different | Bandit counts by severity, summed | Bandit |
| Functional correctness | none | none | Out of scope for D1 | none |
| ΔCCavg, ΔCCmax, ΔMI, ΔPylint, ΔBandit | none | none | Differences between two snapshots (D3) | derived |

**In short:**

- No PDF metric is available directly and identically in SonarQube.
- **SLOC** is close (`ncloc`).
- **Comment %** can be derived from SonarQube's raw counts.
- **CC, MI, Pylint and Bandit** have to come from Radon, Pylint and Bandit.
- **Functional correctness** is out of scope, and the **deltas** are computed later.

---

## Notes per metric

All of these were checked on this server.

### Cyclomatic complexity

`complexity` is described as "Cyclomatic complexity" and is a **sum** over the component (project, directory or file).

The keys that older SonarQube versions had for averages (`function_complexity`, `file_complexity`, `class_complexity`, `complexity_in_functions`, `function_complexity_distribution`) **do not exist in 26.9**.

The finest level available is per file, through:

```text
/api/measures/component_tree?metricKeys=complexity&qualifiers=FIL
```

Per-function values are not exposed. `complexity / functions` gives a rough mean per function, but the numerator also includes complexity outside functions and the counting rules differ from Radon's, so it is not the PDF's CCavg. It is exported as `sq_complexity_per_function` for reference only.

There is no way to get CCmax from SonarQube. `cognitive_complexity` is a different measure (it penalises nesting) and is exported as extra context.

### Maintainability index

SonarQube has no MI. Its "maintainability" keys are based on technical debt:

| Key | Meaning |
|---|---|
| `sqale_index` | Estimated remediation effort for maintainability issues, in minutes |
| `sqale_debt_ratio` | `sqale_index` divided by an estimated development cost |
| `sqale_rating`, `software_quality_maintainability_rating` | The debt ratio turned into grades A-E |

These depend on SonarQube's rule set, not on the Halstead / CC / LOC formula, so they measure a different thing.

### Pylint

There is no equivalent. As a rough proxy I export SonarQube issues per 1,000 ncloc (`violations / ncloc * 1000`) and the maintainability-issue count. These come from SonarQube's own Python rules (444 on this server), not Pylint's.

### SLOC

`ncloc` ("Non commenting lines of code") is close to Radon's `sloc`. Both leave out blank and comment-only lines. They differ in how they handle docstrings and multi-line strings.

`ncloc` also covers every analysed language, unless you restrict it to Python through `ncloc_language_distribution` (which gives `py=<n>`). The comparison across repos is [below](#ncloc-vs-radon-sloc-comment_lines-vs-radon-comments).

### Comment %

On this server, `comment_lines_density` is described as "Comments balanced by ncloc + comment lines", which means:

```text
comment_lines_density = comment_lines / (ncloc + comment_lines) * 100
```

That's a different denominator from the PDF's `comments / SLOC * 100`, and it always gives a lower number. So the PDF version from SonarQube data is derived separately, as `comment_lines / ncloc * 100` (`sq_comment_pct_pdf` in `results.csv`).

For Python, SonarQube counts docstrings as comment lines and Radon's `comments` does not, so the two still differ.

### Bandit vs SonarQube security

SonarQube splits security into `vulnerabilities` (confirmed issues) and `security_hotspots` (code to review). In 26.9, issues also carry impact severities (`software_quality_blocker/high/medium/low/info_issues`, across all software qualities).

Bandit's high / medium / low come from a different rule set and a different severity scale, so the two are reported side by side, never merged.

### Functional correctness

Coverage and test metrics exist (`coverage`, `tests`, ...), but SonarQube only fills them when a scan imports test reports. D1 doesn't do that.

---

## First scan check

**Test project:** `cosc448_2025_capstone-project-team-16`, a Python and JavaScript repo.

```text
ncloc_language_distribution = css=309;docker=10;js=2131;py=7298;web=24
```

Every mapped key returned a value for this project:

> `ncloc`, `lines`, `statements`, `functions`, `classes`, `files`, `comment_lines`, `comment_lines_density`, `complexity`, `cognitive_complexity`, `duplicated_lines_density`, `duplicated_blocks`, `bugs`, `vulnerabilities`, `security_hotspots`, `code_smells`, `violations`, `sqale_index`, `sqale_debt_ratio`, `sqale_rating`, `reliability_rating`, `security_rating`, `ncloc_language_distribution`, all `software_quality_*` issue counts and ratings, and `open_issues`.

`coverage` came back as 0.0 and `tests` wasn't returned, because no test reports are imported. Neither is used.

### What the check showed

1. **Project-level measures mix all languages.** At project level, `ncloc`, `comment_lines` and `complexity` combine Python with JS, CSS and the rest. To compare with Radon (Python only), the export also sums the per-file measures from `/api/measures/component_tree?qualifiers=FIL` for files where `language = py`. These become the `sq_py_*` columns. For this repo, Python alone gives ncloc 7,298, comment_lines 1,333 and complexity 1,615, over 54 files and 334 functions.

2. **Test files are included.** SonarQube flagged tests with a path heuristic, but `component_tree` returned no separate `UTS` components. All 54 tracked `.py` files (31 of them tests) appear as `FIL` and count toward ncloc. That's the same file set Radon sees.

3. **Per-file complexity works, per-function doesn't.** The highest per-file value here is `src/api.py`, with complexity 386. So SonarQube can give a maximum per *file* (`sq_py_file_complexity_max`), but that isn't the PDF's CCmax, which is per function. CCmax stays Radon-only.

4. **Two kinds of issue severity.** The `/api/issues/search` facets return both the older `severities` (BLOCKER / CRITICAL / MAJOR / MINOR / INFO) and the newer `impactSeverities` (BLOCKER / HIGH / MEDIUM / LOW / INFO). The export stores both. The `software_quality_*` issue-count measures match the `impactSeverities` facet (for example, 111 HIGH).

No mapping entries had to change. The only addition was the Python-only `sq_py_*` columns.

---

## ncloc vs Radon SLOC, comment_lines vs Radon comments

Compared on the 48 repos that contain Python, using the Python-only SonarQube sums (`sq_py_ncloc`, `sq_py_comment_lines`) against Radon's totals over the same tracked files.

### File sets

The file sets match in 47 of 48 repos. In W2025 team 10, SonarQube skipped one test-data file stored under a folder named `.git(test)/`. Both tools use the same exclusions (`node_modules`, `venv`, `site-packages`, `build`, `dist`, ...).

### SLOC vs ncloc: effectively the same

| Measure | Value |
|---|---|
| Ratio `sq_py_ncloc / py_sloc` | median 1.000, mean 1.003, range 0.972-1.055 |
| Repos within 2% | 44 of 48 |
| Pearson correlation across repos | 1.00 |
| Totals | Radon 577,179 vs SonarQube 577,987 (+0.14%) |

The small differences come from how multi-line strings, line continuations and docstring lines are counted. The largest gaps (+5%) are W2023 team 17 and W2024 team 1-003.

### Comment lines: clearly different

| Measure | Value |
|---|---|
| Ratio `sq_py_comment_lines / py_comments` | median 1.63, mean 1.84, range 0.91-6.76 |
| Totals | Radon 47,118 vs SonarQube 102,770 (about 2.2×) |
| Pearson correlation of counts | 0.91 |
| Spearman correlation of comment % (`py_comment_pct` vs `sq_py_comment_pct_pdf`) | 0.74 |

The main reason is that SonarQube counts docstring lines as comment lines, while Radon's `comments` field only counts `#` comments (it reports docstrings separately as `multi`). Repos that document heavily with docstrings show the biggest gap. W2025 team 2, for example, has a ratio of 6.8.

The raw counts correlate well, but the rankings by comment % differ more.

### Comment % definitions side by side

Example: W2025 team 16.

| Column | Definition | Value |
|---|---|---:|
| `py_comment_pct` | Radon counts, PDF formula | 10.9 |
| `sq_py_comment_pct_pdf` | SonarQube counts, PDF formula | 18.3 |
| `sq_comment_lines_density` | SonarQube's own definition, all languages | 12.2 |

The three are not interchangeable.

---

## Which source each reported number comes from

| Reported metric | Column used in the report | Source |
|---|---|---|
| CCavg | `py_cc_avg` | Radon |
| CCmax | `py_cc_max` | Radon |
| MI | `py_mi_avg` | Radon |
| Pylint score | `py_pylint_score` (see note below) | Pylint |
| SLOC | `py_sloc` | Radon |
| Comment % | `py_comment_pct` (PDF definition, `#` comments only) | Radon |
| Bandit high / medium / low | `py_bandit_high`, `py_bandit_medium`, `py_bandit_low` | Bandit |
| Whole-repo size, all languages | `sq_ncloc`, `sq_ncloc_language_distribution` | SonarQube |
| SonarQube quality context | `sq_bugs`, `sq_vulnerabilities`, `sq_code_smells`, `sq_security_hotspots`, ratings, `sq_software_quality_*` | SonarQube |

For SLOC, `sq_py_ncloc` agrees with `py_sloc` within 1% in 41 of 48 repos and within 2% in 44 (range 0.972-1.055).

> **Pylint note.** The headline column is `py_pylint_score`, Pylint's own score as the PDF defines it. One repo is affected by Pylint's fatal-message rule: W2025 team 6 scores 0.0 because one file can't be parsed, and 8.37 in `py_pylint_score_excl_fatal` without that file. This pulls the W2025 cohort mean down from 7.63 to 7.21 (by 0.42, over 20 repos). I report the headline column and give both numbers for this repo.

The PDF metrics are only defined for Python, so they are `NA` for the 20 repos without tracked Python. For those repos only the SonarQube columns are available. For C# code, not even those, because the CLI scanner doesn't analyse C# (see [`environment.md`](environment.md)).

---

## UI check

Checked in the SonarQube web UI (view only).

**Projects page, searched for `cosc448_`:** 68 projects found, matching all 68 selected repos. The pre-existing `COSC-499-W2023_year-long-project-team-1` project was not touched.

**Overview of `cosc448_2025_capstone-project-team-16`, "Overall Code" tab, compared with `results/results.csv`:**

| UI | UI value | CSV column | CSV value |
|---|---|---|---|
| Security open issues / rating | 3 / E | `sq_software_quality_security_issues` / `sq_security_rating` | 3 / 5.0 (E) |
| Reliability open issues / rating | 25 / D | `sq_software_quality_reliability_issues` / `sq_reliability_rating` | 25 / 4.0 (D) |
| Maintainability open issues / rating | 203 / A | `sq_software_quality_maintainability_issues` / `sq_sqale_rating` | 203 / 1.0 (A) |
| Duplications | 1.9% on 13k lines | `sq_duplicated_lines_density` / `sq_lines` | 1.9 / 13280 |
| Security Hotspots | 0 | `sq_security_hotspots` | 0 |

No mismatches. Note that the UI shows the newer `software_quality_*` issue counts (203 maintainability issues), not the older `code_smells` (205). When quoting "issues" from the UI, use the `sq_software_quality_*` columns.

**Security caveat.** The overview warns that the Community Build doesn't scan for injection vulnerabilities (SQL injection, XSS and similar). SonarQube's security numbers are therefore a lower bound, which is one more reason not to compare them directly with Bandit.
