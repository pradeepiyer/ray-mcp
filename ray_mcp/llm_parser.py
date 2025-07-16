"""LLM-based natural language parsing for Ray operations."""

import asyncio
import json
import os
from typing import Any, Dict, Optional

from openai import AsyncOpenAI


class LLMActionParser:
    """OpenAI-compatible LLM parser for Ray MCP operations."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
    ):
        """Initialize LLM parser with configuration from environment variables."""
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.api_key = (
            api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        self.model = model or os.getenv("LLM_MODEL", "gpt-4")
        self.cache = {}

        # Initialize OpenAI client with proper configuration
        client_kwargs = {}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        # For testing, use a dummy API key if none provided
        api_key = self.api_key or "test-key"
        client_kwargs["api_key"] = api_key

        self.client = AsyncOpenAI(**client_kwargs)

    def _build_parsing_prompt(self, prompt: str) -> str:
        """Build a structured parsing prompt for consistent JSON output."""
        return f"""Parse the following Ray operation request and return a JSON object with the structured action details.

User Request: "{prompt}"

Based on the request, determine:
1. The type of operation (cluster, job, or cloud)
2. The specific operation being requested
3. Any parameters mentioned

Return JSON in this exact format:
{{
    "type": "cluster|job|cloud",
    "operation": "create|connect|status|list|scale|stop|submit|inspect|logs|cancel|authenticate|list_clusters|connect_cluster|create_cluster|check_environment|get_cluster_info",
    "name": "cluster-name or job-id or null",
    "namespace": "namespace or null", 
    "zone": "zone or null",
    "workers": "number or null",
    "script": "script-path or null",
    "environment": "kubernetes|local|auto",
    "head_only": "true|false|null",
    "cpus": "number or null",
    "gpus": "number or null",
    "dashboard_port": "number or null",
    "address": "address:port or null",
    "job_id": "job-id or null",
    "source": "source-url or null",
    "filter_errors": "true|false|null",
    "provider": "gcp|aws|azure or null",
    "project_id": "project-id or null",
    "cluster_name": "cluster-name or null",
    "context": "context or null",
    "config_file": "config-file or null",
    "runtime_env": "runtime-env-object or null",
    "head_resources": "resource-object or null",
    "worker_resources": "resource-object or null"
}}

Important parsing rules:
- For cluster status/info/inspect operations, set operation to "inspect"
- For listing operations, set operation to "list" 
- Detect "kubernetes", "k8s", "gke" keywords to set environment to "kubernetes"
- Extract numeric values for workers, cpus, gpus, dashboard_port
- Extract cluster/job names but ignore common words like "ray", "cluster", "the", "all"
- For job operations, extract job IDs and script paths
- For cloud operations, detect provider and extract zones/regions
- Set head_only to true if "head only" or "no worker" is mentioned
- Extract addresses in host:port format
- Only include non-null values in the response

Examples:
- "Create a Ray cluster named test-cluster with 3 workers" → {{"type": "cluster", "operation": "create", "name": "test-cluster", "workers": 3, "environment": "local"}}
- "Check status of Ray cluster" → {{"type": "cluster", "operation": "inspect", "environment": "local"}}
- "List jobs" → {{"type": "job", "operation": "list"}}
- "Connect to cluster at 192.168.1.1:10001" → {{"type": "cluster", "operation": "connect", "address": "192.168.1.1:10001"}}
- "Create kubernetes cluster with head only" → {{"type": "cluster", "operation": "create", "environment": "kubernetes", "head_only": true, "workers": 0}}

Parse the user request above and return only the JSON object, no additional text.
"""

    async def parse_action(self, prompt: str) -> Dict[str, Any]:
        """Parse any Ray operation using OpenAI-compatible API."""
        # Check cache first
        if prompt in self.cache:
            return self.cache[prompt]

        parsing_prompt = self._build_parsing_prompt(prompt)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": parsing_prompt}],
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned empty response")
            result = json.loads(content)

            # Clean up null values to match expected format
            cleaned_result = {
                k: v for k, v in result.items() if v is not None and v != "null"
            }

            # Cache the result
            self.cache[prompt] = cleaned_result

            return cleaned_result

        except Exception as e:
            # Fallback error response
            raise ValueError(f"Failed to parse action '{prompt}': {str(e)}")

    async def parse_cluster_action(self, prompt: str) -> Dict[str, Any]:
        """Parse cluster action from prompt using LLM."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cluster":
            raise ValueError(f"Expected cluster action but got: {result.get('type')}")
        return result

    async def parse_job_action(self, prompt: str) -> Dict[str, Any]:
        """Parse job action from prompt using LLM."""
        result = await self.parse_action(prompt)
        if result.get("type") != "job":
            raise ValueError(f"Expected job action but got: {result.get('type')}")
        return result

    async def parse_cloud_action(self, prompt: str) -> Dict[str, Any]:
        """Parse cloud action from prompt using LLM."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cloud":
            raise ValueError(f"Expected cloud action but got: {result.get('type')}")
        return result

    async def parse_kubernetes_action(self, prompt: str) -> Dict[str, Any]:
        """Parse kubernetes action from prompt using LLM."""
        # For kubernetes operations, we use a specialized prompt
        result = await self.parse_action(prompt)
        # Kubernetes actions might be parsed as cluster type with kubernetes environment
        if (
            result.get("type") not in ["cluster", "kubernetes"]
            and result.get("environment") != "kubernetes"
        ):
            # Try to infer it's a kubernetes operation
            if any(
                keyword in prompt.lower()
                for keyword in ["kubernetes", "k8s", "namespace", "context"]
            ):
                result["type"] = "kubernetes"
        return result

    async def parse_kuberay_job_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay job action from prompt using LLM."""
        result = await self.parse_action(prompt)
        # KubeRay job actions are job operations in kubernetes environment
        if result.get("type") == "job":
            result["environment"] = "kubernetes"
        return result

    async def parse_kuberay_cluster_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay cluster action from prompt using LLM."""
        result = await self.parse_action(prompt)
        # KubeRay cluster actions are cluster operations in kubernetes environment
        if result.get("type") == "cluster":
            result["environment"] = "kubernetes"
        return result

    def clear_cache(self):
        """Clear the parsing cache."""
        self.cache.clear()


# Global instance for backwards compatibility
_global_parser = None


def get_parser() -> LLMActionParser:
    """Get global LLM parser instance."""
    global _global_parser
    if _global_parser is None:
        _global_parser = LLMActionParser()
    return _global_parser
