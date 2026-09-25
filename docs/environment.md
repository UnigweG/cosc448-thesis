# Environment

Recorded 2026-09-23.

| Component | Version |
|---|---|
| OS | macOS 27.0 (arm64) |
| SonarQube server | 26.9.0.129388, Community Edition, http://localhost:9000 (embedded H2 database) |
| sonar-scanner CLI | 8.1.0.6389 (Homebrew) |
| Java | OpenJDK 17.0.16 |
| Python | 3.14.0 (venv in .venv) |
| radon | 6.0.1 |
| pylint | 4.0.9 |
| astroid | 4.0.4 (Pylint's parser; all versions in `requirements.lock`) |
| bandit | 1.9.4 |
| pandas | 3.0.6 |
| requests | 2.34.2 |
| git | 2.50.1 |
| gh | 2.87.3 |

radon, pylint and bandit install and run fine on Python 3.14, so no older Python was
needed.

SonarQube notes:
- The server requires authentication for every API call. The scripts use a user token
  from `.env` (basic auth, token as username, empty password). It must be a user token:
  a global analysis token (`sqa_...`) can run scans but gets 403 on
  `/api/ce/activity`, which `03_sonar_scan.py` needs to check each scan.
- The server keeps every analysis in its own data directory. If it runs in Docker,
  use named volumes (or back them up); anonymous volumes are deleted with the
  container, and `04_sonar_export.py` can only export what the server still holds.
- The UI shows a warning that the embedded database is for evaluation only. That is
  fine for this project but it means the server can't be upgraded in place.
- The Community Build does not scan for injection vulnerabilities (SQL injection, XSS,
  ...), according to the warning on each project overview.
- C# files are indexed but not analysed by the sonar-scanner CLI ("Your project
  contains C# files which cannot be analyzed with the scanner you are using"). That
  would need SonarScanner for .NET and a build of each solution. 9 selected repos
  have 35-95% C# code.
- Java files are analysed without compiled classes (warning about missing
  `sonar.java.binaries`). No scan failed because of it, so no retry with
  `-Dsonar.java.binaries=.` was needed.
- 159 metric keys are available (`docs/sonarqube_metrics_available.csv`).

## Languages analysed by this server

Community Edition. Languages not in this list (for example C, C++, Objective-C,
Swift, Dart, PL/SQL) are not analysed.

| Key | Language | Rules |
|---|---|---|
| azureresourcemanager | Azure Resource Manager | 38 |
| cloudformation | CloudFormation | 28 |
| cs | C# | 456 |
| css | CSS | 43 |
| docker | Docker | 28 |
| flex | Flex | 76 |
| go | Go | 36 |
| ipynb | IPython Notebooks | 444 |
| java | Java | 768 |
| js | JavaScript | 528 |
| json | JSON | 0 |
| jsp | JSP | 0 |
| kotlin | Kotlin | 145 |
| kubernetes | Kubernetes | 26 |
| php | PHP | 245 |
| py | Python | 444 |
| ruby | Ruby | 42 |
| rust | Rust | 85 |
| scala | Scala | 41 |
| secrets | Secrets | 30 |
| terraform | Terraform | 54 |
| text | Text | 3 |
| ts | TypeScript | 546 |
| vbnet | VB.NET | 197 |
| web | HTML | 104 |
| xml | XML | 39 |
| yaml | YAML | 0 |

## Metric keys

All keys requested by the export script were checked against
`/api/metrics/search`. Keys from older versions that are missing in 26.9:
`function_complexity`, `file_complexity`, `class_complexity`,
`complexity_in_functions`, `complexity_in_classes`,
`function_complexity_distribution`, `file_complexity_distribution`.

Keys the export asked for but the server did not return for some projects are listed
below after each export run.

### Export run: keys not returned

- `classes` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `cognitive_complexity` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `functions` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `statements` missing for 1 project(s): cosc448_2023_year-long-project-team-14
