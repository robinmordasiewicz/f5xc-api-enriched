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
    Respects protected patterns (URLs, schema refs) that should not be transformed.
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
        self._protected_patterns: list[re.Pattern] = []
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

        # Load protected patterns (URLs, schema refs that should not be transformed)
        protected = branding.get("protected_patterns", [])
        self._protected_patterns = self._compile_protected_patterns(protected)

    @staticmethod
    def _try_compile_pattern(pattern_str: str) -> re.Pattern[str] | None:
        """Try to compile a regex pattern, returning None on failure.

        Args:
            pattern_str: Regex pattern string to compile.

        Returns:
            Compiled pattern or None if invalid.
        """
        try:
            return re.compile(pattern_str)
        except re.error:
            return None

    def _compile_protected_patterns(
        self,
        patterns: list[str],
    ) -> list[re.Pattern[str]]:
        """Compile protected pattern strings to regex patterns.

        Args:
            patterns: List of regex pattern strings.

        Returns:
            List of compiled regex patterns (invalid patterns are skipped).
        """
        compiled = [self._try_compile_pattern(p) for p in patterns]
        return [p for p in compiled if p is not None]

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

    def _contains_protected_pattern(self, text: str) -> bool:
        """Check if text contains any protected pattern.

        Args:
            text: Text to check.

        Returns:
            True if text contains a protected pattern that should not be transformed.
        """
        return any(pattern.search(text) for pattern in self._protected_patterns)

    def _apply_with_protection(
        self,
        text: str,
        pattern: re.Pattern,
        replacement: str,
    ) -> str:
        """Apply replacement while protecting certain patterns.

        Splits text on protected patterns, applies replacement only to
        unprotected segments, then rejoins.

        Args:
            text: Input text.
            pattern: Compiled regex pattern to apply.
            replacement: Replacement string.

        Returns:
            Text with replacement applied to unprotected segments.
        """
        if not self._protected_patterns:
            return pattern.sub(replacement, text)

        # Build a combined pattern for all protected segments
        # NOTE: Don't wrap each pattern in () here - line 165 adds the single outer ()
        # needed for re.split() to keep delimiters. Inner () would create nested groups
        # causing re.split() to duplicate matches (each group level = one copy).
        protected_combined = "|".join(p.pattern for p in self._protected_patterns)

        try:
            split_pattern = re.compile(f"({protected_combined})")
        except re.error:
            # If combined pattern is invalid, fall back to simple replacement
            return pattern.sub(replacement, text)

        # Split on protected patterns, keeping the delimiters
        parts = split_pattern.split(text)

        # Apply replacement only to non-protected parts
        result_parts = []
        for part in parts:
            if part is None:
                continue
            # Check if this part matches any protected pattern
            is_protected = any(p.fullmatch(part) for p in self._protected_patterns)
            if is_protected:
                result_parts.append(part)
            else:
                result_parts.append(pattern.sub(replacement, part))

        return "".join(result_parts)

    def transform_text(self, text: str, field_name: str | None = None) -> str:
        """Apply branding transformations to a text string.

        Respects protected patterns (URLs, schema refs) that should not be modified.

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

            # Apply replacement with protection for special patterns
            if self._protected_patterns and self._contains_protected_pattern(result):
                result = self._apply_with_protection(result, pattern, replacement)
            else:
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
            "protected_pattern_count": len(self._protected_patterns),
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
