#!/usr/bin/env python3
"""
ComfyUI Status - Standalone status monitoring script
Monitor ComfyUI queue and system status
"""

import requests
import json
import time
import argparse
import sys
import configparser
from datetime import datetime
from pathlib import Path
from pathlib import Path


def load_config(config_file='config.ini'):
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path(config_file).exists():
        config.read(config_file)
        return config
    return None


class ComfyUIMonitor:
    """Monitor ComfyUI status"""
    
    def __init__(self, comfyui_url):
        self.comfyui_url = comfyui_url
    
    def get_queue_status(self):
        """Get current queue status"""
        try:
            response = requests.get(f"{self.comfyui_url}/queue", timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.RequestException:
            return None
    
    def get_system_stats(self):
        """Get system statistics"""
        try:
            response = requests.get(f"{self.comfyui_url}/system_stats", timeout=5)
            response.raise_for_status()
            return response.json()
        except:
            return None
    
    def display_status(self, show_details=False):
        """Display current status"""
        queue_data = self.get_queue_status()
        
        if queue_data is None:
            print("❌ Cannot connect to ComfyUI")
            print(f"   URL: {self.comfyui_url}")
            print("   Make sure ComfyUI is running and accessible")
            return False
        
        # Parse queue data
        running_items = queue_data.get("queue_running", [])
        pending_items = queue_data.get("queue_pending", [])
        
        running_count = len(running_items)
        pending_count = len(pending_items)
        total_count = running_count + pending_count
        
        # Determine status
        if running_count > 0:
            status = "🟢 RUNNING"
            status_color = "running"
        elif pending_count > 0:
            status = "🟡 QUEUED"
            status_color = "queued"
        else:
            status = "⚪ IDLE"
            status_color = "idle"
        
        # Display summary
        print(f"Status: {status}")
        print(f"Running: {running_count}")
        print(f"Pending: {pending_count}")
        print(f"Total: {total_count}")
        
        # Show detailed queue info
        if show_details and (running_items or pending_items):
            print("\n📋 Queue Details:")
            
            if running_items:
                print("\n  Currently Running:")
                for idx, item in enumerate(running_items, 1):
                    # Each item is [number, prompt_id, prompt_data, extra_data]
                    if len(item) >= 2:
                        number, prompt_id = item[0], item[1]
                        print(f"    {idx}. Queue #{number} - ID: {prompt_id[:8]}...")
            
            if pending_items:
                print("\n  Pending in Queue:")
                for idx, item in enumerate(pending_items, 1):
                    if len(item) >= 2:
                        number, prompt_id = item[0], item[1]
                        print(f"    {idx}. Queue #{number} - ID: {prompt_id[:8]}...")
        
        # Show system stats if available
        if show_details:
            stats = self.get_system_stats()
            if stats:
                print("\n💻 System Stats:")
                if "system" in stats:
                    sys_info = stats["system"]
                    if "os" in sys_info:
                        print(f"    OS: {sys_info['os']}")
                    if "python_version" in sys_info:
                        print(f"    Python: {sys_info['python_version']}")
                
                if "devices" in stats:
                    print("    Devices:")
                    for device in stats["devices"]:
                        print(f"      - {device.get('name', 'Unknown')}: {device.get('type', 'N/A')}")
        
        return True
    
    def watch_status(self, interval=2):
        """Watch status with auto-refresh"""
        print("="*60)
        print("ComfyUI Status Monitor (Press Ctrl+C to stop)")
        print("="*60)
        print()
        
        try:
            while True:
                # Clear screen (works on Windows and Unix)
                print("\033[H\033[J", end="")
                
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"🔗 {self.comfyui_url}")
                print("-"*60)
                
                self.display_status(show_details=True)
                
                print("-"*60)
                print(f"Refreshing every {interval} seconds... (Ctrl+C to stop)")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor ComfyUI queue and system status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick status check
  python comfyui_status.py
  
  # Show detailed information
  python comfyui_status.py --details
  
  # Watch status with auto-refresh
  python comfyui_status.py --watch
  
  # Watch with custom refresh interval
  python comfyui_status.py --watch --interval 5
  
  # Connect to custom ComfyUI server
  python comfyui_status.py --url http://localhost:8188
        """
    )
    
    parser.add_argument('--config', default='config.ini',
                       help='Configuration file (default: config.ini)')
    parser.add_argument('--url', help='ComfyUI server URL (overrides config.ini)')
    parser.add_argument('--watch', '-w', action='store_true',
                       help='Watch mode: continuously refresh status')
    parser.add_argument('--interval', '-i', type=int, default=2,
                       help='Refresh interval in seconds for watch mode (default: 2)')
    parser.add_argument('--details', '-d', action='store_true',
                       help='Show detailed queue and system information')
    parser.add_argument('--json', action='store_true',
                       help='Output raw JSON data')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Determine ComfyUI URL
    if args.url:
        comfyui_url = args.url
    elif config and config.has_option('comfyui', 'server_url'):
        comfyui_url = config.get('comfyui', 'server_url')
    else:
        print("⚠️  No config.ini found and no --url provided")
        print("   Please create config.ini or specify --url")
        sys.exit(1)
    
    # Initialize monitor
    monitor = ComfyUIMonitor(comfyui_url)
    
    if args.watch:
        # Watch mode
        monitor.watch_status(interval=args.interval)
    else:
        # Single status check
        if not args.json:
            print("="*60)
            print("ComfyUI Status")
            print("="*60)
            print(f"URL: {comfyui_url}")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-"*60)
        
        if args.json:
            # Raw JSON output
            queue_data = monitor.get_queue_status()
            if queue_data:
                print(json.dumps(queue_data, indent=2))
            else:
                print(json.dumps({"error": "Cannot connect to ComfyUI"}, indent=2))
                sys.exit(1)
        else:
            # Human-readable output
            success = monitor.display_status(show_details=args.details)
            if not success:
                sys.exit(1)


if __name__ == "__main__":
    main()
