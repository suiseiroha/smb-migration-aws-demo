"""Builds a client-safe snapshot of this repo.

Pulls only what's actually committed (via `git archive`, so uncommitted
work and gitignored files never leak) and strips internal working docs
that shouldn't go to a client.

Usage:
    python scripts/export_client_snapshot.py [output.zip | output_dir]

Defaults to <repo-name>-client-snapshot.zip next to the repo.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {"CLAUDE.md", "PLAN.md", ".claude"}


def main():
    out_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else REPO_ROOT.parent / f"{REPO_ROOT.name}-client-snapshot.zip"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        archive_zip = tmp / "archive.zip"
        subprocess.run(
            ["git", "archive", "--format=zip", "-o", str(archive_zip), "HEAD"],
            cwd=REPO_ROOT,
            check=True,
        )

        extract_dir = tmp / "extracted"
        shutil.unpack_archive(str(archive_zip), str(extract_dir), "zip")

        for name in EXCLUDE:
            target = extract_dir / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()

        if out_path.suffix == ".zip":
            shutil.make_archive(str(out_path.with_suffix("")), "zip", extract_dir)
        else:
            if out_path.exists():
                shutil.rmtree(out_path)
            shutil.copytree(extract_dir, out_path)

    print(f"Client snapshot written to {out_path}")
    print(f"(excluded: {', '.join(sorted(EXCLUDE))}; only committed files included)")


if __name__ == "__main__":
    main()
