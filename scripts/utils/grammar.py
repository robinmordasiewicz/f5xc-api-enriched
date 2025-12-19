#!/usr/bin/env python3
"""Automated grammar improvement for API specification text fields.

Uses language-tool-python for automated grammar checking and correction.
No manual intervention required.
"""

import re
from typing import Any

try:
    import language_tool_python
    LANGUAGE_TOOL_AVAILABLE = True
except ImportError:
    LANGUAGE_TOOL_AVAILABLE = False


class GrammarImprover:
    """Improves grammar in API specification text using LanguageTool.

    Fully automated grammar correction with configurable rules.
    Falls back to basic improvements if LanguageTool is unavailable.
    """

    def __init__(
        self,
        capitalize_sentences: bool = True,
        ensure_punctuation: bool = True,
        normalize_whitespace: bool = True,
        fix_double_spaces: bool = True,
        trim_whitespace: bool = True,
        use_language_tool: bool = True,
    ):
        """Initialize grammar improver with configuration.

        Args:
            capitalize_sentences: Capitalize first letter of sentences.
            ensure_punctuation: Ensure descriptions end with proper punctuation.
            normalize_whitespace: Fix spacing issues.
            fix_double_spaces: Remove double spaces.
            trim_whitespace: Remove trailing whitespace.
            use_language_tool: Enable LanguageTool for advanced grammar checking.
        """
        self.capitalize_sentences = capitalize_sentences
        self.ensure_punctuation = ensure_punctuation
        self.normalize_whitespace = normalize_whitespace
        self.fix_double_spaces = fix_double_spaces
        self.trim_whitespace = trim_whitespace
        self.use_language_tool = use_language_tool and LANGUAGE_TOOL_AVAILABLE

        self._tool = None
        if self.use_language_tool:
            self._init_language_tool()

    def _init_language_tool(self) -> None:
        """Initialize LanguageTool instance for grammar checking."""
        try:
            # Use English language with common disabled rules
            self._tool = language_tool_python.LanguageTool(
                "en-US",
                config={
                    "cacheSize": 1000,
                    "pipelineCaching": True,
                }
            )
            # Disable rules that don't apply well to API documentation
            disabled_rules = [
                "UPPERCASE_SENTENCE_START",  # We handle this ourselves
                "WHITESPACE_RULE",  # We handle this ourselves
                "COMMA_PARENTHESIS_WHITESPACE",  # Often intentional in technical docs
                "EN_QUOTES",  # Technical docs use various quote styles
                "DASH_RULE",  # Technical docs use various dash styles
            ]
            for rule in disabled_rules:
                self._tool.disable_rules(rule)
        except Exception:
            # Fall back to basic improvements if LanguageTool fails
            self._tool = None

    def improve_text(self, text: str) -> str:
        """Apply grammar improvements to a text string.

        Args:
            text: Input text to improve.

        Returns:
            Text with improved grammar.
        """
        if not text or not isinstance(text, str):
            return text

        result = text

        # Apply basic improvements first
        if self.trim_whitespace:
            result = result.strip()

        if self.normalize_whitespace:
            result = self._normalize_whitespace(result)

        if self.fix_double_spaces:
            result = self._fix_double_spaces(result)

        if self.capitalize_sentences:
            result = self._capitalize_sentences(result)

        if self.ensure_punctuation:
            result = self._ensure_punctuation(result)

        # Apply LanguageTool corrections if available
        if self._tool is not None:
            result = self._apply_language_tool(result)

        return result

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Replace various whitespace characters with regular space
        result = re.sub(r"[\t\r\f\v]+", " ", text)
        # Normalize newlines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _fix_double_spaces(self, text: str) -> str:
        """Remove double spaces."""
        return re.sub(r" {2,}", " ", text)

    def _capitalize_sentences(self, text: str) -> str:
        """Capitalize first letter of sentences."""
        if not text:
            return text

        # Split by sentence-ending punctuation
        sentences = re.split(r"([.!?]\s+)", text)

        result_parts = []
        for i, part in enumerate(sentences):
            if i == 0 and part:
                # First part - capitalize first letter
                part = part[0].upper() + part[1:] if len(part) > 0 else part
            elif i > 0 and i % 2 == 0 and part:
                # Parts after sentence endings
                part = part[0].upper() + part[1:] if len(part) > 0 else part
            result_parts.append(part)

        return "".join(result_parts)

    def _ensure_punctuation(self, text: str) -> str:
        """Ensure text ends with proper punctuation."""
        if not text:
            return text

        # Don't add punctuation to very short texts or code-like content
        if len(text) < 10 or text.endswith(("}", "]", ")", ">", "`", '"', "'")):
            return text

        # Check if already ends with punctuation
        if text.rstrip()[-1] in ".!?:;":
            return text

        # Add period for complete sentences
        return text.rstrip() + "."

    def _apply_language_tool(self, text: str) -> str:
        """Apply LanguageTool corrections to text."""
        if self._tool is None:
            return text

        try:
            # Get correction suggestions
            matches = self._tool.check(text)

            # Apply corrections in reverse order to preserve offsets
            corrections = []
            for match in matches:
                if match.replacements:
                    corrections.append({
                        "offset": match.offset,
                        "length": match.errorLength,
                        "replacement": match.replacements[0],
                    })

            # Sort by offset descending
            corrections.sort(key=lambda x: x["offset"], reverse=True)

            # Apply corrections
            result = text
            for correction in corrections:
                start = correction["offset"]
                end = start + correction["length"]
                result = result[:start] + correction["replacement"] + result[end:]

            return result
        except Exception:
            # Return original text if correction fails
            return text

    def improve_spec(self, spec: dict[str, Any], target_fields: list[str] | None = None) -> dict[str, Any]:
        """Recursively improve grammar in an OpenAPI specification.

        Args:
            spec: OpenAPI specification dictionary.
            target_fields: List of field names to process.

        Returns:
            Specification with improved grammar in target fields.
        """
        if target_fields is None:
            target_fields = ["description", "summary", "title", "x-displayname"]

        return self._improve_recursive(spec, target_fields)

    def _improve_recursive(self, obj: Any, target_fields: list[str]) -> Any:
        """Recursively process object and improve text fields."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in target_fields and isinstance(value, str):
                    result[key] = self.improve_text(value)
                else:
                    result[key] = self._improve_recursive(value, target_fields)
            return result
        elif isinstance(obj, list):
            return [self._improve_recursive(item, target_fields) for item in obj]
        else:
            return obj

    def close(self) -> None:
        """Close LanguageTool resources."""
        if self._tool is not None:
            try:
                self._tool.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
