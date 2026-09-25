# PDF metrics vs SonarQube 26.9

Server: SonarQube 26.9.0.129388 Community Edition. The full list of metric keys on
this server is in `docs/sonarqube_metrics_available.csv` (159 keys, pulled from
`/api/metrics/search`). I only relied on keys confirmed in that list. The machine-readable
version of this table is `docs/metrics_mapping.csv`.

## Summary

| PDF metric | SonarQube keys available in 26.9 | Match | How the PDF version is computed | Source |
|---|---|---|---|---|
| CCavg | `complexity`, `functions` (also `cognitive_complexity`) | different | Radon per-block CC pooled over files, mean | radon |
| CCmax | `complexity` (per file via `component_tree`) | none | Radon per-block CC, max | radon |
| MI | `sqale_index`, `sqale_debt_ratio`, `sqale_rating`, `software_quality_maintainability_*` | none | Radon MI per file, mean over files | radon |
| Pylint score | `violations`, `code_smells` (proxy only) | none | Pylint, one run over all files, 4 import checks off | pylint |
| SLOC | `ncloc` | close | Radon `sloc` summed | radon |
| Comment % | `comment_lines`, `ncloc`, `comment_lines_density` | different | Radon comments / sloc * 100; SonarQube-derived as `comment_lines / ncloc * 100` | radon (sq derived alongside) |
| Bandit high/med/low | `vulnerabilities`, `security_hotspots`, `software_quality_security_issues`, `software_quality_{high,medium,low}_issues` | different | Bandit counts by severity, summed | bandit |
| Functional correctness | none | none | out of scope for D1 | none |
| ΔCCavg, ΔCCmax, ΔMI, ΔPylint, ΔBandit_s | none | none | differences between two snapshots (D3) | derived |

So: no PDF metric is available directly and identically in SonarQube. SLOC is close
(`ncloc`). Comment % can be derived from SonarQube raw counts. CC, MI, Pylint and
Bandit have to come from Radon, Pylint and Bandit. Correctness is out of scope and
the deltas are derived later.

## Notes per metric (checked on this server)

**Cyclomatic complexity.** `complexity` is described as "Cyclomatic complexity" and
is a sum over the component (project, directory or file). Keys that older SonarQube
versions had for averages (`function_complexity`, `file_complexity`,
`class_complexity`, `complexity_in_functions`, `function_complexity_distribution`)
do **not** exist in 26.9. The finest level available is per file, through
`/api/measures/component_tree?metricKeys=complexity&qualifiers=FIL`. Per-function
values are not exposed. `complexity / functions` gives a rough mean per function,
but the numerator also includes complexity outside functions and the counting rules
differ from Radon's, so it is not the PDF's CCavg. It is exported as
`sq_complexity_per_function` for reference only. There is no way to get CCmax from
SonarQube. `cognitive_complexity` is a different measure (it penalises nesting) and
is exported as extra context.

**Maintainability index.** SonarQube has no MI. Its "maintainability" keys are based
on technical debt: `sqale_index` is the estimated remediation effort in minutes for
maintainability issues, `sqale_debt_ratio` divides that by an estimated development
cost, and `sqale_rating` / `software_quality_maintainability_rating` turn the ratio
into grades A-E. These depend on the rule set and not on the Halstead/CC/LOC formula,
so they are a different construct.

**Pylint.** There is no equivalent. As a rough proxy I export SonarQube issues per
1,000 ncloc (`violations / ncloc * 1000`) and the maintainability-issue count, but
these come from SonarQube's own Python rules (444 rules on this server), not
Pylint's.

**SLOC.** `ncloc` ("Non commenting lines of code") is close to Radon's `sloc`. Both
exclude blank and comment-only lines. They differ on docstrings and multi-line
strings, and `ncloc` covers every analysed language unless it is restricted to
Python through `ncloc_language_distribution` (which gives `py=<n>`). The comparison
across repos is below.

**Comment %.** On this server `comment_lines_density` is described as "Comments
balanced by ncloc + comment lines", i.e.
`comment_lines / (ncloc + comment_lines) * 100`. That is a different denominator from
the PDF's `comments / SLOC * 100`, and it is always lower. The PDF version from
SonarQube data is therefore derived as `comment_lines / ncloc * 100`
(`sq_comment_pct_pdf` in results.csv). For Python, SonarQube counts docstrings as
comment lines while Radon's `comments` does not, so the two will still differ.

**Bandit vs SonarQube security.** SonarQube splits security into `vulnerabilities`
(confirmed issues) and `security_hotspots` (code to review). In 26.9 issues also
carry impact severities (`software_quality_blocker/high/medium/low/info_issues`,
across all software qualities). Bandit's high/medium/low come from a different rule
set and a different severity scale, so the numbers are reported side by side and not
merged.

**Functional correctness.** Coverage and test metrics exist (`coverage`,
`tests`, ...), but they are only filled when a scan imports test reports, which D1
does not do.

## First scan check

Test project: `cosc448_2025_capstone-project-team-16`, a Python + JavaScript repo
(`ncloc_language_distribution` = `css=309;docker=10;js=2131;py=7298;web=24`).

Every mapped key returned a value for this project: `ncloc`, `lines`,
`statements`, `functions`, `classes`, `files`, `comment_lines`,
`comment_lines_density`, `complexity`, `cognitive_complexity`,
`duplicated_lines_density`, `duplicated_blocks`, `bugs`, `vulnerabilities`,
`security_hotspots`, `code_smells`, `violations`, `sqale_index`, `sqale_debt_ratio`,
`sqale_rating`, `reliability_rating`, `security_rating`,
`ncloc_language_distribution`, all `software_quality_*` issue counts and ratings,
and `open_issues`. `coverage` came back as 0.0 and `tests` was not returned, because
no test reports are imported. Neither is used.

What I learned from it, and the resulting changes:

- **Project-level measures cover every language.** `ncloc`, `comment_lines` and
  `complexity` at project level mix Python with JS, CSS and so on. To compare with
  Radon (Python only) the export also sums the per-file measures from
  `/api/measures/component_tree?qualifiers=FIL` for files with `language = py`.
  These become the `sq_py_*` columns. For this repo, Python gives ncloc 7298,
  comment_lines 1333, complexity 1615 over 54 files and 334 functions.
- **Test files are included.** SonarQube flagged tests with a path heuristic, but
  `component_tree` returned no separate `UTS` components. All 54 tracked `.py` files
  (31 of them test files) appear as `FIL` and count toward ncloc, the same file set
  Radon sees.
- **Per-file complexity works; per-function complexity does not.** The highest
  per-file value here is `src/api.py` with complexity 386. So SonarQube can give a
  maximum per *file* (`sq_py_file_complexity_max`), which is not the PDF's CCmax
  (per function). CCmax stays Radon-only.
- **Issue severities.** `/api/issues/search` facets return both the old
  `severities` (BLOCKER/CRITICAL/MAJOR/MINOR/INFO) and the newer `impactSeverities`
  (BLOCKER/HIGH/MEDIUM/LOW/INFO). The export stores both. The `software_quality_*`
  issue-count measures match the `impactSeverities` facet, e.g. 111 HIGH.

No mapping entries had to change. The only additions are the Python-only `sq_py_*`
columns.

## ncloc vs Radon SLOC, comment_lines vs Radon comments

Compared on the 48 repos that contain Python, using the Python-only SonarQube sums
(`sq_py_ncloc`, `sq_py_comment_lines`) against Radon's totals over the same tracked
files.

**File sets.** They match in 47 of 48 repos. In W2025 team 10, SonarQube skipped one
test-data file stored under a folder named `.git(test)/`. Both tools use the same
exclusions (node_modules, venv, site-packages, build, dist, ...).

**SLOC vs ncloc: effectively the same.**
- Ratio `sq_py_ncloc / py_sloc`: median 1.000, mean 1.003, range 0.972-1.055.
  44 of 48 repos are within 2%.
- Pearson correlation across repos: 1.00. Totals: Radon 577,179, SonarQube 577,987
  (+0.14%).
- The small differences come from how multi-line strings, line continuations and
  docstring lines are counted. The largest gaps (+5%) are W2023 team 17 and
  W2024 team 1-003.

**Comment lines: clearly different.**
- Ratio `sq_py_comment_lines / py_comments`: median 1.63, mean 1.84, range 0.91-6.76.
  Totals: Radon 47,118, SonarQube 102,770, so SonarQube reports about 2.2 times as
  many.
- The main reason is that SonarQube counts docstring lines as comment lines, while
  Radon's `comments` field only counts `#` comments (it reports docstrings separately
  as `multi`). Repos that document heavily with docstrings show the biggest gap. For
  example, W2025 team 2 has ratio 6.8.
- Pearson correlation of the counts across repos is 0.91, but the rankings of
  comment % differ more: Spearman between `py_comment_pct` and
  `sq_py_comment_pct_pdf` is 0.74.

**Comment % definitions side by side**, for example W2025 team 16:
`py_comment_pct` (Radon, PDF formula) = 10.9, `sq_py_comment_pct_pdf` (SonarQube
counts, PDF formula) = 18.3, `sq_comment_lines_density` (SonarQube's own, all
languages) = 12.2. The three are not interchangeable.

## Which source each reported number comes from

| Reported metric | Column used in the report | Source |
|---|---|---|
| CCavg | `py_cc_avg` | Radon |
| CCmax | `py_cc_max` | Radon |
| MI | `py_mi_avg` | Radon |
| Pylint score | `py_pylint_score` (see note below) | Pylint |
| SLOC | `py_sloc` (`sq_py_ncloc` agrees within 1% in 41 of 48 repos, within 2% in 44, range 0.972-1.055) | Radon |
| Comment % | `py_comment_pct` (PDF definition, `#` comments only) | Radon |
| Bandit high/medium/low | `py_bandit_high/medium/low` | Bandit |
| Whole-repo size, all languages | `sq_ncloc`, `sq_ncloc_language_distribution` | SonarQube |
| SonarQube quality context | `sq_bugs`, `sq_vulnerabilities`, `sq_code_smells`, `sq_security_hotspots`, ratings, `sq_software_quality_*` | SonarQube |

**Pylint note.** The headline column is `py_pylint_score`, Pylint's own score as the
PDF defines it. One repo is affected by Pylint's fatal-message rule: W2025 team 6 gets
0.0 because one file cannot be parsed, and 8.37 in `py_pylint_score_excl_fatal`
without that file. This lowers the W2025 cohort mean from 7.63 to 7.21 (by 0.42,
over 20 repos). I report the headline column and give both numbers for this repo.

The PDF metrics are only defined for Python, so they are NA for the 20 repos without
tracked Python. For those repos, only the SonarQube columns are available. For C#
code, not even those: the CLI scanner does not analyse C# (see `environment.md`).

## UI check (SonarQube web UI, view only)

- **Projects page, searched for `cosc448_`:** 68 projects found, all 68 selected
  repos. The pre-existing `COSC-499-W2023_year-long-project-team-1` project was not
  touched.
- **Overview of `cosc448_2025_capstone-project-team-16`, "Overall Code" tab, compared
  with `results/results.csv`:**

  | UI | UI value | CSV column | CSV value |
  |---|---|---|---|
  | Security open issues / rating | 3 / E | sq_software_quality_security_issues / sq_security_rating | 3 / 5.0 (E) |
  | Reliability open issues / rating | 25 / D | sq_software_quality_reliability_issues / sq_reliability_rating | 25 / 4.0 (D) |
  | Maintainability open issues / rating | 203 / A | sq_software_quality_maintainability_issues / sq_sqale_rating | 203 / 1.0 (A) |
  | Duplications | 1.9% on 13k lines | sq_duplicated_lines_density / sq_lines | 1.9 / 13280 |
  | Security Hotspots | 0 | sq_security_hotspots | 0 |

  No mismatches. The UI shows the newer `software_quality_*` issue counts
  (203 maintainability issues), not the older `code_smells` (205), so when quoting
  "issues" from the UI, use the `sq_software_quality_*` columns.
- **Note on security.** The overview warns that Community Build does not scan for
  injection vulnerabilities (SQL injection, XSS and similar). SonarQube's security
  numbers are therefore a lower bound, which is one more reason not to compare them
  directly with Bandit.
