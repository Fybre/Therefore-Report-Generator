"""Report processing service."""
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
from collections import defaultdict

from app.store import (
    get_report_by_id, get_tenant_by_id, get_template_by_id, get_default_smtp_config,
    update_report, add_run_log
)
from app.services.therefore import ThereforeClient, InstanceForUser, sort_instances, InstanceSortOrder
from app.services.email import EmailTemplateRenderer, EmailService, EmailMessage


class ReportProcessor:
    """Processes reports and sends emails."""
    
    def __init__(self):
        """Initialize processor."""
        self.instances_found = 0
        self.emails_sent = 0
        self.emails_failed = 0
        self.messages: List[str] = []
    
    async def process_report(
        self,
        report_id: int,
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """Process a single report.
        
        Args:
            report_id: The report ID
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if successful
        """
        self.instances_found = 0
        self.emails_sent = 0
        self.emails_failed = 0
        self.messages = []
        
        # Get report
        report = get_report_by_id(report_id)
        
        if not report:
            self.messages.append(f"Report {report_id} not found")
            return False
        
        if not report.get('enabled', True):
            self.messages.append(f"Report {report['name']} is disabled")
            return False
        
        # Get tenant
        tenant = get_tenant_by_id(report['tenant_id'])
        
        if not tenant or not tenant.get('is_active', True):
            self.messages.append(f"Tenant for report {report['name']} not found or inactive")
            return False
        
        # Get template
        template = get_template_by_id(report['template_id'])
        
        if not template:
            self.messages.append(f"Template for report {report['name']} not found")
            return False
        
        # Get SMTP config
        smtp_config = get_default_smtp_config()
        
        if not smtp_config:
            self.messages.append("No default SMTP configuration found")
            return False
        
        # Create services
        print(f"[REPORT] Initializing services for report '{report['name']}'")
        print(f"[REPORT] Tenant: {tenant['name']} ({tenant['base_url']})")
        print(f"[REPORT] SMTP Config: {smtp_config['name']} ({smtp_config['server']}:{smtp_config['port']})")
        
        therefore_client = ThereforeClient(
            base_url=tenant['base_url'],
            tenant_name=tenant['name'],
            auth_token=tenant['auth_token']
        )
        
        email_service = EmailService(
            server=smtp_config['server'],
            port=smtp_config['port'],
            username=smtp_config['username'],
            password=smtp_config['password'],
            use_tls=smtp_config.get('use_tls', True),
            from_address=smtp_config['from_address'],
            from_name=smtp_config.get('from_name')
        )
        
        template_renderer = EmailTemplateRenderer(
            subject_template=template['subject_template'],
            body_template=template['body_template']
        )
        
        try:
            # Step 1: Get all workflow instances
            if progress_callback:
                await progress_callback("querying", 0, 0, "Starting workflow query...")
            
            process_nos = report.get('workflow_processes') or None
            
            async def query_progress(current, total, instance_no):
                if progress_callback:
                    await progress_callback(
                        "querying", 
                        current, 
                        total, 
                        f"Processing instance {instance_no}..."
                    )
            
            instances = await therefore_client.get_all_workflow_instances(
                process_nos=process_nos,
                max_rows=10000,
                progress_callback=query_progress
            )
            
            self.instances_found = len(instances)
            self.messages.append(f"Found {len(instances)} workflow instance assignments")
            
            if not instances:
                # No instances found - still update next run time
                self._update_report_schedule(report)
                add_run_log(report_id, "success", "No workflow instances found", 0, 0, 0)
                return True
            
            # Step 2: Group instances by user email
            instances_by_user: Dict[str, List[InstanceForUser]] = defaultdict(list)
            invalid_instances: List[InstanceForUser] = []

            for instance in instances:
                if instance.user_smtp and "@" in instance.user_smtp:
                    instances_by_user[instance.user_smtp].append(instance)
                else:
                    invalid_instances.append(instance)

            # Sort instances within each user's group
            sort_order = report.get('sort_order', InstanceSortOrder.default())
            for user_email in instances_by_user:
                instances_by_user[user_email] = sort_instances(instances_by_user[user_email], sort_order)

            self.messages.append(f"Grouped into {len(instances_by_user)} users")

            if invalid_instances:
                self.messages.append(f"Warning: {len(invalid_instances)} instances without valid email")

            # Step 3: Send emails
            if progress_callback:
                await progress_callback("emailing", 0, len(instances_by_user), "Sending emails...")
            
            email_messages = []
            recipients_list = []
            for user_email, user_instances in instances_by_user.items():
                # Determine recipient
                if report.get('send_all_to_admin') and report.get('admin_email'):
                    recipient = report['admin_email']
                else:
                    recipient = user_email
                
                recipients_list.append(f"{user_email} -> {recipient}")
                
                # Get user's display name (from first instance)
                user_display_name = user_instances[0].user_display_name if user_instances else "User"
                
                # Render email
                subject, body = template_renderer.render(
                    instances=user_instances,
                    user_display_name=user_display_name,
                    user_email=user_email
                )
                
                # Create email message
                email_messages.append(EmailMessage(
                    to_address=recipient,
                    from_address=smtp_config['from_address'],
                    subject=subject,
                    body_html=body,
                    from_name=smtp_config.get('from_name')
                ))
            
            # Print debug info about recipients
            print(f"[REPORT] Preparing to send {len(email_messages)} emails:")
            if report.get('send_all_to_admin') and report.get('admin_email'):
                print(f"[REPORT] Mode: ALL emails going to admin address: {report['admin_email']}")
            for recipient_info in recipients_list[:10]:  # Show first 10
                print(f"[REPORT]   {recipient_info}")
            if len(recipients_list) > 10:
                print(f"[REPORT]   ... and {len(recipients_list) - 10} more")
            
            # Send emails
            async def email_progress(current, total):
                if progress_callback:
                    await progress_callback(
                        "emailing",
                        current,
                        total,
                        f"Sent {current} of {total} emails..."
                    )
            
            sent, failed = await email_service.send_bulk(
                email_messages,
                progress_callback=email_progress
            )
            
            self.emails_sent = sent
            self.emails_failed = failed
            
            self.messages.append(f"Emails sent: {sent}, failed: {failed}")
            
            # Step 4: Update report schedule
            self._update_report_schedule(report)
            
            # Step 5: Log run
            status = "success" if failed == 0 else ("partial" if sent > 0 else "error")
            message = "; ".join(self.messages)
            add_run_log(
                report_id, 
                status, 
                message,
                instances_found=self.instances_found,
                emails_sent=sent,
                emails_failed=failed
            )
            
            return failed == 0
            
        except Exception as e:
            error_msg = f"Error processing report: {str(e)}"
            self.messages.append(error_msg)
            add_run_log(report_id, "error", error_msg)
            return False
        finally:
            await therefore_client.close()
    
    def _update_report_schedule(self, report: dict):
        """Update the report's next run time based on cron schedule.
        
        Args:
            report: The report to update
        """
        from croniter import croniter
        
        updates = {
            'last_run': datetime.utcnow().isoformat()
        }
        
        try:
            # Calculate next run from cron schedule
            itr = croniter(report['cron_schedule'], datetime.now())
            next_run = itr.get_next(datetime)
            updates['next_run'] = next_run.isoformat()
        except Exception as e:
            self.messages.append(f"Could not calculate next run: {e}")
            updates['next_run'] = None
        
        update_report(report['id'], updates)


    async def test_report(
        self,
        report_id: int,
        progress_callback: Optional[Callable] = None,
        template_id: int = None
    ) -> Dict[str, Any]:
        """Test a report without sending emails.
        
        Returns statistics and a preview of the first user's email.
        
        Args:
            report_id: The report ID
            progress_callback: Optional callback for progress updates
            template_id: Optional template ID to use instead of report's default
            
        Returns:
            Dictionary with test results and preview
        """
        self.instances_found = 0
        self.emails_sent = 0
        self.emails_failed = 0
        self.messages = []
        
        # Get report
        report = get_report_by_id(report_id)
        
        if not report:
            return {
                "success": False,
                "error": f"Report {report_id} not found",
                "instances_found": 0,
                "user_count": 0,
                "preview_html": None
            }
        
        # Note: Allow testing even if report is disabled
        if not report.get('enabled', True):
            self.messages.append(f"Note: Report '{report['name']}' is disabled but can still be tested")
        
        # Get tenant
        tenant = get_tenant_by_id(report['tenant_id'])
        
        if not tenant or not tenant.get('is_active', True):
            return {
                "success": False,
                "error": f"Tenant for report '{report['name']}' not found or inactive",
                "instances_found": 0,
                "user_count": 0,
                "preview_html": None
            }
        
        # Get template - use provided template_id or fall back to report's template
        template = get_template_by_id(template_id or report['template_id'])
        
        if not template:
            return {
                "success": False,
                "error": f"Template not found",
                "instances_found": 0,
                "user_count": 0,
                "preview_html": None
            }
        
        # Create Therefore client (no SMTP needed for test)
        therefore_client = ThereforeClient(
            base_url=tenant['base_url'],
            tenant_name=tenant['name'],
            auth_token=tenant['auth_token']
        )
        
        template_renderer = EmailTemplateRenderer(
            subject_template=template['subject_template'],
            body_template=template['body_template']
        )
        
        try:
            # Step 0: Test connection first
            if progress_callback:
                await progress_callback("querying", 0, 0, "Testing connection to Therefore...")
            
            connection_test = await therefore_client.test_connection()
            if not connection_test.get('success'):
                error_msg = connection_test.get('error', 'Unknown connection error')
                print(f"[REPORT] Connection test failed for tenant '{tenant['name']}': {error_msg}")
                return {
                    "success": False,
                    "error": f"Cannot connect to Therefore: {error_msg}",
                    "instances_found": 0,
                    "user_count": 0,
                    "preview_html": None,
                    "messages": self.messages
                }
            
            print(f"[REPORT] Connection test successful for tenant '{tenant['name']}', Customer ID: {connection_test.get('customer_id')}")
            
            # Step 1: Get all workflow instances
            if progress_callback:
                await progress_callback("querying", 0, 0, "Starting workflow query...")
            
            process_nos = report.get('workflow_processes') or None
            
            async def query_progress(current, total, instance_no):
                if progress_callback:
                    await progress_callback(
                        "querying", 
                        current, 
                        total, 
                        f"Processing instance {instance_no}..."
                    )
            
            print(f"[REPORT] Querying workflow instances for report '{report['name']}' (processes: {process_nos or 'all'})")
            instances = await therefore_client.get_all_workflow_instances(
                process_nos=process_nos,
                max_rows=10000,
                progress_callback=query_progress
            )
            
            self.instances_found = len(instances)
            print(f"[REPORT] Found {len(instances)} workflow instance assignments")
            self.messages.append(f"Found {len(instances)} workflow instance assignments")
            
            if not instances:
                return {
                    "success": True,
                    "error": None,
                    "instances_found": 0,
                    "user_count": 0,
                    "preview_html": None,
                    "messages": self.messages
                }
            
            # Step 2: Group instances by user email
            instances_by_user: Dict[str, List[InstanceForUser]] = defaultdict(list)
            invalid_instances: List[InstanceForUser] = []

            for instance in instances:
                if instance.user_smtp and "@" in instance.user_smtp:
                    instances_by_user[instance.user_smtp].append(instance)
                else:
                    invalid_instances.append(instance)

            # Sort instances within each user's group
            sort_order = report.get('sort_order', InstanceSortOrder.default())
            for user_email in instances_by_user:
                instances_by_user[user_email] = sort_instances(instances_by_user[user_email], sort_order)

            user_count = len(instances_by_user)
            self.messages.append(f"Grouped into {user_count} users")

            if invalid_instances:
                self.messages.append(f"Warning: {len(invalid_instances)} instances without valid email")

            # Step 3: Generate preview for user with most instances
            preview_html = None
            preview_user_email = None
            preview_user_instances = None
            max_instances = 0
            
            for user_email, user_instances in instances_by_user.items():
                if len(user_instances) > max_instances:
                    max_instances = len(user_instances)
                    preview_user_email = user_email
                    preview_user_instances = user_instances
            
            if preview_user_email and preview_user_instances:
                self.messages.append(f"Preview shows user '{preview_user_instances[0].user_display_name}' with {max_instances} tasks (most assigned)")
                
                # Determine recipient
                if report.get('send_all_to_admin') and report.get('admin_email'):
                    recipient = report['admin_email']
                else:
                    recipient = preview_user_email
                
                # Get user's display name (from first instance)
                user_display_name = preview_user_instances[0].user_display_name if preview_user_instances else "User"
                
                # Render email
                subject, body = template_renderer.render(
                    instances=preview_user_instances,
                    user_display_name=user_display_name,
                    user_email=preview_user_email
                )
                
                # Create preview HTML with header info (Outlook compatible)
                preview_html = f"""
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #f8f9fa; border-bottom: 2px solid #dee2e6; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 15px;">
                            <h5 style="margin: 0 0 10px 0;">Email Preview</h5>
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size: 14px;">
                                <tr>
                                    <td width="100" style="color: #6c757d; padding: 2px 0;">To:</td>
                                    <td style="padding: 2px 0;">{recipient}</td>
                                </tr>
                                <tr>
                                    <td width="100" style="color: #6c757d; padding: 2px 0;">Subject:</td>
                                    <td style="padding: 2px 0;">{subject}</td>
                                </tr>
                                <tr>
                                    <td width="100" style="color: #6c757d; padding: 2px 0;">From:</td>
                                    <td style="padding: 2px 0;">{template.get('from_name', 'Report Generator')} &lt;noreply@example.com&gt;</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
                <div style="border: 1px solid #dee2e6;">
                    {body}
                </div>
                """
            
            return {
                "success": True,
                "error": None,
                "instances_found": self.instances_found,
                "user_count": user_count,
                "preview_html": preview_html,
                "messages": self.messages,
                "template_used": {
                    "id": template['id'],
                    "name": template['name']
                }
            }
            
        except Exception as e:
            error_msg = f"Error testing report: {str(e)}"
            self.messages.append(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "instances_found": self.instances_found,
                "user_count": 0,
                "preview_html": None,
                "messages": self.messages
            }
        finally:
            await therefore_client.close()


    async def test_report_with_data(
        self,
        report_id: int,
        progress_callback: Optional[Callable] = None,
        template_id: int = None
    ) -> Dict[str, Any]:
        """Test a report without sending emails, returning data for re-rendering.
        
        Returns statistics, raw workflow data (for re-rendering), and a preview.
        
        Args:
            report_id: The report ID
            progress_callback: Optional callback for progress updates
            template_id: Optional template ID to use instead of report's default
            
        Returns:
            Dictionary with test results, raw data, and preview
        """
        self.instances_found = 0
        self.emails_sent = 0
        self.emails_failed = 0
        self.messages = []
        
        # Get report
        report = get_report_by_id(report_id)
        
        if not report:
            return {
                "success": False,
                "error": f"Report {report_id} not found",
                "instances_found": 0,
                "user_count": 0,
                "preview_html": None,
                "instances_data": None
            }
        
        # Note: Allow testing even if report is disabled
        if not report.get('enabled', True):
            self.messages.append(f"Note: Report '{report['name']}' is disabled but can still be tested")
        
        # Get tenant
        tenant = get_tenant_by_id(report['tenant_id'])
        
        if not tenant or not tenant.get('is_active', True):
            return {
                "success": False,
                "error": f"Tenant for report '{report['name']}' not found or inactive",
                "instances_found": 0,
                "user_count": 0,
                "preview_html": None,
                "instances_data": None
            }
        
        # Create Therefore client
        therefore_client = ThereforeClient(
            base_url=tenant['base_url'],
            tenant_name=tenant['name'],
            auth_token=tenant['auth_token']
        )
        
        try:
            # Step 0: Test connection first
            if progress_callback:
                await progress_callback("querying", 0, 0, "Testing connection to Therefore...")
            
            connection_test = await therefore_client.test_connection()
            if not connection_test.get('success'):
                error_msg = connection_test.get('error', 'Unknown connection error')
                print(f"[REPORT] Connection test failed for tenant '{tenant['name']}': {error_msg}")
                return {
                    "success": False,
                    "error": f"Cannot connect to Therefore: {error_msg}",
                    "instances_found": 0,
                    "user_count": 0,
                    "preview_html": None,
                    "instances_data": None,
                    "messages": self.messages
                }
            
            print(f"[REPORT] Connection test successful for tenant '{tenant['name']}', Customer ID: {connection_test.get('customer_id')}")
            
            # Step 1: Get all workflow instances
            if progress_callback:
                await progress_callback("querying", 0, 0, "Starting workflow query...")
            
            process_nos = report.get('workflow_processes') or None
            
            async def query_progress(current, total, instance_no):
                if progress_callback:
                    await progress_callback(
                        "querying", 
                        current, 
                        total, 
                        f"Processing instance {instance_no}..."
                    )
            
            print(f"[REPORT] Querying workflow instances for report '{report['name']}' (processes: {process_nos or 'all'})")
            instances = await therefore_client.get_all_workflow_instances(
                process_nos=process_nos,
                max_rows=10000,
                progress_callback=query_progress
            )
            
            self.instances_found = len(instances)
            self.messages.append(f"Found {len(instances)} workflow instance assignments")
            
            if not instances:
                return {
                    "success": True,
                    "error": None,
                    "instances_found": 0,
                    "user_count": 0,
                    "preview_html": None,
                    "instances_data": None,
                    "messages": self.messages
                }
            
            # Step 2: Group instances by user email
            from collections import defaultdict
            instances_by_user: Dict[str, List[InstanceForUser]] = defaultdict(list)
            invalid_instances: List[InstanceForUser] = []

            for instance in instances:
                if instance.user_smtp and "@" in instance.user_smtp:
                    instances_by_user[instance.user_smtp].append(instance)
                else:
                    invalid_instances.append(instance)

            # Sort instances within each user's group
            sort_order = report.get('sort_order', InstanceSortOrder.default())
            for user_email in instances_by_user:
                instances_by_user[user_email] = sort_instances(instances_by_user[user_email], sort_order)

            user_count = len(instances_by_user)
            self.messages.append(f"Grouped into {user_count} users")

            if invalid_instances:
                self.messages.append(f"Warning: {len(invalid_instances)} instances without valid email")

            # Serialize instances data for re-rendering
            instances_data = {}
            for user_email, user_instances in instances_by_user.items():
                instances_data[user_email] = [
                    {
                        "instance_no": inst.instance_no,
                        "process_no": inst.process_no,
                        "process_name": inst.process_name,
                        "task_name": inst.task_name,
                        "task_start": inst.task_start.isoformat() if inst.task_start else None,
                        "task_due": inst.task_due.isoformat() if inst.task_due else None,
                        "user_id": inst.user_id,
                        "user_display_name": inst.user_display_name,
                        "user_smtp": inst.user_smtp,
                        "index_data_string": inst.index_data_string,
                        "linked_documents": [
                            {
                                "doc_no": doc.doc_no,
                                "category_no": doc.category_no,
                                "category_name": doc.category_name,
                                "index_data": doc.index_data,
                                "full_string": doc.full_string
                            }
                            for doc in inst.linked_documents
                        ],
                        "is_overdue": inst.is_overdue,
                        "tenant_base_url": inst.tenant_base_url
                    }
                    for inst in user_instances
                ]
            
            # Step 3: Render preview with selected template
            preview_html = self._render_preview_html(
                report, instances_by_user, template_id or report['template_id']
            )
            
            # Get template info
            template = get_template_by_id(template_id or report['template_id'])
            
            return {
                "success": True,
                "error": None,
                "instances_found": self.instances_found,
                "user_count": user_count,
                "preview_html": preview_html,
                "instances_data": instances_data,
                "messages": self.messages,
                "template_used": {
                    "id": template['id'] if template else None,
                    "name": template['name'] if template else "Unknown"
                }
            }
            
        except Exception as e:
            error_msg = f"Error testing report: {str(e)}"
            self.messages.append(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "instances_found": self.instances_found,
                "user_count": 0,
                "preview_html": None,
                "instances_data": None,
                "messages": self.messages
            }
        finally:
            await therefore_client.close()
    
    def render_preview(
        self,
        report: dict,
        instances_data: dict,
        template_id: int = None
    ) -> Dict[str, Any]:
        """Render a preview using provided workflow data and a template.
        
        This allows re-rendering with different templates without re-querying Therefore.
        
        Args:
            report: The report configuration
            instances_data: Serialized instances data from test_report_with_data
            template_id: Optional template ID to use
            
        Returns:
            Dictionary with preview HTML
        """
        if not instances_data:
            return {
                "success": False,
                "error": "No instances data provided",
                "preview_html": None
            }
        
        # Get user with most instances for preview
        preview_user_email = None
        preview_user_instances = None
        max_instances = 0
        
        for user_email, user_instances in instances_data.items():
            if len(user_instances) > max_instances:
                max_instances = len(user_instances)
                preview_user_email = user_email
                preview_user_instances = user_instances
        
        if not preview_user_email or not preview_user_instances:
            return {
                "success": True,
                "error": None,
                "preview_html": None,
                "template_used": None
            }
        
        # Get tenant for base URL
        from app.store import get_tenant_by_id
        tenant = get_tenant_by_id(report['tenant_id'])
        tenant_base_url = tenant['base_url'] if tenant else ''
        
        # Convert serialized data back to objects for the template renderer
        from dataclasses import dataclass, field
        from datetime import datetime
        from typing import List

        @dataclass
        class SimpleLinkedDocument:
            doc_no: int
            category_no: int
            category_name: str
            index_data: str
            full_string: str

        @dataclass
        class SimpleInstance:
            instance_no: int
            process_no: int
            process_name: str
            task_name: str
            task_start: datetime
            task_due: datetime
            user_id: int
            user_display_name: str
            user_smtp: str
            linked_documents: List[SimpleLinkedDocument]
            tenant_base_url: str
            is_overdue: bool

            @property
            def index_data_string(self) -> str:
                """Get concatenated index data string (backwards compatible)."""
                return " | ".join(doc.full_string for doc in self.linked_documents if doc.full_string)

            @property
            def twa_url(self) -> str:
                """Get the Therefore Web Access URL for this instance."""
                return f"{self.tenant_base_url}/Viewer.aspx?InstanceNo={self.instance_no}"

        instances = []
        for inst_data in preview_user_instances:
            # Reconstruct linked documents
            linked_docs = []
            for doc_data in inst_data.get('linked_documents', []):
                linked_docs.append(SimpleLinkedDocument(
                    doc_no=doc_data.get('doc_no', 0),
                    category_no=doc_data.get('category_no', 0),
                    category_name=doc_data.get('category_name', ''),
                    index_data=doc_data.get('index_data', ''),
                    full_string=doc_data.get('full_string', '')
                ))

            instances.append(SimpleInstance(
                instance_no=inst_data['instance_no'],
                process_no=inst_data['process_no'],
                process_name=inst_data['process_name'],
                task_name=inst_data['task_name'],
                task_start=datetime.fromisoformat(inst_data['task_start']) if inst_data['task_start'] else datetime.now(),
                task_due=datetime.fromisoformat(inst_data['task_due']) if inst_data['task_due'] else None,
                user_id=inst_data['user_id'],
                user_display_name=inst_data['user_display_name'],
                user_smtp=inst_data['user_smtp'],
                linked_documents=linked_docs,
                tenant_base_url=tenant_base_url,
                is_overdue=inst_data.get('is_overdue', False)
            ))
        
        preview_html = self._render_preview_html(
            report, {preview_user_email: instances}, template_id or report['template_id']
        )
        
        template = get_template_by_id(template_id or report['template_id'])
        
        return {
            "success": True,
            "error": None,
            "preview_html": preview_html,
            "template_used": {
                "id": template['id'] if template else None,
                "name": template['name'] if template else "Unknown"
            }
        }
    
    def _render_preview_html(
        self,
        report: dict,
        instances_by_user: dict,
        template_id: int
    ) -> Optional[str]:
        """Render preview HTML for the user with the most instances."""
        # Get template
        template = get_template_by_id(template_id)
        if not template:
            return None
        
        template_renderer = EmailTemplateRenderer(
            subject_template=template['subject_template'],
            body_template=template['body_template']
        )
        
        # Get user with most instances
        preview_user_email = None
        preview_user_instances = None
        max_instances = 0
        
        for user_email, user_instances in instances_by_user.items():
            if len(user_instances) > max_instances:
                max_instances = len(user_instances)
                preview_user_email = user_email
                preview_user_instances = user_instances
        
        if not preview_user_email or not preview_user_instances:
            return None
        
        # Determine recipient
        if report.get('send_all_to_admin') and report.get('admin_email'):
            recipient = report['admin_email']
        else:
            recipient = preview_user_email
        
        # Get user's display name
        user_display_name = preview_user_instances[0].user_display_name if preview_user_instances else "User"
        
        # Render email
        subject, body = template_renderer.render(
            instances=preview_user_instances,
            user_display_name=user_display_name,
            user_email=preview_user_email
        )
        
        # Create preview HTML with header info (Outlook compatible)
        preview_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background: #f8f9fa; border-bottom: 2px solid #dee2e6; margin-bottom: 20px;">
            <tr>
                <td style="padding: 15px;">
                    <h5 style="margin: 0 0 10px 0;">Email Preview</h5>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-size: 14px;">
                        <tr>
                            <td width="100" style="color: #6c757d; padding: 2px 0;">To:</td>
                            <td style="padding: 2px 0;">{recipient}</td>
                        </tr>
                        <tr>
                            <td width="100" style="color: #6c757d; padding: 2px 0;">Subject:</td>
                            <td style="padding: 2px 0;">{subject}</td>
                        </tr>
                        <tr>
                            <td width="100" style="color: #6c757d; padding: 2px 0;">From:</td>
                            <td style="padding: 2px 0;">{template.get('from_name', 'Report Generator')} &lt;noreply@example.com&gt;</td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        <div style="border: 1px solid #dee2e6;">
            {body}
        </div>
        """
        
        return preview_html
