# Team process metrics and AI signals

Computed by `scripts/08_process_metrics.py` from the clones (all branches plus every PR
head under `refs/pull/`) and the GitHub API data saved by `scripts/07_github_api.py`.
Outputs: `results/process_metrics.csv` and `results/ai_signals.csv`, one row per repo.
Both files hold aggregates only, with no names, emails or logins.

The metric categories follow the supervisor's list: repository evolution, code quality
(see `metrics_definitions.md`), review process, collaboration and development velocity.

## Common rules

- **Window.** A commit counts if its author date is on or after the repo's creation date
  on GitHub and on or before the snapshot commit (the HEAD measured by SonarQube and
  Radon). This drops the starter-template history that the 2024 and 2025 repos begin
  with. PRs and issues count if they were opened inside the same window.
- **People.** Author names, email addresses and GitHub logins are merged into one person
  when they share a normalised name (lowercase, letters and digits only), an email or a
  login. The API links commit emails to logins, which joins most aliases. Teaching
  assistants who committed are counted like anyone else; the core-contributor count
  (at least 5 percent of commits) is the measure that leaves them out.
- **Bots and agents.** Dependabot, GitHub Actions, GitHub Classroom and other `[bot]`
  accounts are removed. AI coding agents (copilot-swe-agent, Cursor agent, Claude,
  Codex) and AI reviewers (copilot-pull-request-reviewer, CodeRabbit, ...) are removed
  from the team figures and counted only as AI signals.
- **Team commits** are non-merge commits by people.

## Repository evolution (git)

| Column | Definition |
|---|---|
| `evo_team_commits` | team commits in the window |
| `evo_span_days` | days from the first to the last team commit (the active period) |
| `evo_commits_per_day`, `evo_commits_per_week` | team commits / span, per day and per week |
| `evo_weeks_active_pct` | share of 7-day periods, counted from the first team commit, with at least one team commit |
| `evo_authors` | people with at least one team commit |
| `evo_median_commits_per_author`, `evo_median_active_days_per_author` | medians over those people; an active day is a UTC date with a commit |
| `evo_branches` | branches on GitHub when the repo was fetched |
| `evo_prefixed_branches_pct` | branches named `feature`, `feat`, `fix`, `bugfix`, `hotfix`, `bug`, `refactor`, `chore`, `doc(s)`, `test(s)` or `release` followed by `/`, `-` or `_` |
| `evo_has_dev_branch` | a branch named `dev`, `develop` or `development` exists |
| `evo_merge_commits_pct` | merge commits / (merge commits + team commits) |

## Review process (GitHub API)

PRs opened by bots or AI agents are left out. "Merged" means merged on GitHub on or
before the snapshot.

| Column | Definition |
|---|---|
| `rev_prs`, `rev_merged_pct`, `rev_prs_per_week` | PRs opened in the window, the share merged, PRs per week of the active period |
| `rev_pr_size_median`, `rev_pr_files_median` | median lines added + deleted, and files changed, over merged PRs |
| `rev_commits_per_pr_median`, `_mean` | commits per merged PR |
| `rev_reviewed_pct`, `rev_approved_pct` | merged PRs with at least one review, or approval, by someone other than the author |
| `rev_merged_by_other_pct` | merged PRs merged by someone other than the author |
| `rev_first_review_h_median` | **review time**: hours from opening a PR to its first review by someone else, median over reviewed PRs |
| `rev_rounds_mean` | **review iterations**: for each reviewed PR, 1 + the number of reviews that were followed by a further commit to the PR; mean over reviewed PRs |
| `rev_comments_per_pr_mean`, `_median` | conversation comments + inline review comments per PR |
| `rev_uncommented_pct` | PRs with no comments of either kind |
| `rev_reviews_per_dev` | reviews submitted on teammates' PRs / number of PR authors |

## Collaboration

| Column | Definition |
|---|---|
| `col_contributors`, `col_core_contributors` | people with a team commit; those with at least 5 percent of team commits |
| `col_top_author_share_pct`, `col_smallest_author_share_pct` | largest and smallest share of team commits held by one person |
| `col_gini` | Gini coefficient of team commits per person (0 = perfectly even) |
| `col_authors_per_pr`, `col_multi_author_pr_pct` | distinct commit authors per PR (mean), share of PRs with more than one |
| `col_pr_authors` | people who opened at least one PR (the developers, n) |
| `col_review_pairs` | distinct reviewer-to-author pairs among those n people |
| `col_network_density` | review pairs / n(n - 1) |

## Development velocity (GitHub API)

| Column | Definition |
|---|---|
| `vel_ttm_median_h`, `vel_ttm_p75_h`, `vel_merged_24h_pct` | **time-to-merge**: hours from opening a PR to merging it |
| `vel_issues`, `vel_issues_closed_pct` | issues opened in the window (bots excluded), share closed by the snapshot |
| `vel_issue_close_median_days`, `_p75_days` | **issue closing time**: days from opening to closing, over issues closed by the snapshot |

## AI signals (`ai_signals.csv`)

Only traces of AI *coding tools* count. Commits about AI features in the product (a
chatbot, an LLM call) are not AI assistance and are counted separately in
`ai_llm_feature_commits`.

| Column | Definition |
|---|---|
| `ai_coauthor_commits` (+ `_claude`, `_copilot`, `_cursor`, `_other`) | commits with a `Co-authored-by:` trailer naming Copilot, Claude, Codex, Cursor, OpenAI, ChatGPT or Gemini |
| `ai_agent_commits` | commits authored by an AI agent account |
| `ai_branches` | branches, and source branches of merged PRs, starting with `copilot/`, `codex/`, `claude/` or `cursor/` |
| `ai_explicit_commits` | a line of the commit message that starts with e.g. "Generated with", "Written by" or "Fixed using" followed by a named tool (a tool named in the middle of a sentence, as in "resume generated by Codex", is a product feature, not attribution) |
| `ai_reviews` | PR reviews submitted by an AI reviewer account (copilot-pull-request-reviewer, CodeRabbit, Gemini Code Assist, Sourcery, Cursor Bugbot, Codex, Claude) |
| `ai_config_files` | agent configuration files at the snapshot: AGENTS.md, CLAUDE.md, GEMINI.md, .cursorrules, copilot-instructions.md, .cursor/rules/ |
| `ai_window_commits` | all commits in the window, including merge commits and agent commits |
| `ai_traced_commits`, `ai_traced_pct` | commits with any commit-level signal, and their share of `ai_window_commits` |
| `ai_any_signal` | any of the above |
| `ai_llm_feature_commits` | other commits whose message mentions LLM, GPT, OpenAI, Gemini, Ollama, Anthropic, LangChain or "language model" |

## Limits

- Everyday AI use (autocomplete, chat, pasted code) leaves no trace, so the AI signals
  are a lower bound.
- Review data covers GitHub reviews only; feedback given in person or on Discord is
  invisible.
- Branch counts are taken when the repo was fetched, not at the snapshot, since git does
  not keep a history of deleted branches.
- Alias merging is heuristic: a student who committed under an address never linked to
  their login, with a different name, is counted twice.
