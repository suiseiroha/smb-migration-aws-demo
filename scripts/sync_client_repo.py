"""Publishes a client-safe snapshot of this repo to a separate GitHub repo.

Same filtering as export_client_snapshot.py (only committed files, via
`git archive`; CLAUDE.md/PLAN.md/.claude/ stripped out) but instead of a
zip, it pushes the result as a commit to CLIENT_REPO_URL. The client
clones that repo once and just `git pull`s from then on -- no re-sending
a zip every time there's an update.

Usage:
    python scripts/sync_client_repo.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {"CLAUDE.md", "PLAN.md", ".claude"}

CLIENT_REPO_URL = "https://github.com/suiseiroha/smb-migration-aws-demo.git"
MIRROR_DIR = REPO_ROOT.parent / "smb-migration-aws-demo-mirror"


def run(cmd, cwd=None, check=True, capture=False):
    return subprocess.run(
        cmd, cwd=cwd, check=check,
        capture_output=capture, text=True,
    )


def build_filtered_tree(dest: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        archive_zip = tmp / "archive.zip"
        run(["git", "archive", "--format=zip", "-o", str(archive_zip), "HEAD"], cwd=REPO_ROOT)
        shutil.unpack_archive(str(archive_zip), str(dest), "zip")

    for name in EXCLUDE:
        target = dest / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def main():
    if not MIRROR_DIR.exists():
        print(f"Cloning {CLIENT_REPO_URL} into {MIRROR_DIR} ...")
        run(["git", "clone", CLIENT_REPO_URL, str(MIRROR_DIR)])
    else:
        run(["git", "fetch", "origin"], cwd=MIRROR_DIR)
        run(["git", "reset", "--hard", "origin/HEAD"], cwd=MIRROR_DIR, check=False)

    # Wipe the mirror's working tree (except .git) and replace with the
    # current filtered snapshot.
    for item in MIRROR_DIR.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    build_filtered_tree(MIRROR_DIR)

    status = run(["git", "status", "--porcelain"], cwd=MIRROR_DIR, capture=True).stdout
    if not status.strip():
        print("No changes to publish -- client repo is already up to date.")
        return

    source_hash = run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture=True).stdout.strip()
    source_subject = run(["git", "log", "-1", "--format=%s"], cwd=REPO_ROOT, capture=True).stdout.strip()

    run(["git", "add", "-A"], cwd=MIRROR_DIR)
    run(["git", "commit", "-m", f"Sync from smb-migration-aws @ {source_hash}: {source_subject}"], cwd=MIRROR_DIR)
    run(["git", "push"], cwd=MIRROR_DIR)

    print(f"Published to {CLIENT_REPO_URL} (source: {source_hash})")


if __name__ == "__main__":
    main()
