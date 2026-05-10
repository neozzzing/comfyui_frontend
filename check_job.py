#!/usr/bin/env python3
"""
Check specific job data structure
"""
import requests
import json
import configparser

def get_comfyui_url():
    config = configparser.ConfigParser()
    try:
        config.read('config.ini')
        return config.get('comfyui', 'server_url', fallback='http://127.0.0.1:8188')
    except:
        return 'http://127.0.0.1:8188'

job_id = "4c30e91a-62aa-4093-86e3-4fb1f5085810"
url = get_comfyui_url()

print(f"Checking job: {job_id}")
print(f"ComfyUI URL: {url}")
print("=" * 80)

# Fetch the specific job from history
response = requests.get(f"{url}/history/{job_id}", timeout=10)
print(f"Response status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    
    if job_id in data:
        job = data[job_id]
        print(f"✓ Job found in history")
        print(f"\nTop-level keys: {list(job.keys())}")
        
        # Check prompt field
        if 'prompt' in job:
            prompt = job['prompt']
            print(f"\n'prompt' field type: {type(prompt)}")
            
            if isinstance(prompt, list):
                print(f"'prompt' is a list with {len(prompt)} elements")
                for i, item in enumerate(prompt):
                    print(f"  [{i}] type: {type(item)}, ", end='')
                    if isinstance(item, dict):
                        print(f"keys: {len(item)} nodes")
                    elif isinstance(item, str):
                        print(f"value: {item[:50]}...")
                    else:
                        print(f"value: {item}")
                
                # Show workflow if in position [2]
                if len(prompt) >= 3 and isinstance(prompt[2], dict):
                    print(f"\n✓ Workflow found at prompt[2]")
                    print(f"  Workflow has {len(prompt[2])} nodes")
                    print(f"  Node IDs: {list(prompt[2].keys())[:10]}...")
                else:
                    print(f"\n⚠ No workflow dict at prompt[2]")
            
            elif isinstance(prompt, dict):
                print(f"'prompt' is a dict with {len(prompt)} keys")
                print(f"  Keys: {list(prompt.keys())[:10]}...")
            else:
                print(f"'prompt' is: {prompt}")
        else:
            print(f"\n❌ No 'prompt' field found!")
            print(f"Available fields: {list(job.keys())}")
        
        # Show full structure (truncated)
        print("\n" + "=" * 80)
        print("Full job structure (first 2000 chars):")
        print(json.dumps(job, indent=2)[:2000])
        
    else:
        print(f"❌ Job ID not found in response")
        print(f"Response contains {len(data)} jobs")
        if data:
            print(f"Available job IDs: {list(data.keys())[:5]}")
else:
    print(f"❌ Request failed: {response.status_code}")
    print(response.text[:500])
