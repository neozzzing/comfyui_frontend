#!/usr/bin/env python3
"""
ComfyUI Workflows - Standalone workflow management script
List, inspect, and validate ComfyUI workflow JSON files
"""

import json
import glob
import os
import argparse
import sys
import configparser
from pathlib import Path


class ComfyUIWorkflows:
    """Manage ComfyUI workflows"""
    
    def __init__(self, workflow_dir="."):
        self.workflow_dir = workflow_dir
    
    def get_workflows(self, pattern="*.json"):
        """Get list of workflow JSON files"""
        search_pattern = os.path.join(self.workflow_dir, pattern)
        workflows = glob.glob(search_pattern)
        workflows.sort()
        return workflows
    
    def load_workflow(self, workflow_file):
        """Load and parse workflow JSON"""
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Workflow file not found: {workflow_file}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {workflow_file}: {e}")
            return None
    
    def analyze_workflow(self, workflow_data):
        """Analyze workflow structure"""
        if not isinstance(workflow_data, dict):
            return None
        
        nodes = []
        node_types = {}
        
        for node_id, node_data in workflow_data.items():
            if isinstance(node_data, dict):
                class_type = node_data.get('class_type', 'Unknown')
                title = node_data.get('_meta', {}).get('title', node_id)
                
                nodes.append({
                    'id': node_id,
                    'type': class_type,
                    'title': title
                })
                
                # Count node types
                node_types[class_type] = node_types.get(class_type, 0) + 1
        
        return {
            'total_nodes': len(nodes),
            'nodes': nodes,
            'node_types': node_types
        }
    
    def list_workflows(self, pattern="*.json", show_details=False):
        """List all workflow files"""
        workflows = self.get_workflows(pattern=pattern)
        
        if not workflows:
            print(f"📭 No workflow files found matching '{pattern}'")
            print(f"   Directory: {os.path.abspath(self.workflow_dir)}")
            return []
        
        print(f"📋 Found {len(workflows)} workflow(s)")
        print()
        
        for idx, wf_path in enumerate(workflows, 1):
            filename = os.path.basename(wf_path)
            file_size = os.path.getsize(wf_path)
            
            print(f"[{idx}] {filename}")
            
            if show_details:
                workflow_data = self.load_workflow(wf_path)
                if workflow_data:
                    analysis = self.analyze_workflow(workflow_data)
                    if analysis:
                        print(f"    Nodes: {analysis['total_nodes']}")
                        print(f"    File size: {file_size:,} bytes")
                        print(f"    Path: {wf_path}")
                        
                        # Show node type summary
                        if analysis['node_types']:
                            print("    Node types:")
                            for node_type, count in sorted(analysis['node_types'].items()):
                                print(f"      - {node_type}: {count}")
                print()
            else:
                print(f"    Size: {file_size:,} bytes | Path: {wf_path}")
        
        return workflows
    
    def inspect_workflow(self, workflow_file, show_json=False):
        """Inspect a specific workflow in detail"""
        print(f"🔍 Inspecting: {workflow_file}")
        print("-"*60)
        
        if not os.path.exists(workflow_file):
            print(f"❌ File not found: {workflow_file}")
            return False
        
        workflow_data = self.load_workflow(workflow_file)
        if not workflow_data:
            return False
        
        analysis = self.analyze_workflow(workflow_data)
        if not analysis:
            print("❌ Unable to analyze workflow")
            return False
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Total nodes: {analysis['total_nodes']}")
        print(f"   File size: {os.path.getsize(workflow_file):,} bytes")
        
        # Node types breakdown
        print(f"\n📦 Node Types:")
        for node_type, count in sorted(analysis['node_types'].items()):
            print(f"   {node_type}: {count}")
        
        # List all nodes
        print(f"\n🔗 Nodes:")
        for node in analysis['nodes']:
            print(f"   [{node['id']}] {node['title']} ({node['type']})")
        
        # Show raw JSON if requested
        if show_json:
            print(f"\n📄 Raw JSON:")
            print(json.dumps(workflow_data, indent=2))
        
        return True
    
    def validate_workflow(self, workflow_file):
        """Validate workflow JSON structure"""
        print(f"✓ Validating: {workflow_file}")
        
        # Check file exists
        if not os.path.exists(workflow_file):
            print("❌ File not found")
            return False
        
        # Check JSON is valid
        workflow_data = self.load_workflow(workflow_file)
        if not workflow_data:
            print("❌ Invalid JSON")
            return False
        
        print("✅ Valid JSON structure")
        
        # Check if it's a dict (expected format)
        if not isinstance(workflow_data, dict):
            print("⚠️  Warning: Expected dictionary/object at root level")
            return False
        
        # Check for nodes
        if len(workflow_data) == 0:
            print("⚠️  Warning: No nodes found in workflow")
            return False
        
        print(f"✅ Contains {len(workflow_data)} node(s)")
        
        # Check each node has required fields
        valid_nodes = 0
        for node_id, node_data in workflow_data.items():
            if isinstance(node_data, dict):
                if 'class_type' in node_data:
                    valid_nodes += 1
                else:
                    print(f"⚠️  Node {node_id} missing 'class_type'")
        
        print(f"✅ {valid_nodes}/{len(workflow_data)} nodes have valid structure")
        
        if valid_nodes == len(workflow_data):
            print("\n✅ Workflow is valid!")
            return True
        else:
            print("\n⚠️  Workflow has structural issues")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Manage and inspect ComfyUI workflow files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all workflow files
  python comfyui_workflows.py --list
  
  # List with detailed information
  python comfyui_workflows.py --list --details
  
  # List workflows matching pattern
  python comfyui_workflows.py --list --pattern "nianna*.json"
  
  # Inspect specific workflow
  python comfyui_workflows.py --inspect workflow_api.json
  
  # Inspect and show full JSON
  python comfyui_workflows.py --inspect workflow_api.json --json
  
  # Validate workflow structure
  python comfyui_workflows.py --validate workflow_api.json
  
  # Search in different directory
  python comfyui_workflows.py --list --dir ./workflows
        """
    )
    
    parser.add_argument('--dir', default='.',
                       help='Directory containing workflow files (default: current directory)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List all workflow files')
    parser.add_argument('--details', '-d', action='store_true',
                       help='Show detailed information')
    parser.add_argument('--pattern', '-p', default='*.json',
                       help='Filter workflows by filename pattern (default: *.json)')
    parser.add_argument('--inspect', '-i', metavar='FILE',
                       help='Inspect a specific workflow file')
    parser.add_argument('--validate', '-v', metavar='FILE',
                       help='Validate workflow JSON structure')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Show raw JSON (use with --inspect)')
    
    args = parser.parse_args()
    
    # Print header
    print("="*60)
    print("ComfyUI Workflow Manager")
    print("="*60)
    print(f"Directory: {os.path.abspath(args.dir)}")
    print("-"*60)
    print()
    
    # Initialize workflow manager
    manager = ComfyUIWorkflows(args.dir)
    
    # Execute commands
    if args.list or (not args.inspect and not args.validate):
        # List mode (default if no other action specified)
        manager.list_workflows(pattern=args.pattern, show_details=args.details)
    
    elif args.inspect:
        if not manager.inspect_workflow(args.inspect, show_json=args.json):
            sys.exit(1)
    
    elif args.validate:
        if not manager.validate_workflow(args.validate):
            sys.exit(1)


if __name__ == "__main__":
    main()
