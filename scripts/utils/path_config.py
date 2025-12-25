"""Centralized path configuration management for F5 XC API pipeline.

Provides a singleton PathConfig class that manages all directory and file paths
throughout the pipeline, ensuring consistency and enabling environment-aware
configuration.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class PathConfig:
    """Centralized configuration for all pipeline paths.

    Implements singleton pattern for efficiency and consistency.
    Reads from config/paths.yaml with sensible defaults.
    """

    _instance: Optional["PathConfig"] = None
    _initialized: bool = False

    def __new__(cls) -> "PathConfig":
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # noqa: SLF001
        return cls._instance

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize path configuration from YAML file.

        Args:
            config_path: Path to config/paths.yaml. Defaults to config/paths.yaml
                        relative to project root.
        """
        if self._initialized:
            return

        self.config_path = (
            config_path or Path(__file__).parent.parent.parent / "config" / "paths.yaml"
        )
        self.config: dict[str, object] = {}
        self._load_config()
        self._initialized = True

    def _load_config(self) -> None:
        """Load path configuration from YAML file."""
        try:
            with self.config_path.open() as f:
                self.config = yaml.safe_load(f) or {}
                logger.info("Loaded path configuration from %s", self.config_path)
        except FileNotFoundError:
            logger.warning("Config file not found: %s. Using defaults.", self.config_path)
            self.config = {}
        except yaml.YAMLError:
            logger.exception("Error parsing path configuration")
            self.config = {}

    def _get_path(self, *keys: str) -> str:
        """Get a path value from config using dot notation.

        Args:
            *keys: Keys in nested structure (e.g., "reports", "directory")

        Returns:
            Path string value from config or default fallback
        """
        # Try to get from config
        value: object = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                break

        # If found and is a string, return it
        if isinstance(value, str):
            return value

        # Use hardcoded defaults
        defaults: dict[tuple[str, ...], str] = {
            ("reports", "directory"): "reports",
            ("specs", "original_dir"): "specs/original",
            ("specs", "discovered_dir"): "specs/discovered",
            ("output", "docs_api_dir"): "docs/specifications/api",
            ("config", "directory"): "config",
            ("scripts", "utils_dir"): "scripts/utils",
            ("tests", "directory"): "tests",
            ("project", "version_file"): ".version",
        }

        return defaults.get(tuple(keys), "")

    # Report paths
    @property
    def reports_dir(self) -> Path:
        """Directory for generated reports."""
        return Path(self._get_path("reports", "directory"))

    @property
    def discovery_report(self) -> Path:
        """Path to discovery report (markdown)."""
        return self.reports_dir / self._get_path("reports", "discovery_report")

    @property
    def discovery_json(self) -> Path:
        """Path to discovery session JSON."""
        return self.reports_dir / self._get_path("reports", "discovery_json")

    @property
    def constraint_analysis(self) -> Path:
        """Path to constraint analysis report (markdown)."""
        return self.reports_dir / self._get_path("reports", "constraint_analysis")

    @property
    def constraint_analysis_json(self) -> Path:
        """Path to constraint analysis JSON."""
        return self.reports_dir / self._get_path("reports", "constraint_analysis_json")

    @property
    def lint_report(self) -> Path:
        """Path to lint report (markdown)."""
        return self.reports_dir / self._get_path("reports", "lint_report")

    @property
    def lint_report_json(self) -> Path:
        """Path to lint report (JSON)."""
        return self.reports_dir / self._get_path("reports", "lint_report_json")

    @property
    def validation_report(self) -> Path:
        """Path to validation report (markdown)."""
        return self.reports_dir / self._get_path("reports", "validation_report")

    @property
    def validation_report_json(self) -> Path:
        """Path to validation report (JSON)."""
        return self.reports_dir / self._get_path("reports", "validation_report_json")

    # Specs paths
    @property
    def specs_original_dir(self) -> Path:
        """Directory containing original F5 specifications."""
        return Path(self._get_path("specs", "original_dir"))

    @property
    def specs_discovered_dir(self) -> Path:
        """Directory containing discovered specifications."""
        return Path(self._get_path("specs", "discovered_dir"))

    @property
    def discovered_openapi(self) -> Path:
        """Path to discovered OpenAPI spec."""
        return Path(self._get_path("specs", "discovered_openapi"))

    @property
    def discovered_session(self) -> Path:
        """Path to discovery session metadata."""
        return Path(self._get_path("specs", "discovered_session"))

    # Output paths
    @property
    def docs_api_dir(self) -> Path:
        """Directory for generated API documentation specs."""
        return Path(self._get_path("output", "docs_api_dir"))

    @property
    def openapi_spec(self) -> Path:
        """Path to main OpenAPI spec."""
        return Path(self._get_path("output", "openapi_spec"))

    @property
    def index_file(self) -> Path:
        """Path to index JSON file."""
        return Path(self._get_path("output", "index_file"))

    # Config paths
    @property
    def config_dir(self) -> Path:
        """Directory containing configuration files."""
        return Path(self._get_path("config", "directory"))

    @property
    def enrichment_config(self) -> Path:
        """Path to enrichment configuration."""
        return Path(self._get_path("config", "enrichment"))

    @property
    def normalization_config(self) -> Path:
        """Path to normalization configuration."""
        return Path(self._get_path("config", "normalization"))

    @property
    def discovery_config(self) -> Path:
        """Path to discovery configuration."""
        return Path(self._get_path("config", "discovery"))

    @property
    def spectral_config(self) -> Path:
        """Path to Spectral linting configuration."""
        return Path(self._get_path("config", "spectral"))

    @property
    def server_variables_config(self) -> Path:
        """Path to server variables configuration."""
        return Path(self._get_path("config", "server_variables"))

    # Project paths
    @property
    def version_file(self) -> Path:
        """Path to version file."""
        return Path(self._get_path("project", "version_file"))

    # Utility methods
    def ensure_report_dir_exists(self) -> Path:
        """Ensure reports directory exists and return its path."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        return self.reports_dir

    def ensure_output_dir_exists(self) -> Path:
        """Ensure output directory exists and return its path."""
        self.docs_api_dir.mkdir(parents=True, exist_ok=True)
        return self.docs_api_dir
