# Ray MCP Server: Tools Reference

This is a quick reference for all Ray MCP tools.

## Cluster Management

### init_ray
- Start or connect to a Ray cluster.
- **Params:** `num_cpus`, `worker_nodes`, `num_gpus`, `object_store_memory`, ...
- **Example:**
```json
{
  "tool": "init_ray",
  "arguments": {"num_cpus": 4}
}
```

### stop_ray
- Stop the current Ray cluster.
- **Params:** none
- **Example:**
```json
{"tool": "stop_ray", "arguments": {}}
```

### inspect_ray
- Get cluster status and resources.
- **Params:** none
- **Example:**
```json
{"tool": "inspect_ray", "arguments": {}}
```

## Job Management

### submit_job
- Submit a job to the cluster.
- **Params:** `entrypoint`, `runtime_env`
- **Example:**
```json
{
  "tool": "submit_job",
  "arguments": {"entrypoint": "python examples/simple_job.py"}
}
```

### list_jobs
- List all jobs in the cluster.
- **Params:** none
- **Example:**
```json
{"tool": "list_jobs", "arguments": {}}
```

### inspect_job
- Get job status or debug info.
- **Params:** `job_id`, `mode` ("status", "logs", "debug")
- **Example:**
```json
{
  "tool": "inspect_job",
  "arguments": {"job_id": "<your_job_id>"}
}
```

### cancel_job
- Cancel a running or queued job.
- **Params:** `job_id`
- **Example:**
```json
{
  "tool": "cancel_job",
  "arguments": {"job_id": "<your_job_id>"}
}
```

## Logging & Debugging

### retrieve_logs
- Get logs for jobs, actors, or nodes.
- **Params:** `identifier`, `log_type` ("job", "actor", "node"), `num_lines`, `include_errors`
- **Example:**
```json
{
  "tool": "retrieve_logs",
  "arguments": {"identifier": "<your_job_id>", "log_type": "job"}
}
```

---

For detailed configuration and troubleshooting, see [CONFIGURATION.md](CONFIGURATION.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
