#!/usr/bin/env python3
"""Test script to verify TokenNo is returned from workflow queries."""

import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.therefore import ThereforeClient


def load_test_env():
    """Load environment variables from .test.env file."""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".test.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
        print(f"[INFO] Loaded test credentials from {env_file}")
    else:
        print(f"[WARNING] {env_file} not found. Using environment variables.")


async def test_workflow_query_with_token():
    """Test ExecuteWorkflowQueryForAll and ExecuteWorkflowQueryForProcess for TokenNo."""
    
    load_test_env()
    
    # Test with second tenant (craigdemo) which should work
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    if not auth_token:
        print("[ERROR] No auth token found for second tenant")
        return
    
    print(f"\n{'='*60}")
    print(f"Testing with tenant: {tenant_name}")
    print(f"API Base: {api_base}")
    print(f"{'='*60}")
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: ExecuteWorkflowQueryForAll
        print("\n1. Testing ExecuteWorkflowQueryForAll...")
        try:
            result = await client._post("ExecuteWorkflowQueryForAll", {
                "WorkflowFlags": 1,
                "MaxRows": 10
            })
            print(f"   Raw response keys: {result.keys() if result else 'None'}")
            
            if result and "WorkflowQueryResultList" in result:
                query_results = result.get("WorkflowQueryResultList", [])
                print(f"   Got {len(query_results)} query result entries")
                
                for qr in query_results[:1]:  # Show first one
                    rows = qr.get("ResultRows", [])
                    print(f"   First result has {len(rows)} rows")
                    if rows:
                        first_row = rows[0]
                        print(f"   First row keys: {first_row.keys()}")
                        print(f"   First row: {first_row}")
                        if "TokenNo" in first_row:
                            print(f"   ✓ TokenNo found: {first_row['TokenNo']}")
                        else:
                            print(f"   ✗ TokenNo NOT found in row")
            else:
                print(f"   Unexpected response: {result}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: ExecuteWorkflowQueryForProcess with a known process
        print("\n2. Testing ExecuteWorkflowQueryForProcess...")
        # Get a process first
        try:
            processes = await client.get_all_workflow_processes(use_cache=False)
            if processes:
                test_process = processes[0]
                process_no = test_process['process_no']
                print(f"   Using process {process_no}: {test_process['process_name']}")
                
                result = await client._post("ExecuteWorkflowQueryForProcess", {
                    "ProcessNo": process_no,
                    "WorkflowFlags": 1,
                    "MaxRows": 10
                })
                print(f"   Raw response keys: {result.keys() if result else 'None'}")
                
                if result and "WorkflowQueryResult" in result:
                    query_result = result.get("WorkflowQueryResult", {})
                    rows = query_result.get("ResultRows", [])
                    print(f"   Got {len(rows)} rows")
                    
                    if rows:
                        first_row = rows[0]
                        print(f"   First row keys: {first_row.keys()}")
                        print(f"   First row: {first_row}")
                        if "TokenNo" in first_row:
                            print(f"   ✓ TokenNo found: {first_row['TokenNo']}")
                            
                            # Test new TWA URL format
                            instance_no = first_row.get("InstanceNo")
                            token_no = first_row.get("TokenNo")
                            new_url = f"{api_base}/tdwv/#/workflows/instance/{instance_no}/{token_no}"
                            print(f"\n   New TWA URL format: {new_url}")
                        else:
                            print(f"   ✗ TokenNo NOT found in row")
                else:
                    print(f"   Unexpected response: {result}")
            else:
                print("   No processes found to test with")
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    print("="*60)
    print("Testing Workflow Query TokenNo Response")
    print("="*60)
    asyncio.run(test_workflow_query_with_token())
