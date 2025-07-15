"""Base execute request mixin to eliminate duplicated patterns."""

from typing import Any, Callable

from .logging_utils import error_response


class BaseExecuteRequestMixin:
    """Mixin to consolidate duplicated execute_request patterns."""

    def get_action_parser(self):
        """Get the action parser for this manager."""
        raise NotImplementedError("Subclasses must implement get_action_parser")

    def get_operation_handlers(self) -> dict[str, Callable]:
        """Get mapping of operation names to handler methods."""
        raise NotImplementedError("Subclasses must implement get_operation_handlers")

    async def execute_request(self, prompt: str) -> dict[str, Any]:
        """Execute operations using natural language prompts."""
        try:
            action = self.get_action_parser()(prompt)
            operation = action["operation"]

            handlers = self.get_operation_handlers()
            if operation in handlers:
                return await handlers[operation](action)
            else:
                return error_response(f"Unknown operation: {operation}")

        except ValueError as e:
            return error_response(f"Could not parse request: {str(e)}")
        except Exception as e:
            # Fall back to simple error response if _handle_error is not available
            handle_error = getattr(self, "_handle_error", None)
            if handle_error:
                return handle_error("execute_request", e)
            else:
                return error_response(f"Failed to execute_request: {str(e)}")
