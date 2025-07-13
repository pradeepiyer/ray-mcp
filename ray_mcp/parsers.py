"""Natural language parsing for Ray operations."""

import re
from typing import Dict, Any, Optional


class ActionParser:
    """Parse natural language into structured actions."""
    
    # Cluster operations
    CLUSTER_CREATE = r'(?:create|start|init|setup|deploy).+cluster'
    CLUSTER_CONNECT = r'connect.+cluster|attach.+cluster'  
    CLUSTER_STOP = r'(?:stop|shutdown|delete|destroy).+cluster'
    CLUSTER_SCALE = r'scale.+cluster|scale.+worker'
    CLUSTER_INSPECT = r'(?:inspect|status|info|describe).+cluster'
    CLUSTER_LIST = r'(?:list|show).+cluster'
    
    # Job operations  
    JOB_SUBMIT = r'(?:submit|run|execute|start).+job'
    JOB_LIST = r'(?:list|show).+job'
    JOB_INSPECT = r'(?:inspect|status|check).+job'
    JOB_LOGS = r'(?:logs?|log).+job|get.+logs?'
    JOB_CANCEL = r'(?:cancel|stop|kill).+job'
    
    # Cloud operations
    CLOUD_AUTH = r'(?:auth|login|connect).+(?:gcp|google|gke|cloud)'
    CLOUD_LIST = r'(?:list|show).+(?:cluster|k8s|kubernetes)'
    CLOUD_CONNECT = r'connect.+(?:gke|k8s|kubernetes)'
    CLOUD_CREATE = r'create.+(?:cluster|gke|k8s)'
    CLOUD_CHECK = r'(?:check|verify|test).+(?:env|auth|setup)'

    @classmethod
    def parse_cluster_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse cluster action from prompt."""
        prompt_lower = prompt.lower()
        
        if re.search(cls.CLUSTER_CREATE, prompt_lower):
            return {
                'operation': 'create',
                'environment': cls._detect_environment(prompt),
                'resources': cls._extract_resources(prompt),
                'name': cls._extract_name(prompt),
                'head_only': 'head only' in prompt_lower or 'no worker' in prompt_lower
            }
        elif re.search(cls.CLUSTER_CONNECT, prompt_lower):
            return {
                'operation': 'connect',
                'address': cls._extract_address(prompt),
                'name': cls._extract_name(prompt)
            }
        elif re.search(cls.CLUSTER_STOP, prompt_lower):
            return {
                'operation': 'stop', 
                'name': cls._extract_name(prompt)
            }
        elif re.search(cls.CLUSTER_SCALE, prompt_lower):
            return {
                'operation': 'scale',
                'name': cls._extract_name(prompt),
                'workers': cls._extract_number(prompt, 'worker')
            }
        elif re.search(cls.CLUSTER_INSPECT, prompt_lower):
            return {
                'operation': 'inspect',
                'name': cls._extract_name(prompt)
            }
        elif re.search(cls.CLUSTER_LIST, prompt_lower):
            return {'operation': 'list'}
        
        raise ValueError(f"Cannot understand cluster action: {prompt}")

    @classmethod  
    def parse_job_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse job action from prompt."""
        prompt_lower = prompt.lower()
        
        if re.search(cls.JOB_SUBMIT, prompt_lower):
            return {
                'operation': 'submit',
                'source': cls._extract_source_url(prompt),
                'script': cls._extract_script_path(prompt),
                'resources': cls._extract_resources(prompt)
            }
        elif re.search(cls.JOB_LIST, prompt_lower):
            return {'operation': 'list'}
        elif re.search(cls.JOB_INSPECT, prompt_lower):
            return {
                'operation': 'inspect',
                'job_id': cls._extract_job_id(prompt)
            }
        elif re.search(cls.JOB_LOGS, prompt_lower):
            return {
                'operation': 'logs',
                'job_id': cls._extract_job_id(prompt),
                'filter_errors': 'error' in prompt_lower
            }
        elif re.search(cls.JOB_CANCEL, prompt_lower):
            return {
                'operation': 'cancel',
                'job_id': cls._extract_job_id(prompt)
            }
            
        raise ValueError(f"Cannot understand job action: {prompt}")

    @classmethod
    def parse_cloud_action(cls, prompt: str) -> Dict[str, Any]:
        """Parse cloud action from prompt."""
        prompt_lower = prompt.lower()
        
        if re.search(cls.CLOUD_AUTH, prompt_lower):
            return {
                'operation': 'authenticate',
                'provider': 'gke',
                'project': cls._extract_project(prompt)
            }
        elif re.search(cls.CLOUD_LIST, prompt_lower):
            return {
                'operation': 'list_clusters',
                'provider': 'gke'
            }
        elif re.search(cls.CLOUD_CONNECT, prompt_lower):
            return {
                'operation': 'connect_cluster',
                'cluster_name': cls._extract_name(prompt),
                'provider': 'gke'
            }
        elif re.search(cls.CLOUD_CREATE, prompt_lower):
            return {
                'operation': 'create_cluster',
                'cluster_name': cls._extract_name(prompt),
                'provider': 'gke',
                'zone': cls._extract_zone(prompt)
            }
        elif re.search(cls.CLOUD_CHECK, prompt_lower):
            return {'operation': 'check_environment'}
            
        raise ValueError(f"Cannot understand cloud action: {prompt}")

    # Helper extraction methods
    @staticmethod
    def _detect_environment(prompt: str) -> str:
        if re.search(r'\b(?:k8s|kubernetes|gke)\b', prompt, re.IGNORECASE):
            return 'kubernetes'
        return 'local'

    @staticmethod  
    def _extract_resources(prompt: str) -> Dict[str, Any]:
        resources = {}
        if match := re.search(r'(\d+)\s*(?:cpu|core)', prompt, re.IGNORECASE):
            resources['cpu'] = int(match.group(1))
        if match := re.search(r'(\d+)\s*(?:gpu|nvidia)', prompt, re.IGNORECASE):
            resources['gpu'] = int(match.group(1))
        if match := re.search(r'(\d+)\s*worker', prompt, re.IGNORECASE):
            resources['workers'] = int(match.group(1))
        return resources

    @staticmethod
    def _extract_name(prompt: str) -> Optional[str]:
        if match := re.search(r'(?:named|cluster|called)\s+([^\s]+)', prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_address(prompt: str) -> Optional[str]:
        if match := re.search(r'(\d+\.\d+\.\d+\.\d+:\d+)', prompt):
            return match.group(1)
        return None

    @staticmethod
    def _extract_source_url(prompt: str) -> Optional[str]:
        if match := re.search(r'https://github\.com/[^\s]+', prompt):
            return match.group(0)
        if match := re.search(r's3://[^\s]+', prompt):
            return match.group(0)
        return None

    @staticmethod
    def _extract_script_path(prompt: str) -> Optional[str]:
        if match := re.search(r'([^\s]+\.py)', prompt):
            return match.group(1)
        return None

    @staticmethod
    def _extract_job_id(prompt: str) -> Optional[str]:
        if match := re.search(r'job[\s-]+([^\s]+)', prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_number(prompt: str, context: str) -> Optional[int]:
        pattern = rf'(\d+)\s*{context}'
        if match := re.search(pattern, prompt, re.IGNORECASE):
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_project(prompt: str) -> Optional[str]:
        if match := re.search(r'project\s+([^\s]+)', prompt, re.IGNORECASE):
            return match.group(1)
        return None

    @staticmethod
    def _extract_zone(prompt: str) -> Optional[str]:
        if match := re.search(r'(?:zone|region)\s+([^\s]+)', prompt, re.IGNORECASE):
            return match.group(1)
        return None