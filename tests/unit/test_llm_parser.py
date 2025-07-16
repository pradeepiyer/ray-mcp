"""Unit tests for LLM-based parsing functionality."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from ray_mcp.llm_parser import LLMActionParser, get_parser


class TestLLMActionParser:
    """Test the LLM-based action parser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = LLMActionParser(
            base_url="http://test-url", api_key="test-key", model="gpt-4"
        )

    @pytest.mark.asyncio
    async def test_parse_cluster_create_action(self):
        """Test parsing a cluster creation request."""
        mock_response = {
            "type": "cluster",
            "operation": "create",
            "name": "test-cluster",
            "workers": 3,
            "environment": "local",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            result = await self.parser.parse_cluster_action(
                "Create a Ray cluster named test-cluster with 3 workers"
            )

            assert result["type"] == "cluster"
            assert result["operation"] == "create"
            assert result["name"] == "test-cluster"
            assert result["workers"] == 3
            assert result["environment"] == "local"

    @pytest.mark.asyncio
    async def test_parse_job_submit_action(self):
        """Test parsing a job submission request."""
        mock_response = {
            "type": "job",
            "operation": "submit",
            "script": "train.py",
            "environment": "local",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            result = await self.parser.parse_job_action(
                "Submit job with script train.py"
            )

            assert result["type"] == "job"
            assert result["operation"] == "submit"
            assert result["script"] == "train.py"

    @pytest.mark.asyncio
    async def test_parse_cloud_authenticate_action(self):
        """Test parsing a cloud authentication request."""
        mock_response = {
            "type": "cloud",
            "operation": "authenticate",
            "provider": "gcp",
            "project_id": "my-project",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            result = await self.parser.parse_cloud_action(
                "authenticate with GCP project my-project"
            )

            assert result["type"] == "cloud"
            assert result["operation"] == "authenticate"
            assert result["provider"] == "gcp"
            assert result["project_id"] == "my-project"

    @pytest.mark.asyncio
    async def test_parse_kubernetes_action(self):
        """Test parsing a kubernetes-specific action."""
        mock_response = {
            "type": "cluster",
            "operation": "inspect",
            "environment": "kubernetes",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            result = await self.parser.parse_kubernetes_action(
                "inspect kubernetes cluster"
            )

            assert result["environment"] == "kubernetes"

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test that parsing results are cached."""
        mock_response = {"type": "cluster", "operation": "list"}

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            # First call should hit the API
            result1 = await self.parser.parse_action("list clusters")

            # Second call should use cache
            result2 = await self.parser.parse_action("list clusters")

            # Should only call the API once
            assert mock_create.call_count == 1
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling when LLM call fails."""
        with patch.object(self.parser.client.chat.completions, "create") as mock_create:
            mock_create.side_effect = Exception("API Error")

            with pytest.raises(ValueError, match="Failed to parse action"):
                await self.parser.parse_action("some invalid prompt")

    def test_global_parser(self):
        """Test the global parser instance."""
        parser1 = get_parser()
        parser2 = get_parser()

        # Should return the same instance
        assert parser1 is parser2

    @pytest.mark.asyncio
    async def test_clean_null_values(self):
        """Test that null values are cleaned from response."""
        mock_response = {
            "type": "cluster",
            "operation": "create",
            "name": "test-cluster",
            "workers": None,
            "zone": "null",
            "environment": "local",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            result = await self.parser.parse_action("create cluster test-cluster")

            # Should not contain null values
            assert "workers" not in result
            assert "zone" not in result
            assert result["type"] == "cluster"
            assert result["name"] == "test-cluster"

    @pytest.mark.asyncio
    async def test_type_validation(self):
        """Test type validation for specific parsers."""
        mock_response = {
            "type": "job",  # Wrong type for cluster parser
            "operation": "submit",
        }

        with patch.object(
            self.parser.client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message = AsyncMock()
            mock_create.return_value.choices[0].message.content = json.dumps(
                mock_response
            )

            with pytest.raises(
                ValueError, match="Expected cluster action but got: job"
            ):
                await self.parser.parse_cluster_action("submit job")
