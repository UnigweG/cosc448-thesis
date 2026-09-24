# Metrics in plain language

Short explanations of each number in `results/results.csv`, for talking the results
through. The exact definitions and formulas are in `metrics_definitions.md`, and the
SonarQube comparison is in `metrics_mapping.md`.

All `py_*` numbers use only the repo's tracked `.py` files at the analysed commit.
Committed virtualenvs and `node_modules` are skipped (same exclusion list as the
SonarQube scan). A repo with no Python gets NA and `python_file_count = 0`.

A general caveat from the supervisor's document applies throughout: these are
proxies. They help compare repos and cohorts measured the same way, but none of
them says on its own whether code is good.

---

**CCavg: average cyclomatic complexity** (`py_cc_avg`)
- *What it is:* for every function, method and class, Radon counts how many
  independent paths run through it (1 + number of if/for/while/and/or/except...).
  CCavg is the average of those counts across the whole repo.
- *How to read it:* lower is simpler. Roughly 1-5 is simple, 6-10 moderate, above 10
  complex.
- *Limits:* it counts branches, not readability. A long but flat `if/elif` chain
  scores high even when it is easy to follow. Classes are included, as in the PDF,
  and their score is derived from their methods, so methods count twice.
- *SonarQube:* no direct equivalent. `complexity` is a total over the project, and
  `complexity / functions` (`sq_complexity_per_function`) is only a rough average.

**CCmax: maximum cyclomatic complexity** (`py_cc_max`)
- *What it is:* the complexity of the single most complex function, method or
  class in the repo.
- *How to read it:* lower is better. Very high values (30+) usually mean one "god
  function" that is hard to test and change. The PDF calls this the likely
  maintenance bottleneck.
- *Limits:* one outlier decides the value, so it says nothing about the rest of the
  code.
- *SonarQube:* none per function. `sq_py_file_complexity_max` is the most complex
  *file*, which is a different thing.

**MI: maintainability index** (`py_mi_avg`)
- *What it is:* a 0-100 score per file that combines size (Halstead volume and
  lines), complexity and comments into one number. The repo value is the average
  over files.
- *How to read it:* higher is easier to maintain. Radon calls above 19 "A", 10-19
  "B" and 9 or below "C", and most student code lands in the 50-80 range.
- *Limits:* the formula dates from the early 1990s and was fitted on other
  languages. Small files always score high, so a repo with many tiny files looks
  better. Every file counts equally regardless of size.
- *SonarQube:* none. `sqale_rating` and `sqale_debt_ratio` measure estimated
  time to fix rule violations, which is a different idea.

**Pylint score** (`py_pylint_score`)
- *What it is:* Pylint checks all Python files for errors, likely bugs, style
  problems (PEP 8, naming) and refactoring hints, then gives a score out of 10 based
  on messages per statement. Errors weigh 5 times more than the other message types.
- *How to read it:* higher is better, up to 10. The same four import checks as in
  the PDF's SWE-bench setup are turned off, because the projects' libraries are not
  installed and would otherwise show up as errors.
- *Limits:* mostly a style score, so a few repeated conventions (missing docstrings,
  long lines) can dominate it. It punishes style choices the team made on purpose.
- *SonarQube:* no equivalent. `violations` per 1,000 lines (`sq_issues_per_kloc`) is
  the closest rough comparison, but it uses SonarQube's own rules.

**SLOC: source lines of code** (`py_sloc`)
- *What it is:* the number of Python lines that contain code (not blank, not
  comment-only).
- *How to read it:* not good or bad. It shows project size and is the base for
  comment %.
- *Limits:* depends on formatting style.
- *SonarQube:* `ncloc` (all languages) and `sq_py_ncloc` (Python only) are close
  but not identical. See the comparison in `metrics_mapping.md`.

**Comment %** (`py_comment_pct`)
- *What it is:* `#` comment lines divided by SLOC, times 100 (the PDF's formula).
- *How to read it:* a description of documentation density, not a score. Some is
  good. Very high values can mean commented-out code.
- *Limits:* docstrings are not counted as comments by Radon, so a team that
  documents with docstrings looks under-commented. It counts lines, not comment
  quality.
- *SonarQube:* `comment_lines_density` divides by (code + comments) instead of
  code, so it is always lower. The PDF-style number from SonarQube data is
  `sq_comment_pct_pdf` = `comment_lines / ncloc * 100`, and SonarQube counts
  docstrings as comments.

**Bandit high / medium / low** (`py_bandit_high`, `py_bandit_medium`, `py_bandit_low`)
- *What it is:* the number of potential security problems Bandit finds, split by how
  serious Bandit rates them. Examples: `eval`, `subprocess` with `shell=True`,
  hard-coded passwords, weak hashing, `assert` used for checks, requests without
  timeouts.
- *How to read it:* lower is better. Look at the levels separately, since one high
  finding matters more than many low ones.
- *Limits:* pattern matching only, so there are false positives (for example
  `assert` in test files, which is usually a large share of the low count) and
  missed real issues (logic flaws, anything spread across files).
- *SonarQube:* `vulnerabilities` and `security_hotspots` come from different rules
  and a different severity scale, so they are reported next to Bandit, not merged.

**Functional correctness:** not measured in D1. The capstone repos have no common
test harness, and running each project's tests would mean setting up its
dependencies and services.

**Deltas (ΔCCavg, ΔCCmax, ΔMI, ΔPylint, ΔBandit):** "after minus before" for the
same metric. D1 has one snapshot per repo, so there is nothing to subtract yet. D3
can add rows for more commits and compute them.
