# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Guided Workflow Enricher for OpenAPI specifications.

Applies step-by-step deployment workflows from config/guided_workflows.yaml
to OpenAPI specification info section:
- x-f5xc-guided-workflows: Contains deployment workflows for the domain

Workflows help AI assistants and CLI tools guide users through
multi-step resource deployments.

Usage:
    enricher = GuidedWorkflowEnricher()
    spec = enricher.enrich_spec(spec, domain="virtual")
    stats = enricher.get_stats()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .extension_constants import X_F5XC_CLI_DOMAIN, X_F5XC_GUIDED_WORKFLOWS


@dataclass
class GuidedWorkflowEnrichmentStats:
    """Statistics from guided workflow enrichment."""

    specs_processed: int = 0
    workflows_applied: int = 0
    workflows_skipped: int = 0
    total_workflows: int = 0
    domains_without_config: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "specs_processed": self.specs_processed,
            "workflows_applied": self.workflows_applied,
            "workflows_skipped": self.workflows_skipped,
            "total_workflows": self.total_workflows,
            "domains_without_config": self.domains_without_config,
        }


@dataclass
class WorkflowStep:
    """Represents a step in a guided workflow."""

    order: int
    action: str
    name: str
    description: str
    resource: str | None = None
    optional: bool = False
    depends_on: list[int] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "order": self.order,
            "action": self.action,
            "name": self.name,
            "description": self.description,
        }
        if self.resource:
            result["resource"] = self.resource
        if self.optional:
            result["optional"] = self.optional
        if self.depends_on:
            result["depends_on"] = self.depends_on
        if self.required_fields:
            result["required_fields"] = self.required_fields
        if self.tips:
            result["tips"] = self.tips
        if self.verification:
            result["verification"] = self.verification
        return result


@dataclass
class GuidedWorkflow:
    """Represents a complete guided workflow."""

    id: str
    name: str
    description: str
    complexity: str = "medium"
    estimated_steps: int = 0
    prerequisites: list[str] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OpenAPI extension."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "complexity": self.complexity,
            "estimated_steps": self.estimated_steps or len(self.steps),
            "prerequisites": self.prerequisites,
            "steps": [step.to_dict() for step in self.steps],
        }


class GuidedWorkflowEnricher:
    """Enrich OpenAPI specifications with guided workflows.

    Loads workflows from config/guided_workflows.yaml and applies them
    to the x-f5xc-guided-workflows extension in the info section.

    Workflows include:
    - id: Unique identifier for the workflow
    - name: Human-readable workflow name
    - description: What the workflow accomplishes
    - steps: Sequential steps with actions and dependencies

    Attributes:
        config_path: Path to guided_workflows.yaml
        domains: Dictionary of domain -> list of GuidedWorkflow
        stats: Enrichment statistics
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with workflow configuration.

        Args:
            config_path: Path to guided_workflows.yaml config.
                        Defaults to config/guided_workflows.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "guided_workflows.yaml"

        self.config_path = config_path
        self.domains: dict[str, list[GuidedWorkflow]] = {}
        self.stats = GuidedWorkflowEnrichmentStats()
        self._config_version: str = "0.0.0"

        self._load_config()

    def _load_config(self) -> None:
        """Load workflows from YAML configuration file."""
        if not self.config_path.exists():
            # No config file - will skip enrichment gracefully
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self._config_version = config.get("version", "0.0.0")

            # Load domain-specific workflows
            workflows_config = config.get("workflows", {})
            for domain_name, domain_workflows in workflows_config.items():
                if isinstance(domain_workflows, list):
                    parsed_workflows: list[GuidedWorkflow] = []
                    for workflow in domain_workflows:
                        if isinstance(workflow, dict):
                            parsed = self._parse_workflow(workflow)
                            if parsed:
                                parsed_workflows.append(parsed)
                    if parsed_workflows:
                        self.domains[domain_name] = parsed_workflows
                        self.stats.total_workflows += len(parsed_workflows)

        except yaml.YAMLError:
            # Invalid YAML - skip enrichment gracefully
            pass

    def _parse_workflow(self, config: dict[str, Any]) -> GuidedWorkflow | None:
        """Parse a workflow from configuration dictionary.

        Args:
            config: Dictionary with workflow configuration

        Returns:
            GuidedWorkflow if valid, None otherwise
        """
        if not config.get("id") or not config.get("name"):
            return None

        steps: list[WorkflowStep] = [
            WorkflowStep(
                order=step_config.get("order", 0),
                action=step_config.get("action", ""),
                name=step_config.get("name", ""),
                description=step_config.get("description", ""),
                resource=step_config.get("resource"),
                optional=step_config.get("optional", False),
                depends_on=step_config.get("depends_on", []),
                required_fields=step_config.get("required_fields", []),
                tips=step_config.get("tips", []),
                verification=step_config.get("verification", []),
            )
            for step_config in config.get("steps", [])
            if isinstance(step_config, dict)
        ]

        return GuidedWorkflow(
            id=config.get("id", ""),
            name=config.get("name", ""),
            description=config.get("description", ""),
            complexity=config.get("complexity", "medium"),
            estimated_steps=config.get("estimated_steps", len(steps)),
            prerequisites=config.get("prerequisites", []),
            steps=sorted(steps, key=lambda s: s.order),
        )

    def enrich_spec(
        self,
        spec: dict[str, Any],
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Enrich OpenAPI specification with guided workflows.

        Applies workflows from configuration to the spec's info section
        under the x-f5xc-guided-workflows extension.

        Args:
            spec: OpenAPI specification dictionary
            domain: Domain name (e.g., "virtual"). If None, tries to extract
                   from spec's x-f5xc-cli-domain extension.

        Returns:
            Specification with enriched x-f5xc-guided-workflows
        """
        self.stats.specs_processed += 1

        # Determine domain from parameter or spec
        if domain is None:
            domain = self._extract_domain(spec)

        if domain is None:
            self.stats.workflows_skipped += 1
            return spec

        # Get workflows for this domain
        workflows = self.get_workflows(domain)

        if not workflows:
            self.stats.workflows_skipped += 1
            if domain not in self.stats.domains_without_config:
                self.stats.domains_without_config.append(domain)
            return spec

        # Ensure info section exists
        if "info" not in spec:
            spec["info"] = {}

        # Apply workflows extension
        spec["info"][X_F5XC_GUIDED_WORKFLOWS] = [w.to_dict() for w in workflows]

        self.stats.workflows_applied += len(workflows)

        return spec

    def _extract_domain(self, spec: dict[str, Any]) -> str | None:
        """Extract domain from spec's x-f5xc-cli-domain extension.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Domain name if found, None otherwise
        """
        info = spec.get("info", {})
        return info.get(X_F5XC_CLI_DOMAIN)

    def get_workflows(self, domain: str) -> list[GuidedWorkflow]:
        """Get workflows for a domain.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            List of workflows for the domain
        """
        return self.domains.get(domain, [])

    def get_workflow(self, domain: str, workflow_id: str) -> GuidedWorkflow | None:
        """Get a specific workflow by ID.

        Args:
            domain: Domain name (e.g., "virtual")
            workflow_id: Unique workflow identifier

        Returns:
            GuidedWorkflow if found, None otherwise
        """
        workflows = self.get_workflows(domain)
        for workflow in workflows:
            if workflow.id == workflow_id:
                return workflow
        return None

    def has_workflows(self, domain: str) -> bool:
        """Check if workflows exist for a domain.

        Args:
            domain: Domain name to check

        Returns:
            True if workflows are configured for the domain
        """
        return domain in self.domains and len(self.domains[domain]) > 0

    def get_configured_domains(self) -> list[str]:
        """Get list of domains with configured workflows.

        Returns:
            Sorted list of domain names
        """
        return sorted(self.domains.keys())

    def get_config_version(self) -> str:
        """Get version of loaded workflow configuration.

        Returns:
            Version string from config (e.g., "1.0.0")
        """
        return self._config_version

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

    def enrich_index(self, index: dict[str, Any]) -> dict[str, Any]:
        """Enrich index.json with guided workflows summary.

        Adds x-f5xc-guided-workflows section to the index with
        all available workflows organized by domain.

        Args:
            index: Index dictionary to enrich

        Returns:
            Enriched index dictionary
        """
        # Collect all workflows by domain
        all_workflows: list[dict[str, Any]] = []

        for domain in sorted(self.domains.keys()):
            workflows = self.get_workflows(domain)
            for workflow in workflows:
                workflow_dict = workflow.to_dict()
                workflow_dict["domain"] = domain
                all_workflows.append(workflow_dict)

        if all_workflows:
            index[X_F5XC_GUIDED_WORKFLOWS] = {
                "version": self._config_version,
                "total_workflows": len(all_workflows),
                "domains": list(self.domains.keys()),
                "workflows": all_workflows,
            }

        self.stats.total_workflows = len(all_workflows)

        return index


__all__ = [
    "GuidedWorkflow",
    "GuidedWorkflowEnricher",
    "GuidedWorkflowEnrichmentStats",
    "WorkflowStep",
]
