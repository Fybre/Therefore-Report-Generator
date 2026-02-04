# Therefore Report Generator

A Python-based web application that generates bulk workflow reports for Therefore users. Consolidate individual workflow notifications into scheduled summary emails with role-based access control.

## Features

- **Multi-Tenancy**: Monitor multiple Therefore instances from a single dashboard
- **Scheduled Reports**: Automated reports using cron expressions
- **Role-Based Access Control**: Master Admin, Tenant Admin, and User roles
- **Email Templates**: Customizable Jinja2 templates with variables
- **Self-Service Setup**: Initial setup wizard (no pre-configuration required)
- **Password Reset**: Self-service password reset via email
- **Help System**: Built-in documentation for all features
- **YAML-based Storage**: No database required - all data in human-readable YAML files
- **Responsive Web UI**: Modern Bootstrap 5 interface

## Quick Start

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/therefore-report-generator.git
cd therefore-report-generator

# Start the application
docker-compose up -d

# Access the web UI
open http://localhost:8000

# Follow the setup wizard to create the admin account
```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Initial Setup

The first time you access the application, a setup wizard will guide you through:

1. **Create Admin Account** - Set up the master administrator
2. **Configure Base URL** - Auto-detected from your browser
3. **Login** - Use your email and password to access the system

After setup:
1. Configure **SMTP Settings** for email delivery
2. Add a **Therefore Tenant**
3. Create **Email Templates** (or use defaults)
4. Create **Reports** with schedules

## User Roles & Permissions

| Feature | Master Admin | Tenant Admin | User |
|---------|--------------|--------------|------|
| Manage Users | ✓ | ✗ | ✗ |
| Manage SMTP | ✓ | ✗ | ✗ |
| Manage Templates | ✓ | View Only | View Only |
| Manage All Tenants | ✓ | ✗ | ✗ |
| Manage Assigned Tenants | ✓ | ✓ | ✗ |
| Create Reports | ✓ | ✓ (assigned) | ✗ |
| Run Report Tests | ✓ | ✓ | ✓ |
| View Reports | ✓ | ✓ (assigned) | ✓ (assigned) |

## Email Template Variables

Use Jinja2 syntax to customize emails:

**User Variables:**
- `{{ user.name }}` - Recipient's display name
- `{{ user.email }}` - Recipient's email address

**Report Variables:**
- `{{ report.name }}` - Report name
- `{{ tenant.name }}` - Tenant name
- `{{ instances }}` - List of workflow instances
- `{{ instances|length }}` - Number of instances

**Instance Properties:**
- `{{ instance.process_name }}` - Workflow process name
- `{{ instance.task_name }}` - Current task name
- `{{ instance.task_due_date }}` - Due date
- `{{ instance.assigned_to }}` - Assigned user

### Example Template

```html
<p>Hello {{ user.name }},</p>

<p>You have {{ instances|length }} pending task(s):</p>

<ul>
{% for instance in instances %}
  <li>
    <strong>{{ instance.process_name }}</strong> - {{ instance.task_name }}
    {% if instance.task_due_date %}
      <br>Due: {{ instance.task_due_date }}
    {% endif %}
  </li>
{% endfor %}
</ul>
```

## Cron Schedule Examples

| Expression | Description |
|------------|-------------|
| `0 9 * * 1` | Every Monday at 9:00 AM |
| `0 9 * * *` | Every day at 9:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 9 1 * *` | First day of month at 9:00 AM |
| `0 17 * * 5` | Every Friday at 5:00 PM |

## Project Structure

```
therefore-report-generator/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings and configuration
│   ├── auth.py              # Authentication and authorization
│   ├── store.py             # YAML data storage layer
│   ├── schemas.py           # Pydantic validation schemas
│   ├── scheduler.py         # Background report scheduler
│   ├── routers/
│   │   ├── auth.py          # Authentication routes
│   │   ├── admin.py         # User administration
│   │   ├── dashboard.py     # Dashboard and stats
│   │   ├── tenants.py       # Tenant management
│   │   ├── reports.py       # Report management
│   │   ├── templates.py     # Email templates
│   │   ├── smtp.py          # SMTP configuration
│   │   ├── setup.py         # Initial setup wizard
│   │   └── help.py          # Help documentation
│   └── services/
│       ├── therefore.py     # Therefore API client
│       ├── email.py         # Email sending service
│       └── report.py        # Report processing
├── templates/               # Jinja2 HTML templates
│   ├── base.html            # Base layout
│   ├── dashboard.html       # Dashboard page
│   ├── admin/               # Admin templates
│   ├── help/                # Help documentation templates
│   └── ...
├── data/                    # YAML data storage (gitignored)
├── .gitignore               # Git ignore rules
├── .dockerignore            # Docker ignore rules
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Docker Compose configuration
└── requirements.txt         # Python dependencies
```

## Data Storage

All data is stored in YAML files in the `data/` directory:

- `users.yaml` - User accounts and roles
- `tenants.yaml` - Therefore tenant configurations
- `reports.yaml` - Report definitions and schedules
- `templates.yaml` - Email templates
- `smtp.yaml` - SMTP server configurations
- `run_logs.yaml` - Report execution history
- `audit_log.yaml` - Administrative action log
- `app_config.yaml` - Application configuration (BASE_URL)

## Environment Variables

Create a `.env` file for optional configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `SECRET_KEY` | `change-me` | JWT signing key |
| `SCHEDULER_INTERVAL_SECONDS` | `60` | Report check interval |

Note: Admin credentials and BASE_URL are now configured via the setup wizard, not environment variables.

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email/password
- `POST /auth/logout` - Logout
- `POST /auth/forgot-password` - Request password reset
- `POST /auth/reset-password` - Reset password with token
- `GET /auth/me` - Get current user info

### Users (Master Admin only)
- `GET /admin/api/users` - List all users
- `POST /admin/api/users` - Create user
- `PUT /admin/api/users/{id}` - Update user
- `DELETE /admin/api/users/{id}` - Delete user
- `POST /admin/api/users/{id}/reset-password` - Reset password

### Tenants
- `GET /api/tenants` - List tenants (filtered by role)
- `POST /api/tenants` - Create tenant (Master Admin)
- `GET /api/tenants/{id}` - Get tenant details
- `PUT /api/tenants/{id}` - Update tenant
- `DELETE /api/tenants/{id}` - Delete tenant (Master Admin)

### Reports
- `GET /api/reports` - List reports
- `POST /api/reports` - Create report
- `GET /api/reports/{id}` - Get report details
- `PUT /api/reports/{id}` - Update report
- `DELETE /api/reports/{id}` - Delete report
- `POST /api/reports/{id}/run` - Run report manually

### Email Templates
- `GET /api/templates` - List templates
- `POST /api/templates` - Create template (Master Admin)
- `GET /api/templates/{id}` - Get template
- `PUT /api/templates/{id}` - Update template (Master Admin)
- `DELETE /api/templates/{id}` - Delete template (Master Admin)

### SMTP
- `GET /api/smtp` - List SMTP configs (Master Admin)
- `POST /api/smtp` - Create SMTP config (Master Admin)
- `POST /api/smtp/{id}/test` - Test SMTP connection

## Troubleshooting

### Common Issues

**"No SMTP Server Configured" warning:**
- Go to SMTP Settings and add your email server configuration

**Cannot create reports:**
- Ensure at least one tenant is active and fully configured (Base URL + Auth Token)

**"Connection failed" when testing tenant:**
- Verify the Base URL is correct and accessible
- Check that the Auth Token is valid and not expired

**Emails not being sent:**
- Verify SMTP settings with the Test button
- Check run logs for error messages
- Ensure workflow instances have assigned users

### Logs

Check `data/run_logs.yaml` for report execution history, or view the Run Logs page in the web UI.

## Security Notes

- Change the default admin password immediately after setup
- Use HTTPS in production
- Keep your Therefore Auth Tokens secure
- Regularly review user access and roles
- SMTP passwords are stored in the data directory - ensure proper file permissions

## License

MIT License
