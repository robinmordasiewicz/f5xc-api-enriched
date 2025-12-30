"""CRUD validation for curl examples against live F5 XC API.

Validates curl examples by executing actual Create, Read, Update, Delete
operations against the live API to ensure examples work as documented.
"""

from __future__ import annotations

import asyncio
import json
import logging

# Add parent to path for imports
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "discovery"))
from rate_limiter import RateLimitConfig, RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Result of a single CRUD operation."""

    operation: str  # create, read, update, delete, verify_delete
    status_code: int
    success: bool
    response_body: dict | None = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class CrudTestResult:
    """Result of CRUD lifecycle test for a single resource."""

    resource_type: str
    test_name: str
    api_path: str
    operations: list[OperationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def create_result(self) -> OperationResult | None:
        """Get CREATE operation result."""
        return next((op for op in self.operations if op.operation == "create"), None)

    @property
    def read_result(self) -> OperationResult | None:
        """Get READ operation result."""
        return next((op for op in self.operations if op.operation == "read"), None)

    @property
    def update_result(self) -> OperationResult | None:
        """Get UPDATE operation result."""
        return next((op for op in self.operations if op.operation == "update"), None)

    @property
    def delete_result(self) -> OperationResult | None:
        """Get DELETE operation result."""
        return next((op for op in self.operations if op.operation == "delete"), None)

    @property
    def verify_delete_result(self) -> OperationResult | None:
        """Get VERIFY DELETE operation result."""
        return next((op for op in self.operations if op.operation == "verify_delete"), None)

    @property
    def full_success(self) -> bool:
        """Check if all operations succeeded."""
        return all(op.success for op in self.operations)

    @property
    def partial_success(self) -> bool:
        """Check if at least CREATE succeeded."""
        create = self.create_result
        return create is not None and create.success

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "resource_type": self.resource_type,
            "test_name": self.test_name,
            "api_path": self.api_path,
            "full_success": self.full_success,
            "partial_success": self.partial_success,
            "duration_ms": round(self.duration_ms, 2),
            "operations": {
                op.operation: {
                    "status_code": op.status_code,
                    "success": op.success,
                    "error": op.error,
                    "duration_ms": round(op.duration_ms, 2),
                }
                for op in self.operations
            },
            "errors": self.errors,
        }


@dataclass
class ValidationReport:
    """Overall validation report."""

    timestamp: str = ""
    total_resources: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    results: list[CrudTestResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "summary": {
                "total_resources": self.total_resources,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "duration_seconds": round(self.duration_seconds, 2),
                "dry_run": self.dry_run,
            },
            "results": [r.to_dict() for r in self.results],
            "errors": self.errors,
        }


class CurlExampleValidator:
    """Validates curl examples by executing CRUD operations against live API.

    Performs full Create → Read → Update → Delete → Verify lifecycle
    for each configured resource type.
    """

    def __init__(
        self,
        specs_dir: Path,
        api_url: str,
        api_token: str,
        namespace: str = "default",
        dry_run: bool = False,
        config_path: Path | None = None,
    ) -> None:
        """Initialize the validator.

        Args:
            specs_dir: Directory containing enriched OpenAPI specs
            api_url: F5 XC API base URL
            api_token: API authentication token
            namespace: Namespace for test resources
            dry_run: If True, parse and validate without executing
            config_path: Path to curl_validation.yaml config
        """
        self.specs_dir = specs_dir
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.namespace = namespace
        self.dry_run = dry_run

        # Load configuration
        self.config = self._load_config(config_path)

        # Rate limiter
        rate_config = RateLimitConfig(
            requests_per_second=self.config.get("validation", {}).get("rate_limit", 2.0),
            burst_limit=5,
            retry_attempts=self.config.get("validation", {}).get("retries", 3),
        )
        self.rate_limiter = RateLimiter(rate_config)

        # Test naming
        self.test_prefix = self.config.get("validation", {}).get("test_prefix", "curl-test")

        # Results
        self.results: list[CrudTestResult] = []

    def _load_config(self, config_path: Path | None) -> dict:
        """Load configuration from YAML file."""
        default_config = {
            "validation": {
                "namespace": "default",
                "test_prefix": "curl-test",
                "timeout": 30,
                "rate_limit": 2.0,
                "retries": 3,
                "retry_delay": 2.0,
                "resources": [],
                "skip_operations": [],
            },
            "expected_status": {
                "create": [200, 201],
                "read": [200],
                "update": [200],
                "delete": [200, 202, 204],
                "verify_delete": [404],
            },
            "api_paths": {},
            "reports": {
                "output_dir": "reports",
                "base_name": "curl-validation-report",
            },
        }

        if config_path is None:
            config_path = Path("config/curl_validation.yaml")

        if config_path.exists():
            with config_path.open() as f:
                loaded = yaml.safe_load(f) or {}
                # Deep merge
                for key, value in loaded.items():
                    existing = default_config.get(key)
                    if isinstance(existing, dict) and isinstance(value, dict):
                        existing.update(value)
                    else:
                        default_config[key] = value

        return default_config

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"APIToken {self.api_token}",
            "Content-Type": "application/json",
        }

    def _generate_test_name(self) -> str:
        """Generate unique test resource name."""
        short_uuid = uuid.uuid4().hex[:8]
        return f"{self.test_prefix}-{short_uuid}"

    def _get_api_path(self, resource_type: str, include_name: bool = False, name: str = "") -> str:
        """Get API path for a resource type.

        Args:
            resource_type: e.g., 'http_loadbalancer'
            include_name: Whether to include resource name in path
            name: Resource name for individual resource operations
        """
        # Check explicit config first
        api_paths = self.config.get("api_paths", {})
        if resource_type in api_paths:
            paths = api_paths[resource_type]
            if include_name:
                path_template = paths.get("resource", "")
            else:
                path_template = paths.get("collection", "")
            return path_template.format(namespace=self.namespace, name=name)

        # Default path construction
        plural = resource_type + "s"
        base_path = f"/api/config/namespaces/{self.namespace}/{plural}"
        if include_name:
            return f"{base_path}/{name}"
        return base_path

    def load_minimum_configs(self) -> dict[str, dict]:
        """Load minimum configurations from config/minimum_configs.yaml."""
        config_path = Path("config/minimum_configs.yaml")
        if not config_path.exists():
            return {}

        with config_path.open() as f:
            config = yaml.safe_load(f) or {}

        return config.get("resources", {})

    def _parse_example_json(self, example_json: str, test_name: str) -> dict:
        """Parse example JSON and inject test name.

        Args:
            example_json: JSON string from config
            test_name: Unique test resource name
        """
        try:
            data = json.loads(example_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid example_json: {e}") from e

        # Inject test name into metadata
        if "metadata" not in data:
            data["metadata"] = {}

        data["metadata"]["name"] = test_name
        data["metadata"]["namespace"] = self.namespace

        return data

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        json_data: dict | None = None,
    ) -> tuple[int, dict | None, str | None]:
        """Execute HTTP request with rate limiting.

        Returns:
            Tuple of (status_code, response_body, error_message)
        """
        timeout = self.config.get("validation", {}).get("timeout", 30)

        async with self.rate_limiter:
            try:
                if method == "GET":
                    response = await client.get(url, timeout=timeout)
                elif method == "POST":
                    response = await client.post(url, json=json_data, timeout=timeout)
                elif method == "PUT":
                    response = await client.put(url, json=json_data, timeout=timeout)
                elif method == "DELETE":
                    response = await client.delete(url, timeout=timeout)
                else:
                    return 0, None, f"Unsupported method: {method}"

                # Try to parse response body
                try:
                    body = response.json()
                except (json.JSONDecodeError, ValueError):
                    body = None

                return response.status_code, body, None

            except httpx.TimeoutException:
                return 0, None, "Request timed out"
            except httpx.RequestError as e:
                return 0, None, str(e)
            except Exception as e:
                return 0, None, f"Unexpected error: {e}"

    async def _create(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        config_data: dict,
    ) -> OperationResult:
        """Execute CREATE (POST) operation."""
        start = time.monotonic()

        url = f"{self.api_url}{self._get_api_path(resource_type)}"
        status, body, error = await self._execute_request(client, "POST", url, config_data)

        expected = self.config.get("expected_status", {}).get("create", [200, 201])
        success = status in expected

        return OperationResult(
            operation="create",
            status_code=status,
            success=success,
            response_body=body,
            error=error or (None if success else f"Unexpected status: {status}"),
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def _read(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        name: str,
    ) -> OperationResult:
        """Execute READ (GET) operation."""
        start = time.monotonic()

        url = f"{self.api_url}{self._get_api_path(resource_type, include_name=True, name=name)}"
        status, body, error = await self._execute_request(client, "GET", url)

        expected = self.config.get("expected_status", {}).get("read", [200])
        success = status in expected

        return OperationResult(
            operation="read",
            status_code=status,
            success=success,
            response_body=body,
            error=error or (None if success else f"Unexpected status: {status}"),
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def _update(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        name: str,
        config_data: dict,
    ) -> OperationResult:
        """Execute UPDATE (PUT) operation."""
        start = time.monotonic()

        # Add update marker to config
        updated_data = config_data.copy()
        if "metadata" not in updated_data:
            updated_data["metadata"] = {}
        if "labels" not in updated_data["metadata"]:
            updated_data["metadata"]["labels"] = {}
        updated_data["metadata"]["labels"]["curl-test-updated"] = "true"

        url = f"{self.api_url}{self._get_api_path(resource_type, include_name=True, name=name)}"
        status, body, error = await self._execute_request(client, "PUT", url, updated_data)

        expected = self.config.get("expected_status", {}).get("update", [200])
        success = status in expected

        return OperationResult(
            operation="update",
            status_code=status,
            success=success,
            response_body=body,
            error=error or (None if success else f"Unexpected status: {status}"),
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def _delete(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        name: str,
    ) -> OperationResult:
        """Execute DELETE operation."""
        start = time.monotonic()

        url = f"{self.api_url}{self._get_api_path(resource_type, include_name=True, name=name)}"
        status, body, error = await self._execute_request(client, "DELETE", url)

        expected = self.config.get("expected_status", {}).get("delete", [200, 202, 204])
        success = status in expected

        return OperationResult(
            operation="delete",
            status_code=status,
            success=success,
            response_body=body,
            error=error or (None if success else f"Unexpected status: {status}"),
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def _verify_delete(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        name: str,
    ) -> OperationResult:
        """Verify resource was deleted (expect 404)."""
        start = time.monotonic()

        url = f"{self.api_url}{self._get_api_path(resource_type, include_name=True, name=name)}"
        status, body, error = await self._execute_request(client, "GET", url)

        expected = self.config.get("expected_status", {}).get("verify_delete", [404])
        success = status in expected

        return OperationResult(
            operation="verify_delete",
            status_code=status,
            success=success,
            response_body=body,
            error=error or (None if success else f"Resource still exists: status {status}"),
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def validate_resource(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        resource_config: dict,
    ) -> CrudTestResult:
        """Execute full CRUD lifecycle for a single resource.

        Args:
            client: HTTP client
            resource_type: e.g., 'http_loadbalancer'
            resource_config: Configuration from minimum_configs.yaml
        """
        start = time.monotonic()
        test_name = self._generate_test_name()
        result = CrudTestResult(
            resource_type=resource_type,
            test_name=test_name,
            api_path=self._get_api_path(resource_type),
        )

        skip_ops = self.config.get("validation", {}).get("skip_operations", [])

        # Parse example JSON
        example_json = resource_config.get("example_json", "")
        if not example_json:
            result.errors.append("No example_json in configuration")
            return result

        try:
            config_data = self._parse_example_json(example_json, test_name)
        except ValueError as e:
            result.errors.append(str(e))
            return result

        # 1. CREATE
        if "create" not in skip_ops:
            create_result = await self._create(client, resource_type, config_data)
            result.operations.append(create_result)

            if not create_result.success:
                result.errors.append(f"CREATE failed: {create_result.error}")
                result.duration_ms = (time.monotonic() - start) * 1000
                return result
        else:
            result.errors.append("CREATE skipped by configuration")
            return result

        # 2. READ
        if "read" not in skip_ops:
            read_result = await self._read(client, resource_type, test_name)
            result.operations.append(read_result)

            if not read_result.success:
                result.errors.append(f"READ failed: {read_result.error}")
                # Still try to delete
                if "delete" not in skip_ops:
                    delete_result = await self._delete(client, resource_type, test_name)
                    result.operations.append(delete_result)
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        # 3. UPDATE
        if "update" not in skip_ops:
            update_result = await self._update(client, resource_type, test_name, config_data)
            result.operations.append(update_result)

            if not update_result.success:
                result.errors.append(f"UPDATE failed: {update_result.error}")
                # Still try to delete
                if "delete" not in skip_ops:
                    delete_result = await self._delete(client, resource_type, test_name)
                    result.operations.append(delete_result)
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        # 4. DELETE
        if "delete" not in skip_ops:
            delete_result = await self._delete(client, resource_type, test_name)
            result.operations.append(delete_result)

            if not delete_result.success:
                result.errors.append(f"DELETE failed: {delete_result.error}")
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

            # 5. VERIFY DELETE
            if "verify" not in skip_ops and "verify_delete" not in skip_ops:
                # Small delay to allow deletion to propagate
                await asyncio.sleep(1.0)
                verify_result = await self._verify_delete(client, resource_type, test_name)
                result.operations.append(verify_result)

                if not verify_result.success:
                    result.errors.append(f"VERIFY DELETE failed: {verify_result.error}")

        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    async def validate_all(self, resource_filter: list[str] | None = None) -> ValidationReport:
        """Validate all configured resources with CRUD lifecycle.

        Args:
            resource_filter: Optional list of resource types to test

        Returns:
            ValidationReport with all results
        """
        report = ValidationReport(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            dry_run=self.dry_run,
        )

        start = time.monotonic()

        # Load minimum configurations
        resources = self.load_minimum_configs()
        if not resources:
            report.errors.append("No resources found in config/minimum_configs.yaml")
            return report

        # Apply filter
        config_resources = self.config.get("validation", {}).get("resources", [])
        if resource_filter:
            resources = {k: v for k, v in resources.items() if k in resource_filter}
        elif config_resources:
            resources = {k: v for k, v in resources.items() if k in config_resources}

        report.total_resources = len(resources)

        if self.dry_run:
            # Dry run - just validate configuration parsing
            for resource_type, resource_config in resources.items():
                test_name = self._generate_test_name()
                example_json = resource_config.get("example_json", "")

                result = CrudTestResult(
                    resource_type=resource_type,
                    test_name=test_name,
                    api_path=self._get_api_path(resource_type),
                )

                if not example_json:
                    result.errors.append("No example_json in configuration")
                    report.failed += 1
                else:
                    try:
                        self._parse_example_json(example_json, test_name)
                        report.passed += 1
                    except ValueError as e:
                        result.errors.append(str(e))
                        report.failed += 1

                report.results.append(result)

            report.duration_seconds = time.monotonic() - start
            return report

        # Execute actual CRUD tests
        headers = self._get_auth_headers()

        async with httpx.AsyncClient(
            headers=headers,
            verify=True,
            follow_redirects=True,
        ) as client:
            for resource_type, resource_config in resources.items():
                result = await self.validate_resource(client, resource_type, resource_config)
                report.results.append(result)

                if result.full_success:
                    report.passed += 1
                else:
                    report.failed += 1

        report.duration_seconds = time.monotonic() - start
        return report

    async def cleanup_test_resources(self) -> int:
        """Clean up any orphaned test resources with the test prefix.

        Returns:
            Number of resources cleaned up
        """
        cleaned = 0
        headers = self._get_auth_headers()

        resources = self.load_minimum_configs()

        async with httpx.AsyncClient(
            headers=headers,
            verify=True,
            follow_redirects=True,
        ) as client:
            for resource_type in resources:
                # List resources
                list_url = f"{self.api_url}{self._get_api_path(resource_type)}"
                try:
                    response = await client.get(list_url, timeout=30)
                    if response.status_code != 200:
                        continue

                    data = response.json()
                    items = data.get("items", [])

                    for item in items:
                        name = item.get("metadata", {}).get("name", "")
                        if name.startswith(self.test_prefix):
                            # Delete this test resource
                            delete_url = f"{self.api_url}{self._get_api_path(resource_type, include_name=True, name=name)}"
                            await client.delete(delete_url, timeout=30)
                            cleaned += 1

                except Exception:
                    # Continue with other resource types - cleanup is best-effort
                    logger.debug("Cleanup failed for resource type, continuing")

        return cleaned


def generate_markdown_report(report: ValidationReport, output_path: Path) -> None:
    """Generate markdown report from validation results."""
    lines = [
        "# curl Example CRUD Validation Report",
        "",
        f"**Generated**: {report.timestamp}",
        f"**Dry Run**: {'Yes' if report.dry_run else 'No'}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Resources Tested | {report.total_resources} |",
        f"| Passed | {report.passed} |",
        f"| Failed | {report.failed} |",
        f"| Skipped | {report.skipped} |",
        f"| Duration | {report.duration_seconds:.1f}s |",
        "",
        "## Results by Resource",
        "",
    ]

    for result in report.results:
        status_emoji = "✅" if result.full_success else "❌"
        lines.append(f"### {status_emoji} {result.resource_type}")
        lines.append("")
        lines.append(f"**Test Name**: `{result.test_name}`")
        lines.append(f"**API Path**: `{result.api_path}`")
        lines.append("")

        if result.operations:
            lines.append("| Operation | Status | Result |")
            lines.append("|-----------|--------|--------|")

            for op in result.operations:
                op_emoji = "✅" if op.success else "❌"
                status = str(op.status_code) if op.status_code else "-"
                lines.append(
                    f"| {op.operation.upper()} | {status} | {op_emoji} {'Pass' if op.success else 'Fail'} |",
                )

            lines.append("")

        if result.errors:
            lines.append("**Errors**:")
            lines.extend(f"- {error}" for error in result.errors)
            lines.append("")

    if report.errors:
        lines.append("## Global Errors")
        lines.append("")
        lines.extend(f"- {error}" for error in report.errors)
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def generate_json_report(report: ValidationReport, output_path: Path) -> None:
    """Generate JSON report from validation results."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report.to_dict(), f, indent=2)
        f.write("\n")
