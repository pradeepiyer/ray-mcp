# Ray MCP Server Testing Guide

**Complete guide to testing your Ray MCP server without Claude Desktop, covering both local and GKE modes.**

## 🎯 **Overview**

This guide provides multiple approaches to thoroughly test your Ray MCP server independently of Claude Desktop. Your project has excellent testing infrastructure that enables comprehensive validation of all features.

## 🚀 **Quick Start**

### 1. **Setup Testing Environment**
```bash
# Run the setup script to configure your environment
python tests/integration/setup_testing_environment.py
```

### 2. **Choose Your Testing Approach**

#### **Option A: Use Integration Test Scripts (Recommended)**
```bash
# Test local mode
python tests/integration/test_local_mode.py

# Test GKE mode (requires GCP setup)
python tests/integration/test_gke_mode.py

# Or use the convenience script
./tests/integration/run_tests.sh local   # Local mode
./tests/integration/run_tests.sh gke     # GKE mode
./tests/integration/run_tests.sh both    # Both modes

# Or use Make targets
make test-integration-local     # Local integration tests
make test-integration-gke       # GKE integration tests
make test-integration-both      # Both integration tests
```

#### **Option B: Use Existing Test Suite**
```bash
# Fast unit tests (mocked, great for development)
make test-fast

# End-to-end integration tests (no mocking)
make test-e2e

# Complete test suite
make test
```

#### **Option C: Direct Test Runner**
```bash
# Run specific test categories
python tests/integration/test_runner.py unit      # Unit tests only
python tests/integration/test_runner.py e2e       # Integration tests only
python tests/integration/test_runner.py all       # All tests
```

## 🔧 **Testing Approaches Explained**

### **1. Direct Tool Call Testing**

Your project provides excellent utilities for testing MCP tools directly:

```python
# Example: Direct tool testing
from tests.helpers.utils import call_tool, parse_tool_result

# Test cluster operations
result = await call_tool("ray_cluster", {"prompt": "create a local cluster with 4 CPUs"})
response = parse_tool_result(result)
assert response["status"] == "success"

# Test job operations
result = await call_tool("ray_job", {"prompt": "list all jobs"})
response = parse_tool_result(result)

# Test cloud operations
result = await call_tool("cloud", {"prompt": "check environment"})
response = parse_tool_result(result)
```

### **2. Environment-Specific Testing**

#### **Local Mode Testing**
- Tests Ray cluster lifecycle (create, inspect, stop)
- Tests job submission and monitoring
- Tests error handling scenarios
- Tests tool consistency

#### **GKE Mode Testing**
- Tests GCP authentication flow
- Tests GKE cluster listing and creation
- Tests Kubernetes integration
- Tests Ray on Kubernetes deployment
- Tests cloud-specific error handling

### **3. Testing Architecture**

#### **Unit Tests** (`tests/unit/`)
- **Meaningful functionality testing** (not mocked behavior)
- Tests individual components like prompt construction, response parsing, cache behavior
- Perfect for development and rapid iteration
- Run with: `make test-fast`
- **Note**: Tests were refactored to focus on real functionality rather than testing mocked LLM responses

#### **Integration Tests** (`tests/e2e/`)
- **No mocking** - real system integration
- Tests complete workflows from prompt to result
- Validates actual Ray/Kubernetes operations
- Run with: `make test-e2e`

#### **Standalone Integration Tests** (`tests/integration/`)
- **Direct tool testing** without Claude Desktop
- Tests both local and GKE modes independently
- Comprehensive environment setup and validation
- Perfect for manual testing and debugging
- Run with: `make test-integration-local` or `make test-integration-gke`

## 📁 **Integration Test Directory Structure**

The `tests/integration/` directory contains standalone testing scripts that work independently of Claude Desktop:

### **Files Overview**

- **`setup_testing_environment.py`** - Environment setup and dependency checker
- **`test_local_mode.py`** - Comprehensive local Ray cluster testing  
- **`test_gke_mode.py`** - Comprehensive GKE cloud functionality testing
- **`test_runner.py`** - Unified test runner for standard pytest suites
- **`run_tests.sh`** - Convenience shell script for running integration tests

### **Usage Patterns**

#### **Direct Script Execution**
```bash
# From project root
python tests/integration/test_local_mode.py      # Local mode
python tests/integration/test_gke_mode.py        # GKE mode
python tests/integration/test_runner.py unit     # Unit tests
```

#### **Shell Script Convenience**
```bash
# From project root
./tests/integration/run_tests.sh local   # Local integration tests
./tests/integration/run_tests.sh gke     # GKE integration tests
./tests/integration/run_tests.sh both    # Both modes
```

#### **Make Targets**
```bash
make test-integration-local     # Local integration tests
make test-integration-gke       # GKE integration tests (requires GCP setup)
make test-integration-both      # Both integration test modes
make test-integration-setup     # Run environment setup
```

### **Environment Setup**

Before running integration tests, set up your environment:

```bash
# Check and configure your testing environment
python tests/integration/setup_testing_environment.py
```

This will:
- ✅ Check Python version compatibility (3.10+)
- ✅ Verify UV and dependencies are installed
- ✅ Test local Ray cluster functionality
- ✅ Check GKE configuration (if available)
- ✅ Create sample configuration files
- ✅ Provide detailed setup instructions

### **Integration Test Features**

#### **Local Mode Tests** (`test_local_mode.py`)
- Cluster lifecycle (create, inspect, stop)
- Job submission and monitoring
- Error handling scenarios
- Tool consistency validation

#### **GKE Mode Tests** (`test_gke_mode.py`)
- GCP authentication flow
- GKE cluster listing and management
- Kubernetes integration
- Ray on Kubernetes deployment
- Cloud-specific error handling

#### **Test Runner** (`test_runner.py`)
- Unified interface to pytest suites
- Coverage reporting
- Test categorization (unit/e2e/all)
- Flexible test execution options

## 📋 **Local Mode Testing**

### **Prerequisites**
```bash
# Ensure Ray is installed
uv sync

# Verify Ray works
uv run python -c "import ray; ray.init(); print('Ray working!'); ray.shutdown()"
```

### **Test Categories**

#### **1. Cluster Lifecycle**
```bash
# Test cluster creation, inspection, and shutdown
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    # Create cluster
    result = await call_tool('ray_cluster', {'prompt': 'create a local cluster with 4 CPUs'})
    print('Cluster creation:', parse_tool_result(result)['status'])
    
    # Inspect cluster
    result = await call_tool('ray_cluster', {'prompt': 'inspect cluster status'})
    print('Cluster status:', parse_tool_result(result)['status'])
    
    # Stop cluster
    result = await call_tool('ray_cluster', {'prompt': 'stop cluster'})
    print('Cluster shutdown:', parse_tool_result(result)['status'])

asyncio.run(test())
"
```

#### **2. Job Operations**
```bash
# Test job submission and monitoring
python -c "
import asyncio
from tests.helpers.e2e import start_ray_cluster, submit_and_wait_for_job

async def test():
    await start_ray_cluster(cpu_limit=2)
    
    script = '''
import time
print(\"Hello from Ray job!\")
time.sleep(1)
print(\"Job completed!\")
'''
    
    job_id, status = await submit_and_wait_for_job(script)
    print(f'Job {job_id} status: {status}')

asyncio.run(test())
"
```

#### **3. Error Handling**
```bash
# Test error scenarios
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    # Test job without cluster
    result = await call_tool('ray_job', {'prompt': 'list all jobs'})
    print('No cluster error:', parse_tool_result(result)['status'])
    
    # Test invalid connection
    result = await call_tool('ray_cluster', {'prompt': 'connect to cluster at invalid:9999'})
    print('Invalid connection error:', parse_tool_result(result)['status'])

asyncio.run(test())
"
```

## ☁️ **GKE Mode Testing**

### **Prerequisites**

#### **1. GCP Setup**
```bash
# Install GKE dependencies
uv add "ray-mcp[gke]"

# Set up service account with Container Admin role
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

#### **2. Verify GKE Setup**
```bash
# Check GKE environment
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    result = await call_tool('cloud', {'prompt': 'check environment'})
    response = parse_tool_result(result)
    print('GKE available:', response.get('providers', {}).get('gke', {}).get('available', False))

asyncio.run(test())
"
```

### **Test Categories**

#### **1. Authentication**
```bash
# Test GCP authentication
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    result = await call_tool('cloud', {'prompt': 'authenticate with GCP project YOUR_PROJECT_ID'})
    print('Authentication:', parse_tool_result(result)['status'])

asyncio.run(test())
"
```

#### **2. Cluster Management**
```bash
# Test cluster listing
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    result = await call_tool('cloud', {'prompt': 'list all GKE clusters'})
    response = parse_tool_result(result)
    print('Cluster listing:', response['status'])
    if 'clusters' in response:
        print(f'Found {len(response[\"clusters\"])} clusters')

asyncio.run(test())
"
```

#### **3. Ray on Kubernetes**
```bash
# Test Ray cluster on Kubernetes
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def test():
    result = await call_tool('ray_cluster', {'prompt': 'create Ray cluster named test-cluster with 2 workers on kubernetes'})
    print('Ray on K8s:', parse_tool_result(result)['status'])

asyncio.run(test())
"
```

## 🧪 **LLM-Based Testing Strategy**

The Ray MCP system uses Claude for natural language parsing. The test strategy reflects this architecture:

### **What We Test (Meaningful)**
- **Prompt Construction**: Verify parsing prompts contain required structure and examples
- **Response Parsing**: Test JSON extraction from Claude responses and null value cleaning  
- **Cache Behavior**: Validate cache initialization, clearing, and API call avoidance
- **Error Handling**: Test real error scenarios (API failures, empty responses, invalid JSON)
- **Configuration**: Test initialization, environment variables, and singleton behavior
- **Integration**: Optional real LLM calls for end-to-end validation (requires API key)

### **What We Don't Test (Meaningless)**
- ❌ Mocked LLM responses that just return predefined values
- ❌ Specific parsing outcomes without real LLM calls
- ❌ Edge cases that only exist in mocks, not reality

### **Test Types**

#### **Unit Tests** (`test_llm_parser_functionality.py`)
Tests real functionality without API calls:
```python
# ✅ Good - Tests real prompt construction
def test_prompt_contains_required_structure():
    parser = LLMActionParser()
    prompt = parser._build_parsing_prompt("create cluster")
    assert "Parse the following Ray operation" in prompt
    assert "User Request: \"create cluster\"" in prompt

# ❌ Bad - Tests mocked behavior (removed)
@patch('parser.parse_action')
def test_cluster_parsing(mock_parse):
    mock_parse.return_value = {"operation": "create"}
    result = parser.parse_cluster_action("create cluster") 
    assert result["operation"] == "create"  # Just testing mock!
```

#### **Integration Tests** (marked with `@pytest.mark.integration`)
Optional tests with real Claude API calls:
```python
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="No API key")
async def test_real_cluster_parsing():
    parser = LLMActionParser()
    result = await parser.parse_cluster_action("create a local cluster with 4 CPUs")
    assert result["type"] == "cluster"
    assert result["operation"] == "create"
    assert result["cpus"] == 4
```

### **Running LLM Tests**

```bash
# Unit tests (no API key needed)
make test-fast

# Integration tests (requires ANTHROPIC_API_KEY) 
uv run pytest tests/unit/ -m integration
```

## 🛠️ **Advanced Testing Patterns**

### **1. Custom Test Scripts**

Create your own test scripts using the existing utilities:

```python
#!/usr/bin/env python3
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def my_custom_test():
    # Test specific functionality
    result = await call_tool("ray_cluster", {"prompt": "your custom prompt"})
    response = parse_tool_result(result)
    
    assert response["status"] == "success"
    print("Custom test passed!")

if __name__ == "__main__":
    asyncio.run(my_custom_test())
```

### **2. Interactive Testing**

```python
# Interactive testing session
python -c "
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def interactive():
    while True:
        tool = input('Tool (ray_cluster/ray_job/cloud): ')
        if tool == 'quit':
            break
        prompt = input('Prompt: ')
        
        result = await call_tool(tool, {'prompt': prompt})
        response = parse_tool_result(result)
        
        print(f'Status: {response[\"status\"]}')
        print(f'Response: {response}')

asyncio.run(interactive())
"
```

### **3. Performance Testing**

```python
# Test concurrent operations
import asyncio
from tests.helpers.utils import call_tool, parse_tool_result

async def performance_test():
    # Test concurrent cluster inspections
    tasks = [
        call_tool("ray_cluster", {"prompt": "inspect cluster status"})
        for _ in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        response = parse_tool_result(result)
        print(f"Request {i}: {response['status']}")

asyncio.run(performance_test())
```

## 📊 **Test Execution Methods**

### **Method 1: Make Commands (Recommended)**
```bash
# Standard test suite
make test-fast      # Fast unit tests
make test-e2e       # Integration tests  
make test           # All tests
make test-cov       # Tests with coverage

# Integration tests
make test-integration-local     # Local integration tests
make test-integration-gke       # GKE integration tests
make test-integration-both      # Both integration modes
make test-integration-setup     # Environment setup
```

### **Method 2: Integration Test Scripts**
```bash
# Direct script execution
python tests/integration/test_local_mode.py      # Local mode tests
python tests/integration/test_gke_mode.py        # GKE mode tests
python tests/integration/test_runner.py unit     # Unit tests
python tests/integration/test_runner.py e2e      # Integration tests
python tests/integration/test_runner.py all      # Complete suite

# Shell script convenience
./tests/integration/run_tests.sh local   # Local integration tests
./tests/integration/run_tests.sh gke     # GKE integration tests
./tests/integration/run_tests.sh both    # Both modes
```

### **Method 3: Direct pytest**
```bash
# Direct pytest execution
pytest tests/unit/ -m unit -v          # Unit tests
pytest tests/e2e/ -m e2e -v            # Integration tests
pytest tests/unit/test_mcp_tools.py    # Specific test file
```

### **Method 4: Environment Setup**
```bash
# Setup testing environment
python tests/integration/setup_testing_environment.py
```

## 🔍 **Debugging and Troubleshooting**

### **Enable Debug Logging**
```bash
export RAY_MCP_LOG_LEVEL=DEBUG
export RAY_MCP_ENHANCED_OUTPUT=true
```

### **Check Dependencies**
```bash
# Verify all dependencies
python setup_testing_environment.py
```

### **Common Issues**

#### **Local Mode Issues**
- **Ray startup fails**: Check if ports 8265, 10001 are available
- **Permission errors**: Ensure write permissions in current directory
- **Import errors**: Run `uv sync` to install dependencies

#### **GKE Mode Issues**
- **Authentication fails**: Check `GOOGLE_APPLICATION_CREDENTIALS` path
- **No clusters found**: Verify project ID and permissions
- **Network errors**: Check firewall and network connectivity

## 📈 **Best Practices**

### **1. Test Organization**
- Start with unit tests for rapid feedback
- Use integration tests for critical workflows
- Test both success and error scenarios
- Validate response formats and structure

### **2. Environment Management**
- Use environment variables for configuration
- Clean up resources after tests
- Separate test environments from production
- Use CI/CD for automated testing

### **3. Monitoring and Validation**
- Check response status codes
- Validate response structure
- Monitor resource usage
- Test timeout scenarios

## 🎯 **Summary**

Your Ray MCP server has excellent testing infrastructure that enables comprehensive validation without Claude Desktop:

- **Direct tool calls** using `tests.helpers.utils.call_tool`
- **Two-tier testing** with unit (mocked) and integration (real) tests
- **Environment-specific testing** for local and GKE modes
- **Comprehensive utilities** for cluster management, job operations, and error handling
- **Flexible execution** via Make, pytest, or custom scripts

**Recommended workflow:**
1. Run `python tests/integration/setup_testing_environment.py` to configure your environment
2. Use `make test-integration-local` for local integration testing
3. Use `make test-integration-gke` for GKE testing (with proper GCP setup)
4. Use `make test-fast` for rapid development feedback
5. Use `make test-e2e` for comprehensive integration validation

This approach gives you complete control over testing all MCP server features without depending on Claude Desktop, while leveraging the sophisticated testing infrastructure already built into your project. 