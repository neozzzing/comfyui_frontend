#!/usr/bin/env python3
"""
Test script to explore ComfyUI API capabilities with job IDs (prompt_ids)
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

def test_api_endpoints(base_url):
    """Test different ComfyUI API endpoints"""
    
    print("=" * 70)
    print("ComfyUI API - Job ID (prompt_id) Usage Research")
    print("=" * 70)
    print(f"Server: {base_url}\n")
    
    # First, get a sample prompt_id from history
    print("1️⃣  Getting sample prompt_id from history...")
    print("-" * 70)
    try:
        response = requests.get(f"{base_url}/history", timeout=5)
        if response.status_code == 200:
            history = response.json()
            if history:
                sample_prompt_id = list(history.keys())[0]
                print(f"✓ Found sample prompt_id: {sample_prompt_id}")
                print(f"  Total history entries: {len(history)}")
            else:
                print("⚠️  No history entries found. Cannot test prompt_id endpoints.")
                sample_prompt_id = None
        else:
            print(f"❌ Failed to get history: {response.status_code}")
            sample_prompt_id = None
    except Exception as e:
        print(f"❌ Error: {e}")
        sample_prompt_id = None
    
    print("\n")
    
    # Test GET /history/{prompt_id} - Get specific job details
    if sample_prompt_id:
        print("2️⃣  GET /history/{prompt_id} - Get specific job details")
        print("-" * 70)
        try:
            response = requests.get(f"{base_url}/history/{sample_prompt_id}", timeout=5)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Retrieved job details for: {sample_prompt_id}")
                print(f"\nJob structure:")
                if sample_prompt_id in data:
                    job_data = data[sample_prompt_id]
                    print(f"  Keys: {list(job_data.keys())}")
                    if 'outputs' in job_data:
                        print(f"  Outputs: {len(job_data['outputs'])} nodes")
                        for node_id, node_output in job_data['outputs'].items():
                            print(f"    Node {node_id}: {list(node_output.keys())}")
                    if 'prompt' in job_data:
                        print(f"  Prompt nodes: {len(job_data['prompt'])} workflow nodes")
                    if 'status' in job_data:
                        print(f"  Status: {job_data['status']}")
            else:
                print(f"❌ Failed: {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
        print("\n")
    
    # Test POST /history - Delete by prompt_id
    print("3️⃣  POST /history - Delete job from history")
    print("-" * 70)
    print("Usage: POST with JSON: {\"delete\": [\"prompt_id1\", \"prompt_id2\"]}")
    print("Note: This is destructive - not testing with real prompt_id")
    print("✓ Already confirmed working in previous tests")
    print("\n")
    
    # Test POST /history - Clear all history
    print("4️⃣  POST /history - Clear all history")
    print("-" * 70)
    print("Usage: POST with JSON: {\"clear\": true}")
    print("Note: This is destructive - not testing automatically")
    print("✓ Already confirmed working in previous tests")
    print("\n")
    
    # Test GET /queue - Check if job is in queue
    print("5️⃣  GET /queue - Check queue status")
    print("-" * 70)
    try:
        response = requests.get(f"{base_url}/queue", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            queue_data = response.json()
            print(f"✓ Queue retrieved")
            print(f"\nQueue structure:")
            print(f"  Keys: {list(queue_data.keys())}")
            
            if 'queue_running' in queue_data:
                running = queue_data['queue_running']
                print(f"  Running jobs: {len(running)}")
                if running:
                    # Each running job has [number, prompt_id, prompt, extra_data, outputs_to_execute]
                    print(f"    Structure: [number, prompt_id, prompt, extra_data, outputs_to_execute]")
                    job = running[0]
                    print(f"    Example prompt_id: {job[1]}")
            
            if 'queue_pending' in queue_data:
                pending = queue_data['queue_pending']
                print(f"  Pending jobs: {len(pending)}")
                if pending:
                    print(f"    Structure: [number, prompt_id, prompt, extra_data, outputs_to_execute]")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    print("\n")
    
    # Test POST /queue - Cancel/delete job from queue
    print("6️⃣  POST /queue - Cancel/delete job from queue")
    print("-" * 70)
    print("Usage: POST with JSON: {\"delete\": [\"prompt_id\"]}")
    print("Note: Cancels a job that's in queue (not yet completed)")
    print("⚠️  Not testing automatically (no jobs in queue)")
    print("\n")
    
    # Test GET /prompt - Check submitted jobs
    print("7️⃣  GET /prompt - Get list of available endpoints")
    print("-" * 70)
    try:
        response = requests.get(f"{base_url}/prompt", timeout=5)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✓ Response: {response.text[:200]}")
        else:
            print(f"❌ Not a valid GET endpoint")
    except Exception as e:
        print(f"❌ Error: {e}")
    print("\n")
    
    # Test other potential endpoints
    print("8️⃣  Other API endpoints discovered:")
    print("-" * 70)
    endpoints = [
        ("/system_stats", "GET", "System resource statistics"),
        ("/view", "GET", "View image files (requires params)"),
        ("/upload/image", "POST", "Upload images"),
        ("/object_info", "GET", "Get node type information"),
        ("/embeddings", "GET", "Get available embeddings"),
        ("/extensions", "GET", "Get installed extensions"),
    ]
    
    for endpoint, method, description in endpoints:
        print(f"  {method:6} {endpoint:20} - {description}")
    
    print("\n")
    print("=" * 70)
    print("Summary: What can you do with a prompt_id (job ID)?")
    print("=" * 70)
    print("""
✓ GET /history/{prompt_id}
  - Retrieve complete job details including:
    - Workflow prompt (all nodes and parameters)
    - Status information
    - Output files (images, videos, etc.)
    - Execution metadata
    
✓ POST /history with {"delete": ["prompt_id"]}
  - Delete completed job from history
  - Removes job record but not output files from disk
  
✓ GET /queue
  - Check if prompt_id is in running or pending queue
  - Monitor job execution status
  
✓ POST /queue with {"delete": ["prompt_id"]}
  - Cancel a job that's currently queued or running
  - Stops execution before completion
  
✓ Track job lifecycle:
  1. Submit → POST /prompt → returns prompt_id
  2. Monitor → GET /queue → check if running
  3. Complete → GET /history/{prompt_id} → get results
  4. Delete → POST /history → clean up
    """)

if __name__ == '__main__':
    url = get_comfyui_url()
    test_api_endpoints(url)
