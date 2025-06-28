# Ray MCP Server: Troubleshooting Guide

This guide covers common issues and quick solutions.

## Cluster Issues
- **Ray not initialized**: Run `init_ray` before other tools.
- **Port conflicts**: Use default (auto) ports or specify unique ones.
- **Worker nodes not connecting**: Check network/firewall, ensure head node is accessible.

## Job Issues
- **Job fails to submit**: Check entrypoint path and runtime_env.
- **Job hangs or times out**: Inspect job status and logs.
- **Job fails (missing package)**: Add required packages to `runtime_env.pip`.

## Test Issues
- **Tests fail in CI but pass locally**: CI uses minimal resources; check environment detection and resource settings.
- **E2E tests slow**: Use head node only in CI, run unit tests for fast feedback.

## Resource Issues
- **High resource usage in CI**: Use `{ "num_cpus": 1, "worker_nodes": [] }` for CI.
- **Memory errors**: Increase `object_store_memory` or reduce job size.

## Debugging Tips
- Check cluster status: `inspect_ray`
- Get job logs: `retrieve_logs`
- Clean up Ray: `./scripts/ray_cleanup.sh` or `ray stop`
- Check environment: `echo $CI $GITHUB_ACTIONS`

---

For more, see [EXAMPLES.md](EXAMPLES.md) and [TOOLS.md](TOOLS.md).
