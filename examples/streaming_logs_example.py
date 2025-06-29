#!/usr/bin/env python3
"""
Example demonstrating streaming log retrieval with memory protection.

This example shows how the new streaming approach prevents memory leaks
when retrieving large log files from Ray clusters.
"""

import asyncio
import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ray_mcp.ray_manager import RayManager


async def demonstrate_streaming_logs():
    """Demonstrate streaming log retrieval functionality."""

    print("🚀 Ray MCP Streaming Log Retrieval Demo")
    print("=" * 50)

    # Create RayManager instance
    ray_manager = RayManager()

    # Mock the initialization to avoid actual Ray initialization
    ray_manager._is_initialized = True
    ray_manager.__is_initialized = True

    # Mock the _ensure_initialized method to avoid Ray dependency
    def mock_ensure_initialized():
        pass

    ray_manager._ensure_initialized = mock_ensure_initialized

    # Create a mock job client that returns large logs
    class MockJobClient:
        def get_job_logs(self, job_id):
            # Simulate a large log file (20MB)
            large_line = "x" * 1024  # 1KB per line
            return "\n".join(
                [f"Log line {i}: {large_line}" for i in range(20000)]
            )  # ~20MB

    ray_manager._job_client = MockJobClient()

    print("\n1. Testing parameter validation:")
    print("-" * 30)

    # Test invalid parameters
    result = ray_manager._validate_log_parameters(0, 10)
    if result:
        print(f"❌ Invalid num_lines=0: {result['message']}")

    result = ray_manager._validate_log_parameters(100, 150)
    if result:
        print(f"❌ Invalid max_size_mb=150: {result['message']}")

    # Test valid parameters
    result = ray_manager._validate_log_parameters(100, 10)
    if result is None:
        print("✅ Valid parameters accepted")

    print("\n2. Testing log truncation:")
    print("-" * 30)

    # Test truncation with large logs
    large_log = "x" * (2 * 1024 * 1024)  # 2MB
    truncated = ray_manager._truncate_logs_to_size(large_log, 1)  # 1MB limit

    original_size = len(large_log.encode("utf-8")) / (1024 * 1024)
    truncated_size = len(truncated.encode("utf-8")) / (1024 * 1024)

    print(f"📊 Original log size: {original_size:.1f}MB")
    print(f"📊 Truncated log size: {truncated_size:.1f}MB")
    print(f"✅ Truncation successful: {truncated_size <= 1.0}")

    print("\n3. Testing streaming with limits:")
    print("-" * 30)

    # Test streaming with line limits
    logs = "\n".join([f"Line {i}" for i in range(1, 101)])
    streamed = ray_manager._stream_logs_with_limits(logs, max_lines=10, max_size_mb=1)

    lines = streamed.split("\n")
    print(f"📊 Original lines: 100")
    print(f"📊 Streamed lines: {len(lines)}")
    print(
        f"✅ Line limit enforced: {len(lines) == 11}"
    )  # 10 lines + truncation message

    print("\n4. Testing log retrieval with streaming:")
    print("-" * 30)

    # Test retrieving logs with size limits
    result = await ray_manager.retrieve_logs(
        identifier="test_job", log_type="job", num_lines=100, max_size_mb=5  # 5MB limit
    )

    if result["status"] == "success":
        print("✅ Log retrieval successful")
        if "warning" in result:
            print(f"⚠️  {result['warning']}")
            print(f"📊 Original size: {result['original_size_mb']:.1f}MB")

        # Check actual size
        actual_size = len(result["logs"].encode("utf-8")) / (1024 * 1024)
        print(f"📊 Actual returned size: {actual_size:.1f}MB")
        print(f"✅ Size limit respected: {actual_size <= 5.0}")
    else:
        print(f"❌ Log retrieval failed: {result['message']}")

    print("\n5. Testing paginated log retrieval:")
    print("-" * 30)

    # Test paginated retrieval
    result = await ray_manager.retrieve_logs_paginated(
        identifier="test_job", log_type="job", page=1, page_size=50, max_size_mb=5
    )

    if result["status"] == "success":
        print("✅ Paginated log retrieval successful")
        pagination = result["pagination"]
        print(f"📊 Page {pagination['current_page']} of {pagination['total_pages']}")
        print(f"📊 Lines in page: {pagination['lines_in_page']}")
        print(f"📊 Total lines: {pagination['total_lines']}")
        print(f"📊 Has next: {pagination['has_next']}")
        print(f"📊 Has previous: {pagination['has_previous']}")
    else:
        print(f"❌ Paginated log retrieval failed: {result['message']}")

    print("\n6. Memory protection demonstration:")
    print("-" * 30)

    # Demonstrate memory protection by trying to retrieve very large logs
    print("🔄 Attempting to retrieve 50MB logs with 10MB limit...")

    class VeryLargeMockJobClient:
        def get_job_logs(self, job_id):
            # Simulate a very large log file (50MB)
            large_line = "x" * 1024  # 1KB per line
            return "\n".join(
                [f"Log line {i}: {large_line}" for i in range(50000)]
            )  # ~50MB

    ray_manager._job_client = VeryLargeMockJobClient()

    result = await ray_manager.retrieve_logs(
        identifier="large_job",
        log_type="job",
        num_lines=1000,
        max_size_mb=10,  # 10MB limit
    )

    if result["status"] == "success":
        print("✅ Large log retrieval successful with memory protection")
        if "warning" in result:
            print(f"⚠️  {result['warning']}")
            print(f"📊 Original size: {result['original_size_mb']:.1f}MB")

        actual_size = len(result["logs"].encode("utf-8")) / (1024 * 1024)
        print(f"📊 Actual returned size: {actual_size:.1f}MB")
        print(f"✅ Memory protection working: {actual_size <= 10.0}")
    else:
        print(f"❌ Large log retrieval failed: {result['message']}")

    print("\n" + "=" * 50)
    print("🎉 Streaming log retrieval demo completed!")
    print("\nKey benefits demonstrated:")
    print("✅ Memory protection through size limits")
    print("✅ Line-based truncation for readability")
    print("✅ Pagination support for large logs")
    print("✅ Parameter validation")
    print("✅ Graceful handling of oversized logs")


if __name__ == "__main__":
    asyncio.run(demonstrate_streaming_logs())
