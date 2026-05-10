# ComfyUI Lite Dashboard

A lightweight, mobile-responsive web dashboard for ComfyUI that simplifies workflow management and image generation, plus standalone Python scripts for command-line access.

## Features

### Web Dashboard
- **Responsive Design** - Works seamlessly on mobile devices and desktop browsers
- **Workflow Management** - Select, upload, and run pre-saved ComfyUI workflows
- **Easy Input** - Modify prompts, batch sizes; read prompts from file
- **Image Upload** - Upload reference images (optional)
- **Queue Monitoring** - Real-time queue status and progress tracking via WebSocket
- **Live Logs** - Stream ComfyUI execution logs in real-time
- **System Status** - See if ComfyUI is idle or running
- **Gallery View** - Browse generated images with modal preview, fetched from ComfyUI server API
- **Local Gallery** - Store and manage images locally with metadata
- **Job History** - Track submitted jobs with timestamps
- **Authentication** - HTTP Basic Auth with admin and guest accounts
- **HTTPS/SSL** - Optional TLS encryption with self-signed or real certificates
- **Save & Download** - Download images directly to your device

### Standalone Scripts
- **comfyui_submit.py** - Submit workflows from command line
- **comfyui_status.py** - Monitor queue status with watch mode
- **comfyui_gallery.py** - Browse and download images via CLI
- **comfyui_workflows.py** - Inspect and validate workflow files

## Screenshots

### Desktop View
Beautiful gradient design with side-by-side layout for workflow settings and status monitoring.

### Mobile View
Fully responsive design that adapts to smaller screens with stacked cards.

## Installation

### Prerequisites

1. **ComfyUI** running and accessible (e.g., `http://your-server:8188`)
2. **Python 3.8+**

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/neozzzing/comfyui_frontend.git
   cd comfyui_frontend
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure ComfyUI server:**
   
   Edit `config.ini` to set your ComfyUI server URL:
   ```ini
   [comfyui]
   server_url = http://your-server:8188
   ```

4. **Start the Dashboard Server:**
   ```bash
   python dashboard_server.py
   ```

5. **Open the Dashboard:**
   - Navigate to `http://127.0.0.1:5000` in your browser
   - Default login: `admin` / `admin`
   - Guest login: `guest` / `guest` (gallery access only)

## Usage

### Option 1: Web Dashboard

Perfect for visual, interactive workflow management.

#### Generating Images

1. **Select Workflow** - Choose from available workflow JSON files
2. **Enter Prompt** - Type your image generation prompt (or load from file)
3. **Adjust Settings** - Batch size (1-10)
4. **Upload Image** (Optional) - Add a reference image
5. **Click Generate** - Submit to ComfyUI queue

### Monitoring Progress

The **Queue Status** section shows:
- **System Status** - Idle / Running / Error
- **Queue Position** - Your position in queue
- **Live Logs** - Real-time ComfyUI execution logs via WebSocket
- **Progress Bar** - Step-by-step generation progress

### Viewing Results

Generated images appear in the **Gallery**:
- **Single click** - Opens modal with larger image view
- **Double click** - Opens image in new browser tab
- **Save** - Download to your device
- **ESC / click outside** - Close modal
- Images are sorted newest first
- Gallery fetches images directly from ComfyUI server API

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

See [SCRIPTS_USAGE.md](SCRIPTS_USAGE.md) for complete standalone scripts documentation.

## Configuration

All scripts and the dashboard read from `config.ini`:

```ini
[comfyui]
server_url = http://your-server:8188

[output]
output_dir = output

[defaults]
batch_size = 1

[dashboard]
port = 5000

# Authentication
auth_enabled = true
auth_username = admin
auth_password = admin

# Guest account (gallery access only)
guest_enabled = true
guest_username = guest
guest_password = guest

# HTTPS/SSL (optional)
ssl_enabled = false
ssl_cert = cert.pem
ssl_key = key.pem
```

You can override the URL for individual commands:
```bash
python comfyui_status.py --url http://localhost:8188
```

### Image Gallery

The gallery **fetches images directly from ComfyUI server** via its API, not from local files. This means:
- Works with remote ComfyUI servers
- No need to sync files locally
- Always shows the latest server results
- Downloads on-demand when you need them

## File Structure

```
comfyui_frontend/
├── config.ini              # Configuration (server URL, auth, SSL)
├── dashboard.html          # Frontend web interface
├── dashboard_server.py     # Backend Flask server
├── comfyui_submit.py       # Standalone: Submit workflows
├── comfyui_status.py       # Standalone: Monitor queue status
├── comfyui_gallery.py      # Standalone: Browse/download images
├── comfyui_workflows.py    # Standalone: Manage workflow files
├── png_metadata.py         # PNG metadata extraction
├── comfyui_rerun.py        # Re-run previous jobs
├── check_job.py            # Check job status by ID
├── dump_job_data.py        # Dump job data for debugging
├── prompt.txt              # Example prompt file
├── favicon.svg             # Dashboard favicon
├── requirements.txt        # Python dependencies
├── history/                # Job history (JSON records)
├── output/                 # Local image cache
├── gallery/                # Local gallery storage
├── thumbnails/             # Generated thumbnails
├── workflows/              # Workflow JSON files
├── start_dashboard.bat     # Windows: start dashboard
├── stop_dashboard.bat      # Windows: stop dashboard
├── restart_dashboard.bat   # Windows: restart dashboard
├── README.md               # This file
├── QUICKSTART.md           # Quick reference
└── SCRIPTS_USAGE.md        # Detailed scripts guide
```

## API Endpoints

The dashboard server provides these REST endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/workflows` | GET | List available workflows |
| `/api/workflows/upload` | POST | Upload a workflow file |
| `/api/workflow/<filename>` | GET | Get workflow details |
| `/api/submit` | POST | Submit workflow to queue |
| `/api/status` | GET | Get queue status |
| `/api/logs` | GET | Get live execution logs |
| `/api/progress` | GET | Get generation progress |
| `/api/gallery` | GET | List images from ComfyUI server |
| `/api/gallery-local` | GET | List locally stored images |
| `/api/gallery/store` | POST | Store image locally |
| `/api/gallery/list` | GET | List local gallery images |
| `/api/gallery/image/<path>` | GET | Serve local gallery image |
| `/api/gallery/workflow/<path>` | GET | Get workflow for gallery image |
| `/api/image/<filename>` | GET | Serve image from ComfyUI |
| `/api/download/<filename>` | GET | Download image |
| `/api/history` | GET | List job history |
| `/api/history/<filename>` | GET | Get specific history entry |
| `/api/job/<prompt_id>` | GET | Get job details by prompt ID |
| `/api/free` | POST | Free VRAM on ComfyUI server |
| `/api/health` | GET | Health check |

## Troubleshooting

### Dashboard can't connect to ComfyUI

1. Verify ComfyUI is running: check `server_url` in `config.ini`
2. Check ComfyUI console for errors
3. Ensure no firewall is blocking the port

### No images in gallery

1. Verify ComfyUI is generating images
2. Check that `server_url` is correct in `config.ini`
3. Try the local gallery mode if server is on the same machine

### Port already in use

Change the port in `config.ini`:
```ini
[dashboard]
port = 5001
```

## Mobile Access

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

3. Ensure firewall allows connections on the dashboard port

## Security

- **Authentication** - HTTP Basic Auth enabled by default (configure in `config.ini`)
- **Guest accounts** - Read-only gallery access for shared viewing
- **HTTPS/SSL** - Optional TLS encryption; generate a self-signed cert:
  ```bash
  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
  ```
- Designed primarily for **local/trusted network** use

## Contributing

Suggestions and improvements welcome!

## License

Free to use and modify for personal and commercial projects.
