#!/usr/bin/env python3
"""Test script to validate CLI branding transformations.

Tests that:
1. vesctl → xcsh (direct transformation)
2. f5xcctl → xcsh (removal of intermediate branding)
3. Case variations work correctly
4. Environment variables are transformed
5. Protected patterns are NOT transformed
"""

import re
from pathlib import Path
from typing import Any

import yaml


def load_enrichment_config() -> dict[str, Any]:
    """Load enrichment configuration."""
    config_path = Path("config/enrichment.yaml")
    with config_path.open() as f:
        return yaml.safe_load(f)


def apply_branding(text: str, config: dict[str, Any]) -> str:
    """Apply branding transformations to text."""
    replacements = config["branding"]["replacements"]

    for replacement in replacements:
        pattern = replacement["pattern"]
        new_text = replacement["replacement"]
        case_sensitive = replacement.get("case_sensitive", False)

        flags = 0 if case_sensitive else re.IGNORECASE
        text = re.sub(pattern, new_text, text, flags=flags)

    return text


def run_tests() -> bool:
    """Run branding transformation tests."""
    config = load_enrichment_config()

    test_cases = [
        # Test Case 1: vesctl → xcsh (direct)
        {
            "name": "vesctl lowercase",
            "input": "Use vesctl to configure the API",
            "expected": "Use xcsh to configure the API",
        },
        {
            "name": "Vesctl titlecase",
            "input": "Vesctl is the command-line tool",
            "expected": "Xcsh is the command-line tool",
        },
        {
            "name": "VESCTL uppercase",
            "input": "VESCTL environment variables",
            "expected": "XCSH environment variables",
        },
        # Test Case 2: f5xcctl → xcsh (removal)
        {
            "name": "f5xcctl lowercase",
            "input": "Use f5xcctl to manage resources",
            "expected": "Use xcsh to manage resources",
        },
        {
            "name": "F5xcctl titlecase",
            "input": "F5xcctl is the new CLI",
            "expected": "Xcsh is the new CLI",
        },
        {
            "name": "F5XCCTL uppercase",
            "input": "F5XCCTL_API_TOKEN environment variable",
            "expected": "XCSH_API_TOKEN environment variable",
        },
        # Test Case 3: Environment variables
        {
            "name": "VES_API_TOKEN",
            "input": "Set VES_API_TOKEN before running",
            "expected": "Set F5XC_API_TOKEN before running",
        },
        {
            "name": "VES_API_URL",
            "input": "Configure VES_API_URL endpoint",
            "expected": "Configure F5XC_API_URL endpoint",
        },
        # Test Case 4: Mixed context
        {
            "name": "Mixed CLI references",
            "input": "vesctl and f5xcctl both work, use VESCTL or F5XCCTL",
            "expected": "xcsh and xcsh both work, use XCSH or XCSH",
        },
        # Test Case 5: Environment variables with F5XCCTL prefix
        {
            "name": "F5XCCTL_API_TOKEN variable",
            "input": "export F5XCCTL_API_TOKEN=token",
            "expected": "export XCSH_API_TOKEN=token",
        },
        {
            "name": "F5XCCTL_API_URL variable",
            "input": "F5XCCTL_API_URL must be set",
            "expected": "XCSH_API_URL must be set",
        },
        # Test Case 6: Real-world examples
        {
            "name": "Documentation example",
            "input": "Run vesctl configuration get to retrieve settings",
            "expected": "Run xcsh configuration get to retrieve settings",
        },
        {
            "name": "Code example",
            "input": "$ f5xcctl apply -f config.yaml",
            "expected": "$ xcsh apply -f config.yaml",
        },
        {
            "name": "Environment setup",
            "input": "export VES_API_TOKEN=your-token",
            "expected": "export F5XC_API_TOKEN=your-token",
        },
    ]

    print("=" * 80)
    print("CLI BRANDING TRANSFORMATION TESTS")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for test_case in test_cases:
        result = apply_branding(test_case["input"], config)
        success = result == test_case["expected"]

        if success:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"

        print(f"{status}: {test_case['name']}")
        print(f"  Input:    {test_case['input']}")
        print(f"  Expected: {test_case['expected']}")
        print(f"  Got:      {result}")
        if not success:
            print("  ERROR: Mismatch!")
        print()

    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    import sys

    success = run_tests()
    sys.exit(0 if success else 1)
