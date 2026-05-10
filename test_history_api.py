"""
Test script to check if ComfyUI has a clear/delete history API
"""

import requests
import configparser
from pathlib import Path

def load_config():
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    if Path('config.ini').exists():
        config.read('config.ini')
        return config.get('comfyui', 'server_url', fallback='http://127.0.0.1:8188')
    return 'http://127.0.0.1:8188'

def test_history_endpoints():
    """Test various history-related endpoints and methods"""
    base_url = load_config()
    print(f"Testing ComfyUI at: {base_url}\n")
    
    results = []
    
    # Test 1: GET /history (already known to work)
    print("Test 1: GET /history")
    try:
        response = requests.get(f"{base_url}/history", timeout=5)
        print(f"  Status: {response.status_code}")
        print(f"  Response keys: {list(response.json().keys())[:5] if response.status_code == 200 else 'N/A'}")
        results.append(('GET /history', response.status_code, 'Works'))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(('GET /history', None, str(e)))
    print()
    
    # Test 2: DELETE /history (clear all history)
    print("Test 2: DELETE /history (attempt to clear all history)")
    try:
        response = requests.delete(f"{base_url}/history", timeout=5)
        print(f"  Status: {response.status_code}")
        if response.status_code in [200, 204]:
            print(f"  SUCCESS: Clear history API exists!")
            print(f"  Response: {response.text[:200] if response.text else 'Empty response'}")
        elif response.status_code == 405:
            print(f"  Method not allowed - DELETE not supported")
        else:
            print(f"  Response: {response.text[:200] if response.text else 'N/A'}")
        results.append(('DELETE /history', response.status_code, response.text[:100]))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(('DELETE /history', None, str(e)))
    print()
    
    # Test 3: POST /history (clear history - alternate method)
    print("Test 3: POST /history/clear or POST /history with clear action")
    try:
        response = requests.post(f"{base_url}/history/clear", timeout=5)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.text[:200] if response.text else 'Empty response'}")
        results.append(('POST /history/clear', response.status_code, response.text[:100]))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(('POST /history/clear', None, str(e)))
    print()
    
    # Test 4: DELETE /history/{prompt_id} (delete specific entry)
    print("Test 4: DELETE /history/{prompt_id} (delete specific entry)")
    try:
        # First get a history entry
        hist_response = requests.get(f"{base_url}/history", timeout=5)
        if hist_response.status_code == 200:
            history = hist_response.json()
            if history:
                # Get the first prompt_id
                prompt_id = list(history.keys())[0]
                print(f"  Testing with prompt_id: {prompt_id}")
                
                # Try to delete it
                del_response = requests.delete(f"{base_url}/history/{prompt_id}", timeout=5)
                print(f"  Status: {del_response.status_code}")
                print(f"  Response: {del_response.text[:200] if del_response.text else 'Empty response'}")
                results.append((f'DELETE /history/{prompt_id}', del_response.status_code, del_response.text[:100]))
            else:
                print(f"  No history entries to test with")
                results.append(('DELETE /history/{prompt_id}', None, 'No history entries'))
        else:
            print(f"  Could not get history to test with")
            results.append(('DELETE /history/{prompt_id}', None, 'Could not get history'))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(('DELETE /history/{prompt_id}', None, str(e)))
    print()
    
    # Test 5: Check common clear patterns
    print("Test 5: Other potential clear endpoints")
    clear_endpoints = [
        '/clear_history',
        '/history/clear_all',
        '/api/history/clear',
        '/delete_history',
    ]
    for endpoint in clear_endpoints:
        try:
            # Try both POST and DELETE methods
            for method in ['POST', 'DELETE']:
                if method == 'POST':
                    response = requests.post(f"{base_url}{endpoint}", timeout=3)
                else:
                    response = requests.delete(f"{base_url}{endpoint}", timeout=3)
                    
                if response.status_code in [200, 204]:
                    print(f"  {method} {endpoint}: SUCCESS (status {response.status_code})")
                    results.append((f'{method} {endpoint}', response.status_code, 'Found!'))
                elif response.status_code != 404:
                    print(f"  {method} {endpoint}: Status {response.status_code}")
        except Exception:
            pass
    print()
    
    # Summary
    print("="*60)
    print("SUMMARY:")
    print("="*60)
    for endpoint, status, msg in results:
        if status in [200, 204]:
            print(f"✓ {endpoint} - Status {status} - {msg}")
        elif status == 405:
            print(f"✗ {endpoint} - Method not allowed")
        elif status:
            print(f"? {endpoint} - Status {status} - {msg}")
        else:
            print(f"✗ {endpoint} - {msg}")

if __name__ == '__main__':
    test_history_endpoints()
