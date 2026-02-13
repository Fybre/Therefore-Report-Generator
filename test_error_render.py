#!/usr/bin/env python3
"""Test script to verify error report rendering."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.therefore import ThereforeClient, WorkflowFlags
from app.services.email import EmailTemplateRenderer


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


async def test_error_render():
    load_test_env()
    
    tenant_name = os.getenv("TEST_TENANT2_NAME", "craigdemo")
    api_base = os.getenv("TEST_TENANT2_URL", "https://craigdemo.thereforeonline.com")
    auth_token = os.getenv("TEST_AUTH_TOKEN2", "")
    
    print(f"\nTesting with tenant: {tenant_name}")
    print("=" * 60)
    
    async with ThereforeClient(api_base, tenant_name, auth_token) as client:
        # Get error instances
        print("\n1. Querying error instances...")
        error_instances = await client.get_all_workflow_instances(
            workflow_flags=WorkflowFlags.ERROR_INSTANCES,
            skip_user_expansion=True
        )
        print(f"   Found {len(error_instances)} error instances")
        
        if not error_instances:
            print("   No error instances to test")
            return
        
        # Test rendering with the error template
        print("\n2. Testing email template rendering...")
        
        # Get the error template
        from app.services.email import create_default_templates
        templates = create_default_templates()
        subject_template, body_template = templates["error_workflows"]
        
        renderer = EmailTemplateRenderer(
            subject_template=subject_template,
            body_template=body_template
        )
        
        try:
            subject, body = renderer.render(
                instances=error_instances,
                user_display_name="Administrator",
                user_email="admin@example.com"
            )
            print(f"   ✓ Render successful!")
            print(f"   Subject: {subject}")
            print(f"   Body length: {len(body)} chars")
        except Exception as e:
            print(f"   ✗ Render failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Error Report Rendering")
    print("=" * 60)
    asyncio.run(test_error_render())
