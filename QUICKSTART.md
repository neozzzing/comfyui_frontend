# Quick Start Guide

## Configuration

**ComfyUI Server:** Configured in `config.ini`

Current default: `http://neozzzone.synology.me:38188`

Edit `config.ini` to change server URL:
```ini
[comfyui]
server_url = http://your-server:port
```

## What's Available

### 🌐 Web Dashboard
- **URL:** http://127.0.0.1:5000
- **Status:** ✅ Running
- **Features:** Full interactive UI with workflow selection, status monitoring, and gallery

### 📝 Standalone Scripts

All scripts work independently without the web interface:

```bash
# 1. Submit workflows (reads config.ini automatically)
python comfyui_submit.py workflow_api.json --prompt "your prompt" --batch 3

# Or read prompt from file
python comfyui_submit.py workflow_api.json --prompt-file prompt.txt

# 2. Monitor status
python comfyui_status.py --watch

# 3. Download images (fetches from ComfyUI server)
python comfyui_gallery.py --download-latest 5

# 4. Manage workflows
python comfyui_workflows.py --list
```

## Quick Commands

### Test Everything Works

```bash
# Check ComfyUI connection
python comfyui_status.py

# List available workflows
python comfyui_workflows.py --list

# Submit a test workflow
python comfyui_submit.py workflow_api.json --prompt "test image"

# List generated images
python comfyui_gallery.py --list
```

### Daily Workflow

```bash
# Morning: Generate batch of images using prompt file
echo "beautiful artwork, masterpiece" > prompt.txt
python comfyui_submit.py workflow_api.json --prompt-file prompt.txt --batch 5

# Check progress
python comfyui_status.py

# Download from ComfyUI server when ready
python comfyui_gallery.py --download-latest 5 --dest ./today
```

## Configuration

**Current ComfyUI Server:** Read from `config.ini`

The `config.ini` file contains:
- ComfyUI server URL
- Default settings
- Optional local output directory

All scripts automatically read this file. You can override with `--url` flag.

## Documentation

- **[README.md](README.md)** - Overview and web dashboard guide
- **[SCRIPTS_USAGE.md](SCRIPTS_USAGE.md)** - Complete standalone scripts documentation

## Get Help

```bash
python comfyui_submit.py --help
python comfyui_status.py --help
python comfyui_gallery.py --help
python comfyui_workflows.py --help
```

## File Naming Convention

All standalone scripts follow: `comfyui_<function>.py`

- `comfyui_submit.py` - Submit workflows
- `comfyui_status.py` - Monitor status
- `comfyui_gallery.py` - Manage images
- `comfyui_workflows.py` - Manage workflows

Use tab-completion: `python comfyui_<TAB>`

---

**Ready to start!** 🚀

Try: `python comfyui_status.py` to check if ComfyUI is accessible.
