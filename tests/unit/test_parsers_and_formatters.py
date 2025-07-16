#!/usr/bin/env python3
"""Tests for response formatting utilities.

This module tests the response formatting utilities used throughout
the Ray MCP system for consistent output formatting.

Test Focus:
- Response formatting consistency
- Serialization compatibility  
- Helper function behavior
"""

import json

import pytest

from ray_mcp.foundation.logging_utils import error_response, success_response


@pytest.mark.unit
class TestResponseHelpers:
    """Test response helper functions for consistent output formatting."""

    def test_success_response(self):
        """Test successful response formatting."""
        # Test basic success response
        result = success_response(message="Operation completed successfully")

        assert result["status"] == "success"
        assert result["message"] == "Operation completed successfully"

        # Test success response with additional data
        result = success_response(
            job_id="raysubmit_123",
            entrypoint="train.py",
            message="Job submitted successfully",
        )

        assert result["status"] == "success"
        assert result["job_id"] == "raysubmit_123"
        assert result["entrypoint"] == "train.py"
        assert result["message"] == "Job submitted successfully"

    def test_error_response(self):
        """Test error response formatting."""
        # Test basic error response
        result = error_response("Something went wrong")

        assert result["status"] == "error"
        assert result["message"] == "Something went wrong"

        # Test error response with additional data
        result = error_response(
            "Custom error message", operation="test_operation", error_code="ERR_001"
        )

        assert result["status"] == "error"
        assert result["message"] == "Custom error message"
        assert result["operation"] == "test_operation"
        assert result["error_code"] == "ERR_001"

    def test_response_format_consistency(self):
        """Test that all responses follow consistent format."""
        # Success responses should always have status and can have additional fields
        success = success_response(
            cluster_address="localhost:8265", dashboard_url="http://localhost:8265"
        )

        assert "status" in success
        assert success["status"] == "success"
        assert "cluster_address" in success
        assert "dashboard_url" in success

        # Error responses should always have status and message
        error = error_response("Test error")

        assert "status" in error
        assert error["status"] == "error"
        assert "message" in error
        assert isinstance(error["message"], str)

    def test_response_serialization(self):
        """Test that responses can be JSON serialized."""
        # Test success response serialization
        success = success_response(
            job_id="test_123", status_details={"running": True, "progress": 0.5}
        )

        # Should not raise exception
        json_str = json.dumps(success)
        assert isinstance(json_str, str)

        # Should be deserializable
        deserialized = json.loads(json_str)
        assert deserialized["status"] == "success"
        assert deserialized["job_id"] == "test_123"

        # Test error response serialization
        error = error_response("Test error with special chars: àñ™")

        json_str = json.dumps(error)
        deserialized = json.loads(json_str)
        assert deserialized["status"] == "error"

    def test_success_response_with_complex_data(self):
        """Test success response with complex nested data."""
        complex_data = {
            "cluster_info": {
                "nodes": [
                    {
                        "id": "node-1",
                        "status": "running",
                        "resources": {"cpu": 4, "memory": "8GB"},
                    },
                    {
                        "id": "node-2",
                        "status": "running",
                        "resources": {"cpu": 8, "memory": "16GB"},
                    },
                ],
                "total_resources": {"cpu": 12, "memory": "24GB"},
            },
            "jobs": ["job-1", "job-2"],
        }

        result = success_response(message="Cluster status retrieved", **complex_data)

        assert result["status"] == "success"
        assert result["message"] == "Cluster status retrieved"
        assert len(result["cluster_info"]["nodes"]) == 2
        assert result["cluster_info"]["total_resources"]["cpu"] == 12
        assert result["jobs"] == ["job-1", "job-2"]

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_error_response_with_structured_details(self):
        """Test error response with structured error details."""
        error_details = {
            "error_type": "ValidationError",
            "field_errors": {
                "cpus": "Must be a positive integer",
                "memory": "Must be specified in GB or MB",
            },
            "suggestion": "Please check your cluster configuration",
        }

        result = error_response(
            "Cluster creation failed due to validation errors", **error_details
        )

        assert result["status"] == "error"
        assert result["message"] == "Cluster creation failed due to validation errors"
        assert result["error_type"] == "ValidationError"
        assert "cpus" in result["field_errors"]
        assert "memory" in result["field_errors"]
        assert result["suggestion"] == "Please check your cluster configuration"

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_response_helpers_handle_none_values(self):
        """Test that response helpers handle None values appropriately."""
        # Test with None message
        result = success_response(message=None, operation="test")
        assert result["message"] is None
        assert result["operation"] == "test"

        # Test with None additional data
        result = error_response("Error occurred", details=None, code="E001")
        assert result["details"] is None
        assert result["code"] == "E001"

    def test_response_helpers_preserve_boolean_values(self):
        """Test that boolean values are preserved correctly."""
        result = success_response(
            message="Operation completed",
            cluster_running=True,
            dashboard_enabled=False,
            auto_scaling=True,
        )

        assert result["cluster_running"] is True
        assert result["dashboard_enabled"] is False
        assert result["auto_scaling"] is True

        # Verify these remain booleans after JSON round-trip
        json_str = json.dumps(result)
        deserialized = json.loads(json_str)
        assert deserialized["cluster_running"] is True
        assert deserialized["dashboard_enabled"] is False
        assert deserialized["auto_scaling"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
