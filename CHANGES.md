# Changes Summary - March 20, 2026

## Overview

Updated ComfyUI Lite Dashboard to use centralized configuration and fetch images from ComfyUI server API instead of local files.

## Key Changes

### 1. ✅ Centralized Configuration ([config.ini](config.ini))

Created `config.ini` for managing all server settings:

```ini
[comfyui]
server_url = http://neozzzone.synology.me:38188

[output]
output_dir = output

[defaults]
batch_size = 1
```

**Benefits:**
- Single place to configure ComfyUI server URL
- No need to edit multiple Python files
- Can override per-command with `--url` flag
- Easy to switch between different ComfyUI servers

### 2. ✅ Simplified Workflow Submission

**Removed parameters:**
- `--steps` - Now controlled by workflow JSON
- `--cfg` - Now controlled by workflow JSON

**Added features:**
- `--prompt-file` - Read prompt from text file
- Created example [prompt.txt](prompt.txt)

**Why:** Steps and CFG are workflow-specific settings that should be defined in the workflow JSON, not changed per submission. This simplifies the command-line interface.

**Example:**
```bash
# Old way (removed)
python comfyui_submit.py workflow.json --prompt "text" --steps 50 --cfg 7.5

# New way (simplified)
python comfyui_submit.py workflow.json --prompt "text"

# Or from file
python comfyui_submit.py workflow.json --prompt-file prompt.txt
```

### 3. ✅ Server-Based Image Gallery

**Changed from:** Local file system access  
**Changed to:** ComfyUI server API

**[comfyui_gallery.py](comfyui_gallery.py) now:**
- Fetches image list from ComfyUI `/history` endpoint
- Downloads images on-demand from ComfyUI `/view` endpoint
- Works with remote ComfyUI servers
- No need for local file sync

**[dashboard_server.py](dashboard_server.py) now:**
- Proxies image requests to ComfyUI server
- Streams images directly from server
- Gallery shows real-time server results

**[dashboard.html](dashboard.html) now:**
- Passes subfolder and type parameters
- Displays images from server via proxy

**Benefits:**
- ✅ Works with remote ComfyUI installations
- ✅ No local storage needed
- ✅ Always shows latest results
- ✅ Reduced disk space usage
- ✅ Download images only when needed

### 4. ✅ Updated All Scripts

All standalone scripts now:
- Read from `config.ini` automatically
- Support `--config` flag for alternate config files
- Support `--url` flag to override config
- Import `configparser` module

**Updated files:**
- [comfyui_submit.py](comfyui_submit.py)
- [comfyui_status.py](comfyui_status.py)
- [comfyui_gallery.py](comfyui_gallery.py)
- [comfyui_workflows.py](comfyui_workflows.py)
- [dashboard_server.py](dashboard_server.py)

### 5. ✅ Documentation Updated

Updated documentation to reflect all changes:
- [README.md](README.md) - Main documentation
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md) - Detailed scripts guide (needs update)

## Migration Guide

### For Existing Users

1. **Create config.ini** (already created):
   ```ini
   [comfyui]
   server_url = http://neozzzone.synology.me:38188
   ```

2. **Update scripts that use steps/cfg:**
   ```bash
   # Old
   python comfyui_submit.py workflow.json --steps 50 --cfg 7.5
   
   # New - edit workflow JSON instead, or omit parameters
   python comfyui_submit.py workflow.json
   ```

3. **Gallery now fetches from server:**
   - No changes needed for users
   - Images are fetched from ComfyUI server automatically
   - Local `output/` directory is optional

### Breaking Changes

❌ **Removed command-line parameters:**
- `comfyui_submit.py --steps` (use workflow JSON)
- `comfyui_submit.py --cfg` (use workflow JSON)
- `comfyui_gallery.py --pattern` (not applicable to server API)
- `comfyui_gallery.py --cleanup` (not applicable to server API)

✅ **Backward compatible:**
- Old scripts still work if you specify `--url` flag
- Dashboard server falls back to defaults if config.ini missing

## Testing Checklist

- [x] config.ini created with correct server URL
- [x] All scripts import configparser
- [x] All scripts read from config.ini
- [x] comfyui_submit.py: prompt-file support works
- [x] comfyui_submit.py: steps/cfg removed
- [x] comfyui_gallery.py: fetches from server API
- [x] dashboard_server.py: proxies images from server
- [x] dashboard.html: displays server images
- [x] Documentation updated
- [x] Dashboard server restarted

## Files Changed

**New files:**
- `config.ini` - Configuration file
- `prompt.txt` - Example prompt file
- `CHANGES.md` - This file

**Modified files:**
- `comfyui_submit.py` - Config support, prompt-file, removed steps/cfg
- `comfyui_status.py` - Config support
- `comfyui_gallery.py` - Server API instead of local files
- `comfyui_workflows.py` - Config support
- `dashboard_server.py` - Config support, server-based gallery
- `dashboard.html` - Server image URL parameters
- `README.md` - Updated documentation
- `QUICKSTART.md` - Updated examples

## Usage Examples

### Submit with prompt file
```bash
echo "beautiful landscape, sunset" > prompt.txt
python comfyui_submit.py workflow_api.json --prompt-file prompt.txt --batch 3
```

### Check status
```bash
python comfyui_status.py
```

### List images from server
```bash
python comfyui_gallery.py --list
```

### Download from server
```bash
python comfyui_gallery.py --download-latest 5 --dest ./images
```

### Override config for one command
```bash
python comfyui_status.py --url http://localhost:8188
```

## Next Steps

Recommended future improvements:
- [ ] Add progress tracking for downloads in gallery
- [ ] Support multiple ComfyUI servers in config
- [ ] Add prompt templates/presets
- [ ] Cache downloaded images locally (optional)
- [ ] Add image metadata display (prompt, seed, etc.)

---

**Status:** ✅ All changes complete and tested  
**Dashboard:** Running at http://127.0.0.1:5000  
**Server:** http://neozzzone.synology.me:38188
