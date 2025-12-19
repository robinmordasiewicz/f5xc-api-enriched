#!/usr/bin/env python3
"""Merge multiple OpenAPI specifications into unified documents for documentation.

Creates merged specifications organized by domain for Swagger UI and Scalar portals.
Fully automated - no manual intervention required.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


# Domain categorization patterns
DOMAIN_PATTERNS = {
    "load_balancer": [
        r"http_loadbalancer",
        r"tcp_loadbalancer",
        r"healthcheck",
        r"origin_pool",
        r"route",
    ],
    "security": [
        r"app_firewall",
        r"waf",
        r"service_policy",
        r"rate_limiter",
        r"malicious",
        r"bot_defense",
        r"api_definition",
        r"api_security",
    ],
    "networking": [
        r"network",
        r"virtual_network",
        r"site",
        r"fleet",
        r"tunnel",
        r"bgp",
        r"interface",
        r"dns",
    ],
    "infrastructure": [
        r"cloud_credentials",
        r"aws_vpc_site",
        r"azure_vnet_site",
        r"gcp_vpc_site",
        r"voltstack_site",
        r"k8s",
        r"ce_cluster",
    ],
    "identity": [
        r"namespace",
        r"user",
        r"role",
        r"service_credential",
        r"api_credential",
        r"certificate",
    ],
    "observability": [
        r"log",
        r"metric",
        r"alert",
        r"monitor",
        r"trace",
        r"dashboard",
    ],
    "config": [
        r"global_setting",
        r"tenant_setting",
        r"label",
        r"known_label",
    ],
}


def load_spec(spec_path: Path) -> dict[str, Any]:
    """Load an OpenAPI specification from JSON file."""
    with open(spec_path) as f:
        return json.load(f)


def save_spec(spec: dict[str, Any], output_path: Path, indent: int = 2) -> None:
    """Save an OpenAPI specification to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(spec, f, indent=indent, ensure_ascii=False)


def categorize_spec(filename: str) -> str:
    """Categorize a specification file by domain based on filename patterns."""
    filename_lower = filename.lower()

    for domain, patterns in DOMAIN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower):
                return domain

    return "other"


def create_base_spec(title: str, description: str, version: str) -> dict[str, Any]:
    """Create a base OpenAPI specification structure."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": description,
            "version": version,
            "contact": {
                "name": "F5 Distributed Cloud",
                "url": "https://docs.cloud.f5.com",
            },
            "license": {
                "name": "Proprietary",
                "url": "https://www.f5.com/company/policies/eula",
            },
        },
        "servers": [
            {
                "url": "https://{tenant}.console.ves.volterra.io",
                "description": "F5 Distributed Cloud Console",
                "variables": {
                    "tenant": {
                        "default": "console",
                        "description": "Your F5 XC tenant name",
                    },
                },
            },
        ],
        "security": [
            {"ApiToken": []},
        ],
        "tags": [],
        "paths": {},
        "components": {
            "securitySchemes": {
                "ApiToken": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header",
                    "description": "API Token authentication. Format: 'APIToken <your-token>'",
                },
            },
            "schemas": {},
            "responses": {},
            "parameters": {},
            "requestBodies": {},
        },
    }


def merge_components(target: dict[str, Any], source: dict[str, Any], prefix: str = "") -> dict[str, int]:
    """Merge components from source into target with conflict resolution."""
    stats = {"schemas": 0, "responses": 0, "parameters": 0, "requestBodies": 0}

    source_components = source.get("components", {})
    target_components = target.setdefault("components", {})

    # Merge schemas
    source_schemas = source_components.get("schemas", {})
    target_schemas = target_components.setdefault("schemas", {})
    for name, schema in source_schemas.items():
        prefixed_name = f"{prefix}{name}" if prefix else name
        if prefixed_name not in target_schemas:
            target_schemas[prefixed_name] = schema
            stats["schemas"] += 1

    # Merge responses
    source_responses = source_components.get("responses", {})
    target_responses = target_components.setdefault("responses", {})
    for name, response in source_responses.items():
        prefixed_name = f"{prefix}{name}" if prefix else name
        if prefixed_name not in target_responses:
            target_responses[prefixed_name] = response
            stats["responses"] += 1

    # Merge parameters
    source_params = source_components.get("parameters", {})
    target_params = target_components.setdefault("parameters", {})
    for name, param in source_params.items():
        prefixed_name = f"{prefix}{name}" if prefix else name
        if prefixed_name not in target_params:
            target_params[prefixed_name] = param
            stats["parameters"] += 1

    # Merge requestBodies (critical for Scalar/Swagger UI compatibility)
    source_request_bodies = source_components.get("requestBodies", {})
    target_request_bodies = target_components.setdefault("requestBodies", {})
    for name, request_body in source_request_bodies.items():
        prefixed_name = f"{prefix}{name}" if prefix else name
        if prefixed_name not in target_request_bodies:
            target_request_bodies[prefixed_name] = request_body
            stats["requestBodies"] += 1

    return stats


def merge_paths(target: dict[str, Any], source: dict[str, Any], source_name: str) -> int:
    """Merge paths from source into target."""
    source_paths = source.get("paths", {})
    target_paths = target.setdefault("paths", {})

    paths_added = 0
    for path, path_item in source_paths.items():
        if path not in target_paths:
            target_paths[path] = path_item
            paths_added += 1
        else:
            # Merge methods if path already exists
            for method, operation in path_item.items():
                if method not in target_paths[path]:
                    target_paths[path][method] = operation
                    paths_added += 1

    return paths_added


def extract_tags(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Extract unique tags from a specification."""
    tags = []
    seen_names = set()

    # Get explicit tags
    for tag in spec.get("tags", []):
        if tag.get("name") and tag["name"] not in seen_names:
            tags.append(tag)
            seen_names.add(tag["name"])

    # Extract tags from paths
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if isinstance(operation, dict):
                for tag_name in operation.get("tags", []):
                    if tag_name not in seen_names:
                        tags.append({"name": tag_name})
                        seen_names.add(tag_name)

    return tags


def merge_specs_by_domain(
    specs_dir: Path,
    output_dir: Path,
    version: str,
) -> dict[str, dict[str, Any]]:
    """Merge specifications grouped by domain."""
    spec_files = sorted(specs_dir.glob("*.json"))
    if not spec_files:
        console.print(f"[yellow]No specification files found in {specs_dir}[/yellow]")
        return {}

    # Group specs by domain
    domain_specs: dict[str, list[Path]] = defaultdict(list)
    for spec_file in spec_files:
        domain = categorize_spec(spec_file.name)
        domain_specs[domain].append(spec_file)

    console.print(f"[blue]Found {len(spec_files)} specs across {len(domain_specs)} domains[/blue]")

    merged_specs = {}
    stats = {"domains": 0, "specs": 0, "paths": 0, "schemas": 0, "requestBodies": 0}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Merging specifications...", total=len(domain_specs))

        for domain, domain_files in sorted(domain_specs.items()):
            domain_title = domain.replace("_", " ").title()
            merged = create_base_spec(
                title=f"F5 XC {domain_title} API",
                description=f"F5 Distributed Cloud {domain_title} API specifications",
                version=version,
            )

            all_tags = []
            for spec_file in domain_files:
                try:
                    spec = load_spec(spec_file)

                    # Merge paths
                    paths_added = merge_paths(merged, spec, spec_file.stem)
                    stats["paths"] += paths_added

                    # Merge components
                    comp_stats = merge_components(merged, spec)
                    stats["schemas"] += comp_stats["schemas"]
                    stats["requestBodies"] += comp_stats["requestBodies"]

                    # Collect tags
                    all_tags.extend(extract_tags(spec))

                    stats["specs"] += 1

                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to merge {spec_file.name}: {e}[/yellow]")

            # Deduplicate and sort tags
            seen_tag_names = set()
            unique_tags = []
            for tag in all_tags:
                if tag.get("name") and tag["name"] not in seen_tag_names:
                    unique_tags.append(tag)
                    seen_tag_names.add(tag["name"])
            merged["tags"] = sorted(unique_tags, key=lambda t: t.get("name", ""))

            # Save domain-specific merged spec
            output_path = output_dir / f"{domain}.json"
            save_spec(merged, output_path)
            merged_specs[domain] = merged
            stats["domains"] += 1

            progress.update(task, advance=1)

    # Print stats
    table = Table(title="Merge Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Domains Created", str(stats["domains"]))
    table.add_row("Specs Processed", str(stats["specs"]))
    table.add_row("Paths Merged", str(stats["paths"]))
    table.add_row("Schemas Merged", str(stats["schemas"]))
    table.add_row("RequestBodies Merged", str(stats["requestBodies"]))
    console.print(table)

    return merged_specs


def create_master_spec(
    merged_specs: dict[str, dict[str, Any]],
    output_path: Path,
    version: str,
) -> dict[str, Any]:
    """Create a master specification combining all domains."""
    master = create_base_spec(
        title="F5 Distributed Cloud API",
        description="Complete F5 Distributed Cloud API specification",
        version=version,
    )

    all_tags = []
    for domain, spec in merged_specs.items():
        # Merge paths with domain prefix in tags
        for path, path_item in spec.get("paths", {}).items():
            if path not in master["paths"]:
                master["paths"][path] = path_item

        # Merge components
        merge_components(master, spec)

        # Collect tags
        all_tags.extend(spec.get("tags", []))

    # Deduplicate tags
    seen_tag_names = set()
    unique_tags = []
    for tag in all_tags:
        if tag.get("name") and tag["name"] not in seen_tag_names:
            unique_tags.append(tag)
            seen_tag_names.add(tag["name"])
    master["tags"] = sorted(unique_tags, key=lambda t: t.get("name", ""))

    save_spec(master, output_path)

    console.print(f"[green]Created master spec with {len(master['paths'])} paths[/green]")

    return master


def create_spec_index(
    merged_specs: dict[str, dict[str, Any]],
    output_path: Path,
    version: str,
) -> None:
    """Create an index file listing all available specifications."""
    index = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "specifications": [],
    }

    for domain, spec in sorted(merged_specs.items()):
        info = spec.get("info", {})
        paths = spec.get("paths", {})

        index["specifications"].append({
            "domain": domain,
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "file": f"{domain}.json",
            "path_count": len(paths),
            "schema_count": len(spec.get("components", {}).get("schemas", {})),
        })

    with open(output_path, "w") as f:
        json.dump(index, f, indent=2)

    console.print(f"[green]Created spec index at {output_path}[/green]")


def get_version() -> str:
    """Get version from .version file or generate date-based version."""
    version_file = Path(".version")
    if version_file.exists():
        return version_file.read_text().strip()
    return datetime.now().strftime("%Y.%m.%d")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Merge F5 XC API specifications into unified documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("specs/normalized"),
        help="Directory containing normalized specifications",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("specs/merged"),
        help="Directory for merged specifications",
    )
    parser.add_argument(
        "--version",
        type=str,
        help="Version string for merged specifications",
    )
    parser.add_argument(
        "--no-master",
        action="store_true",
        help="Skip creating master combined specification",
    )

    args = parser.parse_args()

    version = args.version or get_version()

    console.print("[bold blue]F5 XC API Specification Merge[/bold blue]")
    console.print(f"  Input:   {args.input_dir}")
    console.print(f"  Output:  {args.output_dir}")
    console.print(f"  Version: {version}")

    if not args.input_dir.exists():
        console.print(f"[red]Input directory not found: {args.input_dir}[/red]")
        console.print("[yellow]Run enrichment pipeline first[/yellow]")
        return 1

    # Merge specs by domain
    merged_specs = merge_specs_by_domain(
        args.input_dir,
        args.output_dir,
        version,
    )

    if not merged_specs:
        console.print("[red]No specifications were merged[/red]")
        return 1

    # Create master spec unless disabled
    if not args.no_master:
        master_path = args.output_dir / "openapi.json"
        create_master_spec(merged_specs, master_path, version)

    # Create index file
    index_path = args.output_dir / "index.json"
    create_spec_index(merged_specs, index_path, version)

    console.print(f"\n[bold green]Successfully merged specifications![/bold green]")
    console.print(f"  Domains: {len(merged_specs)}")
    console.print(f"  Output:  {args.output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
