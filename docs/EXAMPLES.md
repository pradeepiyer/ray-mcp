# Ray MCP Server: Example Usage

This guide shows common usage patterns for the Ray MCP Server.

## 1. Start a Ray Cluster

```json
{
  "tool": "init_ray",
  "arguments": {"num_cpus": 4}
}
```

## 2. Submit a Job

```json
{
  "tool": "submit_job",
  "arguments": {"entrypoint": "python examples/simple_job.py"}
}
```

## 3. Check Job Status

```json
{
  "tool": "inspect_job",
  "arguments": {"job_id": "<your_job_id>"}
}
```

## 4. Retrieve Job Logs

```json
{
  "tool": "retrieve_logs",
  "arguments": {"identifier": "<your_job_id>", "log_type": "job"}
}
```

## 5. Stop the Cluster

```json
{
  "tool": "stop_ray",
  "arguments": {}
}
```

## Advanced: Custom Cluster & Runtime

- Add worker nodes, GPUs, or custom resources in `init_ray` arguments.
- Use `runtime_env` in `submit_job` to specify dependencies:

```json
{
  "tool": "submit_job",
  "arguments": {
    "entrypoint": "python examples/simple_job.py",
    "runtime_env": {"pip": ["numpy", "pandas"]}
  }
}
```

---

For more, see [Tools Reference](TOOLS.md) and [Troubleshooting](TROUBLESHOOTING.md).