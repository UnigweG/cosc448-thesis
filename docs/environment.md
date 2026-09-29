# Environment

Recorded on 2026-09-23.

## Tool versions

| Component         | Version                                                                  |
|-------------------|--------------------------------------------------------------------------|
| OS                | macOS 27.0 (arm64)                                                       |
| SonarQube server  | 26.9.0.129388, Community Edition, `http://localhost:9000` (embedded H2 database) |
| sonar-scanner CLI | 8.1.0.6389 (Homebrew)                                                    |
| Java              | OpenJDK 17.0.16                                                          |
| Python            | 3.14.0 (venv in `.venv`)                                                 |
| radon             | 6.0.1                                                                    |
| pylint            | 4.0.9                                                                    |
| astroid           | 4.0.4 (Pylint's parser)                                                  |
| bandit            | 1.9.4                                                                    |
| pandas            | 3.0.6                                                                    |
| requests          | 2.34.2                                                                   |
| git               | 2.50.1                                                                   |
| gh                | 2.87.3                                                                   |

The full list of Python packages and versions is in `requirements.txt`. Radon, Pylint and Bandit all install and run fine on Python 3.14, so an older Python was not needed.

## SonarQube notes

### Authentication

Every API call needs authentication. The scripts use a user token from `.env`, sent as basic auth with the token as the username and an empty password.

It has to be a **user token**. A global analysis token (`sqa_...`) can run scans, but it gets a 403 on `/api/ce/activity`, which `03_sonar_scan.py` uses to check each scan.

### Where the data lives

The server stores every analysis in its own data directory, and `04_sonar_export.py` can only export what the server still holds. If SonarQube runs in Docker, use named volumes (or back them up). Anonymous volumes are deleted along with the container.

### Known limitations

- **Embedded database.** The UI warns that the embedded database is for evaluation only. That's fine for this project, but it means the server can't be upgraded in place.
- **No injection checks.** According to the warning on each project overview, the Community Build does not scan for injection vulnerabilities such as SQL injection or XSS.
- **C# is not analysed.** The sonar-scanner CLI indexes C# files but doesn't analyse them ("Your project contains C# files which cannot be analyzed with the scanner you are using"). That would need SonarScanner for .NET and a build of each solution. 9 of the selected repos are 35-95% C#.
- **Java without bytecode.** Java files are analysed without compiled classes, so the scanner warns about a missing `sonar.java.binaries`. No scan failed because of this, so there was no need to retry with `-Dsonar.java.binaries=.`.

The server has 159 metric keys, listed in `docs/sonarqube_metrics_available.csv`.

## Languages analysed by this server

Community Edition. Languages not in this table (for example C, C++, Objective-C, Swift, Dart and PL/SQL) are not analysed.

| Key                    | Language               | Rules |
|------------------------|------------------------|------:|
| `azureresourcemanager` | Azure Resource Manager |    38 |
| `cloudformation`       | CloudFormation         |    28 |
| `cs`                   | C#                     |   456 |
| `css`                  | CSS                    |    43 |
| `docker`               | Docker                 |    28 |
| `flex`                 | Flex                   |    76 |
| `go`                   | Go                     |    36 |
| `ipynb`                | IPython Notebooks      |   444 |
| `java`                 | Java                   |   768 |
| `js`                   | JavaScript             |   528 |
| `json`                 | JSON                   |     0 |
| `jsp`                  | JSP                    |     0 |
| `kotlin`               | Kotlin                 |   145 |
| `kubernetes`           | Kubernetes             |    26 |
| `php`                  | PHP                    |   245 |
| `py`                   | Python                 |   444 |
| `ruby`                 | Ruby                   |    42 |
| `rust`                 | Rust                   |    85 |
| `scala`                | Scala                  |    41 |
| `secrets`              | Secrets                |    30 |
| `terraform`            | Terraform              |    54 |
| `text`                 | Text                   |     3 |
| `ts`                   | TypeScript             |   546 |
| `vbnet`                | VB.NET                 |   197 |
| `web`                  | HTML                   |   104 |
| `xml`                  | XML                    |    39 |
| `yaml`                 | YAML                   |     0 |

## Metric keys

Every key the export script requests was checked against `/api/metrics/search`. These keys from older SonarQube versions no longer exist in 26.9:

- `function_complexity`
- `file_complexity`
- `class_complexity`
- `complexity_in_functions`
- `complexity_in_classes`
- `function_complexity_distribution`
- `file_complexity_distribution`

The section below is written by `04_sonar_export.py` on each run. It lists keys that were requested but not returned for some projects.

<!-- Everything from the next heading to the end of the file is replaced by 04_sonar_export.py. Keep that heading exactly as it is and keep it last. -->

### Export run: keys not returned

- `classes` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `cognitive_complexity` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `functions` missing for 1 project(s): cosc448_2023_year-long-project-team-14
- `statements` missing for 1 project(s): cosc448_2023_year-long-project-team-14
