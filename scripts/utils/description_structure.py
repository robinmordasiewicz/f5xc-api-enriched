#!/usr/bin/env python3
"""Description structure normalization for API specifications.

Extracts embedded metadata (examples, validation rules) to proper fields
and normalizes whitespace artifacts in description text.
"""

import re
from pathlib import Path
from typing import Any

import yaml


class DescriptionStructureTransformer:
    """Transforms description fields by extracting embedded metadata.

    Extracts Example: sections to x-ves-example field.
    Extracts Validation Rules: sections to x-validation-rules extension.
    Normalizes leading whitespace artifacts.
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize with configuration from file.

        Args:
            config_path: Path to enrichment.yaml config.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "enrichment.yaml"

        # Default configuration
        self._normalize_leading_spaces = True
        self._preserve_bullet_indentation = True
        self._extract_examples = True
        self._remove_extracted_examples = True
        self._extract_validation_rules = True
        self._remove_extracted_validation = True
        self._preserve_fields: set[str] = set()

        self._load_config(config_path)

        # Compile patterns for efficiency
        self._example_patterns = [
            # Example: `"value"` or Example: ` "value"`
            re.compile(r'\n*Example:\s*`\s*"([^"]+)"\s*`\n*', re.IGNORECASE),
            # Example: `value` (without quotes)
            re.compile(r'\n*Example:\s*`([^`]+)`\n*', re.IGNORECASE),
            # x-example: "value" embedded in description
            re.compile(r'\n*x-example:\s*"([^"]+)"\n*', re.IGNORECASE),
        ]

        # Validation rules pattern - matches multi-line validation sections
        self._validation_pattern = re.compile(
            r'\n*Validation Rules:\n((?:\s+[^\n]+\n?)+)',
            re.IGNORECASE
        )

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML config."""
        if not config_path.exists():
            return

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        desc_config = config.get("description_structure", {})
        self._normalize_leading_spaces = desc_config.get("normalize_leading_spaces", True)
        self._preserve_bullet_indentation = desc_config.get("preserve_bullet_indentation", True)
        self._extract_examples = desc_config.get("extract_examples", True)
        self._remove_extracted_examples = desc_config.get("remove_extracted_examples", True)
        self._extract_validation_rules = desc_config.get("extract_validation_rules", True)
        self._remove_extracted_validation = desc_config.get("remove_extracted_validation", True)
        self._preserve_fields = set(config.get("preserve_fields", []))

    def transform_spec(
        self,
        spec: dict[str, Any],
        target_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Apply description structure transformations to a specification.

        Args:
            spec: OpenAPI specification dictionary.
            target_fields: List of field names to process.

        Returns:
            Specification with normalized descriptions and extracted metadata.
        """
        if target_fields is None:
            target_fields = ["description"]

        return self._transform_recursive(spec, target_fields)

    def _transform_recursive(
        self,
        obj: Any,
        target_fields: list[str],
    ) -> Any:
        """Recursively process object and transform descriptions."""
        if isinstance(obj, dict):
            result = {}
            extracted_example = None
            extracted_validation = None

            for key, value in obj.items():
                # Skip preserved fields
                if key in self._preserve_fields:
                    result[key] = value
                    continue

                if key in target_fields and isinstance(value, str):
                    # Only extract examples/validation from 'description' field
                    # Other target fields just get whitespace normalization
                    if key == "description":
                        # Get existing x-ves-example if present
                        existing_example = obj.get("x-ves-example")

                        # Transform the description (extract metadata)
                        new_value, extracted_example, extracted_validation = self._transform_description(
                            value, existing_example
                        )
                        result[key] = new_value
                    else:
                        # Just normalize whitespace for non-description fields
                        if self._normalize_leading_spaces:
                            result[key] = self._cleanup_whitespace(
                                self._normalize_leading_whitespace(value)
                            )
                        else:
                            result[key] = value
                else:
                    result[key] = self._transform_recursive(value, target_fields)

            # Add extracted fields to this object level
            if extracted_example and "x-ves-example" not in result:
                result["x-ves-example"] = extracted_example

            if extracted_validation:
                result["x-validation-rules"] = extracted_validation

            return result
        elif isinstance(obj, list):
            return [
                self._transform_recursive(item, target_fields)
                for item in obj
            ]
        else:
            return obj

    def _transform_description(
        self,
        description: str,
        existing_example: str | None,
    ) -> tuple[str, str | None, dict[str, str] | None]:
        """Transform a single description field.

        Args:
            description: Original description text.
            existing_example: Existing x-ves-example value if any.

        Returns:
            Tuple of (cleaned description, extracted example, extracted validation rules).
        """
        result = description
        extracted_example = None
        extracted_validation = None

        # 1. Extract validation rules FIRST (before whitespace normalization)
        # The rules pattern depends on leading whitespace to identify rule lines
        if self._extract_validation_rules:
            result, extracted_validation = self._extract_validation_section(result)

        # 2. Extract examples
        if self._extract_examples:
            result, extracted_example = self._extract_example_section(result, existing_example)

        # 3. Normalize leading spaces (after extraction to preserve pattern matching)
        if self._normalize_leading_spaces:
            result = self._normalize_leading_whitespace(result)

        # Final cleanup - remove excessive whitespace
        result = self._cleanup_whitespace(result)

        return result, extracted_example, extracted_validation

    def _normalize_leading_whitespace(self, text: str) -> str:
        """Strip leading spaces while preserving bullet point indentation."""
        lines = text.split('\n')
        normalized = []

        for line in lines:
            if not line.strip():
                # Preserve empty lines for paragraph breaks
                normalized.append('')
            elif self._preserve_bullet_indentation and re.match(r'^\s+[*\-]', line):
                # Preserve indentation for bullets, but normalize to standard
                stripped = line.lstrip()
                indent_depth = (len(line) - len(stripped)) // 2
                normalized.append('  ' * indent_depth + stripped.rstrip())
            else:
                # Strip all leading/trailing whitespace from regular lines
                normalized.append(line.strip())

        return '\n'.join(normalized)

    def _extract_example_section(
        self,
        description: str,
        existing_example: str | None,
    ) -> tuple[str, str | None]:
        """Extract Example: section to x-ves-example field."""
        result = description
        extracted_value = existing_example

        for pattern in self._example_patterns:
            match = pattern.search(result)
            if match:
                # Only extract if we don't have an existing example
                if not extracted_value:
                    extracted_value = match.group(1).strip()

                # Remove the Example: section if configured
                if self._remove_extracted_examples:
                    result = pattern.sub('\n', result)

        return result.strip(), extracted_value

    def _extract_validation_section(
        self,
        description: str,
    ) -> tuple[str, dict[str, str] | None]:
        """Extract Validation Rules: section to x-validation-rules field."""
        match = self._validation_pattern.search(description)

        if not match:
            return description, None

        rules_text = match.group(1)
        rules = {}

        for line in rules_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Handle various rule formats
            # Format: ves.io.schema.rules.uint32.lte: 600000
            # Format: F5 XC.schema.rules.string.max_len: 64
            if ':' in line:
                # Split on first colon only
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key:
                        rules[key] = value

        # Remove the Validation Rules: section if configured
        if self._remove_extracted_validation and rules:
            result = self._validation_pattern.sub('\n', description)
        else:
            result = description

        return result.strip(), rules if rules else None

    def _cleanup_whitespace(self, text: str) -> str:
        """Final cleanup of whitespace in description."""
        # Remove excessive blank lines (more than 2 newlines in a row)
        result = re.sub(r'\n{3,}', '\n\n', text)

        # Remove leading/trailing whitespace
        result = result.strip()

        # Ensure proper spacing after sentences (but don't double-space)
        result = re.sub(r'\.  +', '. ', result)

        return result

    def get_stats(self) -> dict[str, Any]:
        """Return configuration statistics."""
        return {
            "normalize_leading_spaces": self._normalize_leading_spaces,
            "preserve_bullet_indentation": self._preserve_bullet_indentation,
            "extract_examples": self._extract_examples,
            "remove_extracted_examples": self._remove_extracted_examples,
            "extract_validation_rules": self._extract_validation_rules,
            "remove_extracted_validation": self._remove_extracted_validation,
        }
