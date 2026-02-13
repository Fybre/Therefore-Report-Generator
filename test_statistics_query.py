#!/usr/bin/env python3
"""Test script for ExecuteStatisticsQuery as fallback for workflow queries."""

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


async def test_statistics_query_fallback():
    """Test using ExecuteStatisticsQuery (type 102) as a fallback when ExecuteWorkflowQueryForAll fails."""
    
    # Load from .test.env first
    load_test_env()
    
    # Get tenant config from environment
    tenant_name = os.getenv("TEST_TENANT_NAME", "Demo")
    api_base = os.getenv("TEST_TENANT_URL", "https://demo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN", "your-token-here")
    
    print(f"Testing with tenant: {tenant_name}")
    print(f"API Base: {api_base}")
    print("-" * 60)
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Test 1: Try ExecuteWorkflowQueryForAll (may fail on some tenants)
        print("\n1. Testing ExecuteWorkflowQueryForAll...")
        try:
            instance_nos = await client.execute_workflow_query_for_all(max_rows=100)
            print(f"   Success! Got {len(instance_nos)} instances")
            if instance_nos:
                print(f"   First few: {instance_nos[:5]}")
            all_query_success = True
        except Exception as e:
            print(f"   Failed: {e}")
            all_query_success = False
        
        # Test 2: Try ExecuteStatisticsQuery with type 102
        print("\n2. Testing ExecuteStatisticsQuery (type 102 - workflow instances by process)...")
        try:
            # Query type 102 = workflow instances by process
            result = await client._post("ExecuteStatisticsQuery", {
                "QueryType": 102
            })
            print(f"   Raw response: {result}")
            
            # Handle response format: {'QueryResult': {'ResultRows': [...]}}
            query_result = result.get("QueryResult", {}) if result else {}
            stats_list = query_result.get("ResultRows", []) if query_result else []
            if stats_list:
                print(f"   Got {len(stats_list)} process entries")
                
                # Extract process IDs from EntryNo field (CountValue is the instance count)
                process_ids = []
                for entry in stats_list:
                    entry_no = entry.get("EntryNo")
                    count = entry.get("CountValue", 0)
                    name = entry.get("EntryName", "Unknown")
                    if entry_no and count > 0:
                        process_ids.append(entry_no)
                        print(f"   - Process {entry_no} ({name}): {count} instances")
                
                print(f"\n   Active processes to query: {process_ids}")
                statistics_success = True
            else:
                print(f"   Unexpected response format")
                statistics_success = False
                process_ids = []
        except Exception as e:
            print(f"   Failed: {e}")
            statistics_success = False
            process_ids = []
        
        # Test 3: If statistics worked, try querying each process
        if statistics_success and process_ids:
            print(f"\n3. Testing fallback: querying {len(process_ids)} individual processes...")
            all_instances = []
            for process_no in process_ids[:5]:  # Test first 5 only
                try:
                    instances = await client.execute_workflow_query_for_process(process_no, max_rows=1000)
                    print(f"   Process {process_no}: {len(instances)} instances")
                    all_instances.extend(instances)
                except Exception as e:
                    print(f"   Process {process_no}: FAILED - {e}")
            
            print(f"\n   Total instances from individual queries: {len(all_instances)}")
            
            # Remove duplicates
            unique = list(dict.fromkeys(all_instances))
            print(f"   Unique instances: {len(unique)}")
            
            if all_query_success:
                print(f"\n   Comparison:")
                print(f"   - ExecuteWorkflowQueryForAll: {len(instance_nos)} instances")
                print(f"   - Individual process queries: {len(unique)} instances")
        
        # Test 4: Try other statistics query types for reference
        print("\n4. Testing other statistics query types...")
        for query_type in [100, 101, 103]:
            try:
                result = await client._post("ExecuteStatisticsQuery", {
                    "QueryType": query_type
                })
                if result:
                    stats_list = result.get("StatisticsQueryResultList", [])
                    print(f"   Query type {query_type}: {len(stats_list)} entries")
                else:
                    print(f"   Query type {query_type}: No result")
            except Exception as e:
                print(f"   Query type {query_type}: Failed - {str(e)[:80]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing ExecuteStatisticsQuery Fallback")
    print("=" * 60)
    
    # Check for required env vars
    if not os.getenv("TEST_AUTH_TOKEN"):
        print("\nWARNING: TEST_AUTH_TOKEN not set. Using placeholder.")
        print("Set TEST_AUTH_TOKEN, TEST_TENANT_NAME, and TEST_TENANT_URL env vars.")
    
    asyncio.run(test_statistics_query_fallback())
