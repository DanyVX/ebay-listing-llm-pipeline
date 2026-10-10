"""Scan staged blobs and complete Git history for known secrets and private denylist terms.

Add a local, untracked file outside the repository via ELP_LOCAL_DENYLIST.
This is a conservative leak detector, not proof of confidentiality.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "provider_secret": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\s]{80,}"
    ),
}
MAX_BYTES = 1_000_000


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def scan_blob(data: bytes, source: str, denylist: list[str]) -> list[str]:
    if len(data) > MAX_BYTES:
        return [f"{source}: oversized tracked blob ({len(data)} bytes), manual audit required"]
    if b"\0" in data:
        return [f"{source}: binary tracked blob, manual audit required"]
    text = data.decode("utf-8", errors="replace")
    hits = [
        f"{source}: matched {name}" for name, pattern in PATTERNS.items() if pattern.search(text)
    ]
    lowered = text.casefold()
    hits.extend(
        f"{source}: matched private denylist entry #{index}"
        for index, entry in enumerate(denylist, 1)
        if entry.casefold() in lowered
    )
    return hits


def private_terms(root: Path) -> list[str]:
    setting = os.getenv("ELP_LOCAL_DENYLIST")
    if not setting:
        return []
    path = Path(setting).expanduser().resolve()
    if path.is_relative_to(root.resolve()):
        raise ValueError("ELP_LOCAL_DENYLIST must be kept outside the repository")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    terms = private_terms(root)
    findings: list[str] = []
    seen: set[str] = set()
    for entry in git(root, "rev-list", "--objects", "--all").decode().splitlines():
        sha = entry.split(" ", 1)[0]
        if sha in seen:
            continue
        seen.add(sha)
        if git(root, "cat-file", "-t", sha).strip() != b"blob":
            continue
        findings.extend(
            scan_blob(git(root, "cat-file", "-p", sha), f"history blob {sha[:12]}", terms)
        )
    for path in git(root, "ls-files", "-z").split(b"\0"):
        if not path:
            continue
        filename = path.decode("utf-8")
        try:
            data = git(root, "show", f":{filename}")
        except subprocess.CalledProcessError:
            continue
        findings.extend(scan_blob(data, f"index {filename}", terms))
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"Privacy scan passed ({len(seen)} Git objects examined); manual review still required")
    if not terms:
        print("Private denylist not supplied; set ELP_LOCAL_DENYLIST for local checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
