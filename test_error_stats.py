#!/usr/bin/env python3
"""Test script to check Workflow_ErrorInstancesByProcess (108) statistics query."""

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


async def test_error_statistics():
    load_test_env()
    
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    print(f"\nTesting with tenant: {tenant_name}")
    print("=" * 60)
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: Query type 108 - Error instances by process
        print("\n1. Testing ExecuteStatisticsQuery type 108 (Error instances by process)...")
        try:
            result = await client._post("ExecuteStatisticsQuery", {"QueryType": 108})
            
            if result:
                print(f"   Response keys: {result.keys()}")
                query_result = result.get("QueryResult", {})
                result_rows = query_result.get("ResultRows", [])
                print(f"   Got {len(result_rows)} process entries with errors")
                
                if result_rows:
                    print("\n   Processes with error instances:")
                    for entry in result_rows[:10]:  # Show first 10
                        entry_no = entry.get("EntryNo")
                        name = entry.get("EntryName", "Unknown")
                        count = entry.get("CountValue", 0)
                        print(f"     - Process {entry_no} ({name}): {count} errors")
            else:
                print("   No result returned")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test 2: Compare with type 102 (active instances)
        print("\n2. Testing ExecuteStatisticsQuery type 102 (Active instances by process)...")
        try:
            result = await client._post("ExecuteStatisticsQuery", {"QueryType": 102})
            
            if result:
                query_result = result.get("QueryResult", {})
                result_rows = query_result.get("ResultRows", [])
                print(f"   Got {len(result_rows)} process entries with active instances")
        except Exception as e:
            print(f"   Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Error Statistics Query (Type 108)")
    print("=" * 60)
    asyncio.run(test_error_statistics())
