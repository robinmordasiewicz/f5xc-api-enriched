#!/usr/bin/env python3
"""Automated branding transformations for API specification text fields.

Applies consistent F5 branding by replacing legacy Volterra references.
Fully automated - no manual intervention required.
"""

import re
from pathlib import Path
from typing import Any, ClassVar

import yaml


class BrandingTransformer:
    """Transforms legacy branding to current F5 branding in API specifications.

    Fully automated branding updates with configurable rules.
    Loads rules from config/enrichment.yaml.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize with branding rules from config file.

        Args:
            config_path: Path to enrichment.yaml config. Defaults to config/enrichment.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "enrichment.yaml"

        self.replacements: list[dict[str, Any]] = []
        self._compiled_patterns: list[tuple[re.Pattern, str, str | None]] = []
        self._preserve_fields: set[str] = set()

        self._load_config(config_path)
        self._compile_patterns()

    def _load_config(self, config_path: Path) -> None:
        """Load branding rules from YAML config."""
        if not config_path.exists():
            # Use default rules if config doesn't exist
            self.replacements = [
                {
                    "pattern": r"\bVolterra\b",
                    "replacement": "F5 Distributed Cloud",
                    "case_sensitive": True,
                },
                {
                    "pattern": r"\bvolterra\b",
                    "replacement": "F5 Distributed Cloud",
                    "case_sensitive": False,
                },
                {
                    "pattern": r"\bves\.io\b",
                    "replacement": "F5 XC",
                    "case_sensitive": False,
                    "context": "description",
                },
            ]
            self._preserve_fields = {
                "operationId",
                "$ref",
                "x-ves-proto-rpc",
                "x-ves-proto-service",
            }
            return

        with config_path.open() as f:
            config = yaml.safe_load(f) or {}

        branding = config.get("branding", {})
        self.replacements = branding.get("replacements", [])
        self._preserve_fields = set(config.get("preserve_fields", []))

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficient matching."""
        for rule in self.replacements:
            pattern_str = rule.get("pattern", "")
            replacement = rule.get("replacement", "")
            context = rule.get("context")
            case_sensitive = rule.get("case_sensitive", True)

            flags = 0 if case_sensitive else re.IGNORECASE

            try:
                pattern = re.compile(pattern_str, flags)
                self._compiled_patterns.append((pattern, replacement, context))
            except re.error:
                # Skip invalid patterns
                continue

    def transform_text(self, text: str, field_name: str | None = None) -> str:
        """Apply branding transformations to a text string.

        Args:
            text: Input text with legacy branding.
            field_name: Name of the field being transformed (for context filtering).

        Returns:
            Text with updated branding.
        """
        if not text or not isinstance(text, str):
            return text

        result = text

        for pattern, replacement, context in self._compiled_patterns:
            # Skip if context is specified and doesn't match field name
            if context is not None and field_name is not None and field_name != context:
                continue

            result = pattern.sub(replacement, result)

        return result

    def transform_spec(
        self,
        spec: dict[str, Any],
        target_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Recursively apply branding transformations to an OpenAPI specification.

        Args:
            spec: OpenAPI specification dictionary.
            target_fields: List of field names to process.

        Returns:
            Specification with updated branding in target fields.
        """
        if target_fields is None:
            target_fields = ["description", "summary", "title", "x-displayname"]

        return self._transform_recursive(spec, target_fields)

    def _transform_recursive(
        self,
        obj: Any,
        target_fields: list[str],
        current_path: str = "",
    ) -> Any:
        """Recursively process object and transform text fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Skip preserved fields
                if key in self._preserve_fields:
                    result[key] = value
                    continue

                new_path = f"{current_path}.{key}" if current_path else key

                if key in target_fields and isinstance(value, str):
                    result[key] = self.transform_text(value, field_name=key)
                else:
                    result[key] = self._transform_recursive(value, target_fields, new_path)
            return result
        if isinstance(obj, list):
            return [self._transform_recursive(item, target_fields, current_path) for item in obj]
        return obj

    def get_stats(self) -> dict[str, int]:
        """Return statistics about loaded branding rules."""
        return {
            "replacement_count": len(self.replacements),
            "pattern_count": len(self._compiled_patterns),
            "preserve_field_count": len(self._preserve_fields),
        }


class BrandingValidator:
    """Validates that branding transformations were applied correctly.

    Checks for remaining legacy branding terms that should have been replaced.
    """

    # Terms that should not appear after branding transformation
    LEGACY_TERMS: ClassVar[list[str]] = [
        r"\bVolterra\b",
        r"\bvolterra\b",
        r"\bves\.io\b",
        r"\bVES\b",
    ]

    def __init__(self) -> None:
        """Initialize validator with legacy term patterns."""
        self._legacy_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.LEGACY_TERMS
        ]

    def validate_text(self, text: str) -> list[dict[str, Any]]:
        """Check text for remaining legacy branding terms.

        Args:
            text: Text to validate.

        Returns:
            List of found legacy terms with positions.
        """
        if not text or not isinstance(text, str):
            return []

        findings: list[dict[str, Any]] = []
        for pattern in self._legacy_patterns:
            findings.extend(
                {
                    "term": match.group(0),
                    "position": match.start(),
                    "context": text[max(0, match.start() - 20) : match.end() + 20],
                }
                for match in pattern.finditer(text)
            )

        return findings

    def validate_spec(
        self,
        spec: dict[str, Any],
        target_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate an OpenAPI specification for legacy branding.

        Args:
            spec: OpenAPI specification dictionary.
            target_fields: List of field names to check.

        Returns:
            List of found legacy terms with field paths.
        """
        if target_fields is None:
            target_fields = ["description", "summary", "title", "x-displayname"]

        findings: list[dict[str, Any]] = []
        self._validate_recursive(spec, target_fields, "", findings)
        return findings

    def _validate_recursive(
        self,
        obj: Any,
        target_fields: list[str],
        path: str,
        findings: list[dict[str, Any]],
    ) -> None:
        """Recursively validate object for legacy branding."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if key in target_fields and isinstance(value, str):
                    field_findings = self.validate_text(value)
                    for finding in field_findings:
                        finding["path"] = new_path
                        findings.append(finding)
                else:
                    self._validate_recursive(value, target_fields, new_path, findings)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                self._validate_recursive(item, target_fields, new_path, findings)
