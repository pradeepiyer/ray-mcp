#!/usr/bin/env python3
"""
Enhanced Runtime Environment Examples for Ray MCP Server
Demonstrates the improved runtime_env support for KubeRay Job CRDs
"""

import asyncio
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ray_mcp.kubernetes.kuberay_job_manager import KubeRayJobManager
from ray_mcp.llm_parser import get_parser


async def demonstrate_enhanced_runtime_env():
    """Demonstrate the enhanced runtime environment features."""

    print("🚀 Enhanced Runtime Environment Examples")
    print("=" * 50)

    # Example 1: Multiple pip packages
    print("\n1. Multiple pip packages:")
    prompt1 = (
        "submit job with script train.py and pip packages pandas numpy scikit-learn"
    )
    try:
        action1 = await get_parser().parse_job_action(prompt1)
        print(f"   Prompt: {prompt1}")
        print(f"   Parsed runtime_env: {action1.get('runtime_env', {})}")
    except Exception as e:
        print(f"   Error parsing: {e}")

    # Example 2: pip packages + working directory
    print("\n2. Pip packages + working directory:")
    prompt2 = "create job with script model.py, pip packages torch transformers, and working directory /workspace"
    try:
        action2 = await get_parser().parse_job_action(prompt2)
        print(f"   Prompt: {prompt2}")
        print(f"   Parsed runtime_env: {action2.get('runtime_env', {})}")
    except Exception as e:
        print(f"   Error parsing: {e}")

    # Example 3: Conda environment
    print("\n3. Conda environment:")
    prompt3 = "submit job with conda environment ml-env and script compute.py"
    try:
        action3 = await get_parser().parse_job_action(prompt3)
        print(f"   Prompt: {prompt3}")
        print(f"   Parsed runtime_env: {action3.get('runtime_env', {})}")
    except Exception as e:
        print(f"   Error parsing: {e}")

    # Example 4: Git repository
    print("\n4. Git repository:")
    prompt4 = "run job from git repo https://github.com/user/ml-project.git with pip packages torch"
    try:
        action4 = await get_parser().parse_job_action(prompt4)
        print(f"   Prompt: {prompt4}")
        print(f"   Parsed runtime_env: {action4.get('runtime_env', {})}")
    except Exception as e:
        print(f"   Error parsing: {e}")

    # Example 5: Environment variables
    print("\n5. Environment variables:")
    prompt5 = "submit job with script inference.py, environment variable MODEL_PATH=/models, and pip package tensorflow"
    try:
        action5 = await get_parser().parse_job_action(prompt5)
        print(f"   Prompt: {prompt5}")
        print(f"   Parsed runtime_env: {action5.get('runtime_env', {})}")
    except Exception as e:
        print(f"   Error parsing: {e}")


def demonstrate_manifest_generation():
    """Demonstrate how the enhanced runtime_env gets converted to YAML."""

    print("\n\n🔧 Manifest Generation Examples")
    print("=" * 50)

    from ray_mcp.kubernetes.manifest_generator import ManifestGenerator

    # Example 1: Multiple pip packages + working directory
    print("\n1. Multiple pip packages + working directory:")
    action1 = {
        "name": "ml-training",
        "namespace": "ml-workloads",
        "script": "python train.py",
        "runtime_env": {
            "pip": ["pandas", "numpy", "scikit-learn"],
            "working_dir": "/workspace",
        },
    }

    manifest1 = ManifestGenerator.generate_ray_job_manifest("test", action1)
    print("   Generated runtimeEnvYAML:")
    # Extract just the runtime env part
    start = manifest1.find("runtimeEnvYAML:")
    end = manifest1.find("rayClusterSpec:")
    if start != -1 and end != -1:
        runtime_section = manifest1[start:end].strip()
        print(f"   {runtime_section}")

    # Example 2: Conda + environment variables
    print("\n2. Conda + environment variables:")
    action2 = {
        "name": "compute-job",
        "namespace": "default",
        "script": "python compute.py",
        "runtime_env": {
            "conda": "ml-env",
            "env_vars": {"MODEL_PATH": "/models", "CUDA_VISIBLE_DEVICES": "0,1"},
        },
    }

    manifest2 = ManifestGenerator.generate_ray_job_manifest("test", action2)
    start = manifest2.find("runtimeEnvYAML:")
    end = manifest2.find("rayClusterSpec:")
    if start != -1 and end != -1:
        runtime_section = manifest2[start:end].strip()
        print(f"   {runtime_section}")

    # Example 3: Git repository
    print("\n3. Git repository:")
    action3 = {
        "name": "git-job",
        "namespace": "default",
        "script": "python main.py",
        "runtime_env": {
            "git": {"url": "https://github.com/user/ml-project.git", "branch": "main"},
            "pip": ["torch"],
            "working_dir": "/app",
        },
    }

    manifest3 = ManifestGenerator.generate_ray_job_manifest("test", action3)
    start = manifest3.find("runtimeEnvYAML:")
    end = manifest3.find("rayClusterSpec:")
    if start != -1 and end != -1:
        runtime_section = manifest3[start:end].strip()
        print(f"   {runtime_section}")


def demonstrate_backward_compatibility():
    """Demonstrate that the enhanced system is backward compatible."""

    print("\n\n🔄 Backward Compatibility Examples")
    print("=" * 50)

    from ray_mcp.kubernetes.manifest_generator import ManifestGenerator

    # Example 1: Old single pip package (still works)
    print("\n1. Old single pip package format:")
    action1 = {
        "name": "legacy-job",
        "namespace": "default",
        "script": "python legacy.py",
        "runtime_env": {"pip": ["pandas"]},  # Single package in list
    }

    manifest1 = ManifestGenerator.generate_ray_job_manifest("test", action1)
    start = manifest1.find("runtimeEnvYAML:")
    end = manifest1.find("rayClusterSpec:")
    if start != -1 and end != -1:
        runtime_section = manifest1[start:end].strip()
        print(f"   {runtime_section}")

    # Example 2: Old working directory only (still works)
    print("\n2. Old working directory only:")
    action2 = {
        "name": "legacy-job-2",
        "namespace": "default",
        "script": "python legacy.py",
        "runtime_env": {"working_dir": "/app"},
    }

    manifest2 = ManifestGenerator.generate_ray_job_manifest("test", action2)
    start = manifest2.find("runtimeEnvYAML:")
    end = manifest2.find("rayClusterSpec:")
    if start != -1 and end != -1:
        runtime_section = manifest2[start:end].strip()
        print(f"   {runtime_section}")


async def main():
    """Main demonstration function."""
    await demonstrate_enhanced_runtime_env()
    demonstrate_manifest_generation()
    demonstrate_backward_compatibility()

    print("\n\n✅ Enhanced Runtime Environment Features Summary:")
    print("  - Multiple pip packages support")
    print("  - Conda environment support")
    print("  - Git repository integration")
    print("  - Environment variables support")
    print("  - Combined runtime environments (pip + working_dir + conda)")
    print("  - Backward compatibility maintained")
    print("  - Improved LLM parsing for natural language prompts")


if __name__ == "__main__":
    asyncio.run(main())
