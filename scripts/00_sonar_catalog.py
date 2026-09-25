"""Save what this SonarQube server offers: metric keys, languages and rule counts."""
import csv

from common import DOCS, sonar_get, sonar_session


def main():
    s = sonar_session()

    metrics, page = [], 1
    while True:
        data = sonar_get(s, "/api/metrics/search", ps=500, p=page)
        metrics += data["metrics"]
        if len(metrics) >= data["total"] or not data["metrics"]:
            break
        page += 1
    metrics.sort(key=lambda m: m["key"])
    with open(DOCS / "sonarqube_metrics_available.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["key", "name", "type", "domain", "description", "hidden"])
        for m in metrics:
            w.writerow([m["key"], m.get("name", ""), m.get("type", ""), m.get("domain", ""),
                        m.get("description", ""), m.get("hidden", False)])
    print(f"{len(metrics)} metric keys")

    langs = sonar_get(s, "/api/languages/list")["languages"]
    with open(DOCS / "sonarqube_languages.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["language_key", "language_name", "rule_count"])
        for lang in sorted(langs, key=lambda x: x["key"]):
            total = sonar_get(s, "/api/rules/search", languages=lang["key"], ps=1)["total"]
            w.writerow([lang["key"], lang["name"], total])
            print(f"{lang['key']:10} {lang['name']:20} {total} rules")


if __name__ == "__main__":
    main()
