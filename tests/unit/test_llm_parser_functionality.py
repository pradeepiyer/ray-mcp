"""Test LLM parser functionality - simplified for 3-tool interface."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from ray_mcp.llm_parser import LLMActionParser, get_parser, reset_global_parser


@pytest.mark.unit
class TestLLMParserConfiguration:
    """Test LLM parser configuration and initialization."""

    def test_parser_initialization_with_defaults(self):
        """Test parser initializes with default configuration."""
        parser = LLMActionParser()
        assert parser.model == "gpt-3.5-turbo"
        assert parser.cache == {}

    def test_parser_initialization_with_custom_config(self):
        """Test parser initializes with custom configuration."""
        parser = LLMActionParser(model="gpt-4", api_key="test-key")
        assert parser.model == "gpt-4"

    def test_global_parser_singleton(self):
        """Test global parser maintains singleton behavior."""
        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2


@pytest.mark.unit
class TestCacheBehavior:
    """Test caching behavior."""

    def test_cache_initialization(self):
        """Test cache initializes empty."""
        parser = LLMActionParser()
        assert parser.cache == {}

    def test_cache_clear_functionality(self):
        """Test cache can be cleared."""
        parser = LLMActionParser()
        parser.cache["test"] = {"type": "job"}
        parser.clear_cache()
        assert parser.cache == {}


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_type_validation_in_specialized_methods(self):
        """Test type validation in specialized parsing methods."""
        parser = LLMActionParser()

        # Mock parse_action to return wrong type
        with patch.object(parser, "parse_action") as mock_parse:
            mock_parse.return_value = {"type": "cloud", "operation": "list"}

            # Should raise ValueError for wrong type
            with pytest.raises(ValueError, match="Expected job action"):
                await parser.parse_job_action("test prompt")




@pytest.fixture(autouse=True)
async def cleanup_parser():
    """Clean up global parser after each test."""
    yield
    await reset_global_parser()
