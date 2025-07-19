"""Compatibility layer for ActionParser - redirects to LLM-based parsing."""

import asyncio
from typing import Any

from .llm_parser import get_parser


class ActionParser:
    """Compatibility layer for legacy ActionParser interface."""

    @classmethod
    def parse_cluster_action(cls, prompt: str) -> dict[str, Any]:
        """Parse cluster action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_cluster_action(prompt))

    @classmethod
    def parse_job_action(cls, prompt: str) -> dict[str, Any]:
        """Parse job action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_job_action(prompt))

    @classmethod
    def parse_cloud_action(cls, prompt: str) -> dict[str, Any]:
        """Parse cloud action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_cloud_action(prompt))

    @classmethod
    def parse_kubernetes_action(cls, prompt: str) -> dict[str, Any]:
        """Parse kubernetes action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_kubernetes_action(prompt))

    @classmethod
    def parse_kuberay_job_action(cls, prompt: str) -> dict[str, Any]:
        """Parse KubeRay job action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_kuberay_job_action(prompt))

    @classmethod
    def parse_kuberay_cluster_action(cls, prompt: str) -> dict[str, Any]:
        """Parse KubeRay cluster action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_kuberay_cluster_action(prompt))

    @classmethod
    def parse_kuberay_service_action(cls, prompt: str) -> dict[str, Any]:
        """Parse KubeRay service action from prompt - compatibility wrapper."""
        return asyncio.run(get_parser().parse_kuberay_service_action(prompt))
