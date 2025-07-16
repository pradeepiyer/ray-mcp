"""Claude-based natural language parsing for Ray operations."""

import json
import os
from typing import Any, Dict, Optional

import anthropic


class LLMActionParser:
    """Claude-based LLM parser for Ray MCP operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307",
    ):
        """Initialize Claude parser with configuration from environment variables."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
        self.cache = {}

        # For testing, use a dummy API key if none provided
        api_key = self.api_key or "test-key"

        self.client = anthropic.AsyncAnthropic(api_key=api_key)

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
        """Parse any Ray operation using Claude."""
        # Check cache first
        if prompt in self.cache:
            return self.cache[prompt]

        parsing_prompt = self._build_parsing_prompt(prompt)

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": parsing_prompt}],
            )

            # Extract text content from Claude's response
            content = None
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    content = block.text
                    break

            if content is None:
                raise ValueError("Claude returned empty response")

            # Extract JSON from response (Claude might include extra text)
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in Claude response")

            json_content = content[json_start:json_end]
            result = json.loads(json_content)

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
        """Parse cluster action from prompt using Claude."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cluster":
            raise ValueError(f"Expected cluster action but got: {result.get('type')}")
        return result

    async def parse_job_action(self, prompt: str) -> Dict[str, Any]:
        """Parse job action from prompt using Claude."""
        result = await self.parse_action(prompt)
        if result.get("type") != "job":
            raise ValueError(f"Expected job action but got: {result.get('type')}")
        return result

    async def parse_cloud_action(self, prompt: str) -> Dict[str, Any]:
        """Parse cloud action from prompt using Claude."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cloud":
            raise ValueError(f"Expected cloud action but got: {result.get('type')}")
        return result

    async def parse_kubernetes_action(self, prompt: str) -> Dict[str, Any]:
        """Parse kubernetes action from prompt using Claude."""
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
        """Parse KubeRay job action from prompt using Claude."""
        result = await self.parse_action(prompt)
        # KubeRay job actions are job operations in kubernetes environment
        if result.get("type") == "job":
            result["environment"] = "kubernetes"
        return result

    async def parse_kuberay_cluster_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay cluster action from prompt using Claude."""
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
    """Get global Claude parser instance."""
    global _global_parser
    if _global_parser is None:
        _global_parser = LLMActionParser()
    return _global_parser
