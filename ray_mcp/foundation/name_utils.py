"""Simple unique name generation utilities for Ray resources."""

import hashlib
import re
import time
from datetime import datetime
from typing import Optional


class NameGenerator:
    """Generates simple unique names for Ray resources based on tool context."""

    @staticmethod
    def generate_ray_job_name(
        base_name: Optional[str] = None, max_length: int = 63
    ) -> str:
        """Generate a simple unique name for a Ray job.
        
        Args:
            base_name: Optional base name from action parsing
            max_length: Maximum name length (Kubernetes limit is 63 characters)
            
        Returns:
            A unique name following Kubernetes naming conventions
        """
        # If base_name is provided and is not a default, use it (with uniqueness)
        if base_name and base_name != "ray-job":
            if NameGenerator._is_likely_unique(base_name):
                return NameGenerator._sanitize_k8s_name(base_name, max_length)
            else:
                # Make the custom name unique
                timestamp = datetime.now().strftime("%m%d-%H%M")
                unique_id = NameGenerator._generate_unique_id()
                name = f"{base_name}-{timestamp}-{unique_id}"
                return NameGenerator._sanitize_k8s_name(name, max_length)
        
        # Generate simple unique job name
        timestamp = datetime.now().strftime("%m%d-%H%M")
        unique_id = NameGenerator._generate_unique_id()
        name = f"ray-job-{timestamp}-{unique_id}"
        
        return NameGenerator._sanitize_k8s_name(name, max_length)

    @staticmethod
    def generate_ray_service_name(
        base_name: Optional[str] = None, max_length: int = 63
    ) -> str:
        """Generate a simple unique name for a Ray service.
        
        Args:
            base_name: Optional base name from action parsing
            max_length: Maximum name length (Kubernetes limit is 63 characters)
            
        Returns:
            A unique name following Kubernetes naming conventions
        """
        # If base_name is provided and is not a default, use it (with uniqueness)
        if base_name and base_name != "ray-service":
            if NameGenerator._is_likely_unique(base_name):
                return NameGenerator._sanitize_k8s_name(base_name, max_length)
            else:
                # Make the custom name unique
                timestamp = datetime.now().strftime("%m%d-%H%M")
                unique_id = NameGenerator._generate_unique_id()
                name = f"{base_name}-svc-{timestamp}-{unique_id}"
                return NameGenerator._sanitize_k8s_name(name, max_length)
        
        # Generate simple unique service name
        timestamp = datetime.now().strftime("%m%d-%H%M")
        unique_id = NameGenerator._generate_unique_id()
        name = f"ray-service-{timestamp}-{unique_id}"
        
        return NameGenerator._sanitize_k8s_name(name, max_length)

    @staticmethod
    def _generate_unique_id() -> str:
        """Generate a short unique identifier."""
        import random
        # Use timestamp microseconds and random component for uniqueness
        timestamp_us = str(int(time.time() * 1000000))[-4:]  # Last 4 digits of microsecond timestamp
        random_part = f"{random.randint(10, 99)}"  # 2-digit random number
        return f"{timestamp_us}{random_part}"

    @staticmethod
    def _is_likely_unique(name: str) -> bool:
        """Check if a name looks like it was already made unique."""
        # Contains timestamp-like patterns
        if re.search(r'\d{4}-\d{4}', name) or re.search(r'\d{6,}', name):
            return True
        
        # Contains hash-like suffixes
        if re.search(r'-[a-f0-9]{6,}$', name):
            return True
        
        # Contains UUID-like patterns
        if re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}', name):
            return True
        
        return False

    @staticmethod
    def _sanitize_k8s_name(name: str, max_length: int = 63) -> str:
        """Sanitize name to follow Kubernetes naming conventions.
        
        Rules:
        - Start and end with alphanumeric
        - Contain only lowercase alphanumeric and hyphens
        - Maximum 63 characters
        """
        # Convert to lowercase
        name = name.lower()
        
        # Replace invalid characters with hyphens
        name = re.sub(r'[^a-z0-9-]', '-', name)
        
        # Remove consecutive hyphens
        name = re.sub(r'-+', '-', name)
        
        # Ensure it starts and ends with alphanumeric
        name = re.sub(r'^-+', '', name)
        name = re.sub(r'-+$', '', name)
        
        # Ensure it starts with alphanumeric (not just numeric)
        if name and not name[0].isalpha():
            name = f"job-{name}"
        
        # Truncate if too long, preserving the unique suffix
        if len(name) > max_length:
            # Try to preserve a unique suffix (last 8 characters if they look unique)
            if len(name) > 8:
                suffix = name[-8:]
                if re.search(r'[a-f0-9]{6}', suffix):
                    # Preserve unique suffix
                    prefix_length = max_length - 9  # -1 for hyphen
                    name = f"{name[:prefix_length]}-{suffix}"
                else:
                    name = name[:max_length]
            else:
                name = name[:max_length]
        
        # Ensure we have a valid name
        if not name or not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', name):
            # Fallback to simple unique name
            timestamp = str(int(time.time()))[-6:]
            name = f"ray-job-{timestamp}"
        
        return name