# Data dictionary

Detector outputs are raw: no calibrated threshold exists for the Qwen-based Binoculars score. `*_percentile` columns are ranks within this run only.

## file_level.csv (one row per scored file)

| column | meaning |
|---|---|
| `year` | Cohort year: 2022 = pre-AI baseline, 2023-2025 = AI years, 2026 = the user's capstone. |
| `repo` | Repository (directory under data/repos/<year>/). |
| `path` | File path inside the repo at the scanned commit. |
| `content_hash` | Git blob SHA of the file content (with year/repo/path it is the key). |
| `sha` | Commit (HEAD) the repo was scanned at. |
| `language` | Language from the file extension (.m is read as MATLAB). |
| `ext` | Lower-case file extension. |
| `bytes` | Size in bytes (git blob size). |
| `lines` | Number of lines. |
| `sloc` | Non-blank lines (includes comment lines; differs from SonarQube ncloc). |
| `is_test` | 1 if the path looks like a test file (tests/, test_*, *_test.*, *.test.*, *.spec.*). |
| `detector_language_supported` | yes/no. 'no' = MATLAB, SQL, HTML, CSS: probably outside the detectors' training data; scored anyway. |
| `qwen_tokens` | Tokens of the whole file under the Qwen2.5-Coder tokenizer. |
| `bino_chunks` | Number of Binoculars chunks (<= 512 Qwen tokens each, cut at line ends where possible). |
| `bino_tokens_scored` | Tokens that had a prediction (chunk tokens minus the first token of each chunk); the Binoculars weights. |
| `bino_score` | Binoculars statistic = performer log-perplexity / cross-perplexity, token-weighted mean over chunks. LOWER = more AI-like (original orientation). No calibrated threshold exists for this Qwen pair. |
| `bino_score_min` | Lowest chunk Binoculars score in the file. |
| `bino_score_max` | Highest chunk Binoculars score in the file. |
| `obs_logppl` | Observer (Qwen2.5-Coder-1.5B) log-perplexity, nats/token, token-weighted mean over chunks. |
| `perf_logppl` | Performer (Qwen2.5-Coder-1.5B-Instruct) log-perplexity, nats/token, token-weighted mean over chunks. |
| `xppl` | Cross-perplexity (observer next-token distribution scored by the performer), nats/token, token-weighted mean. |
| `droid_chunks` | Number of DroidDetect chunks (<= 510 content tokens + [CLS]/[SEP] = 512). |
| `droid_tokens` | DroidDetect tokens scored (specials included); the DroidDetect weights. |
| `droid_logit_human` | DroidDetect class-0 (HUMAN_GENERATED) logit, token-weighted mean over chunks. |
| `droid_logit_ai` | DroidDetect class-1 (MACHINE_GENERATED) logit, token-weighted mean over chunks. |
| `droid_p_ai` | DroidDetect probability(AI) (softmax of the class logits per chunk), token-weighted mean over chunks. |
| `droid_label` | DroidDetect's own binary label for the file: MACHINE_GENERATED if droid_p_ai >= 0.5 else HUMAN_GENERATED. |
| `droid_ai_chunk_share` | Share of the file's chunks that DroidDetect labels MACHINE_GENERATED. |
| `device` | Torch device used. |
| `dtype` | Model dtype used (float16 on mps). |
| `observer` | Observer model id. |
| `performer` | Performer model id. |
| `droid_model` | DroidDetect checkpoint id. |
| `seconds` | Seconds spent scoring the file. |
| `scored_at` | UTC timestamp when the file was scored. |
| `bino_score_percentile` | Percentile (0-100) of bino_score among all scored files of the run. Low = more AI-like. A rank, not a threshold. |
| `droid_p_ai_percentile` | Percentile (0-100) of droid_p_ai among all scored files of the run. High = more AI-like. |
| `sq_language` | SonarQube's language key for the file (empty when no analyser). |
| `sq_qualifier` | SonarQube component qualifier: FIL = source file, UTS = test file. |
| `sq_comment_lines` | SonarQube comment lines. |
| `sq_comment_lines_density` | SonarQube comment lines / (ncloc + comment lines) * 100. |
| `sq_lines` | SonarQube total lines. |
| `sq_ncloc` | SonarQube lines of code (non-comment, non-blank). |
| `sq_reliability_rating` | SonarQube reliability rating, 1 (A) to 5 (E). |
| `sq_security_rating` | SonarQube security rating, 1 (A) to 5 (E). |
| `sq_software_quality_maintainability_rating` | SonarQube maintainability rating (new-model key), 1 (A) to 5 (E). |
| `sq_sqale_rating` | SonarQube maintainability rating, 1 (A) to 5 (E). |
| `sq_dead_unused` | Open SonarQube issues for unused code: rules S1481, S1172, S1854, S1128, S1068, S1144, S5603, S3985, S4487, S1065, S2326 (any language prefix). |
| `sq_dead_commented` | Open SonarQube issues for commented-out code: S125, Web:AvoidCommentedOutCodeCheck. |
| `sq_dead_unreachable` | Open SonarQube issues for unreachable code: S1763, S2583. |
| `sq_dead_total` | sq_dead_unused + sq_dead_commented + sq_dead_unreachable. |
| `sq_classes` | SonarQube classes. |
| `sq_complexity` | SonarQube cyclomatic complexity. |
| `sq_functions` | SonarQube functions. |
| `sq_statements` | SonarQube statements. |
| `sq_code_smells` | SonarQube code smells (maintainability issues); 0 for an analysed file with none. |
| `sq_cognitive_complexity` | SonarQube cognitive complexity. |
| `sq_software_quality_maintainability_issues` | SonarQube maintainability issues (new model). |
| `sq_violations` | SonarQube open issues of all kinds; 0 for an analysed file with none. |
| `sq_software_quality_maintainability_debt_ratio` | SonarQube maintainability debt ratio (new model). |
| `sq_sqale_debt_ratio` | SonarQube technical debt ratio (%). |
| `sq_sqale_index` | SonarQube technical debt in minutes. |
| `sq_software_quality_reliability_issues` | SonarQube reliability issues (new model). |
| `sq_bugs` | SonarQube bugs (reliability issues); 0 for an analysed file with none. |
| `sq_vulnerabilities` | SonarQube vulnerabilities; 0 for an analysed file with none. |
| `sq_software_quality_security_issues` | SonarQube security issues (new model). |
| `sq_duplicated_blocks` | SonarQube duplicated blocks. |
| `sq_duplicated_lines` | SonarQube duplicated lines. |
| `sq_duplicated_lines_density` | SonarQube duplicated lines in % of lines. |
| `sonar_analysed` | yes if SonarQube reported measures for this file (it has a language analyser), else no. |

## repo_level.csv (derived from file_level.csv)

| column | meaning |
|---|---|
| `year` | Cohort year. |
| `repo` | Repository. |
| `files_candidate` | Source-extension files tracked at HEAD (file_inventory.csv rows). |
| `files_excluded` | Candidate files not scored (vendored, generated, SonarQube-excluded dirs, empty, too short...), see file_inventory.csv. |
| `files_included` | Candidate files that were meant to be scored. |
| `files_scored` | Included files with a result. |
| `files_failed` | Included files without a result (listed in failed.csv with the error). |
| `sloc_scored` | Sum of sloc over scored files. |
| `tokens_scored` | Sum of qwen_tokens over scored files. |
| `bino_score_wmean` | bino_score - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `bino_score_median` | bino_score - median over files |
| `bino_score_std` | bino_score - standard deviation over files (unweighted, ddof=1) |
| `bino_score_min` | bino_score - minimum over files |
| `bino_score_max` | bino_score - maximum over files |
| `obs_logppl_wmean` | obs_logppl - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `obs_logppl_median` | obs_logppl - median over files |
| `obs_logppl_std` | obs_logppl - standard deviation over files (unweighted, ddof=1) |
| `obs_logppl_min` | obs_logppl - minimum over files |
| `obs_logppl_max` | obs_logppl - maximum over files |
| `perf_logppl_wmean` | perf_logppl - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `perf_logppl_median` | perf_logppl - median over files |
| `perf_logppl_std` | perf_logppl - standard deviation over files (unweighted, ddof=1) |
| `perf_logppl_min` | perf_logppl - minimum over files |
| `perf_logppl_max` | perf_logppl - maximum over files |
| `xppl_wmean` | xppl - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `xppl_median` | xppl - median over files |
| `xppl_std` | xppl - standard deviation over files (unweighted, ddof=1) |
| `xppl_min` | xppl - minimum over files |
| `xppl_max` | xppl - maximum over files |
| `droid_p_ai_wmean` | droid_p_ai - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `droid_p_ai_median` | droid_p_ai - median over files |
| `droid_p_ai_std` | droid_p_ai - standard deviation over files (unweighted, ddof=1) |
| `droid_p_ai_min` | droid_p_ai - minimum over files |
| `droid_p_ai_max` | droid_p_ai - maximum over files |
| `droid_logit_ai_wmean` | droid_logit_ai - token-weighted mean over files (weights: bino_tokens_scored for Binoculars columns, droid_tokens for DroidDetect columns) |
| `droid_logit_ai_median` | droid_logit_ai - median over files |
| `droid_logit_ai_std` | droid_logit_ai - standard deviation over files (unweighted, ddof=1) |
| `droid_logit_ai_min` | droid_logit_ai - minimum over files |
| `droid_logit_ai_max` | droid_logit_ai - maximum over files |
| `droid_ai_file_share` | Share of scored files that DroidDetect labels MACHINE_GENERATED (droid_p_ai >= 0.5). |
| `droid_ai_sloc_share` | Share of scored sloc in files labelled MACHINE_GENERATED. |
| `droid_ai_token_share` | Share of scored Qwen tokens in files labelled MACHINE_GENERATED. |
| `unsupported_language_file_share` | Share of scored files in MATLAB/SQL/HTML/CSS (outside the detectors' training languages). |
| `bino_score_pct_below_p10` | Share of scored files whose bino_score is in the lowest 10% of the whole run (a rank, not a threshold). |
| `sq_ncloc` | Repo-level SonarQube measure `ncloc` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_lines` | Repo-level SonarQube measure `lines` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_statements` | Repo-level SonarQube measure `statements` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_functions` | Repo-level SonarQube measure `functions` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_classes` | Repo-level SonarQube measure `classes` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_files` | Repo-level SonarQube measure `files` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_comment_lines` | Repo-level SonarQube measure `comment_lines` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_comment_lines_density` | Repo-level SonarQube measure `comment_lines_density` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_complexity` | Repo-level SonarQube measure `complexity` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_cognitive_complexity` | Repo-level SonarQube measure `cognitive_complexity` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_duplicated_lines_density` | Repo-level SonarQube measure `duplicated_lines_density` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_duplicated_blocks` | Repo-level SonarQube measure `duplicated_blocks` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_bugs` | Repo-level SonarQube measure `bugs` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_vulnerabilities` | Repo-level SonarQube measure `vulnerabilities` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_security_hotspots` | Repo-level SonarQube measure `security_hotspots` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_code_smells` | Repo-level SonarQube measure `code_smells` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_violations` | Repo-level SonarQube measure `violations` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_sqale_index` | Repo-level SonarQube measure `sqale_index` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_sqale_debt_ratio` | Repo-level SonarQube measure `sqale_debt_ratio` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_sqale_rating` | Repo-level SonarQube measure `sqale_rating` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_reliability_rating` | Repo-level SonarQube measure `reliability_rating` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_security_rating` | Repo-level SonarQube measure `security_rating` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_maintainability_issues` | Repo-level SonarQube measure `software_quality_maintainability_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_reliability_issues` | Repo-level SonarQube measure `software_quality_reliability_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_security_issues` | Repo-level SonarQube measure `software_quality_security_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_blocker_issues` | Repo-level SonarQube measure `software_quality_blocker_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_high_issues` | Repo-level SonarQube measure `software_quality_high_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_medium_issues` | Repo-level SonarQube measure `software_quality_medium_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_low_issues` | Repo-level SonarQube measure `software_quality_low_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_info_issues` | Repo-level SonarQube measure `software_quality_info_issues` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_maintainability_rating` | Repo-level SonarQube measure `software_quality_maintainability_rating` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_software_quality_maintainability_debt_ratio` | Repo-level SonarQube measure `software_quality_maintainability_debt_ratio` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_ncloc_language_distribution` | Repo-level SonarQube measure `ncloc_language_distribution` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_analysis_date` | Repo-level SonarQube measure `analysis_date` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_files` | Repo-level SonarQube measure `py_files` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_file_complexity_max` | Repo-level SonarQube measure `py_file_complexity_max` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_ncloc` | Repo-level SonarQube measure `py_ncloc` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_comment_lines` | Repo-level SonarQube measure `py_comment_lines` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_complexity` | Repo-level SonarQube measure `py_complexity` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_functions` | Repo-level SonarQube measure `py_functions` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_py_classes` | Repo-level SonarQube measure `py_classes` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_sev_minor` | Repo-level SonarQube measure `issues_sev_minor` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_sev_major` | Repo-level SonarQube measure `issues_sev_major` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_sev_critical` | Repo-level SonarQube measure `issues_sev_critical` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_sev_blocker` | Repo-level SonarQube measure `issues_sev_blocker` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_sev_info` | Repo-level SonarQube measure `issues_sev_info` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_impact_high` | Repo-level SonarQube measure `issues_impact_high` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_impact_medium` | Repo-level SonarQube measure `issues_impact_medium` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_impact_low` | Repo-level SonarQube measure `issues_impact_low` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_impact_info` | Repo-level SonarQube measure `issues_impact_info` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sq_issues_impact_blocker` | Repo-level SonarQube measure `issues_impact_blocker` for the whole repo (same columns as results/sonarqube_metrics.csv; see docs/metrics_mapping.md). Empty where the metric does not apply. |
| `sonar_status` | Scan status from results/sonar_scan_status*.csv. |
| `sonar_notes` | Notes from the scan: languages SonarQube cannot analyse, exclusions. |
