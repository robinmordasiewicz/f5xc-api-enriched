#!/usr/bin/env python3
"""
F5 XC API Constraint Enricher

Purpose: Enrich OpenAPI specifications with x-f5xc-constraints extension
Based on: Pattern matching, discovery data, and API validation rules

Architecture:
- PatternMatcher: Regex-based field name matching
- Type-specific extractors: String, Array, Numeric, Object
- ConstraintReconciler: 3-tier priority resolution (EXISTING > DISCOVERY > INFERRED)
- Main ConstraintEnricher: Orchestrates the enrichment process

Usage:
    enricher = ConstraintEnricher(config_path="config/constraint_patterns.yaml")
    enriched_spec = enricher.enrich_spec(spec)
    stats = enricher.get_stats()
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatternMatcher:
    """Regex-based pattern matcher for field names"""

    def __init__(self, patterns: Dict[str, List[Dict]]):
        """
        Initialize pattern matcher with compiled regex patterns

        Args:
            patterns: Dict with 'string_patterns', 'array_patterns', 'number_patterns'
        """
        self.string_patterns = self._compile_patterns(patterns.get('string_patterns', []))
        self.array_patterns = self._compile_patterns(patterns.get('array_patterns', []))
        self.number_patterns = self._compile_patterns(patterns.get('number_patterns', []))

    def _compile_patterns(self, pattern_list: List[Dict]) -> List[Tuple]:
        """
        Compile regex patterns for efficiency

        Args:
            pattern_list: List of pattern dictionaries

        Returns:
            List of (compiled_regex, pattern_dict) tuples
        """
        compiled = []
        for pattern_dict in pattern_list:
            pattern = pattern_dict.get('pattern', '')
            try:
                compiled_regex = re.compile(pattern, re.IGNORECASE)
                compiled.append((compiled_regex, pattern_dict))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        return compiled

    def match_string_pattern(self, field_name: str) -> Optional[Dict]:
        """Match field name against string patterns"""
        return self._match_against_patterns(field_name, self.string_patterns)

    def match_array_pattern(self, field_name: str) -> Optional[Dict]:
        """Match field name against array patterns"""
        return self._match_against_patterns(field_name, self.array_patterns)

    def match_number_pattern(self, field_name: str) -> Optional[Dict]:
        """Match field name against number patterns"""
        return self._match_against_patterns(field_name, self.number_patterns)

    def _match_against_patterns(self, field_name: str, patterns: List[Tuple]) -> Optional[Dict]:
        """
        Match field name against compiled patterns

        Args:
            field_name: Field name to match
            patterns: List of (compiled_regex, pattern_dict) tuples

        Returns:
            First matching pattern dict or None
        """
        for regex, pattern_dict in patterns:
            if regex.search(field_name):
                return pattern_dict
        return None


class StringConstraintExtractor:
    """Extract string-specific constraints"""

    @staticmethod
    def extract(field_name: str, schema: Dict, pattern_match: Optional[Dict]) -> Dict:
        """
        Extract string constraints from schema and pattern

        Args:
            field_name: Name of the field
            schema: OpenAPI schema for the field
            pattern_match: Matched pattern dictionary or None

        Returns:
            String constraint dictionary
        """
        constraints = {}

        # Extract from existing schema
        if 'minLength' in schema:
            constraints['minLength'] = schema['minLength']
        if 'maxLength' in schema:
            constraints['maxLength'] = schema['maxLength']
        if 'pattern' in schema:
            constraints['pattern'] = schema['pattern']
        if 'format' in schema:
            constraints['format'] = schema['format']

        # Apply pattern constraints if no existing value
        if pattern_match:
            pattern_constraints = pattern_match.get('constraints', {})
            for key, value in pattern_constraints.items():
                if key not in constraints:
                    constraints[key] = value

        return constraints if constraints else None


class ArrayConstraintExtractor:
    """Extract array-specific constraints"""

    @staticmethod
    def extract(field_name: str, schema: Dict, pattern_match: Optional[Dict]) -> Dict:
        """
        Extract array constraints from schema and pattern

        Args:
            field_name: Name of the field
            schema: OpenAPI schema for the field
            pattern_match: Matched pattern dictionary or None

        Returns:
            Array constraint dictionary
        """
        constraints = {}

        # Extract from existing schema
        if 'minItems' in schema:
            constraints['minItems'] = schema['minItems']
        if 'maxItems' in schema:
            constraints['maxItems'] = schema['maxItems']
        if 'uniqueItems' in schema:
            constraints['uniqueItems'] = schema['uniqueItems']

        # Apply pattern constraints if no existing value
        if pattern_match:
            pattern_constraints = pattern_match.get('constraints', {})
            for key, value in pattern_constraints.items():
                if key not in constraints:
                    constraints[key] = value

        return constraints if constraints else None


class NumericConstraintExtractor:
    """Extract numeric-specific constraints"""

    @staticmethod
    def extract(field_name: str, schema: Dict, pattern_match: Optional[Dict]) -> Dict:
        """
        Extract numeric constraints from schema and pattern

        Args:
            field_name: Name of the field
            schema: OpenAPI schema for the field
            pattern_match: Matched pattern dictionary or None

        Returns:
            Numeric constraint dictionary
        """
        constraints = {}

        # Extract from existing schema
        if 'minimum' in schema:
            constraints['minimum'] = schema['minimum']
        if 'maximum' in schema:
            constraints['maximum'] = schema['maximum']
        if 'multipleOf' in schema:
            constraints['multipleOf'] = schema['multipleOf']
        if 'exclusiveMinimum' in schema:
            constraints['exclusiveMinimum'] = schema['exclusiveMinimum']
        if 'exclusiveMaximum' in schema:
            constraints['exclusiveMaximum'] = schema['exclusiveMaximum']

        # Apply pattern constraints if no existing value
        if pattern_match:
            pattern_constraints = pattern_match.get('constraints', {})
            for key, value in pattern_constraints.items():
                if key not in constraints:
                    constraints[key] = value

        return constraints if constraints else None


class ObjectConstraintExtractor:
    """Extract object-specific constraints"""

    @staticmethod
    def extract(field_name: str, schema: Dict) -> Dict:
        """
        Extract object constraints from schema

        Args:
            field_name: Name of the field
            schema: OpenAPI schema for the field

        Returns:
            Object constraint dictionary
        """
        constraints = {}

        # Extract from existing schema
        if 'minProperties' in schema:
            constraints['minProperties'] = schema['minProperties']
        if 'maxProperties' in schema:
            constraints['maxProperties'] = schema['maxProperties']
        if 'required' in schema:
            constraints['required'] = schema['required']

        return constraints if constraints else None


class ConstraintReconciler:
    """Reconcile constraints from multiple sources with priority"""

    PRIORITY_ORDER = ['existing', 'discovery', 'inferred']

    @staticmethod
    def reconcile(
        existing: Optional[Dict],
        discovery: Optional[Dict],
        inferred: Optional[Dict],
        confidence_threshold: float = 0.9
    ) -> Optional[Dict]:
        """
        Reconcile constraints from multiple sources

        Priority: EXISTING > DISCOVERY > INFERRED

        Args:
            existing: Existing x-f5xc-constraints from spec
            discovery: Constraints from discovery data
            inferred: Constraints from pattern matching
            confidence_threshold: Threshold for deterministic flag

        Returns:
            Reconciled constraints dictionary or None
        """
        # If existing constraints present, preserve them completely
        if existing:
            return existing

        # Start with inferred as base
        result = inferred.copy() if inferred else {}

        # Merge discovery constraints (override inferred)
        if discovery:
            for key, value in discovery.items():
                if key != 'metadata':
                    result[key] = value

        # If no constraints collected, return None
        if not result:
            return None

        # Determine source and confidence
        if discovery:
            source = 'discovery'
            confidence = 0.99
        elif inferred:
            source = 'inferred'
            metadata = inferred.get('metadata', {})
            confidence = metadata.get('confidence', 0.85)
        else:
            return None

        # Add metadata
        result['metadata'] = {
            'source': source,
            'confidence': confidence,
            'validatedAt': datetime.now(timezone.utc).isoformat()
        }

        # Set deterministic flag if confidence meets threshold
        if confidence >= confidence_threshold:
            result['deterministic'] = True

        return result


class ConstraintEnricher:
    """Main constraint enrichment orchestrator"""

    def __init__(self, config_path: Path):
        """
        Initialize constraint enricher

        Args:
            config_path: Path to constraint_patterns.yaml
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.pattern_matcher = PatternMatcher(self.config)

        # Statistics
        self.stats = {
            'properties_analyzed': 0,
            'constraints_added': 0,
            'constraints_skipped_existing': 0,
            'string_constraints': 0,
            'array_constraints': 0,
            'number_constraints': 0,
            'object_constraints': 0,
            'pattern_matches': 0,
            'discovery_merges': 0,
            'confidence_scores': []
        }

    def _load_config(self) -> Dict:
        """Load constraint patterns configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise

    def enrich_spec(self, spec: Dict) -> Dict:
        """
        Enrich OpenAPI specification with x-f5xc-constraints

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Enriched specification
        """
        logger.info("Starting constraint enrichment")

        # Process all schemas
        if 'components' in spec and 'schemas' in spec['components']:
            for schema_name, schema in spec['components']['schemas'].items():
                self._enrich_schema(schema_name, schema)

        logger.info(f"Constraint enrichment complete. Added {self.stats['constraints_added']} constraints")
        return spec

    def _enrich_schema(self, schema_name: str, schema: Dict):
        """Enrich a single schema definition"""
        if 'properties' not in schema:
            return

        for prop_name, prop_schema in schema['properties'].items():
            self._enrich_property(prop_name, prop_schema)

    def _extract_discovery_constraints(self, schema: Dict) -> Optional[Dict]:
        """
        Extract constraints from x-ves-validation-rules

        Args:
            schema: Property schema with potential x-ves-validation-rules

        Returns:
            Constraints dictionary in x-f5xc-constraints format or None
        """
        ves_rules = schema.get('x-ves-validation-rules')
        if not ves_rules:
            return None

        field_type = schema.get('type')
        if not field_type:
            return None

        # Get discovery mapping from config
        mapping = self.config.get('discovery_mapping', {})

        constraints = {}

        # Map string rules
        if field_type == 'string':
            string_rules = mapping.get('string_rules', [])
            for rule_def in string_rules:
                ves_rule = rule_def.get('ves_rule')
                if ves_rule in ves_rules:
                    constraint_field = rule_def.get('constraint_field')
                    constraint_subfield = rule_def.get('constraint_subfield')
                    constraint_value = rule_def.get('constraint_value')

                    if constraint_value is not None:
                        # Fixed value mapping (e.g., format: "email")
                        constraints[constraint_field] = constraint_value
                    elif constraint_subfield:
                        # Nested field mapping (e.g., byteLength.max)
                        rule_value = ves_rules[ves_rule]
                        try:
                            value = int(rule_value)
                            if constraint_field not in constraints:
                                constraints[constraint_field] = {}
                            constraints[constraint_field][constraint_subfield] = value
                        except ValueError:
                            pass
                    else:
                        # Direct value mapping
                        rule_value = ves_rules[ves_rule]
                        if rule_value not in ('true', 'false'):
                            # Convert string numbers to int
                            try:
                                constraints[constraint_field] = int(rule_value)
                            except ValueError:
                                constraints[constraint_field] = rule_value

        # Map array rules
        elif field_type == 'array':
            array_rules = mapping.get('array_rules', [])
            for rule_def in array_rules:
                ves_rule = rule_def.get('ves_rule')
                if ves_rule in ves_rules:
                    constraint_field = rule_def.get('constraint_field')
                    constraint_value = rule_def.get('constraint_value')

                    if constraint_value is not None:
                        constraints[constraint_field] = constraint_value
                    else:
                        rule_value = ves_rules[ves_rule]
                        try:
                            constraints[constraint_field] = int(rule_value)
                        except ValueError:
                            constraints[constraint_field] = rule_value

        # Map numeric rules
        elif field_type in ('integer', 'number'):
            number_rules = mapping.get('number_rules', [])
            for rule_def in number_rules:
                ves_rule = rule_def.get('ves_rule')
                if ves_rule in ves_rules:
                    constraint_field = rule_def.get('constraint_field')
                    rule_value = ves_rules[ves_rule]

                    try:
                        value = int(rule_value)
                        constraints[constraint_field] = value

                        # Handle exclusive bounds
                        if rule_def.get('exclusive'):
                            exclusive_field = f'exclusive{constraint_field.capitalize()}'
                            constraints[exclusive_field] = True
                    except ValueError:
                        pass

        if not constraints:
            return None

        # Build x-f5xc-constraints structure
        result = {
            'type': field_type,
            'category': 'discovery'
        }

        if field_type == 'string':
            result['string'] = constraints
        elif field_type == 'array':
            result['array'] = constraints
        elif field_type in ('integer', 'number'):
            result['number'] = constraints

        # Add metadata
        result['metadata'] = {
            'source': 'discovery',
            'confidence': 0.99,
            'validatedAt': datetime.now(timezone.utc).isoformat()
        }
        result['deterministic'] = True

        return result

    def _enrich_property(self, field_name: str, schema: Dict):
        """
        Enrich a single property with constraints

        Args:
            field_name: Name of the property
            schema: Property schema
        """
        self.stats['properties_analyzed'] += 1

        # Get existing constraints
        existing = schema.get('x-f5xc-constraints')
        if existing:
            self.stats['constraints_skipped_existing'] += 1
            return

        # Extract discovery constraints
        discovery = self._extract_discovery_constraints(schema)
        if discovery:
            self.stats['discovery_merges'] += 1

        # Determine field type
        field_type = schema.get('type')
        if not field_type:
            return

        # Extract inferred constraints based on type
        inferred = None
        pattern_match = None

        if field_type == 'string':
            pattern_match = self.pattern_matcher.match_string_pattern(field_name)
            if pattern_match:
                self.stats['pattern_matches'] += 1
            inferred = self._extract_string_constraints(field_name, schema, pattern_match)
            if inferred:
                self.stats['string_constraints'] += 1

        elif field_type == 'array':
            pattern_match = self.pattern_matcher.match_array_pattern(field_name)
            if pattern_match:
                self.stats['pattern_matches'] += 1
            inferred = self._extract_array_constraints(field_name, schema, pattern_match)
            if inferred:
                self.stats['array_constraints'] += 1

        elif field_type in ('integer', 'number'):
            pattern_match = self.pattern_matcher.match_number_pattern(field_name)
            if pattern_match:
                self.stats['pattern_matches'] += 1
            inferred = self._extract_numeric_constraints(field_name, schema, pattern_match)
            if inferred:
                self.stats['number_constraints'] += 1

        elif field_type == 'object':
            inferred = self._extract_object_constraints(field_name, schema)
            if inferred:
                self.stats['object_constraints'] += 1

        # Reconcile constraints from all sources
        constraints = ConstraintReconciler.reconcile(
            existing=existing,
            discovery=discovery,
            inferred=inferred
        )

        # Apply constraints if found
        if constraints:
            schema['x-f5xc-constraints'] = constraints
            self.stats['constraints_added'] += 1

            # Track confidence
            if 'metadata' in constraints and 'confidence' in constraints['metadata']:
                self.stats['confidence_scores'].append(constraints['metadata']['confidence'])

    def _extract_string_constraints(
        self, field_name: str, schema: Dict, pattern_match: Optional[Dict]
    ) -> Optional[Dict]:
        """Extract string constraints and build x-f5xc-constraints structure"""
        string_constraints = StringConstraintExtractor.extract(field_name, schema, pattern_match)
        if not string_constraints:
            return None

        result = {
            'type': 'string',
            'category': pattern_match.get('metadata', {}).get('category', 'general') if pattern_match else 'general',
            'string': string_constraints
        }

        # Add metadata from pattern
        if pattern_match and 'metadata' in pattern_match:
            result['metadata'] = pattern_match['metadata'].copy()
            result['metadata']['validatedAt'] = datetime.now(timezone.utc).isoformat()

            # Set deterministic flag based on confidence
            confidence = result['metadata'].get('confidence', 0)
            threshold = self.config.get('metadata', {}).get('confidence_thresholds', {}).get('high', 0.9)
            if confidence >= threshold:
                result['deterministic'] = True

        return result

    def _extract_array_constraints(
        self, field_name: str, schema: Dict, pattern_match: Optional[Dict]
    ) -> Optional[Dict]:
        """Extract array constraints and build x-f5xc-constraints structure"""
        array_constraints = ArrayConstraintExtractor.extract(field_name, schema, pattern_match)
        if not array_constraints:
            return None

        result = {
            'type': 'array',
            'category': pattern_match.get('metadata', {}).get('category', 'general') if pattern_match else 'general',
            'array': array_constraints
        }

        # Add metadata from pattern
        if pattern_match and 'metadata' in pattern_match:
            result['metadata'] = pattern_match['metadata'].copy()
            result['metadata']['validatedAt'] = datetime.now(timezone.utc).isoformat()

            # Set deterministic flag based on confidence
            confidence = result['metadata'].get('confidence', 0)
            threshold = self.config.get('metadata', {}).get('confidence_thresholds', {}).get('high', 0.9)
            if confidence >= threshold:
                result['deterministic'] = True

        return result

    def _extract_numeric_constraints(
        self, field_name: str, schema: Dict, pattern_match: Optional[Dict]
    ) -> Optional[Dict]:
        """Extract numeric constraints and build x-f5xc-constraints structure"""
        numeric_constraints = NumericConstraintExtractor.extract(field_name, schema, pattern_match)
        if not numeric_constraints:
            return None

        result = {
            'type': 'number',
            'category': pattern_match.get('metadata', {}).get('category', 'general') if pattern_match else 'general',
            'number': numeric_constraints
        }

        # Add metadata from pattern
        if pattern_match and 'metadata' in pattern_match:
            result['metadata'] = pattern_match['metadata'].copy()
            result['metadata']['validatedAt'] = datetime.now(timezone.utc).isoformat()

            # Set deterministic flag based on confidence
            confidence = result['metadata'].get('confidence', 0)
            threshold = self.config.get('metadata', {}).get('confidence_thresholds', {}).get('high', 0.9)
            if confidence >= threshold:
                result['deterministic'] = True

        return result

    def _extract_object_constraints(self, field_name: str, schema: Dict) -> Optional[Dict]:
        """Extract object constraints and build x-f5xc-constraints structure"""
        object_constraints = ObjectConstraintExtractor.extract(field_name, schema)
        if not object_constraints:
            return None

        result = {
            'type': 'object',
            'category': 'general',
            'object': object_constraints,
            'metadata': {
                'source': 'inferred',
                'confidence': 0.75,
                'validatedAt': datetime.now(timezone.utc).isoformat()
            }
        }

        return result

    def _merge_discovery_constraints(
        self, schema: Dict, discovery_data: Optional[Dict]
    ) -> Optional[Dict]:
        """
        Merge constraints from discovery data

        Args:
            schema: Property schema
            discovery_data: Discovery validation rules

        Returns:
            Merged constraints or None
        """
        if not discovery_data:
            return None

        # Extract x-ves-validation-rules
        ves_rules = schema.get('x-ves-validation-rules', {})
        if not ves_rules:
            return None

        self.stats['discovery_merges'] += 1

        constraints = {}
        field_type = schema.get('type')

        # Map based on field type
        if field_type == 'string':
            constraints = self._map_string_discovery_rules(ves_rules)
        elif field_type == 'array':
            constraints = self._map_array_discovery_rules(ves_rules)
        elif field_type in ('integer', 'number'):
            constraints = self._map_numeric_discovery_rules(ves_rules)

        if constraints:
            return {
                'type': field_type,
                'category': 'discovery',
                field_type: constraints,
                'metadata': {
                    'source': 'discovery',
                    'confidence': 0.99,
                    'validatedAt': datetime.now(timezone.utc).isoformat()
                },
                'deterministic': True
            }

        return None

    def _map_string_discovery_rules(self, ves_rules: Dict) -> Dict:
        """Map x-ves-validation-rules to string constraints"""
        mapping = self.config.get('discovery_mapping', {}).get('string_rules', [])
        constraints = {}

        for rule in mapping:
            ves_rule = rule.get('ves_rule')
            constraint_field = rule.get('constraint_field')
            constraint_value = rule.get('constraint_value')

            if ves_rule in ves_rules:
                if constraint_value:
                    constraints[constraint_field] = constraint_value
                else:
                    constraints[constraint_field] = ves_rules[ves_rule]

        return constraints

    def _map_array_discovery_rules(self, ves_rules: Dict) -> Dict:
        """Map x-ves-validation-rules to array constraints"""
        mapping = self.config.get('discovery_mapping', {}).get('array_rules', [])
        constraints = {}

        for rule in mapping:
            ves_rule = rule.get('ves_rule')
            constraint_field = rule.get('constraint_field')
            constraint_value = rule.get('constraint_value')

            if ves_rule in ves_rules:
                if constraint_value is not None:
                    constraints[constraint_field] = constraint_value
                else:
                    constraints[constraint_field] = ves_rules[ves_rule]

        return constraints

    def _map_numeric_discovery_rules(self, ves_rules: Dict) -> Dict:
        """Map x-ves-validation-rules to numeric constraints"""
        mapping = self.config.get('discovery_mapping', {}).get('number_rules', [])
        constraints = {}

        for rule in mapping:
            ves_rule = rule.get('ves_rule')
            constraint_field = rule.get('constraint_field')
            exclusive = rule.get('exclusive', False)

            if ves_rule in ves_rules:
                value = ves_rules[ves_rule]
                if exclusive:
                    # Adjust for exclusive bounds
                    if 'minimum' in constraint_field:
                        constraints['minimum'] = value + 1
                    elif 'maximum' in constraint_field:
                        constraints['maximum'] = value - 1
                else:
                    constraints[constraint_field] = value

        return constraints

    def get_stats(self) -> Dict:
        """
        Get enrichment statistics

        Returns:
            Statistics dictionary
        """
        stats = self.stats.copy()

        # Calculate average confidence
        if stats['confidence_scores']:
            stats['average_confidence'] = sum(stats['confidence_scores']) / len(stats['confidence_scores'])
        else:
            stats['average_confidence'] = 0.0

        # Calculate coverage percentage
        if stats['properties_analyzed'] > 0:
            stats['coverage_percentage'] = (
                stats['constraints_added'] / stats['properties_analyzed'] * 100
            )
        else:
            stats['coverage_percentage'] = 0.0

        return stats


if __name__ == '__main__':
    # Test the enricher
    import json
    from pathlib import Path

    # Load a test spec
    test_spec_path = Path('specs/enriched/dns.json')
    if test_spec_path.exists():
        with open(test_spec_path, 'r') as f:
            spec = json.load(f)

        # Run enricher
        enricher = ConstraintEnricher(config_path=Path('config/constraint_patterns.yaml'))
        enriched_spec = enricher.enrich_spec(spec)

        # Print statistics
        stats = enricher.get_stats()
        print(json.dumps(stats, indent=2))

        # Save enriched spec
        output_path = Path('specs/enriched/dns_with_constraints.json')
        with open(output_path, 'w') as f:
            json.dump(enriched_spec, f, indent=2)
        print(f"Enriched spec saved to {output_path}")
    else:
        print(f"Test spec not found: {test_spec_path}")
