"""JSON Schema inference from API responses.

Analyzes live API responses to infer:
- Type detection (string, number, boolean, object, array)
- Pattern detection (email, uuid, date, url)
- Constraint detection (min/max length, enum values)
- Default value identification
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferredConstraints:
    """Inferred constraints for a field."""

    min_length: int | None = None
    max_length: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    enum_values: list[Any] = field(default_factory=list)
    required: bool = False
    nullable: bool = False
    default: Any = None


@dataclass
class InferredSchema:
    """Inferred JSON schema for a field or object."""

    type: str  # string, number, integer, boolean, object, array, null
    title: str | None = None
    description: str | None = None
    format: str | None = None  # date-time, email, uri, uuid, etc.
    constraints: InferredConstraints = field(default_factory=InferredConstraints)
    properties: dict[str, "InferredSchema"] = field(default_factory=dict)
    items: "InferredSchema | None" = None  # For arrays
    additional_properties: bool = True
    examples: list[Any] = field(default_factory=list)

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to JSON Schema format."""
        schema: dict[str, Any] = {"type": self.type}

        if self.title:
            schema["title"] = self.title
        if self.description:
            schema["description"] = self.description
        if self.format:
            schema["format"] = self.format

        # Add constraints
        c = self.constraints
        if c.min_length is not None:
            schema["minLength"] = c.min_length
        if c.max_length is not None:
            schema["maxLength"] = c.max_length
        if c.minimum is not None:
            schema["minimum"] = c.minimum
        if c.maximum is not None:
            schema["maximum"] = c.maximum
        if c.pattern:
            schema["pattern"] = c.pattern
        if c.enum_values:
            schema["enum"] = c.enum_values
        if c.default is not None:
            schema["default"] = c.default
        if c.nullable:
            # JSON Schema draft-07 style
            if isinstance(schema["type"], str):
                schema["type"] = [schema["type"], "null"]

        # Object properties
        if self.type == "object" and self.properties:
            schema["properties"] = {
                name: prop.to_json_schema() for name, prop in self.properties.items()
            }
            required = [name for name, prop in self.properties.items() if prop.constraints.required]
            if required:
                schema["required"] = required
            schema["additionalProperties"] = self.additional_properties

        # Array items
        if self.type == "array" and self.items:
            schema["items"] = self.items.to_json_schema()

        if self.examples:
            schema["examples"] = self.examples[:3]  # Limit examples

        return schema


class SchemaInferrer:
    """Infer JSON schema from API response data.

    Provides:
    - Type inference from values
    - Pattern detection for strings
    - Constraint inference from multiple samples
    - Schema merging for consistency
    """

    # Regex patterns for common string formats
    PATTERNS = {
        "uuid": re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        ),
        "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "date-time": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
        "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        "uri": re.compile(r"^https?://"),
        "ipv4": re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
        "hostname": re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"),
    }

    def __init__(
        self,
        detect_patterns: bool = True,
        detect_constraints: bool = True,
        max_array_items: int = 10,
        pattern_thresholds: dict[str, float] | None = None,
    ) -> None:
        """Initialize schema inferrer.

        Args:
            detect_patterns: Whether to detect string patterns
            detect_constraints: Whether to detect constraints
            max_array_items: Maximum array items to analyze
            pattern_thresholds: Confidence thresholds for pattern detection
        """
        self.detect_patterns = detect_patterns
        self.detect_constraints = detect_constraints
        self.max_array_items = max_array_items
        self.pattern_thresholds = pattern_thresholds or {
            "uuid": 0.9,
            "email": 0.9,
            "date-time": 0.8,
            "date": 0.9,
            "uri": 0.9,
            "ipv4": 0.9,
            "hostname": 0.8,
        }

    def infer(self, data: Any) -> InferredSchema:
        """Infer schema from data.

        Args:
            data: JSON data to analyze

        Returns:
            Inferred schema
        """
        return self._infer_value(data)

    def _infer_value(self, value: Any) -> InferredSchema:
        """Infer schema for a single value."""
        if value is None:
            return InferredSchema(type="null")

        if isinstance(value, bool):
            return InferredSchema(type="boolean", examples=[value])

        if isinstance(value, int):
            return InferredSchema(
                type="integer",
                examples=[value],
                constraints=InferredConstraints(minimum=value, maximum=value),
            )

        if isinstance(value, float):
            return InferredSchema(
                type="number",
                examples=[value],
                constraints=InferredConstraints(minimum=value, maximum=value),
            )

        if isinstance(value, str):
            return self._infer_string(value)

        if isinstance(value, list):
            return self._infer_array(value)

        if isinstance(value, dict):
            return self._infer_object(value)

        # Unknown type, treat as string
        return InferredSchema(type="string", examples=[str(value)])

    def _infer_string(self, value: str) -> InferredSchema:
        """Infer schema for a string value."""
        schema = InferredSchema(
            type="string",
            examples=[value] if len(value) < 100 else [value[:100] + "..."],
            constraints=InferredConstraints(
                min_length=len(value),
                max_length=len(value),
            ),
        )

        # Detect patterns
        if self.detect_patterns:
            for format_name, pattern in self.PATTERNS.items():
                if pattern.match(value):
                    schema.format = format_name
                    break

        return schema

    def _infer_array(self, value: list) -> InferredSchema:
        """Infer schema for an array value."""
        schema = InferredSchema(type="array")

        if not value:
            schema.items = InferredSchema(type="string")  # Default
            return schema

        # Analyze items (limited)
        items_to_analyze = value[: self.max_array_items]
        item_schemas = [self._infer_value(item) for item in items_to_analyze]

        # Merge item schemas
        if item_schemas:
            schema.items = self._merge_schemas(item_schemas)

        return schema

    def _infer_object(self, value: dict) -> InferredSchema:
        """Infer schema for an object value."""
        schema = InferredSchema(type="object")

        for key, val in value.items():
            prop_schema = self._infer_value(val)
            prop_schema.constraints.required = True  # Present = required initially
            schema.properties[key] = prop_schema

        return schema

    def _merge_schemas(self, schemas: list[InferredSchema]) -> InferredSchema:
        """Merge multiple schemas into one.

        Used for inferring array item types from multiple items
        or merging schemas from multiple responses.
        """
        if not schemas:
            return InferredSchema(type="string")

        if len(schemas) == 1:
            return schemas[0]

        # Determine common type
        types = set(s.type for s in schemas)

        if len(types) == 1:
            base_type = types.pop()
        elif types == {"integer", "number"}:
            base_type = "number"
        else:
            # Multiple types - use first non-null
            base_type = next((s.type for s in schemas if s.type != "null"), "string")

        merged = InferredSchema(type=base_type)

        # Merge constraints
        if self.detect_constraints:
            merged.constraints = self._merge_constraints(schemas)

        # Merge format (most common)
        formats = [s.format for s in schemas if s.format]
        if formats:
            from collections import Counter

            merged.format = Counter(formats).most_common(1)[0][0]

        # Merge object properties
        if base_type == "object":
            all_props: dict[str, list[InferredSchema]] = {}
            for s in schemas:
                for name, prop in s.properties.items():
                    if name not in all_props:
                        all_props[name] = []
                    all_props[name].append(prop)

            for name, props in all_props.items():
                merged.properties[name] = self._merge_schemas(props)
                # Mark as not required if not in all schemas
                if len(props) < len(schemas):
                    merged.properties[name].constraints.required = False

        # Merge array items
        if base_type == "array":
            item_schemas = [s.items for s in schemas if s.items]
            if item_schemas:
                merged.items = self._merge_schemas(item_schemas)

        # Collect examples
        for s in schemas[:3]:
            merged.examples.extend(s.examples[:1])

        return merged

    def _merge_constraints(self, schemas: list[InferredSchema]) -> InferredConstraints:
        """Merge constraints from multiple schemas."""
        constraints = InferredConstraints()

        # String constraints
        min_lengths = [
            s.constraints.min_length for s in schemas if s.constraints.min_length is not None
        ]
        max_lengths = [
            s.constraints.max_length for s in schemas if s.constraints.max_length is not None
        ]

        if min_lengths:
            constraints.min_length = min(min_lengths)
        if max_lengths:
            constraints.max_length = max(max_lengths)

        # Numeric constraints
        minimums = [s.constraints.minimum for s in schemas if s.constraints.minimum is not None]
        maximums = [s.constraints.maximum for s in schemas if s.constraints.maximum is not None]

        if minimums:
            constraints.minimum = min(minimums)
        if maximums:
            constraints.maximum = max(maximums)

        # Enum values (collect unique)
        enum_values: set = set()
        for s in schemas:
            enum_values.update(s.constraints.enum_values)
        if enum_values:
            constraints.enum_values = sorted(enum_values, key=str)

        # Nullable if any schema is null type
        constraints.nullable = any(s.type == "null" for s in schemas)

        # Required if all schemas have it required
        constraints.required = all(s.constraints.required for s in schemas)

        return constraints

    def infer_from_responses(self, responses: list[dict]) -> InferredSchema:
        """Infer schema from multiple API responses.

        Args:
            responses: List of response JSON objects

        Returns:
            Merged inferred schema
        """
        if not responses:
            return InferredSchema(type="object")

        schemas = [self.infer(response) for response in responses]
        return self._merge_schemas(schemas)
