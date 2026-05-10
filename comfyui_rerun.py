#!/usr/bin/env python3
"""
Utility function to rerun ComfyUI jobs by prompt_id
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

def rerun_job(base_url, prompt_id, modifications=None, client_id=None):
    """
    Rerun a ComfyUI job by extracting its workflow and resubmitting
    
    Args:
        base_url (str): ComfyUI server URL
        prompt_id (str): The prompt_id of the job to rerun
        modifications (dict, optional): Dict of node_id -> {input_name: value} to modify
        client_id (str, optional): Client ID for WebSocket updates
    
    Returns:
        dict: Response containing new prompt_id, number, and node_errors
        
    Example:
        # Rerun with same parameters
        result = rerun_job(base_url, old_prompt_id)
        new_id = result['prompt_id']
        
        # Rerun with modified seed
        result = rerun_job(base_url, old_prompt_id, {'3': {'seed': 12345}})
    """
    try:
        # Step 1: Get the original job details
        response = requests.get(f"{base_url}/history/{prompt_id}", timeout=10)
        response.raise_for_status()
        
        job_data = response.json()
        
        if prompt_id not in job_data:
            raise ValueError(f"Job {prompt_id} not found in history")
        
        # Step 2: Extract the workflow
        job_info = job_data[prompt_id]
        workflow = job_info.get('prompt')
        
        if not workflow:
            raise ValueError(f"No workflow found for job {prompt_id}")
        
        # Handle both dict and list formats
        # Some ComfyUI versions return prompt as list of node IDs
        # We need to get the full workflow from the job data
        if not isinstance(workflow, dict):
            # If prompt is not a dict, try to reconstruct from outputs
            print(f"Warning: prompt field is {type(workflow)}, attempting to use full job data")
            # In some cases, the full workflow might be in extra_data or meta
            if 'meta' in job_info and isinstance(job_info['meta'], dict):
                workflow = job_info['meta'].get('workflow', workflow)
        
        # Step 3: Apply modifications if provided
        if modifications and isinstance(workflow, dict):
            for node_id, changes in modifications.items():
                if node_id in workflow:
                    if 'inputs' in workflow[node_id]:
                        workflow[node_id]['inputs'].update(changes)
                    else:
                        workflow[node_id]['inputs'] = changes
        
        # Step 4: Prepare submission payload
        payload = {'prompt': workflow}
        if client_id:
            payload['client_id'] = client_id
        
        # Step 5: Submit the workflow
        response = requests.post(
            f"{base_url}/prompt",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Check for errors
        if 'error' in result:
            raise ValueError(f"ComfyUI error: {result['error']}")
        
        if result.get('node_errors'):
            print(f"Warning: Node errors in workflow: {result['node_errors']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {e}")
    except Exception as e:
        raise Exception(f"Failed to rerun job: {e}")


def get_job_workflow(base_url, prompt_id):
    """
    Get the workflow definition from a completed job
    
    Args:
        base_url (str): ComfyUI server URL
        prompt_id (str): The prompt_id of the job
    
    Returns:
        dict: The workflow definition
    """
    try:
        response = requests.get(f"{base_url}/history/{prompt_id}", timeout=10)
        response.raise_for_status()
        
        job_data = response.json()
        
        if prompt_id not in job_data:
            return None
        
        return job_data[prompt_id].get('prompt')
        
    except Exception as e:
        print(f"Error getting workflow: {e}")
        return None


def compare_workflows(workflow1, workflow2):
    """
    Compare two workflows to find differences
    
    Args:
        workflow1 (dict): First workflow
        workflow2 (dict): Second workflow
    
    Returns:
        dict: Differences found
    """
    differences = {}
    
    if not isinstance(workflow1, dict) or not isinstance(workflow2, dict):
        return {"error": "Both workflows must be dictionaries"}
    
    # Check for different nodes
    nodes1 = set(workflow1.keys())
    nodes2 = set(workflow2.keys())
    
    if nodes1 != nodes2:
        differences['nodes'] = {
            'only_in_1': list(nodes1 - nodes2),
            'only_in_2': list(nodes2 - nodes1)
        }
    
    # Check for different inputs in common nodes
    common_nodes = nodes1 & nodes2
    for node_id in common_nodes:
        node1 = workflow1[node_id]
        node2 = workflow2[node_id]
        
        if node1.get('class_type') != node2.get('class_type'):
            if 'class_types' not in differences:
                differences['class_types'] = {}
            differences['class_types'][node_id] = {
                'workflow1': node1.get('class_type'),
                'workflow2': node2.get('class_type')
            }
        
        inputs1 = node1.get('inputs', {})
        inputs2 = node2.get('inputs', {})
        
        for key in set(list(inputs1.keys()) + list(inputs2.keys())):
            if inputs1.get(key) != inputs2.get(key):
                if 'inputs' not in differences:
                    differences['inputs'] = {}
                if node_id not in differences['inputs']:
                    differences['inputs'][node_id] = {}
                differences['inputs'][node_id][key] = {
                    'workflow1': inputs1.get(key),
                    'workflow2': inputs2.get(key)
                }
    
    return differences


# Example usage
if __name__ == '__main__':
    base_url = get_comfyui_url()
    
    # Get a sample job from history
    response = requests.get(f"{base_url}/history", timeout=5)
    if response.status_code == 200:
        history = response.json()
        if history:
            sample_id = list(history.keys())[0]
            print(f"Sample prompt_id: {sample_id}")
            
            # Get workflow
            workflow = get_job_workflow(base_url, sample_id)
            print(f"Workflow type: {type(workflow)}")
            
            if isinstance(workflow, dict):
                print(f"Workflow nodes: {list(workflow.keys())}")
                
                print("\n" + "="*70)
                print("Example: How to rerun with modified seed")
                print("="*70)
                print(f"""
# Find KSampler node
for node_id, node in workflow.items():
    if node.get('class_type') == 'KSampler':
        print(f"Found KSampler: {{node_id}}")
        print(f"Current seed: {{node['inputs'].get('seed')}}")

# Rerun with new seed
modifications = {{'node_id_here': {{'seed': 999}}}}
result = rerun_job('{base_url}', '{sample_id}', modifications)
print(f"New job created: {{result['prompt_id']}}")
                """)
            else:
                print(f"Workflow preview: {workflow}")
                print("\nNote: This workflow format may not support direct modification")
                print("You can still rerun it as-is using:")
                print(f"result = rerun_job('{base_url}', '{sample_id}')")
