"""Log processing strategy for Ray MCP server."""

from typing import Any, Dict, Optional


class LogProcessorStrategy:
    """Strategy pattern for processing logs from different sources (local Ray, KubeRay)."""

    @staticmethod
    async def process_kuberay_logs(
        kuberay_result: Dict[str, Any],
        raw_logs: str,
        identifier: str,
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Process KubeRay logs with pagination and filtering similar to local logs.

        Args:
            kuberay_result: The original result from KubeRay log retrieval
            raw_logs: Raw log content from KubeRay
            identifier: Job identifier
            num_lines: Maximum number of lines to return
            include_errors: Whether to include error analysis
            max_size_mb: Maximum size in MB for log content
            page: Page number for pagination (optional)
            page_size: Number of lines per page (optional)
            **kwargs: Additional parameters

        Returns:
            Dict containing processed log result
        """
        from .logging_utils import LogAnalyzer, LogProcessor, ResponseFormatter

        log_processor = LogProcessor()

        try:
            # Apply size and line limits
            if page is not None:
                # Use pagination
                if page_size is None:
                    page_size = 100

                paginated_result = await log_processor.stream_logs_with_pagination(
                    raw_logs, page, page_size, max_size_mb
                )

                if paginated_result.get("status") == "error":
                    return paginated_result

                # Merge with KubeRay-specific information
                final_result = {
                    **kuberay_result,
                    **paginated_result,
                    "log_type": "job",
                    "identifier": identifier,
                }

            else:
                # Use simple line/size limits
                processed_logs = log_processor.stream_logs_with_limits(
                    raw_logs, num_lines, max_size_mb
                )

                final_result = {
                    **kuberay_result,
                    "logs": processed_logs,
                    "log_type": "job",
                    "identifier": identifier,
                    "num_lines_retrieved": len(processed_logs.split("\n")),
                    "max_size_mb": max_size_mb,
                }

            # Add error analysis if requested
            if include_errors and final_result.get("logs"):
                final_result["error_analysis"] = LogAnalyzer.analyze_logs_for_errors(
                    final_result["logs"]
                )

            return final_result

        except Exception as e:
            return ResponseFormatter().format_error_response("process kuberay logs", e)

    @staticmethod
    async def process_unified_logs(
        identifier: str,
        system_state: Dict[str, Any],
        log_type: str = "job",
        num_lines: int = 100,
        include_errors: bool = False,
        max_size_mb: int = 10,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        namespace: str = "default",
        local_log_manager=None,
        kuberay_job_manager=None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Unified log processing that supports both local and KubeRay jobs.

        Args:
            identifier: Job identifier
            system_state: Current system state
            log_type: Type of logs to retrieve
            num_lines: Maximum number of lines to return
            include_errors: Whether to include error analysis
            max_size_mb: Maximum size in MB for log content
            page: Page number for pagination (optional)
            page_size: Number of lines per page (optional)
            namespace: Kubernetes namespace for KubeRay jobs
            local_log_manager: Local log manager instance
            kuberay_job_manager: KubeRay job manager instance
            **kwargs: Additional parameters

        Returns:
            Dict containing processed log result
        """
        from .job_type_detector import JobTypeDetector
        from .logging_utils import LogAnalyzer, LogProcessor, ResponseFormatter

        # Detect job type based on identifier patterns and system state
        job_type = JobTypeDetector.detect_from_identifier(identifier, system_state)

        if job_type == "local":
            # Use local Ray log manager
            if local_log_manager is None:
                return ResponseFormatter().format_error_response(
                    "process unified logs", Exception("Local log manager not available")
                )

            return await local_log_manager.retrieve_logs(
                identifier,
                log_type,
                num_lines,
                include_errors,
                max_size_mb,
                page,
                page_size,
                **kwargs,
            )

        elif job_type == "kubernetes":
            # Use KubeRay log retrieval
            if kuberay_job_manager is None:
                return ResponseFormatter().format_error_response(
                    "process unified logs",
                    Exception("KubeRay job manager not available"),
                )

            kuberay_result = await kuberay_job_manager.get_ray_job_logs(
                identifier, namespace
            )

            # Process the result to match the expected format
            if kuberay_result.get("status") == "success":
                raw_logs = kuberay_result.get("logs", "")

                # Apply pagination and processing similar to local logs
                return await LogProcessorStrategy.process_kuberay_logs(
                    kuberay_result,
                    raw_logs,
                    identifier,
                    num_lines,
                    include_errors,
                    max_size_mb,
                    page,
                    page_size,
                    **kwargs,
                )
            else:
                return kuberay_result
        else:
            return ResponseFormatter().format_error_response(
                "process unified logs",
                Exception(f"Unable to determine job type for identifier: {identifier}"),
            )
