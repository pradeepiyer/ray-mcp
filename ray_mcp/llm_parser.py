"""OpenAI-based natural language parsing for Ray operations."""

import json
import logging
import os
from typing import Any, Dict, Optional

import openai
import yaml

logger = logging.getLogger(__name__)


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
1. The type of operation (cluster, job, or cloud)
2. The specific operation being requested
3. Any parameters mentioned
4. Runtime environment requirements (pip packages, conda, working directory, etc.)

Return JSON in this exact format:
{{
    "type": "cluster|job|cloud",
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
- For listing operations, set operation to "list" (except for cloud clusters which use "list_clusters")
- CRITICAL: List operations with cloud keywords (GKE, AWS, Azure, cloud) should be type "cloud" 
- CRITICAL: Phrases like "current project", "available clusters", "all clusters" without explicit local/kubernetes context should be type "cloud"
- For job submit operations, set operation to "create"
- For status/info/inspect operations, set operation to "get"
- For stop/delete/terminate operations, set operation to "delete"
- Detect "kubernetes", "k8s" keywords to set environment to "kubernetes"
- CRITICAL: If request mentions "authenticate", "cloud", or cloud providers (aws, azure, gcp), prioritize as cloud operation
- CRITICAL: If request mentions cloud zones/regions (like "us-west1-c", "us-east-1", "eastus2"), treat as cloud operation
- CRITICAL: For provider field, ALWAYS use standardized names: "gcp" for Google Cloud/GCP/GKE, "aws" for AWS/Amazon Cloud, "azure" for Azure/Microsoft Azure - never use full names like "Google Cloud" or "Amazon Cloud"
- CRITICAL: "List GKE clusters", "List cloud clusters", "List AWS clusters" are CLOUD operations, not cluster operations
- CRITICAL: "List available clusters", "List all clusters", "clusters in project" are CLOUD operations, not cluster operations
- Cloud cluster operations are CLOUD operations, not local cluster operations
- IMPORTANT: For connect operations with IP addresses, set environment to "local" unless explicitly mentioning kubernetes/k8s or cloud keywords
- Extract numeric values for workers, cpus, gpus, dashboard_port
- Extract cluster/job names but ignore common words like "ray", "cluster", "the", "all"
- CRITICAL: For "Connect to [cloud] cluster X" patterns, extract X as cluster_name (not name)
- For job operations, extract job IDs and script paths
- For cloud operations, detect provider and extract zones/regions
- Set head_only to true if "head only" or "no worker" is mentioned
- Extract addresses in host:port format

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
- "Create a Ray cluster named test-cluster with 3 workers" → {{"type": "cluster", "operation": "create", "name": "test-cluster", "workers": 3, "environment": "local"}}
- "Check status of Ray cluster" → {{"type": "cluster", "operation": "get", "environment": "local"}}
- "List jobs" → {{"type": "job", "operation": "list"}}
- "Connect to cluster at 192.168.1.1:10001" → {{"type": "cluster", "operation": "connect", "address": "192.168.1.1:10001", "environment": "local"}}
- "Create kubernetes cluster with head only" → {{"type": "cluster", "operation": "create", "environment": "kubernetes", "head_only": true, "workers": 0}}
- "Submit job script train.py to kubernetes" → {{"type": "job", "operation": "create", "script": "train.py", "environment": "kubernetes"}}
- "Submit job with script train.py and pip packages pandas numpy" → {{"type": "job", "operation": "create", "script": "train.py", "runtime_env": {{"pip": ["pandas", "numpy"]}}}}
- "Stop local cluster" → {{"type": "cluster", "operation": "delete", "environment": "local"}}
- "Delete kubernetes cluster" → {{"type": "cluster", "operation": "delete", "environment": "kubernetes"}}
- "Get status of job on kubernetes" → {{"type": "job", "operation": "get", "environment": "kubernetes"}}
- "Authenticate with GCP" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Authenticate with Google Cloud" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Authenticate with AWS" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Authenticate with Amazon Cloud" → {{"type": "cloud", "operation": "authenticate", "provider": "aws"}}
- "Authenticate with Azure" → {{"type": "cloud", "operation": "authenticate", "provider": "azure"}}
- "List cloud clusters" → {{"type": "cloud", "operation": "list_clusters"}}
- "List GKE clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "gcp"}}
- "List AWS clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "aws"}}
- "List all GKE clusters" → {{"type": "cloud", "operation": "list_clusters", "provider": "gcp"}}
- "List all available clusters in the current project" → {{"type": "cloud", "operation": "list_clusters"}}
- "Authenticate with Google Cloud and list Kubernetes clusters" → {{"type": "cloud", "operation": "authenticate", "provider": "gcp"}}
- "Connect to cluster my-cluster in zone us-central1-a" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "us-central1-a", "provider": "gcp"}}
- "Connect to cluster ray-cluster in us-west1-c" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "ray-cluster", "zone": "us-west1-c", "provider": "gcp"}}
- "Connect to cluster my-cluster in us-east-1" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "us-east-1", "provider": "aws"}}
- "Connect to cluster my-cluster in eastus2" → {{"type": "cloud", "operation": "connect_cluster", "cluster_name": "my-cluster", "zone": "eastus2", "provider": "azure"}}

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

    async def parse_cluster_action(self, prompt: str) -> Dict[str, Any]:
        """Parse cluster action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        if result.get("type") != "cluster":
            raise ValueError(f"Expected cluster action but got: {result.get('type')}")
        return result

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
        """Parse KubeRay job action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        # KubeRay job actions are job operations in kubernetes environment
        if result.get("type") == "job":
            result["environment"] = "kubernetes"
        return result

    async def parse_kuberay_cluster_action(self, prompt: str) -> Dict[str, Any]:
        """Parse KubeRay cluster action from prompt using OpenAI."""
        result = await self.parse_action(prompt)
        # KubeRay cluster actions are cluster operations in kubernetes environment
        if result.get("type") == "cluster":
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


class LLMYAMLGenerator(LLMActionParser):
    """Enhanced LLM parser with YAML generation and validation capabilities."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        enable_validation: bool = True,
    ):
        """Initialize YAML generator with validation support."""
        super().__init__(api_key, model)
        self.enable_validation = enable_validation
        self._validation_orchestrator = None

    def _get_validation_orchestrator(self):
        """Lazy load validation orchestrator to avoid circular imports."""
        if self._validation_orchestrator is None and self.enable_validation:
            from .kubernetes.validation_pipeline import ValidationOrchestrator

            self._validation_orchestrator = ValidationOrchestrator()
        return self._validation_orchestrator

    def _build_yaml_generation_prompt(
        self, prompt: str, resource_type: str = "auto"
    ) -> str:
        """Build a prompt for direct YAML generation."""

        # Determine resource type if auto
        prompt_lower = prompt.lower()
        if resource_type == "auto":
            if any(
                keyword in prompt_lower for keyword in ["job", "submit", "run script"]
            ):
                resource_type = "rayjob"
            else:
                resource_type = "raycluster"

        base_prompt = f"""Generate a complete Kubernetes YAML manifest for Ray based on this request:

User Request: "{prompt}"

Requirements:
1. Generate a valid Kubernetes YAML manifest
2. Use the Ray CRD format (ray.io/v1)
3. Include proper metadata with name and namespace
4. Set appropriate resource limits and requests
5. Follow Ray and Kubernetes best practices
6. Extract all requirements from the user prompt

"""

        if resource_type.lower() == "rayjob":
            base_prompt += """Generate a RayJob manifest with these components:
- apiVersion: ray.io/v1
- kind: RayJob
- metadata: name, namespace (default: default)
- spec:
  - entrypoint: the script/command to run
  - runtimeEnvYAML: pip packages, conda env, working_dir, git repo, env vars (if mentioned)
  - rayClusterSpec: embedded cluster configuration
  - shutdownAfterJobFinishes: true (recommended)
  - ttlSecondsAfterFinished: reasonable cleanup time

Example structure:
```yaml
apiVersion: ray.io/v1
kind: RayJob
metadata:
  name: my-ray-job
  namespace: default
spec:
  entrypoint: python train.py
  runtimeEnvYAML: |
    pip:
      - pandas
      - numpy
    working_dir: /workspace
  rayClusterSpec:
    rayVersion: '2.47.0'
    headGroupSpec:
      rayStartParams:
        dashboard-host: '0.0.0.0'
      template:
        spec:
          containers:
          - name: ray-head
            image: rayproject/ray:2.47.0
            resources:
              limits:
                cpu: "1"
                memory: "2Gi"
              requests:
                cpu: "1"
                memory: "2Gi"
    workerGroupSpecs:
    - replicas: 2
      minReplicas: 1
      maxReplicas: 5
      groupName: worker-group
      template:
        spec:
          containers:
          - name: ray-worker
            image: rayproject/ray:2.47.0
            resources:
              limits:
                cpu: "1"
                memory: "2Gi"
              requests:
                cpu: "1"
                memory: "2Gi"
  shutdownAfterJobFinishes: true
  ttlSecondsAfterFinished: 300
```
"""
        else:
            base_prompt += """Generate a RayCluster manifest with these components:
- apiVersion: ray.io/v1
- kind: RayCluster
- metadata: name, namespace (default: default)
- spec:
  - rayVersion: '2.47.0'
  - enableInTreeAutoscaling: true
  - headGroupSpec: head node configuration
  - workerGroupSpecs: worker nodes configuration

Include a corresponding Service manifest:
- apiVersion: v1
- kind: Service
- metadata: name (cluster-name-head-svc), namespace
- spec: ClusterIP service exposing dashboard and client ports

Example structure:
```yaml
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: my-ray-cluster
  namespace: default
spec:
  rayVersion: '2.47.0'
  enableInTreeAutoscaling: true
  headGroupSpec:
    rayStartParams:
      dashboard-host: '0.0.0.0'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.47.0
          resources:
            limits:
              cpu: "1"
              memory: "2Gi"
            requests:
              cpu: "1"
              memory: "2Gi"
          ports:
          - containerPort: 6379
            name: gcs-server
          - containerPort: 8265
            name: dashboard
          - containerPort: 10001
            name: client
  workerGroupSpecs:
  - replicas: 3
    minReplicas: 1
    maxReplicas: 10
    groupName: worker-group
    rayStartParams: {}
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.47.0
          resources:
            limits:
              cpu: "1"
              memory: "2Gi"
            requests:
              cpu: "1"
              memory: "2Gi"
---
apiVersion: v1
kind: Service
metadata:
  name: my-ray-cluster-head-svc
  namespace: default
spec:
  selector:
    ray.io/cluster: my-ray-cluster
    ray.io/node-type: head
  ports:
  - name: dashboard
    port: 8265
    targetPort: 8265
  - name: client
    port: 10001
    targetPort: 10001
  type: ClusterIP
```
"""

        base_prompt += """
Important parsing guidelines:
- Extract resource names from the prompt (avoid generic names like "ray-cluster")
- If CPU/memory/GPU requirements are mentioned, use those values
- If worker count is specified, set replicas accordingly
- If namespace is mentioned, use it instead of "default"
- For runtime environment:
  * Extract pip packages from "with pip packages X Y Z" or "install X"
  * Extract conda environment from "conda env NAME" or "with conda ENV"
  * Extract working directory from "in directory PATH" or "working dir PATH"
  * Extract git repository from "from git REPO" or "git clone REPO"
  * Extract environment variables from "with env KEY=VALUE"
- Set reasonable resource limits based on workload hints
- Use proper YAML formatting with correct indentation

Generate ONLY the YAML manifest(s), no explanations or additional text.
"""

        return base_prompt

    async def generate_validated_yaml(
        self, prompt: str, resource_type: str = "auto"
    ) -> str:
        """Generate YAML with full validation pipeline."""
        logger.debug(f"Generating validated YAML for prompt: {prompt}")

        # Generate initial YAML
        yaml_str = await self._generate_raw_yaml(prompt, resource_type)
        logger.debug("Initial YAML generated")

        # Validate with retry loop if validation is enabled
        orchestrator = self._get_validation_orchestrator()
        if orchestrator:
            logger.debug("Running validation pipeline with retry")
            result = await orchestrator.validate_with_retry(yaml_str, prompt, self)

            if result.valid:
                logger.debug("Validation passed")
                return result.corrected_yaml or yaml_str
            else:
                error_messages = [msg.message for msg in result.errors]
                raise ValueError(
                    f"Failed to generate valid YAML: {'; '.join(error_messages)}"
                )
        else:
            logger.debug("Validation disabled, returning raw YAML")
            return yaml_str

    async def _generate_raw_yaml(self, prompt: str, resource_type: str = "auto") -> str:
        """Generate raw YAML without validation."""
        # Check cache first
        cache_key = f"yaml:{resource_type}:{prompt}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        yaml_prompt = self._build_yaml_generation_prompt(prompt, resource_type)

        try:
            # Initialize client if not already done
            if self._client is None:
                self._client = openai.AsyncOpenAI(api_key=self.api_key or "test-key")

            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=2000,  # Increased for YAML generation
                temperature=0.1,  # Low temperature for consistent structure
                messages=[{"role": "user", "content": yaml_prompt}],
            )

            # Extract text content from OpenAI's response
            content = response.choices[0].message.content

            if content is None:
                raise ValueError("OpenAI returned empty response")

            # Clean up the response - remove markdown code blocks if present
            yaml_content = content.strip()
            if yaml_content.startswith("```yaml"):
                yaml_content = yaml_content[7:]
            elif yaml_content.startswith("```"):
                yaml_content = yaml_content[3:]

            if yaml_content.endswith("```"):
                yaml_content = yaml_content[:-3]

            yaml_content = yaml_content.strip()

            # Basic validation that it's valid YAML
            try:
                yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                raise ValueError(f"Generated invalid YAML: {str(e)}")

            # Cache the result
            self.cache[cache_key] = yaml_content

            return yaml_content

        except Exception as e:
            raise ValueError(f"Failed to generate YAML for prompt '{prompt}': {str(e)}")

    async def regenerate_with_feedback(
        self, original_prompt: str, feedback: str
    ) -> str:
        """Regenerate YAML based on validation feedback."""
        logger.debug("Regenerating YAML with validation feedback")

        regeneration_prompt = f"""The previous YAML generation had validation issues. Please fix them and regenerate.

{feedback}

Generate a corrected YAML manifest that addresses all the issues mentioned above.
Return ONLY the corrected YAML, no explanations.
"""

        try:
            if self._client is None:
                self._client = openai.AsyncOpenAI(api_key=self.api_key or "test-key")

            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": regeneration_prompt}],
            )

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("OpenAI returned empty response for regeneration")

            # Clean up the response
            yaml_content = content.strip()
            if yaml_content.startswith("```yaml"):
                yaml_content = yaml_content[7:]
            elif yaml_content.startswith("```"):
                yaml_content = yaml_content[3:]

            if yaml_content.endswith("```"):
                yaml_content = yaml_content[:-3]

            yaml_content = yaml_content.strip()

            # Validate it's proper YAML
            try:
                yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                raise ValueError(f"Regenerated invalid YAML: {str(e)}")

            return yaml_content

        except Exception as e:
            raise ValueError(f"Failed to regenerate YAML: {str(e)}")

    async def generate_cluster_yaml(self, prompt: str) -> str:
        """Generate RayCluster YAML manifest."""
        return await self.generate_validated_yaml(prompt, "raycluster")

    async def generate_job_yaml(self, prompt: str) -> str:
        """Generate RayJob YAML manifest."""
        return await self.generate_validated_yaml(prompt, "rayjob")


# Global YAML generator instance
_global_yaml_generator = None


def get_yaml_generator() -> LLMYAMLGenerator:
    """Get global YAML generator instance."""
    global _global_yaml_generator
    if _global_yaml_generator is None:
        _global_yaml_generator = LLMYAMLGenerator()
    return _global_yaml_generator


async def reset_global_yaml_generator():
    """Reset the global YAML generator instance - useful for testing."""
    global _global_yaml_generator
    if _global_yaml_generator is not None:
        await _global_yaml_generator.close()
    _global_yaml_generator = None
