"""Unit tests for critical resources configuration and loading.

Tests the x-ves-critical-resources extension added to index.json
for downstream tooling (e.g., xcsh CLI).
"""

from pathlib import Path

import pytest
import yaml

from scripts.merge_specs import DEFAULT_CRITICAL_RESOURCES, load_critical_resources


class TestDefaultCriticalResources:
    """Test default critical resources list."""

    def test_default_resources_not_empty(self) -> None:
        """Verify default resources list is not empty."""
        assert len(DEFAULT_CRITICAL_RESOURCES) > 0

    def test_default_resources_contains_core_lb(self) -> None:
        """Verify default resources includes core load balancing resources."""
        assert "http_loadbalancer" in DEFAULT_CRITICAL_RESOURCES
        assert "tcp_loadbalancer" in DEFAULT_CRITICAL_RESOURCES
        assert "origin_pool" in DEFAULT_CRITICAL_RESOURCES

    def test_default_resources_contains_security(self) -> None:
        """Verify default resources includes security resources."""
        assert "app_firewall" in DEFAULT_CRITICAL_RESOURCES
        assert "service_policy" in DEFAULT_CRITICAL_RESOURCES
        assert "network_policy" in DEFAULT_CRITICAL_RESOURCES

    def test_default_resources_contains_dns(self) -> None:
        """Verify default resources includes DNS resources."""
        assert "dns_zone" in DEFAULT_CRITICAL_RESOURCES
        assert "dns_load_balancer" in DEFAULT_CRITICAL_RESOURCES

    def test_default_resources_contains_cloud_sites(self) -> None:
        """Verify default resources includes cloud site resources."""
        assert "aws_vpc_site" in DEFAULT_CRITICAL_RESOURCES
        assert "azure_vnet_site" in DEFAULT_CRITICAL_RESOURCES
        assert "gcp_vpc_site" in DEFAULT_CRITICAL_RESOURCES


class TestLoadCriticalResources:
    """Test loading critical resources from configuration."""

    def test_load_returns_list(self) -> None:
        """Verify load function returns a list."""
        result = load_critical_resources()
        assert isinstance(result, list)

    def test_load_returns_non_empty_list(self) -> None:
        """Verify load function returns a non-empty list."""
        result = load_critical_resources()
        assert len(result) > 0

    def test_load_returns_strings(self) -> None:
        """Verify load function returns list of strings."""
        result = load_critical_resources()
        for item in result:
            assert isinstance(item, str)

    def test_load_includes_core_resources(self) -> None:
        """Verify loaded resources include core load balancing."""
        result = load_critical_resources()
        assert "http_loadbalancer" in result
        assert "origin_pool" in result


class TestCriticalResourcesConfig:
    """Test critical resources configuration file."""

    @pytest.fixture
    def config_path(self) -> Path:
        """Get path to critical resources config file."""
        return Path(__file__).parent.parent / "config" / "critical_resources.yaml"

    def test_config_file_exists(self, config_path: Path) -> None:
        """Verify configuration file exists."""
        assert config_path.exists(), f"Config file not found: {config_path}"

    def test_config_is_valid_yaml(self, config_path: Path) -> None:
        """Verify configuration file is valid YAML."""
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert config is not None

    def test_config_has_resources_key(self, config_path: Path) -> None:
        """Verify configuration has resources key."""
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert "resources" in config

    def test_config_resources_is_list(self, config_path: Path) -> None:
        """Verify resources is a list."""
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert isinstance(config["resources"], list)

    def test_config_has_version(self, config_path: Path) -> None:
        """Verify configuration has version."""
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert "version" in config

    def test_config_has_description(self, config_path: Path) -> None:
        """Verify configuration has description."""
        with config_path.open() as f:
            config = yaml.safe_load(f)
        assert "description" in config

    def test_config_matches_default_fallback(self, config_path: Path) -> None:
        """Verify config resources match default fallback for consistency."""
        with config_path.open() as f:
            config = yaml.safe_load(f)

        # Config should have same resources as defaults
        config_resources = set(config["resources"])
        default_resources = set(DEFAULT_CRITICAL_RESOURCES)

        assert config_resources == default_resources, (
            f"Config resources differ from defaults. "
            f"Extra in config: {config_resources - default_resources}, "
            f"Missing in config: {default_resources - config_resources}"
        )
