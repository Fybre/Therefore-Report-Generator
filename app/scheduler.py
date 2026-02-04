"""Background scheduler for running reports."""
import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.services.report import ReportProcessor
from app.store import get_reports_due_now


class ReportScheduler:
    """Scheduler for running reports."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.running = False
        self.current_jobs: dict = {}
        
    def start(self):
        """Start the scheduler."""
        if self.running:
            return
            
        settings = get_settings()
        
        self.scheduler = AsyncIOScheduler()
        
        # Add job to check for reports to run
        self.scheduler.add_job(
            self._check_and_run_reports,
            trigger=IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
            id="check_reports",
            replace_existing=True
        )
        
        self.scheduler.start()
        self.running = True
        print(f"Scheduler started - checking every {settings.SCHEDULER_INTERVAL_SECONDS} seconds")
    
    def stop(self):
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self.running = False
            print("Scheduler stopped")
    
    async def _check_and_run_reports(self):
        """Check for reports due and run them."""
        if not self.running:
            return
            
        try:
            # Get reports due now
            reports = get_reports_due_now()
            
            if reports:
                print(f"[{datetime.now()}] {len(reports)} report(s) due to run")
                
                # Run each report
                for report in reports:
                    print(f"  Running report: {report['name']}")
                    processor = ReportProcessor()
                    
                    try:
                        success = await processor.process_report(report['id'])
                        status = "✓" if success else "✗"
                        print(f"  {status} Report '{report['name']}' completed")
                    except Exception as e:
                        print(f"  ✗ Report '{report['name']}' failed: {e}")
                        
        except Exception as e:
            print(f"Error checking reports: {e}")
    
    async def run_report_now(self, report_id: int) -> tuple[bool, str]:
        """Manually run a report immediately.
        
        Args:
            report_id: The report ID to run
            
        Returns:
            Tuple of (success, message)
        """
        processor = ReportProcessor()
        
        try:
            success = await processor.process_report(report_id)
            message = "; ".join(processor.messages)
            return success, message
        except Exception as e:
            return False, f"Error: {str(e)}"


# Global scheduler instance
_scheduler: Optional[ReportScheduler] = None


def get_scheduler() -> ReportScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReportScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
