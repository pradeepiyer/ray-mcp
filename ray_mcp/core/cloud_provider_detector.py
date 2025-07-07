"""Cloud provider detection logic for Ray MCP."""

import asyncio
import json
import os
from typing import Any, Dict, Optional

try:
    from ..logging_utils import LoggingUtility, ResponseFormatter
except ImportError:
    # Fallback for direct execution
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from logging_utils import LoggingUtility, ResponseFormatter

from .interfaces import (
    AuthenticationType,
    CloudProvider,
    CloudProviderAuth,
    StateManager,
)


class CloudProviderDetector(CloudProviderAuth):
    """Detects cloud provider environments and authentication methods."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        self._state_manager = state_manager
        self._response_formatter = ResponseFormatter()
        self._detection_cache = {}
        self._cache_ttl = 300  # 5 minutes

    def detect_provider(self) -> Optional[CloudProvider]:
        """Detect the current cloud provider environment."""
        # Check cache first
        if self._is_cache_valid("provider_detection"):
            return self._detection_cache.get("provider")

        provider = self._detect_cloud_environment()
        self._update_cache("provider_detection", {"provider": provider})
        return provider

    def get_auth_type(self) -> Optional[AuthenticationType]:
        """Get the authentication type available for the detected provider."""
        provider = self.detect_provider()
        if not provider:
            return None

        # Check cache first
        cache_key = f"auth_type_{provider.value}"
        if self._is_cache_valid(cache_key):
            return self._detection_cache.get(cache_key)

        auth_type = self._detect_auth_type(provider)
        self._update_cache(cache_key, auth_type)
        return auth_type

    async def authenticate(
        self, provider: CloudProvider, auth_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Authenticate with the specified cloud provider."""
        try:
            auth_type = self.get_auth_type()
            if not auth_type:
                return self._response_formatter.format_error_response(
                    "cloud provider authentication",
                    Exception(
                        f"No authentication method available for {provider.value}"
                    ),
                )

            if provider == CloudProvider.GKE:
                return await self._authenticate_gke(auth_config or {})
            else:
                return self._response_formatter.format_error_response(
                    "cloud provider authentication",
                    Exception(f"Authentication not supported for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "cloud provider authentication", e
            )

    async def validate_authentication(self, provider: CloudProvider) -> Dict[str, Any]:
        """Validate authentication with the specified cloud provider."""
        try:
            if provider == CloudProvider.GKE:
                return await self._validate_gke_auth()
            else:
                return self._response_formatter.format_error_response(
                    "validate cloud authentication",
                    Exception(f"Validation not supported for {provider.value}"),
                )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "validate cloud authentication", e
            )

    def _detect_cloud_environment(self) -> Optional[CloudProvider]:
        """Detect which cloud environment we're running in."""
        # Check for GKE
        if self._is_gke_environment():
            return CloudProvider.GKE

        # Default to local
        return CloudProvider.LOCAL

    def _is_gke_environment(self) -> bool:
        """Check if we're running in a GKE environment."""
        # Check for GKE metadata service
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
            # Additional GKE-specific checks
            try:
                # Check for GCP metadata service
                import urllib.error
                import urllib.request

                # This is a common way to detect GCP/GKE
                req = urllib.request.Request(
                    "http://metadata.google.internal/computeMetadata/v1/",
                    headers={"Metadata-Flavor": "Google"},
                )
                with urllib.request.urlopen(req, timeout=1) as response:
                    return response.status == 200
            except (urllib.error.URLError, OSError):
                pass

        # Check for GKE-specific environment variables
        gke_indicators = [
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GCLOUD_PROJECT",
            "GOOGLE_CLOUD_PROJECT",
        ]

        for indicator in gke_indicators:
            if os.getenv(indicator):
                return True

        # Check for gcloud SDK
        if os.path.exists(os.path.expanduser("~/.config/gcloud")):
            return True

        return False

    def _detect_auth_type(
        self, provider: CloudProvider
    ) -> Optional[AuthenticationType]:
        """Detect available authentication type for the provider."""
        if provider == CloudProvider.GKE:
            # Check for service account
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                return AuthenticationType.SERVICE_ACCOUNT

            # Check for in-cluster service account
            if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount"):
                return AuthenticationType.IN_CLUSTER

            # Check for gcloud SDK
            if os.path.exists(os.path.expanduser("~/.config/gcloud")):
                return AuthenticationType.SERVICE_ACCOUNT

        elif provider == CloudProvider.LOCAL:
            return AuthenticationType.KUBECONFIG

        return None

    async def _authenticate_gke(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with GKE."""
        auth_type = self.get_auth_type()

        if auth_type == AuthenticationType.SERVICE_ACCOUNT:
            # Use service account authentication
            service_account_path = auth_config.get("service_account_path") or os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            if not service_account_path:
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    Exception(
                        "Service account path not provided and GOOGLE_APPLICATION_CREDENTIALS not set"
                    ),
                )

            if not os.path.exists(service_account_path):
                return self._response_formatter.format_error_response(
                    "gke authentication",
                    Exception(
                        f"Service account file not found: {service_account_path}"
                    ),
                )

            # Set environment variable
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path

            # Update state
            if self._state_manager:
                self._state_manager.update_state(
                    cloud_provider_auth={
                        "gke": {
                            "authenticated": True,
                            "auth_type": auth_type.value,
                            "service_account_path": service_account_path,
                        }
                    }
                )

            return self._response_formatter.format_success_response(
                provider="gke",
                auth_type=auth_type.value,
                authenticated=True,
                service_account_path=service_account_path,
            )

        elif auth_type == AuthenticationType.IN_CLUSTER:
            # Use in-cluster authentication
            if self._state_manager:
                self._state_manager.update_state(
                    cloud_provider_auth={
                        "gke": {"authenticated": True, "auth_type": auth_type.value}
                    }
                )

            return self._response_formatter.format_success_response(
                provider="gke", auth_type=auth_type.value, authenticated=True
            )

        return self._response_formatter.format_error_response(
            "gke authentication",
            Exception(f"Unsupported authentication type: {auth_type}"),
        )

    async def _validate_gke_auth(self) -> Dict[str, Any]:
        """Validate GKE authentication."""
        try:
            # Try to call GKE API to validate credentials
            # This is a simplified validation - in practice, you'd use the Google Cloud SDK

            # Check if we have credentials
            if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                return self._response_formatter.format_error_response(
                    "validate gke authentication", Exception("No GKE credentials found")
                )

            return self._response_formatter.format_success_response(
                provider="gke", authenticated=True, valid=True
            )

        except Exception as e:
            return self._response_formatter.format_error_response(
                "validate gke authentication", e
            )

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._detection_cache:
            return False

        import time

        entry = self._detection_cache[key]
        if isinstance(entry, dict) and "timestamp" in entry:
            return time.time() - entry["timestamp"] < self._cache_ttl

        return False

    def _update_cache(self, key: str, value: Any) -> None:
        """Update cache with new value."""
        import time

        self._detection_cache[key] = {"value": value, "timestamp": time.time()}
