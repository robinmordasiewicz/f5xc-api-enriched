#!/usr/bin/env python3
"""Download and extract F5 XC API specifications from the official source."""

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import requests
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Default configuration
DEFAULT_CONFIG = {
    "source": {
        "url": "https://docs.cloud.f5.com/docs-v2/downloads/f5-distributed-cloud-open-api.zip",
        "etag_file": ".etag",
        "version_file": ".version",
    },
    "paths": {
        "original": "specs/original",
    },
}


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from YAML file or use defaults."""
    if config_path and config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            # Merge with defaults
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subvalue
            return config
    return DEFAULT_CONFIG


def get_remote_etag(url: str, timeout: int = 30) -> str | None:
    """Get the ETag header from the remote URL."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.headers.get("ETag", "").strip('"').strip("W/").strip('"')
    except requests.RequestException as e:
        console.print(f"[yellow]Warning: Could not fetch ETag: {e}[/yellow]")
        return None


def get_local_etag(etag_file: Path) -> str | None:
    """Read the stored ETag from local file."""
    if etag_file.exists():
        return etag_file.read_text().strip()
    return None


def save_etag(etag: str, etag_file: Path) -> None:
    """Save ETag to local file."""
    etag_file.parent.mkdir(parents=True, exist_ok=True)
    etag_file.write_text(etag)


def get_version() -> str:
    """Generate version string based on current date."""
    return datetime.now().strftime("%Y.%m.%d")


def save_version(version: str, version_file: Path) -> None:
    """Save version to local file."""
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(version)


def download_zip(url: str, output_path: Path, timeout: int = 300) -> bool:
    """Download ZIP file from URL with progress indication."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Downloading API specifications...", total=None)

            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        progress.update(
                            task,
                            description=f"Downloading... {downloaded / 1024 / 1024:.1f} MB",
                        )

            progress.update(task, description="Download complete!")

        console.print(f"[green]Downloaded to {output_path}[/green]")
        return True

    except requests.RequestException as e:
        console.print(f"[red]Error downloading: {e}[/red]")
        return False


def extract_zip(zip_path: Path, output_dir: Path) -> list[str]:
    """Extract ZIP file to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear existing files
    for existing_file in output_dir.glob("*.json"):
        existing_file.unlink()

    extracted_files = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting specifications...", total=None)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith(".json"):
                    # Extract directly to output dir (flatten structure)
                    filename = os.path.basename(member)
                    target_path = output_dir / filename

                    with zf.open(member) as source, open(target_path, "wb") as target:
                        target.write(source.read())

                    extracted_files.append(filename)

            progress.update(
                task, description=f"Extracted {len(extracted_files)} specification files"
            )

    console.print(f"[green]Extracted {len(extracted_files)} files to {output_dir}[/green]")
    return extracted_files


def generate_manifest(output_dir: Path, files: list[str], version: str, etag: str) -> None:
    """Generate manifest file with metadata about extracted specs."""
    manifest = {
        "version": version,
        "etag": etag,
        "timestamp": datetime.now().isoformat(),
        "file_count": len(files),
        "files": sorted(files),
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    console.print(f"[green]Generated manifest: {manifest_path}[/green]")


def check_for_updates(config: dict) -> tuple[bool, str | None]:
    """Check if there are updates available."""
    url = config["source"]["url"]
    etag_file = Path(config["source"]["etag_file"])

    remote_etag = get_remote_etag(url)
    if not remote_etag:
        console.print("[yellow]Could not determine remote version[/yellow]")
        return True, None  # Assume update needed if we can't check

    local_etag = get_local_etag(etag_file)

    if local_etag == remote_etag:
        console.print(f"[blue]No updates available (ETag: {remote_etag[:20]}...)[/blue]")
        return False, remote_etag

    if local_etag:
        console.print(f"[green]Update available![/green]")
        console.print(f"  Local ETag:  {local_etag[:30]}...")
        console.print(f"  Remote ETag: {remote_etag[:30]}...")
    else:
        console.print("[green]First download - no local version found[/green]")

    return True, remote_etag


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download F5 XC API specifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/enrichment.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for updates, don't download",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force download even if no updates detected",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override output directory for extracted specs",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Determine output directory
    output_dir = args.output_dir or Path(config["paths"]["original"])

    # Check for updates
    has_updates, remote_etag = check_for_updates(config)

    # Set GitHub Actions output if running in CI
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"updated={'true' if has_updates or args.force else 'false'}\n")
            if remote_etag:
                f.write(f"etag={remote_etag}\n")

    if args.check_only:
        return 0 if not has_updates else 1

    if not has_updates and not args.force:
        console.print("[blue]No updates needed. Use --force to download anyway.[/blue]")
        return 0

    # Download
    url = config["source"]["url"]
    temp_zip = Path("/tmp/f5xc-api-specs.zip")

    if not download_zip(url, temp_zip):
        return 1

    # Extract
    extracted_files = extract_zip(temp_zip, output_dir)

    if not extracted_files:
        console.print("[red]No files were extracted![/red]")
        return 1

    # Save version and ETag
    version = get_version()
    etag_file = Path(config["source"]["etag_file"])
    version_file = Path(config["source"]["version_file"])

    if remote_etag:
        save_etag(remote_etag, etag_file)

    save_version(version, version_file)

    # Generate manifest
    generate_manifest(output_dir, extracted_files, version, remote_etag or "unknown")

    # Cleanup
    temp_zip.unlink(missing_ok=True)

    console.print(f"\n[bold green]Successfully downloaded {len(extracted_files)} specs![/bold green]")
    console.print(f"  Version: {version}")
    console.print(f"  Output:  {output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
