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
    """Build the prompt for Claude to generate descriptions.

    Uses research-based technical writing guidelines (Google, Microsoft, Apple)
    for consistent, DRY-compliant descriptions that fit character limits naturally.
    """
    use_cases_str = "\n".join(f"  - {uc}" for uc in context.get("use_cases", []))
    paths_str = "\n".join(f"  - {p}" for p in context.get("paths", [])[:15])
    schemas_str = ", ".join(context.get("schemas", [])[:20])

    # Domain name variants to ban (the domain and common transforms)
    domain_variants = domain.replace("_", " ")

    prompt = f"""Generate 3-tier descriptions for the "{context["domain_title"]}" domain.

CONTEXT:
Domain: {domain}
Category: {context.get("domain_category", "Other")}
Related: {", ".join(context.get("related_domains", []))}
Specs: {context.get("spec_count", 0)} source specifications

Use cases:
{use_cases_str or "  - (none specified)"}

Sample paths:
{paths_str or "  - (none)"}

Schemas: {schemas_str or "(none)"}

═══════════════════════════════════════════════════════════════════════════════
STRICT RULES - Violations cause output rejection:

1. BANNED TERMS (never use these):
   ✗ "F5", "F5 XC", "F5 Distributed Cloud", "Distributed Cloud", "XC"
   ✗ "API", "specifications", "spec", "endpoint"
   ✗ "comprehensive", "complete", "full", "various", "extensive"
   ✗ "{domain_variants}" (the domain name itself)

2. STYLE REQUIREMENTS:
   ✓ Start EVERY tier with action verb: Configure, Create, Manage, Define, Deploy, Set up
   ✓ Use present tense and active voice exclusively
   ✓ NEVER start with: "This", "The", "A", "An", "Provides", "Enables"

3. PROGRESSIVE INFORMATION (no repetition across tiers):
   - SHORT: Primary capability only (the core "what")
   - MEDIUM: Add secondary features + benefit (the "what else" + "why")
   - LONG: Add mechanics, options, usage context (the "how" + "when")

   CRITICAL: If a concept appears in SHORT, it MUST NOT appear in MEDIUM or LONG.
   Each tier reveals NEW information only.

═══════════════════════════════════════════════════════════════════════════════
COMPRESSION TECHNIQUES - Apply these to stay under limits:

• Remove articles: "the load balancers" → "load balancers"
• Remove qualifiers: "global distribution" → "distribution"
• Shorten phrases: "for domain resolution" → (remove entirely)
• Remove redundant words: "authoritative name services" → "name services"

NEGATIVE EXAMPLES (from actual failures - DO NOT repeat these patterns):
❌ "Configure content delivery and caching policies for global distribution" (71 chars)
   → Remove "policies for global": "Configure caching and content delivery" (38 chars) ✓

❌ "Manage zones, records, and load balancing for domain resolution" (63 chars)
   → Remove "for domain resolution": "Manage zones, records, and load balancing" (42 chars) ✓

═══════════════════════════════════════════════════════════════════════════════
CHARACTER LIMITS - WRITE TO FIT, NEVER TRUNCATE:

⚠️ CRITICAL: Write descriptions that NATURALLY fit within limits.
   NEVER write long text and truncate it. No "..." endings. No partial sentences.
   If your draft is too long, REWRITE it shorter - do not cut it off.

SHORT (TARGET: 35-50 chars, HARD MAX: {MAX_SHORT}):
  • Format: [Verb] [object]
  • Remove ALL unnecessary words
  • If over 50 chars, REMOVE WORDS (don't truncate!)
  • Examples:
    ✓ "Configure HTTP load balancers" (30 chars)
    ✓ "Manage WAF rules and bot protection" (35 chars)
    ✗ TOO LONG (71 chars): "Configure content delivery and caching..."

MEDIUM (TARGET: 100-130 chars, HARD MAX: {MAX_MEDIUM}):
  • Two short sentences
  • If over 130 chars, REWRITE with fewer words (don't truncate!)
  • Example (82 chars): "Define routing rules and health checks. Enable failover."
  • AVOID long phrases like "with support for BIND and AXFR transfer protocols"

LONG (TARGET: 350-450 chars, HARD MAX: {MAX_LONG}):
  • 3-4 sentences, stay under 450 to be safe
  • If over 450 chars, SIMPLIFY sentences (don't truncate!)
  • Remove verbose qualifiers ("authoritative", "global", "comprehensive")

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT:

Respond with JSON only: {{"short": "...", "medium": "...", "long": "..."}}

BEFORE RESPONDING - MANDATORY VERIFICATION:

⚠️ NEVER TRUNCATE - If any tier exceeds its target, REWRITE IT SHORTER.
   Truncated text with "..." is REJECTED. Incomplete sentences are REJECTED.

□ Count SHORT chars: Must be ≤50 (if >50, REWRITE SHORTER - do not cut off!)
□ Count MEDIUM chars: Must be ≤130 (if >130, REWRITE SHORTER - do not cut off!)
□ Count LONG chars: Must be ≤450 (if >450, REWRITE SHORTER - do not cut off!)
□ Verify no banned terms (F5, XC, comprehensive, etc.)
□ Confirm each tier starts with action verb
□ Verify no ellipsis ("...") or incomplete sentences

Do not use any tools. Generate based on context provided."""

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


# Validation constants
BANNED_TERMS = [
    "f5",
    "f5 xc",
    "f5xc",
    "distributed cloud",
    "xc ",
    " xc",
    " api",
    "api ",
    "specifications",
    " spec",
    "spec ",
    "endpoint",
    "comprehensive",
    "complete",
    "full ",
    " full",
    "various",
    "extensive",
]

BAD_STARTERS = [
    "this",
    "the ",
    "a ",
    "an ",
    "provides",
    "enables",
    "allows",
    "offers",
]

MAX_RETRIES = 3


def check_dry_compliance(domain: str, descriptions: dict[str, str]) -> list[str]:
    """Check for DRY violations in descriptions.

    Args:
        domain: Domain name to check against
        descriptions: Dictionary with short/medium/long descriptions

    Returns:
        List of violation messages (empty if compliant)
    """
    violations: list[str] = []

    # Domain name variants to check
    domain_lower = domain.lower()
    domain_spaced = domain_lower.replace("_", " ")

    for tier, text in descriptions.items():
        text_lower = text.lower()

        # Check banned terms (use extend for performance)
        violations.extend(
            f"{tier}: Contains banned term '{term}'" for term in BANNED_TERMS if term in text_lower
        )

        # Check domain name (avoid self-reference)
        if domain_lower in text_lower or domain_spaced in text_lower:
            violations.append(f"{tier}: Contains domain name '{domain}'")

    # Check cross-tier repetition (significant words)
    # Only flag if there are more than 2 overlapping significant words
    # (some overlap is acceptable for coherence)
    short_words = set(_extract_significant_words(descriptions.get("short", "")))
    medium_words = set(_extract_significant_words(descriptions.get("medium", "")))
    long_words = set(_extract_significant_words(descriptions.get("long", "")))

    # Short words should not appear in medium/long (threshold: >2 overlapping)
    short_in_medium = short_words & medium_words
    short_in_long = short_words & long_words
    medium_in_long = medium_words & long_words

    min_overlap_threshold = 4  # Only flag if >=4 significant words overlap
    if len(short_in_medium) >= min_overlap_threshold:
        violations.append(
            f"Repetition: short→medium overlap ({len(short_in_medium)} words): {short_in_medium}",
        )
    if len(short_in_long) >= min_overlap_threshold:
        violations.append(
            f"Repetition: short→long overlap ({len(short_in_long)} words): {short_in_long}",
        )
    if len(medium_in_long) >= min_overlap_threshold:
        violations.append(
            f"Repetition: medium→long overlap ({len(medium_in_long)} words): {medium_in_long}",
        )

    return violations


def _extract_significant_words(text: str) -> list[str]:
    """Extract significant words from text (excluding common stop words).

    Returns words that are meaningful for repetition detection.
    Excludes common technical terms that naturally appear across tiers.
    """
    stop_words = {
        # Common English stop words
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "about",
        "into",
        "through",
        "during",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "used",
        "as",
        "if",
        "when",
        "than",
        "because",
        "while",
        "although",
        "where",
        "after",
        "so",
        "though",
        "since",
        "until",
        "unless",
        "that",
        "which",
        "who",
        "whom",
        "this",
        "these",
        "those",
        "it",
        "its",
        "their",
        "your",
        "our",
        "my",
        # Common action verbs (expected in all tiers)
        "configure",
        "create",
        "manage",
        "define",
        "deploy",
        "set",
        "use",
        "enable",
        "support",
        "include",
        "provide",
        "specify",
        "implement",
        "apply",
        "establish",
        "monitor",
        "control",
        "handle",
        "process",
        # Common technical terms (acceptable in multiple tiers)
        "rules",
        "policies",
        "settings",
        "options",
        "parameters",
        "values",
        "security",
        "protection",
        "traffic",
        "requests",
        "responses",
        "load",
        "balancer",
        "balancers",
        "balancing",
        "origin",
        "origins",
        "pool",
        "pools",
        "server",
        "servers",
        "service",
        "services",
        "application",
        "applications",
        "network",
        "networks",
        "cloud",
        "configuration",
        "configurations",
        "management",
        "routing",
        "health",
        "checks",
        "monitoring",
        "logging",
        "analytics",
        "authentication",
        "authorization",
        "access",
        "certificate",
        "certificates",
        "dns",
        "domain",
        "domains",
        "zone",
        "zones",
        "record",
        "records",
        "waf",
        "firewall",
        "bot",
        "rate",
        "limiting",
        "ddos",
        "mitigation",
        "api",
        "apis",
        "endpoint",
        "endpoints",
        "gateway",
        "gateways",
        "http",
        "https",
        "tcp",
        "tls",
        "ssl",
        "web",
        "data",
        "based",
        "multiple",
        "custom",
        "advanced",
        "automated",
        "automatic",
        # CDN-specific terms
        "content",
        "delivery",
        "caching",
        "cache",
        "cached",
        "edge",
        "edges",
        "distribution",
        "distributed",
        "latency",
        "performance",
        # DNS-specific terms
        "resolver",
        "resolvers",
        "lookup",
        "lookups",
        "query",
        "queries",
        "nameserver",
        "nameservers",
        "delegation",
        "propagation",
        # Attack/security-specific terms
        "attack",
        "attacks",
        "signature",
        "signatures",
        "detection",
        "threat",
        "threats",
        "malicious",
        "injection",
        "blocking",
    }

    words = text.lower().split()
    return [w.strip(".,;:!?()[]{}\"'") for w in words if len(w) > 4 and w.lower() not in stop_words]


def check_character_limits(descriptions: dict[str, str]) -> list[str]:
    """Check character limits without truncation.

    Args:
        descriptions: Dictionary with short/medium/long descriptions

    Returns:
        List of violation messages (empty if compliant)
    """
    violations = []
    limits = {"short": MAX_SHORT, "medium": MAX_MEDIUM, "long": MAX_LONG}

    for tier, limit in limits.items():
        text = descriptions.get(tier, "")
        if len(text) > limit:
            violations.append(f"{tier}: Exceeds {limit} chars ({len(text)} chars)")

    return violations


def check_style_compliance(descriptions: dict[str, str]) -> list[str]:
    """Check style compliance (active voice, verb-first, no bad starters).

    Args:
        descriptions: Dictionary with short/medium/long descriptions

    Returns:
        List of violation messages (empty if compliant)
    """
    violations = []

    for tier, text in descriptions.items():
        text_lower = text.lower().strip()

        # Check bad starters
        for starter in BAD_STARTERS:
            if text_lower.startswith(starter):
                violations.append(
                    f"{tier}: Starts with '{starter}' - should start with action verb",
                )
                break

    return violations


def run_all_validations(domain: str, descriptions: dict[str, str]) -> list[str]:
    """Run all validation checks on descriptions.

    Args:
        domain: Domain name
        descriptions: Dictionary with short/medium/long descriptions

    Returns:
        Combined list of all violations
    """
    violations = []
    violations.extend(check_dry_compliance(domain, descriptions))
    violations.extend(check_character_limits(descriptions))
    violations.extend(check_style_compliance(descriptions))
    return violations


def build_refinement_prompt(
    domain: str,
    context: dict[str, Any],
    previous_response: dict[str, str],
    violations: list[str],
) -> str:
    """Build a refinement prompt with specific, actionable feedback.

    Instead of retrying with the same prompt, this provides the model with:
    - The previous response that failed
    - Specific violations with concrete fix instructions
    - Character reduction targets (not just "too long")

    This implements the Self-Refine approach which achieves 85-95% compliance
    vs ~50% for blind retries.

    Args:
        domain: Domain name being processed
        context: Domain context dictionary
        previous_response: The descriptions that failed validation
        violations: List of violation messages from validation

    Returns:
        Refined prompt with specific feedback
    """
    # Parse violations into actionable feedback with specific fix instructions
    feedback_items = []
    limits = {"short": MAX_SHORT, "medium": MAX_MEDIUM, "long": MAX_LONG}

    for violation in violations:
        v_lower = violation.lower()
        tier = violation.split(":")[0].lower() if ":" in violation else ""

        if "exceeds" in v_lower:
            # Character limit violation - calculate exact reduction needed
            # Expected format is tier name followed by char counts in parentheses
            try:
                current_chars = int(violation.split("(")[1].split()[0])
                max_chars = limits.get(tier, 500)
                reduction = current_chars - max_chars
                pct = (reduction * 100) // current_chars
                feedback_items.append(
                    f"❌ {tier.upper()}: {current_chars} chars → max {max_chars}. "
                    f"REMOVE {reduction} chars ({pct}% reduction). "
                    f"Cut phrases like 'and policies', 'for distribution', etc.",
                )
            except (IndexError, ValueError):
                feedback_items.append(f"❌ {violation} - SHORTEN this tier")

        elif "banned term" in v_lower:
            # Extract the banned term and suggest alternatives
            try:
                term = violation.split("'")[1]
                alternatives = {
                    "comprehensive": "broad",
                    "complete": "full-featured",
                    "extensive": "wide-ranging",
                    "specifications": "definitions",
                    "spec": "definition",
                    "api": "interface",
                    "endpoint": "path",
                }
                alt = alternatives.get(term.lower(), "(remove entirely)")
                feedback_items.append(
                    f"❌ {tier.upper()}: Remove banned term '{term}'. Alternative: {alt}",
                )
            except IndexError:
                feedback_items.append(f"❌ {violation}")

        elif "domain name" in v_lower:
            feedback_items.append(
                f"❌ {tier.upper()}: Self-references domain '{domain}'. "
                f"Never mention the domain name in its own description.",
            )

        elif "starts with" in v_lower:
            try:
                starter = violation.split("'")[1]
                feedback_items.append(
                    f"❌ {tier.upper()}: Starts with '{starter}'. "
                    f"MUST start with action verb: Configure, Create, Manage, Define, Deploy",
                )
            except IndexError:
                feedback_items.append(f"❌ {violation}")

        elif "repetition" in v_lower:
            feedback_items.append(
                f"❌ {violation}. Use DIFFERENT words in each tier - no overlap.",
            )

        else:
            feedback_items.append(f"❌ {violation}")

    feedback_str = "\n".join(feedback_items)
    prev_json = json.dumps(previous_response, indent=2)

    # Current character counts for reference
    char_counts = {
        tier: len(previous_response.get(tier, "")) for tier in ["short", "medium", "long"]
    }
    counts_str = ", ".join(f"{t}: {c}" for t, c in char_counts.items())

    return f"""Your previous response for "{context["domain_title"]}" domain FAILED validation.

PREVIOUS RESPONSE (char counts: {counts_str}):
{prev_json}

═══════════════════════════════════════════════════════════════════════════════
SPECIFIC VIOLATIONS TO FIX:
{feedback_str}

═══════════════════════════════════════════════════════════════════════════════
FIX INSTRUCTIONS:

1. For CHARACTER LIMIT violations:
   - Count characters in your draft BEFORE responding
   - SHORT must be ≤{MAX_SHORT} chars (aim for 35-50)
   - MEDIUM must be ≤{MAX_MEDIUM} chars (aim for 100-130)
   - LONG must be ≤{MAX_LONG} chars (aim for 350-450)
   - Remove words/phrases, don't truncate with "..."

2. For BANNED TERM violations:
   - Remove or replace the specific term mentioned
   - Never use: F5, XC, API, spec, comprehensive, complete, full, various, extensive

3. For STYLE violations:
   - Start EVERY tier with action verb: Configure, Create, Manage, Define, Deploy, Set up
   - Never start with: This, The, A, An, Provides, Enables

4. For REPETITION violations:
   - Each tier must use DIFFERENT words
   - If SHORT says "load balancers", MEDIUM/LONG cannot

═══════════════════════════════════════════════════════════════════════════════
OUTPUT:

Respond with CORRECTED JSON only. Fix ALL violations listed above.
{{"short": "...", "medium": "...", "long": "..."}}

Do not use any tools. Generate corrected output based on the feedback."""


def create_violation_issue(
    domain: str,
    violations: list[str],
    prompt: str,
    response: str,
) -> bool:
    """Create GitHub issue when generation fails validation after retries.

    Args:
        domain: Domain that failed validation
        violations: List of violation messages
        prompt: The prompt that was used
        response: The response that was generated

    Returns:
        True if issue was created successfully
    """
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    violations_list = "\n".join(f"- {v}" for v in violations)

    # Truncate prompt for readability (keep first 2000 chars)
    prompt_truncated = prompt[:2000] + "..." if len(prompt) > 2000 else prompt

    title = f"Description generation violation: {domain}"
    body = f"""## Violation Report

**Domain**: `{domain}`
**Timestamp**: {timestamp}
**Retry Attempts**: {MAX_RETRIES}

### Violations Detected

{violations_list}

### Prompt Used

```
{prompt_truncated}
```

### Generated Response

```json
{response}
```

### Expected Behavior

Descriptions should:
- Not contain F5/XC/Distributed Cloud references
- Not mention domain name in own description
- Fit within character limits without truncation (60/150/500)
- Start with action verbs (Configure, Create, Manage, etc.)
- Have no cross-tier repetition

### Next Steps

1. Analyze why the prompt failed to produce compliant output
2. Update `build_prompt()` in `scripts/generate_descriptions.py` with refined instructions
3. Re-test with this domain: `python -m scripts.generate_descriptions --domain {domain} --force`

---
🤖 Generated automatically by description generation script
"""

    try:
        # Create issue without labels (labels may not exist in repo)
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                body,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print(f"  ✓ Created GitHub issue: {result.stdout.strip()}")
            return True
        print(f"  Warning: Failed to create GitHub issue: {result.stderr}")
        return False

    except FileNotFoundError:
        print("  Warning: 'gh' CLI not found. Cannot create GitHub issue.")
        return False


def generate_for_domain(
    domain: str,
    config: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Generate descriptions for a single domain with validation and retry.

    Uses a retry loop (up to MAX_RETRIES attempts) to ensure descriptions
    meet all DRY, character limit, and style requirements. Creates a GitHub
    issue for prompt refinement if all retries are exhausted.

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

    if dry_run:
        print(f"\n{'=' * 60}")
        print("DRY RUN: Would call claude -p with the following:")
        print(f"{'=' * 60}")
        print(f"\n[PROMPT]\n{prompt}\n")
        return True

    # Self-refine loop with specific feedback (not blind retry)
    # Research shows self-refine achieves 85-95% compliance vs ~50% for blind retries
    last_descriptions = None
    last_response = ""
    violations = []
    current_prompt = prompt  # Start with initial prompt, switch to refinement on retry

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"  Attempt {attempt}/{MAX_RETRIES}: Calling Claude Code CLI...")
        descriptions = call_claude(current_prompt, dry_run=False, verbose=verbose)

        if not descriptions:
            print(f"  Attempt {attempt}: No descriptions returned from Claude")
            continue

        last_descriptions = descriptions
        last_response = json.dumps(descriptions, indent=2)

        # Run all validations
        violations = run_all_validations(domain, descriptions)

        if not violations:
            print(f"  ✓ Attempt {attempt}: All validations passed")
            break

        # Print violations with character counts for transparency
        char_info = ", ".join(
            f"{t}: {len(descriptions.get(t, ''))}" for t in ["short", "medium", "long"]
        )
        print(f"  Attempt {attempt}: {len(violations)} violation(s) detected (chars: {char_info}):")
        for v in violations[:5]:  # Show first 5 violations
            print(f"    - {v}")
        if len(violations) > 5:
            print(f"    ... and {len(violations) - 5} more")

        if attempt < MAX_RETRIES:
            # Build refinement prompt with specific feedback (Self-Refine approach)
            current_prompt = build_refinement_prompt(domain, context, descriptions, violations)
            print("  Building refinement prompt with specific feedback...")

    # Check if we succeeded
    if violations:
        print(f"\n  ✗ All {MAX_RETRIES} attempts failed validation. Creating GitHub issue...")
        create_violation_issue(domain, violations, prompt, last_response)
        return False

    if not last_descriptions:
        print("  Error: No valid descriptions generated after all attempts")
        return False

    # Validate lengths (truncate if needed, but this shouldn't happen with good prompts)
    descriptions = validate_descriptions(last_descriptions)

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
        f"    short ({len(descriptions.get('short', ''))} chars): {descriptions.get('short', '')}",
    )
    print(
        f"    medium ({len(descriptions.get('medium', ''))} chars): {descriptions.get('medium', '')}",
    )
    print(
        f"    long ({len(descriptions.get('long', ''))} chars): {descriptions.get('long', '')[:150]}...",
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
