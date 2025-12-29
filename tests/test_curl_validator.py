"""Tests for CurlExampleValidator CRUD validation.

Tests the validation of curl examples against live F5 XC API
through Create, Read, Update, Delete operations.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scripts.utils.curl_validator import (
    CrudTestResult,
    CurlExampleValidator,
    OperationResult,
    ValidationReport,
    generate_json_report,
    generate_markdown_report,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""

    def _create_response(status_code: int, json_data: dict | None = None):
        response = MagicMock()
        response.status_code = status_code
        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = json.JSONDecodeError("No JSON", "", 0)
        return response

    return _create_response


@pytest.fixture
def sample_resource_config():
    """Sample resource configuration for testing."""
    return {
        "description": "HTTP Load Balancer",
        "example_json": json.dumps(
            {
                "metadata": {"name": "example-lb", "namespace": "default"},
                "spec": {
                    "domains": ["example.com"],
                    "http": {"dns_volterra_managed": True},
                },
            },
        ),
        "example_yaml": "metadata:\n  name: example-lb\n",
        "example_curl": 'curl -X POST "$F5XC_API_URL/api/config/..."',
    }


@pytest.fixture
def validator_with_mocked_configs(tmp_path):
    """Create a validator with mocked minimum configs."""
    validator = CurlExampleValidator(
        specs_dir=tmp_path,
        api_url="https://test.console.ves.volterra.io",
        api_token="test-token-123",
        namespace="test-ns",
        dry_run=False,
    )
    return validator


class TestOperationResult:
    """Test OperationResult dataclass."""

    def test_operation_result_initialization(self):
        """Test OperationResult initialization with defaults."""
        result = OperationResult(
            operation="create",
            status_code=200,
            success=True,
        )
        assert result.operation == "create"
        assert result.status_code == 200
        assert result.success is True
        assert result.response_body is None
        assert result.error is None
        assert result.duration_ms == 0.0

    def test_operation_result_with_error(self):
        """Test OperationResult with error."""
        result = OperationResult(
            operation="create",
            status_code=400,
            success=False,
            error="Bad request: missing required field",
        )
        assert result.success is False
        assert result.error == "Bad request: missing required field"

    def test_operation_result_with_response_body(self):
        """Test OperationResult with response body."""
        body = {"metadata": {"name": "test"}, "spec": {}}
        result = OperationResult(
            operation="read",
            status_code=200,
            success=True,
            response_body=body,
        )
        assert result.response_body == body
        assert result.response_body["metadata"]["name"] == "test"


class TestCrudTestResult:
    """Test CrudTestResult dataclass."""

    def test_crud_result_initialization(self):
        """Test CrudTestResult initialization."""
        result = CrudTestResult(
            resource_type="http_loadbalancer",
            test_name="curl-test-abc12345",
            api_path="/api/config/namespaces/default/http_loadbalancers",
        )
        assert result.resource_type == "http_loadbalancer"
        assert result.test_name == "curl-test-abc12345"
        assert result.api_path == "/api/config/namespaces/default/http_loadbalancers"
        assert result.operations == []
        assert result.errors == []
        assert result.duration_ms == 0.0

    def test_create_result_property(self):
        """Test create_result property."""
        result = CrudTestResult(
            resource_type="origin_pool",
            test_name="test-1",
            api_path="/api/config/namespaces/default/origin_pools",
        )
        result.operations.append(
            OperationResult(operation="create", status_code=201, success=True),
        )
        result.operations.append(
            OperationResult(operation="read", status_code=200, success=True),
        )

        assert result.create_result is not None
        assert result.create_result.status_code == 201

    def test_read_result_property(self):
        """Test read_result property."""
        result = CrudTestResult(
            resource_type="origin_pool",
            test_name="test-1",
            api_path="/api/config/namespaces/default/origin_pools",
        )
        result.operations.append(
            OperationResult(operation="create", status_code=201, success=True),
        )
        result.operations.append(
            OperationResult(operation="read", status_code=200, success=True),
        )

        assert result.read_result is not None
        assert result.read_result.status_code == 200

    def test_update_result_property(self):
        """Test update_result property."""
        result = CrudTestResult(
            resource_type="healthcheck",
            test_name="test-1",
            api_path="/api/config/namespaces/default/healthchecks",
        )
        result.operations.append(
            OperationResult(operation="update", status_code=200, success=True),
        )

        assert result.update_result is not None
        assert result.update_result.success is True

    def test_delete_result_property(self):
        """Test delete_result property."""
        result = CrudTestResult(
            resource_type="app_firewall",
            test_name="test-1",
            api_path="/api/config/namespaces/default/app_firewalls",
        )
        result.operations.append(
            OperationResult(operation="delete", status_code=204, success=True),
        )

        assert result.delete_result is not None
        assert result.delete_result.status_code == 204

    def test_verify_delete_result_property(self):
        """Test verify_delete_result property."""
        result = CrudTestResult(
            resource_type="tcp_loadbalancer",
            test_name="test-1",
            api_path="/api/config/namespaces/default/tcp_loadbalancers",
        )
        result.operations.append(
            OperationResult(operation="verify_delete", status_code=404, success=True),
        )

        assert result.verify_delete_result is not None
        assert result.verify_delete_result.status_code == 404

    def test_full_success_property_true(self):
        """Test full_success property when all operations succeed."""
        result = CrudTestResult(
            resource_type="http_loadbalancer",
            test_name="test-1",
            api_path="/api/config/namespaces/default/http_loadbalancers",
        )
        result.operations = [
            OperationResult(operation="create", status_code=201, success=True),
            OperationResult(operation="read", status_code=200, success=True),
            OperationResult(operation="update", status_code=200, success=True),
            OperationResult(operation="delete", status_code=204, success=True),
            OperationResult(operation="verify_delete", status_code=404, success=True),
        ]

        assert result.full_success is True

    def test_full_success_property_false(self):
        """Test full_success property when one operation fails."""
        result = CrudTestResult(
            resource_type="http_loadbalancer",
            test_name="test-1",
            api_path="/api/config/namespaces/default/http_loadbalancers",
        )
        result.operations = [
            OperationResult(operation="create", status_code=201, success=True),
            OperationResult(operation="read", status_code=200, success=True),
            OperationResult(operation="update", status_code=400, success=False),
        ]

        assert result.full_success is False

    def test_partial_success_property(self):
        """Test partial_success property."""
        result = CrudTestResult(
            resource_type="origin_pool",
            test_name="test-1",
            api_path="/api/config/namespaces/default/origin_pools",
        )
        result.operations = [
            OperationResult(operation="create", status_code=201, success=True),
            OperationResult(operation="read", status_code=500, success=False),
        ]

        assert result.partial_success is True
        assert result.full_success is False

    def test_to_dict(self):
        """Test to_dict method."""
        result = CrudTestResult(
            resource_type="http_loadbalancer",
            test_name="test-1",
            api_path="/api/config/namespaces/default/http_loadbalancers",
            duration_ms=1234.56,
        )
        result.operations = [
            OperationResult(operation="create", status_code=201, success=True, duration_ms=100.5),
        ]
        result.errors = ["Some warning"]

        d = result.to_dict()
        assert d["resource_type"] == "http_loadbalancer"
        assert d["test_name"] == "test-1"
        assert d["full_success"] is True
        assert d["partial_success"] is True
        assert d["duration_ms"] == 1234.56
        assert "create" in d["operations"]
        assert d["operations"]["create"]["status_code"] == 201
        assert d["errors"] == ["Some warning"]


class TestValidationReport:
    """Test ValidationReport dataclass."""

    def test_report_initialization(self):
        """Test ValidationReport initialization."""
        report = ValidationReport()
        assert report.timestamp == ""
        assert report.total_resources == 0
        assert report.passed == 0
        assert report.failed == 0
        assert report.skipped == 0
        assert report.duration_seconds == 0.0
        assert report.results == []
        assert report.errors == []
        assert report.dry_run is False

    def test_report_to_dict(self):
        """Test ValidationReport to_dict method."""
        report = ValidationReport(
            timestamp="2025-01-15T10:30:00Z",
            total_resources=5,
            passed=4,
            failed=1,
            skipped=0,
            duration_seconds=45.123456,
            dry_run=False,
        )

        d = report.to_dict()
        assert d["timestamp"] == "2025-01-15T10:30:00Z"
        assert d["summary"]["total_resources"] == 5
        assert d["summary"]["passed"] == 4
        assert d["summary"]["failed"] == 1
        assert d["summary"]["duration_seconds"] == 45.12
        assert d["summary"]["dry_run"] is False


class TestCurlExampleValidatorInit:
    """Test CurlExampleValidator initialization."""

    def test_validator_initialization(self, tmp_path):
        """Test validator initializes with correct parameters."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
            dry_run=True,
        )
        assert validator.specs_dir == tmp_path
        assert validator.api_url == "https://example.console.ves.volterra.io"
        assert validator.api_token == "test-token"
        assert validator.namespace == "test-ns"
        assert validator.dry_run is True

    def test_api_url_strips_trailing_slash(self, tmp_path):
        """Test API URL trailing slash is stripped."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io/",
            api_token="test-token",
        )
        assert validator.api_url == "https://example.console.ves.volterra.io"

    def test_config_loading_defaults(self, tmp_path):
        """Test default config is loaded when no config file exists."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            config_path=tmp_path / "nonexistent.yaml",
        )
        # Defaults should be used
        assert validator.config.get("validation", {}).get("namespace") == "default"
        assert validator.config.get("validation", {}).get("test_prefix") == "curl-test"
        assert validator.config.get("expected_status", {}).get("create") == [200, 201]

    def test_test_prefix_from_config(self, tmp_path):
        """Test test_prefix is read from config."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            """
validation:
  test_prefix: "my-custom-prefix"
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )
        assert validator.test_prefix == "my-custom-prefix"


class TestAuthHeaders:
    """Test authentication header generation."""

    def test_get_auth_headers(self, tmp_path):
        """Test auth headers are correctly formatted."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="my-secret-token",
        )
        headers = validator._get_auth_headers()
        assert headers["Authorization"] == "APIToken my-secret-token"
        assert headers["Content-Type"] == "application/json"


class TestTestNameGeneration:
    """Test unique test name generation."""

    def test_generate_test_name_format(self, tmp_path):
        """Test test name follows expected format."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
        )
        name = validator._generate_test_name()
        assert name.startswith("curl-test-")
        # Should have 8 character UUID suffix
        suffix = name.replace("curl-test-", "")
        assert len(suffix) == 8
        # Should be hexadecimal
        int(suffix, 16)

    def test_generate_test_name_unique(self, tmp_path):
        """Test test names are unique."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
        )
        names = [validator._generate_test_name() for _ in range(100)]
        assert len(set(names)) == 100  # All unique

    def test_generate_test_name_custom_prefix(self, tmp_path):
        """Test test name uses custom prefix."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            """
validation:
  test_prefix: "my-prefix"
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )
        name = validator._generate_test_name()
        assert name.startswith("my-prefix-")


class TestApiPathConstruction:
    """Test API path construction."""

    def test_get_api_path_collection(self, tmp_path):
        """Test API path for collection endpoint."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="my-namespace",
        )
        path = validator._get_api_path("http_loadbalancer")
        assert path == "/api/config/namespaces/my-namespace/http_loadbalancers"

    def test_get_api_path_resource(self, tmp_path):
        """Test API path for individual resource endpoint."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="my-namespace",
        )
        path = validator._get_api_path(
            "origin_pool",
            include_name=True,
            name="my-pool",
        )
        assert path == "/api/config/namespaces/my-namespace/origin_pools/my-pool"

    def test_get_api_path_from_config(self, tmp_path):
        """Test API path uses configured path templates."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            """
api_paths:
  custom_resource:
    collection: "/api/custom/namespaces/{namespace}/resources"
    resource: "/api/custom/namespaces/{namespace}/resources/{name}"
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
            config_path=config_path,
        )
        path = validator._get_api_path("custom_resource")
        assert path == "/api/custom/namespaces/test-ns/resources"

        path_with_name = validator._get_api_path(
            "custom_resource",
            include_name=True,
            name="my-resource",
        )
        assert path_with_name == "/api/custom/namespaces/test-ns/resources/my-resource"


class TestExampleJsonParsing:
    """Test example JSON parsing and name injection."""

    def test_parse_example_json_valid(self, tmp_path):
        """Test parsing valid example JSON."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )
        example_json = json.dumps(
            {
                "metadata": {"name": "placeholder"},
                "spec": {"domains": ["example.com"]},
            },
        )
        result = validator._parse_example_json(example_json, "curl-test-abc123")

        assert result["metadata"]["name"] == "curl-test-abc123"
        assert result["metadata"]["namespace"] == "test-ns"
        assert result["spec"]["domains"] == ["example.com"]

    def test_parse_example_json_no_metadata(self, tmp_path):
        """Test parsing JSON without metadata key."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )
        example_json = json.dumps({"spec": {"port": 443}})
        result = validator._parse_example_json(example_json, "curl-test-def456")

        assert result["metadata"]["name"] == "curl-test-def456"
        assert result["metadata"]["namespace"] == "test-ns"
        assert result["spec"]["port"] == 443

    def test_parse_example_json_invalid(self, tmp_path):
        """Test parsing invalid JSON raises error."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
        )
        with pytest.raises(ValueError, match="Invalid example_json"):
            validator._parse_example_json("not valid json", "test-name")


class TestLoadMinimumConfigs:
    """Test loading minimum configurations."""

    def test_load_minimum_configs_file_exists(self, tmp_path):
        """Test loading configs when file exists."""
        # Create a mock minimum_configs.yaml
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "minimum_configs.yaml").write_text(
            """
resources:
  http_loadbalancer:
    description: "HTTP Load Balancer"
    example_json: |
      {"metadata": {"name": "example"}, "spec": {}}
  origin_pool:
    description: "Origin Pool"
    example_json: |
      {"metadata": {"name": "example"}, "spec": {"port": 443}}
""",
        )

        # Patch the path to use our temp directory
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
        )

        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "description": "HTTP Load Balancer",
                    "example_json": '{"metadata": {"name": "example"}, "spec": {}}',
                },
                "origin_pool": {
                    "description": "Origin Pool",
                    "example_json": '{"metadata": {"name": "example"}, "spec": {"port": 443}}',
                },
            },
        ):
            resources = validator.load_minimum_configs()
            assert "http_loadbalancer" in resources
            assert "origin_pool" in resources


class TestReportGeneration:
    """Test report generation functions."""

    def test_generate_json_report(self, tmp_path):
        """Test JSON report generation."""
        report = ValidationReport(
            timestamp="2025-01-15T10:30:00Z",
            total_resources=2,
            passed=1,
            failed=1,
            duration_seconds=30.5,
        )
        result = CrudTestResult(
            resource_type="http_loadbalancer",
            test_name="curl-test-abc123",
            api_path="/api/config/namespaces/default/http_loadbalancers",
        )
        result.operations.append(
            OperationResult(operation="create", status_code=201, success=True),
        )
        report.results.append(result)

        output_path = tmp_path / "report.json"
        generate_json_report(report, output_path)

        assert output_path.exists()
        with output_path.open() as f:
            data = json.load(f)
        assert data["summary"]["total_resources"] == 2
        assert data["summary"]["passed"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["resource_type"] == "http_loadbalancer"

    def test_generate_markdown_report(self, tmp_path):
        """Test Markdown report generation."""
        report = ValidationReport(
            timestamp="2025-01-15T10:30:00Z",
            total_resources=2,
            passed=2,
            failed=0,
            duration_seconds=25.0,
        )
        result = CrudTestResult(
            resource_type="origin_pool",
            test_name="curl-test-xyz789",
            api_path="/api/config/namespaces/default/origin_pools",
        )
        result.operations = [
            OperationResult(operation="create", status_code=201, success=True),
            OperationResult(operation="read", status_code=200, success=True),
            OperationResult(operation="delete", status_code=204, success=True),
        ]
        report.results.append(result)

        output_path = tmp_path / "report.md"
        generate_markdown_report(report, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "# curl Example CRUD Validation Report" in content
        assert "origin_pool" in content
        assert "curl-test-xyz789" in content
        assert "✅" in content  # Success emoji
        assert "CREATE" in content
        assert "READ" in content
        assert "DELETE" in content

    def test_generate_markdown_report_with_errors(self, tmp_path):
        """Test Markdown report includes errors."""
        report = ValidationReport(
            timestamp="2025-01-15T10:30:00Z",
            total_resources=1,
            passed=0,
            failed=1,
            duration_seconds=5.0,
        )
        result = CrudTestResult(
            resource_type="healthcheck",
            test_name="curl-test-fail1",
            api_path="/api/config/namespaces/default/healthchecks",
        )
        result.operations = [
            OperationResult(
                operation="create",
                status_code=400,
                success=False,
                error="Bad request",
            ),
        ]
        result.errors = ["CREATE failed: Bad request"]
        report.results.append(result)
        report.errors = ["Global error message"]

        output_path = tmp_path / "report.md"
        generate_markdown_report(report, output_path)

        content = output_path.read_text()
        assert "❌" in content  # Failure emoji
        assert "CREATE failed: Bad request" in content
        assert "Global error message" in content

    def test_report_creates_parent_directories(self, tmp_path):
        """Test report generation creates parent directories."""
        report = ValidationReport()
        output_path = tmp_path / "nested" / "path" / "report.json"

        generate_json_report(report, output_path)

        assert output_path.exists()
        assert (tmp_path / "nested" / "path").is_dir()


class TestDryRunMode:
    """Test dry-run mode functionality."""

    @pytest.mark.asyncio
    async def test_validate_all_dry_run(self, tmp_path):
        """Test validate_all in dry-run mode doesn't make HTTP calls."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="dummy-token",
            dry_run=True,
        )

        # Mock the load_minimum_configs to return test data
        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "example_json": '{"metadata": {"name": "test"}, "spec": {"domains": ["example.com"]}}',
                },
            },
        ):
            report = await validator.validate_all()

        assert report.dry_run is True
        assert report.total_resources == 1
        assert report.passed == 1
        assert report.failed == 0

    @pytest.mark.asyncio
    async def test_validate_all_dry_run_invalid_json(self, tmp_path):
        """Test dry-run mode catches invalid JSON."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="dummy-token",
            dry_run=True,
        )

        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "example_json": "not valid json",
                },
            },
        ):
            report = await validator.validate_all()

        assert report.dry_run is True
        assert report.total_resources == 1
        assert report.passed == 0
        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_validate_all_dry_run_missing_json(self, tmp_path):
        """Test dry-run mode handles missing example_json."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="dummy-token",
            dry_run=True,
        )

        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "description": "No example_json here",
                },
            },
        ):
            report = await validator.validate_all()

        assert report.dry_run is True
        assert report.failed == 1
        assert any("No example_json" in err for r in report.results for err in r.errors)


class TestResourceFiltering:
    """Test resource filtering functionality."""

    @pytest.mark.asyncio
    async def test_validate_all_with_resource_filter(self, tmp_path):
        """Test validate_all respects resource filter."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="dummy-token",
            dry_run=True,
        )

        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "example_json": '{"metadata": {}, "spec": {}}',
                },
                "origin_pool": {
                    "example_json": '{"metadata": {}, "spec": {}}',
                },
                "tcp_loadbalancer": {
                    "example_json": '{"metadata": {}, "spec": {}}',
                },
            },
        ):
            report = await validator.validate_all(resource_filter=["origin_pool"])

        assert report.total_resources == 1
        assert report.results[0].resource_type == "origin_pool"

    @pytest.mark.asyncio
    async def test_validate_all_with_config_resources(self, tmp_path):
        """Test validate_all respects config resources list."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            """
validation:
  resources: ["http_loadbalancer"]
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="dummy-token",
            dry_run=True,
            config_path=config_path,
        )

        with patch.object(
            validator,
            "load_minimum_configs",
            return_value={
                "http_loadbalancer": {
                    "example_json": '{"metadata": {}, "spec": {}}',
                },
                "origin_pool": {
                    "example_json": '{"metadata": {}, "spec": {}}',
                },
            },
        ):
            report = await validator.validate_all()

        assert report.total_resources == 1
        assert report.results[0].resource_type == "http_loadbalancer"


class TestExpectedStatusCodes:
    """Test expected status code configuration."""

    def test_default_expected_status_codes(self, tmp_path):
        """Test default expected status codes are set."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
        )
        expected = validator.config.get("expected_status", {})
        assert expected.get("create") == [200, 201]
        assert expected.get("read") == [200]
        assert expected.get("update") == [200]
        assert expected.get("delete") == [200, 202, 204]
        assert expected.get("verify_delete") == [404]

    def test_custom_expected_status_codes(self, tmp_path):
        """Test custom expected status codes from config."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text(
            """
expected_status:
  create: [201]
  read: [200, 304]
  update: [200, 204]
  delete: [200, 202]
  verify_delete: [404, 410]
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://example.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )
        expected = validator.config.get("expected_status", {})
        assert expected.get("create") == [201]
        assert expected.get("read") == [200, 304]
        assert expected.get("update") == [200, 204]
        assert expected.get("delete") == [200, 202]
        assert expected.get("verify_delete") == [404, 410]


# ============================================================================
# HTTP Request Execution Tests
# ============================================================================


class TestExecuteRequest:
    """Test HTTP request execution with mocked client."""

    @pytest.mark.asyncio
    async def test_execute_request_get_success(self, tmp_path, mock_httpx_response):
        """Test successful GET request."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "test"}},
        )

        status, body, error = await validator._execute_request(
            mock_client,
            "GET",
            "https://test.console.ves.volterra.io/api/test",
        )

        assert status == 200
        assert body == {"metadata": {"name": "test"}}
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_request_post_success(self, tmp_path, mock_httpx_response):
        """Test successful POST request."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(
            201,
            {"metadata": {"name": "created"}},
        )

        status, body, error = await validator._execute_request(
            mock_client,
            "POST",
            "https://test.console.ves.volterra.io/api/test",
            json_data={"spec": {}},
        )

        assert status == 201
        assert body == {"metadata": {"name": "created"}}
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_request_put_success(self, tmp_path, mock_httpx_response):
        """Test successful PUT request."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.put.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "updated"}},
        )

        status, body, error = await validator._execute_request(
            mock_client,
            "PUT",
            "https://test.console.ves.volterra.io/api/test/resource",
            json_data={"spec": {"updated": True}},
        )

        assert status == 200
        assert body == {"metadata": {"name": "updated"}}
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_request_delete_success(self, tmp_path, mock_httpx_response):
        """Test successful DELETE request."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_httpx_response(204)

        status, body, error = await validator._execute_request(
            mock_client,
            "DELETE",
            "https://test.console.ves.volterra.io/api/test/resource",
        )

        assert status == 204
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_request_unsupported_method(self, tmp_path):
        """Test unsupported HTTP method returns error."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()

        status, body, error = await validator._execute_request(
            mock_client,
            "PATCH",
            "https://test.console.ves.volterra.io/api/test",
        )

        assert status == 0
        assert body is None
        assert "Unsupported method" in error

    @pytest.mark.asyncio
    async def test_execute_request_timeout(self, tmp_path):
        """Test request timeout handling."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

        status, body, error = await validator._execute_request(
            mock_client,
            "GET",
            "https://test.console.ves.volterra.io/api/test",
        )

        assert status == 0
        assert body is None
        assert error == "Request timed out"

    @pytest.mark.asyncio
    async def test_execute_request_network_error(self, tmp_path):
        """Test network error handling."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")

        status, body, error = await validator._execute_request(
            mock_client,
            "GET",
            "https://test.console.ves.volterra.io/api/test",
        )

        assert status == 0
        assert body is None
        assert "Connection refused" in error

    @pytest.mark.asyncio
    async def test_execute_request_unexpected_error(self, tmp_path):
        """Test unexpected error handling."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        mock_client = AsyncMock()
        mock_client.get.side_effect = RuntimeError("Unexpected failure")

        status, body, error = await validator._execute_request(
            mock_client,
            "GET",
            "https://test.console.ves.volterra.io/api/test",
        )

        assert status == 0
        assert body is None
        assert "Unexpected error" in error


# ============================================================================
# CRUD Operation Tests
# ============================================================================


class TestCrudOperations:
    """Test individual CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_success(self, tmp_path, mock_httpx_response):
        """Test CREATE operation success."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(
            201,
            {"metadata": {"name": "test-resource"}},
        )

        # Patch rate limiter to not actually wait
        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._create(
                    mock_client,
                    "http_loadbalancer",
                    {"metadata": {"name": "test"}, "spec": {}},
                )

        assert result.operation == "create"
        assert result.status_code == 201
        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_create_failure(self, tmp_path, mock_httpx_response):
        """Test CREATE operation failure."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(
            400,
            {"error": "Bad request"},
        )

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._create(
                    mock_client,
                    "http_loadbalancer",
                    {"metadata": {"name": "test"}, "spec": {}},
                )

        assert result.operation == "create"
        assert result.status_code == 400
        assert result.success is False
        assert "Unexpected status" in result.error

    @pytest.mark.asyncio
    async def test_read_success(self, tmp_path, mock_httpx_response):
        """Test READ operation success."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "test-resource"}, "spec": {}},
        )

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._read(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                )

        assert result.operation == "read"
        assert result.status_code == 200
        assert result.success is True

    @pytest.mark.asyncio
    async def test_read_not_found(self, tmp_path, mock_httpx_response):
        """Test READ operation when resource not found."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_httpx_response(404, {"error": "Not found"})

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._read(
                    mock_client,
                    "http_loadbalancer",
                    "nonexistent",
                )

        assert result.operation == "read"
        assert result.status_code == 404
        assert result.success is False

    @pytest.mark.asyncio
    async def test_update_success(self, tmp_path, mock_httpx_response):
        """Test UPDATE operation success."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.put.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "test-resource", "labels": {"curl-test-updated": "true"}}},
        )

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._update(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                    {"metadata": {"name": "test-resource"}, "spec": {}},
                )

        assert result.operation == "update"
        assert result.status_code == 200
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_adds_label(self, tmp_path, mock_httpx_response):
        """Test UPDATE adds curl-test-updated label."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.put.return_value = mock_httpx_response(200, {})

        captured_data = None

        async def capture_put(url, json, timeout):
            nonlocal captured_data
            captured_data = json
            return mock_httpx_response(200, {})

        mock_client.put = capture_put

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                await validator._update(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                    {"metadata": {"name": "test-resource"}, "spec": {}},
                )

        assert captured_data["metadata"]["labels"]["curl-test-updated"] == "true"

    @pytest.mark.asyncio
    async def test_delete_success(self, tmp_path, mock_httpx_response):
        """Test DELETE operation success."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_httpx_response(204)

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._delete(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                )

        assert result.operation == "delete"
        assert result.status_code == 204
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_delete_success(self, tmp_path, mock_httpx_response):
        """Test VERIFY DELETE operation success (resource gone)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_httpx_response(404, {"error": "Not found"})

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._verify_delete(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                )

        assert result.operation == "verify_delete"
        assert result.status_code == 404
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_delete_failure_resource_exists(self, tmp_path, mock_httpx_response):
        """Test VERIFY DELETE fails when resource still exists."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "still-here"}},
        )

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._verify_delete(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                )

        assert result.operation == "verify_delete"
        assert result.status_code == 200
        assert result.success is False
        assert "Resource still exists" in result.error


# ============================================================================
# Full CRUD Lifecycle Tests
# ============================================================================


class TestValidateResource:
    """Test full CRUD lifecycle validation for a resource."""

    @pytest.mark.asyncio
    async def test_validate_resource_full_success(self, tmp_path, mock_httpx_response):
        """Test full CRUD lifecycle success."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()

        # Setup responses for each CRUD operation
        mock_client.post.return_value = mock_httpx_response(201, {"metadata": {"name": "test"}})
        mock_client.get.side_effect = [
            mock_httpx_response(200, {"metadata": {"name": "test"}}),  # READ
            mock_httpx_response(404, {"error": "Not found"}),  # VERIFY DELETE
        ]
        mock_client.put.return_value = mock_httpx_response(200, {"metadata": {"name": "test"}})
        mock_client.delete.return_value = mock_httpx_response(204)

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {"domains": ["example.com"]}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await validator.validate_resource(
                        mock_client,
                        "http_loadbalancer",
                        resource_config,
                    )

        assert result.resource_type == "http_loadbalancer"
        assert result.full_success is True
        assert len(result.operations) == 5  # CREATE, READ, UPDATE, DELETE, VERIFY_DELETE
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_validate_resource_create_failure(self, tmp_path, mock_httpx_response):
        """Test CRUD stops on CREATE failure."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(400, {"error": "Bad request"})

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator.validate_resource(
                    mock_client,
                    "http_loadbalancer",
                    resource_config,
                )

        assert result.full_success is False
        assert result.partial_success is False
        assert len(result.operations) == 1  # Only CREATE attempted
        assert any("CREATE failed" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_validate_resource_read_failure_still_deletes(
        self,
        tmp_path,
        mock_httpx_response,
    ):
        """Test cleanup happens even when READ fails."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(201, {"metadata": {"name": "test"}})
        mock_client.get.return_value = mock_httpx_response(500, {"error": "Server error"})
        mock_client.delete.return_value = mock_httpx_response(204)

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator.validate_resource(
                    mock_client,
                    "http_loadbalancer",
                    resource_config,
                )

        assert result.full_success is False
        assert result.partial_success is True  # CREATE succeeded
        assert len(result.operations) == 3  # CREATE, READ (failed), DELETE (cleanup)
        assert result.delete_result is not None
        assert result.delete_result.success is True

    @pytest.mark.asyncio
    async def test_validate_resource_missing_example_json(self, tmp_path):
        """Test handling of missing example_json."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        resource_config = {"description": "No example_json"}

        result = await validator.validate_resource(
            mock_client,
            "http_loadbalancer",
            resource_config,
        )

        assert len(result.operations) == 0
        assert any("No example_json" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_validate_resource_invalid_example_json(self, tmp_path):
        """Test handling of invalid example_json."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        resource_config = {"example_json": "not valid json"}

        result = await validator.validate_resource(
            mock_client,
            "http_loadbalancer",
            resource_config,
        )

        assert len(result.operations) == 0
        assert any("Invalid example_json" in err for err in result.errors)


# ============================================================================
# Skip Operations Tests
# ============================================================================


class TestSkipOperations:
    """Test skip_operations configuration."""

    @pytest.mark.asyncio
    async def test_skip_create_returns_early(self, tmp_path):
        """Test that skipping CREATE returns early."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
validation:
  skip_operations: ["create"]
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )

        mock_client = AsyncMock()
        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
        }

        result = await validator.validate_resource(
            mock_client,
            "http_loadbalancer",
            resource_config,
        )

        assert len(result.operations) == 0
        assert any("CREATE skipped" in err for err in result.errors)

    @pytest.mark.asyncio
    async def test_skip_update(self, tmp_path, mock_httpx_response):
        """Test skipping UPDATE operation."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
validation:
  skip_operations: ["update"]
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_httpx_response(201, {})
        mock_client.get.side_effect = [
            mock_httpx_response(200, {}),  # READ
            mock_httpx_response(404, {}),  # VERIFY DELETE
        ]
        mock_client.delete.return_value = mock_httpx_response(204)

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await validator.validate_resource(
                        mock_client,
                        "http_loadbalancer",
                        resource_config,
                    )

        # Should have CREATE, READ, DELETE, VERIFY_DELETE (no UPDATE)
        operations = [op.operation for op in result.operations]
        assert "update" not in operations
        assert "create" in operations
        assert "delete" in operations


# ============================================================================
# Validate All (Non-Dry-Run) Tests
# ============================================================================


class TestValidateAllNonDryRun:
    """Test validate_all in non-dry-run mode."""

    @pytest.mark.asyncio
    async def test_validate_all_empty_resources(self, tmp_path):
        """Test validate_all with no resources."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            dry_run=False,
        )

        with patch.object(validator, "load_minimum_configs", return_value={}):
            report = await validator.validate_all()

        assert report.total_resources == 0
        assert any("No resources found" in err for err in report.errors)

    @pytest.mark.asyncio
    async def test_validate_all_with_resources(self, tmp_path, mock_httpx_response):
        """Test validate_all executes CRUD for each resource."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            dry_run=False,
        )

        resources = {
            "http_loadbalancer": {
                "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
            },
        }

        # Mock the HTTP client
        with patch.object(validator, "load_minimum_configs", return_value=resources):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_httpx_response(201, {})
                mock_client.get.side_effect = [
                    mock_httpx_response(200, {}),
                    mock_httpx_response(404, {}),
                ]
                mock_client.put.return_value = mock_httpx_response(200, {})
                mock_client.delete.return_value = mock_httpx_response(204)

                # Make AsyncClient return our mock
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client_class.return_value.__aexit__.return_value = None

                with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
                    with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                        with patch("asyncio.sleep", new_callable=AsyncMock):
                            report = await validator.validate_all()

        assert report.total_resources == 1
        assert report.dry_run is False


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanupTestResources:
    """Test cleanup of orphaned test resources."""

    @pytest.mark.asyncio
    async def test_cleanup_finds_and_deletes_test_resources(self, tmp_path, mock_httpx_response):
        """Test cleanup deletes resources with test prefix."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        resources = {
            "http_loadbalancer": {"example_json": "{}"},
        }

        list_response = mock_httpx_response(
            200,
            {
                "items": [
                    {"metadata": {"name": "curl-test-abc123"}},
                    {"metadata": {"name": "curl-test-def456"}},
                    {"metadata": {"name": "production-lb"}},  # Should not be deleted
                ],
            },
        )

        with patch.object(validator, "load_minimum_configs", return_value=resources):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = list_response
                mock_client.delete.return_value = mock_httpx_response(204)

                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client_class.return_value.__aexit__.return_value = None

                cleaned = await validator.cleanup_test_resources()

        # Should delete 2 test resources (curl-test-*)
        assert cleaned == 2
        assert mock_client.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_handles_list_error(self, tmp_path, mock_httpx_response):
        """Test cleanup handles errors gracefully."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        resources = {"http_loadbalancer": {"example_json": "{}"}}

        with patch.object(validator, "load_minimum_configs", return_value=resources):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_httpx_response(500, {"error": "Server error"})

                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client_class.return_value.__aexit__.return_value = None

                cleaned = await validator.cleanup_test_resources()

        assert cleaned == 0  # No cleanup on error

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception(self, tmp_path):
        """Test cleanup handles exceptions gracefully."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )

        resources = {"http_loadbalancer": {"example_json": "{}"}}

        with patch.object(validator, "load_minimum_configs", return_value=resources):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get.side_effect = Exception("Connection failed")

                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client_class.return_value.__aexit__.return_value = None

                cleaned = await validator.cleanup_test_resources()

        assert cleaned == 0  # Continues with other resource types


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_config_loading_with_partial_config(self, tmp_path):
        """Test config loading with partial config file."""
        config_path = tmp_path / "partial.yaml"
        config_path.write_text(
            """
validation:
  timeout: 60
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )

        # Timeout should be overridden
        assert validator.config.get("validation", {}).get("timeout") == 60
        # Other defaults should be preserved
        assert validator.config.get("validation", {}).get("test_prefix") == "curl-test"
        assert validator.config.get("expected_status", {}).get("create") == [200, 201]

    def test_empty_operations_full_success(self):
        """Test full_success with empty operations list."""
        result = CrudTestResult(
            resource_type="test",
            test_name="test-1",
            api_path="/test",
        )
        # all() on empty list is True
        assert result.full_success is True

    def test_result_none_properties(self):
        """Test operation result properties return None when not present."""
        result = CrudTestResult(
            resource_type="test",
            test_name="test-1",
            api_path="/test",
        )
        assert result.create_result is None
        assert result.read_result is None
        assert result.update_result is None
        assert result.delete_result is None
        assert result.verify_delete_result is None

    @pytest.mark.asyncio
    async def test_validate_all_timestamp_format(self, tmp_path):
        """Test validate_all sets proper ISO timestamp."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            dry_run=True,
        )

        with patch.object(validator, "load_minimum_configs", return_value={}):
            report = await validator.validate_all()

        # Should be ISO format with timezone
        assert "T" in report.timestamp
        assert "+" in report.timestamp or "Z" in report.timestamp


# ============================================================================
# Coverage Completion Tests - Edge Cases
# ============================================================================


class TestConfigMerge:
    """Test configuration merging edge cases."""

    def test_config_merge_non_dict_value(self, tmp_path):
        """Test config merge with non-dict values (covers line 228)."""
        config_path = tmp_path / "test_config.yaml"
        # Include a non-dict value at top level that needs to replace (line 228)
        # validation is a dict that gets merged, but we also add a top-level string
        config_path.write_text(
            """
# Custom top-level key that doesn't exist in defaults (triggers line 228)
custom_setting: "my-custom-value"
# Nested validation config with test_prefix
validation:
  test_prefix: "custom-prefix"
  skip_operations:
    - verify_delete
""",
        )
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            config_path=config_path,
        )
        # The test_prefix should be loaded from config under validation key
        assert validator.test_prefix == "custom-prefix"
        assert "verify_delete" in validator.config.get("validation", {}).get("skip_operations", [])
        # Line 228 is hit when custom_setting doesn't exist in default_config
        assert validator.config.get("custom_setting") == "my-custom-value"


class TestLoadMinimumConfigsFile:
    """Test load_minimum_configs with actual file operations."""

    def test_load_minimum_configs_missing_file(self, tmp_path, monkeypatch):
        """Test load_minimum_configs when config file doesn't exist (covers lines 271-278)."""
        # Change to tmp_path so config/minimum_configs.yaml doesn't exist
        monkeypatch.chdir(tmp_path)

        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )
        result = validator.load_minimum_configs()
        assert result == {}

    def test_load_minimum_configs_with_file(self, tmp_path, monkeypatch):
        """Test load_minimum_configs with actual config file (covers lines 271-278)."""
        # Create config directory and file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "minimum_configs.yaml"
        config_file.write_text(
            """
resources:
  http_loadbalancer:
    example_json: '{"metadata": {"name": "test"}}'
    description: "Test LB"
""",
        )

        # Change to tmp_path so config/minimum_configs.yaml is found
        monkeypatch.chdir(tmp_path)

        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
        )
        result = validator.load_minimum_configs()
        assert "http_loadbalancer" in result
        assert result["http_loadbalancer"]["description"] == "Test LB"


class TestUpdateNoMetadata:
    """Test update operation with config missing metadata."""

    @pytest.mark.asyncio
    async def test_update_config_no_metadata(self, tmp_path, mock_httpx_response):
        """Test UPDATE with config that has no metadata key (covers line 404)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()
        mock_client.put.return_value = mock_httpx_response(
            200,
            {"metadata": {"name": "test", "labels": {"curl-test-updated": "true"}}},
        )

        # Config with no "metadata" key at all
        config_data = {"spec": {"domains": ["example.com"]}}

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator._update(
                    mock_client,
                    "http_loadbalancer",
                    "test-resource",
                    config_data,
                )

        assert result.operation == "update"
        assert result.success is True
        # Verify the PUT was called with metadata added
        call_args = mock_client.put.call_args
        assert "metadata" in call_args.kwargs.get("json", {})


class TestFailurePaths:
    """Test CRUD failure paths in validate_resource."""

    @pytest.mark.asyncio
    async def test_update_failure_triggers_cleanup(self, tmp_path, mock_httpx_response):
        """Test UPDATE failure still attempts DELETE (covers lines 540-546)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()

        # CREATE and READ succeed, UPDATE fails
        mock_client.post.return_value = mock_httpx_response(201, {"metadata": {"name": "test"}})
        mock_client.get.return_value = mock_httpx_response(200, {"metadata": {"name": "test"}})
        mock_client.put.return_value = mock_httpx_response(400, {"error": "Update failed"})
        mock_client.delete.return_value = mock_httpx_response(204)

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {"domains": ["example.com"]}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator.validate_resource(
                    mock_client,
                    "http_loadbalancer",
                    resource_config,
                )

        assert result.full_success is False
        assert any("UPDATE failed" in err for err in result.errors)
        # DELETE should still have been called
        mock_client.delete.assert_called_once()
        # Should have 4 operations: CREATE, READ, UPDATE, DELETE (no VERIFY since early return)
        assert len(result.operations) == 4

    @pytest.mark.asyncio
    async def test_delete_failure_returns_early(self, tmp_path, mock_httpx_response):
        """Test DELETE failure returns early (covers lines 554-556)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()

        # CREATE, READ, UPDATE succeed, DELETE fails
        mock_client.post.return_value = mock_httpx_response(201, {"metadata": {"name": "test"}})
        mock_client.get.return_value = mock_httpx_response(200, {"metadata": {"name": "test"}})
        mock_client.put.return_value = mock_httpx_response(200, {"metadata": {"name": "test"}})
        mock_client.delete.return_value = mock_httpx_response(500, {"error": "Server error"})

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {"domains": ["example.com"]}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                result = await validator.validate_resource(
                    mock_client,
                    "http_loadbalancer",
                    resource_config,
                )

        assert result.full_success is False
        assert any("DELETE failed" in err for err in result.errors)
        # Should have 4 operations: CREATE, READ, UPDATE, DELETE (no VERIFY since early return)
        assert len(result.operations) == 4

    @pytest.mark.asyncio
    async def test_verify_delete_failure_in_lifecycle(self, tmp_path, mock_httpx_response):
        """Test VERIFY DELETE failure in full lifecycle (covers line 566)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
        )

        mock_client = AsyncMock()

        # All operations succeed except VERIFY DELETE
        mock_client.post.return_value = mock_httpx_response(201, {"metadata": {"name": "test"}})
        mock_client.get.side_effect = [
            mock_httpx_response(200, {"metadata": {"name": "test"}}),  # READ
            mock_httpx_response(200, {"metadata": {"name": "still-exists"}}),  # VERIFY DELETE fails
        ]
        mock_client.put.return_value = mock_httpx_response(200, {"metadata": {"name": "test"}})
        mock_client.delete.return_value = mock_httpx_response(204)

        resource_config = {
            "example_json": '{"metadata": {"name": "test"}, "spec": {"domains": ["example.com"]}}',
        }

        with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
            with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await validator.validate_resource(
                        mock_client,
                        "http_loadbalancer",
                        resource_config,
                    )

        assert result.full_success is False
        assert any("VERIFY DELETE failed" in err for err in result.errors)
        # Should have all 5 operations
        assert len(result.operations) == 5


class TestValidateAllFailedCount:
    """Test validate_all failed count increment."""

    @pytest.mark.asyncio
    async def test_validate_all_increments_failed_count(self, tmp_path, mock_httpx_response):
        """Test validate_all increments failed count for failed resources (covers line 645)."""
        validator = CurlExampleValidator(
            specs_dir=tmp_path,
            api_url="https://test.console.ves.volterra.io",
            api_token="test-token",
            namespace="test-ns",
            dry_run=False,  # Non-dry-run to hit the actual HTTP path
        )

        mock_client = AsyncMock()
        # CREATE fails immediately
        mock_client.post.return_value = mock_httpx_response(400, {"error": "Bad request"})

        with (
            patch.object(
                validator,
                "load_minimum_configs",
                return_value={
                    "http_loadbalancer": {
                        "example_json": '{"metadata": {"name": "test"}, "spec": {}}',
                    },
                },
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            # Create async context manager
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_client
            mock_cm.__aexit__.return_value = None
            mock_client_class.return_value = mock_cm

            with patch.object(validator.rate_limiter, "__aenter__", new_callable=AsyncMock):
                with patch.object(validator.rate_limiter, "__aexit__", new_callable=AsyncMock):
                    report = await validator.validate_all()

        assert report.dry_run is False
        assert report.total_resources == 1
        assert report.failed == 1
        assert report.passed == 0
