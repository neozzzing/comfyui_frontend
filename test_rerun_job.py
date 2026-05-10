#!/usr/bin/env python3
"""
Test script to explore rerunning ComfyUI jobs by prompt_id
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

def test_rerun_job(base_url):
    """Test rerunning a job by prompt_id"""
    
    print("=" * 70)
    print("ComfyUI API - Rerun Job by prompt_id")
    print("=" * 70)
    print(f"Server: {base_url}\n")
    
    # Step 1: Get a sample prompt_id from history
    print("Step 1: Getting sample job from history...")
    print("-" * 70)
    try:
        response = requests.get(f"{base_url}/history", timeout=5)
        if response.status_code == 200:
            history = response.json()
            if history:
                sample_prompt_id = list(history.keys())[0]
                print(f"✓ Found job: {sample_prompt_id}")
                print(f"  Total history entries: {len(history)}")
            else:
                print("❌ No history entries found. Cannot test rerun.")
                return
        else:
            print(f"❌ Failed to get history: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("\n")
    
    # Step 2: Get the job details including workflow
    print("Step 2: Retrieving job details and workflow...")
    print("-" * 70)
    try:
        response = requests.get(f"{base_url}/history/{sample_prompt_id}", timeout=5)
        if response.status_code == 200:
            job_data = response.json()
            
            if sample_prompt_id in job_data:
                job_info = job_data[sample_prompt_id]
                
                print(f"✓ Retrieved job details")
                print(f"\nJob Information:")
                print(f"  Status: {job_info.get('status', {}).get('status_str', 'unknown')}")
                print(f"  Completed: {job_info.get('status', {}).get('completed', False)}")
                
                # Extract the workflow (prompt)
                workflow = job_info.get('prompt')
                if workflow:
                    if isinstance(workflow, dict):
                        print(f"  Workflow type: Dictionary")
                        print(f"  Workflow nodes: {len(workflow)}")
                        print(f"  Node IDs: {list(workflow.keys())}")
                        
                        # Show a sample node
                        first_node_id = list(workflow.keys())[0]
                        first_node = workflow[first_node_id]
                        print(f"\n  Sample node ({first_node_id}):")
                        print(f"    class_type: {first_node.get('class_type')}")
                        if 'inputs' in first_node:
                            print(f"    inputs: {list(first_node['inputs'].keys())}")
                    elif isinstance(workflow, list):
                        print(f"  Workflow type: List")
                        print(f"  Workflow length: {len(workflow)}")
                        if len(workflow) > 0:
                            print(f"\n  Sample item [0]: {workflow[0]}")
                    else:
                        print(f"  Workflow type: {type(workflow)}")
                        print(f"  Workflow preview: {str(workflow)[:200]}")
                else:
                    print("  ❌ No workflow found in job data")
                    return
            else:
                print(f"❌ Unexpected response structure")
                return
        else:
            print(f"❌ Failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print("\n")
    
    # Step 3: Show how to rerun (without actually doing it)
    print("Step 3: How to rerun this job")
    print("-" * 70)
    print(f"""
To rerun job {sample_prompt_id}:

Method 1: Resubmit the exact workflow
--------------------------------------
workflow = job_data['{sample_prompt_id}']['prompt']
response = requests.post(
    '{base_url}/prompt',
    json={{'prompt': workflow}}
)
new_prompt_id = response.json()['prompt_id']

This creates a NEW job with a NEW prompt_id using the same workflow.


Method 2: Modify parameters before rerunning
---------------------------------------------
workflow = job_data['{sample_prompt_id}']['prompt']

# Modify specific parameters (e.g., change seed)
for node_id, node in workflow.items():
    if node.get('class_type') == 'KSampler':
        workflow[node_id]['inputs']['seed'] = 12345  # New seed

# Submit modified workflow
response = requests.post(
    '{base_url}/prompt',
    json={{'prompt': workflow}}
)
new_prompt_id = response.json()['prompt_id']


Important Notes:
----------------
✓ There is NO direct "rerun job ID" API endpoint
✓ You must extract the workflow and resubmit it
✓ A new prompt_id is always generated
✓ Original job stays in history unchanged
✓ This is essentially "clone and rerun"


Advantages:
-----------
✓ Can modify parameters before rerunning
✓ Original job is preserved
✓ Can run same workflow multiple times
✓ Can extract workflow for sharing


Example Code:
-------------
def rerun_job(base_url, prompt_id, modifications=None):
    # Get original job
    response = requests.get(f"{{base_url}}/history/{{prompt_id}}")
    job_data = response.json()
    workflow = job_data[prompt_id]['prompt']
    
    # Apply modifications if provided
    if modifications:
        for node_id, changes in modifications.items():
            if node_id in workflow:
                workflow[node_id]['inputs'].update(changes)
    
    # Resubmit
    response = requests.post(
        f"{{base_url}}/prompt",
        json={{'prompt': workflow}}
    )
    return response.json()['prompt_id']

# Usage:
# new_id = rerun_job(base_url, old_prompt_id)
# new_id = rerun_job(base_url, old_prompt_id, {{'3': {{'seed': 999}}}})
    """)
    
    print("\n")
    print("=" * 70)
    print("Summary: Can you rerun a job by prompt_id?")
    print("=" * 70)
    print("""
❌ NO direct "rerun" endpoint exists

✓ YES, you can achieve this by:
  1. GET /history/{prompt_id} → Get workflow
  2. Extract the 'prompt' field
  3. POST /prompt with the workflow → New job created
  
✓ This allows you to:
  - Rerun with same parameters
  - Rerun with modified parameters (seeds, prompts, etc.)
  - Clone successful workflows
  - Share workflows between users
  
✓ The original job remains in history
✓ A new prompt_id is generated for the rerun
    """)

if __name__ == '__main__':
    url = get_comfyui_url()
    test_rerun_job(url)
