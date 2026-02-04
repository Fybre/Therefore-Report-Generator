# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI web application that generates bulk workflow reports for Therefore (document management system) users. It replaces individual per-workflow email notifications with consolidated summary emails sent on cron schedules.

## Commands

### Development
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker
```bash
docker-compose up -d              # Start application (exposed on port 8088)
docker-compose logs -f            # View logs
docker-compose down               # Stop application
```

## Architecture

### Data Storage
All data is stored in YAML files in the `data/` directory (no database). The `app/store.py` module provides CRUD operations for all entities:
- `users.yaml` - User accounts with bcrypt password hashes
- `tenants.yaml` - Therefore instance configurations (base URL, auth token)
- `reports.yaml` - Report definitions with cron schedules
- `templates.yaml` - Jinja2 email templates
- `smtp.yaml` - SMTP server configurations
- `run_logs.yaml` - Report execution history

### Core Services

**ThereforeClient** (`app/services/therefore.py`): Async HTTP client for Therefore's REST API. Key operations:
- `get_all_workflow_instances()` - Main entry point that queries instances, fetches details, expands user groups, and returns flattened `InstanceForUser` objects
- Handles .NET date format parsing (`/Date(timestamp)/`)
- Expands `UserGroup` assignments to individual users recursively

**ReportProcessor** (`app/services/report.py`): Orchestrates report execution:
1. Fetches workflow instances from Therefore
2. Groups instances by user email
3. Renders Jinja2 templates with workflow data
4. Sends bulk emails via SMTP

**Scheduler** (`app/scheduler.py`): APScheduler-based background job that checks `reports.yaml` for due reports based on cron schedules.

### Authentication
JWT tokens stored in cookies or Authorization header. Three roles: `master_admin`, `tenant_admin`, `user`. Role checking via `RoleChecker` dependency class.

### Request Flow
```
Routers (app/routers/) -> Services (app/services/) -> Store (app/store.py) -> YAML files
```

## Email Template Context

Templates receive these Jinja2 variables:
- `instances` / `overdue` / `not_overdue` - Lists of workflow instances
- `instance_count` / `overdue_count` / `not_overdue_count` - Counts
- `user.display_name`, `user.email` - Recipient info

Each instance has:
- `instance_no`, `process_name`, `task_name`, `task_start`, `task_due`, `is_overdue`, `twa_url`
- `index_data_string` - Concatenated string of all linked document data (backwards compatible)
- `linked_documents` - List of linked documents with structured data:
  - `doc_no` - Document number
  - `category_no` - Category number
  - `category_name` - Category name (e.g., "Xero Invoices")
  - `index_data` - Index values without category name (e.g., "Acme Corp, INV-001, $1,234.00")
  - `full_string` - Full IndexDataString from Therefore

Example template usage:
```jinja2
{% for doc in instance.linked_documents %}
  <strong>{{ doc.category_name }}:</strong> {{ doc.index_data }}
{% endfor %}
```

Custom filters: `format_date`, `format_datetime`

## Key Configuration

Environment variables (via `.env` or docker-compose):
- `SECRET_KEY` - JWT signing key
- `SCHEDULER_INTERVAL_SECONDS` - How often to check for due reports (default: 60)
