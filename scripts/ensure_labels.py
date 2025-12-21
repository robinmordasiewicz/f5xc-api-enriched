#!/usr/bin/env python3
"""Ensure GitHub Labels Script.

Creates required labels for workflow monitoring if they don't exist.
Labels are used to categorize and filter workflow failure issues.
"""

import subprocess
import sys

# Label definitions: (name, description, color)
REQUIRED_LABELS = [
    # Primary labels
    ("workflow-failure", "Automatically created for workflow failures", "d73a4a"),
    ("auto-created", "Issue created automatically by monitoring", "c5def5"),
    # Failure type labels
    ("failure:download", "Failure during spec download", "f9d0c4"),
    ("failure:enrichment", "Failure during enrichment pipeline", "f9d0c4"),
    ("failure:validation", "Failure during linting or validation", "f9d0c4"),
    ("failure:git", "Failure during git operations", "f9d0c4"),
    ("failure:release", "Failure during release creation", "f9d0c4"),
    ("failure:deployment", "Failure during GitHub Pages deployment", "f9d0c4"),
    ("failure:deprecation", "Deprecation warning detected", "fbca04"),
    ("failure:other", "Other workflow failure", "f9d0c4"),
    # Severity labels
    ("severity:critical", "Critical failure requiring immediate attention", "b60205"),
    ("severity:warning", "Warning that should be addressed", "fbca04"),
    ("severity:info", "Informational issue", "0e8a16"),
    # Status labels
    ("needs-investigation", "Requires investigation", "d876e3"),
]


def run_gh_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command."""
    cmd = ["gh", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"Warning: {result.stderr.strip()}", file=sys.stderr)
    return result


def label_exists(name: str) -> bool:
    """Check if a label already exists."""
    result = run_gh_command(["label", "list", "--search", name, "--limit", "1"], check=False)
    if result.returncode != 0:
        return False
    return name in result.stdout


def create_label(name: str, description: str, color: str) -> bool:
    """Create a label if it doesn't exist."""
    if label_exists(name):
        print(f"  Label '{name}' already exists")
        return True

    result = run_gh_command(
        ["label", "create", name, "--description", description, "--color", color, "--force"],
        check=False,
    )

    if result.returncode == 0:
        print(f"  Created label '{name}'")
        return True
    print(f"  Failed to create label '{name}': {result.stderr.strip()}", file=sys.stderr)
    return False


def main() -> int:
    """Main entry point."""
    print("Ensuring required workflow monitoring labels exist...")

    success_count = 0
    total = len(REQUIRED_LABELS)

    for name, description, color in REQUIRED_LABELS:
        if create_label(name, description, color):
            success_count += 1

    print(f"\nLabels: {success_count}/{total} ensured")
    return 0 if success_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
