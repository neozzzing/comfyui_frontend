# ComfyUI Lite Dashboard ⚡

A lightweight, mobile-responsive web dashboard for ComfyUI that simplifies workflow management and image generation, plus standalone Python scripts for command-line access.

## Features ✨

### Web Dashboard
- 📱 **Responsive Design** - Works seamlessly on mobile devices and desktop browsers
- 🎨 **Workflow Management** - Select and run pre-saved ComfyUI workflows
- ✍️ **Easy Input** - Modify prompts, batch sizes, CFG scale, and steps
- 🖼️ **Image Upload** - Upload reference images (optional)
- 📊 **Queue Monitoring** - Real-time queue status and progress tracking
- 🎯 **System Status** - See if ComfyUI is idle or running
- 🖼️ **Gallery View** - Browse and download generated images
- 💾 **One-Click Save** - Download images directly to your device

### Standalone Scripts
- 🚀 **comfyui_submit.py** - Submit workflows from command line
- 📊 **comfyui_status.py** - Monitor queue status with watch mode
- 🖼️ **comfyui_gallery.py** - Browse and download images via CLI
- 📋 **comfyui_workflows.py** - Inspect and validate workflow files

## Screenshots

### Desktop View
Beautiful gradient design with side-by-side layout for workflow settings and status monitoring.

### Mobile View
Fully responsive design that adapts to smaller screens with stacked cards.

## Installation 🚀

### Prerequisites

1. **ComfyUI** running and accessible (e.g., `http://neozzzone.synology.me:38188`)
2. **Python 3.8+**

### Setup Steps

1. **Configure ComfyUI server:**
   
   Edit `config.ini` to set your ComfyUI server URL:
   ```ini
   [comfyui]
   server_url = http://your-server:38188
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Dashboard Server:**
   ```bash
   python dashboard_server.py
   ```
   Server automatically reads `config.ini` for ComfyUI URL

4. **Open the Dashboard:**
   - Navigate to `http://127.0.0.1:5000` in your browser
   - Or open `dashboard.html` directly (will connect to server)

## Usage 📖

### Option 1: Web Dashboard

Perfect for visual, interactive workflow management.

#### Generating Images

1. **Select Workflow** - Choose from available workflow JSON files
2. **Enter Prompt** - Type your image generation prompt
3. **Adjust Settings**:
   - Batch Size: Number of images to generate (1-10)
   - CFG Scale: Guidance strength (1-20)
   - Steps: Generation steps (1-150)
4. **Upload Image** (Optional) - Add a reference image
5. **Click Generate** - Submit to ComfyUI queue

### Monitoring Progress

The **Queue Status** section shows:
- **System Status** - Idle / Running / Error
- **Queue Position** - Your position in queue
- *# Viewing Results

Generated images appear in the **Gallery**:
- Hover over images to see actions
- **💾 Save** - Download to your device
- **🔍 View** - Open full size in new tab
- Images are sorted by creation time (newest first)
- Shows last 50 generated images

### Option 2: Standalone Scripts

Perfect for automation, scripting, and command-line workflows.

```bash
# Submit with prompt from file
python comfyui_submit.py workflow_api.json --prompt-file prompt.txt --batch 3

# Monitor queue status
python comfyui_status.py --watch

# List images from ComfyUI server
python comfyui_gallery.py --list

# Download latest images from server
python comfyui_gallery.py --download-latest 5 --dest ./my_images

# Validate workflow files
python comfyui_workflows.py --validate workflow_api.json
```

**Note:** Steps and CFG parameters are controlled by the workflow JSON file. Scripts focus on prompt and batch size.

**📖 See [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md) for complete standalone scripts documentation.**ns
- **💾 Save** - Download to your device
- **🔍 View** - Open full size in new tab
- Images are sorted by creation time (newest first)
- Shows last 50 generated images

## Configuration ⚙️

All scripts and the dashboard read from `config.ini`:

```ini
[comfyui]
server_url = http://neozzzone.synology.me:38188

[output]
output_dir = output

[defaults]
batch_size = 1
```

You can override the URL for individual commands:
```bash
python comfyui_status.py --url http://localhost:8188
```

### Image Gallery

The gallery **fetches images directly from ComfyUI server** via its API, not from local files. This means:
- ✅ Works with remote ComfyUI servers
- ✅ No need to sync files locally
- ✅ Always shows the latest server results
- ✅ Downloads on-demand when you need themFYUI_URL = "http://127.0.0.1:8188"  # Your ComfyUI address
OUTPUT_DIR = "output"                   # ComfyUI output directory
```

### Port Configuration

Change the dashboard port in `dashboard_server.py`:
config.ini              # Configuration file (ComfyUI URL, defaults)
├── prompt.txt              # Example prompt file
├── dashboard.html          # Frontend web interface
├── dashboard_server.py     # Backend Flask server
├── comfyui_submit.py      # Standalone: Submit workflows
├── comfyui_status.py      # Standalone: Monitor queue status
├── comfyui_gallery.py     # Standalone: Browse/download images from server
├── comfyui_workflows.py   # Standalone: Manage workflow files
├── requirements.txt        # Python dependencies
├── workflow_api.json       # Example ComfyUI workflow
├── nianna_test.py         # Original test script
├── output/                # Optional: local cache (auto-created)
├── README.md              # This file
├── SCRIPTS_USAGE.md       # Detailed standalone scripts guide
└── QUICKSTART.md          # Quick referenc
const API_BASE = 'http://127.0.0.1:5000';  // Match your port
```

## File Structure 📁

```
comfyui_frontend/
├── dashboard.html          # Frontend web interface
├── dashboard_server.py     # Backend Flask server
├── comfyui_submit.py      # Standalone: Submit workflows
├── comfyui_status.py      # Standalone: Monitor queue status
├── comfyui_gallery.py     # Standalone: Browse/download images
├── comfyui_workflows.py   # Standalone: Manage workflow files
├── requirements.txt        # Python dependencies
├── workflow_api.json       # Example ComfyUI workflow
├── nianna_test.py         # Original test script
├── output/                # Generated images (auto-created)
├── README.md              # This file
└── SCRIPTS_USAGE.md       # Detailed standalone scripts guide
```

## API Endpoints 🔌

The dashboard server provides these REST endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/workflows` | GET | List available workflows |
| `/api/workflow/<filename>` | GET | Get workflow details |
| `/api/submit` | POST | Submit workflow to queue |
| `/api/status` | GET | Get queue status |
| `/api/gallery` | GET | List generated images |
| `/api/image/<filename>` | GET | Serve image file |
| `/api/download/<filename>` | GET | Download image |
| `/api/health` | GET | Health check |

## Troubleshooting 🔧

### Dashboard can't connect to ComfyUI

1. Verify ComfyUI is running: `http://127.0.0.1:8188` in browser
2. Check ComfyUI console for errors
3. Ensure no firewall is blocking port 8188

### No images in gallery

1. Check ComfyUI output directory location
2. Update `OUTPUT_DIR` in `dashboard_server.py` if needed
3. Verify images are being saved by ComfyUI

### Queue not updating

1. Check browser console for errors (F12)
2. Verify dashboard server is running
3. Check CORS is enabled (flask-cors installed)

### Port already in use

```
Error: Address already in use
```

Solution: Change port in `dashboard_server.py` and `dashboard.html`

## Mobile Access 📱

To access from mobile devices on same network:

1. Find your computer's IP address:
   ```bash
   ipconfig  # Windows
   ifconfig  # Mac/Linux
   ```

2. On mobile browser, navigate to:
   ```
   http://YOUR_IP_ADDRESS:5000
   ```

3. Ensure firewall allows connections on port 5000

## Advanced Features 🎯

### Adding Custom Workflows

1. Save ComfyUI workflow as JSON (from ComfyUI interface)
2. Place JSON file in the same directory as `dashboard_server.py`
3. Workflow will automatically appear in dropdown

### Modifying Workflow Parameters

The server automatically modifies these nodes:
- **Node 108** - Prompt text
- **Node 107** - Batch size
- **Node 106** - CFG scale, steps, seed

To modify different nodes, edit the `submit_workflow()` function in `dashboard_server.py`.

## Security Notes 🔒

This dashboard is designed for **local network use**:
- No authentication built-in
- Assumes trusted network environment
- For production use, add authentication and HTTPS

## Contributing 🤝

Suggestions and improvements welcome!

## License 📄

Free to use and modify for personal and commercial projects.

## Credits 👏

Built for ComfyUI community with ❤️

---

**Enjoy your simplified ComfyUI experience!** 🎨✨
