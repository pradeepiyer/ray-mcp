"""Validation orchestrator with LLM feedback loop."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import yaml

from .validation_models import ValidationMessage, ValidationResult, ValidationSeverity
from .validators import (
    CorrectiveValidator,
    KubernetesValidator,
    SchemaValidator,
    SecurityValidator,
    SemanticValidator,
    SyntaxValidator,
)

logger = logging.getLogger(__name__)


class ValidationOrchestrator:
    """Orchestrates validation layers with LLM feedback loop."""

    def __init__(self, max_retry_attempts: int = 3):
        self.max_retry_attempts = max_retry_attempts

        # Initialize validators in order of execution
        self.validators = [
            ("syntax", SyntaxValidator()),
            ("schema", SchemaValidator()),
            ("kubernetes", KubernetesValidator()),
            ("semantic", SemanticValidator()),
            ("security", SecurityValidator()),
            ("corrective", CorrectiveValidator()),
        ]

    async def validate_with_retry(
        self,
        yaml_str: str,
        original_prompt: str,
        llm_generator: Optional["LLMYAMLGenerator"] = None,
    ) -> ValidationResult:
        """
        Validate YAML with retry loop using LLM feedback.

        Args:
            yaml_str: The YAML string to validate
            original_prompt: The original user prompt for context
            llm_generator: Optional LLM generator for re-generation on failures

        Returns:
            ValidationResult with final validation status
        """
        current_yaml = yaml_str

        for attempt in range(self.max_retry_attempts):
            logger.debug(f"Validation attempt {attempt + 1}/{self.max_retry_attempts}")

            # Run the complete validation pipeline
            result = await self._run_validation_pipeline(current_yaml)

            # If validation passed, return success
            if result.valid:
                logger.debug("Validation passed successfully")
                return result

            # If we have a corrected version from corrective validator, use it
            if result.corrected_yaml:
                logger.debug("Using auto-corrected YAML for next attempt")
                current_yaml = result.corrected_yaml
                continue

            # If we have an LLM generator and this isn't the last attempt, try regeneration
            if llm_generator and attempt < self.max_retry_attempts - 1:
                logger.debug("Attempting LLM-based regeneration")
                try:
                    feedback = self._generate_llm_feedback(result, original_prompt)
                    current_yaml = await llm_generator.regenerate_with_feedback(
                        original_prompt, feedback
                    )
                    logger.debug("LLM regeneration completed")
                except Exception as e:
                    logger.warning(f"LLM regeneration failed: {e}")
                    # Continue with current YAML if regeneration fails
            else:
                # No more attempts or no LLM generator, return the failed result
                logger.debug("No more validation attempts available")
                break

        return result

    async def _run_validation_pipeline(self, yaml_str: str) -> ValidationResult:
        """Run the complete validation pipeline on the YAML."""
        logger.debug("Starting validation pipeline")

        # Create final result to accumulate all messages
        final_result = ValidationResult(valid=True, messages=[])
        parsed_yaml = None

        # Run validators in sequence
        for validator_name, validator in self.validators:
            logger.debug(f"Running {validator_name} validator")

            try:
                # Pass parsed YAML to avoid re-parsing in each validator
                result = await validator.validate(yaml_str, parsed_yaml)

                # Parse YAML once after syntax validation for subsequent validators
                if validator_name == "syntax" and result.valid and parsed_yaml is None:
                    try:
                        parsed_yaml = yaml.safe_load(yaml_str)
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse YAML after syntax validation: {e}"
                        )

                # Accumulate messages
                final_result.messages.extend(result.messages)

                # If this validator found errors, mark overall result as invalid
                if not result.valid:
                    final_result.valid = False

                # Use corrected YAML if available (typically from corrective validator)
                if result.corrected_yaml:
                    final_result.corrected_yaml = result.corrected_yaml
                    # Update current YAML for subsequent validators
                    yaml_str = result.corrected_yaml
                    parsed_yaml = yaml.safe_load(yaml_str)

                # Stop early if syntax validation fails
                if validator_name == "syntax" and not result.valid:
                    logger.debug("Stopping pipeline due to syntax validation failure")
                    break

            except Exception as e:
                logger.error(f"Error in {validator_name} validator: {e}")
                final_result.add_error(
                    f"Validator {validator_name} failed: {str(e)}",
                    suggestion=f"Check the YAML format for {validator_name} requirements",
                )

        # Final validation summary
        error_count = len(final_result.errors)
        warning_count = len(final_result.warnings)

        logger.debug(
            f"Validation pipeline completed: {error_count} errors, {warning_count} warnings"
        )

        return final_result

    def _generate_llm_feedback(
        self, result: ValidationResult, original_prompt: str
    ) -> str:
        """Generate structured feedback for LLM regeneration."""
        feedback_parts = []

        # Add context
        feedback_parts.append(f"Original user request: {original_prompt}")
        feedback_parts.append(
            "\nThe generated YAML has validation issues that need to be fixed:"
        )

        # Group messages by severity
        errors = result.errors
        warnings = result.warnings

        if errors:
            feedback_parts.append(f"\nCRITICAL ERRORS ({len(errors)}):")
            for i, error in enumerate(errors, 1):
                feedback_parts.append(f"{i}. {error.message}")
                if error.field_path:
                    feedback_parts.append(f"   Field: {error.field_path}")
                if error.suggestion:
                    feedback_parts.append(f"   Fix: {error.suggestion}")
                feedback_parts.append("")

        if warnings:
            feedback_parts.append(f"\nWARNINGS ({len(warnings)}):")
            for i, warning in enumerate(warnings, 1):
                feedback_parts.append(f"{i}. {warning.message}")
                if warning.field_path:
                    feedback_parts.append(f"   Field: {warning.field_path}")
                if warning.suggestion:
                    feedback_parts.append(f"   Improvement: {warning.suggestion}")
                feedback_parts.append("")

        # Add specific instructions for regeneration
        feedback_parts.extend(
            [
                "\nPlease regenerate the YAML addressing these issues:",
                "1. Fix all CRITICAL ERRORS - these must be resolved",
                "2. Address warnings where possible to improve quality",
                "3. Maintain the original intent from the user request",
                "4. Ensure proper YAML syntax and structure",
                "5. Follow Kubernetes and Ray best practices",
                "\nGenerate only the corrected YAML, no explanations.",
            ]
        )

        return "\n".join(feedback_parts)

    async def validate_yaml_string(self, yaml_str: str) -> ValidationResult:
        """Simple validation without retry loop - useful for testing."""
        return await self._run_validation_pipeline(yaml_str)

    def get_validator_by_name(self, name: str):
        """Get a specific validator by name for testing."""
        for validator_name, validator in self.validators:
            if validator_name == name:
                return validator
        raise ValueError(f"Validator '{name}' not found")

    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """Get a summary of validation results for logging/reporting."""
        return {
            "valid": result.valid,
            "total_messages": len(result.messages),
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "has_corrections": result.corrected_yaml is not None,
            "error_messages": [msg.message for msg in result.errors],
            "warning_messages": [msg.message for msg in result.warnings],
        }


class ValidationError(Exception):
    """Exception raised when validation fails."""

    def __init__(self, result: ValidationResult):
        self.result = result
        error_messages = [msg.message for msg in result.errors]
        super().__init__(
            f"Validation failed with {len(error_messages)} errors: {'; '.join(error_messages)}"
        )


# Convenience functions for direct usage
async def validate_ray_yaml(
    yaml_str: str,
    original_prompt: Optional[str] = None,
    llm_generator: Optional["LLMYAMLGenerator"] = None,
) -> ValidationResult:
    """
    Validate Ray YAML with full pipeline.

    Args:
        yaml_str: The YAML string to validate
        original_prompt: Optional original prompt for LLM feedback
        llm_generator: Optional LLM generator for retry with feedback

    Returns:
        ValidationResult with validation status and messages
    """
    orchestrator = ValidationOrchestrator()

    if llm_generator and original_prompt:
        return await orchestrator.validate_with_retry(
            yaml_str, original_prompt, llm_generator
        )
    else:
        return await orchestrator.validate_yaml_string(yaml_str)


async def validate_and_raise(
    yaml_str: str,
    original_prompt: Optional[str] = None,
    llm_generator: Optional["LLMYAMLGenerator"] = None,
) -> str:
    """
    Validate Ray YAML and raise ValidationError if invalid.

    Returns:
        The corrected YAML string if corrections were applied, otherwise original YAML

    Raises:
        ValidationError: If validation fails
    """
    result = await validate_ray_yaml(yaml_str, original_prompt, llm_generator)

    if not result.valid:
        raise ValidationError(result)

    return result.corrected_yaml or yaml_str


# Type alias for forward reference
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm_parser import LLMYAMLGenerator
