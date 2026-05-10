# ComfyUI API - Job ID (prompt_id) Usage Guide

## What is a prompt_id?
A `prompt_id` (also called job ID) is a unique identifier returned when you submit a workflow to ComfyUI. It's used to track and manage jobs throughout their lifecycle.

## Job Lifecycle Flow
```
1. Submit  → POST /prompt → Returns {prompt_id, number, node_errors}
2. Queue   → GET /queue → Check running/pending status
3. Execute → Running in background
4. Complete → GET /history/{prompt_id} → Retrieve results
5. Cleanup → POST /history → Delete from history
```

## API Endpoints Using prompt_id

### 1. GET /history/{prompt_id}
**Purpose**: Retrieve complete details for a specific job

**Response Structure**:
```json
{
  "prompt_id": {
    "prompt": {...},        // Workflow nodes and parameters
    "outputs": {...},       // Generated files (images, videos, etc.)
    "status": {
      "status_str": "success",
      "completed": true,
      "messages": [...]     // Execution events
    },
    "meta": {...}          // Metadata
  }
}
```

**Use Cases**:
- Get job execution status and results
- Retrieve output file locations
- Access workflow parameters used
- View execution messages and errors

---

### 2. POST /history
**Purpose**: Delete completed jobs from history

**Delete Specific Jobs**:
```json
{
  "delete": ["prompt_id1", "prompt_id2", ...]
}
```

**Clear All History**:
```json
{
  "clear": true
}
```

**Important**: 
- Only removes job records from history
- Does NOT delete output files from disk
- Already completed jobs only (not queued jobs)

---

### 3. GET /queue
**Purpose**: Check queue status and find running/pending jobs

**Response Structure**:
```json
{
  "queue_running": [
    [number, prompt_id, prompt, extra_data, outputs_to_execute],
    ...
  ],
  "queue_pending": [
    [number, prompt_id, prompt, extra_data, outputs_to_execute],
    ...
  ]
}
```

**Use Cases**:
- Check if a specific job is running
- Monitor queue length
- Find prompt_id of currently executing jobs
- Estimate wait time

---

### 4. POST /queue
**Purpose**: Cancel or delete jobs from queue

**Cancel Job**:
```json
{
  "delete": ["prompt_id"]
}
```

**Use Cases**:
- Stop a job that's queued but not started
- Cancel a currently running job
- Free up queue space

**Note**: Different from POST /history - this affects queued/running jobs, not completed ones

---

### 5. POST /prompt
**Purpose**: Submit a new workflow job

**Request**:
```json
{
  "prompt": {...},         // Workflow definition
  "client_id": "...",      // Optional client identifier
  "extra_data": {...}      // Optional extra data
}
```

**Response**:
```json
{
  "prompt_id": "uuid-here",
  "number": 123,
  "node_errors": {}
}
```

**Returns**: The prompt_id for tracking the job

---

## Typical Usage Patterns

### Pattern 1: Submit and Track
```python
# Submit job
response = requests.post(f"{url}/prompt", json={"prompt": workflow})
prompt_id = response.json()["prompt_id"]

# Check queue status
queue = requests.get(f"{url}/queue").json()
# Look for prompt_id in queue_running or queue_pending

# Get results when complete
result = requests.get(f"{url}/history/{prompt_id}").json()
```

### Pattern 2: Monitor Until Complete
```python
while True:
    # Check if still in queue
    queue = requests.get(f"{url}/queue").json()
    in_queue = any(prompt_id in str(job) for job in 
                   queue["queue_running"] + queue["queue_pending"])
    
    if not in_queue:
        # Job completed, get results
        result = requests.get(f"{url}/history/{prompt_id}").json()
        break
    
    time.sleep(1)
```

### Pattern 3: Cancel Running Job
```python
# Cancel the job
requests.post(f"{url}/queue", json={"delete": [prompt_id]})
```

### Pattern 4: Cleanup Old Jobs
```python
# Get all history
history = requests.get(f"{url}/history").json()

# Delete old jobs
old_prompt_ids = list(history.keys())[:10]
requests.post(f"{url}/history", json={"delete": old_prompt_ids})
```

---

## Job Status Values

From status response:
- `status_str`: "success", "error", or other status
- `completed`: true/false
- `messages`: Array of execution events:
  - `execution_start`
  - `execution_cached` (if nodes were cached)
  - `execution_success` or `execution_error`

---

## Current Dashboard Implementation

Our dashboard uses prompt_id for:

1. **Display**: Show prompt_id in image metadata
2. **Delete**: 
   ```python
   requests.post(f"{COMFYUI_URL}/history", 
                 json={"delete": [prompt_id]})
   ```
3. **Track**: Associate images with their generation job
4. **Workflow**: Link back to original workflow parameters

---

## Additional Capabilities

### Get Output Files
```python
result = requests.get(f"{url}/history/{prompt_id}").json()
for node_id, output in result[prompt_id]["outputs"].items():
    if "images" in output:
        for img in output["images"]:
            filename = img["filename"]
            subfolder = img.get("subfolder", "")
            # Use GET /view to retrieve actual image
```

### Get Execution Time
```python
result = requests.get(f"{url}/history/{prompt_id}").json()
messages = result[prompt_id]["status"]["messages"]
start_time = next(m[1]["timestamp"] for m in messages 
                  if m[0] == "execution_start")
end_time = next(m[1]["timestamp"] for m in messages 
                if m[0] == "execution_success")
duration_ms = end_time - start_time
```

### Check Node Caching
```python
result = requests.get(f"{url}/history/{prompt_id}").json()
cached_event = next((m for m in messages 
                     if m[0] == "execution_cached"), None)
if cached_event:
    cached_nodes = cached_event[1]["nodes"]
    print(f"Cached nodes: {cached_nodes}")
```

---

## Summary Table

| Endpoint | Method | Purpose | Affects |
|----------|--------|---------|---------|
| `/prompt` | POST | Submit new job | Creates new prompt_id |
| `/queue` | GET | Check queue | Read only |
| `/queue` | POST | Cancel job | Queued/running jobs |
| `/history` | GET | Get all history | Read only |
| `/history/{prompt_id}` | GET | Get specific job | Read only |
| `/history` | POST | Delete from history | Completed jobs only |

---

## Best Practices

1. **Store prompt_id**: Always save it when submitting jobs
2. **Check queue first**: Before assuming job is complete
3. **Handle errors**: Check for node_errors in response
4. **Cleanup regularly**: Delete old history entries to save memory
5. **Don't delete files**: POST /history deletes records, not output files
6. **Use for tracking**: Link images back to generation parameters

---

## Testing Script

Run `test_comfyui_api_jobid.py` to explore these capabilities on your ComfyUI server.
