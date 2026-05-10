#!/usr/bin/env python3
"""
ComfyUI Submit - Standalone workflow submission script
Submit workflows to ComfyUI queue with custom parameters
"""

import json
import requests
import uuid
import time
import argparse
import sys
import configparser
from pathlib import Path


def load_config(config_file='config.ini'):
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path(config_file).exists():
        config.read(config_file)
        return config
    else:
        print(f"⚠️  Config file '{config_file}' not found, using defaults")
        return None


class ComfyUISubmitter:
    """Submit workflows to ComfyUI"""
    
    def __init__(self, comfyui_url):
        self.comfyui_url = comfyui_url
        self.client_id = str(uuid.uuid4())
    
    def load_workflow(self, workflow_file):
        """Load workflow from JSON file"""
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Error: Workflow file '{workflow_file}' not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in workflow file: {e}")
            sys.exit(1)
    
    def modify_workflow(self, workflow, prompt=None, batch_size=None, seed=None):
        """Modify workflow parameters"""
        # Update prompt (node 108)
        if prompt and "108" in workflow:
            workflow["108"]["inputs"]["text"] = prompt
            print(f"✓ Prompt set to: {prompt}")
        
        # Update batch size (node 107)
        if batch_size and "107" in workflow:
            workflow["107"]["inputs"]["batch_size"] = batch_size
            print(f"✓ Batch size set to: {batch_size}")
        
        # Update seed (node 106)
        if "106" in workflow:
            if seed is not None:
                workflow["106"]["inputs"]["seed"] = seed
                print(f"✓ Seed set to: {seed}")
            else:
                # Randomize seed if not specified
                random_seed = int(time.time() * 1000) % 1000000000
                workflow["106"]["inputs"]["seed"] = random_seed
                print(f"✓ Random seed: {random_seed}")
        
        return workflow
    
    def submit(self, workflow):
        """Submit workflow to ComfyUI"""
        try:
            payload = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            
            print(f"\n🚀 Submitting to ComfyUI at {self.comfyui_url}...")
            response = requests.post(
                f"{self.comfyui_url}/prompt",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            print("✅ Workflow submitted successfully!")
            print(f"   Prompt ID: {result.get('prompt_id')}")
            print(f"   Queue Number: {result.get('number')}")
            return result
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Error: Cannot connect to ComfyUI at {self.comfyui_url}")
            print("   Make sure ComfyUI is running and accessible")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print("❌ Error: Request timed out")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Submit workflows to ComfyUI queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit with default settings
  python comfyui_submit.py workflow_api.json
  
  # Submit with custom prompt
  python comfyui_submit.py workflow_api.json --prompt "a beautiful landscape"
  
  # Submit with prompt from file
  python comfyui_submit.py workflow_api.json --prompt-file prompt.txt
  
  # Submit with batch size
  python comfyui_submit.py workflow_api.json --prompt "portrait" --batch 4
  
  # Submit with fixed seed for reproducibility
  python comfyui_submit.py workflow_api.json --seed 12345
        """
    )
    
    parser.add_argument('workflow', help='Workflow JSON file to submit')
    parser.add_argument('--config', default='config.ini',
                       help='Configuration file (default: config.ini)')
    parser.add_argument('--url', help='ComfyUI server URL (overrides config.ini)')
    parser.add_argument('--prompt', '-p', help='Text prompt for generation')
    parser.add_argument('--prompt-file', help='Read prompt from text file')
    parser.add_argument('--batch', '-b', type=int, help='Batch size (number of images)')
    parser.add_argument('--seed', type=int, help='Random seed (omit for random)')
    parser.add_argument('--show-workflow', action='store_true', 
                       help='Display modified workflow JSON before submitting')
    
    args = parser.parse_args()
    
    # Print header
    print("="*60)
    print("ComfyUI Workflow Submitter")
    print("="*60)
    
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
    
    print(f"Server: {comfyui_url}")
    print()
    
    # Initialize submitter
    submitter = ComfyUISubmitter(comfyui_url)
    
    # Handle prompt from file
    prompt_text = args.prompt
    if args.prompt_file:
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                prompt_text = f.read().strip()
            print(f"📄 Loaded prompt from: {args.prompt_file}")
        except Exception as e:
            print(f"❌ Error reading prompt file: {e}")
            sys.exit(1)
    
    # Load and modify workflow
    print(f"\n📂 Loading workflow: {args.workflow}")
    workflow = submitter.load_workflow(args.workflow)
    
    print("\n⚙️ Configuring parameters:")
    workflow = submitter.modify_workflow(
        workflow,
        prompt=prompt_text,
        batch_size=args.batch,
        seed=args.seed
    )
    
    # Show workflow if requested
    if args.show_workflow:
        print("\n📋 Modified workflow:")
        print(json.dumps(workflow, indent=2))
        print()
    
    # Submit
    result = submitter.submit(workflow)
    
    print("\n✨ Done! Check ComfyUI for progress.")


if __name__ == "__main__":
    main()
