# Verification

## Every repo present for every year

| year | expected | in repo_level | with >=1 scored file |
|---|---|---|---|
| 2022 | 4 | 4 | 4 |
| 2026 | 1 | 1 | 1 |
| 2025 | 20 | 20 | 20 |
| 2024 | 26 | 26 | 26 |
| 2023 | 22 | 22 | 22 |

All expected repos present: **True**

## Row counts

- inventory candidates: 74098
- included in inventory: 15290
- recorded failures: 0
- file_level rows: 15290
- included minus failures: 15290
- **match: True**

## Duplicate keys

- file_level duplicates on (year, repo, path): 0
- file_level duplicates on (year, repo, path, content_hash): 0
- repo_level duplicates on (year, repo): 0

## Null rate per file_level column (%)

Detector columns and keys must be 0; Sonar columns are empty for files SonarQube did not analyse (no analyser for the language, or excluded from the scan).

| column | % empty |
|---|---|
| sq_language | 1.42 |
| sq_qualifier | 1.42 |
| sq_comment_lines | 20.8 |
| sq_comment_lines_density | 21.26 |
| sq_lines | 1.42 |
| sq_ncloc | 20.8 |
| sq_reliability_rating | 1.42 |
| sq_security_rating | 1.42 |
| sq_software_quality_maintainability_rating | 1.42 |
| sq_sqale_rating | 1.42 |
| sq_dead_unused | 1.42 |
| sq_dead_commented | 1.42 |
| sq_dead_unreachable | 1.42 |
| sq_dead_total | 1.42 |
| sq_classes | 28.12 |
| sq_complexity | 24.95 |
| sq_functions | 28.12 |
| sq_statements | 28.12 |
| sq_code_smells | 20.8 |
| sq_cognitive_complexity | 59.77 |
| sq_software_quality_maintainability_issues | 20.8 |
| sq_violations | 20.8 |
| sq_software_quality_maintainability_debt_ratio | 67.76 |
| sq_sqale_debt_ratio | 67.25 |
| sq_sqale_index | 20.8 |
| sq_software_quality_reliability_issues | 20.8 |
| sq_bugs | 20.8 |
| sq_vulnerabilities | 20.8 |
| sq_software_quality_security_issues | 20.8 |
| sq_duplicated_blocks | 20.8 |
| sq_duplicated_lines | 20.8 |
| sq_duplicated_lines_density | 90.2 |

Detector columns all complete: **True**; all finite: **True**

## Spot check: file value vs its chunk rows

| file | chunks | stored bino_score | recomputed | stored droid_p_ai | recomputed |
|---|---|---|---|---|---|
| 2024/capstone-project-team-2-002/test/test_ticket_completion.py | 2/2 | 0.972393 | 0.972393 | 0.925973 | 0.925973 |
| 2024/capstone-project-team10-003/app/Src/KelownaSoftware.Application/AggregateRoots/Authentication/SignIn/SignInResult.cs | 1/1 | 0.909187 | 0.909187 | 0.947157 | 0.947157 |
| 2023/year-long-project-team-21/app/LooseTheLeftovers_Frontend/src/components/HomeIcon.tsx | 1/1 | 1.047371 | 1.047371 | 0.921476 | 0.921476 |

Fresh re-run of the models on chunk 0:

- `test/test_ticket_completion.py` chunk 0 rescored: bino 0.939732 (stored 0.939732), droid p_ai 0.863007 (stored 0.863007)
- `app/Src/KelownaSoftware.Application/AggregateRoots/Authentication/SignIn/SignInResult.cs` chunk 0 rescored: bino 0.909187 (stored 0.909187), droid p_ai 0.947157 (stored 0.947157)
- `app/LooseTheLeftovers_Frontend/src/components/HomeIcon.tsx` chunk 0 rescored: bino 1.047371 (stored 1.047371), droid p_ai 0.921476 (stored 0.921476)
