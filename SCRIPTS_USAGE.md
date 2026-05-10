# ComfyUI Standalone Scripts Documentation

Complete guide for using standalone Python scripts to interact with ComfyUI without the web interface.

## 📚 Table of Contents

- [Overview](#overview)
- [Script Naming Convention](#script-naming-convention)
- [Installation](#installation)
- [Scripts Reference](#scripts-reference)
  - [comfyui_submit.py](#comfyui_submitpy)
  - [comfyui_status.py](#comfyui_statuspy)
  - [comfyui_gallery.py](#comfyui_gallerypy)
  - [comfyui_workflows.py](#comfyui_workflowspy)
- [Common Usage Patterns](#common-usage-patterns)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

These standalone scripts provide command-line access to ComfyUI functionality:

- **Submit workflows** with custom parameters
- **Monitor queue status** in real-time
- **Browse and download** generated images
- **Manage workflow files** and validate JSON

All scripts can run independently without the web dashboard.

---

## Script Naming Convention

All scripts follow the naming pattern: `comfyui_<function>.py`

- **comfyui_submit.py** - Submit workflows to queue
- **comfyui_status.py** - Monitor queue and system status
- **comfyui_gallery.py** - Browse and download images
- **comfyui_workflows.py** - Manage workflow files

This makes it easy to find the right script using tab-completion: `python comfyui_<TAB>`

---

## Installation

### Prerequisites

- Python 3.8 or higher
- `requests` library

### Quick Setup

```bash
# Install required package
pip install requests

# Or use the virtual environment
pip install -r requirements.txt
```

All scripts are standalone - no web server or additional dependencies needed!

---

## Scripts Reference

### comfyui_submit.py

**Purpose:** Submit workflows to ComfyUI queue with custom parameters

#### Basic Usage

```bash
# Submit with default settings
python comfyui_submit.py workflow_api.json

# Submit with custom prompt
python comfyui_submit.py workflow_api.json --prompt "a beautiful landscape"

# Submit with all parameters
python comfyui_submit.py workflow_api.json \
  --prompt "portrait of a woman" \
  --batch 4 \
  --cfg 7.5 \
  --steps 50

# Use fixed seed for reproducibility
python comfyui_submit.py workflow_api.json --seed 12345

# Preview workflow before submitting
python comfyui_submit.py workflow_api.json --show-workflow
```

#### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--url` | | ComfyUI server URL | `http://neozzzone.synology.me:38188` |
| `--prompt` | `-p` | Text prompt for generation | (from workflow) |
| `--batch` | `-b` | Number of images to generate | (from workflow) |
| `--cfg` | `-c` | CFG scale value | (from workflow) |
| `--steps` | `-s` | Number of generation steps | (from workflow) |
| `--seed` | | Random seed (omit for random) | Random |
| `--show-workflow` | | Display modified workflow JSON | Off |

#### Output Example

```
============================================================
ComfyUI Workflow Submitter
============================================================

📂 Loading workflow: workflow_api.json

⚙️ Configuring parameters:
✓ Prompt set to: a beautiful landscape
✓ Batch size set to: 4
✓ CFG scale set to: 7.5
✓ Steps set to: 50
✓ Random seed: 847362819

🚀 Submitting to ComfyUI at http://neozzzone.synology.me:38188...
✅ Workflow submitted successfully!
   Prompt ID: 9a8f7b6c-5d4e-3f2a-1b0c-9d8e7f6a5b4c
   Queue Number: 5

✨ Done! Check ComfyUI for progress.
```

---

### comfyui_status.py

**Purpose:** Monitor ComfyUI queue and system status

#### Basic Usage

```bash
# Quick status check
python comfyui_status.py

# Show detailed information
python comfyui_status.py --details

# Watch status with auto-refresh (updates every 2 seconds)
python comfyui_status.py --watch

# Watch with custom refresh interval
python comfyui_status.py --watch --interval 5

# Get raw JSON output (for scripting)
python comfyui_status.py --json

# Connect to different ComfyUI server
python comfyui_status.py --url http://localhost:8188
```

#### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--url` | | ComfyUI server URL | `http://neozzzone.synology.me:38188` |
| `--watch` | `-w` | Continuous refresh mode | Off |
| `--interval` | `-i` | Refresh interval (seconds) | 2 |
| `--details` | `-d` | Show detailed queue info | Off |
| `--json` | | Output raw JSON | Off |

#### Output Example

**Simple status:**
```
============================================================
ComfyUI Status
============================================================
URL: http://neozzzone.synology.me:38188
Time: 2026-03-20 14:30:45
------------------------------------------------------------

Status: 🟢 RUNNING
Running: 1
Pending: 3
Total: 4
```

**Detailed status:**
```
Status: 🟢 RUNNING
Running: 1
Pending: 3
Total: 4

📋 Queue Details:

  Currently Running:
    1. Queue #47 - ID: 9a8f7b6c...

  Pending in Queue:
    1. Queue #48 - ID: 7f6e5d4c...
    2. Queue #49 - ID: 3b2a1c0d...
    3. Queue #50 - ID: 8e9f0a1b...

💻 System Stats:
    OS: Windows
    Python: 3.11.0
    Devices:
      - NVIDIA GeForce RTX 4090: GPU
```

**Watch mode:**
```
⏰ 2026-03-20 14:30:45
🔗 http://neozzzone.synology.me:38188
------------------------------------------------------------
Status: 🟢 RUNNING
Running: 1
Pending: 2
Total: 3
------------------------------------------------------------
Refreshing every 2 seconds... (Ctrl+C to stop)
```

---

### comfyui_gallery.py

**Purpose:** Browse and download generated images from ComfyUI output

#### Basic Usage

```bash
# List all images
python comfyui_gallery.py --list

# List with detailed information
python comfyui_gallery.py --list --details

# List only recent 10 images
python comfyui_gallery.py --list --limit 10

# Search for specific images
python comfyui_gallery.py --list --pattern "nianna*"

# Download latest image
python comfyui_gallery.py --download-latest

# Download latest 5 images
python comfyui_gallery.py --download-latest 5

# Download to specific directory
python comfyui_gallery.py --download-latest 3 --dest ./my_images

# Download specific images by index
python comfyui_gallery.py --list
python comfyui_gallery.py --download 1 3 5

# Clean up old images (keep only 50 most recent)
python comfyui_gallery.py --cleanup 50

# Preview cleanup without deleting
python comfyui_gallery.py --cleanup 50 --dry-run
```

#### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output-dir` | | ComfyUI output directory | `output` |
| `--list` | `-l` | List all images | Off |
| `--details` | `-d` | Show detailed info | Off |
| `--limit` | | Limit number of results | All |
| `--pattern` | `-p` | Filter by filename pattern | `*` |
| `--download-latest` | | Download N latest images | - |
| `--download` | | Download by index numbers | - |
| `--dest` | | Destination directory | `.` (current) |
| `--cleanup` | | Delete old images, keeping N | - |
| `--dry-run` | | Preview cleanup without deleting | Off |

#### Output Example

**List mode:**
```
============================================================
ComfyUI Gallery Manager
============================================================
Output directory: C:\...\comfyui_frontend\output
------------------------------------------------------------

🖼️  Found 15 image(s)

[1] nianna_test_00042.png (2.34 MB)
[2] nianna_test_00041.png (2.28 MB)
[3] nianna_test_00040.png (2.31 MB)
...
```

**Download mode:**
```
📥 Downloading 3 image(s) to ./my_images

✅ Downloaded: nianna_test_00042.png
   → ./my_images/nianna_test_00042.png
✅ Downloaded: nianna_test_00041.png
   → ./my_images/nianna_test_00041.png
✅ Downloaded: nianna_test_00040.png
   → ./my_images/nianna_test_00040.png

✨ Downloaded 3/3 image(s)
```

**Cleanup mode:**
```
🧹 Would delete 25 image(s):
   - nianna_test_00001.png
   - nianna_test_00002.png
   ...

Run without --dry-run to actually delete these files
```

---

### comfyui_workflows.py

**Purpose:** Manage and inspect ComfyUI workflow JSON files

#### Basic Usage

```bash
# List all workflow files
python comfyui_workflows.py --list

# List with detailed analysis
python comfyui_workflows.py --list --details

# List workflows matching pattern
python comfyui_workflows.py --list --pattern "nianna*.json"

# Inspect specific workflow
python comfyui_workflows.py --inspect workflow_api.json

# Inspect and show full JSON
python comfyui_workflows.py --inspect workflow_api.json --json

# Validate workflow structure
python comfyui_workflows.py --validate workflow_api.json

# Search in different directory
python comfyui_workflows.py --list --dir ./workflows
```

#### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--dir` | | Directory with workflows | `.` (current) |
| `--list` | `-l` | List all workflow files | Off |
| `--details` | `-d` | Show detailed information | Off |
| `--pattern` | `-p` | Filter by filename pattern | `*.json` |
| `--inspect` | `-i` | Inspect specific workflow | - |
| `--validate` | `-v` | Validate workflow structure | - |
| `--json` | `-j` | Show raw JSON (with inspect) | Off |

#### Output Example

**List mode:**
```
============================================================
ComfyUI Workflow Manager
============================================================
Directory: C:\...\comfyui_frontend
------------------------------------------------------------

📋 Found 2 workflow(s)

[1] workflow_api.json
    Size: 1,534 bytes | Path: .\workflow_api.json
[2] workflow_test.json
    Size: 2,107 bytes | Path: .\workflow_test.json
```

**Inspect mode:**
```
🔍 Inspecting: workflow_api.json
------------------------------------------------------------

📊 Summary:
   Total nodes: 8
   File size: 1,534 bytes

📦 Node Types:
   CLIPLoader: 1
   CLIPTextEncode: 1
   ConditioningZeroOut: 1
   EmptySD3LatentImage: 1
   KSampler: 1
   LoraLoaderModelOnly: 1
   ModelSamplingAuraFlow: 1
   SaveImage: 1
   UNETLoader: 1
   VAEDecode: 1
   VAELoader: 1

🔗 Nodes:
   [103] Load VAE (VAELoader)
   [104] Load CLIP (CLIPLoader)
   [105] Load Diffusion Model (UNETLoader)
   [106] KSampler (KSampler)
   [107] EmptySD3LatentImage (EmptySD3LatentImage)
   [108] CLIP Text Encode (Positive Prompt) (CLIPTextEncode)
   [109] VAE Decode (VAEDecode)
   [110] ModelSamplingAuraFlow (ModelSamplingAuraFlow)
   [114] Load LoRA (LoraLoaderModelOnly)
   [123] Save Image (SaveImage)
   [128] ConditioningZeroOut (ConditioningZeroOut)
```

**Validate mode:**
```
✓ Validating: workflow_api.json
✅ Valid JSON structure
✅ Contains 8 node(s)
✅ 8/8 nodes have valid structure

✅ Workflow is valid!
```

---

## Common Usage Patterns

### Complete Workflow: Submit → Monitor → Download

```bash
# 1. Check status before submitting
python comfyui_status.py

# 2. Submit workflow
python comfyui_submit.py workflow_api.json --prompt "beautiful landscape" --batch 3

# 3. Watch progress
python comfyui_status.py --watch

# 4. Download results when done
python comfyui_gallery.py --download-latest 3 --dest ./results
```

### Batch Processing Multiple Prompts

```bash
# Submit multiple variations
python comfyui_submit.py workflow_api.json --prompt "sunset over ocean" --seed 1000
python comfyui_submit.py workflow_api.json --prompt "mountain landscape" --seed 1001
python comfyui_submit.py workflow_api.json --prompt "forest path" --seed 1002

# Monitor all jobs
python comfyui_status.py --watch
```

### Daily Workflow Management

```bash
# Morning: Check what workflows are available
python comfyui_workflows.py --list --details

# Generate some images
python comfyui_submit.py workflow_api.json --prompt "..." --batch 5

# Evening: Clean up old images
python comfyui_gallery.py --cleanup 100 --dry-run
python comfyui_gallery.py --cleanup 100
```

### Debugging Workflow Issues

```bash
# Validate workflow file
python comfyui_workflows.py --validate workflow_api.json

# Inspect workflow structure
python comfyui_workflows.py --inspect workflow_api.json --json

# Test submission with preview
python comfyui_submit.py workflow_api.json --show-workflow

# Check if ComfyUI is responding
python comfyui_status.py
```

---

## Configuration

### ComfyUI Server URL

All scripts use `http://neozzzone.synology.me:38188` by default.

To change for individual commands:
```bash
python comfyui_status.py --url http://localhost:8188
python comfyui_submit.py workflow.json --url http://localhost:8188
```

To change default URL, edit each script:
```python
# Change this line in each script
parser.add_argument('--url', default='http://YOUR_URL:PORT', ...)
```

### Output Directory

For `comfyui_gallery.py`, the default output directory is `output/`.

To use a different directory:
```bash
# One-time use
python comfyui_gallery.py --list --output-dir /path/to/comfyui/output

# Change default in script
parser.add_argument('--output-dir', default='/your/path/here', ...)
```

---

## Troubleshooting

### "Cannot connect to ComfyUI"

**Symptoms:**
```
❌ Cannot connect to ComfyUI at http://...
   Make sure ComfyUI is running and accessible
```

**Solutions:**
1. Check if ComfyUI is running
2. Verify the URL is correct
3. Test connection: `curl http://neozzzone.synology.me:38188/queue`
4. Check firewall settings

### "Workflow file not found"

**Symptoms:**
```
❌ Error: Workflow file 'workflow.json' not found
```

**Solutions:**
1. Check file exists: `dir workflow.json` (Windows) or `ls workflow.json` (Linux/Mac)
2. Use full path: `python comfyui_submit.py C:\path\to\workflow.json`
3. List available workflows: `python comfyui_workflows.py --list`

### "Invalid JSON in workflow file"

**Symptoms:**
```
❌ Error: Invalid JSON in workflow file: Expecting ',' delimiter
```

**Solutions:**
1. Validate JSON: `python comfyui_workflows.py --validate workflow.json`
2. Use online JSON validator
3. Check for missing commas, brackets, or quotes
4. Re-export workflow from ComfyUI interface

### "No images found in output directory"

**Symptoms:**
```
📭 No images found in output directory
   Directory: C:\...\output
```

**Solutions:**
1. Check ComfyUI output directory location
2. Update path: `python comfyui_gallery.py --output-dir "C:\ComfyUI\output"`
3. Verify images were actually generated in ComfyUI
4. Check if running on remote server (need to access remote files)

### Queue not updating

**Symptoms:**
Status shows 0 running, 0 pending even though jobs are queued

**Solutions:**
1. Refresh: `python comfyui_status.py`
2. Check ComfyUI web interface directly
3. Verify URL is correct
4. Restart ComfyUI if needed

---

## Advanced Tips

### Integration with Shell Scripts

**Windows (PowerShell):**
```powershell
# Generate batch of images
$prompts = @("sunset", "mountain", "forest")
foreach ($prompt in $prompts) {
    python comfyui_submit.py workflow_api.json --prompt $prompt
}
```

**Linux/Mac (Bash):**
```bash
#!/bin/bash
# Auto-download new images every minute
while true; do
    python comfyui_gallery.py --download-latest 1 --dest ./auto_download
    sleep 60
done
```

### Using with Task Scheduler

Schedule automated image generation:

1. Create batch file `generate_daily.bat`:
```batch
@echo off
cd C:\path\to\comfyui_frontend
python comfyui_submit.py workflow_api.json --prompt "daily art" --batch 5
```

2. Add to Windows Task Scheduler to run daily

### JSON Output for Scripting

Use `--json` flag to parse output programmatically:

```python
import subprocess
import json

# Get status as JSON
result = subprocess.run(
    ['python', 'comfyui_status.py', '--json'],
    capture_output=True,
    text=True
)

status = json.loads(result.stdout)
if status['queue_running']:
    print("ComfyUI is busy")
else:
    print("ComfyUI is ready")
```

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Submit workflow | `python comfyui_submit.py workflow.json` |
| Check status | `python comfyui_status.py` |
| Watch queue | `python comfyui_status.py --watch` |
| List images | `python comfyui_gallery.py --list` |
| Download latest | `python comfyui_gallery.py --download-latest` |
| List workflows | `python comfyui_workflows.py --list` |
| Validate workflow | `python comfyui_workflows.py --validate file.json` |
| Get help | `python <script> --help` |

---

**Need more help?** Run any script with `--help` flag for detailed usage information.

```bash
python comfyui_submit.py --help
python comfyui_status.py --help
python comfyui_gallery.py --help
python comfyui_workflows.py --help
```
