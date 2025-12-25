"""Tests for base reporter class."""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

from report_base import BaseReporter


class ConcreteReporter(BaseReporter):
    """Concrete implementation of BaseReporter for testing."""

    def __init__(self, title: str = "Test Report", description: str = "Test"):
        super().__init__(title, description)
        self.data = {"key": "value"}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "generated_at": self.generated_at,
            "data": self.data,
        }

    def to_markdown(self) -> str:
        """Convert to markdown."""
        md = self.markdown_report_header()
        md += "## Summary\n\n"
        md += "This is a test report.\n\n"
        return md


@pytest.fixture
def reporter():
    """Create a test reporter instance."""
    return ConcreteReporter(title="Test Report", description="A test report")


@pytest.fixture
def temp_dir():
    """Create temporary directory for file output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_reporter_initialization(reporter):
    """Test reporter initialization."""
    assert reporter.title == "Test Report"
    assert reporter.description == "A test report"
    assert reporter.generated_at is not None


def test_reporter_to_dict(reporter):
    """Test converting reporter to dictionary."""
    result = reporter.to_dict()

    assert isinstance(result, dict)
    assert result["title"] == "Test Report"
    assert result["data"]["key"] == "value"


def test_reporter_to_markdown(reporter):
    """Test converting reporter to markdown."""
    md = reporter.to_markdown()

    assert isinstance(md, str)
    assert "Test Report" in md
    assert "A test report" in md
    assert "## Summary" in md


def test_reporter_markdown_table():
    """Test markdown table generation."""
    headers = ["Name", "Value", "Description"]
    rows = [
        ["Row1", "Value1", "Desc1"],
        ["Row2", "Value2", "Desc2"],
    ]

    table = BaseReporter.markdown_table(headers, rows)

    assert "| Name | Value | Description |" in table
    assert "| Row1 | Value1 | Desc1 |" in table
    assert "| Row2 | Value2 | Desc2 |" in table
    assert "| --- | --- | --- |" in table


def test_reporter_markdown_section():
    """Test markdown section generation."""
    section = BaseReporter.markdown_section(
        "Test Section",
        "Test content",
        level=2,
    )

    assert "## Test Section" in section
    assert "Test content" in section


def test_reporter_markdown_section_different_levels():
    """Test markdown section with different heading levels."""
    section2 = BaseReporter.markdown_section("Title", "Content", level=2)
    section3 = BaseReporter.markdown_section("Title", "Content", level=3)

    assert "## Title" in section2
    assert "### Title" in section3


def test_reporter_markdown_metadata_section():
    """Test metadata section generation."""
    metadata = {"Version": "1.0.0", "Author": "Test", "Date": "2024-01-01"}

    section = BaseReporter.markdown_metadata_section(metadata)

    assert "Metadata" in section
    assert "**Version**: 1.0.0" in section
    assert "**Author**: Test" in section
    assert "**Date**: 2024-01-01" in section


def test_reporter_generate_markdown(reporter, temp_dir):
    """Test generating markdown report file."""
    output_path = temp_dir / "test_report.md"

    reporter.generate_markdown(output_path)

    assert output_path.exists()
    content = output_path.read_text()
    assert "Test Report" in content


def test_reporter_generate_json(reporter, temp_dir):
    """Test generating JSON report file."""
    output_path = temp_dir / "test_report.json"

    reporter.generate_json(output_path)

    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert data["title"] == "Test Report"


def test_reporter_generate_all(reporter, temp_dir):
    """Test generating both markdown and JSON reports."""
    md_path = temp_dir / "test.md"
    json_path = temp_dir / "test.json"

    reporter.generate_all(md_path, json_path)

    assert md_path.exists()
    assert json_path.exists()


def test_reporter_markdown_report_header(reporter):
    """Test report header generation."""
    header = reporter.markdown_report_header()

    assert "# Test Report" in header
    assert "A test report" in header
    assert "**Generated**:" in header
