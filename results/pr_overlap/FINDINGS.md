# PR file-overlap: findings against the TAs' observation

Numbers are from the CSVs in this folder (`pr_level.csv`, `repo_level.csv`, `year_comparison.csv`, `year_summary.csv`, `validation_changedfiles.csv`), regenerated after two changes to `23_pr_overlap.py`: a PR with no other PR in its window has an undefined overlap (empty, not 0), and the `*_excl_integration` columns also drop release PRs from the reference sets. Read `ASSUMPTIONS.md` for the limits. Descriptive only; no hypothesis tests were run.

## What the TAs wanted
Students make few PRs early in the term and many later. The TAs suspect the later PRs are partly AI redoing earlier work, because they touch the same files as earlier merged PRs. Agreed first approach (Discord, 2026-10-23): file overlap, i.e. how often a PR touches files from PRs merged in the previous weeks. Open caveat: some rework is normal iteration, so a baseline is needed.

## What was measured
For each merged PR, the share of its source files that other PRs merged in the previous 14 or 28 days also touched (73 repos, 2022-2026, 12,971 kept PRs; 8,101 of them have a defined `code` overlap: 4,732 have no source file and 138 have no other PR in the 28-day window). Plus per-week and first-half vs second-half views of each repo's term. The 2022 repos (before AI coding tools were common) serve as the baseline.

## Result by claim

| TA claim or question | What the data shows | Verdict |
|---|---|---|
| Few PRs early, many later | Second / first half PR ratio (median over repos): 1.08 (2022, 3 repos), 1.46 (2023), 1.26 (2024), 1.24 (2025), 1.40 (2026). Weekly PR count rises in 73-95 % of 2023-25 repos. | Seen in all years, including 2022, so it is normal in this course. |
| Later PRs touch files from earlier merged PRs | Mean 28-day code overlap per PR is 0.67-0.75 in every year; 73-83 % of PRs have at least half their files in the previous 28 days' set (see table below). | Overlap is high everywhere. Without a null baseline (placebo window, shuffled merge times) this does not show it is more than central files being touched often. |
| This overlap is higher in the AI era than before | PR-pooled 2022 baseline 0.71; 2023 0.75, 2024 0.67, 2025 0.69, 2026 0.71. Resampling whole repos gives 95 % intervals that overlap across 2022-2025 (2022 0.68-0.81 from 3 repos; 2023 0.71-0.78; 2024 0.64-0.70; 2025 0.66-0.72). Without release PRs: 0.71, 0.65, 0.65, 0.68, 0.70. | No evidence of a difference at this resolution: the pre-AI repos are not lower, but 2022 rests on 3 repos (2 without release PRs, where the interval means little) and 2026 on one. Years also differ in term length, team size and course process (2022 was a summer term). |
| Overlap rises as the term goes on | Second-half mean overlap is higher than first-half in 50 % (2023), 46 % (2024) and 55 % (2025) of repos (median 0.72 -> 0.73, 0.65 -> 0.64, 0.64 -> 0.69). Among PRs with a defined value, those in a repo's first 28 days score 0.51-0.72 vs 0.69-0.77 later, in every year including 2022. | Weak, and partly a warm-up artefact (little history to overlap with at the start). |
| The extra overlap is AI redo | Overlap cannot tell redo from bug fixes, refactors, review rounds or follow-up work on the same feature. | Cannot be answered with this feature. It is at most an upper bound. |

## Overlap by year (28-day window, `code` files)

| year | repos (with a defined value) | PRs with a defined value | mean overlap share (PR-pooled) | 95 % interval, repos resampled | median over repos | PRs with share >= 0.5 | PRs touching any recent file |
|---|---|---|---|---|---|---|---|
| 2022 | 4 (3) | 127 | 0.71 | 0.68-0.81 | 0.72 | 74 % | 91 % |
| 2023 | 22 | 1,968 | 0.75 | 0.71-0.78 | 0.75 | 81 % | 93 % |
| 2024 | 26 | 2,588 | 0.67 | 0.64-0.70 | 0.66 | 73 % | 91 % |
| 2025 | 20 | 3,297 | 0.69 | 0.66-0.72 | 0.67 | 77 % | 91 % |
| 2026 | 1 | 121 | 0.71 | none (one repo) | 0.71 | 83 % | 99 % |

The same measure on all files that pass hygiene (`all`, not only source) is lower: 0.50, 0.64, 0.54, 0.62, 0.47 (141 PRs without history are left out). 2022 is n=4 (database has 1 PR, hot-desking-deploy 8, so it rests on two repos) and 2026 is n=1.

## Why overlap is so high everywhere
- Teams work on a small set of central files, and most PRs are small (median 3-7 files after hygiene).
- 53-73 % of merged PRs in 2023-25 target a non-default branch (usually `dev`). The `dev` -> `main` release PRs re-contain recent work and score 0.77-1.00 vs 0.67-0.71 for the other PRs; 31 % of 2023's PRs are of this kind. They are flagged `integration_pr` and a column without them is given.
- Start-of-term PRs have little history, which pulls early-term overlap down and makes any later rise look larger. The very first PR of a repo, and any PR after a gap longer than the window, is now left out of the means instead of counting as 0.

## What this supports and what it does not
- **Supports:** a descriptive table of how much rework of recent files happens per PR, per week and per half-term, for every year, with 2022 as a first reference. The TAs' timing observation is real.
- **Does not support:** saying that overlap measures AI redo, that one year or team is higher than another, or setting a threshold to flag a team. There is no label for "AI redo" to calibrate against, and the baseline is small (2022) or not clean (2023 already had ChatGPT and Copilot available).
- **Quality of the file lists:** 78 % of PRs match GitHub's `changedFiles` exactly and 87 % within one file; our union is larger for about 1 PR in 5. 96 PRs (0.7 %) have more than 100 commits and are flagged.

## Suggested discussion points for the meeting
1. The first-half / second-half PR growth also appears in 2022, so by itself it is not a sign of AI. Do the TAs have a view on how much growth is expected?
2. Release and integration PRs distort the measure. Drop them, keep them flagged, or measure on feature PRs only?
3. Could a placebo baseline work (overlap with PRs 60-90 days back instead of the last 14/28), or a shuffled merge-time null? Not done here.
4. To separate fixes and refactors from redo we need content, not only file names: git blame (how much merged code is rewritten within weeks) was the Discord follow-up idea.
5. Is the `code` extension list right? It omits Vue, Svelte, Dart and notebooks, and 35-41 % of PRs have no `code` file.
6. Is a merged-PR view enough, given that teams who push straight to `main` have no PRs to measure?
