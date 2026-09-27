# Metric definitions

**Source:** the supervisor's metrics document, *Metrics* (May 20, 2026), stored at [`docs/references/Metrics.pdf`](references/Metrics.pdf).

That document was written to evaluate LLM-generated Python code from LiveCodeBench and SWE-bench Verified. The same definitions are applied to student capstone repositories. Wherever the unit of analysis changes (a whole repository instead of a single solution or patch), it is mentioned how the definitions are adapted. If this file and the PDF ever disagree, the PDF is the reference.

**Tools:** Radon 6.0.1, Pylint 4.0.9 and Bandit 1.9.4 on Python 3.14.0. All versions, including dependencies, are pinned in `requirements.txt`.

## Contents

- [Why these metrics](#why-these-metrics)
- [Unit of analysis and file set](#unit-of-analysis-and-file-set)
- [Aggregation rules](#aggregation-rules)
- [Metrics](#metrics)
  - [Cyclomatic complexity (CCavg, CCmax)](#cyclomatic-complexity-ccavg-and-ccmax)
  - [Maintainability index (MI)](#maintainability-index-mi)
  - [Pylint score](#pylint-score)
  - [Source lines of code (SLOC)](#source-lines-of-code-sloc)
  - [Comment percentage](#comment-percentage)
  - [Bandit security findings](#bandit-security-findings)
  - [Functional correctness](#functional-correctness)
  - [Pre/post deltas](#prepost-deltas)
- [Limitations](#limitations)
- [References](#references)

---

## Why these metrics

The PDF groups the metrics into four quality dimensions: **functional correctness**, **code quality**, **maintainability** and **security**. Every one of them can be computed automatically with open-source tools, so they are reproducible and cheap to run across many repositories.

Two lines of research support using them:

- **Chowdhury et al. (2022)** studied about 730K Java methods in 47 projects and found that code metrics help predict which methods will change later, even after controlling for method size. So they carry information beyond plain size.
- **Antinyan et al. (2017)** report that practitioners see complexity as hurting readability, understandability, modifiability and maintenance time.

The PDF is also clear that these metrics are indicators for relative comparison, not a replacement for expert review. Pantiuchina et al. (2018) show that metric changes don't always match what developers see as quality improvements. Börstler et al. (2023) show that the properties developers care about (readability, structure, comprehensibility) are hard to capture with static metrics.

We use the metrics the same way: to compare repositories and cohorts measured with the same procedure, not to pass absolute judgement on any team's code.

---

## Unit of analysis and file set

- **One measurement = one snapshot**, meaning a repository at a specific commit.
- **Python file set:** `git ls-files '*.py'` at that commit. Using only tracked files keeps untracked virtual environments and installed packages out.
- **Vendored code is excluded.** A few teams committed a virtualenv or `node_modules` (W2023 teams 13 and 17, W2024 team 12-003), so tracked files under these folders are also skipped:

  ```text
  node_modules/  .venv/  venv/  site-packages/  dist/  build/  target/  __pycache__/
  ```

  The SonarQube scan uses the same list, so both tools measure the same files. The one exception is that the scan keeps `build/` for `capstone-project-team-2-003-1`, because that team kept its source there. That repo has no Python, so it doesn't affect the Python metrics. The number of skipped files is recorded in `py_excluded_files`.
- **Repos without Python** get `NA` for every Python metric and `python_file_count = 0`.
- **Jupyter notebooks are not included.** `.ipynb` files are outside the file set, so notebook code doesn't count toward any `py_*` metric. In most repos this barely matters, but in W2024 team 1-003 SonarQube counts 2,183 lines of notebook code against 1,333 lines of `.py` code.
- **Commit history includes the starter template.** The inventory's `commit_count` and `first_commit_date` include the template's history. Every W2024 repo reports a first commit of `2024-09-05T18:56:49Z` and every W2025 repo `2025-08-26T22:28:55Z`. Those are the template's commits, not each team's first commit.

---

## Aggregation rules

These follow the PDF's multi-file rules for SWE-bench Verified, applied to all tracked Python files in the repo rather than only the files a patch touched.

| Metric         | Repo-level rule                                                                                         |
|----------------|---------------------------------------------------------------------------------------------------------|
| CC             | Pool every per-block value (functions, methods, classes) from all files into one list. CCavg is the mean of that list and CCmax is its maximum. |
| MI             | Compute MI per file, then take the mean over files.                                                     |
| Pylint         | One Pylint run over all Python files together; use the overall score.                                   |
| Bandit         | Sum the high, medium and low severity findings over all files.                                          |
| SLOC, comments | Sum over all files. Comment % is computed from the sums.                                                |

---

## Metrics

### Cyclomatic complexity: CCavg and CCmax

**What it measures.** McCabe's (1976) cyclomatic complexity counts the linearly independent paths through a piece of code. In practice, it's 1 plus the number of decision points: `if`/`elif`, loops, boolean operators, `except` clauses, comprehension conditions and so on.

**Formula.** For a single block, on its control-flow graph:

```math
CC = E - N + 2P
```

Radon computes this as 1 + the number of decision points. At repo level, with $B$ the pooled set of blocks:

```math
CC_{avg} = \frac{1}{|B|} \sum_{b \in B} CC_b
\qquad
CC_{max} = \max_{b \in B} CC_b
```

**How to read it.** Lower is better. CCavg describes the typical function. CCmax points to the single most complex block, which the PDF describes as the likely maintenance bottleneck.

| Radon rank | CC range |
|:----------:|:--------:|
| A          | 1-5      |
| B          | 6-10     |
| C          | 11-20    |
| D          | 21-30    |
| E          | 31-40    |
| F          | 41+      |

**Tool.** Radon 6.0.1 (`radon cc`), default settings.

**Aggregation.** Blocks are pooled across all files (see [Aggregation rules](#aggregation-rules)). Radon's default output lists top-level functions, classes and their methods, which matches the PDF's "functions, methods, or classes".

Radon leaves out nested blocks entirely. A closure (a function defined inside another function), a class nested in a class, and a class defined inside a function are not listed, and their complexity is not added to the enclosing block either. For example, a function with CC 2 that contains a closure with CC 3 contributes a single block with CC 2.

**Limits.**

- Radon derives a class block's complexity from its methods, so including classes counts those methods twice in the pooled list. I keep classes in because the PDF lists them as blocks.
- CC counts paths, not how hard code is to read. A flat 30-case dispatch scores high but is easy to follow.
- CC ignores naming, nesting depth and data complexity.
- Radon counts every `assert` as a decision point, so test functions with many asserts score higher than their logic suggests.

---

### Maintainability index (MI)

**What it measures.** Oman and Hagemeister (1992) proposed MI as a single score for how easy code is to maintain. It combines size, complexity and comment density.

**Formula (Radon's variant).**

```math
MI = \min\left(100,\ \max\left(0,\ 100 \cdot \frac{171 - 5.2 \ln V - 0.23\,G - 16.2 \ln L + 50 \sin\left(\sqrt{2.46 \cdot \mathrm{radians}(C)}\right)}{171}\right)\right)
```

where:

| Symbol | Meaning                                                                 |
|:------:|-------------------------------------------------------------------------|
| $V$    | Halstead volume                                                         |
| $G$    | total cyclomatic complexity                                             |
| $L$    | logical lines of code (LLOC, not SLOC)                                  |
| $C$    | comment percentage: (comment lines + multi-line string lines) / SLOC × 100 |

Radon passes $C$ through `radians()` as if it were an angle in degrees. It counts multi-line strings (docstrings) as comments by default, and I keep that default. A file with zero SLOC or zero Halstead volume gets an MI of 100.

**How to read it.** Higher is better, on a 0-100 scale. Radon's ranks are **A** (> 19), **B** (10-19) and **C** (≤ 9).

**Tool.** Radon 6.0.1 (`radon mi`), default settings.

**Aggregation.** Mean of the per-file MI over all Python files. Every file counts the same, whatever its size.

**Limits.**

- The coefficients were fitted on 1990s industrial C and Pascal systems.
- Short files score close to 100 regardless of quality, so many tiny files (for example empty `__init__.py`) push the repo mean up. In a few repos this effect is large:

  | Repo            | Repo MI | Mean MI over files with ≥ 10 logical lines |
  |-----------------|--------:|-------------------------------------------:|
  | W2023 team 7    |    90.9 |                                       64.4 |
  | W2023 team 11   |    90.9 |                                       66.5 |

  Across the 48 Python repos, the median difference is 4.1 points.

---

### Pylint score

**What it measures.** An overall rating of a file set's errors and how closely it follows Python coding standards: PEP 8 style, naming, unused code, likely bugs and refactoring hints.

**Formula.** Pylint's default evaluation:

```math
\text{score} = \max\left(0,\ 10 - \frac{5 \cdot \text{error} + \text{warning} + \text{refactor} + \text{convention}}{\text{statement}} \cdot 10\right)
```

Each term is the count of messages in that category, and `statement` is the number of statements analysed.

**How to read it.** Higher is better, up to 10. Code with many messages per statement can hit the floor of 0.

**Tool.** Pylint 4.0.9.

**Aggregation.** One run over all of the repo's Python files together, as the PDF did for SWE-bench ("all files at once, as PyLint supports it"). Each repo has a 10-minute timeout; the score is `NA` if the run fails.

**Settings.** The PDF used default parameters for LiveCodeBench. For SWE-bench Verified it turned off four import-related checks, because imports could fail when the surrounding files were missing:

- `import-error`
- `no-name-in-module`
- `wrong-import-position`
- `ungrouped-imports`

> **Decision for this project:** I turn off the same four checks. The capstone repos' dependencies aren't installed in my environment, so import errors would otherwise dominate the score. Everything else stays at its default, and repo-level `.pylintrc` files are ignored so every repo is scored the same way.

**Fatal messages.** By default, Pylint sets the score to 0 if any file produces a fatal message, for example `F0010` when it can't parse a file. This happened in one repo: W2025 team 6, where a demo file was saved as ISO-8859 instead of UTF-8. I keep Pylint's own number in `py_pylint_score` and also store `py_pylint_score_excl_fatal`, which re-runs Pylint without the files that raised fatal messages.

**Limits.**

- The score mostly reflects style conventions, and a few noisy message types can dominate it.
- It isn't calibrated across project sizes.
- It can't tell a deliberate style choice from a mistake.

---

### Source lines of code (SLOC)

**What it measures.** Code size, counted in lines that contain source code. Blank lines and comment-only lines are not counted.

**Formula.** The sum over files of Radon's `sloc` field.

**How to read it.** Neither higher nor lower is better. SLOC describes size and verbosity, and it is the denominator for comment %.

**Tool.** Radon 6.0.1 (`radon raw`).

**Aggregation.** Sum over files.

**Limits.** SLOC depends on formatting style, since the same logic can take one line or five. On its own it says nothing about quality.

---

### Comment percentage

**What it measures.** Documentation density: how much comment text there is relative to code.

**Formula (PDF).**

```math
\text{comment \%} = \frac{\text{comments}}{\text{SLOC}} \times 100
```

Here `comments` is the sum of Radon's `comments` field (lines containing a `#` comment, inline comments included), and SLOC is as above.

**How to read it.** Some commenting is good, but very high values can mean commented-out code rather than documentation. Treat the value as a description, not a score.

**Tool.** Radon 6.0.1 (`radon raw`).

**Aggregation.** Ratio of the repo totals, not a mean of per-file ratios.

**Limits.**

- Radon counts docstrings as `multi`, not `comments`, so a repo that documents with docstrings looks under-commented.
- It counts lines, not comment quality.
- SonarQube's `comment_lines_density` uses a different denominator. See [`metrics_mapping.md`](metrics_mapping.md).

---

### Bandit security findings

**What it measures.** The number of potential security problems found by Bandit's Python rule set, split into high, medium and low severity. Typical findings include `eval`, shell injection, hard-coded passwords, weak hashes, `assert` used for checks and unsafe deserialisation.

**Formula.** For each severity $s \in \{\text{high}, \text{medium}, \text{low}\}$:

```math
\text{Bandit}_s = \sum_{f} |\text{Issues}_s(f)|
```

**How to read it.** Lower is better. Keep the three levels separate, since one high finding weighs more than several low ones.

**Tool.** Bandit 1.9.4, default profile, all confidence levels counted.

**Aggregation.** Summed over all Python files.

**Limits.**

- Detection is rule-based pattern matching. It misses logic flaws and data flow across files.
- It reports false positives. `assert` in test files is by far the most common low finding: rule B101 accounts for 29,830 of the 31,835 low findings (94%) across the 48 Python repos.
- Bandit's severity levels are its own and don't correspond to SonarQube's.
- Bandit honours `# nosec` comments and SonarQube honours `NOSONAR`, so teams can suppress findings. I don't record how many suppressions each repo has.

---

### Functional correctness

**What it measures.** Whether code produces the expected output on a benchmark's tests.

**Formula (PDF).** For instance $i$, $C_i = 1$ if all tests pass and $0$ otherwise.

**Status.** Out of scope for Deliverable 1. The capstone repos don't share a test harness, and running their tests would mean installing each project's dependencies and services. This could be revisited for repos that ship runnable test suites.

---

### Pre/post deltas

The PDF measures the effect of a patch as the post-patch value minus the pre-patch value:

```math
\begin{aligned}
\Delta CC_{avg} &= \frac{1}{|B_{post}|} \sum_{b \in B_{post}} CC_b \;-\; \frac{1}{|B_{pre}|} \sum_{b \in B_{pre}} CC_b \\
\Delta CC_{max} &= \max_{b \in B_{post}} CC_b \;-\; \max_{b \in B_{pre}} CC_b \\
\Delta MI &= MI_{avg}^{post} - MI_{avg}^{pre} \\
\Delta Pylint &= Pylint^{post} - Pylint^{pre} \\
\Delta Bandit_s &= \sum_{f \in F} |Issues_s^{post}(f)| \;-\; \sum_{f \in F} |Issues_s^{pre}(f)|, \quad s \in \{high, medium, low\}
\end{aligned}
```

$B$ is the set of blocks (functions, methods, classes) in the modified files, and $F$ is the set of modified files. This follows Chen and Jiang (2025), who compare agent patches against the code before the patch.

Deliverable 1 takes one snapshot per repo (the `HEAD` of the default branch), so no deltas are computed yet. `results/results.csv` stores one row per (repo, commit), so D3 can add more commits per repo and compute the same deltas, either between consecutive snapshots or between the before and after versions of the files a single commit changed.

---

## Limitations

The PDF treats all of these metrics as interpretable proxies, not complete measures of software quality:

- **MI and CC** focus on structural maintainability risk.
- **Pylint** covers style and static code-quality conventions.
- **SLOC and comment %** describe verbosity and documentation.
- **Bandit** only finds rule-based security issues.

None of them matches a professional developer's judgement of whether code is maintainable or good in production. The results should be read as relative comparisons between groups measured with the same procedure.

The PDF also adds a qualitative code-book analysis on top of the metrics, covering communication style, response structure, code explanations, readability, commenting quality, error handling and hallucination patterns. A version of this for student repos is a possible later extension, for example coding a sample of files for readability, commenting quality and error handling. It would complement the metrics, not replace developer judgement.

---

## References

- Antinyan, V., Staron, M., Sandberg, A. (2017). Evaluating code complexity triggers, use of complexity measures and the influence of code complexity on maintenance time. *Empirical Software Engineering* 22(6), 3057-3087.
- Börstler, J., Bennin, K.E., Hooshangi, S., Jeuring, J., Keuning, H., Kleiner, C., MacKellar, B., Duran, R., Störrle, H., Toll, D., et al. (2023). Developers talking about code quality. *Empirical Software Engineering* 28(6), 128.
- Chen, Z., Jiang, L. (2025). Evaluating software development agents: Patch patterns, code quality, and issue complexity in real-world GitHub scenarios. *SANER 2025*, 657-668.
- Chowdhury, S., Holmes, R., Zaidman, A., Kazman, R. (2022). Revisiting the debate: Are code metrics useful for measuring maintenance effort? *Empirical Software Engineering* 27(6), 158.
- Lacchia, M. Radon. <https://github.com/rubik/radon> (version 6.0.1 used here).
- McCabe, T.J. (1976). A complexity measure. *IEEE Transactions on Software Engineering* SE-2(4), 308-320.
- Oman, P., Hagemeister, J. (1992). Metrics for assessing a software system's maintainability. *Proc. Conference on Software Maintenance 1992*, 337-338.
- Pantiuchina, J., Lanza, M., Bavota, G. (2018). Improving code: The (mis) perception of quality metrics. *ICSME 2018*, 80-91.
- Pylint contributors. Pylint. <https://github.com/pylint-dev/pylint> (version 4.0.9 used here).
- PyCQA. Bandit. <https://github.com/PyCQA/bandit> (version 1.9.4 used here).