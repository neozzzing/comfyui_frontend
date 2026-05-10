#!/bin/bash
# ComfyUI Lite Dashboard - Linux Launcher
# Usage:
#   ./start_dashboard.sh              # Run in foreground (non-service mode)
#   ./start_dashboard.sh start        # Start as background service
#   ./start_dashboard.sh stop         # Stop the background service
#   ./start_dashboard.sh restart      # Restart the background service
#   ./start_dashboard.sh status       # Check service status
#   ./start_dashboard.sh install      # Install as systemd auto-start service
#   ./start_dashboard.sh uninstall    # Remove systemd service

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PID_FILE="$SCRIPT_DIR/dashboard_server.pid"
LOG_FILE="$SCRIPT_DIR/dashboard_server.log"
SERVICE_NAME="comfyui-dashboard"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Activate virtual environment
activate_venv() {
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    else
        echo "Error: Virtual environment not found at $VENV_DIR"
        echo "Create it with: python3 -m venv .venv && pip install -r requirements.txt"
        exit 1
    fi
}

# Run in foreground (non-service mode)
run_foreground() {
    echo "========================================"
    echo "ComfyUI Lite Dashboard"
    echo "========================================"
    echo ""
    echo "Starting dashboard server..."
    echo ""
    echo "Dashboard will be available at:"
    echo "  http://127.0.0.1:5000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo "========================================"
    echo ""
    cd "$SCRIPT_DIR"
    activate_venv
    python dashboard_server.py
}

# Start as background process
start_service() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Dashboard is already running (PID: $PID)"
            return 1
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "Starting dashboard in background..."
    cd "$SCRIPT_DIR"
    activate_venv
    nohup python dashboard_server.py --service >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Dashboard started (PID: $(cat "$PID_FILE"))"
    echo "Log file: $LOG_FILE"
}

# Stop background process
stop_service() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping dashboard (PID: $PID)..."
            kill "$PID"
            # Wait up to 10 seconds for graceful shutdown
            for i in $(seq 1 10); do
                if ! kill -0 "$PID" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            # Force kill if still running
            if kill -0 "$PID" 2>/dev/null; then
                echo "Force killing..."
                kill -9 "$PID"
            fi
            rm -f "$PID_FILE"
            echo "Dashboard stopped."
        else
            echo "Dashboard is not running (stale PID file)."
            rm -f "$PID_FILE"
        fi
    else
        echo "Dashboard is not running (no PID file)."
    fi
}

# Check status
check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Dashboard is running (PID: $PID)"
            return 0
        else
            echo "Dashboard is not running (stale PID file)"
            return 1
        fi
    else
        echo "Dashboard is not running"
        return 1
    fi
}

# Install systemd service
install_systemd() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: Must run as root to install systemd service."
        echo "Usage: sudo $0 install"
        exit 1
    fi

    CURRENT_USER="${SUDO_USER:-$(whoami)}"
    PYTHON_PATH="$VENV_DIR/bin/python"

    if [ ! -f "$PYTHON_PATH" ]; then
        echo "Error: Python not found at $PYTHON_PATH"
        echo "Create venv first: python3 -m venv .venv && pip install -r requirements.txt"
        exit 1
    fi

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ComfyUI Lite Dashboard
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_PATH dashboard_server.py --service
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    echo "Systemd service installed and started."
    echo ""
    echo "Manage with:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo "  sudo systemctl stop $SERVICE_NAME"
    echo "  sudo systemctl restart $SERVICE_NAME"
    echo "  journalctl -u $SERVICE_NAME -f"
}

# Uninstall systemd service
uninstall_systemd() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: Must run as root to uninstall systemd service."
        echo "Usage: sudo $0 uninstall"
        exit 1
    fi

    if [ -f "$SERVICE_FILE" ]; then
        systemctl stop "$SERVICE_NAME" 2>/dev/null
        systemctl disable "$SERVICE_NAME" 2>/dev/null
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        echo "Systemd service removed."
    else
        echo "Service is not installed."
    fi
}

# Main
case "${1:-}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 1
        start_service
        ;;
    status)
        check_status
        ;;
    install)
        install_systemd
        ;;
    uninstall)
        uninstall_systemd
        ;;
    "")
        run_foreground
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|install|uninstall}"
        echo ""
        echo "Commands:"
        echo "  (none)      Run in foreground (Ctrl+C to stop)"
        echo "  start       Start as background process"
        echo "  stop        Stop background process"
        echo "  restart     Restart background process"
        echo "  status      Check if running"
        echo "  install     Install as systemd auto-start service (requires sudo)"
        echo "  uninstall   Remove systemd service (requires sudo)"
        exit 1
        ;;
esac
