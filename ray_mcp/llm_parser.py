"""OpenAI-based natural language parsing for Ray operations."""

import json
import os
from typing import Any, Dict, Optional

import openai


class LLMActionParser:
    """OpenAI-based LLM parser for Ray MCP operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
    ):
        """Initialize OpenAI parser with configuration from environment variables."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.cache = {}
        self._client = None

    def _build_parsing_prompt(self, prompt: str) -> str:
        """Build a structured parsing prompt for consistent JSON output."""
        return f"""Parse the following Ray operation request and return a JSON object with the structured action details.

User Request: "{prompt}"

Based on the request, determine:
1. The type of operation (job, service, or cloud)
2. The specific operation being requested
3. Any parameters mentioned
4. Runtime environment requirements (pip packages, conda, working directory, etc.)

Return JSON in this exact format:
{{
    "type": "job|service|cloud",
    "operation": "create|connect|list|scale|delete|get|logs|cancel|authenticate|list_clusters|connect_cluster|create_cluster|check_environment|get_cluster_info|disconnect|health_check|list_namespaces|list_contexts",
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
    "runtime_env": {{"pip": ["package1", "package2"], "conda": "env-name", "working_dir": "/path", "git": {{"url": "repo-url", "branch": "main"}}, "env_vars": {{"KEY": "value"}}}} or null,
    "head_resources": "resource-object or null",
    "worker_resources": "resource-object or null"
}}

Important parsing rules:
- CRITICAL: Any cluster-related operations (create, list, connect, delete cluster) should be type "cloud"
- For cluster listing operations, set operation to "list_clusters" and type to "cloud"
- For job submit operations, set operation to "create" and type to "job"
- For service create/deploy operations, set operation to "create" and type to "service"
- CRITICAL: Service operations with keywords "service", "serve", "serving", "inference", "deploy", "model" should be type "service"
- For status/info/inspect operations, set operation to "get"
- For stop/delete/terminate operations, set operation to "delete"
- Detect "kubernetes", "k8s" keywords to set environment to "kubernetes"
- CRITICAL: If request mentions "authenticate", "cloud", or cloud providers (aws, azure, gcp), set type to "cloud"
- CRITICAL: If request mentions cloud zones/regions (like "us-west1-c", "us-east-1", "eastus2"), set type to "cloud"
- CRITICAL: For provider field, ALWAYS use standardized names: "gcp" for Google Cloud/GCP/GKE, "aws" for AWS/Amazon Cloud, "azure" for Azure/Microsoft Azure
- CRITICAL: Cluster operations like "List clusters", "Connect to cluster", "Create cluster" are CLOUD operations
- Extract numeric values for workers, cpus, gpus, dashboard_port
- Extract cluster/job names but ignore common words like "ray", "cluster", "the", "all"
- CRITICAL: For "Connect to cluster X" patterns, extract X as cluster_name (not name)
- For job operations, extract job IDs and script paths
- For cloud operations, detect provider and extract zones/regions
- Set head_only to true if "head only" or "no worker" is mentioned

**RUNTIME ENVIRONMENT PARSING:**
- Extract pip packages from phrases like "with pip packages pandas numpy", "install pandas", "requires numpy"
- Extract conda environments from phrases like "with conda env ml-env", "conda environment base"
- Extract working directory from phrases like "in directory /app", "working dir /workspace"
- Extract git repositories from phrases like "from git repo https://github.com/user/repo.git"
- Extract environment variables from phrases like "with env var MODEL_PATH=/models"
- Combine multiple runtime environment requirements into a single runtime_env object

Runtime Environment Examples:
- "submit job with script train.py and pip packages pandas numpy scikit-learn" → {{"runtime_env": {{"pip": ["pandas", "numpy", "scikit-learn"]}}}}
- "create job with conda environment ml-env and working directory /workspace" → {{"runtime_env": {{"conda": "ml-env", "working_dir": "/workspace"}}}}
- "run job from git repo https://github.com/user/ml-project.git with pip packages torch" → {{"runtime_env": {{"git": {{"url": "https://github.com/user/ml-project.git"}}, "pip": ["torch"]}}}}
- "submit job with environment variable MODEL_PATH=/models and pip package tensorflow" → {{"runtime_env": {{"env_vars": {{"MODEL_PATH": "/models"}}, "pip": ["tensorflow"]}}}}

- Only include non-null values in the response

Examples:
- "List jobs" → {{"type": "job", "operation": "list"}}
- "Submit job script train.py to kubernetes" → {{"type": "job", "operation": "create", "script": "train.py", "environment": "kubernetes"}}
- "Submit job with script train.py and pip packages pandas numpy" → {{"type": "job", "operation": "create", "script": "train.py", "runtime_env": {{"pip": ["pandas", "numpy"]}}}}
- "Get status of job on kubernetes" → {{"type": "job", "operation": "get", "environment": "kubernetes"}}
- "Authenticate with GCP" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Authenticate with Google Cloud" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Login to GCP" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Login to Google Cloud" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Login to GKE" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Connect to GCP" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Authenticate with AWS" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Authenticate with Amazon Cloud" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Login to AWS" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Login to EKS" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Connect to AWS" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Authenticate with Azure" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "Login to Azure" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "Login to AKS" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "Connect to Azure" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "List cloud clusters" → {{"type": "cloud", "operation": "list_clusters"}}
- "List GKE clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "gcp"}}
- "List EKS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "aws"}}
- "List AKS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "azure"}}
- "List AWS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "aws"}}
- "List all GKE clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "gcp"}}
- "List all EKS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "aws"}}
- "List all AKS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "azure"}}
- "List all available clusters in the current project" → {{"type": "cloud", "operation": "list_clusters"}}
- "Login to GKE and list clusters" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Login to EKS and list clusters" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Login to AKS and list clusters" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "Authenticate with Google Cloud and list Kubernetes clusters" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Connect to cluster my-cluster in zone us-central1-a" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "us-central1-a", "provider": "gcp"}}
- "Connect to cluster ray-cluster in us-west1-c" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "ray-cluster", "zone": "us-west1-c", "provider": "gcp"}}
- "Connect to cluster my-cluster in us-east-1" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "us-east-1", "provider": "aws"}}
- "Connect to EKS cluster my-cluster" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "provider": "aws"}}
- "Connect to cluster my-cluster in eastus2" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "eastus2", "provider": "azure"}}
- "Create Ray service with model serve.py" → {{"type": "service", "operation": "create", "script": "serve.py", "environment": "kubernetes"}}
- "Deploy service named image-classifier with inference model classifier.py" → {{"type": "service", "operation": "create", "name": "image-classifier", "script": "classifier.py", "environment": "kubernetes"}}
- "List all Ray services" → {{"type": "service", "operation": "list", "environment": "kubernetes"}}
- "Get status of service model-serving" → {{"type": "service", "operation": "get", "name": "model-serving", "environment": "kubernetes"}}
- "Delete service inference-api" → {{"type": "service", "operation": "delete", "name": "inference-api", "environment": "kubernetes"}}
- "Get logs for service text-analyzer" → {{"type": "service", "operation": "logs", "name": "text-analyzer", "environment": "kubernetes"}}
- "Scale service recommendation-engine to 5 replicas" → {{"type": "service", "operation": "scale", "name": "recommendation-engine", "workers": 5, "environment": "kubernetes"}}

Parse the user request above and return only the JSON object, no additional text.
"""

    async def parse_action(self, prompt: str) -> Dict[str, Any]:
        """Parse any Ray operation using OpenAI."""
        # Check cache first
        if prompt in self.cache:
            return self.cache[prompt]

        parsing_prompt = self._build_parsing_prompt(prompt)

        try:
            # Initialize client if not already done
            if self._client is None:
                self._client = openai.AsyncOpenAI(api_key=self.api_key or "test-key")

            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": parsing_prompt}],
            )

            # Extract text content from OpenAI's response
            content = response.choices[0].message.content

            if content is None:
                raise ValueError("OpenAI returned empty response")

            # Extract JSON from response (OpenAI might include extra text)
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in OpenAI response")

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

    async def parse_job_action(self, prompt: str) -> Dict[str, Any]:
        """Parse job action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        if result.get("type") != "job":
            raise ValueError(f"Expected job action but got: {result.get('type')}")
        return result

    async def parse_cloud_action(self, prompt: str) -> Dict[str, Any]:
        """Parse cloud action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cloud":
            raise ValueError(f"Expected cloud action but got: {result.get('type')}")
        return result

    async def parse_kubernetes_action(self, prompt: str) -> Dict[str, Any]:
        """Parse kubernetes action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        # For kubernetes operations, ensure environment is set to kubernetes
        if any(
            keyword in prompt.lower()
            for keyword in ["kubernetes", "k8s", "namespace", "context"]
        ):
            result["environment"] = "kubernetes"
            # If no specific type was determined, default based on operation keywords
            if result.get("type") not in ["job", "service", "cloud"]:
                if any(
                    keyword in prompt.lower()
                    for keyword in ["cluster", "authenticate", "connect"]
                ):
                    result["type"] = "cloud"
                else:
                    result["type"] = "job"  # Default for kubernetes operations
        return result

    async def parse_kuberay_job_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay job action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        # KubeRay job actions are job operations in kubernetes environment
        if result.get("type") == "job":
            result["environment"] = "kubernetes"
        return result

    async def parse_kuberay_service_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay service action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        # KubeRay service actions are service operations in kubernetes environment
        # Map from job type to service type if detected as a service operation
        if any(
            keyword in prompt.lower()
            for keyword in ["service", "serve", "serving", "inference", "model"]
        ):
            result["type"] = "service"
            result["environment"] = "kubernetes"
        elif result.get("type") == "job" and any(
            keyword in prompt.lower()
            for keyword in ["serve", "serving", "inference", "model"]
        ):
            result["type"] = "service"
            result["environment"] = "kubernetes"
        return result

    def clear_cache(self):
        """Clear the parsing cache."""
        self.cache.clear()

    async def close(self):
        """Close the OpenAI client."""
        if self._client is not None:
            await self._client.close()
            self._client = None


# Global instance for backwards compatibility
_global_parser = None


def get_parser() -> LLMActionParser:
    """Get global OpenAI parser instance."""
    global _global_parser
    if _global_parser is None:
        _global_parser = LLMActionParser()
    return _global_parser


async def reset_global_parser():
    """Reset the global parser instance - useful for testing."""
    global _global_parser
    if _global_parser is not None:
        await _global_parser.close()
    _global_parser = None
