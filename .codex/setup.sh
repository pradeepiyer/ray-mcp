#!/bin/bash
set -e
uv sync --all-extras --dev    # installs ray and pytest-asyncio
uv pip install -e . 