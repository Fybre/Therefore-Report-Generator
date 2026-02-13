#!/usr/bin/env python3
"""Test script to verify full TokenNo flow including InstanceForUser and TWA URL."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.therefore import ThereforeClient


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
        print(f"[INFO] Loaded test credentials from {env_file}")


async def test_full_token_flow():
    load_test_env()
    
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    print(f"\n{'='*60}")
    print(f"Testing Full Token Flow with tenant: {tenant_name}")
    print(f"{'='*60}")
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: execute_workflow_query_for_all returns tuples
        print("\n1. Testing execute_workflow_query_for_all returns (instance_no, token_no) tuples...")
        instances = await client.execute_workflow_query_for_all(max_rows=5)
        if instances:
            print(f"   ✓ Got {len(instances)} results")
            first = instances[0]
            print(f"   First result type: {type(first)}")
            print(f"   First result: {first}")
            if isinstance(first, tuple) and len(first) == 2:
                print(f"   ✓ Correct format: (instance_no={first[0]}, token_no={first[1]})")
            else:
                print(f"   ✗ Expected tuple, got {type(first)}")
        else:
            print("   No instances found")
        
        # Test 2: Verify new TWA URL format
        print("\n2. Testing new TWA URL format...")
        from app.services.therefore import InstanceForUser, LinkedDocument
        from datetime import datetime
        
        # Create a mock InstanceForUser with token_no
        test_instance = InstanceForUser(
            instance_no=5579,
            process_no=1,
            process_name="Test Process",
            task_name="Test Task",
            task_start=datetime.now(),
            task_due=None,
            process_start_date=datetime.now(),
            user_id=123,
            user_display_name="Test User",
            user_smtp="test@example.com",
            linked_documents=[],
            tenant_base_url=api_base,
            token_no=5
        )
        
        expected_url = f"{api_base}/tdwv/#/workflows/instance/5579/5"
        actual_url = test_instance.twa_url
        
        print(f"   Expected: {expected_url}")
        print(f"   Actual:   {actual_url}")
        if actual_url == expected_url:
            print("   ✓ TWA URL format is correct!")
        else:
            print("   ✗ TWA URL format mismatch!")
        
        # Test 3: get_all_workflow_instances returns InstanceForUser with token_no
        print("\n3. Testing get_all_workflow_instances includes token_no...")
        try:
            results = await client.get_all_workflow_instances(max_rows=3)
            if results:
                print(f"   ✓ Got {len(results)} InstanceForUser objects")
                first = results[0]
                print(f"   First instance: {first.instance_no}, token_no={first.token_no}")
                print(f"   TWA URL: {first.twa_url}")
            else:
                print("   No results (may be no active workflows)")
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_full_token_flow())
