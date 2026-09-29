# Metrics in Plain Language

Short explanations of each number in `results/results.csv`, for talking through the results. The exact definitions and formulas are in [`metrics_definitions.md`](metrics_definitions.md), and the SonarQube comparison is in [`metrics_mapping.md`](metrics_mapping.md).

**What gets measured.** All `py_*` numbers use only the repo's tracked `.py` files at the analysed commit. Committed virtualenvs and `node_modules` are skipped, using the same exclusion list as the SonarQube scan. A repo with no Python gets `NA` and `python_file_count = 0`.

> **A caveat that applies to everything below.** As the supervisor's document says, these are proxies. They help compare repos and cohorts measured the same way, but none of them tells you on its own whether code is good.

## Quick reference

| Metric | Column | Better when | Source |
|---|---|:---:|---|
| [CCavg](#ccavg-average-cyclomatic-complexity) | `py_cc_avg` | lower | Radon |
| [CCmax](#ccmax-maximum-cyclomatic-complexity) | `py_cc_max` | lower | Radon |
| [MI](#mi-maintainability-index) | `py_mi_avg` | higher | Radon |
| [Pylint score](#pylint-score) | `py_pylint_score` | higher | Pylint |
| [SLOC](#sloc-source-lines-of-code) | `py_sloc` | neither | Radon |
| [Comment %](#comment-) | `py_comment_pct` | neither | Radon |
| [Bandit high / medium / low](#bandit-high--medium--low) | `py_bandit_*` | lower | Bandit |

---

## CCavg: average cyclomatic complexity

`py_cc_avg`

**What it is.** For every function, method and class, Radon counts how many independent paths run through it: 1 + the number of `if`, `for`, `while`, `and`, `or`, `except` and so on. CCavg is the average of those counts across the whole repo.

**How to read it.** Lower means simpler. As a rough guide:

| CC | Complexity |
|---|---|
| 1-5 | simple |
| 6-10 | moderate |
| above 10 | complex |

**Limits.** It counts branches, not readability. A long but flat `if/elif` chain scores high even when it's easy to follow. Classes are included, as in the PDF, and their score comes from their methods, so methods get counted twice.

**SonarQube.** No direct equivalent. `complexity` is a total over the project, and `complexity / functions` (`sq_complexity_per_function`) is only a rough average.

---

## CCmax: maximum cyclomatic complexity

`py_cc_max`

**What it is.** The complexity of the single most complex function, method or class in the repo.

**How to read it.** Lower is better. Very high values (30+) usually point to one "god function" that is hard to test and change. The PDF calls this the likely maintenance bottleneck.

**Limits.** One outlier sets the value, so it says nothing about the rest of the code.

**SonarQube.** Nothing per function. `sq_py_file_complexity_max` is the most complex *file*, which is a different thing.

---

## MI: maintainability index

`py_mi_avg`

**What it is.** A 0-100 score per file that combines size (Halstead volume and lines), complexity and comments into one number. The repo value is the average over files.

**How to read it.** Higher means easier to maintain. Radon rates above 19 as "A", 10-19 as "B" and 9 or below as "C". Most student code lands in the 50-80 range.

**Limits.** The formula dates from the early 1990s and was fitted on other languages. Small files always score high, so a repo with lots of tiny files looks better. Every file counts equally, whatever its size.

**SonarQube.** None. `sqale_rating` and `sqale_debt_ratio` estimate the time needed to fix rule violations, which is a different idea.

---

## Pylint score

`py_pylint_score`

**What it is.** Pylint checks all Python files for errors, likely bugs, style problems (PEP 8, naming) and refactoring hints, then gives a score out of 10 based on messages per statement. Errors count 5 times as much as the other message types.

**How to read it.** Higher is better, up to 10. The same four import checks as in the PDF's SWE-bench setup are turned off, because the projects' libraries aren't installed and would otherwise show up as errors.

**Limits.** It's mostly a style score, so a few repeated conventions (missing docstrings, long lines) can dominate it. It also penalises style choices a team made on purpose.

**SonarQube.** No equivalent. Issues per 1,000 lines (`sq_issues_per_kloc`) is the closest rough comparison, but it uses SonarQube's own rules.

---

## SLOC: source lines of code

`py_sloc`

**What it is.** The number of Python lines that contain code, not counting blank or comment-only lines.

**How to read it.** Neither good nor bad. It shows project size and is the base for comment %.

**Limits.** Depends on formatting style.

**SonarQube.** `ncloc` (all languages) and `sq_py_ncloc` (Python only) are close but not identical. See the comparison in [`metrics_mapping.md`](metrics_mapping.md).

---

## Comment %

`py_comment_pct`

**What it is.** `#` comment lines divided by SLOC, times 100. This is the PDF's formula.

**How to read it.** A description of documentation density, not a score. Some commenting is good; very high values can mean commented-out code.

**Limits.** Radon doesn't count docstrings as comments, so a team that documents with docstrings looks under-commented. It counts lines, not comment quality.

**SonarQube.** `comment_lines_density` divides by (code + comments) instead of by code, so it's always lower. The PDF-style number from SonarQube data is `sq_comment_pct_pdf` = `comment_lines / ncloc * 100`. Note that SonarQube does count docstrings as comments.

---

## Bandit high / medium / low

`py_bandit_high`, `py_bandit_medium`, `py_bandit_low`

**What it is.** The number of potential security problems Bandit finds, split by how serious Bandit rates them. Examples include `eval`, `subprocess` with `shell=True`, hard-coded passwords, weak hashing, `assert` used for checks and requests without timeouts.

**How to read it.** Lower is better. Look at each level separately, since one high finding matters more than many low ones.

**Limits.** It's pattern matching only, so there are false positives and missed issues:

- False positives: `assert` in test files, for example, usually makes up a large share of the low count.
- Missed issues: logic flaws, and anything spread across several files.

**SonarQube.** `vulnerabilities` and `security_hotspots` come from different rules and a different severity scale, so they are reported next to Bandit, not merged with it.

---

## Not measured yet

**Functional correctness.** Not measured in D1. The capstone repos have no common test harness, and running each project's tests would mean setting up its dependencies and services.

**Deltas** (ΔCCavg, ΔCCmax, ΔMI, ΔPylint, ΔBandit). These are "after minus before" for the same metric. D1 has one snapshot per repo, so there is nothing to subtract yet. D3 can add rows for more commits and compute them.
