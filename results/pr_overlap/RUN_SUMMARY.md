# PR file-overlap run summary

Run 2026-10-28, regenerated 2026-10-29 after the review changes (undefined overlap without history, release PRs removed from the reference sets of the `excl_integration` columns, `year_comparison.csv`), on branch `feat/pr-overlap` (stacked on `d2-v3`); the full run takes about 10 s because everything comes from local git plus the saved `prs.json`. All numbers are read from the CSVs in this folder.

## What ran
- `scripts/07b_github_extra.py`: PRs and issues for the five 2022/2026 repos into `data/github/<year>/<repo>/` (plus `meta.json` with the GitHub default branch), and `refs/pull/*` fetched into their clones. 81 / 1 / 8 / 158 PRs (2022) and 228 PRs (2026), PR heads fetched for all of them. Read-only (GraphQL query, `git fetch`).
- `scripts/23_pr_overlap.py`: files per PR from git, hygiene, overlap for W = 14 and 28 and variants `code` (primary) and `all`, term shape, validation against `changedFiles`. No API calls, no models.

## Counts per year
| year | repos | PRs | merged | bots dropped | no files left | kept (in `pr_level.csv`) |
|---|---|---|---|---|---|---|
| 2022 | 4 | 248 | 211 | 0 | 0 | 211 |
| 2023 | 22 | 4,203 | 3,343 | 109 | 21 | 3,213 |
| 2024 | 26 | 4,468 | 4,097 | 0 | 18 | 4,079 |
| 2025 | 20 | 5,683 | 5,266 | 0 | 4 | 5,262 |
| 2026 | 1 | 228 | 206 | 0 | 0 | 206 |
| all | 73 | 14,830 | 13,123 | 109 | 43 | 12,971 |

Files: `pr_level.csv` 12,971 rows, `repo_level.csv` 73, `weekly.csv` 1,981, `validation_changedfiles.csv` 158, `year_summary.csv` 225, `year_comparison.csv` 40.

## Validation against GitHub's `changedFiles` (merged PRs, complete commit lists)
Exact match 71.5-84.2 % by year (78.0 % pooled), within +-1 file 80.2-92.3 % (86.8 % pooled), median ratio 1.00 in every year. Our union is larger than GitHub's for 21 % of PRs and smaller for 0.9 %. Table in `ASSUMPTIONS.md` section 3. Truncated lists: 96 kept PRs (0.7 %) have more than 100 commits (flag `files_incomplete`); no listed commit was missing from the clones.

## Verification
- All 73 repos present (68 in `config/repo_selection.txt` + 5), none empty except `2022/database`, which has 1 PR (its term-shape columns are empty).
- No duplicate keys in `pr_level.csv` (year, repo, pr_number), `repo_level.csv` or `weekly.csv`. Merged PR counts per year match `prs.json`: merged = kept + bots + no-files.
- No empty cell where a value is defined: `code` overlap is empty exactly for the 4,732 kept PRs with no `code` file plus the 138 with no other PR in their 28-day window (186 for 14 days); `all` overlap is empty only for the 141 without history (182 for 14 days); all shares in [0, 1].
- Three PRs recomputed by hand with a separate implementation (plain `git show` per commit, no code shared with the script) agree on file count and 28-day code overlap: 2022 api-development-and-testing PR 89 (3 files, 0.333), 2024 capstone-project-best-looking PR 267 (2 files, 0.5), 2026 capstone PR 167 (30 files, 0.167).
- `pytest tests`: 71 passed (`tests/test_pr_overlap.py`: 29 tests with a fixture git repo).

## Findings worth a look (descriptive; see ASSUMPTIONS.md for why none of them is evidence of AI redo)
- Mean 28-day code overlap over PRs with a defined value: 2022 0.71, 2023 0.75, 2024 0.67, 2025 0.69, 2026 0.71 (without release PRs 0.71, 0.65, 0.65, 0.68, 0.70). Repo-resampled 95 % intervals overlap across 2022-2025 (`year_comparison.csv`). The pre-AI 2022 repos are not lower.
- Second / first half PR ratio (repo median): 1.08 (2022, 3 repos), 1.46, 1.26, 1.24, 1.40. More PRs late in the term also happens in 2022.
- Warm-up: PRs in the first 28 days of a repo have lower overlap (0.51-0.72) than later PRs (0.69-0.77) in every year, among PRs with a defined value.
- 53-73 % of merged PRs in 2023-25 go into a non-default branch (usually `dev`); `integration_pr` release PRs (31 % of 2023's PRs) score 0.77-1.00 vs 0.67-0.71.

## Caveats
Overlap is a proxy that includes normal iteration; 2022 is n=4 (database 1 PR, hot-desking 8) and 2026 is n=1, so year comparisons are descriptive and no test was run. `code` uses the `20_file_detect.py` extension list (no Vue, Svelte, Dart, notebooks). Bots were matched with the wider pattern of `08_process_metrics.py` (2 extra PRs beyond the literal `[bot]`/`dependabot` rule). Integration PRs and the warm-up are flagged, not removed. Details: `ASSUMPTIONS.md`.

## Rerun
```
.venv/bin/python scripts/07b_github_extra.py                 # 2022 + 2026: PR/issue JSON, PR heads (skips what exists)
.venv/bin/python scripts/23_pr_overlap.py > logs/pr_overlap/run.log 2>&1   # everything
.venv/bin/python scripts/23_pr_overlap.py --only 2022/database             # one repo -> logs/pr_overlap/test/
.venv/bin/python -m pytest -q tests
```
