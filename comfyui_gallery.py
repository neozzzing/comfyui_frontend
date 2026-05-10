#!/usr/bin/env python3
"""
ComfyUI Gallery - Standalone image gallery and download script
Browse and download generated images from ComfyUI server
"""

import os
import requests
import shutil
import argparse
import sys
import configparser
from pathlib import Path
from datetime import datetime


def load_config(config_file='config.ini'):
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path(config_file).exists():
        config.read(config_file)
        return config
    return None


class ComfyUIGallery:
    """Manage ComfyUI output images from server"""
    
    def __init__(self, comfyui_url):
        self.comfyui_url = comfyui_url
    
    def get_images(self, limit=None, subfolder="", folder_type="output"):
        """Get list of images from ComfyUI server"""
        try:
            # Get history to find recent outputs
            response = requests.get(f"{self.comfyui_url}/history", timeout=10)
            response.raise_for_status()
            history = response.json()
            
            images = []
            
            # Parse history to extract image information
            for prompt_id, prompt_data in history.items():
                if 'outputs' in prompt_data:
                    for node_id, node_output in prompt_data['outputs'].items():
                        if 'images' in node_output:
                            for img in node_output['images']:
                                images.append({
                                    'filename': img['filename'],
                                    'subfolder': img.get('subfolder', ''),
                                    'type': img.get('type', 'output'),
                                    'prompt_id': prompt_id
                                })
            
            # Remove duplicates based on filename
            seen = set()
            unique_images = []
            for img in images:
                if img['filename'] not in seen:
                    seen.add(img['filename'])
                    unique_images.append(img)
            
            # Reverse to show newest first (ComfyUI history is oldest to newest)
            unique_images.reverse()
            
            # Apply limit if specified
            if limit:
                unique_images = unique_images[:limit]
            
            return unique_images
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to ComfyUI: {e}")
            return []
    
    def get_image_url(self, filename, subfolder="", folder_type="output"):
        """Get URL to view image"""
        params = f"?filename={filename}&subfolder={subfolder}&type={folder_type}"
        return f"{self.comfyui_url}/view{params}"
    
    def list_images(self, limit=None, show_details=False):
        """List all images from ComfyUI server"""
        images = self.get_images(limit=limit)
        
        if not images:
            print("📭 No images found on ComfyUI server")
            print(f"   Server: {self.comfyui_url}")
            return []
        
        print(f"🖼️  Found {len(images)} image(s) on server")
        print()
        
        for idx, img in enumerate(images, 1):
            if show_details:
                print(f"[{idx}] {img['filename']}")
                print(f"    Prompt ID: {img['prompt_id']}")
                subfolder_display = img['subfolder'] if img['subfolder'] else '(root)'
                print(f"    Subfolder: {subfolder_display}") 
                print(f"    Type: {img['type']}")
                print(f"    URL: {self.get_image_url(img['filename'], img['subfolder'], img['type'])}")
                print()
            else:
                print(f"[{idx}] {img['filename']}")
        
        return images
    
    def download_image(self, image_info, destination):
        """Download image from ComfyUI server"""
        try:
            # Create destination directory if it doesn't exist
            dest_dir = os.path.dirname(destination)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            # Download from server
            url = self.get_image_url(
                image_info['filename'],
                image_info.get('subfolder', ''),
                image_info.get('type', 'output')
            )
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✅ Downloaded: {image_info['filename']}")
            print(f"   → {destination}")
            return True
            
        except Exception as e:
            print(f"❌ Error downloading {image_info['filename']}: {e}")
            return False
    
    def download_latest(self, count=1, destination_dir="."):
        """Download latest N images"""
        images = self.get_images(limit=count)
        
        if not images:
            print("❌ No images to download")
            return 0
        
        print(f"📥 Downloading {len(images)} image(s) to {destination_dir}")
        print()
        
        success_count = 0
        for img in images:
            dest_path = os.path.join(destination_dir, img['filename'])
            if self.download_image(img, dest_path):
                success_count += 1
        
        print()
        print(f"✨ Downloaded {success_count}/{len(images)} image(s)")
        return success_count
    
    def download_by_index(self, indices, destination_dir="."):
        """Download images by their index numbers"""
        all_images = self.get_images()
        
        if not all_images:
            print("❌ No images available")
            return 0
        
        success_count = 0
        for idx in indices:
            if 1 <= idx <= len(all_images):
                img = all_images[idx - 1]
                dest_path = os.path.join(destination_dir, img['filename'])
                
                if self.download_image(img, dest_path):
                    success_count += 1
            else:
                print(f"⚠️  Index {idx} out of range (1-{len(all_images)})")
        
        print()
        print(f"✨ Downloaded {success_count}/{len(indices)} image(s)")
        return success_count


def main():
    parser = argparse.ArgumentParser(
        description="Browse and download ComfyUI generated images from server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all images from ComfyUI server
  python comfyui_gallery.py --list
  
  # List with details
  python comfyui_gallery.py --list --details
  
  # List only recent 10 images
  python comfyui_gallery.py --list --limit 10
  
  # Download latest image to current directory
  python comfyui_gallery.py --download-latest
  
  # Download latest 5 images
  python comfyui_gallery.py --download-latest 5
  
  # Download specific images by index
  python comfyui_gallery.py --list
  python comfyui_gallery.py --download 1 3 5
  
  # Download to specific directory
  python comfyui_gallery.py --download-latest 3 --dest ./my_images
        """
    )
    
    parser.add_argument('--config', default='config.ini',
                       help='Configuration file (default: config.ini)')
    parser.add_argument('--url', help='ComfyUI server URL (overrides config.ini)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List all images')
    parser.add_argument('--details', '-d', action='store_true',
                       help='Show detailed information')
    parser.add_argument('--limit', type=int,
                       help='Limit number of images to show/process')
    parser.add_argument('--download-latest', type=int, nargs='?', const=1, metavar='N',
                       help='Download latest N images (default: 1)')
    parser.add_argument('--download', type=int, nargs='+', metavar='INDEX',
                       help='Download images by index numbers')
    parser.add_argument('--dest', default='.',
                       help='Destination directory for downloads (default: current directory)')
    
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
    
    # Print header
    print("="*60)
    print("ComfyUI Gallery Manager")
    print("="*60)
    print(f"Server: {comfyui_url}")
    print("-"*60)
    print()
    
    # Initialize gallery
    gallery = ComfyUIGallery(comfyui_url)
    
    # Execute commands
    if args.list or (not args.download_latest and not args.download):
        # List mode (default if no other action specified)
        gallery.list_images(limit=args.limit, show_details=args.details)
    
    elif args.download_latest:
        gallery.download_latest(count=args.download_latest, destination_dir=args.dest)
    
    elif args.download:
        gallery.download_by_index(indices=args.download, destination_dir=args.dest)


if __name__ == "__main__":
    main()
