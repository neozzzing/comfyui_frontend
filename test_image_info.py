#!/usr/bin/env python3
"""
Test script to show what information is available when clicking an image
"""

import requests
import json
import configparser

def get_comfyui_url():
    """Read ComfyUI URL from config.ini"""
    config = configparser.ConfigParser()
    try:
        config.read('config.ini')
        return config.get('comfyui', 'server_url', fallback='http://127.0.0.1:8188')
    except:
        return 'http://127.0.0.1:8188'

def show_image_information(base_url):
    """Show all information available for an image from history"""
    
    print("=" * 80)
    print("INFORMATION AVAILABLE WHEN CLICKING AN IMAGE")
    print("=" * 80)
    print(f"Server: {base_url}\n")
    
    # Get history
    try:
        response = requests.get(f"{base_url}/history", timeout=5)
        if response.status_code != 200:
            print("❌ Failed to get history")
            return
        
        history = response.json()
        if not history:
            print("❌ No history found")
            return
        
        # Get the first job with an image
        sample_prompt_id = None
        sample_job = None
        
        for prompt_id, job_data in history.items():
            if 'outputs' in job_data and job_data['outputs']:
                sample_prompt_id = prompt_id
                sample_job = job_data
                break
        
        if not sample_job:
            print("❌ No jobs with outputs found")
            return
        
        print(f"Sample Job: {sample_prompt_id}")
        print("=" * 80)
        print("\n")
        
        # 1. BASIC IMAGE INFO (already shown in dashboard)
        print("1️⃣  BASIC IMAGE INFO (Currently Shown)")
        print("-" * 80)
        if 'outputs' in sample_job:
            for node_id, node_output in sample_job['outputs'].items():
                if 'images' in node_output:
                    for img in node_output['images']:
                        print(f"✓ Filename: {img['filename']}")
                        print(f"✓ Subfolder: {img.get('subfolder', '(root)')}")
                        print(f"✓ Type: {img.get('type', 'output')}")
                        print(f"✓ Prompt ID: {sample_prompt_id}")
                        break
                    break
        print("\n")
        
        # 2. TIMESTAMP INFO
        print("2️⃣  TIMESTAMP INFORMATION (Currently Shown)")
        print("-" * 80)
        if 'status' in sample_job and 'messages' in sample_job['status']:
            for msg in sample_job['status']['messages']:
                if msg[0] == 'execution_start' and 'timestamp' in msg[1]:
                    timestamp = msg[1]['timestamp'] / 1000
                    from datetime import datetime
                    dt = datetime.fromtimestamp(timestamp)
                    print(f"✓ Execution Started: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                if msg[0] == 'execution_success' and 'timestamp' in msg[1]:
                    timestamp = msg[1]['timestamp'] / 1000
                    dt = datetime.fromtimestamp(timestamp)
                    print(f"✓ Execution Completed: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n")
        
        # 3. EXECUTION STATUS (available but not shown)
        print("3️⃣  EXECUTION STATUS (Available but NOT shown)")
        print("-" * 80)
        if 'status' in sample_job:
            status = sample_job['status']
            print(f"✓ Status: {status.get('status_str', 'unknown')}")
            print(f"✓ Completed: {status.get('completed', False)}")
            if 'messages' in status:
                print(f"✓ Execution Events: {len(status['messages'])} events")
                for msg in status['messages']:
                    print(f"   - {msg[0]}: {msg[1].get('timestamp', 'N/A')}")
        print("\n")
        
        # 4. COMPLETE WORKFLOW (available but not readily accessible)
        print("4️⃣  COMPLETE WORKFLOW (Available but NOT accessible from image click)")
        print("-" * 80)
        if 'prompt' in sample_job:
            workflow = sample_job['prompt']
            print(f"✓ Workflow Type: {type(workflow).__name__}")
            if isinstance(workflow, dict):
                print(f"✓ Number of Nodes: {len(workflow)}")
                print(f"✓ Node IDs: {list(workflow.keys())}")
                print("\nWorkflow Nodes Details:")
                for node_id, node_data in workflow.items():
                    class_type = node_data.get('class_type', 'unknown')
                    print(f"   Node {node_id}: {class_type}")
                    if 'inputs' in node_data:
                        print(f"      Inputs: {list(node_data['inputs'].keys())}")
        print("\n")
        
        # 5. SPECIFIC PARAMETER VALUES (available but buried in workflow)
        print("5️⃣  GENERATION PARAMETERS (Buried in workflow, not easily shown)")
        print("-" * 80)
        if 'prompt' in sample_job:
            workflow = sample_job['prompt']
            if isinstance(workflow, dict):
                # Look for common parameter nodes
                for node_id, node_data in workflow.items():
                    class_type = node_data.get('class_type', '')
                    
                    if class_type == 'KSampler':
                        print("✓ Sampling Parameters:")
                        inputs = node_data.get('inputs', {})
                        print(f"   - Seed: {inputs.get('seed', 'N/A')}")
                        print(f"   - Steps: {inputs.get('steps', 'N/A')}")
                        print(f"   - CFG: {inputs.get('cfg', 'N/A')}")
                        print(f"   - Sampler: {inputs.get('sampler_name', 'N/A')}")
                        print(f"   - Scheduler: {inputs.get('scheduler', 'N/A')}")
                    
                    elif class_type == 'CLIPTextEncode':
                        print("✓ Text Prompt:")
                        inputs = node_data.get('inputs', {})
                        text = inputs.get('text', 'N/A')
                        print(f"   {text[:200]}...")
                    
                    elif class_type == 'EmptyLatentImage':
                        print("✓ Image Dimensions:")
                        inputs = node_data.get('inputs', {})
                        print(f"   - Width: {inputs.get('width', 'N/A')}")
                        print(f"   - Height: {inputs.get('height', 'N/A')}")
                        print(f"   - Batch Size: {inputs.get('batch_size', 'N/A')}")
                    
                    elif class_type == 'CheckpointLoaderSimple':
                        print("✓ Model:")
                        inputs = node_data.get('inputs', {})
                        print(f"   - Checkpoint: {inputs.get('ckpt_name', 'N/A')}")
        print("\n")
        
        # 6. METADATA (if available)
        print("6️⃣  METADATA (Sometimes available)")
        print("-" * 80)
        if 'meta' in sample_job:
            meta = sample_job['meta']
            print(f"✓ Metadata: {json.dumps(meta, indent=2)}")
        else:
            print("⚠️  No metadata found in this job")
        print("\n")
        
        # 7. CACHED NODES (available but not shown)
        print("7️⃣  EXECUTION OPTIMIZATIONS (Available but NOT shown)")
        print("-" * 80)
        if 'status' in sample_job and 'messages' in sample_job['status']:
            for msg in sample_job['status']['messages']:
                if msg[0] == 'execution_cached':
                    cached_nodes = msg[1].get('nodes', [])
                    print(f"✓ Cached Nodes: {len(cached_nodes)} nodes were cached")
                    print(f"   {', '.join(cached_nodes)}")
        print("\n")
        
        # SUMMARY
        print("=" * 80)
        print("SUMMARY: What information CAN be retrieved from history?")
        print("=" * 80)
        print("""
CURRENTLY SHOWN IN DASHBOARD:
✓ Filename
✓ Subfolder
✓ Timestamp
✓ Prompt ID
✓ Source (history/filesystem)

AVAILABLE BUT NOT SHOWN (can be added):
✓ Complete workflow (all nodes and connections)
✓ Generation parameters:
  - Seed, steps, CFG, sampler, scheduler
  - Text prompts (positive/negative)
  - Image dimensions
  - Model/checkpoint used
  - LoRA models and weights
  - VAE used
✓ Execution status and success/failure
✓ Cached nodes (performance info)
✓ Execution duration (start to finish)
✓ All node inputs and outputs
✓ Custom metadata (if embedded)

CAPABILITIES FOR IMAGE CLICK:
1. Show generation parameters in modal
2. Display the text prompt used
3. Show model/checkpoint info
4. Show seed and sampling settings
5. Display workflow structure
6. Enable workflow export/rerun
7. Show execution time/performance
8. Display full node graph

WORKFLOW RETRIEVAL:
✓ YES - The complete workflow is stored in job history
✓ Can be retrieved via: GET /history/{prompt_id}
✓ Workflow is in job['prompt'] field
✓ Can be resubmitted via: POST /prompt
        """)
        
        # Show JSON structure
        print("\n")
        print("=" * 80)
        print("SAMPLE JSON STRUCTURE")
        print("=" * 80)
        print(json.dumps({
            "prompt_id": {
                "prompt": {"node_id": "workflow_definition"},
                "outputs": {"node_id": {"images": ["list_of_images"]}},
                "status": {"status_str": "success", "completed": True, "messages": []},
                "meta": {}
            }
        }, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    url = get_comfyui_url()
    show_image_information(url)
