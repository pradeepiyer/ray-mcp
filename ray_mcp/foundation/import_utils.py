"""Simplified import utilities for Ray MCP."""

from typing import TYPE_CHECKING, Any, Optional

# Ray imports
try:
    import ray

    RAY_AVAILABLE = True
except ImportError:
    ray = None
    RAY_AVAILABLE = False

# Kubernetes imports
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    from kubernetes.config.config_exception import ConfigException

    KUBERNETES_AVAILABLE = True
except ImportError:
    client = None
    config = None
    ApiException = Exception
    ConfigException = Exception
    KUBERNETES_AVAILABLE = False

# Google Cloud imports
if TYPE_CHECKING:
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError
    from google.auth.transport import requests as google_auth_transport
    from google.cloud import container_v1

try:
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError
    from google.auth.transport import requests as google_auth_transport
    from google.cloud import container_v1

    GOOGLE_CLOUD_AVAILABLE = True
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    default = None
    DefaultCredentialsError = Exception
    container_v1 = None
    google_auth_transport = None
    GOOGLE_CLOUD_AVAILABLE = False
    GOOGLE_AUTH_AVAILABLE = False
