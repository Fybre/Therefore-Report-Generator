#!/usr/bin/env python3
"""Test script to check Status field values for error workflows."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.therefore import ThereforeClient, WorkflowFlags


def load_test_env():
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


async def test_error_status():
    load_test_env()
    
    # Use the craigdemo tenant (Demo has corruption issues)
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    print(f"\nTesting with tenant: {tenant_name}")
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: Query with ERROR_INSTANCES flag (4)
        print("\n1. Testing ExecuteWorkflowQueryForAll with ERROR_INSTANCES flag (4)...")
        try:
            result = await client._post("ExecuteWorkflowQueryForAll", {
                "WorkflowFlags": 4,  # ErrorInstances
                "MaxRows": 10
            })
            
            if result and "WorkflowQueryResultList" in result:
                query_results = result.get("WorkflowQueryResultList", [])
                total_rows = 0
                for qr in query_results:
                    rows = qr.get("ResultRows", [])
                    total_rows += len(rows)
                
                print(f"   Found {total_rows} error instances")
                
                if total_rows > 0:
                    # Show sample rows with their Status values
                    print("\n   Sample error instances:")
                    shown = 0
                    for qr in query_results:
                        for row in qr.get("ResultRows", [])[:5]:
                            shown += 1
                            print(f"\n   Row {shown}:")
                            print(f"     InstanceNo: {row.get('InstanceNo')}")
                            print(f"     TokenNo: {row.get('TokenNo')}")
                            print(f"     Status: {row.get('Status')}")
                            print(f"     WorkflowNo: {row.get('WorkflowNo')}")
                            print(f"     IndexValues: {row.get('IndexValues', [])[:3] if row.get('IndexValues') else 'None'}...")
                else:
                    print("   No error instances found")
            else:
                print(f"   No result or unexpected format: {result}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: Query with different flags for comparison
        print("\n2. Testing with RUNNING_INSTANCES (1) for comparison...")
        try:
            result = await client._post("ExecuteWorkflowQueryForAll", {
                "WorkflowFlags": 1,
                "MaxRows": 3
            })
            
            if result and "WorkflowQueryResultList" in result:
                for qr in result.get("WorkflowQueryResultList", [])[:1]:
                    for row in qr.get("ResultRows", [])[:2]:
                        print(f"   Instance {row.get('InstanceNo')}: Status={row.get('Status')}")
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    print("="*60)
    print("Testing Error Workflow Status Values")
    print("="*60)
    asyncio.run(test_error_status())
