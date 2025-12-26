#!/usr/bin/env python3
"""Automated branding transformations for API specification text fields.

Applies consistent F5 branding by replacing legacy Volterra references
and industry-standard terminology (XCKS/XCCS) for Kubernetes offerings.
Fully automated - no manual intervention required.

Branding Strategy:
  - XCKS (XC Kubernetes Service) = AppStack/VoltStack (comparable to AWS EKS, Azure AKS, GCP GKE)
  - XCCS (XC Container Services) = Virtual Kubernetes (comparable to AWS ECS, Azure Container Services)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml


@dataclass
class BrandingStats:
    """Statistics from branding transformations."""

    legacy_terms_replaced: int = 0
    xks_transformations: int = 0
    xcs_transformations: int = 0
    glossary_terms_added: int = 0
    files_processed: int = 0
    transformations_by_type: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "legacy_terms_replaced": self.legacy_terms_replaced,
            "xks_transformations": self.xks_transformations,
            "xcs_transformations": self.xcs_transformations,
            "glossary_terms_added": self.glossary_terms_added,
            "files_processed": self.files_processed,
            "transformations_by_type": self.transformations_by_type,
        }


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


class BrandingNormalizer:
    """Normalizes F5 XC Kubernetes terminology to industry-standard naming.

    Transforms legacy marketing terms to customer-friendly, industry-aligned names:
    - AppStack/VoltStack → F5 XC Managed Kubernetes (XCKS) - like AWS EKS, Azure AKS
    - Virtual Kubernetes → F5 XC Container Services (XCCS) - like AWS ECS

    Configuration-driven from config/branding.yaml.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize with branding configuration.

        Args:
            config_path: Path to branding.yaml config. Defaults to config/branding.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "branding.yaml"

        self.config_path = config_path
        self.canonical: dict[str, Any] = {}
        self.transformations: list[dict[str, Any]] = []
        self.glossary: dict[str, Any] = {}
        self.domain_branding: dict[str, Any] = {}
        self._compiled_patterns: list[tuple[re.Pattern, str, list[str], str]] = []
        self.stats = BrandingStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load branding configuration from YAML file."""
        if not self.config_path.exists():
            # Use built-in defaults if config doesn't exist
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.canonical = config.get("canonical", {})
            self.transformations = config.get("transformations", [])
            self.glossary = config.get("glossary", {})
            self.domain_branding = config.get("domain_branding", {})

            self._compile_patterns()
        except Exception:
            # Fall back to defaults on any config error
            self._use_default_config()

    def _use_default_config(self) -> None:
        """Use built-in default XCKS/XCCS branding rules."""
        self.canonical = {
            "managed_kubernetes": {
                "long_form": "F5 XC Managed Kubernetes",
                "short_form": "XCKS",
                "full_acronym": "XC Kubernetes Service",
                "legacy_names": ["AppStack", "VoltStack", "voltstack_site"],
                "comparable_to": ["AWS EKS", "Azure AKS", "Google GKE"],
            },
            "container_services": {
                "long_form": "F5 XC Container Services",
                "short_form": "XCCS",
                "full_acronym": "XC Container Services",
                "legacy_names": ["Virtual Kubernetes", "vK8s", "virtual_k8s"],
                "comparable_to": ["AWS ECS", "Azure Container Services", "Cloud Run"],
            },
        }

        self.transformations = [
            {
                "pattern": r"\bVirtual Kubernetes\b",
                "replacement": "F5 XC Container Services (XCCS)",
                "context": ["info.description", "operation.description", "schema.description"],
                "case_sensitive": False,
            },
            {
                "pattern": r"\bvK8s\b",
                "replacement": "XCCS",
                "context": ["info.description", "operation.description"],
                "case_sensitive": True,
            },
            {
                "pattern": r"\bAppStack\b",
                "replacement": "F5 XC Managed Kubernetes (XCKS)",
                "context": ["info.description", "operation.description", "schema.description"],
                "case_sensitive": False,
            },
            {
                "pattern": r"\bVoltStack\b",
                "replacement": "F5 XC Managed Kubernetes (XCKS)",
                "context": ["info.description", "operation.description", "schema.description"],
                "case_sensitive": False,
            },
        ]

        self.glossary = {
            "XCKS": {
                "term": "XC Kubernetes Service",
                "definition": "F5's enterprise managed Kubernetes offering (comparable to AWS EKS, Azure AKS)",
                "legacy": "Formerly known as AppStack",
            },
            "XCCS": {
                "term": "XC Container Services",
                "definition": "F5's multi-tenant container orchestration service (comparable to AWS ECS)",
                "legacy": "Formerly known as Virtual Kubernetes (vK8s)",
            },
        }

        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for efficient matching."""
        self._compiled_patterns = []

        for rule in self.transformations:
            pattern_str = rule.get("pattern", "")
            replacement = rule.get("replacement", "")
            context = rule.get("context", [])
            case_sensitive = rule.get("case_sensitive", True)

            flags = 0 if case_sensitive else re.IGNORECASE

            try:
                pattern = re.compile(pattern_str, flags)
                # Determine transformation type for stats tracking
                trans_type = (
                    "xcs" if "XCCS" in replacement else "xks" if "XCKS" in replacement else "other"
                )
                self._compiled_patterns.append((pattern, replacement, context, trans_type))
            except re.error:
                # Skip invalid patterns
                continue

    def normalize_text(self, text: str, field_context: str = "") -> str:
        """Apply XCKS/XCCS terminology normalization to text.

        Args:
            text: Input text with legacy terminology.
            field_context: Field path context for selective application.

        Returns:
            Text with normalized terminology.
        """
        if not text or not isinstance(text, str):
            return text

        result = text

        for pattern, replacement, contexts, trans_type in self._compiled_patterns:
            # Check if this transformation applies to the current context
            if contexts and field_context:
                # Check if any context pattern matches the field path
                matches_context = any(ctx in field_context for ctx in contexts)
                if not matches_context:
                    continue

            # Check if pattern matches and apply replacement
            if pattern.search(result):
                new_result = pattern.sub(replacement, result)
                if new_result != result:
                    # Track statistics
                    if trans_type == "xcs":
                        self.stats.xcs_transformations += 1
                    elif trans_type == "xks":
                        self.stats.xks_transformations += 1

                    self.stats.transformations_by_type[trans_type] = (
                        self.stats.transformations_by_type.get(trans_type, 0) + 1
                    )
                    result = new_result

        return result

    def normalize_spec(
        self,
        spec: dict[str, Any],
        target_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Apply XCKS/XCCS terminology normalization to an OpenAPI specification.

        Args:
            spec: OpenAPI specification dictionary.
            target_fields: List of field names to process.

        Returns:
            Specification with normalized terminology.
        """
        if target_fields is None:
            target_fields = ["description", "summary", "title", "x-displayname"]

        self.stats.files_processed += 1
        result = self._normalize_recursive(spec, target_fields, "")

        # Optionally add glossary to spec info
        if self.glossary and "info" in result:
            result = self._add_glossary_to_info(result)

        return result

    def _normalize_recursive(
        self,
        obj: Any,
        target_fields: list[str],
        current_path: str,
    ) -> Any:
        """Recursively process object and normalize text fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                new_path = f"{current_path}.{key}" if current_path else key

                if key in target_fields and isinstance(value, str):
                    result[key] = self.normalize_text(value, field_context=new_path)
                else:
                    result[key] = self._normalize_recursive(value, target_fields, new_path)
            return result

        if isinstance(obj, list):
            return [self._normalize_recursive(item, target_fields, current_path) for item in obj]

        return obj

    def _add_glossary_to_info(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Add glossary terms to spec info section.

        Args:
            spec: OpenAPI specification dictionary.

        Returns:
            Specification with glossary added to info.
        """
        if "info" not in spec:
            return spec

        # Check if glossary already exists
        existing_glossary = spec["info"].get("x-ves-glossary", {})

        # Merge our glossary terms
        for term, definition in self.glossary.items():
            if term not in existing_glossary:
                existing_glossary[term] = definition
                self.stats.glossary_terms_added += 1

        if existing_glossary:
            spec["info"]["x-ves-glossary"] = existing_glossary

        return spec

    def get_canonical_name(self, domain: str) -> dict[str, Any] | None:
        """Get canonical naming information for a domain.

        Args:
            domain: Domain identifier (e.g., "managed_kubernetes", "container_services").

        Returns:
            Dictionary with long_form, short_form, comparable_to, etc. or None.
        """
        return self.canonical.get(domain)

    def get_domain_branding(self, domain: str) -> dict[str, Any] | None:
        """Get domain-specific branding information.

        Args:
            domain: Domain identifier.

        Returns:
            Dictionary with title and description for the domain or None.
        """
        return self.domain_branding.get(domain)

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about branding normalizations applied."""
        return self.stats.to_dict()

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = BrandingStats()
