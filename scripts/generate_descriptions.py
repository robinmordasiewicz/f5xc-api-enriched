#!/usr/bin/env python3
"""Generate enriched domain descriptions using Claude Code CLI.

Uses `claude -p` in headless mode to generate 3-tier descriptions
(short, medium, long) for each API domain based on source spec context.

Usage:
    # Generate for specific domain
    python scripts/generate_descriptions.py --domain virtual

    # Generate for all domains without descriptions
    python scripts/generate_descriptions.py --all

    # Force regeneration even if descriptions exist
    python scripts/generate_descriptions.py --domain virtual --force

    # Dry run (show prompts without calling Claude)
    python scripts/generate_descriptions.py --all --dry-run
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scripts.utils.domain_categorizer import DomainCategorizer
from scripts.utils.domain_metadata import DOMAIN_METADATA

# Constants
CONFIG_PATH = Path("config/domain_descriptions.yaml")
ORIGINAL_SPECS_PATH = Path("specs/original")
DOMAIN_PATTERNS_PATH = Path("config/domain_patterns.yaml")

# Description tier constraints
MAX_SHORT = 60
MAX_MEDIUM = 150
MAX_LONG = 500

# JSON Schema for Claude Code structured output
DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "short": {"type": "string"},
        "medium": {"type": "string"},
        "long": {"type": "string"},
    },
    "required": ["short", "medium", "long"],
}


def load_config() -> dict[str, Any]:
    """Load existing domain descriptions config."""
    if not CONFIG_PATH.exists():
        return {"version": "1.0.0", "domains": {}}

    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {"version": "1.0.0", "domains": {}}


def save_config(config: dict[str, Any]) -> None:
    """Save domain descriptions config."""
    config["generated_at"] = datetime.now(tz=timezone.utc).isoformat()

    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_domain_source_specs(domain: str) -> list[Path]:
    """Get source spec files that belong to a domain."""
    categorizer = DomainCategorizer()
    return [
        spec_file
        for spec_file in ORIGINAL_SPECS_PATH.glob("*.json")
        if categorizer.categorize(spec_file.name) == domain
    ]


def _load_spec_safely(spec_path: Path) -> dict[str, Any] | None:
    """Load a spec file, returning None if it fails."""
    try:
        with spec_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def compute_source_patterns_hash(domain: str) -> str:
    """Compute a stable hash of source spec patterns for change detection.

    Creates a SHA256 hash based on:
    - Sorted list of source spec filenames
    - Sorted list of all paths in those specs
    - Sorted list of all schema names in those specs

    Args:
        domain: Domain name to compute hash for

    Returns:
        SHA256 hash prefixed with 'sha256:'
    """
    source_specs = get_domain_source_specs(domain)

    # Collect patterns from all specs
    patterns = {
        "files": sorted([spec.name for spec in source_specs]),
        "paths": [],
        "schemas": [],
    }

    for spec_path in source_specs:
        spec = _load_spec_safely(spec_path)
        if spec:
            patterns["paths"].extend(spec.get("paths", {}).keys())
            patterns["schemas"].extend(
                spec.get("components", {}).get("schemas", {}).keys(),
            )

    # Sort and deduplicate
    patterns["paths"] = sorted(set(patterns["paths"]))
    patterns["schemas"] = sorted(set(patterns["schemas"]))

    # Create stable JSON representation and hash it
    content = json.dumps(patterns, sort_keys=True)
    hash_value = hashlib.sha256(content.encode()).hexdigest()

    return f"sha256:{hash_value}"


def extract_spec_context(spec_path: Path) -> dict[str, Any]:
    """Extract context from a source spec for prompt generation."""
    with spec_path.open() as f:
        spec = json.load(f)

    return {
        "title": spec.get("info", {}).get("title", ""),
        "description": spec.get("info", {}).get("description", ""),
        "paths": list(spec.get("paths", {}).keys())[:20],  # First 20 paths
        "schemas": list(spec.get("components", {}).get("schemas", {}).keys())[:30],
        "path_count": len(spec.get("paths", {})),
        "schema_count": len(spec.get("components", {}).get("schemas", {})),
    }


def get_domain_context(domain: str) -> dict[str, Any]:
    """Gather all context for a domain."""
    # Get metadata from domain_metadata.py
    metadata = DOMAIN_METADATA.get(domain, {})

    # Get source specs and extract context
    source_specs = get_domain_source_specs(domain)
    spec_contexts = [extract_spec_context(spec) for spec in source_specs[:5]]  # First 5 specs

    # Aggregate paths and schemas
    all_paths = []
    all_schemas = []
    for ctx in spec_contexts:
        all_paths.extend(ctx.get("paths", []))
        all_schemas.extend(ctx.get("schemas", []))

    # Deduplicate and limit
    unique_paths = list(dict.fromkeys(all_paths))[:30]
    unique_schemas = list(dict.fromkeys(all_schemas))[:40]

    return {
        "domain": domain,
        "domain_title": domain.replace("_", " ").title(),
        "use_cases": metadata.get("use_cases", []),
        "related_domains": metadata.get("related_domains", []),
        "domain_category": metadata.get("domain_category", "Other"),
        "paths": unique_paths,
        "schemas": unique_schemas,
        "spec_count": len(source_specs),
    }


def build_prompt(domain: str, context: dict[str, Any]) -> str:
    """Build the prompt for Claude to generate descriptions."""
    use_cases_str = "\n".join(f"  - {uc}" for uc in context.get("use_cases", []))
    paths_str = "\n".join(f"  - {p}" for p in context.get("paths", [])[:15])
    schemas_str = ", ".join(context.get("schemas", [])[:20])

    prompt = f"""Generate 3-tier API descriptions for the "{context["domain_title"]}" domain.

CONTEXT:
Domain: {domain}
Category: {context.get("domain_category", "Other")}
Related domains: {", ".join(context.get("related_domains", []))}
Spec count: {context.get("spec_count", 0)} source specifications

Use cases:
{use_cases_str or "  - (none specified)"}

Sample API paths:
{paths_str or "  - (none)"}

Key schemas: {schemas_str or "(none)"}

REQUIREMENTS:
1. short (max {MAX_SHORT} chars): For CLI columns and badges. Be extremely concise.
2. medium (max {MAX_MEDIUM} chars): For tooltips. 1-2 complete sentences.
3. long (max {MAX_LONG} chars): For documentation. Comprehensive paragraph.

RULES:
- NO "F5 Distributed Cloud" prefix (redundant in context)
- NO "API specifications" suffix (implied)
- Focus on PURPOSE and CAPABILITIES
- Use active voice
- Be specific to this domain's functionality

Respond ONLY with a JSON object containing exactly three keys: "short", "medium", and "long".
Do not use any tools. Do not search the web. Just generate the descriptions based on the context provided."""

    return prompt  # noqa: RET504


def call_claude(prompt: str, dry_run: bool = False, verbose: bool = False) -> dict[str, str] | None:
    """Call Claude Code CLI with the prompt using JSON output format.

    Args:
        prompt: The prompt to send to Claude
        dry_run: If True, print the prompt without calling Claude
        verbose: If True, print detailed debug information

    Returns:
        Dictionary with short/medium/long descriptions, or None on error
    """
    if dry_run:
        print(f"\n{'=' * 60}")
        print("DRY RUN: Would call claude -p with the following:")
        print(f"{'=' * 60}")
        print(f"\n[PROMPT]\n{prompt}\n")
        print(f"\n[JSON SCHEMA]\n{json.dumps(DESCRIPTION_SCHEMA, indent=2)}\n")
        return None

    # Build command with JSON output, schema validation, and minimal config
    # Use --strict-mcp-config and --disable-slash-commands for clean environment
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(DESCRIPTION_SCHEMA),
        "--tools",
        "",  # Disable all tools - only need text generation
        "--no-session-persistence",  # Don't save session to disk
        "--strict-mcp-config",  # Ignore all MCP configurations
        "--disable-slash-commands",  # Disable skills/slash commands
        "--append-system-prompt",
        "You are generating API descriptions. Respond ONLY with JSON matching the schema. Do not use any tools.",
    ]

    if verbose:
        print(f"\n[COMMAND]\n{' '.join(cmd[:4])} ...")
        print(f"\n[PROMPT]\n{prompt}\n")

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if verbose:
            print(f"\n[RETURN CODE] {result.returncode}")
            if result.stderr:
                print(f"[STDERR]\n{result.stderr}")
            print(f"\n[STDOUT]\n{result.stdout[:1000]}...")

        if result.returncode != 0:
            print(f"Error: Claude CLI returned {result.returncode}")
            print(f"stderr: {result.stderr}")
            return None

        # Parse JSON response
        return parse_claude_output(result.stdout.strip(), verbose=verbose)

    except subprocess.TimeoutExpired:
        print("Error: Claude CLI timed out after 120 seconds")
        return None
    except FileNotFoundError:
        print("Error: 'claude' CLI not found. Please install Claude Code.")
        return None


def parse_claude_output(output: str, verbose: bool = False) -> dict[str, str] | None:
    """Parse JSON output from Claude Code CLI.

    The JSON response has structure:
    {
        "type": "result",
        "structured_output": {"short": ..., "medium": ..., "long": ...},
        ...
    }

    Args:
        output: Raw JSON string from Claude CLI
        verbose: If True, print debug information

    Returns:
        Dictionary with short/medium/long descriptions, or None on error
    """
    if not output:
        return None

    try:
        data = json.loads(output)

        if verbose:
            print(f"\n[PARSED JSON STRUCTURE]\n{json.dumps(data, indent=2)[:500]}...")

        # Claude JSON output with --json-schema puts result in "structured_output"
        result = data.get("structured_output")

        if result is None:
            # Fallback to "result" field for older format
            result = data.get("result", data)

        if not isinstance(result, dict):
            print(f"Error: Expected dict, got {type(result)}")
            if verbose:
                print(f"  Available keys: {list(data.keys())}")
            return None

        # Extract description tiers
        descriptions = {}
        for tier in ["short", "medium", "long"]:
            value = result.get(tier, "")
            if isinstance(value, str):
                descriptions[tier] = value.strip()

        if verbose:
            print("\n[EXTRACTED DESCRIPTIONS]")
            for tier, desc in descriptions.items():
                print(f"  {tier}: {desc[:60]}...")

        return descriptions if descriptions else None

    except json.JSONDecodeError as e:
        print(f"Error parsing Claude output as JSON: {e}")
        print(f"Raw output: {output[:500]}...")
        return None


def validate_descriptions(descriptions: dict[str, str]) -> dict[str, str]:
    """Validate and truncate descriptions to max lengths."""
    validated = {}

    for tier, max_len in [("short", MAX_SHORT), ("medium", MAX_MEDIUM), ("long", MAX_LONG)]:
        value = descriptions.get(tier, "")
        if len(value) > max_len:
            # Truncate at word boundary
            truncated = value[: max_len - 3].rsplit(" ", 1)[0] + "..."
            validated[tier] = truncated
            print(f"  Warning: {tier} truncated from {len(value)} to {len(truncated)} chars")
        else:
            validated[tier] = value

    return validated


def generate_for_domain(
    domain: str,
    config: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Generate descriptions for a single domain.

    Args:
        domain: Domain name to generate descriptions for
        config: Configuration dictionary to update
        force: If True, regenerate even if descriptions exist
        dry_run: If True, show prompt without calling Claude
        verbose: If True, show detailed debug output

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'=' * 60}")
    print(f"Processing domain: {domain}")
    print(f"{'=' * 60}")

    # Compute current source patterns hash for change detection
    current_hash = compute_source_patterns_hash(domain)

    # Check if already configured and whether source specs have changed
    existing_config = config.get("domains", {}).get(domain, {})
    if existing_config and not force:
        stored_hash = existing_config.get("source_patterns_hash")
        if stored_hash == current_hash:
            print("  Skipping: descriptions exist and source specs unchanged")
            return True
        if stored_hash:
            print("  Source specs changed (hash mismatch), regenerating...")
        else:
            print("  Skipping: descriptions already exist (use --force to regenerate)")
            return True

    # Gather context
    context = get_domain_context(domain)
    if context.get("spec_count", 0) == 0:
        print(f"  Warning: No source specs found for domain '{domain}'")

    # Build prompt
    prompt = build_prompt(domain, context)
    print(
        f"  Context gathered: {context.get('spec_count', 0)} specs, {len(context.get('paths', []))} paths",
    )

    # Call Claude (returns parsed dict directly)
    print("  Calling Claude Code CLI...")
    descriptions = call_claude(prompt, dry_run=dry_run, verbose=verbose)

    if dry_run:
        return True

    if not descriptions:
        print("  Error: No descriptions returned from Claude")
        return False

    # Validate lengths
    descriptions = validate_descriptions(descriptions)

    # Update config with descriptions and source hash for change detection
    if "domains" not in config:
        config["domains"] = {}

    config["domains"][domain] = {
        "source_patterns_hash": current_hash,
        "short": descriptions.get("short", ""),
        "medium": descriptions.get("medium", ""),
        "long": descriptions.get("long", ""),
    }

    print("  Generated descriptions:")
    print(
        f"    short ({len(descriptions.get('short', ''))} chars): {descriptions.get('short', '')[:60]}...",
    )
    print(
        f"    medium ({len(descriptions.get('medium', ''))} chars): {descriptions.get('medium', '')[:80]}...",
    )
    print(
        f"    long ({len(descriptions.get('long', ''))} chars): {descriptions.get('long', '')[:100]}...",
    )

    return True


def get_all_domains() -> list[str]:
    """Get all domains from domain patterns config."""
    categorizer = DomainCategorizer()
    return categorizer.get_all_domains()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate enriched domain descriptions using Claude Code CLI",
    )
    parser.add_argument(
        "--domain",
        help="Generate for specific domain (e.g., 'virtual', 'dns')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate for all domains without existing descriptions",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if descriptions exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompts without calling Claude",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed debug output (prompt, command, response)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all domains and their description status",
    )

    args = parser.parse_args()

    # Load existing config
    config = load_config()
    existing_domains = set(config.get("domains", {}).keys())

    if args.list:
        all_domains = get_all_domains()
        print(
            f"\nDomain Description Status ({len(existing_domains)}/{len(all_domains)} configured):",
        )
        print("=" * 60)
        for domain in sorted(all_domains):
            status = "✓" if domain in existing_domains else "✗"
            print(f"  {status} {domain}")
        return 0

    if not args.domain and not args.all:
        parser.error("Either --domain or --all is required (or use --list)")

    # Determine domains to process
    if args.all:
        all_domains = get_all_domains()
        domains_to_process = [d for d in all_domains if d not in existing_domains or args.force]
        print(f"\nProcessing {len(domains_to_process)} domains...")
    else:
        domains_to_process = [args.domain]

    # Process domains
    success_count = 0
    for domain in domains_to_process:
        if generate_for_domain(
            domain,
            config,
            force=args.force,
            dry_run=args.dry_run,
            verbose=args.verbose,
        ):
            success_count += 1

    # Save config (unless dry run)
    if not args.dry_run and success_count > 0:
        save_config(config)
        print(f"\n✓ Saved {success_count} descriptions to {CONFIG_PATH}")

    print(f"\nCompleted: {success_count}/{len(domains_to_process)} domains processed successfully")
    return 0 if success_count == len(domains_to_process) else 1


if __name__ == "__main__":
    sys.exit(main())
