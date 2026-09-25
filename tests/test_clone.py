import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "02_clone.sh"


def test_failed_fetch_is_retried_under_its_own_name(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "repo_selection.txt").write_text("COSC-499-W2023/x\n")
    clone = tmp_path / "data" / "repos" / "2023" / "x"
    clone.mkdir(parents=True)
    git = ["git", "-C", str(clone)]
    subprocess.run([*git, "init", "-q"], check=True)
    # two unreachable remotes make `git fetch --all` fail with several lines of output
    subprocess.run([*git, "remote", "add", "origin", "/nonexistent/a"], check=True)
    subprocess.run([*git, "remote", "add", "upstream", "/nonexistent/b"], check=True)

    proc = subprocess.run(["bash", str(tmp_path / "scripts" / "02_clone.sh")],
                          capture_output=True, text=True)

    assert proc.returncode == 1
    assert "retrying 1 failed repo(s)" in proc.stdout
    log = (tmp_path / "logs" / "clone_failures.log").read_text().splitlines()
    assert log and all(line.startswith("COSC-499-W2023/x fetch failed:") for line in log)
