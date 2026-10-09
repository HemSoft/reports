"""Validated GitHub owner scope and repository identities for collection and links."""

import os
import re

OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+\Z")


def github_owners():
    owners = [
        owner.strip()
        for owner in os.environ.get("REPORT_GITHUB_OWNERS", "HemSoft,hemsoft-dev").split(",")
    ]
    if any(not OWNER.fullmatch(owner) for owner in owners):
        raise ValueError("REPORT_GITHUB_OWNERS must contain comma-separated GitHub owner names")
    if len({owner.lower() for owner in owners}) != len(owners):
        raise ValueError("REPORT_GITHUB_OWNERS contains duplicate owners")
    return owners


def repository_identity(name, canonical=None):
    if canonical is None:
        owner = (
            "HemSoft"
            if name.lower() in {"now-leadership-group", "set-it-free-loop-site"}
            else "hemsoft-dev"
        )
        canonical = f"{owner}/{name}"
    parts = canonical.split("/")
    if (
        len(parts) != 2
        or not OWNER.fullmatch(parts[0])
        or not REPOSITORY.fullmatch(parts[1])
        or parts[1] in {".", ".."}
        or parts[1].lower() != name.lower()
    ):
        raise ValueError(f"Invalid GitHub repository identity: {canonical!r}")
    return canonical
