#!/usr/bin/env python3
"""Setup script for ray-mcp."""

from setuptools import setup, find_packages

# Read the contents of README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

def run_server():
    """Synchronous wrapper for the async main function"""
    import asyncio
    from ray_mcp.main import main
    asyncio.run(main())

setup(
    name="ray-mcp",
    version="0.1.0",
    author="Ray MCP Team",
    author_email="ray-mcp@example.com",
    description="MCP (Model Context Protocol) server for Ray distributed computing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pradeepiyer/ray-mcp",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ray-mcp=ray_mcp.main:run_server",
        ],
    },
    include_package_data=True,
    package_data={
        "ray_mcp": ["*.py"],
    },
) 