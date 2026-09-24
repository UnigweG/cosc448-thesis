# Metric definitions

Source: my supervisor's metrics document, *Metrics* (May 20, 2026), stored at
`docs/references/Metrics.pdf`. That document was written for an evaluation of
LLM-generated Python code (LiveCodeBench and SWE-bench Verified). I reuse the same
definitions on student capstone repositories, so wherever the unit of analysis
changes (a whole repository instead of a single solution or patch) I state how I
adapted it. Where this file and the PDF disagree, the PDF is the reference.

Tool versions used (pinned in `requirements.txt`): Radon 6.0.1, Pylint 4.0.9,
Bandit 1.9.4, running on Python 3.14.0.

## Why these metrics

The PDF groups the metrics into four quality dimensions: functional correctness,
code quality, maintainability and security. All of them can be computed
automatically with open-source tools, so they are reproducible and cheap to run on
many repositories. The case for using them comes from two lines of work. Chowdhury
et al. (2022) found, across roughly 730K Java methods in 47 projects, that code
metrics help predict which methods will change later, even after controlling for
method size, so they carry information beyond plain size. Antinyan et al. (2017)
report that practitioners see complexity as hurting readability, understandability,
modifiability and maintenance time.

The PDF is also clear that these are indicators for relative comparison and not a
replacement for expert review. Pantiuchina et al. (2018) show that metric changes
do not always line up with what developers perceive as quality improvements, and
Börstler et al. (2023) show that properties developers care about (readability,
structure, comprehensibility) are hard to capture with static metrics. I use the
metrics the same way: to compare repositories and cohorts measured with the same
procedure, not as absolute judgements of a team's code.

## Unit of analysis and file set

- One measurement is a repository at a specific commit (a "snapshot").
- The Python file set is `git ls-files '*.py'` at that commit. Using tracked files
  only keeps virtual environments, installed packages and other untracked files out.
- Repositories with no tracked Python files get NA for the Python metrics and
  `python_file_count = 0`.

## Aggregation rules (repo level)

These follow the PDF's multi-file rules for SWE-bench Verified, applied to all
tracked Python files of the repo instead of only the files touched by a patch.

| Metric | Rule |
|---|---|
| CC | Pool every per-block value (functions, methods, classes) from all files into one list; CCavg = mean of the list, CCmax = maximum of the list |
| MI | Compute MI per file; repo MI = mean over files |
| Pylint | One Pylint run over all Python files together; take the overall score |
| Bandit | Sum the high, medium and low severity findings over all files |
| SLOC, comments | Sum over all files; comment % computed from the sums |

## Metrics

### Cyclomatic complexity: CCavg and CCmax

- **What it measures.** McCabe's (1976) cyclomatic complexity counts the linearly
  independent paths through a piece of code. In practice it is 1 plus the number of
  decision points (if/elif, loops, boolean operators, except clauses,
  comprehension conditions, and so on).
- **Formula.** For one block, CC = E - N + 2P on the control-flow graph, which Radon
  computes as 1 + number of decision points. At repo level, with B the pooled set of
  blocks:
  CCavg = (1/|B|) * sum over b in B of CC_b, and CCmax = max over b in B of CC_b.
- **How to read it.** Lower is better. CCavg describes the typical function. CCmax
  points at the single most complex block, which the PDF describes as the likely
  maintenance bottleneck. Radon's letter ranks are A (1-5), B (6-10), C (11-20),
  D (21-30), E (31-40), F (41+).
- **Tool.** Radon 6.0.1 (`radon cc`), default settings.
- **Aggregation.** Pooled blocks across all files (see above). Radon's default output
  lists functions, methods and classes. Nested functions (closures) are folded into
  their parent function and not listed separately. This matches the PDF's "functions,
  methods, or classes".
- **Limits.** A class block in Radon is derived from its methods' complexity, so
  including classes counts those methods twice in the pooled list. I keep it because
  the PDF lists classes as blocks. CC counts paths, not how hard the code is to read.
  A flat 30-case dispatch scores high but is easy to follow. CC also ignores naming,
  nesting depth and data complexity.

### Maintainability index (MI)

- **What it measures.** Oman and Hagemeister (1992) proposed MI as a single score
  for how easy code is to maintain. It combines size, complexity and comment density.
- **Formula (Radon's variant).**
  MI = max(0, 100 * (171 - 5.2 ln V - 0.23 G - 16.2 ln L + 50 sin(sqrt(2.4 C))) / 171),
  where V is Halstead volume, G is total cyclomatic complexity, L is SLOC and C is the
  percentage of comment lines. Radon counts multi-line strings (docstrings) as
  comments by default, and I keep that default.
- **How to read it.** Higher is better, on a 0-100 scale. Radon ranks A (> 19),
  B (10-19) and C (<= 9).
- **Tool.** Radon 6.0.1 (`radon mi`), default settings.
- **Aggregation.** Mean of per-file MI over all Python files. Every file counts the
  same regardless of size.
- **Limits.** The coefficients were fitted on 1990s industrial C and Pascal systems.
  Short files score near 100 whatever their quality. The mean over files lets many
  tiny files (for example empty `__init__.py`) push the repo score up.

### Pylint score

- **What it measures.** An overall rating of a file set's errors and its adherence to
  Python coding standards (PEP 8 style, naming, unused code, likely bugs, refactoring
  hints).
- **Formula.** Pylint's default evaluation:
  score = max(0, 10 - (5 * error + warning + refactor + convention) / statement * 10),
  where each term is a count of messages of that category and `statement` is the
  number of statements analysed.
- **How to read it.** Higher is better, up to 10. The score can hit the floor of 0 on
  code with many messages per statement.
- **Tool.** Pylint 4.0.9.
- **Aggregation.** One run over all of the repo's Python files together, as the PDF
  did for SWE-bench ("all files at once, as PyLint supports it"). 10-minute timeout
  per repo; NA if it fails.
- **Settings.** The PDF used default parameters for LiveCodeBench. For SWE-bench
  Verified it disabled four import-related checks (import-error, no-name-in-module,
  wrong-import-position, ungrouped-imports), because imports could fail when the
  surrounding files were missing. **Decision for this project:** I disable the same
  four checks, since the capstone repos' dependencies are not installed in my
  environment and import errors would otherwise dominate the score. All other
  settings stay at their defaults, and repo-level `.pylintrc` files are ignored so
  every repo is scored the same way.
- **Limits.** The score mostly reflects style conventions, and a few noisy message
  types can dominate it. It is not calibrated across project sizes, and it cannot
  tell a deliberate style choice from a mistake.

### Source lines of code (SLOC)

- **What it measures.** The size of the code in lines that contain source code, not
  counting blank and comment-only lines.
- **Formula.** SLOC = sum over files of Radon's `sloc` field.
- **How to read it.** Neither higher nor lower is better. It measures size and
  verbosity, and it is the denominator for comment %.
- **Tool.** Radon 6.0.1 (`radon raw`).
- **Aggregation.** Sum over files.
- **Limits.** It depends on formatting style, since the same logic can span one line
  or five. It says nothing about quality by itself.

### Comment percentage

- **What it measures.** Documentation density: how much comment text there is
  relative to code.
- **Formula (PDF).** comment % = comments / SLOC * 100, with comments = sum of Radon's
  `comments` field (lines containing a `#` comment, including inline comments) and
  SLOC as above.
- **How to read it.** Some commenting is good. Very high values can mean
  commented-out code rather than documentation, so the value is read as a
  description, not a score.
- **Tool.** Radon 6.0.1 (`radon raw`).
- **Aggregation.** Ratio of the repo totals (not a mean of per-file ratios).
- **Limits.** Docstrings are counted by Radon as `multi`, not `comments`, so a repo
  that documents with docstrings looks under-commented. The metric counts lines, not
  comment quality. Note that SonarQube's `comment_lines_density` uses a different
  denominator (see `metrics_mapping.md`).

### Bandit security findings (high / medium / low)

- **What it measures.** The number of potential security problems found by Bandit's
  rule set for Python, for example `eval`, shell injection, hard-coded passwords,
  weak hashes, `assert` used for checks, or unsafe deserialisation.
- **Formula.** For each severity s in {high, medium, low}:
  Bandit_s = sum over files f of |Issues_s(f)|.
- **How to read it.** Lower is better. Keep the three levels separate, since one high
  finding weighs more than several low ones.
- **Tool.** Bandit 1.9.4, default profile, all confidence levels counted.
- **Aggregation.** Summed over all Python files.
- **Limits.** Detection is rule-based pattern matching. It misses logic flaws and
  cross-file data flow, and it reports false positives (`assert` in test files is a
  very common low finding). Bandit's severity levels are its own and do not
  correspond to SonarQube's severities.

### Functional correctness

- **What it measures.** Whether code produces the expected output on the benchmark's
  tests.
- **Formula (PDF).** For instance i, C_i = 1 if all tests pass, 0 otherwise.
- **Status here.** Out of scope for Deliverable 1. Capstone repos do not share a test
  harness, and running their tests would mean installing each project's dependencies
  and services. It could be revisited for repos that ship runnable test suites.

### Pre/post deltas

The PDF measures the effect of a patch as post-patch minus pre-patch values:

- ΔCCavg = (1/|B_post|) Σ_{b∈B_post} CC_b − (1/|B_pre|) Σ_{b∈B_pre} CC_b
- ΔCCmax = max_{b∈B_post} CC_b − max_{b∈B_pre} CC_b
- ΔMI = MI_avg^post − MI_avg^pre
- ΔPylint = Pylint^post − Pylint^pre
- ΔBandit_s = Σ_{f∈F} |Issues_s^post(f)| − Σ_{f∈F} |Issues_s^pre(f)|, for s in {high, medium, low}

Here B is the set of blocks (functions, methods, classes) in the modified files and F
is the set of modified files. This follows Chen and Jiang (2025), who compare agent
patches against the code before the patch.

Deliverable 1 takes one snapshot per repo (HEAD of the default branch), so no deltas
are computed yet. `results/results.csv` stores one row per (repo, commit), so D3
can add more commits per repo and compute the same deltas between consecutive
snapshots, or between the pre and post versions of a single commit's changed files.

## Limitations (from the PDF)

The PDF treats all of these metrics as interpretable proxies, not complete measures
of software quality. MI and CC focus on structural maintainability risk. Pylint
covers style and static code-quality conventions. SLOC and comment % describe
verbosity and documentation. Bandit only finds rule-based security issues. None of
them matches a professional developer's judgement of whether code is maintainable
or good in production. Results should therefore be read as relative comparisons
between groups measured under the same procedure.

The PDF adds a qualitative code-book analysis on top of the metrics. It covers
communication style, response structure, code explanations, readability,
commenting quality, error handling and hallucination patterns. A version of this
for student repos is a possible later extension, for example coding a sample of
files for readability, commenting quality and error handling. It would be a
complement to the metrics, not a replacement for developer judgement.

## References

- Antinyan, V., Staron, M., Sandberg, A. (2017). Evaluating code complexity triggers, use of complexity measures and the influence of code complexity on maintenance time. *Empirical Software Engineering* 22(6), 3057-3087.
- Börstler, J., Bennin, K.E., Hooshangi, S., Jeuring, J., Keuning, H., Kleiner, C., MacKellar, B., Duran, R., Störrle, H., Toll, D., et al. (2023). Developers talking about code quality. *Empirical Software Engineering* 28(6), 128.
- Chen, Z., Jiang, L. (2025). Evaluating software development agents: Patch patterns, code quality, and issue complexity in real-world GitHub scenarios. *SANER 2025*, 657-668.
- Chowdhury, S., Holmes, R., Zaidman, A., Kazman, R. (2022). Revisiting the debate: Are code metrics useful for measuring maintenance effort? *Empirical Software Engineering* 27(6), 158.
- Lacchia, M. Radon. https://github.com/rubik/radon (version 6.0.1 used here).
- McCabe, T.J. (1976). A complexity measure. *IEEE Transactions on Software Engineering* SE-2(4), 308-320.
- Oman, P., Hagemeister, J. (1992). Metrics for assessing a software system's maintainability. *Proc. Conference on Software Maintenance 1992*, 337-338.
- Pantiuchina, J., Lanza, M., Bavota, G. (2018). Improving code: The (mis) perception of quality metrics. *ICSME 2018*, 80-91.
- Pylint contributors. Pylint. https://github.com/pylint-dev/pylint (version 4.0.9 used here).
- PyCQA. Bandit. https://github.com/PyCQA/bandit (version 1.9.4 used here).
