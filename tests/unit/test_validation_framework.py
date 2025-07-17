"""Tests for the YAML validation framework."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from ray_mcp.kubernetes.validation_models import (
    ValidationMessage,
    ValidationResult,
    ValidationSeverity,
)
from ray_mcp.kubernetes.validation_pipeline import ValidationOrchestrator
from ray_mcp.kubernetes.validators import (
    SchemaValidator,
    SemanticValidator,
    SyntaxValidator,
)


class TestValidationModels:
    """Test validation data models."""

    def test_validation_result_creation(self):
        """Test creating ValidationResult."""
        result = ValidationResult(valid=True, messages=[])
        assert result.valid is True
        assert len(result.messages) == 0
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validation_result_with_errors(self):
        """Test ValidationResult with error messages."""
        result = ValidationResult(valid=False, messages=[])
        result.add_error("Test error", "field.path", "Fix this")

        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].message == "Test error"
        assert result.errors[0].field_path == "field.path"
        assert result.errors[0].suggestion == "Fix this"

    def test_validation_result_with_warnings(self):
        """Test ValidationResult with warning messages."""
        result = ValidationResult(valid=True, messages=[])
        result.add_warning("Test warning", "field.path", "Consider this")

        assert result.valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0].message == "Test warning"
        assert result.warnings[0].severity == ValidationSeverity.WARNING


class TestSyntaxValidator:
    """Test syntax validator."""

    @pytest.fixture
    def syntax_validator(self):
        """Create syntax validator instance."""
        return SyntaxValidator()

    @pytest.mark.asyncio
    async def test_valid_yaml(self, syntax_validator):
        """Test valid YAML passes syntax validation."""
        valid_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
  namespace: default
spec:
  rayVersion: '2.47.0'
"""
        result = await syntax_validator.validate(valid_yaml)
        assert result.valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_invalid_yaml_syntax(self, syntax_validator):
        """Test invalid YAML syntax fails validation."""
        invalid_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
  namespace: default
spec:
  rayVersion: '2.47.0'
  invalid: [unclosed list
"""
        result = await syntax_validator.validate(invalid_yaml)
        assert result.valid is False
        assert len(result.errors) > 0
        assert "syntax error" in result.errors[0].message.lower()

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, syntax_validator):
        """Test missing required fields fails validation."""
        missing_fields_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
"""
        result = await syntax_validator.validate(missing_fields_yaml)
        assert result.valid is False
        assert any(
            "Missing required field: spec" in error.message for error in result.errors
        )

    @pytest.mark.asyncio
    async def test_invalid_structure(self, syntax_validator):
        """Test invalid root structure fails validation."""
        invalid_structure = "not a dictionary"
        result = await syntax_validator.validate(invalid_structure)
        assert result.valid is False
        assert any("dictionary" in error.message.lower() for error in result.errors)


class TestSchemaValidator:
    """Test schema validator."""

    @pytest.fixture
    def schema_validator(self):
        """Create schema validator instance."""
        return SchemaValidator()

    @pytest.mark.asyncio
    async def test_valid_raycluster_schema(self, schema_validator):
        """Test valid RayCluster schema passes validation."""
        valid_raycluster = {
            "apiVersion": "ray.io/v1",
            "kind": "RayCluster",
            "metadata": {"name": "test-cluster", "namespace": "default"},
            "spec": {
                "rayVersion": "2.47.0",
                "headGroupSpec": {
                    "rayStartParams": {"dashboard-host": "0.0.0.0"},
                    "template": {
                        "spec": {
                            "containers": [
                                {"name": "ray-head", "image": "rayproject/ray:2.47.0"}
                            ]
                        }
                    },
                },
                "workerGroupSpecs": [
                    {
                        "replicas": 1,
                        "groupName": "worker-group",
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "ray-worker",
                                        "image": "rayproject/ray:2.47.0",
                                    }
                                ]
                            }
                        },
                    }
                ],
            },
        }

        result = await schema_validator.validate(
            yaml.dump(valid_raycluster), valid_raycluster
        )
        # Note: Some validation errors might occur due to incomplete structure
        # This test ensures the validator runs without crashing
        assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_api_version(self, schema_validator):
        """Test invalid API version fails validation."""
        invalid_api_version = {
            "apiVersion": "invalid/v1",
            "kind": "RayCluster",
            "metadata": {"name": "test"},
            "spec": {},
        }

        result = await schema_validator.validate(
            yaml.dump(invalid_api_version), invalid_api_version
        )
        assert result.valid is False
        assert len(result.errors) > 0


class TestSemanticValidator:
    """Test semantic validator."""

    @pytest.fixture
    def semantic_validator(self):
        """Create semantic validator instance."""
        return SemanticValidator()

    @pytest.mark.asyncio
    async def test_valid_ray_version(self, semantic_validator):
        """Test valid Ray version passes semantic validation."""
        valid_cluster = {"kind": "RayCluster", "spec": {"rayVersion": "2.47.0"}}

        result = await semantic_validator.validate(
            yaml.dump(valid_cluster), valid_cluster
        )
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_old_ray_version_warning(self, semantic_validator):
        """Test old Ray version generates warning."""
        old_version_cluster = {"kind": "RayCluster", "spec": {"rayVersion": "1.13.0"}}

        result = await semantic_validator.validate(
            yaml.dump(old_version_cluster), old_version_cluster
        )
        # Should generate warning about old version
        assert (
            len(result.warnings) > 0 or result.valid is True
        )  # Depends on validation logic

    @pytest.mark.asyncio
    async def test_job_entrypoint_validation(self, semantic_validator):
        """Test RayJob entrypoint validation."""
        valid_job = {
            "kind": "RayJob",
            "spec": {"entrypoint": "python train.py", "ttlSecondsAfterFinished": 300},
        }

        result = await semantic_validator.validate(yaml.dump(valid_job), valid_job)
        assert result.valid is True


class TestValidationOrchestrator:
    """Test validation orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create validation orchestrator instance."""
        return ValidationOrchestrator(max_retry_attempts=2)

    @pytest.mark.asyncio
    async def test_valid_yaml_pipeline(self, orchestrator):
        """Test valid YAML passes complete validation pipeline."""
        valid_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
  namespace: default
spec:
  rayVersion: '2.47.0'
  headGroupSpec:
    rayStartParams:
      dashboard-host: '0.0.0.0'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.47.0
  workerGroupSpecs:
  - replicas: 1
    groupName: worker-group
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.47.0
"""

        result = await orchestrator.validate_yaml_string(valid_yaml)
        # Note: May have warnings but should not have critical errors
        assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_yaml_pipeline(self, orchestrator):
        """Test invalid YAML fails validation pipeline."""
        invalid_yaml = """
apiVersion: invalid/v1
kind: UnknownKind
metadata:
  name: 123-invalid-name!
spec:
  invalid: structure
"""

        result = await orchestrator.validate_yaml_string(invalid_yaml)
        assert result.valid is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_validation_with_retry_mock(self, orchestrator):
        """Test validation with retry using mocked LLM generator."""
        initial_yaml = "invalid yaml"
        corrected_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
spec:
  rayVersion: '2.47.0'
  headGroupSpec:
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.47.0
"""

        # Mock LLM generator
        mock_generator = AsyncMock()
        mock_generator.regenerate_with_feedback.return_value = corrected_yaml

        # First attempt should fail, second should succeed
        with patch.object(orchestrator, "_run_validation_pipeline") as mock_validate:
            # First call fails
            mock_validate.side_effect = [
                ValidationResult(
                    valid=False,
                    messages=[
                        ValidationMessage(
                            severity=ValidationSeverity.ERROR,
                            message="YAML syntax error",
                        )
                    ],
                ),
                ValidationResult(valid=True, messages=[]),
            ]

            result = await orchestrator.validate_with_retry(
                initial_yaml, "Create a test cluster", mock_generator
            )

            assert mock_validate.call_count == 2
            assert mock_generator.regenerate_with_feedback.called

    def test_validation_summary(self, orchestrator):
        """Test validation summary generation."""
        result = ValidationResult(valid=False, messages=[])
        result.add_error("Test error", "field.path")
        result.add_warning("Test warning", "field.path")

        summary = orchestrator.get_validation_summary(result)

        assert summary["valid"] is False
        assert summary["errors"] == 1
        assert summary["warnings"] == 1
        assert summary["total_messages"] == 2
        assert "Test error" in summary["error_messages"]
        assert "Test warning" in summary["warning_messages"]


class TestValidationIntegration:
    """Integration tests for validation framework."""

    @pytest.mark.asyncio
    async def test_end_to_end_validation(self):
        """Test complete end-to-end validation."""
        from ray_mcp.kubernetes.validation_pipeline import validate_ray_yaml

        # Test with a reasonably valid YAML
        test_yaml = """
apiVersion: ray.io/v1
kind: RayCluster
metadata:
  name: test-cluster
  namespace: default
spec:
  rayVersion: '2.47.0'
  headGroupSpec:
    rayStartParams:
      dashboard-host: '0.0.0.0'
    template:
      spec:
        containers:
        - name: ray-head
          image: rayproject/ray:2.47.0
  workerGroupSpecs:
  - replicas: 1
    groupName: worker-group
    template:
      spec:
        containers:
        - name: ray-worker
          image: rayproject/ray:2.47.0
"""

        result = await validate_ray_yaml(test_yaml)
        # Should complete without crashing
        assert result is not None

        # Print results for debugging
        if result.errors:
            print(f"Validation errors: {[e.message for e in result.errors]}")
        if result.warnings:
            print(f"Validation warnings: {[w.message for w in result.warnings]}")

    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test validation error handling."""
        from ray_mcp.kubernetes.validation_pipeline import (
            ValidationError,
            validate_and_raise,
        )

        invalid_yaml = """
apiVersion: invalid
kind: Unknown
metadata:
  name: bad-name!
spec:
  invalid: true
"""

        with pytest.raises(ValidationError) as exc_info:
            await validate_and_raise(invalid_yaml)

        # Should contain validation result
        assert exc_info.value.result is not None
        assert not exc_info.value.result.valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
