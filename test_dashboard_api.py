#!/usr/bin/env python3
"""
Test the dashboard API endpoint for the specific job
"""
import requests
import json

job_id = "4c30e91a-62aa-4093-86e3-4fb1f5085810"

# Assuming dashboard is running on port 5000
dashboard_url = "http://127.0.0.1:5000"

print(f"Testing dashboard API for job: {job_id}")
print("=" * 80)

try:
    response = requests.get(f"{dashboard_url}/api/job/{job_id}", timeout=10)
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\nSuccess: {data.get('success')}")
        print(f"Has workflow: {'workflow' in data and data['workflow'] is not None}")
        
        if data.get('workflow'):
            workflow = data['workflow']
            print(f"Workflow nodes: {len(workflow)}")
            print(f"Node IDs: {list(workflow.keys())}")
        else:
            print("⚠ No workflow in response")
        
        print(f"\nParameters extracted: {list(data.get('parameters', {}).keys())}")
        
        # Show full response (truncated)
        print("\n" + "=" * 80)
        print("Full response (first 1500 chars):")
        print(json.dumps(data, indent=2)[:1500])
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n⚠ Make sure the dashboard server is running:")
    print("  python dashboard_server.py")
