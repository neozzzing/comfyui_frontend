"""
Test POST /history endpoint based on API documentation
Documentation says: POST /history - clear history or delete history item
"""

import requests
import configparser
import json
from pathlib import Path

def load_config():
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path('config.ini').exists():
        config.read('config.ini')
        return config.get('comfyui', 'server_url', fallback='http://127.0.0.1:8188')
    return 'http://127.0.0.1:8188'

def test_history_post():
    """Test POST /history with different payloads"""
    base_url = load_config()
    print(f"Testing ComfyUI at: {base_url}\n")
    print("="*70)
    
    # First, get current history to have some data
    print("Getting current history...")
    try:
        hist_response = requests.get(f"{base_url}/history", timeout=5)
        history = hist_response.json()
        prompt_ids = list(history.keys())
        print(f"Found {len(prompt_ids)} history entries")
        if prompt_ids:
            print(f"Sample prompt_id: {prompt_ids[0]}")
        print()
    except Exception as e:
        print(f"Error getting history: {e}\n")
        return
    
    # Test 1: POST with empty body
    print("Test 1: POST /history with empty body")
    print("-" * 70)
    try:
        response = requests.post(f"{base_url}/history", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    # Test 2: POST with JSON: {"clear": true}
    print("Test 2: POST /history with JSON: {\"clear\": true}")
    print("-" * 70)
    try:
        response = requests.post(
            f"{base_url}/history",
            json={"clear": True},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    # Test 3: POST with JSON: {"delete": [prompt_id]}
    if prompt_ids:
        print(f"Test 3: POST /history with JSON: {{\"delete\": [\"{prompt_ids[0]}\"]}}") 
        print("-" * 70)
        try:
            response = requests.post(
                f"{base_url}/history",
                json={"delete": [prompt_ids[0]]},
                timeout=5
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Verify deletion
            verify_response = requests.get(f"{base_url}/history", timeout=5)
            new_history = verify_response.json()
            if prompt_ids[0] not in new_history:
                print(f"✓ Successfully deleted prompt_id: {prompt_ids[0]}")
            else:
                print(f"✗ Prompt still exists in history")
        except Exception as e:
            print(f"Error: {e}")
        print()
    
    # Test 4: Form data instead of JSON
    print("Test 4: POST /history with form data")
    print("-" * 70)
    try:
        response = requests.post(
            f"{base_url}/history",
            data={"clear": "true"},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    # Test 5: Try other possible parameter names
    print("Test 5: Testing other parameter variations")
    print("-" * 70)
    variations = [
        {"clear_all": True},
        {"clear_history": True},
        {"action": "clear"},
        {"reset": True},
    ]
    
    for payload in variations:
        try:
            response = requests.post(
                f"{base_url}/history",
                json=payload,
                timeout=3
            )
            if response.status_code in [200, 204]:
                print(f"✓ SUCCESS with payload: {payload} - Status: {response.status_code}")
                print(f"  Response: {response.text}")
            elif response.status_code != 400:
                print(f"? {payload} - Status: {response.status_code}")
        except Exception:
            pass
    print()
    
    # Final check - get history again
    print("="*70)
    print("Final history check:")
    try:
        final_response = requests.get(f"{base_url}/history", timeout=5)
        final_history = final_response.json()
        print(f"History entries now: {len(final_history)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_history_post()
