"""Discovery Enricher Module.

Merges live API discovery data into published OpenAPI specifications,
adding x-discovered-* extensions with real-world constraints, patterns,
and examples without modifying the core schema.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class EnrichmentStats:
    """Statistics from discovery enrichment."""

    constraints_added: int = 0
    examples_added: int = 0
    mutability_detected: int = 0
    fields_enriched: int = 0
    schemas_processed: int = 0
    paths_processed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "constraints_added": self.constraints_added,
            "examples_added": self.examples_added,
            "mutability_detected": self.mutability_detected,
            "fields_enriched": self.fields_enriched,
            "schemas_processed": self.schemas_processed,
            "paths_processed": self.paths_processed,
        }


@dataclass
class ConstraintDiff:
    """Difference between published and discovered constraints."""

    field_path: str
    published_value: Any = None
    discovered_value: Any = None
    constraint_type: str = ""  # minLength, maxLength, pattern, enum, format
    recommendation: str = ""
    confidence: float = 0.0


@dataclass
class DiscoveryData:
    """Container for loaded discovery data."""

    openapi_spec: dict = field(default_factory=dict)
    session: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    schemas: dict = field(default_factory=dict)
    response_times: dict = field(default_factory=dict)
    discovered_at: str = ""


class DiscoveryEnricher:
    """Merge discovered constraints with published specs.

    This class loads discovery data from the specs/discovered directory
    and enriches published OpenAPI specs with real-world constraints,
    patterns, and examples using x-discovered-* extensions.
    """

    def __init__(self, config: dict) -> None:
        """Initialize the discovery enricher.

        Args:
            config: Discovery enrichment configuration from YAML
        """
        self.config = config.get("discovery_enrichment", config)
        self.stats = EnrichmentStats()
        self.constraint_diffs: list[ConstraintDiff] = []
        self.discovery_data: DiscoveryData | None = None

        # Extension prefix
        self.prefix = self.config.get("extensions", {}).get("prefix", "x-discovered")

        # Known read-only fields
        self.known_read_only = set(
            self.config.get("mutability", {}).get("known_read_only", []),
        )

        # Known write-only fields
        self.known_write_only = set(
            self.config.get("mutability", {}).get("known_write_only", []),
        )

        # PII redaction patterns
        self.redact_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.config.get("examples", {}).get("redact_patterns", [])
        ]

    def load_discovery_data(self, discovered_dir: Path | str) -> DiscoveryData:
        """Load discovered API specifications.

        Args:
            discovered_dir: Directory containing discovered specs

        Returns:
            DiscoveryData with loaded specifications
        """
        discovered_dir = Path(discovered_dir)
        data = DiscoveryData()

        # Load main OpenAPI spec
        openapi_path = discovered_dir / "openapi.json"
        if openapi_path.exists():
            with openapi_path.open() as f:
                data.openapi_spec = json.load(f)
                data.paths = data.openapi_spec.get("paths", {})
                data.schemas = data.openapi_spec.get("components", {}).get("schemas", {})

            # Extract discovered timestamp
            info = data.openapi_spec.get("info", {})
            data.discovered_at = info.get("x-discovered-at", "")

        # Load session data
        session_path = discovered_dir / "session.json"
        if session_path.exists():
            with session_path.open() as f:
                data.session = json.load(f)

        # Build response time index
        for path, path_item in data.paths.items():
            for method, operation in path_item.items():
                if isinstance(operation, dict):
                    rt = operation.get("x-response-time-ms")
                    if rt:
                        key = f"{method.upper()} {path}"
                        data.response_times[key] = rt

        self.discovery_data = data
        return data

    def enrich_with_discoveries(
        self,
        spec: dict,
        discoveries: DiscoveryData | None = None,
    ) -> dict:
        """Enrich a published spec with discovery data.

        Args:
            spec: Published OpenAPI specification
            discoveries: Optional discovery data (uses loaded data if not provided)

        Returns:
            Enriched specification with x-discovered-* extensions
        """
        if discoveries is None:
            discoveries = self.discovery_data

        if discoveries is None or not discoveries.openapi_spec:
            return spec

        # Enrich paths/operations
        if self.config.get("performance", {}).get("add_response_times", True):
            spec = self._enrich_paths(spec, discoveries)

        # Enrich schemas
        spec = self._enrich_schemas(spec, discoveries)

        # Add discovery metadata to info
        if "info" not in spec:
            spec["info"] = {}

        spec["info"][f"{self.prefix}-enrichment-applied"] = True
        spec["info"][f"{self.prefix}-enrichment-at"] = datetime.now(
            timezone.utc,
        ).isoformat()

        if discoveries.discovered_at:
            spec["info"][f"{self.prefix}-source-timestamp"] = discoveries.discovered_at

        return spec

    def _enrich_paths(self, spec: dict, discoveries: DiscoveryData) -> dict:
        """Enrich path operations with discovery data.

        Args:
            spec: Published specification
            discoveries: Discovery data

        Returns:
            Spec with enriched paths
        """
        published_paths = spec.get("paths", {})

        for path, path_item in published_paths.items():
            if not isinstance(path_item, dict):
                continue

            for method in ["get", "post", "put", "delete", "patch", "options"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                # Find matching discovered operation
                discovered_op = self._find_discovered_operation(
                    path,
                    method,
                    discoveries,
                )

                if discovered_op:
                    # Add response time baseline
                    rt = discovered_op.get("x-response-time-ms")
                    if rt:
                        operation[f"{self.prefix}-response-time-ms"] = round(rt, 2)

                    # Add sample size if available
                    if self.config.get("performance", {}).get("add_sample_size", True):
                        operation[f"{self.prefix}-sample-size"] = 1

                    self.stats.paths_processed += 1

        return spec

    def _enrich_schemas(self, spec: dict, discoveries: DiscoveryData) -> dict:
        """Enrich component schemas with discovery data.

        Args:
            spec: Published specification
            discoveries: Discovery data

        Returns:
            Spec with enriched schemas
        """
        if "components" not in spec or "schemas" not in spec["components"]:
            return spec

        published_schemas = spec["components"]["schemas"]
        discovered_schemas = discoveries.schemas

        # Build a lookup of discovered property constraints from component schemas
        discovered_constraints = self._extract_discovered_constraints(
            discovered_schemas,
        )

        # ALSO extract constraints from inline schemas in paths
        # This handles cases where discovered data has schemas inline in responses
        inline_constraints = self._extract_inline_path_constraints(discoveries.paths)

        # Merge inline constraints into discovered constraints
        for prop_name, prop_constraints in inline_constraints.items():
            if prop_name in discovered_constraints:
                # Merge with existing (keep tightest constraints)
                existing = discovered_constraints[prop_name]
                for key, value in prop_constraints.items():
                    if key == "minLength":
                        existing[key] = max(existing.get(key, 0), value)
                    elif key == "maxLength":
                        existing[key] = min(existing.get(key, float("inf")), value)
                    elif key not in existing:
                        existing[key] = value
            else:
                discovered_constraints[prop_name] = prop_constraints

        # Enrich each published schema
        for schema_name, schema in published_schemas.items():
            if not isinstance(schema, dict):
                continue

            self._enrich_schema_recursive(
                schema,
                schema_name,
                discovered_constraints,
                discoveries,
            )
            self.stats.schemas_processed += 1

        return spec

    def _enrich_schema_recursive(
        self,
        schema: dict,
        path: str,
        discovered_constraints: dict,
        discoveries: DiscoveryData,
    ) -> None:
        """Recursively enrich a schema and its nested properties.

        Args:
            schema: Schema to enrich
            path: Current path for constraint lookup
            discovered_constraints: Discovered constraint lookup
            discoveries: Full discovery data
        """
        # Enrich properties
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue

            prop_path = f"{path}/{prop_name}"
            self._enrich_property(prop_schema, prop_name, prop_path, discovered_constraints)

            # Recurse into nested objects
            if prop_schema.get("type") == "object":
                self._enrich_schema_recursive(
                    prop_schema,
                    prop_path,
                    discovered_constraints,
                    discoveries,
                )

            # Handle array items
            if prop_schema.get("type") == "array" and "items" in prop_schema:
                items = prop_schema["items"]
                if isinstance(items, dict):
                    self._enrich_schema_recursive(
                        items,
                        f"{prop_path}/items",
                        discovered_constraints,
                        discoveries,
                    )

        # Enrich allOf/oneOf/anyOf
        for combiner in ["allOf", "oneOf", "anyOf"]:
            if combiner in schema:
                for i, sub_schema in enumerate(schema[combiner]):
                    if isinstance(sub_schema, dict):
                        self._enrich_schema_recursive(
                            sub_schema,
                            f"{path}/{combiner}[{i}]",
                            discovered_constraints,
                            discoveries,
                        )

    def _enrich_property(
        self,
        prop_schema: dict,
        prop_name: str,
        prop_path: str,
        discovered_constraints: dict,
    ) -> None:
        """Enrich a single property with discovered constraints.

        Args:
            prop_schema: Property schema to enrich
            prop_name: Property name
            prop_path: Full path for lookup
            discovered_constraints: Discovered constraints lookup
        """
        # OpenAPI 3.0: $ref cannot have sibling properties (except description/summary)
        # Skip enrichment for schemas that use $ref to avoid invalid specs
        if "$ref" in prop_schema:
            return

        # confidence_threshold and min_sample_size reserved for future statistical validation
        _ = self.config.get("constraints", {}).get("confidence_threshold", 0.8)
        _ = self.config.get("constraints", {}).get("min_sample_size", 5)

        # Check for discovered constraints by property name
        constraints = discovered_constraints.get(prop_name, {})

        if not constraints:
            # Try normalized name
            normalized = prop_name.lower().replace("_", "").replace("-", "")
            constraints = discovered_constraints.get(normalized, {})

        if constraints:
            added = False

            # Add minLength if discovered and not published
            if "minLength" in constraints and "minLength" not in prop_schema:
                prop_schema[f"{self.prefix}-min-length"] = constraints["minLength"]
                self._record_diff(
                    prop_path,
                    "minLength",
                    None,
                    constraints["minLength"],
                )
                added = True

            # Add maxLength if discovered is tighter than published
            if "maxLength" in constraints:
                published_max = prop_schema.get("maxLength")
                discovered_max = constraints["maxLength"]
                if published_max is None or discovered_max < published_max:
                    prop_schema[f"{self.prefix}-max-length"] = discovered_max
                    self._record_diff(
                        prop_path,
                        "maxLength",
                        published_max,
                        discovered_max,
                    )
                    added = True

            # Add pattern if discovered and not published
            if "pattern" in constraints and "pattern" not in prop_schema:
                prop_schema[f"{self.prefix}-pattern"] = constraints["pattern"]
                self._record_diff(
                    prop_path,
                    "pattern",
                    None,
                    constraints["pattern"],
                )
                added = True

            # Add format if discovered and not published
            if "format" in constraints and "format" not in prop_schema:
                prop_schema[f"{self.prefix}-format"] = constraints["format"]
                self._record_diff(
                    prop_path,
                    "format",
                    None,
                    constraints["format"],
                )
                added = True

            # Add enum values if discovered
            if "enum" in constraints and "enum" not in prop_schema:
                prop_schema[f"{self.prefix}-enum-values"] = constraints["enum"]
                self._record_diff(prop_path, "enum", None, constraints["enum"])
                added = True

            if added:
                self.stats.constraints_added += 1
                self.stats.fields_enriched += 1

        # Detect field mutability
        if self.config.get("mutability", {}).get("detect_read_only", True):
            mutability = self._detect_mutability(prop_name)
            if mutability:
                prop_schema["x-field-mutability"] = mutability
                self.stats.mutability_detected += 1

    def _detect_mutability(self, field_name: str) -> str | None:
        """Detect field mutability based on known patterns.

        Args:
            field_name: Name of the field

        Returns:
            Mutability string or None
        """
        if field_name in self.known_read_only:
            return "read-only"
        if field_name in self.known_write_only:
            return "write-only"

        # Check common read-only patterns
        read_only_patterns = [
            "created_at",
            "updated_at",
            "creation_timestamp",
            "modification_timestamp",
            "creator",
            "modifier",
            "_id",
            "object_index",
        ]

        normalized = field_name.lower()
        for pattern in read_only_patterns:
            if pattern in normalized:
                return "read-only"

        return None

    def _extract_discovered_constraints(self, schemas: dict) -> dict[str, dict]:
        """Extract constraint patterns from discovered schemas.

        Args:
            schemas: Discovered component schemas

        Returns:
            Dictionary mapping property names to their discovered constraints
        """
        constraints: dict[str, dict] = {}

        def extract_from_schema(schema: dict) -> None:
            if not isinstance(schema, dict):
                return

            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue

                prop_constraints = {}

                # Extract string constraints
                if "minLength" in prop_schema:
                    prop_constraints["minLength"] = prop_schema["minLength"]
                if "maxLength" in prop_schema:
                    prop_constraints["maxLength"] = prop_schema["maxLength"]
                if "pattern" in prop_schema:
                    prop_constraints["pattern"] = prop_schema["pattern"]
                if "format" in prop_schema:
                    prop_constraints["format"] = prop_schema["format"]

                # Extract enum
                if "enum" in prop_schema:
                    prop_constraints["enum"] = prop_schema["enum"]

                # Extract number constraints
                if "minimum" in prop_schema:
                    prop_constraints["minimum"] = prop_schema["minimum"]
                if "maximum" in prop_schema:
                    prop_constraints["maximum"] = prop_schema["maximum"]

                if prop_constraints:
                    # Merge with existing constraints (keep tightest)
                    if prop_name in constraints:
                        existing = constraints[prop_name]
                        for key, value in prop_constraints.items():
                            if key == "minLength":
                                existing[key] = max(
                                    existing.get(key, 0),
                                    value,
                                )
                            elif key == "maxLength":
                                existing[key] = min(
                                    existing.get(key, float("inf")),
                                    value,
                                )
                            else:
                                existing[key] = value
                    else:
                        constraints[prop_name] = prop_constraints

                # Recurse into nested objects
                if prop_schema.get("type") == "object":
                    extract_from_schema(prop_schema)

                # Handle array items
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict):
                        extract_from_schema(items)

        # Process all discovered schemas
        for schema in schemas.values():
            extract_from_schema(schema)

        return constraints

    def _extract_inline_path_constraints(self, paths: dict) -> dict[str, dict]:
        """Extract constraints from inline schemas in discovered paths.

        The discovery process creates inline schemas within path responses,
        not in components.schemas. This method extracts constraints from
        those inline schemas.

        Args:
            paths: Discovered paths dictionary

        Returns:
            Dictionary mapping property names to their discovered constraints
        """
        constraints: dict[str, dict] = {}

        def extract_from_schema(schema: dict) -> None:
            """Recursively extract constraints from a schema."""
            if not isinstance(schema, dict):
                return

            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue

                prop_constraints: dict = {}

                # Extract string constraints
                if "minLength" in prop_schema:
                    prop_constraints["minLength"] = prop_schema["minLength"]
                if "maxLength" in prop_schema:
                    prop_constraints["maxLength"] = prop_schema["maxLength"]
                if "pattern" in prop_schema:
                    prop_constraints["pattern"] = prop_schema["pattern"]
                if "format" in prop_schema:
                    prop_constraints["format"] = prop_schema["format"]

                # Extract enum
                if "enum" in prop_schema:
                    prop_constraints["enum"] = prop_schema["enum"]

                # Extract number constraints
                if "minimum" in prop_schema:
                    prop_constraints["minimum"] = prop_schema["minimum"]
                if "maximum" in prop_schema:
                    prop_constraints["maximum"] = prop_schema["maximum"]

                # Extract examples as potential enum values for small sets
                if (
                    "examples" in prop_schema
                    and len(prop_schema["examples"]) <= 10
                    and "enum" not in prop_constraints
                ):
                    # Only use examples as potential enum if all are same type
                    examples = prop_schema["examples"]
                    if examples and all(isinstance(e, type(examples[0])) for e in examples):
                        prop_constraints["x-discovered-examples"] = examples

                if prop_constraints:
                    # Merge with existing constraints (keep tightest)
                    if prop_name in constraints:
                        existing = constraints[prop_name]
                        for key, value in prop_constraints.items():
                            if key == "minLength":
                                existing[key] = max(existing.get(key, 0), value)
                            elif key == "maxLength":
                                existing[key] = min(
                                    existing.get(key, float("inf")),
                                    value,
                                )
                            elif key not in existing:
                                existing[key] = value
                    else:
                        constraints[prop_name] = prop_constraints

                # Recurse into nested objects
                if prop_schema.get("type") == "object":
                    extract_from_schema(prop_schema)

                # Handle array items
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict):
                        extract_from_schema(items)

        # Process all paths and their inline schemas
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue

            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue

                # Extract from response schemas
                responses = operation.get("responses", {})
                for response in responses.values():
                    if not isinstance(response, dict):
                        continue

                    content = response.get("content", {})
                    for media_obj in content.values():
                        if not isinstance(media_obj, dict):
                            continue

                        schema = media_obj.get("schema", {})
                        if schema:
                            extract_from_schema(schema)

                        # Also check example data for additional constraints
                        example = media_obj.get("example", {})
                        if isinstance(example, dict):
                            self._extract_constraints_from_example(
                                example,
                                constraints,
                            )

                # Extract from requestBody schemas
                request_body = operation.get("requestBody", {})
                if isinstance(request_body, dict):
                    content = request_body.get("content", {})
                    for media_obj in content.values():
                        if isinstance(media_obj, dict):
                            schema = media_obj.get("schema", {})
                            if schema:
                                extract_from_schema(schema)

        return constraints

    def _extract_constraints_from_example(
        self,
        example: dict,
        constraints: dict[str, dict],
        path: str = "",
    ) -> None:
        """Extract constraint hints from actual example data.

        Analyzes real API response examples to infer constraints like
        string lengths, patterns, and potential enum values.

        Args:
            example: Example response data
            constraints: Constraints dict to update
            path: Current path for nested objects
        """
        if not isinstance(example, dict):
            return

        for key, value in example.items():
            if value is None:
                continue

            prop_constraints: dict = {}

            if isinstance(value, str):
                # Infer string constraints from actual values
                length = len(value)
                if length > 0:
                    prop_constraints["minLength"] = length
                    prop_constraints["maxLength"] = length

                # Detect common formats
                if self._looks_like_uuid(value):
                    prop_constraints["format"] = "uuid"
                elif self._looks_like_datetime(value):
                    prop_constraints["format"] = "date-time"
                elif self._looks_like_email(value):
                    prop_constraints["format"] = "email"
                elif self._looks_like_uri(value):
                    prop_constraints["format"] = "uri"

            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                # Infer numeric constraints
                prop_constraints["minimum"] = value
                prop_constraints["maximum"] = value

            elif isinstance(value, dict):
                # Recurse into nested objects
                self._extract_constraints_from_example(
                    value,
                    constraints,
                    f"{path}/{key}" if path else key,
                )

            elif isinstance(value, list) and value:
                # For arrays, analyze items
                for item in value[:5]:  # Limit to first 5 items
                    if isinstance(item, dict):
                        self._extract_constraints_from_example(
                            item,
                            constraints,
                            f"{path}/{key}/items" if path else f"{key}/items",
                        )

            if prop_constraints:
                if key in constraints:
                    # Merge - expand min/max ranges
                    existing = constraints[key]
                    if "minLength" in prop_constraints:
                        existing["minLength"] = min(
                            existing.get("minLength", prop_constraints["minLength"]),
                            prop_constraints["minLength"],
                        )
                    if "maxLength" in prop_constraints:
                        existing["maxLength"] = max(
                            existing.get("maxLength", prop_constraints["maxLength"]),
                            prop_constraints["maxLength"],
                        )
                    if "minimum" in prop_constraints:
                        existing["minimum"] = min(
                            existing.get("minimum", prop_constraints["minimum"]),
                            prop_constraints["minimum"],
                        )
                    if "maximum" in prop_constraints:
                        existing["maximum"] = max(
                            existing.get("maximum", prop_constraints["maximum"]),
                            prop_constraints["maximum"],
                        )
                    if "format" in prop_constraints and "format" not in existing:
                        existing["format"] = prop_constraints["format"]
                else:
                    constraints[key] = prop_constraints

    def _looks_like_uuid(self, value: str) -> bool:
        """Check if string looks like a UUID."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        return bool(uuid_pattern.match(value))

    def _looks_like_datetime(self, value: str) -> bool:
        """Check if string looks like ISO datetime."""
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value))

    def _looks_like_email(self, value: str) -> bool:
        """Check if string looks like an email."""
        return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value))

    def _looks_like_uri(self, value: str) -> bool:
        """Check if string looks like a URI."""
        return bool(re.match(r"^https?://", value))

    def _find_discovered_operation(
        self,
        path: str,
        method: str,
        discoveries: DiscoveryData,
    ) -> dict | None:
        """Find matching discovered operation.

        Args:
            path: Published path pattern
            method: HTTP method
            discoveries: Discovery data

        Returns:
            Discovered operation or None
        """
        discovered_paths = discoveries.paths

        # Direct match
        if path in discovered_paths:
            path_item = discovered_paths[path]
            if method in path_item:
                return path_item[method]

        # Try to match with different parameter styles
        # e.g., {namespace} vs {metadata.namespace}
        normalized_path = re.sub(r"\{[^}]+\}", "{}", path)

        for disc_path, disc_item in discovered_paths.items():
            disc_normalized = re.sub(r"\{[^}]+\}", "{}", disc_path)
            if disc_normalized == normalized_path and method in disc_item:
                return disc_item[method]

        return None

    def _record_diff(
        self,
        field_path: str,
        constraint_type: str,
        published_value: Any,
        discovered_value: Any,
    ) -> None:
        """Record a constraint difference for reporting.

        Args:
            field_path: Path to the field
            constraint_type: Type of constraint
            published_value: Published constraint value
            discovered_value: Discovered constraint value
        """
        recommendation = ""
        if constraint_type == "maxLength" and published_value:
            if discovered_value < published_value:
                recommendation = f"Consider tightening from {published_value} to {discovered_value}"
        elif published_value is None:
            recommendation = f"Consider adding {constraint_type}: {discovered_value}"

        diff = ConstraintDiff(
            field_path=field_path,
            published_value=published_value,
            discovered_value=discovered_value,
            constraint_type=constraint_type,
            recommendation=recommendation,
            confidence=0.9,  # Default high confidence
        )
        self.constraint_diffs.append(diff)

    def sanitize_example(self, example: dict[str, Any]) -> dict[str, Any]:
        """Sanitize an example by redacting sensitive fields.

        Args:
            example: Example data to sanitize

        Returns:
            Sanitized example
        """
        if not isinstance(example, dict):
            return example

        sanitized: dict[str, Any] = {}
        for key, value in example.items():
            # Check if key matches redaction pattern
            should_redact = any(p.match(key) for p in self.redact_patterns)

            if should_redact:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self.sanitize_example(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self.sanitize_example(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    def get_stats(self) -> dict[str, int]:
        """Get enrichment statistics.

        Returns:
            Dictionary of statistics
        """
        return self.stats.to_dict()

    def get_constraint_diffs(self) -> list[ConstraintDiff]:
        """Get all recorded constraint differences.

        Returns:
            List of constraint differences
        """
        return self.constraint_diffs

    def reset_stats(self) -> None:
        """Reset statistics and diffs for a new enrichment run."""
        self.stats = EnrichmentStats()
        self.constraint_diffs = []
