# PR file-overlap: data dictionary

Produced by `scripts/23_pr_overlap.py`. No GitHub logins or emails in any file. Years: 2022 (4 repos), 2023-25 (68 repos, `config/repo_selection.txt`), 2026 (1 repo). `repo` is the clone folder name (for 2026: `capstone-project-team-11`).

## Which PRs are in the tables
- Merged PRs only (`mergedAt` set).
- Dropped: bot authors (login ends in `[bot]`, contains `dependabot`, or matches the bot pattern of `08_process_metrics.py`, which also catches `github-classroom`, `github-actions`, ...; GraphQL returns bot logins without the `[bot]` suffix), and PRs that have no file left after hygiene. Dropped PRs are counted in `repo_level.csv` and are in neither the measured set nor any reference set.
- Kept but flagged: PRs into a non-default branch, integration PRs, truncated commit lists, AI-agent authors.

## Files of a PR
Union of the files changed by the PR's non-merge commits (oids from `prs.json`, `git log --no-walk --no-merges --no-renames --name-only`). `--no-renames`: a rename counts the old and the new path. Raw = that union. `all` = raw minus lockfiles, `node_modules`/`dist`/`build`/`target`/venv/`site-packages`/`__pycache__` directories (the SonarQube scan exclusions; `build/` is kept for the one team that keeps source there), `vendor`/`bower_components`/`third_party`, `*.min.js|css`, `.d.ts`, `_pb2.py`, `.designer.cs`, `.g.dart`, `.map`, `.pyc`, `.DS_Store`, and the vendored packages of `hot-desking-deploy`. `code` = `all` restricted to the extensions of `EXT_LANG` in `20_file_detect.py` (`.py .js .jsx .ts .tsx .java .c .cc .cpp .h .hpp .cs .go .php .rb .rs .kt .swift .m .sql .html .css`). `code` is the primary variant.

## Overlap
For a merged PR P at time t, R_W = union of the files (same variant) of all other kept PRs of the same repo with `mergedAt` in (t - W days, t), W in {14, 28}. Both ends open; PRs with an identical timestamp are ordered by PR number, so the lower number counts as earlier and is in the other's window (the tie is the only case where the window includes `t`). `overlap_share_W = |files(P) ∩ R_W| / |files(P)|`; `overlap_any_W = 1` if the intersection is non-empty. A PR with no `code` file has no `code` overlap (empty cell, not 0), and does not enter the `code` reference sets. **A PR with no other PR in its window has no history to overlap with: its share and `overlap_any` are empty (undefined), not 0**, and it is not counted in `n_defined_*` or in any mean.

## pr_level.csv (one row per kept merged PR; key: year, repo, pr_number)
| column | meaning |
|---|---|
| year, repo, pr_number | key |
| merged_at, merged_week | UTC timestamp; ISO week `YYYY-Www` |
| days_since_first_merge | days after the repo's first kept merged PR (use it to drop the warm-up, see ASSUMPTIONS) |
| n_files_raw / n_files_all / n_files_code | file counts before hygiene / after hygiene / source files only |
| base_branch, is_default_branch | PR target branch; default branch from GitHub (2022, 2026) or `origin/HEAD` of the clone |
| flags | `;`-separated: `non_default_base`, `files_incomplete`, `integration_pr` (the PR's head branch is the base branch of another PR of the repo, e.g. dev -> main), `ai_agent_author` (Copilot/Cursor-type agent account). Empty = none |
| commits_total | GitHub's commit count of the PR |
| commits_listed | commits returned by the query (at most the first 100) |
| commits_nonmerge | listed commits that are not merge commits |
| commits_missing_locally | listed oids not found in the clone |
| files_complete | false if `commits_total > commits_listed` or any listed commit is missing |
| overlap_share_{code,all}_{14,28} | share of the PR's files in the reference set |
| overlap_any_{code,all}_{14,28} | 1 if that share > 0 |
| overlap_share_{code,all}_{14,28}_excl_integration | the same share, with `integration_pr` PRs neither measured (empty) nor part of any reference set |
| ref_prs_{v}_{W} | number of other PRs in the window (0 = no history, share is then empty) |
| ref_files_{v}_{W} | size of the reference file set (use it to control for how much was there to overlap with) |

## repo_level.csv (one row per repo; key: year, repo)
`n_merged_prs` (kept), `n_excluded_bot`, `n_excluded_bot_beyond_spec` (bots caught only by the wider pattern), `n_excluded_no_files`, `first_merged`, `last_merged`, `span_days`, `n_weeks`, `median_files_all/code`, `share_prs_no_code_files`, `share_files_incomplete`, `share_non_default_base`, `share_ai_agent_author`, `n_integration_prs`.
Term shape: `prs_first_half` / `prs_second_half` (calendar midpoint between first and last kept merge; a PR exactly at the midpoint is in the second half), `half_ratio` = second / first (empty when the first half has no PR), `weekly_pr_count_slope` = OLS slope of weekly PR count over all weeks including empty ones (PRs per week per week, descriptive; empty below 3 weeks).
Per variant v and window W: `n_defined_v_W` (PRs with a defined share), `mean_overlap_share_v_W`, `mean_overlap_any_v_W`, `share_prs_overlap_ge_half_v_W`, `mean_overlap_share_v_W_first_half`, `..._second_half`, and `mean_overlap_share_v_W_excl_integration` (mean of the `*_excl_integration` column of `pr_level.csv`: release PRs are neither measured nor part of any reference set). Means are over PRs with a defined share. Cells are empty where nothing is defined (e.g. `database` has 1 PR).

## weekly.csv (key: year, repo, week_index)
One row per ISO week from the week of the repo's first kept merge to the week of its last, empty weeks included. `n_prs`, and per variant and window `n_defined_*`, `mean_overlap_share_*`, `share_prs_overlap_ge_half_*` (share of PRs with overlap >= 0.5). Empty cells in weeks with no PR.

## validation_changedfiles.csv
Raw file count (before hygiene) against GitHub's `changedFiles`, only for PRs whose commit list is complete. Rows per year, per repo and pooled (`repo` = ALL, `year` = ALL), for `scope` = `all_prs` (any state) and `merged_prs`. `share_exact`, `share_within_1`, `share_union_larger` / `share_union_smaller` (our count above / below GitHub's), `median_ratio`, `ratio_p25/p75`, `median_diff`, `share_incomplete` (PRs left out for an incomplete list).

## year_comparison.csv
Per year, variant (`code`, `all`), window (14, 28) and basis (`all_kept`; `excl_integration` = release PRs neither measured nor in any reference set): `n_repos`, `n_prs_defined` (PRs with a defined share), `pooled_mean` (mean over PRs), `repo_median` and `repo_mean` (over the repos' own means), and `ci95_low` / `ci95_high`, the 2.5 and 97.5 percentiles of the pooled mean over 2,000 resamples of whole repos (seed 448). Empty for a year with one repo. With 2-3 repos the interval is not informative.

## year_summary.csv
Long format: per year and per numeric `repo_level.csv` column, `n_repos_defined`, `n_repos`, `median`, `mean` over repos. `note` repeats that 2022 is n=4 (database has 1 PR, hot-desking-deploy 8) and 2026 is n=1. Descriptive only; no tests.
