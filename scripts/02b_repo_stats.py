"""Inventory of the selected repos with git history stats from the local clones.

Writes results/repo_inventory.csv and prints the language mix.
"""
import json
import re
import subprocess

import pandas as pd

from common import RESULTS, read_selection, repo_dir


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def section_of(repo, description):
    for text in (repo, description or ""):
        m = re.search(r"(?<!\d)(00[23])(?!\d)", text)
        if m:
            return m.group(1)
    return ""


def team_number(repo, description):
    for text in (repo, description or ""):
        m = re.search(r"(?:team|group)[-_ ]?0*(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def first_last(log):
    """Earliest and latest commit dates from `git log --format='%ct %cI'` lines.

    Compared by epoch seconds: the ISO strings carry different UTC offsets, so string
    order is not time order. The chosen commits keep their original ISO dates.
    """
    dates = sorted((int(ts), iso) for ts, iso in (line.split(" ", 1) for line in log))
    return dates[0][1], dates[-1][1]


def main():
    inv = pd.read_csv(RESULTS / "repo_inventory_all.csv")
    rows = []
    for org, repo, year in read_selection():
        meta = inv[(inv.org == org) & (inv.repo == repo)].iloc[0].to_dict()
        desc = meta.pop("description", "")
        desc = "" if pd.isna(desc) else desc
        path = repo_dir(year, repo)
        log = git(path, "log", "--format=%ct %cI", "HEAD").splitlines()
        first, last = first_last(log)
        section = section_of(repo, desc)
        num = team_number(repo, desc)
        meta.update({
            "section": section,
            "team_key": f"{year}-t{num}" + (f"-{section}" if section else "") if num else "",
            "commit_count": len(log),
            "first_commit_date": first,
            "last_commit_date": last,
            "head_sha": git(path, "rev-parse", "HEAD"),
            "tracked_file_count": len(git(path, "ls-files").splitlines()),
        })
        rows.append(meta)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "repo_inventory.csv", index=False)
    print(f"wrote results/repo_inventory.csv ({len(df)} repos)")

    dup = df[df.team_key != ""].groupby("team_key").repo.apply(list)
    dup = dup[dup.map(len) > 1]
    if len(dup):
        print("\nteam_key shared by more than one repo:")
        for k, v in dup.items():
            print(f"  {k}: {', '.join(v)}")

    lang_bytes, lang_repos = {}, {}
    for s in df.language_bytes.dropna():
        for lang, b in json.loads(s).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + b
            lang_repos[lang] = lang_repos.get(lang, 0) + 1
    mix = (pd.DataFrame({"bytes": lang_bytes, "repos": lang_repos})
           .sort_values("bytes", ascending=False))
    mix["share_pct"] = (100 * mix.bytes / mix.bytes.sum()).round(2)
    print("\nlanguage mix across selected repos (GitHub linguist bytes):")
    print(mix.to_string())


if __name__ == "__main__":
    main()
