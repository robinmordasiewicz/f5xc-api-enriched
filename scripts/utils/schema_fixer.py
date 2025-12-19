#!/usr/bin/env python3
"""Schema fixer for OpenAPI specifications.

Fixes malformed schema definitions that violate OpenAPI 3.0.3 specification,
such as schemas with 'format' but missing 'type' field.
"""

from pathlib import Path
from typing import Any

import yaml


class SchemaFixer:
    """Fixes malformed schema definitions in OpenAPI specs.

    Primary fix: Add missing 'type' field where 'format' exists alone.
    This addresses 14,000+ malformed error response schemas.
    """

    # Mapping of format values to their corresponding type
    FORMAT_TYPE_MAPPING = {
        # String formats
        "string": "string",
        "binary": "string",
        "byte": "string",
        "date": "string",
        "date-time": "string",
        "password": "string",
        "uuid": "string",
        "email": "string",
        "uri": "string",
        "hostname": "string",
        "ipv4": "string",
        "ipv6": "string",
        # Integer formats
        "int32": "integer",
        "int64": "integer",
        # Number formats
        "float": "number",
        "double": "number",
    }

    def __init__(self, config_path: Path | None = None):
        """Initialize with configuration from file.

        Args:
            config_path: Path to enrichment.yaml config.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "enrichment.yaml"

        # Default configuration
        self._fix_format_without_type = True
        self._format_type_mapping = self.FORMAT_TYPE_MAPPING.copy()

        self._load_config(config_path)

        # Statistics tracking
        self._fixes_applied = 0

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML config."""
        if not config_path.exists():
            return

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        schema_config = config.get("schema_fixes", {})
        self._fix_format_without_type = schema_config.get("fix_format_without_type", True)

        # Override format-type mappings if provided
        custom_mappings = schema_config.get("format_type_mapping", {})
        if custom_mappings:
            self._format_type_mapping.update(custom_mappings)

    def fix_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Apply schema fixes to a specification.

        Args:
            spec: OpenAPI specification dictionary.

        Returns:
            Specification with fixed schemas.
        """
        self._fixes_applied = 0
        return self._fix_recursive(spec)

    def _fix_recursive(self, obj: Any) -> Any:
        """Recursively traverse and fix schema objects."""
        if isinstance(obj, dict):
            # Check if this is a schema with format but no type
            if self._fix_format_without_type and self._needs_type_fix(obj):
                obj = self._apply_type_fix(obj)

            # Recurse into all values
            return {key: self._fix_recursive(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._fix_recursive(item) for item in obj]
        else:
            return obj

    def _needs_type_fix(self, obj: dict[str, Any]) -> bool:
        """Check if object has 'format' but no 'type' field.

        This is a common issue in error response schemas where they only
        specify format: "string" without the required type field.
        """
        # Must have 'format' field
        if "format" not in obj:
            return False

        # Must NOT have 'type' field
        if "type" in obj:
            return False

        # Must NOT be a reference (has $ref)
        if "$ref" in obj:
            return False

        # Must NOT have allOf/oneOf/anyOf (composition)
        if any(key in obj for key in ("allOf", "oneOf", "anyOf")):
            return False

        return True

    def _apply_type_fix(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Add missing 'type' field based on 'format' value."""
        format_value = obj.get("format", "")

        # Look up the appropriate type for this format
        type_value = self._format_type_mapping.get(format_value.lower(), "string")

        # Create new dict with 'type' added before other fields
        result = {"type": type_value}
        result.update(obj)

        self._fixes_applied += 1
        return result

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about fixes applied."""
        return {
            "fixes_applied": self._fixes_applied,
            "fix_format_without_type": self._fix_format_without_type,
        }
