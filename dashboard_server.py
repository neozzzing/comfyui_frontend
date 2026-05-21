"""
ComfyUI Lite Dashboard - Backend Server
Provides REST API for the dashboard frontend to interact with ComfyUI
"""

# Set UTF-8 encoding for stdout/stderr on Windows (must be first)
import sys
import io
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from flask_cors import CORS
import json
from functools import wraps
import requests
import uuid
import os
import glob
import re
import configparser
from datetime import datetime
import time
from pathlib import Path
import signal
import psutil
import subprocess
import logging
import hashlib
import threading
from collections import deque
from io import BytesIO
try:
    import websocket as ws_client
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("⚠️  websocket-client not installed - live logs/progress disabled (pip install websocket-client)")
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("\u26a0\ufe0f  Pillow not installed - thumbnails disabled (pip install Pillow)")

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# ── Shared client ID so WebSocket listener receives progress for our prompts ──
SHARED_CLIENT_ID = str(uuid.uuid4())

# ── Live log & progress state (fed by WebSocket listener) ──────────
_log_lock = threading.Lock()
_log_entries = deque(maxlen=200)  # Recent log messages from ComfyUI
_log_seq = 0  # Monotonic sequence counter for each log entry

_progress_lock = threading.Lock()
_progress_state = {
    "value": 0,
    "max": 0,
    "node": None,
    "prompt_id": None,
    "running": False,
}


def _add_log(message, level="info"):
    """Thread-safe: append a log entry."""
    global _log_seq
    with _log_lock:
        _log_seq += 1
        _log_entries.append({
            "seq": _log_seq,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "level": level,
        })


def _set_progress(value=0, max_val=0, node=None, prompt_id=None, running=False):
    with _progress_lock:
        _progress_state["value"] = value
        _progress_state["max"] = max_val
        _progress_state["node"] = node
        _progress_state["prompt_id"] = prompt_id
        _progress_state["running"] = running


class _ComfyWSListener(threading.Thread):
    """Background thread that connects to ComfyUI WebSocket and streams events."""

    daemon = True  # dies when main process exits

    def __init__(self, comfyui_url):
        super().__init__(name="comfy-ws-listener")
        # Derive ws:// URL from http:// URL
        self._http_url = comfyui_url.rstrip("/")
        ws_url = self._http_url.replace("https://", "wss://").replace("http://", "ws://")
        self._client_id = SHARED_CLIENT_ID
        self._ws_url = f"{ws_url}/ws?clientId={self._client_id}"
        self._running = True
        self._current_node_titles = {}  # node_id -> title mapping from prompt

    def run(self):
        while self._running:
            try:
                _add_log("Connecting to ComfyUI WebSocket...", "info")
                ws = ws_client.WebSocketApp(
                    self._ws_url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open,
                )
                ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                _add_log(f"WebSocket error: {e}", "error")
            if self._running:
                time.sleep(5)  # Reconnect delay

    def stop(self):
        self._running = False

    # ── WebSocket callbacks ──────────────────────────────────────
    def _on_open(self, ws):
        _add_log("Connected to ComfyUI server", "success")

    def _on_close(self, ws, close_status_code, close_msg):
        _add_log("Disconnected from ComfyUI server", "warning")
        _set_progress(running=False)

    def _on_error(self, ws, error):
        _add_log(f"WebSocket error: {error}", "error")

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return  # binary frame (preview image) – ignore

        msg_type = data.get("type", "")
        msg_data = data.get("data", {})

        if msg_type == "status":
            queue_remaining = (
                msg_data.get("status", {})
                .get("exec_info", {})
                .get("queue_remaining", 0)
            )
            _add_log(f"Queue remaining: {queue_remaining}", "info")

        elif msg_type == "execution_start":
            prompt_id = msg_data.get("prompt_id", "?")
            _add_log(f"Execution started  [prompt {prompt_id[:8]}…]", "success")
            self._load_node_titles(prompt_id)
            _set_progress(value=0, max_val=0, prompt_id=prompt_id, running=True)

        elif msg_type == "execution_cached":
            nodes = msg_data.get("nodes", [])
            if nodes:
                _add_log(f"Cached nodes skipped: {len(nodes)}", "info")

        elif msg_type == "executing":
            node_id = msg_data.get("node")
            prompt_id = msg_data.get("prompt_id", "")
            if node_id is None:
                # Execution finished
                _add_log(f"Execution finished  [prompt {prompt_id[:8]}…]", "success")
                _set_progress(running=False)
            else:
                title = self._current_node_titles.get(node_id, node_id)
                _add_log(f"Executing node: {title}", "info")
                _set_progress(
                    value=0, max_val=0, node=title,
                    prompt_id=prompt_id, running=True,
                )

        elif msg_type == "progress":
            value = msg_data.get("value", 0)
            max_val = msg_data.get("max", 0)
            prompt_id = msg_data.get("prompt_id", "")
            with _progress_lock:
                cur_node = _progress_state.get("node")
            pct = round(value / max_val * 100) if max_val > 0 else 0
            # Log progress at key milestones to avoid spam
            if pct in (1, 25, 50, 75, 100) or value == 1:
                node_txt = f" [{cur_node}]" if cur_node else ""
                _add_log(f"Progress{node_txt}: {value}/{max_val} ({pct}%)", "info")
            _set_progress(
                value=value, max_val=max_val, node=cur_node,
                prompt_id=prompt_id, running=True,
            )

        elif msg_type == "executed":
            node_id = msg_data.get("node", "")
            title = self._current_node_titles.get(node_id, node_id)
            _add_log(f"Node completed: {title}", "success")

        elif msg_type == "execution_error":
            node_id = msg_data.get("node_id", "")
            err_type = msg_data.get("exception_type", "Error")
            err_msg = msg_data.get("exception_message", "Unknown error")
            title = self._current_node_titles.get(node_id, node_id)
            _add_log(f"Error in {title}: {err_type} – {err_msg}", "error")
            _set_progress(running=False)

    def _load_node_titles(self, prompt_id):
        """Fetch the prompt from /history to map node IDs -> class_type (titles)."""
        self._current_node_titles = {}
        try:
            resp = requests.get(f"{self._http_url}/history/{prompt_id}", timeout=3)
            if resp.status_code == 200:
                hist = resp.json()
                prompt_data = hist.get(prompt_id, {}).get("prompt", [])
                # prompt is [index, prompt_id, workflow_dict, ...]
                if isinstance(prompt_data, list) and len(prompt_data) >= 3:
                    workflow = prompt_data[2]
                elif isinstance(prompt_data, dict):
                    workflow = prompt_data
                else:
                    return
                for nid, node in workflow.items():
                    meta_title = node.get("_meta", {}).get("title")
                    self._current_node_titles[nid] = (
                        meta_title or node.get("class_type", nid)
                    )
        except Exception:
            pass  # Non-critical


def stop_dashboard_servers():
    """Stop all running dashboard servers"""
    current_pid = os.getpid()
    stopped_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check if it's a Python process running dashboard_server.py
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info['cmdline']
                if cmdline and any('dashboard_server.py' in str(arg) for arg in cmdline):
                    if proc.info['pid'] != current_pid:  # Don't kill ourselves
                        print(f"Stopping dashboard server (PID: {proc.info['pid']})")
                        proc.terminate()
                        stopped_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return stopped_count


def load_config(config_file='config.ini'):
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path(config_file).exists():
        config.read(config_file)
        return config
    else:
        print(f"⚠️  Config file '{config_file}' not found, using defaults")
        return None


# Load configuration
config = load_config()

# Configuration
if config and config.has_option('comfyui', 'server_url'):
    COMFYUI_URL = config.get('comfyui', 'server_url')
else:
    print("⚠️  Warning: config.ini not found or missing 'server_url'")
    print("   Please create config.ini with ComfyUI server URL")
    print("   Using fallback: http://127.0.0.1:8188")
    COMFYUI_URL = "http://127.0.0.1:8188"

# Local ComfyUI path (for local mode)
COMFYUI_LOCAL_PATH = None
COMFYUI_LOCAL_PATH_CONFIGURED = False
if config and config.has_option('comfyui', 'local_path'):
    path = config.get('comfyui', 'local_path')
    if path and path.strip():  # Check if not empty
        COMFYUI_LOCAL_PATH_CONFIGURED = True
        COMFYUI_LOCAL_PATH = path.strip()
        if os.path.exists(COMFYUI_LOCAL_PATH):
            print(f"✓ Local ComfyUI path configured and found: {COMFYUI_LOCAL_PATH}")
        else:
            print(f"⚠️  Local ComfyUI path configured but not found: {COMFYUI_LOCAL_PATH}")
            print(f"   Local mode will be visible but disabled")
    else:
        print("ℹ️  Local ComfyUI path not configured")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_dir(path):
    """Resolve a directory path: absolute paths are used as-is, relative paths are resolved from the script directory."""
    if os.path.isabs(path):
        return path
    return os.path.join(_SCRIPT_DIR, path)

WORKFLOW_DIR = _resolve_dir(config.get('paths', 'workflows_dir', fallback='workflows') if config and config.has_section('paths') else 'workflows')
HISTORY_DIR = _resolve_dir(config.get('paths', 'history_dir', fallback='history') if config and config.has_section('paths') else 'history')
OUTPUT_DIR = _resolve_dir(config.get('paths', 'output_dir', fallback='output') if config and config.has_section('paths') else 'output')
GALLERY_DIR = _resolve_dir(config.get('paths', 'gallery_dir', fallback='gallery') if config and config.has_section('paths') else 'gallery')
THUMBNAIL_DIR = _resolve_dir(config.get('paths', 'thumbnails_dir', fallback='thumbnails') if config and config.has_section('paths') else 'thumbnails')
THUMBNAIL_SIZE = (300, 300)  # Max thumbnail dimensions

# Dashboard port
if config and config.has_option('dashboard', 'port'):
    DASHBOARD_PORT = config.getint('dashboard', 'port')
else:
    DASHBOARD_PORT = 5000  # Default port

# SSL/HTTPS configuration
SSL_CONTEXT = None
if config and config.has_option('dashboard', 'ssl_enabled'):
    ssl_enabled = config.getboolean('dashboard', 'ssl_enabled')
    if ssl_enabled:
        ssl_cert = config.get('dashboard', 'ssl_cert', fallback='cert.pem')
        ssl_key = config.get('dashboard', 'ssl_key', fallback='key.pem')
        if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            SSL_CONTEXT = (ssl_cert, ssl_key)
            print(f"✓ HTTPS enabled with cert: {ssl_cert}, key: {ssl_key}")
        else:
            print(f"⚠️  SSL enabled but cert/key files not found: {ssl_cert}, {ssl_key}")
            print(f"   Generate self-signed cert with:")
            print(f"   openssl req -x509 -newkey rsa:4096 -keyout {ssl_key} -out {ssl_cert} -days 365 -nodes")
            print(f"   Falling back to HTTP")

PROTOCOL = 'https' if SSL_CONTEXT else 'http'

# HTTP Basic Authentication configuration
AUTH_ENABLED = False
AUTH_USERNAME = 'admin'
AUTH_PASSWORD = 'comfyui'
GUEST_ENABLED = False
GUEST_USERNAME = 'guest'
GUEST_PASSWORD = 'guest'
if config and config.has_option('dashboard', 'auth_enabled'):
    AUTH_ENABLED = config.getboolean('dashboard', 'auth_enabled')
    if AUTH_ENABLED:
        AUTH_USERNAME = config.get('dashboard', 'auth_username', fallback='admin')
        AUTH_PASSWORD = config.get('dashboard', 'auth_password', fallback='comfyui')
        print(f"\u2713 HTTP Basic Authentication enabled (user: {AUTH_USERNAME})")
        if config.has_option('dashboard', 'guest_enabled') and config.getboolean('dashboard', 'guest_enabled'):
            GUEST_ENABLED = True
            GUEST_USERNAME = config.get('dashboard', 'guest_username', fallback='guest')
            GUEST_PASSWORD = config.get('dashboard', 'guest_password', fallback='guest')
            print(f"\u2713 Guest account enabled (user: {GUEST_USERNAME}, gallery only)")

# Paths that the guest account is allowed to access
GUEST_ALLOWED_PATHS = ('/gallery', '/api/gallery/', '/api/image/', '/favicon.svg')


@app.before_request
def check_auth():
    """Check HTTP Basic Auth on every request if auth is enabled."""
    if not AUTH_ENABLED:
        return None
    auth = request.authorization
    if not auth:
        return Response(
            'Login required.', 401,
            {'WWW-Authenticate': 'Basic realm="ComfyUI Dashboard"'}
        )
    # Admin has full access
    if auth.username == AUTH_USERNAME and auth.password == AUTH_PASSWORD:
        return None
    # Guest has gallery-only access
    if GUEST_ENABLED and auth.username == GUEST_USERNAME and auth.password == GUEST_PASSWORD:
        path = request.path
        if any(path.startswith(p) for p in GUEST_ALLOWED_PATHS):
            return None
        return Response(
            'Access denied. Guest account can only access the gallery.', 403
        )
    return Response(
        'Login required.', 401,
        {'WWW-Authenticate': 'Basic realm="ComfyUI Dashboard"'}
    )


# Create directories if they don't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(GALLERY_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)


def generate_thumbnail(image_data, cache_key=None):
    """Generate a thumbnail from image bytes. Returns BytesIO with JPEG thumbnail.
    If cache_key is provided, caches to disk."""
    if not PIL_AVAILABLE:
        return None
    try:
        # Check disk cache first
        if cache_key:
            cache_path = os.path.join(THUMBNAIL_DIR, f"{cache_key}.jpg")
            if os.path.exists(cache_path):
                return cache_path

        img = PILImage.open(BytesIO(image_data))
        img.thumbnail(THUMBNAIL_SIZE, PILImage.LANCZOS)
        # Convert to RGB if necessary (e.g. RGBA PNGs)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        if cache_key:
            cache_path = os.path.join(THUMBNAIL_DIR, f"{cache_key}.jpg")
            img.save(cache_path, 'JPEG', quality=80)
            return cache_path
        else:
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=80)
            buf.seek(0)
            return buf
    except Exception as e:
        print(f"Thumbnail generation failed: {e}")
        return None


def extract_workflow_parameters(workflow):
    """Extract key parameters from a ComfyUI workflow dict."""
    params = {}
    if not workflow or not isinstance(workflow, dict):
        return params
    loras = []
    for node_id, node_data in workflow.items():
        class_type = node_data.get('class_type', '')
        inputs = node_data.get('inputs', {})

        if class_type == 'KSampler':
            params['sampler'] = {
                'seed': inputs.get('seed'),
                'steps': inputs.get('steps'),
                'cfg': inputs.get('cfg'),
                'sampler_name': inputs.get('sampler_name'),
                'scheduler': inputs.get('scheduler'),
                'denoise': inputs.get('denoise')
            }
        elif class_type == 'CLIPTextEncode':
            text = inputs.get('text', '')
            if 'positive' not in params:
                params['positive'] = text
            elif 'negative' not in params:
                params['negative'] = text
        elif class_type in ['EmptyLatentImage', 'EmptySD3LatentImage']:
            params['dimensions'] = {
                'width': inputs.get('width'),
                'height': inputs.get('height'),
                'batch_size': inputs.get('batch_size', 1)
            }
        elif class_type in ['CheckpointLoaderSimple', 'UNETLoader']:
            if 'model' not in params:
                params['model'] = inputs.get('ckpt_name') or inputs.get('unet_name')
        elif class_type in ['LoraLoader', 'LoraLoaderModelOnly']:
            loras.append({
                'name': inputs.get('lora_name'),
                'strength': inputs.get('strength_model', inputs.get('strength', 1.0))
            })
        elif class_type == 'ModelMergeSimple':
            params['model_merge'] = {
                'ratio': inputs.get('ratio', 'N/A')
            }
        elif class_type == 'VAELoader':
            params['vae'] = inputs.get('vae_name')
        elif class_type == 'CLIPLoader':
            params['clip'] = inputs.get('clip_name')
    if loras:
        params['loras'] = loras
        # Keep backward compat: single 'lora' key for first one
        params['lora'] = loras[0]
    return params


class ComfyUIClient:
    """Client for interacting with ComfyUI API"""
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.client_id = SHARED_CLIENT_ID
    
    def queue_prompt(self, workflow):
        """Submit a workflow to ComfyUI queue"""
        try:
            payload = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            response = requests.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error queuing prompt: {e}")
            return None
    
    def get_queue(self):
        """Get current queue status"""
        try:
            response = requests.get(f"{self.base_url}/queue", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting queue: {e}")
            return {"queue_running": [], "queue_pending": []}
    
    def get_history(self, prompt_id):
        """Get execution history for a prompt"""
        try:
            response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting history: {e}")
            return {}
    
    def get_system_stats(self):
        """Get system stats from ComfyUI"""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting system stats: {e}")
            return {}


# Initialize ComfyUI client
comfy_client = ComfyUIClient(COMFYUI_URL)

# ── Prompt directory ──
PROMPT_DIR = _resolve_dir(config.get('paths', 'prompt_dir', fallback='prompt') if config and config.has_section('paths') else 'prompt')


@app.route('/api/prompt-parts', methods=['GET'])
def get_prompt_parts():
    """Get all prompt part files for the Prompt Assemble feature"""
    categories = ['header', 'characters', 'outfit', 'scene', 'camera', 'posture', 'footer']
    result = {}
    for cat in categories:
        filepath = os.path.join(PROMPT_DIR, f'prompt-{cat}.txt')
        entries = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            current_label = None
            current_text = []
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('[') and stripped.endswith(']'):
                    if current_label is not None:
                        entries.append({'label': current_label, 'text': '\n'.join(current_text).strip()})
                    current_label = stripped[1:-1]
                    current_text = []
                elif current_label is not None:
                    current_text.append(line)
            if current_label is not None:
                entries.append({'label': current_label, 'text': '\n'.join(current_text).strip()})
        result[cat] = entries
    return jsonify({'success': True, 'parts': result})


@app.route('/api/workflows', methods=['GET'])
def get_workflows():
    """Get list of available workflow JSON files"""
    try:
        os.makedirs(WORKFLOW_DIR, exist_ok=True)
        workflow_files = glob.glob(os.path.join(WORKFLOW_DIR, "*.json"))
        workflows = [os.path.basename(f) for f in workflow_files]
        return jsonify({
            "success": True,
            "workflows": workflows
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/workflows/upload', methods=['POST'])
def upload_workflow():
    """Upload a workflow JSON file"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files['file']
        if not file.filename or not file.filename.endswith('.json'):
            return jsonify({"success": False, "error": "Only .json files allowed"}), 400

        # Sanitize filename
        safe_name = os.path.basename(file.filename).replace('..', '').strip()
        if not safe_name:
            return jsonify({"success": False, "error": "Invalid filename"}), 400

        os.makedirs(WORKFLOW_DIR, exist_ok=True)
        filepath = os.path.join(WORKFLOW_DIR, safe_name)

        # Validate it's valid JSON
        content = file.read()
        json.loads(content)

        with open(filepath, 'wb') as f:
            f.write(content)

        logging.info(f"Workflow uploaded: {filepath}")
        return jsonify({"success": True, "filename": safe_name})
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Invalid JSON file"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/editor/files', methods=['GET'])
def list_editor_files():
    """List all editable files (workflows, prompt parts, config.ini)"""
    try:
        files = []
        # Workflow files
        os.makedirs(WORKFLOW_DIR, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(WORKFLOW_DIR, "*.json"))):
            files.append({
                'name': os.path.basename(f),
                'category': 'workflows',
                'key': 'workflows/' + os.path.basename(f)
            })
        # Prompt part files
        prompt_categories = ['header', 'characters', 'outfit', 'scene', 'camera', 'posture', 'footer']
        for cat in prompt_categories:
            filepath = os.path.join(PROMPT_DIR, f'prompt-{cat}.txt')
            if os.path.exists(filepath):
                files.append({
                    'name': f'prompt-{cat}.txt',
                    'category': 'prompt-parts',
                    'key': 'prompt/prompt-' + cat + '.txt'
                })
        # Config file
        config_path = os.path.join(_SCRIPT_DIR, 'config.ini')
        if os.path.exists(config_path):
            files.append({
                'name': 'config.ini',
                'category': 'config',
                'key': 'config.ini'
            })
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/editor/read/<path:key>', methods=['GET'])
def read_editor_file(key):
    """Read a file content for editing"""
    try:
        # Security: prevent directory traversal
        if '..' in key or key.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid path'}), 400

        if key.startswith('workflows/'):
            filename = key[len('workflows/'):]
            filepath = os.path.join(WORKFLOW_DIR, filename)
        elif key.startswith('prompt/'):
            filename = key[len('prompt/'):]
            filepath = os.path.join(PROMPT_DIR, filename)
        elif key == 'config.ini':
            filepath = os.path.join(_SCRIPT_DIR, 'config.ini')
        else:
            return jsonify({'success': False, 'error': 'Unknown file category'}), 400

        # Additional safety check
        filepath = os.path.abspath(filepath)
        allowed_dirs = [os.path.abspath(WORKFLOW_DIR), os.path.abspath(PROMPT_DIR), os.path.abspath(_SCRIPT_DIR)]
        if not any(filepath.startswith(d) for d in allowed_dirs):
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({'success': True, 'content': content, 'key': key})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/editor/save/<path:key>', methods=['POST'])
def save_editor_file(key):
    """Save file content from editor"""
    try:
        # Security: prevent directory traversal
        if '..' in key or key.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid path'}), 400

        data = request.json
        content = data.get('content', '')
        if content is None:
            content = ''

        if key.startswith('workflows/'):
            filename = key[len('workflows/'):]
            # Sanitize filename
            safe_name = os.path.basename(filename).replace('..', '').strip()
            if not safe_name or not safe_name.endswith('.json'):
                return jsonify({'success': False, 'error': 'Invalid filename'}), 400
            filepath = os.path.join(WORKFLOW_DIR, safe_name)
        elif key.startswith('prompt/'):
            filename = key[len('prompt/'):]
            safe_name = os.path.basename(filename).replace('..', '').strip()
            if not safe_name:
                return jsonify({'success': False, 'error': 'Invalid filename'}), 400
            filepath = os.path.join(PROMPT_DIR, safe_name)
        elif key == 'config.ini':
            filepath = os.path.join(_SCRIPT_DIR, 'config.ini')
        else:
            return jsonify({'success': False, 'error': 'Unknown file category'}), 400

        # Additional safety check
        filepath = os.path.abspath(filepath)
        allowed_dirs = [os.path.abspath(WORKFLOW_DIR), os.path.abspath(PROMPT_DIR), os.path.abspath(_SCRIPT_DIR)]
        if not any(filepath.startswith(d) for d in allowed_dirs):
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logging.info(f"File saved via editor: {filepath}")
        return jsonify({'success': True, 'path': filepath})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Image2Text (Image Captioning) ────────────────────────────────────
IMAGE2TEXT_DIR = os.path.join(_SCRIPT_DIR, 'image2text')
IMAGE2TEXT_WORKFLOW = os.path.join(IMAGE2TEXT_DIR, 'llm_qwen3_5_text_gen.json')


def _load_image2text_workflow():
    """Load the image2text workflow template"""
    if not os.path.exists(IMAGE2TEXT_WORKFLOW):
        return None
    with open(IMAGE2TEXT_WORKFLOW, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.route('/api/image2text/images', methods=['GET'])
def list_image2text_images():
    """List images available in the image2text folder"""
    try:
        os.makedirs(IMAGE2TEXT_DIR, exist_ok=True)
        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        images = []
        for f in sorted(os.listdir(IMAGE2TEXT_DIR)):
            ext = os.path.splitext(f)[1].lower()
            if ext in image_exts:
                filepath = os.path.join(IMAGE2TEXT_DIR, f)
                size = os.path.getsize(filepath)
                images.append({
                    'name': f,
                    'path': 'image2text/' + f,
                    'size': size,
                    'size_formatted': f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
                })
        return jsonify({
            'success': True,
            'images': images,
            'count': len(images)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image2text/caption', methods=['POST'])
def caption_image():
    """Submit image2text workflow and return the generated caption"""
    try:
        data = request.json
        image_key = data.get('image', '')  # e.g. 'image2text/photo.jpg' (from folder)
        temp_image = data.get('temp_image', '')  # e.g. 'pasted_image_0.png' (from upload/paste)
        source = data.get('source', 'folder')  # 'folder', 'upload', or 'paste'
        custom_prompt = data.get('prompt', '')

        workflow = _load_image2text_workflow()
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow file not found: llm_qwen3_5_text_gen.json'}), 404

        if not temp_image and not image_key:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        # Determine which image to use
        if temp_image:
            image_filename = temp_image
            image_path = os.path.join(IMAGE2TEXT_DIR, image_filename)
            if not os.path.exists(image_path):
                return jsonify({'success': False, 'error': f'Image not found: {image_filename}'}), 404
        else:
            # Validate folder image path
            if '..' in image_key or image_key.startswith('/'):
                return jsonify({'success': False, 'error': 'Invalid image path'}), 400
            if not image_key.startswith('image2text/'):
                return jsonify({'success': False, 'error': 'Image must be from image2text folder'}), 400
            image_filename = image_key[len('image2text/'):]
            image_path = os.path.join(IMAGE2TEXT_DIR, image_filename)
            if not os.path.exists(image_path):
                return jsonify({'success': False, 'error': f'Image not found: {image_filename}'}), 404

        # Copy image to ComfyUI's input directory so LoadImage can find it
        comfyui_input_dir = os.path.join(COMFYUI_LOCAL_PATH, 'input') if COMFYUI_LOCAL_PATH else None
        if comfyui_input_dir:
            os.makedirs(comfyui_input_dir, exist_ok=True)
            dest_path = os.path.join(comfyui_input_dir, image_filename)
            try:
                import shutil
                shutil.copy2(image_path, dest_path)
            except OSError:
                try:
                    import shutil
                    shutil.copy(image_path, dest_path)
                except OSError as e2:
                    print(f"Warning: Failed to copy image to ComfyUI input: {e2}")
            except Exception as e:
                print(f"Warning: Failed to copy image to ComfyUI input: {e}")
        else:
            return jsonify({'success': False, 'error': 'ComfyUI local path not configured (need [comfyui] local_path in config.ini)'}), 500

        # Update LoadImage node with the selected image
        found = False
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get('class_type') == 'LoadImage':
                workflow[node_id]['inputs']['image'] = image_filename
                found = True
                break
        if not found:
            return jsonify({'success': False, 'error': 'LoadImage node not found in workflow'}), 400

        # Update TextGenerate prompt if custom prompt provided
        if custom_prompt:
            for node_id, node_data in workflow.items():
                if isinstance(node_data, dict) and node_data.get('class_type') == 'TextGenerate':
                    workflow[node_id]['inputs']['prompt'] = custom_prompt
                    break

        # Submit to ComfyUI
        result = comfy_client.queue_prompt(workflow)
        if not result:
            return jsonify({'success': False, 'error': 'Failed to submit workflow to ComfyUI'}), 500

        prompt_id = result.get('prompt_id')
        if not prompt_id:
            return jsonify({'success': False, 'error': 'No prompt_id returned'}), 500

        # Poll for completion - wait for the prompt to finish
        max_attempts = 300  # 5 minutes at 1s intervals
        generated_text = None

        for attempt in range(max_attempts):
            time.sleep(1)
            try:
                hist_resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5)
                if hist_resp.status_code == 200:
                    hist = hist_resp.json()
                    if prompt_id in hist:
                        node_outputs = hist[prompt_id].get('outputs', {})
                        # Look for text output in PreviewAny or TextGenerate nodes
                        for node_id, node_out in node_outputs.items():
                            if 'images' in node_out:
                                # PreviewAny stores text in 'images' as gbk/binary type
                                for img_entry in node_out['images']:
                                    text_data = img_entry.get('filename', '')
                                    if text_data and 'TEXT/' in text_data:
                                        # Text output files from TextGenerate appear as TEXT/filename
                                        pass
                            if 'text' in node_out:
                                text_val = node_out['text']
                                if isinstance(text_val, list) and len(text_val) > 0:
                                    generated_text = str(text_val[0])
                                    break
                                elif isinstance(text_val, str) and text_val:
                                    generated_text = text_val
                                    break
                        if generated_text:
                            break
            except requests.exceptions.RequestException:
                pass

        if not generated_text:
            # Try to extract text from the raw output differently
            # TextGenerate outputs text that PreviewAny captures
            for attempt in range(max_attempts):
                time.sleep(1)
                try:
                    hist_resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=5)
                    if hist_resp.status_code == 200:
                        hist = hist_resp.json()
                        if prompt_id not in hist:
                            # Prompt no longer in history - it completed
                            break
                except requests.exceptions.RequestException:
                    break

            return jsonify({
                'success': False,
                'error': 'Timed out waiting for text generation (5 min max)',
                'prompt_id': prompt_id
            }), 504

        return jsonify({
            'success': True,
            'text': generated_text,
            'prompt_id': prompt_id,
            'image': image_filename
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _save_to_image2text_dir(filename, data):
    """Helper: save bytes data to image2text dir with unique filename to avoid collisions"""
    import shutil
    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}:
        ext = '.png'
    safe_name = base_name.replace(' ', '_').replace('.', '_')
    filepath = os.path.join(IMAGE2TEXT_DIR, safe_name + ext)

    # Avoid collisions by appending timestamp-based suffix
    counter = 0
    original = filepath
    while os.path.exists(filepath):
        counter += 1
        filepath = f"{original}_{counter}{ext}"

    with open(filepath, 'wb') as f:
        f.write(data)

    # Copy to ComfyUI input dir too
    if COMFYUI_LOCAL_PATH:
        comfyui_input_dir = os.path.join(COMFYUI_LOCAL_PATH, 'input')
        os.makedirs(comfyui_input_dir, exist_ok=True)
        try:
            shutil.copy2(filepath, os.path.join(comfyui_input_dir, os.path.basename(filepath)))
        except OSError:
            try:
                shutil.copy(filepath, os.path.join(comfyui_input_dir, os.path.basename(filepath)))
            except OSError as e2:
                print(f"Warning: Failed to copy to ComfyUI input: {e2}")

    return os.path.basename(filepath)


@app.route('/api/image2text/upload', methods=['POST'])
def upload_image2text_image():
    """Upload an image file to the image2text folder"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        file = request.files['file']
        if file.filename == '' or file.filename is None:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        filename = file.filename.replace('/', '_').replace('..', '')
        data = file.read()
        saved_name = _save_to_image2text_dir(filename, data)
        return jsonify({'success': True, 'filename': saved_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image2text/paste', methods=['POST'])
def paste_image2text_image():
    """Accept a base64-encoded image from clipboard paste, save to image2text folder"""
    try:
        data = request.json
        b64_data = data.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400
        # Strip data URI prefix: data:image/png;base64,...
        if ',' in b64_data:
            b64_data = b64_data.split(',', 1)[1]
        import base64
        image_bytes = base64.b64decode(b64_data)
        # Guess extension from MIME in the data URI prefix
        ext = '.png'
        if 'image/jpeg' in data.get('data', ''):
            ext = '.jpg'
        elif 'image/webp' in data.get('data', ''):
            ext = '.webp'
        elif 'image/gif' in data.get('data', ''):
            ext = '.gif'
        saved_name = _save_to_image2text_dir('pasted_image' + ext, image_bytes)
        return jsonify({'success': True, 'filename': saved_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image2text/preview/<path:filename>', methods=['GET'])
def preview_image2text_image(filename):
    """Serve an image from the image2text folder for preview"""
    # Security: prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    filepath = os.path.join(IMAGE2TEXT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'Image not found'}), 404
    allowed_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_exts:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    mime_types = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.bmp': 'image/bmp', '.gif': 'image/gif', '.tiff': 'image/tiff',
        '.webp': 'image/webp'
    }
    return send_file(filepath, mimetype=mime_types.get(ext, 'image/jpeg'))


@app.route('/api/workflow/<filename>', methods=['GET'])
def get_workflow(filename):
    """Get a specific workflow configuration"""
    try:
        filepath = os.path.join(WORKFLOW_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({
                "success": False,
                "error": "Workflow not found"
            }), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # Analyze workflow to find key nodes
        node_info = {}
        
        # Find prompt node (CLIPTextEncode with text input)
        prompt_node_id, prompt_node = find_node_by_class(workflow, 'CLIPTextEncode', 'text')
        if prompt_node_id:
            node_info['prompt'] = {
                'node_id': prompt_node_id,
                'title': prompt_node.get('_meta', {}).get('title', 'CLIP Text Encode'),
                'value': prompt_node['inputs'].get('text', '')
            }
        
        # Find save node (SaveImage with filename_prefix)
        save_node_id, save_node = find_node_by_class(workflow, 'SaveImage', 'filename_prefix')
        if save_node_id:
            node_info['filename_prefix'] = {
                'node_id': save_node_id,
                'title': save_node.get('_meta', {}).get('title', 'Save Image'),
                'value': save_node['inputs'].get('filename_prefix', 'ComfyUI')
            }
        
        # Find sampler node (KSampler with seed)
        sampler_node_id, sampler_node = find_node_by_class(workflow, 'KSampler', 'seed')
        if sampler_node_id:
            node_info['seed'] = {
                'node_id': sampler_node_id,
                'title': sampler_node.get('_meta', {}).get('title', 'KSampler'),
                'value': sampler_node['inputs'].get('seed', 0)
            }
        
        # Find batch size node (EmptyLatentImage with batch_size)
        batch_node_id, batch_node = find_node_by_class(workflow, 'EmptyLatentImage', 'batch_size')
        if batch_node_id:
            node_info['batch_size'] = {
                'node_id': batch_node_id,
                'title': batch_node.get('_meta', {}).get('title', 'Empty Latent Image'),
                'value': batch_node['inputs'].get('batch_size', 1)
            }
        
        return jsonify({
            "success": True,
            "workflow": workflow,
            "node_info": node_info
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def find_node_by_class(workflow, class_type, input_key=None):
    """Find a node in workflow by its class_type, optionally filtering by input key"""
    for node_id, node_data in workflow.items():
        if isinstance(node_data, dict) and node_data.get('class_type') == class_type:
            # If input_key specified, check if this node has that input
            if input_key:
                if 'inputs' in node_data and input_key in node_data['inputs']:
                    return node_id, node_data
            else:
                return node_id, node_data
    return None, None


@app.route('/api/submit', methods=['POST'])
def submit_workflow():
    """Submit a workflow to ComfyUI queue"""
    try:
        data = request.json
        
        # Check if workflow object is provided directly (for re-running)
        if 'workflow' in data and isinstance(data['workflow'], dict):
            workflow = data['workflow']

            # Save workflow to history log folder
            history_dir = HISTORY_DIR
            os.makedirs(history_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            history_path = os.path.join(history_dir, f"{timestamp}.json")
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(workflow, f, indent=2)
            logging.info(f"Workflow saved to history: {history_path}")

            # For direct workflow submission, skip modifications
            result = comfy_client.queue_prompt(workflow)
            
            if result:
                return jsonify({
                    "success": True,
                    "prompt_id": result.get("prompt_id"),
                    "number": result.get("number"),
                    "message": "Workflow submitted successfully"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to submit workflow to ComfyUI"
                }), 500
        
        # Original workflow file submission
        workflow_file = data.get('workflow', 'workflow_api.json')
        prompt_text = data.get('prompt', '')
        batch_size = data.get('batch_size', 1)
        filename_prefix = data.get('filename_prefix', 'comfyui_')
        seed = data.get('seed', int(time.time() * 1000) % 4294967295)
        
        # Load workflow
        filepath = os.path.join(WORKFLOW_DIR, workflow_file)
        with open(filepath, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # Modify workflow parameters dynamically by finding nodes
        
        # Update prompt - find CLIPTextEncode node with 'text' input
        prompt_node_id, prompt_node = find_node_by_class(workflow, 'CLIPTextEncode', 'text')
        if prompt_node_id:
            workflow[prompt_node_id]["inputs"]["text"] = prompt_text
        
        # Update batch size - find EmptyLatentImage or LatentBatch node
        batch_node_id, batch_node = find_node_by_class(workflow, 'EmptyLatentImage', 'batch_size')
        if batch_node_id:
            workflow[batch_node_id]["inputs"]["batch_size"] = batch_size
        
        # Update filename prefix - find SaveImage node
        save_node_id, save_node = find_node_by_class(workflow, 'SaveImage', 'filename_prefix')
        if save_node_id:
            workflow[save_node_id]["inputs"]["filename_prefix"] = filename_prefix
        
        # Update seed - find KSampler node
        sampler_node_id, sampler_node = find_node_by_class(workflow, 'KSampler', 'seed')
        if sampler_node_id:
            workflow[sampler_node_id]["inputs"]["seed"] = int(seed)
        
        # Save workflow to history folder with datetime filename
        history_dir = HISTORY_DIR
        os.makedirs(history_dir, exist_ok=True)
        
        # Format: YYYYMMDD_HHMM.json (date + hour + minute)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        history_filename = f"{timestamp}.json"
        history_path = os.path.join(history_dir, history_filename)
        
        # Save the modified workflow
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(workflow, f, indent=2)
        
        # Submit to ComfyUI
        result = comfy_client.queue_prompt(workflow)
        
        if result:
            return jsonify({
                "success": True,
                "prompt_id": result.get("prompt_id"),
                "number": result.get("number"),
                "message": "Workflow submitted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to submit workflow to ComfyUI"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current queue and system status"""
    try:
        # Get queue information
        response = requests.get(f"{COMFYUI_URL}/queue", timeout=5)
        response.raise_for_status()
        queue_data = response.json()
        
        # Extract queue info - ComfyUI returns {queue_running: [...], queue_pending: [...]}
        running_items = queue_data.get("queue_running", [])
        pending_items = queue_data.get("queue_pending", [])
        
        # Count actual items (each item is a tuple/array with prompt info)
        running_count = len(running_items)
        pending_count = len(pending_items)
        
        # Determine system status
        if running_count > 0:
            status = "running"
        elif pending_count > 0:
            status = "queued"
        else:
            status = "idle"
        
        return jsonify({
            "success": True,
            "queue": {
                "running": running_count,
                "pending": pending_count,
                "total": running_count + pending_count
            },
            "system": {
                "status": status
            },
            "timestamp": datetime.now().isoformat()
        })
    except requests.exceptions.RequestException as e:
        # Connection error - ComfyUI might not be running
        return jsonify({
            "success": False,
            "error": f"Cannot connect to ComfyUI: {str(e)}",
            "queue": {
                "running": 0,
                "pending": 0,
                "total": 0
            },
            "system": {
                "status": "disconnected"
            },
            "timestamp": datetime.now().isoformat()
        }), 200  # Still return 200 so frontend doesn't break
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "queue": {
                "running": 0,
                "pending": 0,
                "total": 0
            },
            "system": {
                "status": "error"
            },
            "timestamp": datetime.now().isoformat()
        }), 200


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Return ComfyUI server logs + WebSocket events.
    - Fetches actual console logs from ComfyUI /internal/logs
    - Merges with WebSocket execution events
    Optional query params:
      ?after=<seq>      only WS events newer than seq
      ?log_cursor=<int> only server log lines after this index
    """
    after = request.args.get('after', 0, type=int)
    log_cursor = request.args.get('log_cursor', 0, type=int)

    # 1) WebSocket execution events
    with _log_lock:
        ws_entries = [e for e in _log_entries if e["seq"] > after]

    # 2) Actual ComfyUI server console logs
    server_lines = []
    new_cursor = log_cursor
    try:
        resp = requests.get(f"{COMFYUI_URL}/internal/logs", timeout=3)
        if resp.status_code == 200:
            raw = resp.json()  # JSON string of all log text
            if isinstance(raw, str):
                all_lines = raw.strip().split('\n')
            elif isinstance(raw, list):
                all_lines = raw
            else:
                all_lines = []
            # Only return lines after cursor
            new_lines = all_lines[log_cursor:]
            new_cursor = len(all_lines)
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                # Parse timestamp if present (format: 2026-03-30T23:48:23.075741 - message)
                ts = ""
                msg = line
                if len(line) > 28 and line[10] == 'T' and ' - ' in line[:35]:
                    ts = line[11:19]  # HH:MM:SS
                    msg = line[line.index(' - ') + 3:]
                # Classify log level
                level = "info"
                msg_lower = msg.lower()
                if any(w in msg_lower for w in ['error', 'exception', 'traceback', 'failed']):
                    level = "error"
                elif any(w in msg_lower for w in ['warning', 'warn']):
                    level = "warning"
                elif any(w in msg_lower for w in ['executed', 'done', 'completed', 'loaded']):
                    level = "success"
                server_lines.append({
                    "timestamp": ts or datetime.now().strftime("%H:%M:%S"),
                    "message": msg,
                    "level": level,
                    "source": "server",
                })
    except Exception:
        pass  # ComfyUI /internal/logs not available – use WS events only

    return jsonify({
        "success": True,
        "logs": ws_entries,
        "server_logs": server_lines,
        "log_cursor": new_cursor,
    })


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Return current execution progress parsed from ComfyUI logs + queue status.
    Scrapes tqdm progress bars and execution messages from /internal/logs."""
    progress = {
        "value": 0, "max": 0, "percent": 0,
        "node": None, "prompt_id": None,
        "running": False, "success": True,
    }

    try:
        # Check queue first – if something is running, we need progress
        q_resp = requests.get(f"{COMFYUI_URL}/queue", timeout=3)
        q_data = q_resp.json() if q_resp.status_code == 200 else {}
        running_count = len(q_data.get("queue_running", []))
        pending_count = len(q_data.get("queue_pending", []))

        if running_count == 0:
            # Nothing running – return idle
            return jsonify(progress)

        progress["running"] = True

        # Parse progress from /internal/logs – look at tail for tqdm percentage
        log_resp = requests.get(f"{COMFYUI_URL}/internal/logs", timeout=3)
        if log_resp.status_code == 200:
            raw = log_resp.json()
            if isinstance(raw, str):
                all_lines = raw.strip().split('\n')
            elif isinstance(raw, list):
                all_lines = raw
            else:
                all_lines = []

            # Scan last ~30 lines in reverse for the most recent tqdm progress
            tqdm_pct_re = re.compile(r'(\d{1,3})%\|')
            tqdm_frac_re = re.compile(r'(\d+)/(\d+)\s*\[')
            got_prompt_re = re.compile(r'got prompt')
            executed_re = re.compile(r'Prompt executed in ([\d.]+) seconds')

            for line in reversed(all_lines[-40:]):
                # Check tqdm percentage pattern: " 56%|███..."
                m = tqdm_pct_re.search(line)
                if m:
                    pct = int(m.group(1))
                    progress["percent"] = pct
                    # Also try to extract fraction (e.g. 5/9)
                    mf = tqdm_frac_re.search(line)
                    if mf:
                        progress["value"] = int(mf.group(1))
                        progress["max"] = int(mf.group(2))
                    else:
                        progress["value"] = pct
                        progress["max"] = 100
                    progress["node"] = "Sampling"
                    break
                # If we see "Prompt executed" before any tqdm, execution just finished
                if executed_re.search(line):
                    progress["running"] = False
                    progress["percent"] = 100
                    break
                # If we see "got prompt" with no tqdm after it, just started
                if got_prompt_re.search(line):
                    progress["running"] = True
                    progress["percent"] = 0
                    progress["node"] = "Starting..."
                    break

    except Exception as e:
        progress["error"] = str(e)

    return jsonify(progress)


@app.route('/api/gallery', methods=['GET'])
def get_gallery():
    """Get list of generated images from ComfyUI server"""
    try:
        # Get history from ComfyUI
        response = requests.get(f"{COMFYUI_URL}/history", timeout=10)
        response.raise_for_status()
        history = response.json()
        
        images = []
        seen = set()
        
        # Parse history to extract image information
        for prompt_id, prompt_data in history.items():
            # Extract timestamp from status messages (execution_success or execution_start)
            timestamp = None
            if 'status' in prompt_data and 'messages' in prompt_data['status']:
                # Find execution_success timestamp (most accurate completion time)
                for msg in prompt_data['status']['messages']:
                    if msg[0] == 'execution_success' and 'timestamp' in msg[1]:
                        timestamp = msg[1]['timestamp'] / 1000  # Convert ms to seconds
                        break
                # Fallback to execution_start if success not found
                if not timestamp:
                    for msg in prompt_data['status']['messages']:
                        if msg[0] == 'execution_start' and 'timestamp' in msg[1]:
                            timestamp = msg[1]['timestamp'] / 1000
                            break
            
            if 'outputs' in prompt_data:
                for node_id, node_output in prompt_data['outputs'].items():
                    if 'images' in node_output:
                        for img in node_output['images']:
                            filename = img['filename']
                            if filename not in seen:
                                seen.add(filename)
                                images.append({
                                    "filename": filename,
                                    "subfolder": img.get('subfolder', ''),
                                    "type": img.get('type', 'output'),
                                    "prompt_id": prompt_id,
                                    "timestamp": timestamp
                                })
        
        # Reverse to show newest first (ComfyUI history is oldest to newest)
        images.reverse()
        
        # Limit to last 300 images
        images = images[:300]
        
        return jsonify({
            "success": True,
            "images": images,
            "count": len(images)
        })
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Cannot connect to ComfyUI: {str(e)}",
            "images": [],
            "count": 0
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "images": [],
            "count": 0
        }), 200


@app.route('/api/local-mode-available', methods=['GET'])
def check_local_mode():
    """Check if local mode is available"""
    path_exists = COMFYUI_LOCAL_PATH and os.path.exists(COMFYUI_LOCAL_PATH)
    return jsonify({
        "success": True,
        "configured": COMFYUI_LOCAL_PATH_CONFIGURED,
        "available": path_exists,
        "path": COMFYUI_LOCAL_PATH if COMFYUI_LOCAL_PATH else None,
        "reason": None if path_exists else ("Path not found" if COMFYUI_LOCAL_PATH else "Path not configured")
    })


@app.route('/api/free', methods=['POST'])
def free_vram():
    """Unload all models and free VRAM/memory via ComfyUI /free endpoint"""
    try:
        data = request.json or {}
        payload = {
            "unload_models": data.get("unload_models", True),
            "free_memory": data.get("free_memory", True)
        }
        response = requests.post(f"{COMFYUI_URL}/free", json=payload, timeout=10)
        if response.status_code == 200:
            return jsonify({"success": True, "message": "Models unloaded and memory freed"})
        else:
            return jsonify({"success": False, "error": f"ComfyUI returned status {response.status_code}"}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Cannot reach ComfyUI: {str(e)}"}), 502


@app.route('/api/save-workflow-local', methods=['POST'])
def save_workflow_local():
    """Save workflow JSON to ComfyUI's local workflows directory"""
    if not COMFYUI_LOCAL_PATH or not os.path.exists(COMFYUI_LOCAL_PATH):
        return jsonify({"success": False, "error": "Local ComfyUI path not available"}), 400

    data = request.json
    workflow = data.get('workflow')
    filename = data.get('filename', 'workflow')
    if not workflow:
        return jsonify({"success": False, "error": "No workflow provided"}), 400

    # Sanitize filename
    safe_name = os.path.basename(filename).replace('..', '').strip()
    if not safe_name:
        safe_name = 'workflow'
    if not safe_name.endswith('.json'):
        safe_name += '.json'

    workflows_dir = os.path.join(COMFYUI_LOCAL_PATH, 'user', 'default', 'workflows')
    os.makedirs(workflows_dir, exist_ok=True)

    filepath = os.path.join(workflows_dir, safe_name)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(workflow, f, indent=2)

    logging.info(f"Workflow saved to: {filepath}")
    return jsonify({"success": True, "path": filepath, "filename": safe_name})


@app.route('/api/gallery-local', methods=['GET'])
def get_gallery_local():
    """Get gallery with local filesystem files included"""
    if not COMFYUI_LOCAL_PATH:
        return jsonify({
            "success": False,
            "error": "Local mode not configured",
            "images": [],
            "count": 0
        }), 400
    
    try:
        # First, get images from history (API)
        history_images = {}
        try:
            response = requests.get(f"{COMFYUI_URL}/history", timeout=10)
            response.raise_for_status()
            history = response.json()
            
            for prompt_id, prompt_data in history.items():
                timestamp = None
                if 'status' in prompt_data and 'messages' in prompt_data['status']:
                    for msg in prompt_data['status']['messages']:
                        if msg[0] == 'execution_success' and 'timestamp' in msg[1]:
                            timestamp = msg[1]['timestamp'] / 1000
                            break
                    if not timestamp:
                        for msg in prompt_data['status']['messages']:
                            if msg[0] == 'execution_start' and 'timestamp' in msg[1]:
                                timestamp = msg[1]['timestamp'] / 1000
                                break
                
                if 'outputs' in prompt_data:
                    for node_id, node_output in prompt_data['outputs'].items():
                        if 'images' in node_output:
                            for img in node_output['images']:
                                filename = img['filename']
                                subfolder = img.get('subfolder', '')
                                # Use composite key to prevent filename collisions across subfolders
                                key = f"{subfolder}|{filename}"
                                history_images[key] = {
                                    "filename": filename,
                                    "subfolder": subfolder,
                                    "type": img.get('type', 'output'),
                                    "prompt_id": prompt_id,
                                    "timestamp": timestamp,
                                    "source": "assets"
                                }
        except Exception as e:
            print(f"Warning: Could not fetch history: {e}")
        
        # Then, scan local filesystem
        output_path = os.path.join(COMFYUI_LOCAL_PATH, 'output')
        if not os.path.exists(output_path):
            return jsonify({
                "success": False,
                "error": f"Output directory not found: {output_path}",
                "images": [],
                "count": 0
            }), 400
        
        all_images = {}
        
        # Scan output directory
        for root, dirs, files in os.walk(output_path):
            for filename in files:
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(root, output_path)
                    subfolder = '' if rel_path == '.' else rel_path.replace('\\', '/')
                    
                    # Get file stats
                    stat = os.stat(file_path)
                    timestamp = stat.st_mtime
                    file_size = stat.st_size
                    
                    # Use composite key to prevent filename collisions across subfolders
                    key = f"{subfolder}|{filename}"
                    
                    # Prefer history data if available for this specific file+subfolder combo
                    if key in history_images:
                        all_images[key] = history_images[key]
                        all_images[key]['file_size'] = file_size
                        all_images[key]['file_exists'] = True
                    else:
                        all_images[key] = {
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": "output",
                            "timestamp": timestamp,
                            "file_size": file_size,
                            "source": "output",
                            "file_exists": True
                        }
        
        # Convert to list and sort by timestamp (newest first)
        images = list(all_images.values())
        images.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Limit to last 300 images for performance
        images = images[:300]
        
        return jsonify({
            "success": True,
            "images": images,
            "count": len(images),
            "local_mode": True
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "images": [],
            "count": 0
        }), 500


@app.route('/api/delete-image', methods=['DELETE'])
def delete_image():
    """Delete an image from ComfyUI history and/or local filesystem"""
    try:
        filename = request.json.get('filename')
        subfolder = request.json.get('subfolder', '')
        prompt_id = request.json.get('prompt_id')  # Optional: for history entries
        
        if not filename:
            return jsonify({
                "success": False,
                "error": "Filename is required"
            }), 400
        
        deleted_from_history = False
        deleted_from_filesystem = False
        errors = []
        
        # If prompt_id is provided, delete from ComfyUI history first
        if prompt_id:
            try:
                history_response = requests.post(
                    f"{COMFYUI_URL}/history",
                    json={"delete": [prompt_id]},
                    timeout=5
                )
                if history_response.status_code == 200:
                    deleted_from_history = True
                else:
                    errors.append(f"History API returned status {history_response.status_code}")
            except Exception as e:
                errors.append(f"Failed to delete from history: {str(e)}")
        
        # Delete physical file from filesystem (only if local path is configured)
        if COMFYUI_LOCAL_PATH:
            try:
                # Construct file path
                output_path = os.path.join(COMFYUI_LOCAL_PATH, 'output')
                if subfolder:
                    file_path = os.path.join(output_path, subfolder, filename)
                else:
                    file_path = os.path.join(output_path, filename)
                
                # Security check: ensure path is within output directory
                file_path = os.path.abspath(file_path)
                output_path = os.path.abspath(output_path)
                if not file_path.startswith(output_path):
                    return jsonify({
                        "success": False,
                        "error": "Invalid file path"
                    }), 400
                
                # Delete the file if it exists
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_from_filesystem = True
                else:
                    # File doesn't exist locally, but might have been deleted from history
                    if not deleted_from_history:
                        errors.append("File not found in local filesystem")
            except Exception as e:
                errors.append(f"Failed to delete file: {str(e)}")
        else:
            # No local path configured, only history deletion is possible
            if not prompt_id:
                return jsonify({
                    "success": False,
                    "error": "Cannot delete: no prompt_id provided and local mode not configured"
                }), 400
        
        # Build response message
        success = deleted_from_history or deleted_from_filesystem
        message_parts = []
        if deleted_from_history:
            message_parts.append("history entry")
        if deleted_from_filesystem:
            message_parts.append("file")
        
        if success:
            message = f"Deleted {' and '.join(message_parts)} for {filename}"
            if errors:
                message += f" (warnings: {'; '.join(errors)})"
            return jsonify({
                "success": True,
                "message": message,
                "deleted_from_history": deleted_from_history,
                "deleted_from_filesystem": deleted_from_filesystem
            })
        else:
            return jsonify({
                "success": False,
                "error": "; ".join(errors) if errors else "Failed to delete"
            }), 500
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/image/<filename>', methods=['GET'])
def get_image(filename):
    """Serve an image file from ComfyUI server"""
    try:
        subfolder = request.args.get('subfolder', '')
        folder_type = request.args.get('type', 'output')
        want_thumbnail = request.args.get('thumbnail', '') == '1'
        
        # Proxy request to ComfyUI server
        params = {
            'filename': filename,
            'subfolder': subfolder,
            'type': folder_type
        }
        
        response = requests.get(
            f"{COMFYUI_URL}/view",
            params=params,
            stream=not want_thumbnail,
            timeout=30
        )
        response.raise_for_status()
        
        # Generate thumbnail if requested
        if want_thumbnail and PIL_AVAILABLE:
            cache_key = hashlib.md5(f"{filename}_{subfolder}_{folder_type}".encode()).hexdigest()
            image_data = response.content
            result = generate_thumbnail(image_data, cache_key)
            if result:
                if isinstance(result, str):
                    return send_file(result, mimetype='image/jpeg')
                return send_file(result, mimetype='image/jpeg')
        
        # Stream the full response
        from flask import Response
        return Response(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('content-type', 'image/png')
        )
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Cannot fetch image from ComfyUI: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_image(filename):
    """Download an image file from ComfyUI server"""
    try:
        subfolder = request.args.get('subfolder', '')
        folder_type = request.args.get('type', 'output')
        
        # Proxy request to ComfyUI server
        params = {
            'filename': filename,
            'subfolder': subfolder,
            'type': folder_type
        }
        
        response = requests.get(
            f"{COMFYUI_URL}/view",
            params=params,
            stream=True,
            timeout=30
        )
        response.raise_for_status()
        
        # Stream as download
        from flask import Response
        return Response(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('content-type', 'image/png'),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Cannot download image from ComfyUI: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test connection to ComfyUI
        queue_info = comfy_client.get_queue()
        comfy_connected = queue_info is not None
        
        return jsonify({
            "success": True,
            "status": "healthy",
            "comfyui_connected": comfy_connected,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503


@app.route('/api/test-comfyui-endpoints', methods=['GET'])
def test_comfyui_endpoints():
    """Test various ComfyUI endpoints to discover available APIs"""
    results = {}
    base_url = COMFYUI_URL
    
    # List of potential endpoints to test
    test_endpoints = [
        '/history',
        '/queue',
        '/system_stats',
        '/view',
        '/object_info',
        '/embeddings',
        '/extensions',
        '/upload/image',
        '/folder_paths',
        '/files',
        '/outputs',
        '/output',
        '/list',
        '/models',
    ]
    
    for endpoint in test_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=3)
            results[endpoint] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200,
                'content_type': response.headers.get('content-type', 'unknown'),
                'response_preview': str(response.text)[:200] if response.status_code == 200 else None
            }
        except requests.exceptions.RequestException as e:
            results[endpoint] = {
                'status_code': None,
                'accessible': False,
                'error': str(e)
            }
    
    # Test /view with parameters to check file access
    try:
        response = requests.get(
            f"{base_url}/view",
            params={'filename': 'test.png', 'type': 'output'},
            timeout=3
        )
        results['/view (with params)'] = {
            'status_code': response.status_code,
            'accessible': True,
            'note': 'File may not exist, but endpoint is accessible'
        }
    except Exception as e:
        results['/view (with params)'] = {
            'accessible': False,
            'error': str(e)
        }
    
    return jsonify({
        'success': True,
        'comfyui_url': base_url,
        'endpoints': results
    })


@app.route('/api/history', methods=['GET'])
def get_history_files():
    """Get list of history workflow files"""
    try:
        history_dir = os.path.join(os.getcwd(), 'history')
        
        if not os.path.exists(history_dir):
            return jsonify({
                "success": True,
                "files": []
            })
        
        # Get all JSON files in history directory
        json_files = glob.glob(os.path.join(history_dir, '*.json'))
        
        # Sort by filename (newest first)
        json_files.sort(reverse=True)
        
        # Extract just the filename
        files = [os.path.basename(f) for f in json_files]
        
        return jsonify({
            "success": True,
            "files": files
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/history/<filename>', methods=['GET'])
def get_history_file(filename):
    """Get a specific history workflow file"""
    try:
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                "success": False,
                "error": "Invalid filename"
            }), 400
        
        history_dir = os.path.join(os.getcwd(), 'history')
        file_path = os.path.join(history_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "error": "File not found"
            }), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        return jsonify(workflow)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/job/<prompt_id>', methods=['GET'])
def get_job_details(prompt_id):
    """Get job details including workflow from ComfyUI history"""
    try:
        # Fetch job details from ComfyUI
        response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
        
        if response.status_code != 200:
            return jsonify({
                "success": False,
                "error": f"ComfyUI returned status {response.status_code}"
            }), response.status_code
        
        job_data = response.json()
        
        if prompt_id not in job_data:
            return jsonify({
                "success": False,
                "error": "Job not found in history"
            }), 404
        
        job = job_data[prompt_id]
        
        # Extract workflow from the prompt field
        # ComfyUI returns: [queue_number, prompt_id, {workflow_dict}]
        workflow = None
        if 'prompt' in job:
            if isinstance(job['prompt'], list) and len(job['prompt']) >= 3:
                workflow = job['prompt'][2]
            elif isinstance(job['prompt'], dict):
                workflow = job['prompt']
        
        # Parse workflow to extract key parameters
        params = extract_workflow_parameters(workflow)
        
        # Get execution info
        status_info = job.get('status', {})
        execution_time = None
        start_time = None
        end_time = None
        
        if 'messages' in status_info:
            for msg in status_info['messages']:
                if msg[0] == 'execution_start' and 'timestamp' in msg[1]:
                    start_time = msg[1]['timestamp'] / 1000
                if msg[0] == 'execution_success' and 'timestamp' in msg[1]:
                    end_time = msg[1]['timestamp'] / 1000
        
        if start_time and end_time:
            execution_time = end_time - start_time
        
        return jsonify({
            "success": True,
            "prompt_id": prompt_id,
            "status": status_info.get('status_str', 'unknown'),
            "completed": status_info.get('completed', False),
            "execution_time": execution_time,
            "parameters": params,
            "workflow": workflow,
            "outputs": job.get('outputs', {}),
            "meta": job.get('meta', {})
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "success": False,
            "error": f"Failed to fetch from ComfyUI: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/gallery/store', methods=['POST'])
def store_to_gallery():
    """Store image and workflow to gallery with date-based organization"""
    try:
        data = request.json
        filename = data.get('filename')
        subfolder = data.get('subfolder', '')
        prompt_id = data.get('prompt_id')
        
        if not filename:
            return jsonify({
                "success": False,
                "error": "filename is required"
            }), 400
        
        # Get image from ComfyUI or local filesystem
        image_data = None
        source_file_path = None  # Track source file for timestamp preservation
        
        # Try to get from ComfyUI first
        try:
            params = {
                'filename': filename,
                'subfolder': subfolder,
                'type': 'output'
            }
            response = requests.get(f"{COMFYUI_URL}/view", params=params, timeout=10)
            if response.status_code == 200:
                image_data = response.content
                
                # Even if fetched via HTTP, try to locate source file for timestamp preservation
                if COMFYUI_LOCAL_PATH:
                    local_output = os.path.join(COMFYUI_LOCAL_PATH, 'output')
                    if subfolder:
                        local_output = os.path.join(local_output, subfolder)
                    local_file = os.path.join(local_output, filename)
                    if os.path.exists(local_file):
                        source_file_path = local_file
        except Exception as e:
            print(f"Failed to fetch from ComfyUI: {e}")
        
        # If not found, try local filesystem
        if not image_data and COMFYUI_LOCAL_PATH:
            local_output = os.path.join(COMFYUI_LOCAL_PATH, 'output')
            if subfolder:
                local_output = os.path.join(local_output, subfolder)
            local_file = os.path.join(local_output, filename)
            if os.path.exists(local_file):
                source_file_path = local_file  # Save source path for timestamp preservation
                with open(local_file, 'rb') as f:
                    image_data = f.read()
        
        if not image_data:
            return jsonify({
                "success": False,
                "error": "Image not found"
            }), 404
        
        # Extract file timestamp from source file (if available)
        file_timestamp = None
        if source_file_path and os.path.exists(source_file_path):
            try:
                stat_info = os.stat(source_file_path)
                file_timestamp = stat_info.st_mtime  # Use modification time
                print(f"File timestamp from source: {datetime.fromtimestamp(file_timestamp)}")
            except Exception as e:
                print(f"Failed to get file timestamp: {e}")
        
        # Try to extract date from filename as fallback
        # Common patterns: YYYY-MM-DD or MM-DD-HHMMSS
        filename_date = None
        
        # Try pattern: YYYY-MM-DD (most reliable)
        match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
        if match:
            try:
                year, month, day = match.groups()
                filename_date = datetime(int(year), int(month), int(day))
            except ValueError:
                pass
        
        # If not found, try pattern: MM-DD (assume current year)
        if not filename_date:
            match = re.search(r'(\d{2})-(\d{2})-\d{6}', filename)
            if match:
                try:
                    month, day = match.groups()
                    current_year = datetime.now().year
                    filename_date = datetime(current_year, int(month), int(day))
                except ValueError:
                    pass
        
        # Try to get workflow from job history (optional)
        workflow_data = None
        workflow_available = False
        generation_timestamp = None
        
        if prompt_id:
            try:
                print(f"Fetching workflow for prompt_id: {prompt_id}")
                response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=10)
                print(f"History response status: {response.status_code}")
                
                if response.status_code == 200:
                    job_data = response.json()
                    print(f"History contains prompt_id: {prompt_id in job_data}")
                    
                    if prompt_id in job_data:
                        job = job_data[prompt_id]
                        print(f"Job has 'prompt' field: {'prompt' in job}")
                        
                        # Extract workflow from prompt field
                        if 'prompt' in job:
                            prompt_field = job['prompt']
                            print(f"Prompt field type: {type(prompt_field)}")
                            
                            if isinstance(prompt_field, list):
                                print(f"Prompt list length: {len(prompt_field)}")
                                if len(prompt_field) >= 3:
                                    workflow_data = prompt_field[2]
                                    workflow_available = True
                                    print(f"✓ Workflow extracted from list[2], nodes: {len(workflow_data) if isinstance(workflow_data, dict) else 'N/A'}")
                                else:
                                    print(f"⚠ Prompt list too short (length {len(prompt_field)})")
                            elif isinstance(prompt_field, dict):
                                workflow_data = prompt_field
                                workflow_available = True
                                print(f"✓ Workflow extracted from dict, nodes: {len(workflow_data)}")
                            else:
                                print(f"⚠ Unexpected prompt field type: {type(prompt_field)}")
                        else:
                            print(f"⚠ Job missing 'prompt' field. Available fields: {list(job.keys())}")
                        
                        # Extract generation timestamp from status messages
                        if 'status' in job and 'messages' in job['status']:
                            for msg in job['status']['messages']:
                                if msg[0] == 'execution_start' and 'timestamp' in msg[1]:
                                    generation_timestamp = msg[1]['timestamp'] / 1000  # Convert ms to seconds
                                    break
                    else:
                        print(f"⚠ prompt_id not found in history. Available IDs: {list(job_data.keys())[:5]}")
                else:
                    print(f"⚠ History request failed with status {response.status_code}")
            except Exception as e:
                print(f"❌ Failed to fetch workflow: {e}")
                import traceback
                traceback.print_exc()
                # Continue without workflow
        else:
            print("ℹ No prompt_id provided, skipping workflow fetch")
        
        # Create date-based subfolder (YYYY-MM-DD format)
        # Priority: 1) Source file timestamp, 2) Job history timestamp, 3) Filename pattern, 4) Current date
        if file_timestamp:
            date_folder = datetime.fromtimestamp(file_timestamp).strftime('%Y-%m-%d')
        elif generation_timestamp:
            date_folder = datetime.fromtimestamp(generation_timestamp).strftime('%Y-%m-%d')
        elif filename_date:
            date_folder = filename_date.strftime('%Y-%m-%d')
        else:
            date_folder = datetime.now().strftime('%Y-%m-%d')
        
        gallery_subfolder = os.path.join(GALLERY_DIR, date_folder)
        os.makedirs(gallery_subfolder, exist_ok=True)
        
        # Generate base filename (remove extension)
        base_name = os.path.splitext(filename)[0]
        file_ext = os.path.splitext(filename)[1]
        
        # Check for identical duplicates (skip only if BOTH png and json are identical)
        import hashlib
        new_image_hash = hashlib.sha256(image_data).hexdigest()
        new_workflow_json = json.dumps(workflow_data, sort_keys=True) if (workflow_available and workflow_data) else None
        
        # Scan gallery subfolder for matching files
        if os.path.exists(gallery_subfolder):
            for existing_file in os.listdir(gallery_subfolder):
                if not existing_file.lower().endswith(file_ext.lower()):
                    continue
                existing_path = os.path.join(gallery_subfolder, existing_file)
                try:
                    with open(existing_path, 'rb') as f:
                        existing_hash = hashlib.sha256(f.read()).hexdigest()
                    if existing_hash != new_image_hash:
                        continue
                    # Image is identical — compare workflow JSON
                    existing_base = os.path.splitext(existing_file)[0]
                    existing_json_path = os.path.join(gallery_subfolder, f"{existing_base}.json")
                    existing_has_json = os.path.exists(existing_json_path)
                    
                    # Both have no workflow JSON — identical pair
                    if new_workflow_json is None and not existing_has_json:
                        return jsonify({
                            "success": True,
                            "message": f"Skipped (identical image already exists: {date_folder}/{existing_file})",
                            "gallery_path": date_folder,
                            "filename": existing_file,
                            "has_workflow": False,
                            "skipped": True
                        })
                    # Both have workflow JSON — compare content
                    if new_workflow_json is not None and existing_has_json:
                        with open(existing_json_path, 'r', encoding='utf-8') as f:
                            existing_workflow_json = json.dumps(json.load(f), sort_keys=True)
                        if existing_workflow_json == new_workflow_json:
                            return jsonify({
                                "success": True,
                                "message": f"Skipped (identical image+workflow already exists: {date_folder}/{existing_file})",
                                "gallery_path": date_folder,
                                "filename": existing_file,
                                "has_workflow": True,
                                "skipped": True
                            })
                    # Image matches but workflow differs (one has it, other doesn't,
                    # or contents differ) — not a duplicate, continue to save normally
                except Exception as e:
                    print(f"Error comparing with {existing_file}: {e}")
                    continue
        
        # Find unique filename if already exists
        counter = 1
        final_base = base_name
        while (os.path.exists(os.path.join(gallery_subfolder, f"{final_base}{file_ext}")) or
               os.path.exists(os.path.join(gallery_subfolder, f"{final_base}.json"))):
            final_base = f"{base_name}_{counter}"
            counter += 1
        
        # Save image file
        image_path = os.path.join(gallery_subfolder, f"{final_base}{file_ext}")
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # Preserve original file timestamps
        timestamp_preserved = False
        if source_file_path and os.path.exists(source_file_path):
            # Copy timestamps from source file (access and modification times)
            try:
                stat_info = os.stat(source_file_path)
                os.utime(image_path, (stat_info.st_atime, stat_info.st_mtime))
                timestamp_preserved = True
                print(f"Preserved timestamps from source file: {source_file_path}")
            except Exception as e:
                print(f"Failed to preserve timestamps from source: {e}")
        elif generation_timestamp:
            # Use generation timestamp if source file not available
            try:
                os.utime(image_path, (generation_timestamp, generation_timestamp))
                timestamp_preserved = True
                print(f"Set timestamps to generation time: {datetime.fromtimestamp(generation_timestamp)}")
            except Exception as e:
                print(f"Failed to set generation timestamp: {e}")
        
        # Save workflow JSON (if available)
        if workflow_available and workflow_data:
            workflow_path = os.path.join(gallery_subfolder, f"{final_base}.json")
            with open(workflow_path, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, indent=2)
            
            # Set workflow JSON timestamp to match image
            if source_file_path and os.path.exists(source_file_path):
                try:
                    stat_info = os.stat(source_file_path)
                    os.utime(workflow_path, (stat_info.st_atime, stat_info.st_mtime))
                except Exception as e:
                    print(f"Failed to set workflow timestamp: {e}")
            elif generation_timestamp:
                try:
                    os.utime(workflow_path, (generation_timestamp, generation_timestamp))
                except Exception as e:
                    print(f"Failed to set workflow timestamp: {e}")
        
        # Prepare response message
        message = "Stored to gallery successfully"
        if not workflow_available:
            message += " (workflow not available)"
        
        return jsonify({
            "success": True,
            "message": message,
            "gallery_path": date_folder,
            "filename": f"{final_base}{file_ext}",
            "has_workflow": workflow_available
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/gallery/list', methods=['GET'])
def list_gallery():
    """List all items in gallery organized by date folders"""
    try:
        gallery_items = []
        
        # Scan gallery directory for date folders
        if not os.path.exists(GALLERY_DIR):
            return jsonify({
                "success": True,
                "items": []
            })
        
        # Get all date folders (sorted newest first)
        date_folders = []
        for item in os.listdir(GALLERY_DIR):
            folder_path = os.path.join(GALLERY_DIR, item)
            if os.path.isdir(folder_path):
                date_folders.append(item)
        
        date_folders.sort(reverse=True)
        
        # Scan each date folder for image files
        for date_folder in date_folders:
            folder_path = os.path.join(GALLERY_DIR, date_folder)
            
            # Find all image files
            image_extensions = ['.png', '.jpg', '.jpeg', '.webp', '.gif']
            for file in os.listdir(folder_path):
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in image_extensions:
                    base_name = os.path.splitext(file)[0]
                    json_file = f"{base_name}.json"
                    txt_file = f"{base_name}.txt"
                    
                    # Check if corresponding files exist
                    has_workflow = os.path.exists(os.path.join(folder_path, json_file))
                    has_keywords = os.path.exists(os.path.join(folder_path, txt_file))
                    
                    # Get file modification time
                    file_path = os.path.join(folder_path, file)
                    mtime = os.path.getmtime(file_path)
                    
                    gallery_items.append({
                        "filename": file,
                        "base_name": base_name,
                        "date_folder": date_folder,
                        "has_workflow": has_workflow,
                        "has_keywords": has_keywords,
                        "timestamp": mtime,
                        "relative_path": f"{date_folder}/{file}"
                    })
        
        # Sort by timestamp (newest first)
        gallery_items.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            "success": True,
            "items": gallery_items,
            "total": len(gallery_items)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/gallery/image/<path:relative_path>', methods=['GET'])
def serve_gallery_image(relative_path):
    """Serve an image from the gallery (with optional thumbnail)"""
    try:
        # Security: prevent directory traversal
        if '..' in relative_path or relative_path.startswith('/'):
            return jsonify({
                "success": False,
                "error": "Invalid path"
            }), 400
        
        file_path = os.path.join(GALLERY_DIR, relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "error": "File not found"
            }), 404
        
        want_thumbnail = request.args.get('thumbnail', '') == '1'
        if want_thumbnail and PIL_AVAILABLE:
            cache_key = hashlib.md5(relative_path.encode()).hexdigest()
            cache_path = os.path.join(THUMBNAIL_DIR, f"{cache_key}.jpg")
            # Use cached thumbnail if it exists and is newer than source
            if os.path.exists(cache_path) and os.path.getmtime(cache_path) >= os.path.getmtime(file_path):
                return send_file(cache_path, mimetype='image/jpeg')
            # Generate thumbnail
            with open(file_path, 'rb') as f:
                image_data = f.read()
            result = generate_thumbnail(image_data, cache_key)
            if result and isinstance(result, str):
                return send_file(result, mimetype='image/jpeg')
        
        return send_file(file_path)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/gallery/delete', methods=['DELETE'])
def delete_gallery_image():
    """Delete an image (and associated workflow/keywords files) from gallery"""
    try:
        data = request.json
        relative_path = data.get('relative_path', '')

        if not relative_path:
            return jsonify({"success": False, "error": "relative_path is required"}), 400

        # Security: prevent directory traversal
        if '..' in relative_path or relative_path.startswith('/') or relative_path.startswith('\\'):
            return jsonify({"success": False, "error": "Invalid path"}), 400

        file_path = os.path.abspath(os.path.join(GALLERY_DIR, relative_path))
        gallery_abs = os.path.abspath(GALLERY_DIR)

        # Ensure path stays within gallery directory
        if not file_path.startswith(gallery_abs + os.sep):
            return jsonify({"success": False, "error": "Invalid path"}), 400

        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": "File not found"}), 404

        # Delete the image file
        os.remove(file_path)

        # Also delete associated workflow (.json) and keywords (.txt) files
        base_path = os.path.splitext(file_path)[0]
        for ext in ['.json', '.txt']:
            assoc_file = base_path + ext
            if os.path.exists(assoc_file):
                os.remove(assoc_file)

        filename = os.path.basename(file_path)
        return jsonify({
            "success": True,
            "message": f"Deleted {filename} from gallery"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/gallery/workflow/<path:relative_path>', methods=['GET'])
def get_gallery_workflow(relative_path):
    """Get workflow JSON for a gallery item with parsed parameters"""
    try:
        # Security: prevent directory traversal
        if '..' in relative_path or relative_path.startswith('/'):
            return jsonify({
                "success": False,
                "error": "Invalid path"
            }), 400
        
        # Replace image extension with .json
        base_name = os.path.splitext(relative_path)[0]
        json_path = f"{base_name}.json"
        file_path = os.path.join(GALLERY_DIR, json_path)
        
        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "error": "Workflow not found"
            }), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # Parse workflow to extract key parameters (same as /api/job/)
        params = extract_workflow_parameters(workflow)
        print(f"Gallery workflow '{relative_path}': {len(workflow)} nodes, {len(params)} params extracted: {list(params.keys())}")
        
        return jsonify({
            "success": True,
            "workflow": workflow,
            "parameters": params
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/')
def index():
    """Serve the dashboard HTML with prompt parts injected"""
    return _serve_dashboard()


@app.route('/gallery')
def gallery_page():
    """Serve the dashboard HTML with gallery tab active"""
    return _serve_dashboard()


def _serve_dashboard():
    """Read dashboard.html and inject prompt parts data inline."""
    import json as _json
    # Build prompt parts data locally
    categories = ['header', 'characters', 'outfit', 'scene', 'camera', 'posture', 'footer']
    parts = {}
    for cat in categories:
        filepath = os.path.join(PROMPT_DIR, f'prompt-{cat}.txt')
        entries = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            current_label = None
            current_text = []
            for line in content.split('\n'):
                stripped = line.strip()
                if stripped.startswith('[') and stripped.endswith(']'):
                    if current_label is not None:
                        entries.append({'label': current_label, 'text': '\n'.join(current_text).strip()})
                    current_label = stripped[1:-1]
                    current_text = []
                elif current_label is not None:
                    current_text.append(line)
            if current_label is not None:
                entries.append({'label': current_label, 'text': '\n'.join(current_text).strip()})
        parts[cat] = entries

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject prompt parts as inline data before </head>
    inject = f'<script>window.__PROMPT_PARTS__ = {_json.dumps(parts)};</script>'
    html = html.replace('</head>', inject + '\n</head>', 1)
    return Response(html, mimetype='text/html')


@app.route('/favicon.svg')
def favicon():
    """Serve the favicon"""
    return send_file('favicon.svg', mimetype='image/svg+xml')


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


def start_service_mode():
    """Start the dashboard server in service mode (background)"""
    log_file = 'dashboard_server.log'
    pid_file = 'dashboard_server.pid'
    
    # Check if already running
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            old_pid = int(f.read().strip())
        try:
            # Check if process with this PID is still running
            if psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                if 'dashboard_server.py' in ' '.join(proc.cmdline()):
                    print(f"⚠️  Dashboard server already running in service mode (PID: {old_pid})")
                    print(f"   Use 'python dashboard_server.py --stop' to stop it")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    # Get the Python executable and script path
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    
    print("=" * 60)
    print("🚀 Starting Dashboard Server in Service Mode")
    print("=" * 60)
    
    # Start the server process in background
    if os.name == 'nt':  # Windows
        # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS for Windows
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                [python_exe, script_path, '--service-worker'],
                stdout=log,
                stderr=log,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True
            )
    else:  # Unix/Linux/Mac
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                [python_exe, script_path, '--service-worker'],
                stdout=log,
                stderr=log,
                start_new_session=True,
                close_fds=True
            )
    
    # Save PID
    with open(pid_file, 'w') as f:
        f.write(str(process.pid))
    
    print(f"✓ Server started in background (PID: {process.pid})")
    print(f"  Dashboard: http://127.0.0.1:{DASHBOARD_PORT}")
    print(f"  Log file:  {os.path.abspath(log_file)}")
    print(f"  PID file:  {os.path.abspath(pid_file)}")
    print("=" * 60)
    print("\nTo stop the server:")
    print("  python dashboard_server.py --stop")
    print("\nTo view logs:")
    print(f"  tail -f {log_file}  (Linux/Mac)")
    print(f"  Get-Content {log_file} -Wait  (PowerShell)")
    print("=" * 60)


def run_service_worker():
    """Run the Flask app as a service worker"""
    # Setup logging to file with UTF-8 encoding
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('dashboard_server.log', encoding='utf-8'),
        ]
    )
    
    logging.info("=" * 60)
    logging.info("Dashboard Server Service Worker Started")
    logging.info("=" * 60)
    logging.info(f"Dashboard: {PROTOCOL}://127.0.0.1:{DASHBOARD_PORT}")
    logging.info(f"ComfyUI:   {COMFYUI_URL}")
    logging.info(f"Output:    {os.path.abspath(OUTPUT_DIR)}")
    logging.info(f"PID:       {os.getpid()}")
    if COMFYUI_LOCAL_PATH_CONFIGURED:
        if COMFYUI_LOCAL_PATH and os.path.exists(COMFYUI_LOCAL_PATH):
            logging.info(f"Local Path: {COMFYUI_LOCAL_PATH}")
        else:
            logging.info(f"Local Path: {COMFYUI_LOCAL_PATH} (not accessible)")
    logging.info("=" * 60)

    # Start WebSocket listener for live logs/progress
    if WS_AVAILABLE:
        _ws_listener = _ComfyWSListener(COMFYUI_URL)
        _ws_listener.start()
        logging.info("WebSocket listener started for live logs & progress")

    # Run Flask without debug mode (for production/service)
    app.run(
        host='0.0.0.0',
        port=DASHBOARD_PORT,
        debug=False,
        threaded=True,
        use_reloader=False,
        ssl_context=SSL_CONTEXT
    )


if __name__ == '__main__':
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--service-worker':
            # Internal flag - runs as the background service worker
            run_service_worker()
            sys.exit(0)
        elif sys.argv[1] == '--service' or sys.argv[1] == '--daemon' or sys.argv[1] == '-d':
            # Start in service/daemon mode
            start_service_mode()
            sys.exit(0)
        elif sys.argv[1] == '--restart' or sys.argv[1] == '-r':
            # Restart: stop all servers and start a new one
            print("=" * 60)
            print("🔄 Restarting Dashboard Server")
            print("=" * 60)
            
            # Stop any running servers
            count = stop_dashboard_servers()
            if count > 0:
                print(f"✓ Stopped {count} server(s)")
            
            # Remove PID file if exists
            pid_file = 'dashboard_server.pid'
            if os.path.exists(pid_file):
                os.remove(pid_file)
            
            # Wait a moment for processes to fully terminate
            print("⏳ Waiting for processes to terminate...")
            time.sleep(2)
            
            # Start new server in service mode
            print("🚀 Starting new server in service mode...")
            start_service_mode()
            sys.exit(0)
        elif sys.argv[1] == '--stop' or sys.argv[1] == '-s':
            print("=" * 60)
            print("🛑 Stopping Dashboard Servers")
            print("=" * 60)
            count = stop_dashboard_servers()
            
            # Also remove PID file if exists
            pid_file = 'dashboard_server.pid'
            if os.path.exists(pid_file):
                os.remove(pid_file)
                print("✓ Removed PID file")
            
            if count > 0:
                print(f"✓ Stopped {count} dashboard server(s)")
            else:
                print("⚠️  No running dashboard servers found")
            print("=" * 60)
            sys.exit(0)
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("ComfyUI Lite Dashboard Server")
            print("\nUsage:")
            print("  python dashboard_server.py                Start the server (foreground)")
            print("  python dashboard_server.py --service      Start in service mode (background)")
            print("  python dashboard_server.py --daemon       Start in daemon mode (background)")
            print("  python dashboard_server.py -d             Short for --daemon")
            print("  python dashboard_server.py --restart      Restart the server (stop + start service)")
            print("  python dashboard_server.py -r             Short for --restart")
            print("  python dashboard_server.py --stop         Stop all running servers")
            print("  python dashboard_server.py -s             Stop all running servers (short)")
            print("  python dashboard_server.py --help         Show this help message")
            print("\nService Mode:")
            print("  When started with --service or --daemon, the server runs in the background")
            print("  and logs to 'dashboard_server.log'. Use --stop to terminate.")
            print("\nRestart:")
            print("  Use --restart to stop all running servers and start a fresh instance")
            print("  in service mode. Useful for applying updates or recovering from errors.")
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            sys.exit(1)
    
    # Normal foreground mode
    print("=" * 60)
    print("🚀 ComfyUI Lite Dashboard Server")
    print("=" * 60)
    print(f"Dashboard: {PROTOCOL}://127.0.0.1:{DASHBOARD_PORT}")
    print(f"ComfyUI:   {COMFYUI_URL}")
    print(f"Output:    {os.path.abspath(OUTPUT_DIR)}")
    if WS_AVAILABLE:
        print(f"WebSocket: live logs & progress enabled")
    else:
        print(f"WebSocket: disabled (pip install websocket-client)")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server")
    print("Or run: python dashboard_server.py --stop")
    print("\nTip: Use --service to run in background mode\n")

    # Start WebSocket listener for live logs/progress
    if WS_AVAILABLE:
        _ws_listener = _ComfyWSListener(COMFYUI_URL)
        _ws_listener.start()
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n" + "=" * 60)
        print("🛑 Shutting down dashboard server...")
        print("=" * 60)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app.run(
        host='0.0.0.0',
        port=DASHBOARD_PORT,
        debug=True,
        threaded=True,
        use_reloader=False,  # Disable reloader to avoid signal handler issues
        ssl_context=SSL_CONTEXT
    )
