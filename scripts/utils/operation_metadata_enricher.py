"""Operation Metadata Enricher for OpenAPI specifications.

Adds operation-level metadata for CLI tooling:
- Required fields extraction (from request body schema)
- Danger level classification (low/medium/high)
- Side effects determination
- CLI example generation

Conservative approach: only applies well-established patterns.
Uses x-ves-* extensions to store operation metadata.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class OperationEnrichmentStats:
    """Statistics from operation metadata enrichment."""

    operations_enriched: int = 0
    required_fields_added: int = 0
    danger_levels_assigned: int = 0
    examples_generated: int = 0
    side_effects_documented: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "operations_enriched": self.operations_enriched,
            "required_fields_added": self.required_fields_added,
            "danger_levels_assigned": self.danger_levels_assigned,
            "examples_generated": self.examples_generated,
            "side_effects_documented": self.side_effects_documented,
        }


class OperationMetadataEnricher:
    """Add operation-level metadata for CLI tools.

    Enriches operations with:
    - x-ves-required-fields: List of required field paths
    - x-ves-danger-level: low/medium/high risk classification
    - x-ves-confirmation-required: Boolean for dangerous operations
    - x-ves-side-effects: Create/modify/delete effects
    - x-ves-cli-examples: CLI usage examples

    Configuration-driven from operation_metadata.yaml.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with operation metadata configuration.

        Args:
            config_path: Path to operation_metadata.yaml config.
                        Defaults to config/operation_metadata.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "operation_metadata.yaml"

        self.config_path = config_path
        self.danger_levels: dict[str, Any] = {}
        self.required_fields_config: dict[str, Any] = {}
        self.extension_prefix = "x-ves"
        self.stats = OperationEnrichmentStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load operation metadata configuration from YAML config."""
        if not self.config_path.exists():
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.danger_levels = config.get("danger_levels", {})
            self.required_fields_config = config.get("required_fields", {})
            self.extension_prefix = config.get("extension_prefix", "x-ves")
        except Exception:
            self._use_default_config()

    def _use_default_config(self) -> None:
        """Use built-in default operation metadata rules."""
        self.danger_levels = {
            "method_base_levels": {
                "GET": "low",
                "HEAD": "low",
                "OPTIONS": "low",
                "POST": "medium",
                "PUT": "medium",
                "PATCH": "medium",
                "DELETE": "high",
            },
            "escalation_patterns": [
                {
                    "pattern": r"DELETE.*/namespace",
                    "level": "high",
                    "reason": "Deletes entire namespace",
                },
                {
                    "pattern": r"DELETE.*/(security|firewall|policy)",
                    "level": "high",
                    "reason": "Security-critical deletion",
                },
                {
                    "pattern": r"POST.*/(system|global)_",
                    "level": "medium",
                    "reason": "System-level operation",
                },
            ],
        }

        self.required_fields_config = {
            "standard_create_fields": ["metadata.name", "metadata.namespace"],
        }

        self.extension_prefix = "x-ves"

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with operation metadata.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Specification with added operation metadata
        """
        if "paths" not in spec:
            return spec

        spec_copy = spec.copy()
        paths = spec_copy.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue

                # Skip non-operation items like parameters, servers, etc.
                if method.lower() not in [
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                ]:
                    continue

                self._enrich_operation(operation, method.upper(), path)

        return spec_copy

    def _enrich_operation(
        self,
        operation: dict[str, Any],
        method: str,
        path: str,
    ) -> None:
        """Enrich a single operation with metadata.

        Modifies operation dict in-place.

        Args:
            operation: Operation definition
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API path
        """
        self.stats.operations_enriched += 1

        # Extract and add required fields
        required_fields = self._extract_required_fields(operation, method)
        if required_fields:
            operation[f"{self.extension_prefix}-required-fields"] = required_fields
            self.stats.required_fields_added += 1

        # Calculate and assign danger level
        danger_level = self._calculate_danger_level(method, path, operation)
        operation[f"{self.extension_prefix}-danger-level"] = danger_level
        self.stats.danger_levels_assigned += 1

        # Add confirmation requirement for dangerous operations
        if danger_level == "high":
            operation[f"{self.extension_prefix}-confirmation-required"] = True

        # Determine and add side effects
        side_effects = self._determine_side_effects(method, path, operation)
        if side_effects:
            operation[f"{self.extension_prefix}-side-effects"] = side_effects
            self.stats.side_effects_documented += 1

        # Generate and add CLI examples
        examples = self._generate_cli_examples(method, path, operation)
        if examples:
            operation[f"{self.extension_prefix}-cli-examples"] = examples
            self.stats.examples_generated += 1

    def _extract_required_fields(
        self,
        operation: dict[str, Any],
        method: str,
    ) -> list[str]:
        """Extract required fields from operation request body.

        Args:
            operation: Operation definition
            method: HTTP method

        Returns:
            List of required field paths (e.g., ["metadata.name", "metadata.namespace"])
        """
        required = []

        # Get request body schema
        request_body = operation.get("requestBody", {})
        if request_body:
            # Get schema from request body content
            content = request_body.get("content", {})
            for media_content in content.values():
                schema = media_content.get("schema", {})
                if not schema:
                    continue

                # Extract schema.required fields
                if "required" in schema:
                    required.extend(schema["required"])

                # Handle nested properties with their own required fields
                for prop_name, prop_schema in schema.get("properties", {}).items():
                    if isinstance(prop_schema, dict) and "required" in prop_schema:
                        nested_required = prop_schema["required"]
                        required.extend(f"{prop_name}.{field}" for field in nested_required)

        # For path parameters, extract those that are required
        required.extend(
            f"path.{param.get('name')}"
            for param in operation.get("parameters", [])
            if param.get("in") == "path" and param.get("required")
        )

        # Add standard create fields for POST operations (applies even without requestBody)
        if method == "POST":
            for std_field in self.required_fields_config.get(
                "standard_create_fields",
                [],
            ):
                if std_field not in required:
                    required.append(std_field)

        return sorted(set(required))

    def _calculate_danger_level(
        self,
        method: str,
        path: str,
        operation: dict[str, Any],
    ) -> str:
        """Calculate danger level for an operation.

        Args:
            method: HTTP method
            path: API path
            operation: Operation definition

        Returns:
            Danger level: "low", "medium", or "high"
        """
        method_levels = self.danger_levels.get("method_base_levels", {})
        base_level = method_levels.get(method, "medium")

        # Check for escalation patterns
        path_method_str = f"{method} {path}"

        for escalation in self.danger_levels.get("escalation_patterns", []):
            pattern_str = escalation.get("pattern", "")
            try:
                if re.search(pattern_str, path_method_str):
                    return escalation.get("level", "high")
            except re.error:
                continue

        # Check for force/cascade flags in parameters
        has_dangerous_param = False
        for param in operation.get("parameters", []):
            param_name = param.get("name", "").lower()
            if param_name in ["force", "cascade", "delete_options"]:
                has_dangerous_param = True
                break

        # Escalate level if dangerous param found
        if has_dangerous_param:
            if base_level == "low":
                return "medium"
            if base_level == "medium":
                return "high"

        return base_level

    def _determine_side_effects(
        self,
        method: str,
        path: str,
        _operation: dict[str, Any],
    ) -> dict[str, Any]:
        """Determine side effects of an operation.

        Args:
            method: HTTP method
            path: API path
            operation: Operation definition

        Returns:
            Dictionary with creates/modifies/deletes arrays
        """
        side_effects: dict[str, Any] = {
            "creates": [],
            "modifies": [],
            "deletes": [],
        }

        # Infer from HTTP method and path
        resource_type = self._extract_resource_type(path)

        if method == "POST":
            side_effects["creates"].append(resource_type)
        elif method in ["PUT", "PATCH"]:
            side_effects["modifies"].append(resource_type)
        elif method == "DELETE":
            side_effects["deletes"].append(resource_type)

        # Check for related resources affected
        if "namespace" in path and method == "DELETE":
            # Deleting namespace affects contained resources
            side_effects["deletes"].append("contained_resources")

        # Remove empty arrays
        return {k: v for k, v in side_effects.items() if v}

    def _generate_cli_examples(
        self,
        method: str,
        path: str,
        _operation: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Generate CLI usage examples for an operation.

        Args:
            method: HTTP method
            path: API path
            operation: Operation definition

        Returns:
            List of example objects with description and command
        """
        examples = []
        resource_type = self._extract_resource_type(path)
        domain = self._extract_domain(path)

        if method == "GET":
            if "{name}" in path or "{id}" in path:
                # Get specific resource
                examples.append(
                    {
                        "description": f"Get specific {resource_type}",
                        "command": f"f5xcctl {domain} {resource_type} get {{name}} --namespace {{namespace}}",
                        "use_case": "get_specific",
                    },
                )
            else:
                # List operation
                examples.append(
                    {
                        "description": f"List all {resource_type}s",
                        "command": f"f5xcctl {domain} {resource_type} list --namespace {{namespace}}",
                        "use_case": "list_all",
                    },
                )

        elif method == "POST":
            examples.append(
                {
                    "description": f"Create {resource_type}",
                    "command": f"f5xcctl {domain} {resource_type} create {{name}} --namespace {{namespace}}",
                    "use_case": "basic_create",
                },
            )
            examples.append(
                {
                    "description": "Create from YAML file",
                    "command": f"f5xcctl {domain} {resource_type} create -f {{file}}.yaml",
                    "use_case": "file_based",
                },
            )

        elif method == "PUT":
            examples.append(
                {
                    "description": f"Update {resource_type}",
                    "command": f"f5xcctl {domain} {resource_type} update {{name}} --namespace {{namespace}} -f {{file}}.yaml",
                    "use_case": "update",
                },
            )

        elif method == "DELETE":
            examples.append(
                {
                    "description": f"Delete {resource_type}",
                    "command": f"f5xcctl {domain} {resource_type} delete {{name}} --namespace {{namespace}}",
                    "use_case": "delete",
                    "warning": "Permanent operation - cannot be undone",
                },
            )

        return examples[:3]  # Limit to 3 examples per operation

    @staticmethod
    def _extract_resource_type(path: str) -> str:
        """Extract resource type from API path.

        Examples:
            /api/config/namespaces/{namespace}/http_loadbalancers → http-loadbalancer
            /api/config/namespaces/{namespace}/origin_pools → origin-pool

        Args:
            path: API path

        Returns:
            Resource type identifier in kebab-case
        """
        # Extract last path component that is not a parameter
        parts = [p for p in path.split("/") if p and not p.startswith("{")]

        if parts:
            # Take the last part and convert underscore to hyphen
            resource_type = parts[-1]
            # Remove trailing 's' for plurals
            resource_type = resource_type.removesuffix("s")
            return resource_type.replace("_", "-")

        return "resource"

    @staticmethod
    def _extract_domain(path: str) -> str:
        """Extract domain name from API path.

        Examples:
            /api/config/namespaces/{namespace}/http_loadbalancers → http-loadbalancer (implicit)
            /api/virtual/loadbalancers → virtual

        Args:
            path: API path

        Returns:
            Domain identifier
        """
        parts = path.split("/")

        # Try to find domain in path
        if len(parts) > 2 and parts[1] == "api":
            # /api/{domain}/...
            return parts[2]

        return "default"

    def get_stats(self) -> dict[str, int]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()
