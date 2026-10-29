# PR file-overlap: assumptions and cases it cannot handle

Discussion document for the next meeting with Dr. Hui. One approach (file overlap of a merged PR with PRs merged in the previous 14 / 28 days), its assumptions, and what it cannot tell us. Numbers are from `results/pr_overlap/*.csv`.

## What the feature measures
The share of a merged PR's source files that were also touched by other PRs merged in the previous W days. The TAs' idea is that late-term PRs redo earlier merged work, partly with AI. This feature records *rework of recent files*; it does not see who or what wrote the code.

## 1. Overlap is a proxy, and an upper bound on AI redo
Overlap includes normal iteration: bug fixes, refactors, review rounds, follow-up PRs on the same feature, merge-conflict fixes, and files that are simply central (routers, `App.jsx`, `models.py`). Nothing here separates those from AI redo. Reading a high overlap as "AI redoing earlier work" would be wrong; at most it is an upper bound. We do not have an independent label for "redo" to calibrate against.

**The 2022 baseline shows how high normal rework is.** In the 2022 repos (pre-AI) the mean 28-day code overlap is 0.69 (pooled over the 131 PRs with a defined value; 211 are kept; repo medians in `year_summary.csv`). Pooled over PRs it is 0.73 (2023), 0.66 (2024), 0.68 (2025), 0.70 (2026). The years are not separable at this resolution, and 2022 is not lower than the later years.

## 2. Things that distort the file lists
- **Squash / rebase merges.** The PR's own commits (GitHub's list) are used, not the merge result, so squash merges are fine for file lists; rebased commits keep their changes but the oids listed are the PR's. Not checked repo by repo.
- **No rename tracking.** `--no-renames`: a moved file counts as the old path (deleted) plus the new path (added). Moving a file therefore overlaps with the PRs that touched the old path, and a file renamed later is a new file with no history. We do not follow content across paths.
- **Force-pushes.** The commit list is the PR head's current history. Commits dropped by a force-push are not in it, and `refs/pull/N/head` only has the last head.
- **Stacked / integration PRs.** 53-73 % of merged PRs (2023-25) target a non-default branch: teams merge features into `dev` and release `dev -> main`. A release PR re-contains the files of all PRs merged into `dev` before it, so its overlap is high by construction. These are flagged `integration_pr` (31 % of 2023's PRs, 1.5-6 % in the other years). Their mean 28-day code overlap is 0.76-1.00 against 0.65-0.70 for the rest (`pr_level.csv`). They are *kept* in the main columns; `*_excl_integration` columns give the sensitivity, with release PRs removed from both the measured and the reference sets (a release PR is dated at its merge but re-contains older work, so as a reference it would stretch the window). A feature PR that is merged into `dev` and again in a release is also double-counted as reference.
- **Merge commits from the base branch inside a PR** are excluded from the file union (`--no-merges`), so files brought in by "merge main into my branch" are not counted. A conflict resolved inside such a merge commit is lost too. Whether base-branch commits end up in a PR's commit list after a rebase was not checked; if they do, they inflate that PR's file list.
- **Union of commits vs net diff.** A file touched and reverted stays in our list but not in GitHub's `changedFiles` (see 3).

## 3. Commit cap, missing commits and validation against GitHub
- The query lists the first 100 commits of a PR. 96 kept PRs (0.7 %) have more commits than listed; they are flagged `files_incomplete`. Their file sets are a lower bound. No listed commit was missing from the clones (`commits_missing_locally` is 0 for every kept PR).
- Validation (PRs with a complete list, raw count before hygiene vs GitHub's `changedFiles`, merged PRs):

| year | n PRs | exact match | within +-1 | our count larger | our count smaller | median ratio | p75 ratio |
|---|---|---|---|---|---|---|---|
| 2022 | 210 | 73.8 % | 83.8 % | 26.2 % | 0.0 % | 1.00 | 1.08 |
| 2023 | 3,312 | 71.5 % | 80.2 % | 27.4 % | 1.1 % | 1.00 | 1.04 |
| 2024 | 4,039 | 75.4 % | 85.1 % | 23.7 % | 0.9 % | 1.00 | 1.00 |
| 2025 | 5,236 | 84.2 % | 92.3 % | 15.1 % | 0.7 % | 1.00 | 1.00 |
| 2026 | 203 | 79.8 % | 87.7 % | 17.2 % | 3.0 % | 1.00 | 1.00 |
| all | 13,000 | 78.0 % | 86.8 % | 21.1 % | 0.9 % | 1.00 | 1.00 |

  The median ratio is 1.0 everywhere, but about one PR in five has more files in our union than GitHub reports (the gap is systematic and mostly one-directional: our count is smaller than GitHub's for about 1 % of PRs, 3 % in 2026). That is what the union-of-commits (touched then reverted, renames counted twice) is expected to give; we did not separate the causes. The match is worst in a few 2023 repos (`year-long-project-team-13`: 39 % exact). Per-repo numbers are in `validation_changedfiles.csv`. The file-level inputs are therefore not exact, and about a fifth of the PRs have a file count that differs from GitHub's, so a PR's share can be off by a file or more.

## 4. Windows and timing
- 14 and 28 days are arbitrary. Both are reported; they give similar patterns (28-day code shares are 0.04-0.10 higher than 14-day ones in the year medians).
- PRs merged the same day (or the same minute) count as "recent" to each other. A burst of five PRs merged before a deadline overlaps heavily with itself even if each is independent work. Merge time, not work time, is used: a PR open for two weeks is placed at its merge.
- **Warm-up (left censoring).** In the first 28 days after a repo's first merge there is little history to overlap with: mean 28-day code overlap in those PRs is 0.45-0.66 against 0.68-0.77 later, in every year including 2022 (`days_since_first_merge`). Any rise of overlap through a term is partly this. The term-shape columns do not remove it.
- **Volume confounds share.** More PRs in a window means a larger reference set, so a higher overlap with no change in behaviour. `ref_prs_*` and `ref_files_*` are given for that reason; no adjustment is made.

## 5. What the numbers can and cannot support
- **The TAs' observation (few PRs early, many later) is visible**, but it is also present in 2022: median second / first half ratio of kept merged PRs is 1.08 (2022, 3 repos with at least 2 PRs), 1.46 (2023), 1.26 (2024), 1.24 (2025), 1.40 (2026). Weekly PR count slopes are positive in 73-95 % of 2023-25 repos. So more PRs late in the term is normal in this course and is not by itself a sign of AI.
- **Overlap in the second half is higher than in the first half in only about half the repos** (2023: 55 %, 2024: 54 %, 2025: 55 %; median share 0.71 -> 0.72, 0.63 -> 0.63, 0.63 -> 0.68). Given the warm-up effect that is a weak signal.
- **Baseline.** 2022 is 4 repos (3 with more than one PR; `database` has 1 PR and `hot-desking-deploy` 8; the others 81 and 158 PRs), so it is a weak baseline: its numbers rest on two large repos. 2023 (September 2023 to April 2024) came after ChatGPT and Copilot were widely available and may already contain AI use, so it cannot be called clean either. 2026 is one repo. Year comparisons are descriptive and no tests were run.
- Supported: a descriptive table of how much rework of recent files occurs per PR, per week and per term half, in every year, with the 2022 level as a first reference. Not supported: any statement that overlap measures AI redo, that a year or team is higher than another, or a threshold for flagging a team.

## 6. Other limits
- **`code` uses the 20_file_detect extension list.** It leaves out `.vue .svelte .dart .ipynb .mjs .kts .scala .sh .yml/.yaml .json .md`. Frontend code in Vue/Svelte/Dart is missed, and 35-41 % of kept PRs have no `code` file (docs, config, assets), so their `code` overlap is empty. About 55 % of the files that pass hygiene are not source files (images, Unity `.meta`/`.prefab`, `.md`, `.json`, committed `.dll`), which is why `all` is much lower than `code`.
- Hygiene works on paths only. Generated or vendored files without a recognisable path (a library copied into `src/`) are kept.
- Bots: besides `[bot]` / `dependabot`, accounts such as `github-classroom` are excluded (109 PRs, 2 of them outside the literal rule). One kept PR is by an AI-agent account (flagged).
- Merged PRs only. Unmerged and abandoned PRs, direct pushes to the default branch, and work that never goes through a PR are invisible. Teams that commit directly to `main` look like they have no PRs.
- Files are paths, not content. A one-line change and a full rewrite of a file are both an overlap of 1 file. The share is per file, not per line.
- Clock: GitHub timestamps are UTC; the ISO weeks start on Monday UTC.

## Cases it cannot handle (for discussion)
1. Separating a bug fix, refactor or review round from an AI rewrite of the same file (needs content: git blame / diff size / how much of the earlier lines survive; the follow-up ideas in the Discord).
2. Release / integration PRs and stacked PRs, where overlap is high by construction; an agreed treatment is needed (drop, keep flagged, or measure on the feature PRs only).
3. Teams that do not use PRs, or squash many weeks of work into one PR.
4. A baseline for "normal" overlap: 2022 is small, 2023 is not clean. A within-repo baseline (e.g. overlap with *older* PRs, 60-90 days back, as a placebo for the 14/28-day windows) or a shuffled-merge-time null would help, but is not done here.
5. The warm-up and volume effects on any trend through the term.
6. Moved / renamed files, and generated or vendored files that hygiene cannot see.
7. Who made the change: no author-level numbers are computed (no logins are stored), so a single student redoing their own work and a teammate redoing someone else's look the same.
