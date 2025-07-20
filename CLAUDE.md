# Ray MCP Server

**3-tool prompt-driven Ray management via natural language.**

## Architecture
- **3 Tools**: `ray_job`, `ray_service`, `ray_cloud` (single `prompt` parameter each)
- **Natural Language**: OpenAI parses prompts into Ray operations
- **Multi-Environment**: Local Ray + Kubernetes/KubeRay + AWS EKS support

## Configuration

### Required Environment Variables
```bash
OPENAI_API_KEY=your_api_key_here       # Required for LLM parsing
```

### Optional Environment Variables
```bash
LLM_MODEL=gpt-3.5-turbo                # OpenAI model (default: gpt-3.5-turbo)
RAY_MCP_ENHANCED_OUTPUT=true           # LLM-friendly responses with suggestions
RAY_MCP_LOG_LEVEL=DEBUG                # Logging level
GOOGLE_APPLICATION_CREDENTIALS=path    # GKE authentication
AWS_ACCESS_KEY_ID=your_key             # AWS authentication
AWS_SECRET_ACCESS_KEY=your_secret      # AWS authentication
AWS_DEFAULT_REGION=us-west-2           # AWS default region
RAY_DISABLE_USAGE_STATS=1              # Disable Ray telemetry
```

## Commands

### Development
```bash
make test-fast     # Unit tests (mocked)
make test-e2e      # Integration tests
make lint          # Code quality
make dev-install   # Setup development environment
uv run ray-mcp     # Run MCP server
```

### Testing
```bash
python tests/integration/test_runner.py unit    # Fast feedback
python tests/integration/test_runner.py e2e     # Integration validation
python tests/integration/test_runner.py all     # Complete test suite
```

## Dependencies
- `ray[default]>=2.47.0`
- `mcp>=1.0.0` 
- `openai>=1.0.0,<2.0.0`
- `kubernetes>=26.1.0`
- `boto3>=1.0.0` (AWS support)
- `pydantic>=2.0.0`
- Python 3.10+

## Entry Points
- `uv run ray-mcp` - Start MCP server
- `python tests/integration/test_runner.py [unit|e2e|all]` - Run tests
- `python -m ray_mcp.main` - Direct module execution

## Key Files
- `ray_mcp/tools.py` - 3-tool definitions
- `ray_mcp/parsers.py` - Natural language parsing
- `ray_mcp/handlers.py` - MCP protocol handlers
- `ray_mcp/managers/` - Business logic
- `ray_mcp/llm_parser.py` - OpenAI API integration

## Debugging
- **LLM Issues**: Verify `OPENAI_API_KEY` is set
- **GKE Issues**: Check `GOOGLE_APPLICATION_CREDENTIALS`
- **EKS Issues**: Check AWS credentials and region configuration
- **KubeRay Issues**: `kubectl get pods -n kuberay-system`
- **Architecture Validation**: `make lint-tool-functions`
