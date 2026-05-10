#!/usr/bin/env python3
"""
Get full workflow JSON from a job to display what's available
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

url = get_comfyui_url()
response = requests.get(f"{url}/history", timeout=5)
history = response.json()

# Get first job
prompt_id = list(history.keys())[0]
job = history[prompt_id]

print("Full Job Data Structure:")
print("=" * 80)
print(json.dumps(job, indent=2))
