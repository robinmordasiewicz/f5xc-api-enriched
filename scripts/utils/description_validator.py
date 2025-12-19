#!/usr/bin/env python3
"""Description validator for OpenAPI specifications.

Validates description completeness and auto-generates missing descriptions
from operationId and schema names.
"""

import re
from pathlib import Path
from typing import Any

import yaml


class DescriptionValidator:
    """Validates and auto-generates missing descriptions.

    Finds operations and schemas without descriptions and optionally
    generates placeholder descriptions from operationId or schema name.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize with configuration from file.

        Args:
            config_path: Path to enrichment.yaml config.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "enrichment.yaml"

        # Default configuration
        self._auto_generate_operation_descriptions = True
        self._auto_generate_schema_descriptions = False  # More risky, off by default
        self._description_prefix = ""  # Optional prefix like "[Auto-generated] "

        self._load_config(config_path)

        # Statistics tracking
        self._operations_missing = 0
        self._operations_generated = 0
        self._schemas_missing = 0
        self._schemas_generated = 0

    def _load_config(self, config_path: Path) -> None:
        """Load configuration from YAML config."""
        if not config_path.exists():
            return

        with config_path.open() as f:
            config = yaml.safe_load(f) or {}

        desc_config = config.get("description_validation", {})
        self._auto_generate_operation_descriptions = desc_config.get(
            "auto_generate_operation_descriptions",
            True,
        )
        self._auto_generate_schema_descriptions = desc_config.get(
            "auto_generate_schema_descriptions",
            False,
        )
        self._description_prefix = desc_config.get("description_prefix", "")

    def validate_and_generate(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Validate descriptions and generate missing ones.

        Args:
            spec: OpenAPI specification dictionary.

        Returns:
            Specification with generated descriptions.
        """
        self._operations_missing = 0
        self._operations_generated = 0
        self._schemas_missing = 0
        self._schemas_generated = 0

        result = spec.copy()

        # Process operations
        result = self._process_operations(result)

        # Process schemas
        if self._auto_generate_schema_descriptions:
            result = self._process_schemas(result)

        return result

    def _process_operations(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Process operations to find and generate missing descriptions."""
        result = spec.copy()
        paths = result.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                # Skip non-operation keys
                if method.lower() not in (
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                ):
                    continue

                if not isinstance(operation, dict):
                    continue

                # Check for missing description
                description = operation.get("description")
                if not description or not description.strip():
                    self._operations_missing += 1

                    if self._auto_generate_operation_descriptions:
                        # Try to generate from operationId
                        operation_id = operation.get("operationId", "")
                        generated = self._generate_description_from_operation_id(
                            operation_id,
                            method,
                            path,
                        )
                        if generated:
                            operation["description"] = self._description_prefix + generated
                            self._operations_generated += 1

        return result

    def _process_schemas(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Process schemas to find and generate missing descriptions."""
        result = spec.copy()
        components = result.get("components", {})
        schemas = components.get("schemas", {})

        for schema_name, schema_def in schemas.items():
            if not isinstance(schema_def, dict):
                continue

            # Skip if it's just a reference
            if "$ref" in schema_def:
                continue

            description = schema_def.get("description")
            if not description or not description.strip():
                self._schemas_missing += 1

                if self._auto_generate_schema_descriptions:
                    generated = self._generate_description_from_schema_name(schema_name)
                    if generated:
                        schema_def["description"] = self._description_prefix + generated
                        self._schemas_generated += 1

        return result

    def _generate_description_from_operation_id(
        self,
        operation_id: str,
        method: str,
        path: str,
    ) -> str | None:
        """Generate description from operationId.

        Parses operationId patterns like:
        - "getUserById" -> "Get user by ID"
        - "ves.io.schema.namespace.API.Create" -> "Create namespace"
        - "createHttpLoadbalancer" -> "Create HTTP loadbalancer"

        Args:
            operation_id: The operationId value.
            method: HTTP method (get, post, etc.).
            path: API path.

        Returns:
            Generated description or None.
        """
        if not operation_id:
            # Fall back to method + path
            return self._generate_description_from_path(method, path)

        # Handle F5 XC style: ves.io.schema.namespace.API.Create
        if "ves.io.schema" in operation_id:
            parts = operation_id.split(".")
            if len(parts) >= 2:
                # Get the action (last part) and resource (second to last)
                action = parts[-1]
                resource = parts[-2] if parts[-2] != "API" else parts[-3]
                resource = self._format_resource_name(resource)
                action = self._format_action(action)
                return f"{action} {resource}."

        # Handle camelCase: getUserById -> Get user by ID
        # Split on uppercase letters
        words = re.sub(r"([a-z])([A-Z])", r"\1 \2", operation_id)
        words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", words)

        # Split and clean
        word_list = words.split()
        if not word_list:
            return self._generate_description_from_path(method, path)

        # Capitalize first word, lowercase rest (except acronyms)
        result_words = []
        for i, word in enumerate(word_list):
            if i == 0:
                result_words.append(word.capitalize())
            elif word.isupper() and len(word) <= 4:
                # Keep short uppercase words as-is (HTTP, API, ID, etc.)
                result_words.append(word)
            else:
                result_words.append(word.lower())

        description = " ".join(result_words)

        # Ensure it ends with a period
        if not description.endswith("."):
            description += "."

        return description

    def _generate_description_from_path(self, method: str, path: str) -> str | None:
        """Generate description from HTTP method and path.

        Args:
            method: HTTP method.
            path: API path.

        Returns:
            Generated description.
        """
        # Extract resource from path
        # /api/v1/namespace/{namespace}/http_loadbalancer -> http_loadbalancer
        parts = path.rstrip("/").split("/")
        resource = None

        # Find the last non-parameter path segment
        for part in reversed(parts):
            if not part.startswith("{"):
                resource = part
                break

        if not resource:
            return None

        resource = self._format_resource_name(resource)
        action = self._method_to_action(method)

        return f"{action} {resource}."

    def _generate_description_from_schema_name(self, schema_name: str) -> str | None:
        """Generate description from schema name.

        Args:
            schema_name: Name of the schema.

        Returns:
            Generated description.
        """
        # Handle patterns like:
        # schemaHttpLoadbalancerGetSpec -> HTTP loadbalancer get specification
        # ioschemaObjectMetaType -> Object metadata type

        # Remove common prefixes
        name = schema_name
        prefixes_to_remove = [
            "schema",
            "ioschema",
            "vesio",
            "ves_io",
        ]
        for prefix in prefixes_to_remove:
            if name.lower().startswith(prefix):
                name = name[len(prefix) :]
                break

        # Split camelCase
        words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", words)

        word_list = words.split()
        if not word_list:
            return None

        # Format words
        result_words = []
        for word in word_list:
            if word.isupper() and len(word) <= 4:
                result_words.append(word)
            else:
                result_words.append(word.lower())

        # Capitalize first word
        if result_words:
            result_words[0] = result_words[0].capitalize()

        description = " ".join(result_words)

        # Add "type" or "specification" if not present
        if not any(word in description.lower() for word in ["type", "spec", "request", "response"]):
            description += " type"

        if not description.endswith("."):
            description += "."

        return description

    def _format_resource_name(self, resource: str) -> str:
        """Format a resource name for human readability.

        Args:
            resource: Raw resource name (e.g., "http_loadbalancer").

        Returns:
            Formatted name (e.g., "HTTP load balancer").
        """
        # Replace underscores with spaces
        name = resource.replace("_", " ")

        # Handle known acronyms
        acronyms = {
            "http": "HTTP",
            "tcp": "TCP",
            "udp": "UDP",
            "dns": "DNS",
            "api": "API",
            "waf": "WAF",
            "cdn": "CDN",
            "vpn": "VPN",
            "ip": "IP",
            "ssl": "SSL",
            "tls": "TLS",
            "bgp": "BGP",
            "acl": "ACL",
            "lb": "load balancer",
            "k8s": "Kubernetes",
            "aws": "AWS",
            "gcp": "GCP",
            "azure": "Azure",
            "oidc": "OIDC",
            "rbac": "RBAC",
        }

        words = name.split()
        result = []
        for word in words:
            lower_word = word.lower()
            if lower_word in acronyms:
                result.append(acronyms[lower_word])
            else:
                result.append(word)

        return " ".join(result)

    def _format_action(self, action: str) -> str:
        """Format an action word.

        Args:
            action: Action from operationId (e.g., "Create", "Get").

        Returns:
            Formatted action.
        """
        action_map = {
            "create": "Create",
            "get": "Get",
            "list": "List",
            "update": "Update",
            "replace": "Replace",
            "delete": "Delete",
            "patch": "Patch",
        }
        return action_map.get(action.lower(), action.capitalize())

    def _method_to_action(self, method: str) -> str:
        """Convert HTTP method to action verb.

        Args:
            method: HTTP method.

        Returns:
            Action verb.
        """
        method_map = {
            "get": "Get",
            "post": "Create",
            "put": "Update",
            "patch": "Partially update",
            "delete": "Delete",
            "head": "Check",
            "options": "Get options for",
        }
        return method_map.get(method.lower(), method.capitalize())

    def get_stats(self) -> dict[str, Any]:
        """Return statistics about description validation."""
        return {
            "operations_missing": self._operations_missing,
            "operations_generated": self._operations_generated,
            "schemas_missing": self._schemas_missing,
            "schemas_generated": self._schemas_generated,
            "auto_generate_operation_descriptions": self._auto_generate_operation_descriptions,
            "auto_generate_schema_descriptions": self._auto_generate_schema_descriptions,
        }

    def find_missing_descriptions(self, spec: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        """Find all operations and schemas with missing descriptions.

        This is a read-only method that reports issues without modifying the spec.

        Args:
            spec: OpenAPI specification dictionary.

        Returns:
            Dictionary with lists of missing descriptions.
        """
        missing: dict[str, list[dict[str, str]]] = {
            "operations": [],
            "schemas": [],
        }

        # Check operations
        for path, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() not in (
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                    "trace",
                ):
                    continue

                if not isinstance(operation, dict):
                    continue

                description = operation.get("description")
                if not description or not description.strip():
                    missing["operations"].append(
                        {
                            "path": path,
                            "method": method.upper(),
                            "operationId": operation.get("operationId", ""),
                        },
                    )

        # Check schemas
        for schema_name, schema_def in spec.get("components", {}).get("schemas", {}).items():
            if not isinstance(schema_def, dict):
                continue
            if "$ref" in schema_def:
                continue

            description = schema_def.get("description")
            if not description or not description.strip():
                missing["schemas"].append(
                    {
                        "name": schema_name,
                        "type": schema_def.get("type", "unknown"),
                    },
                )

        return missing
