"""Email service with Jinja2 templating."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, BaseLoader, TemplateError

from app.services.therefore import InstanceForUser


@dataclass
class EmailMessage:
    """Email message."""
    to_address: str
    from_address: str
    subject: str
    body_html: str
    from_name: Optional[str] = None


class EmailTemplateRenderer:
    """Renders email templates using Jinja2."""
    
    def __init__(self, subject_template: str, body_template: str):
        """Initialize with templates.
        
        Args:
            subject_template: Jinja2 template for subject
            body_template: Jinja2 template for body
        """
        self.env = Environment(loader=BaseLoader())
        
        # Add custom filters
        self.env.filters['format_date'] = self._format_date
        self.env.filters['format_datetime'] = self._format_datetime
        
        self.subject_template = self.env.from_string(subject_template)
        self.body_template = self.env.from_string(body_template)
    
    @staticmethod
    def _format_date(value: datetime, format_str: str = "%Y-%m-%d") -> str:
        """Format a datetime as date string."""
        if not value:
            return "-"
        return value.strftime(format_str)
    
    @staticmethod
    def _format_datetime(value: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """Format a datetime."""
        if not value:
            return "-"
        return value.strftime(format_str)
    
    def render(
        self, 
        instances: List[InstanceForUser],
        user_display_name: str,
        user_email: str
    ) -> tuple[str, str]:
        """Render email subject and body.
        
        Args:
            instances: List of workflow instances for this user
            user_display_name: The user's display name
            user_email: The user's email address
            
        Returns:
            Tuple of (subject, body_html)
        """
        # Separate overdue and not overdue
        overdue = [i for i in instances if i.is_overdue]
        not_overdue = [i for i in instances if not i.is_overdue]
        
        # Build context for template
        context = {
            # User info
            'user': {
                'display_name': user_display_name,
                'email': user_email,
            },
            
            # All instances
            'instances': instances,
            'instance_count': len(instances),
            
            # Overdue instances
            'overdue': overdue,
            'overdue_count': len(overdue),
            
            # Not overdue instances
            'not_overdue': not_overdue,
            'not_overdue_count': len(not_overdue),
            
            # System info
            'now': datetime.now(),
            'timezone': datetime.now().astimezone().tzname(),
        }
        
        try:
            subject = self.subject_template.render(**context)
            body = self.body_template.render(**context)
            return subject, body
        except TemplateError as e:
            raise ValueError(f"Template rendering error: {e}")


class EmailService:
    """Service for sending emails."""
    
    def __init__(
        self,
        server: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        from_address: str = None,
        from_name: str = None
    ):
        """Initialize email service.
        
        Args:
            server: SMTP server
            port: SMTP port
            username: SMTP username
            password: SMTP password
            use_tls: Whether to use TLS
            from_address: Default from address
            from_name: Default from name
        """
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_address = from_address
        self.from_name = from_name
    
    async def send(self, message: EmailMessage) -> bool:
        """Send an email.
        
        Args:
            message: Email message to send
            
        Returns:
            True if sent successfully
        """
        # Build MIME message
        mime_msg = MIMEMultipart('alternative')
        mime_msg['Subject'] = message.subject
        mime_msg['From'] = f"{message.from_name or self.from_name or 'Report Generator'} <{message.from_address}>"
        mime_msg['To'] = message.to_address
        
        # Attach HTML body
        html_part = MIMEText(message.body_html, 'html')
        mime_msg.attach(html_part)
        
        print(f"[SMTP] Connecting to {self.server}:{self.port} (TLS={self.use_tls}) with user '{self.username}'")
        print(f"[SMTP] Sending email to: {message.to_address} (Subject: {message.subject[:50]}...)")
        
        try:
            await aiosmtplib.send(
                mime_msg,
                hostname=self.server,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls
            )
            print(f"[SMTP] ✓ Email sent successfully to {message.to_address}")
            return True
        except Exception as e:
            print(f"[SMTP] ✗ Failed to send email to {message.to_address}: {e}")
            return False
    
    async def send_bulk(
        self, 
        messages: List[EmailMessage],
        progress_callback=None
    ) -> tuple[int, int]:
        """Send multiple emails.
        
        Args:
            messages: List of email messages
            progress_callback: Optional callback(sent, total)
            
        Returns:
            Tuple of (sent_count, failed_count)
        """
        sent = 0
        failed = 0
        total = len(messages)
        
        for i, message in enumerate(messages):
            if await self.send(message):
                sent += 1
            else:
                failed += 1
            
            if progress_callback:
                await progress_callback(i + 1, total)
        
        return sent, failed
    
    @classmethod
    def from_smtp_config(cls, config) -> "EmailService":
        """Create email service from SMTP config model.
        
        Args:
            config: SMTPConfig model instance
            
        Returns:
            EmailService instance
        """
        return cls(
            server=config.server,
            port=config.port,
            username=config.username,
            password=config.password,
            use_tls=config.use_tls,
            from_address=config.from_address,
            from_name=config.from_name
        )


def create_default_templates() -> dict:
    """Create default email templates.
    
    Returns:
        Dictionary of template name -> (subject, body)
    """
    templates = {}
    
    # Template 1: All instances listed with overdue highlighted in red
    templates["all_instances"] = (
        "Workflow Report - {{ now.strftime('%Y-%m-%d %H:%M') }}",
        """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background-color: #3498db; color: white; padding: 14px; text-align: left; font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid #eee; }
        tr.overdue { background-color: #ffe6e6; }
        tr.overdue td { color: #c0392b; font-weight: 500; }
        .overdue-badge { background-color: #e74c3c; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; margin-left: 8px; }
        a { color: #3498db; text-decoration: none; font-weight: 500; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #7f8c8d; text-align: center; }
        .no-tasks { text-align: center; padding: 40px; color: #7f8c8d; font-style: italic; background: #f8f9fa; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Workflow Task Report</h1>
        
        <p>Hello {{ user.display_name }},</p>
        
        <p>The following workflow tasks have been assigned to you, or to a group you are a member of. 
        Click on the task name to open and process the task.</p>
        
        {% if instances %}
            <!-- Summary Section - Outlook Compatible -->
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0; background-color: #667eea;">
                <tr>
                    <td style="padding: 20px;">
                        <table width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                                <td width="33%" align="center" style="padding: 10px; color: white; border-right: 1px solid rgba(255,255,255,0.3);">
                                    <span style="font-size: 32px; font-weight: bold; display: block;">{{ instance_count }}</span>
                                    <span style="font-size: 12px; text-transform: uppercase;">Total Tasks</span>
                                </td>
                                <td width="33%" align="center" style="padding: 10px; color: #ff6b6b; border-right: 1px solid rgba(255,255,255,0.3);">
                                    <span style="font-size: 32px; font-weight: bold; display: block;">{{ overdue_count }}</span>
                                    <span style="font-size: 12px; text-transform: uppercase; color: white;">Overdue</span>
                                </td>
                                <td width="33%" align="center" style="padding: 10px; color: #51cf66;">
                                    <span style="font-size: 32px; font-weight: bold; display: block;">{{ not_overdue_count }}</span>
                                    <span style="font-size: 12px; text-transform: uppercase; color: white;">On Track</span>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            
            <h2>All Workflow Tasks ({{ instance_count }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Task</th>
                        <th>Workflow</th>
                        <th>Details</th>
                        <th>Started</th>
                        <th>Due Date</th>
                    </tr>
                </thead>
                <tbody>
                    {% for instance in instances %}
                    <tr class="{% if instance.is_overdue %}overdue{% endif %}">
                        <td>
                            <a href="{{ instance.twa_url }}">{{ instance.task_name }}</a>
                            {% if instance.is_overdue %}
                                <span class="overdue-badge">OVERDUE</span>
                            {% endif %}
                        </td>
                        <td>{{ instance.process_name }}</td>
                        <td>{{ instance.index_data_string or '-' }}</td>
                        <td>{{ instance.task_start | format_date }}</td>
                        <td>{{ instance.task_due | format_date if instance.task_due else '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <div class="no-tasks">No workflow tasks found.</div>
        {% endif %}
        
        <div class="footer">
            <p>Generated at {{ now | format_datetime }} &bull; Server Timezone: {{ timezone }}</p>
            <p><small>Do not reply to this email.</small></p>
        </div>
    </div>
</body>
</html>"""
    )
    
    # Template 2: Overdue instances only
    templates["overdue_only"] = (
        "Overdue Workflow Tasks - {{ now.strftime('%Y-%m-%d %H:%M') }}",
        """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #c0392b; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background-color: #e74c3c; color: white; padding: 14px; text-align: left; font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid #f5c6cb; background-color: #fff5f5; }
        a { color: #c0392b; text-decoration: none; font-weight: 600; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #7f8c8d; text-align: center; }
        .no-tasks { text-align: center; padding: 30px; color: #27ae60; background: #d4edda; border-radius: 8px; margin: 20px 0; }
        .on-track-info { text-align: center; padding: 15px; color: #155724; background: #d4edda; border-radius: 8px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Overdue Workflow Tasks</h1>
        
        <p>Hello {{ user.display_name }},</p>
        
        {% if overdue %}
            <!-- Summary Section - Outlook Compatible -->
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0; background-color: #e74c3c;">
                <tr>
                    <td style="padding: 20px; text-align: center; color: white;">
                        <span style="font-size: 48px; font-weight: bold; display: block;">{{ overdue_count }}</span>
                        <span style="font-size: 14px; text-transform: uppercase;">Overdue Task{% if overdue_count != 1 %}s{% endif %} Requiring Attention</span>
                    </td>
                </tr>
            </table>
            
            <!-- Warning Box - Outlook Compatible -->
            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
                <tr>
                    <td style="background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px 20px;">
                        <strong>Action Required:</strong> You have {{ overdue_count }} overdue workflow task(s) that require immediate attention.
                    </td>
                </tr>
            </table>
            
            <!-- On-Track Count -->
            {% if not_overdue_count > 0 %}
            <div class="on-track-info">
                <strong>Good news:</strong> You also have {{ not_overdue_count }} on-track task{% if not_overdue_count != 1 %}s{% endif %} in good standing.
            </div>
            {% endif %}
            
            <table>
                <thead>
                    <tr>
                        <th>Task</th>
                        <th>Workflow</th>
                        <th>Details</th>
                        <th>Started</th>
                        <th>Due Date</th>
                    </tr>
                </thead>
                <tbody>
                    {% for instance in overdue %}
                    <tr>
                        <td><a href="{{ instance.twa_url }}">{{ instance.task_name }}</a></td>
                        <td>{{ instance.process_name }}</td>
                        <td>{{ instance.index_data_string or '-' }}</td>
                        <td>{{ instance.task_start | format_date }}</td>
                        <td>{{ instance.task_due | format_date if instance.task_due else '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <div class="no-tasks">
                <strong>No overdue tasks. Great job!</strong><br>
                {% if not_overdue_count > 0 %}
                <small>You have {{ not_overdue_count }} on-track task{% if not_overdue_count != 1 %}s{% endif %} in good standing.</small>
                {% else %}
                <small>You have no workflow tasks assigned.</small>
                {% endif %}
            </div>
        {% endif %}
        
        <div class="footer">
            <p>Generated at {{ now | format_datetime }} &bull; Server Timezone: {{ timezone }}</p>
            <p><small>Do not reply to this email.</small></p>
        </div>
    </div>
</body>
</html>"""
    )
    
    # Template 3: Separated sections - two tables (not overdue and overdue)
    templates["separated_sections"] = (
        "Workflow Summary - {{ now.strftime('%Y-%m-%d %H:%M') }}",
        """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; padding-bottom: 10px; border-bottom: 2px solid #ecf0f1; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th { background-color: #34495e; color: white; padding: 12px; text-align: left; font-weight: 600; }
        td { padding: 12px; border-bottom: 1px solid #ecf0f1; }
        tr.overdue td { background-color: #ffe6e6; color: #c0392b; }
        a { color: #3498db; text-decoration: none; font-weight: 500; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #7f8c8d; text-align: center; }
        .empty { color: #95a5a6; font-style: italic; padding: 30px; text-align: center; background: #f8f9fa; border-radius: 8px; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Workflow Task Summary</h1>
        
        <p>Hello {{ user.display_name }},</p>
        
        <!-- Summary Section - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0; background-color: #667eea;">
            <tr>
                <td style="padding: 20px;">
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="33%" align="center" style="padding: 15px; color: white; border-right: 1px solid rgba(255,255,255,0.3);">
                                <span style="font-size: 36px; font-weight: bold; display: block;">{{ instance_count }}</span>
                                <span style="font-size: 12px; text-transform: uppercase;">Total Tasks</span>
                            </td>
                            <td width="33%" align="center" style="padding: 15px; color: #ff6b6b; border-right: 1px solid rgba(255,255,255,0.3);">
                                <span style="font-size: 36px; font-weight: bold; display: block;">{{ overdue_count }}</span>
                                <span style="font-size: 12px; text-transform: uppercase; color: white;">Overdue</span>
                            </td>
                            <td width="33%" align="center" style="padding: 15px; color: #51cf66;">
                                <span style="font-size: 36px; font-weight: bold; display: block;">{{ not_overdue_count }}</span>
                                <span style="font-size: 12px; text-transform: uppercase; color: white;">On Track</span>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        
        {% if overdue %}
        <!-- Overdue Section Header - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 25px;">
            <tr>
                <td style="background-color: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px;">
                    <div style="font-size: 18px; font-weight: 600; color: #c0392b;">Overdue Tasks</div>
                    <div style="font-size: 14px; color: #7f8c8d; margin-top: 5px;">{{ overdue_count }} task{% if overdue_count != 1 %}s{% endif %} requiring immediate attention</div>
                </td>
            </tr>
        </table>
        <table>
            <thead>
                <tr>
                    <th style="background-color: #c0392b;">Task</th>
                    <th style="background-color: #c0392b;">Workflow</th>
                    <th style="background-color: #c0392b;">Details</th>
                    <th style="background-color: #c0392b;">Started</th>
                    <th style="background-color: #c0392b;">Due Date</th>
                </tr>
            </thead>
            <tbody>
                {% for instance in overdue %}
                <tr class="overdue">
                    <td><a href="{{ instance.twa_url }}" style="color: #c0392b;">{{ instance.task_name }}</a></td>
                    <td>{{ instance.process_name }}</td>
                    <td>{{ instance.index_data_string or '-' }}</td>
                    <td>{{ instance.task_start | format_date }}</td>
                    <td>{{ instance.task_due | format_date if instance.task_due else '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
        
        {% if not_overdue %}
        <!-- On Track Section Header - Outlook Compatible -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 25px;">
            <tr>
                <td style="background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px;">
                    <div style="font-size: 18px; font-weight: 600; color: #2c3e50;">On Track Tasks</div>
                    <div style="font-size: 14px; color: #7f8c8d; margin-top: 5px;">{{ not_overdue_count }} task{% if not_overdue_count != 1 %}s{% endif %} in good standing</div>
                </td>
            </tr>
        </table>
        <table>
            <thead>
                <tr>
                    <th>Task</th>
                    <th>Workflow</th>
                    <th>Details</th>
                    <th>Started</th>
                    <th>Due Date</th>
                </tr>
            </thead>
            <tbody>
                {% for instance in not_overdue %}
                <tr>
                    <td><a href="{{ instance.twa_url }}">{{ instance.task_name }}</a></td>
                    <td>{{ instance.process_name }}</td>
                    <td>{{ instance.index_data_string or '-' }}</td>
                    <td>{{ instance.task_start | format_date }}</td>
                    <td>{{ instance.task_due | format_date if instance.task_due else '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
        
        {% if not instances %}
        <p class="empty">No workflow tasks found.</p>
        {% endif %}
        
        <div class="footer">
            <p>Generated at {{ now | format_datetime }} &bull; Server Timezone: {{ timezone }}</p>
            <p><small>Do not reply to this email.</small></p>
        </div>
    </div>
</body>
</html>"""
    )
    
    return templates
