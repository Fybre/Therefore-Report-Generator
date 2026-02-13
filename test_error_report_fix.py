#!/usr/bin/env python3
"""Test script to verify error report logic."""

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


async def test_error_report():
    load_test_env()
    
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    print(f"\nTesting with tenant: {tenant_name}")
    print("=" * 60)
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: Query error instances WITH user expansion (old behavior)
        print("\n1. Testing get_all_workflow_instances WITH user expansion...")
        instances_with_expansion = await client.get_all_workflow_instances(
            workflow_flags=WorkflowFlags.ERROR_INSTANCES,
            skip_user_expansion=False
        )
        print(f"   Found {len(instances_with_expansion)} instances with user expansion")
        
        # Test 2: Query error instances WITHOUT user expansion (new behavior)
        print("\n2. Testing get_all_workflow_instances WITHOUT user expansion...")
        instances_without_expansion = await client.get_all_workflow_instances(
            workflow_flags=WorkflowFlags.ERROR_INSTANCES,
            skip_user_expansion=True
        )
        print(f"   Found {len(instances_without_expansion)} instances without user expansion")
        
        # Show sample results
        if instances_without_expansion:
            print("\n   Sample error instances:")
            for inst in instances_without_expansion[:4]:
                print(f"     - Instance {inst.instance_no}: {inst.task_name} (Process: {inst.process_name})")
                print(f"       Token: {inst.token_no}, User: {inst.user_display_name}")
                print(f"       TWA URL: {inst.twa_url}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Error Report Fix")
    print("=" * 60)
    asyncio.run(test_error_report())
