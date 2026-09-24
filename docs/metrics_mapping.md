# PDF metrics vs SonarQube 26.9

Server: SonarQube 26.9.0.129388 Community Edition. The full list of metric keys on
this server is in `docs/sonarqube_metrics_available.csv` (159 keys, pulled from
`/api/metrics/search`). I only relied on keys confirmed in that list. The machine-readable
version of this table is `results/metrics_mapping.csv`.

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

To be filled after the first project is scanned (Phase 4).

## ncloc vs Radon SLOC, comment_lines vs Radon comments

To be filled after Phase 5.
