"""Therefore Web API client."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import List, Optional, Dict, Any
import httpx
import re

# Simple in-memory cache for workflow processes
# Key: (tenant_name, cache_type), Value: (timestamp, data)
_process_cache: Dict[tuple, tuple] = {}
_PROCESS_CACHE_TTL = timedelta(hours=1)  # Cache processes for 1 hour

def _get_cache(key: tuple) -> Optional[Any]:
    """Get cached data if not expired."""
    if key not in _process_cache:
        return None
    timestamp, data = _process_cache[key]
    if datetime.utcnow() - timestamp > _PROCESS_CACHE_TTL:
        del _process_cache[key]
        return None
    return data

def _set_cache(key: tuple, data: Any) -> None:
    """Set cached data with current timestamp."""
    _process_cache[key] = (datetime.utcnow(), data)

def clear_process_cache(tenant_name: str = None) -> None:
    """Clear the workflow process cache.
    
    Args:
        tenant_name: If provided, only clear cache for this tenant.
                    If None, clear all cached process lists.
    """
    global _process_cache
    if tenant_name:
        keys_to_remove = [k for k in _process_cache.keys() if k[0] == tenant_name]
        for key in keys_to_remove:
            del _process_cache[key]
        print(f"[THEREFORE] Cleared workflow process cache for {tenant_name}")
    else:
        _process_cache.clear()
        print("[THEREFORE] Cleared all workflow process cache")


def parse_dotnet_date(date_str: str) -> Optional[datetime]:
    """Parse .NET /Date(timestamp)/ format or ISO format.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    # Handle /Date(1234567890)/ format (milliseconds since epoch)
    dotnet_match = re.match(r'/Date\((\d+)(?:[+-]\d{4})?\)/', date_str)
    if dotnet_match:
        timestamp_ms = int(dotnet_match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    
    # Handle ISO format with Z
    if 'Z' in date_str:
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass
    
    # Handle standard ISO format
    try:
        return datetime.fromisoformat(date_str)
    except:
        pass
    
    return None


class WorkflowInstanceStatus(IntEnum):
    """Workflow instance status enum."""
    DOC_STATUS_CHECKED_IN = 0
    DOC_STATUS_CHECKED_OUT_BY_USER = 1
    DOC_STATUS_CHECKED_OUT = 2
    CASE_STATUS_NORMAL = 10
    CASE_STATUS_CLOSED = 11


class WorkflowFlags(IntEnum):
    """Workflow query flags for ExecuteWorkflowQueryForAll/ExecuteWorkflowQueryForProcess.

    These flags filter which workflow instances are returned by the query.
    Flags can be combined using bitwise OR for multiple filters.
    """
    DEFAULT_INSTANCES = 0   # Standard workflow instances (behavior varies by system)
    RUNNING_INSTANCES = 1   # Currently executing processes
    FINISHED_INSTANCES = 2  # Completed processes
    ALL_INSTANCES = 3       # All workflow instances regardless of state
    ERROR_INSTANCES = 4     # Processes that encountered errors
    OVERDUE_INSTANCES = 8   # Processes exceeding time limits


class InstanceSortOrder(str):
    """Sort order options for workflow instances in reports."""
    TASK_DUE_DATE = "task_due_date"      # By task due date (overdue first)
    PROCESS_NAME = "process_name"         # By process name, then task due date
    TASK_START_DATE = "task_start_date"   # By task start date (chronological)

    @classmethod
    def choices(cls) -> list:
        """Return list of (value, label) tuples for form select."""
        return [
            (cls.TASK_DUE_DATE, "Task Due Date (overdue first)"),
            (cls.PROCESS_NAME, "Process Name, then Due Date"),
            (cls.TASK_START_DATE, "Task Start Date (chronological)"),
        ]

    @classmethod
    def default(cls) -> str:
        return cls.TASK_DUE_DATE


class UserType(IntEnum):
    """User type enum from GetUserDetails/GetUsersFromGroup.
    
    Values from API:
    - 1 = SingleUser (regular user)
    - 2 = UserGroup (group that can be expanded)
    """
    SINGLE_USER = 1  # SingleUser
    USER_GROUP = 2   # UserGroup
    SYSTEM_USER = 3  # SystemUser (if exists)


class CounterMode(IntEnum):
    """Counter mode enum for category fields."""
    UNDEFINED = 0
    CLIENT_COUNTER = 1
    SERVER_COUNTER = 2


class DependencyMode(IntEnum):
    """Dependency mode enum for category fields."""
    REFERENCED = 0
    SYNCHRONIZED_REDUNDANT = 1
    EDITABLE_REDUNDANT = 2


class FieldType(IntEnum):
    """Category field type enum."""
    STRING_FIELD = 1
    INT_FIELD = 2
    DATE_FIELD = 3
    LABEL_FIELD = 4
    MONEY_FIELD = 5
    LOGICAL_FIELD = 6
    NUMERIC_COUNTER = 8
    TEXT_COUNTER = 9
    TABLE_FIELD = 10
    CUSTOM_FIELD = 99


class TypeGroup(IntEnum):
    """Type group enum for category fields."""
    STANDARD_TYPE_GROUP = 1
    KEYWORD_TYPE_GROUP = 2
    USER_INT = 3
    USER_TEXT_ANSI = 4
    USER_DATE = 5
    USER_FLOAT = 6
    USER_TEXT_UNICODE = 7
    CASE_DEFINITION_TYPE_GROUP = 8


class HorizontalAlignment(IntEnum):
    """Horizontal alignment enum."""
    LEFT = 0
    CENTER_H = 1
    RIGHT = 2


@dataclass
class UserDetail:
    """User detail from Therefore."""
    user_id: int
    display_name: str
    smtp: str
    user_type: UserType  # SINGLE_USER, USER_GROUP, or SYSTEM_USER
    disabled: bool = False


@dataclass
class LinkedDocument:
    """A document linked to a workflow instance."""
    doc_no: int
    category_no: int
    category_name: str
    index_data: str  # The index data portion (after category name)
    full_string: str  # The full IndexDataString

    @classmethod
    def from_index_string(cls, doc_no: int, category_no: int, index_data_string: str) -> 'LinkedDocument':
        """Parse a LinkedDocument from an IndexDataString.

        The IndexDataString format is typically: "Category Name - Value1, Value2, ..."
        """
        full_string = index_data_string or ""

        # Try to split on " - " to separate category name from data
        if " - " in full_string:
            parts = full_string.split(" - ", 1)
            category_name = parts[0].strip()
            index_data = parts[1].strip() if len(parts) > 1 else ""
        else:
            # No separator found, use the whole string
            category_name = ""
            index_data = full_string

        return cls(
            doc_no=doc_no,
            category_no=category_no,
            category_name=category_name,
            index_data=index_data,
            full_string=full_string
        )


@dataclass
class WorkflowInstance:
    """Workflow instance detail."""
    instance_no: int
    process_no: int
    process_name: str
    task_name: str
    task_start: datetime
    task_due: Optional[datetime]
    process_start_date: datetime
    linked_documents: List[LinkedDocument]
    assigned_to_users: List[UserDetail]

    @property
    def index_data_string(self) -> str:
        """Get concatenated index data string (backwards compatible)."""
        return " | ".join(doc.full_string for doc in self.linked_documents if doc.full_string)


@dataclass
class InstanceForUser:
    """Flattened instance assigned to a specific user."""
    instance_no: int
    process_no: int
    process_name: str
    task_name: str
    task_start: datetime
    task_due: Optional[datetime]
    process_start_date: datetime
    user_id: int
    user_display_name: str
    user_smtp: str
    linked_documents: List[LinkedDocument]
    tenant_base_url: str
    token_no: int = 0  # Token number for TWA URL and grouping

    @property
    def index_data_string(self) -> str:
        """Get concatenated index data string (backwards compatible)."""
        return " | ".join(doc.full_string for doc in self.linked_documents if doc.full_string)

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.task_due:
            # Make sure we compare offset-aware datetimes
            now = datetime.now(self.task_due.tzinfo) if self.task_due.tzinfo else datetime.now()
            return now > self.task_due
        return False

    @property
    def twa_url(self) -> str:
        """Get the Therefore Web Access URL for this instance.
        
        Uses the new TDWV format with token number for direct task access.
        """
        return f"{self.tenant_base_url}/tdwv/#/workflows/instance/{self.instance_no}/{self.token_no}"


def sort_instances(instances: List[InstanceForUser], sort_order: str) -> List[InstanceForUser]:
    """Sort a list of instances based on the specified sort order.

    Args:
        instances: List of InstanceForUser objects to sort
        sort_order: One of InstanceSortOrder values

    Returns:
        Sorted list of instances
    """
    if not instances:
        return instances

    # Far future date for instances without due date (sort to end)
    far_future = datetime(9999, 12, 31, tzinfo=timezone.utc)

    if sort_order == InstanceSortOrder.TASK_DUE_DATE:
        # Sort by: overdue first, then by due date ascending, no due date last
        def due_date_key(inst):
            if inst.task_due is None:
                return (2, far_future)  # No due date - sort last
            elif inst.is_overdue:
                return (0, inst.task_due)  # Overdue - sort first
            else:
                return (1, inst.task_due)  # Not overdue - sort by date
        return sorted(instances, key=due_date_key)

    elif sort_order == InstanceSortOrder.PROCESS_NAME:
        # Sort by process name, then by due date
        def process_name_key(inst):
            due = inst.task_due if inst.task_due else far_future
            return (inst.process_name.lower(), due)
        return sorted(instances, key=process_name_key)

    elif sort_order == InstanceSortOrder.TASK_START_DATE:
        # Sort by task start date (chronological, oldest first)
        return sorted(instances, key=lambda inst: inst.task_start or far_future)

    else:
        # Default to task due date if unknown sort order
        return sort_instances(instances, InstanceSortOrder.TASK_DUE_DATE)


class ThereforeClient:
    """Client for Therefore Web API."""
    
    # Default workflow flag for queries - use RUNNING_INSTANCES for consistent behavior
    DEFAULT_WORKFLOW_FLAG = WorkflowFlags.RUNNING_INSTANCES
    
    def __init__(self, base_url: str, tenant_name: str, auth_token: str, is_single_instance: bool = False):
        """Initialize the Therefore client.
        
        Args:
            base_url: The Therefore instance base URL (e.g., https://company.thereforeonline.com)
            tenant_name: The tenant name
            auth_token: The authorization token
            is_single_instance: If True, the TenantName header will not be sent (for single-instance on-prem servers)
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/theservice/v0001/restun"
        self.tenant_name = tenant_name
        self.auth_token = auth_token
        self.is_single_instance = is_single_instance
        self.client = httpx.AsyncClient(timeout=300.0)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Authorization": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Only include TenantName header for multi-tenant (cloud) instances
        if not self.is_single_instance:
            headers["TenantName"] = self.tenant_name
        return headers
    
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make a POST request to the API."""
        url = f"{self.api_base}/{endpoint}"
        try:
            response = await self.client.post(
                url,
                headers=self._get_headers(),
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_text = str(e.response.text)
            # Don't print errors that are handled gracefully by callers
            if "User has wrong type" not in error_text and "BuildWorkflowQuery failed" not in error_text:
                print(f"[THEREFORE] HTTP error {e.response.status_code} on {endpoint}: {e.response.text}")
            return None
        except Exception as e:
            print(f"[THEREFORE] Request error on {endpoint}: {type(e).__name__}: {e}")
            return None
    
    async def _get(self, endpoint: str) -> Optional[Any]:
        """Make a GET request to the API."""
        url = f"{self.api_base}/{endpoint}"
        headers = self._get_headers()
        # Request JSON response
        headers["Accept"] = "application/json"
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Request error: {e}")
            raise
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to the Therefore server.
        
        Returns:
            Dictionary with success status and customer_id or error message
        """
        try:
            # Call GetSystemCustomerId endpoint - returns {"CustomerId": "..."}
            result = await self._get("GetSystemCustomerId")
            if result and isinstance(result, dict) and "CustomerId" in result:
                return {
                    "success": True,
                    "customer_id": result["CustomerId"]
                }
            return {
                "success": False,
                "error": "Invalid response from server"
            }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_all_workflow_processes(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get a list of all workflow processes.

        Uses GetObjectsList with Type=19 (WorkflowProcess) which is much faster
        than querying all instances. Results are cached for 1 hour.

        Args:
            use_cache: Whether to use cached data if available (default: True)

        Returns:
            List of dictionaries with process_no, process_name, and folder_name
        """
        cache_key = (self.tenant_name, "workflow_processes")
        
        # Try cache first
        if use_cache:
            cached = _get_cache(cache_key)
            if cached is not None:
                print(f"[THEREFORE] Using cached workflow processes for {self.tenant_name}")
                return cached
        
        # Type 19 = WorkflowProcess in WSObjectType enum
        data = {
            "LoadItemsList": [{"Flags": 0, "Type": 19}]
        }

        result = await self._post("GetObjectsList", data)
        
        if not result:
            return []

        processes = []
        all_items = result.get("AllItemsList", [])

        # Build folder lookup for folder names
        folder_lookup = {}
        for item_list in all_items:
            for folder in item_list.get("FolderList", []):
                folder_lookup[folder.get("FolderNo")] = folder.get("Name", "")

        # Extract workflow processes from ItemList
        for item_list in all_items:
            for item in item_list.get("ItemList", []):
                process_no = item.get("ID")  # ID field contains ProcessNo (not Data!)
                process_name = item.get("Name", "Unknown Process")
                folder_no = item.get("FolderNo", 0)
                folder_name = folder_lookup.get(folder_no, "")

                if process_no:
                    processes.append({
                        "process_no": process_no,
                        "process_name": process_name,
                        "folder_name": folder_name
                    })

        # Sort and cache the result
        sorted_processes = sorted(processes, key=lambda p: (p["folder_name"], p["process_name"]))
        _set_cache(cache_key, sorted_processes)
        print(f"[THEREFORE] Cached {len(sorted_processes)} workflow processes for {self.tenant_name}")
        
        return sorted_processes
    
    async def execute_workflow_query_for_all(
        self,
        max_rows: int = 10000,
        workflow_flags: Optional[WorkflowFlags] = None
    ) -> Optional[List[tuple[int, int]]]:
        """Execute workflow query for all processes.

        Args:
            max_rows: Maximum rows to return
            workflow_flags: WorkflowFlags enum value (default: RUNNING_INSTANCES)

        Returns:
            List of instance numbers, or None if the query failed
        """
        if workflow_flags is None:
            workflow_flags = self.DEFAULT_WORKFLOW_FLAG

        data = {
            "WorkflowFlags": int(workflow_flags),
            "MaxRows": max_rows
        }
        
        result = await self._post("ExecuteWorkflowQueryForAll", data)
        if not result:
            return None  # Return None to indicate query failed
        
        instances = []
        query_results = result.get("WorkflowQueryResultList", [])
        for query_result in query_results:
            rows = query_result.get("ResultRows", [])
            for row in rows:
                instance_no = row.get("InstanceNo")
                token_no = row.get("TokenNo", 0)
                if instance_no:
                    instances.append((instance_no, token_no))
        
        return instances
    
    async def _get_active_processes_from_stats(self) -> Optional[set]:
        """Get set of process IDs that have active workflow instances.
        
        Uses ExecuteStatisticsQuery type 102 to efficiently find processes
        with active instances. Returns None if the query fails.
        
        Returns:
            Set of process numbers with active instances, or None on error
        """
        try:
            stats_result = await self._post("ExecuteStatisticsQuery", {"QueryType": 102})
            if not stats_result:
                return None
            
            query_result = stats_result.get("QueryResult", {})
            result_rows = query_result.get("ResultRows", [])
            
            # Return set of process IDs with CountValue > 0
            active_processes = {
                entry.get("EntryNo") 
                for entry in result_rows 
                if entry.get("EntryNo") and entry.get("CountValue", 0) > 0
            }
            return active_processes
        except Exception as e:
            # Silently fail - we'll just query all requested processes
            print(f"[THEREFORE] Stats pre-filter failed (non-critical): {e}")
            return None
    
    async def execute_workflow_query_with_fallback(
        self,
        max_rows: int = 10000,
        workflow_flags: Optional[WorkflowFlags] = None
    ) -> List[tuple[int, int]]:
        """Execute workflow query with fallback for corrupted workflows.
        
        Tries ExecuteWorkflowQueryForAll first. If that fails (e.g., due to corrupted
        workflow instances), falls back to querying each process individually using
        ExecuteStatisticsQuery to find active/error processes.
        
        Args:
            max_rows: Maximum rows to return
            workflow_flags: WorkflowFlags enum value (default: RUNNING_INSTANCES)
            
        Returns:
            List of (instance_no, token_no) tuples
        """
        # Try the standard all-processes query first
        instances = await self.execute_workflow_query_for_all(max_rows, workflow_flags)
        if instances is not None:
            # Query succeeded (may be empty list, which is valid)
            return instances
        
        # Query failed - use fallback
        print(f"[THEREFORE] ExecuteWorkflowQueryForAll failed, using fallback...")
        
        # Fallback: Get processes from statistics, query each individually
        print(f"[THEREFORE] Falling back to individual process queries...")
        
        # Determine which statistics query to use based on workflow_flags
        # Type 102 = active instances, Type 108 = error instances
        is_error_query = (workflow_flags == WorkflowFlags.ERROR_INSTANCES)
        stats_query_type = 108 if is_error_query else 102
        
        stats_result = await self._post("ExecuteStatisticsQuery", {"QueryType": stats_query_type})
        if not stats_result:
            print("[THEREFORE] ExecuteStatisticsQuery returned no result")
            return []
        
        # Extract process IDs with active instances
        query_result = stats_result.get("QueryResult", {})
        result_rows = query_result.get("ResultRows", [])
        
        process_ids = []
        for entry in result_rows:
            entry_no = entry.get("EntryNo")
            count = entry.get("CountValue", 0)
            if entry_no and count > 0:
                process_ids.append(entry_no)
        
        print(f"[THEREFORE] Found {len(process_ids)} active processes to query")
        
        # Query each process individually, skipping any that fail
        all_instances = []
        failed_processes = []
        for process_no in process_ids:
            try:
                instances = await self.execute_workflow_query_for_process(
                    process_no, max_rows, workflow_flags
                )
                all_instances.extend(instances)
            except Exception as e:
                # Log but continue - some processes may be corrupted
                failed_processes.append(process_no)
                print(f"[THEREFORE] Skipping process {process_no} (query failed): {e}")
        
        if failed_processes:
            print(f"[THEREFORE] Warning: {len(failed_processes)} processes failed: {failed_processes}")
        
        # Remove duplicates while preserving order (based on instance_no + token_no)
        seen = set()
        unique_instances = []
        for inst_tuple in all_instances:
            if inst_tuple not in seen:
                seen.add(inst_tuple)
                unique_instances.append(inst_tuple)
        
        print(f"[THEREFORE] Fallback query complete: {len(unique_instances)} unique instances from {len(process_ids) - len(failed_processes)} processes")
        return unique_instances
    
    async def execute_workflow_query_for_process(
        self,
        process_no: int,
        max_rows: int = 10000,
        workflow_flags: Optional[WorkflowFlags] = None
    ) -> List[tuple[int, int]]:
        """Execute workflow query for a specific process.

        Args:
            process_no: The workflow process number
            max_rows: Maximum rows to return
            workflow_flags: WorkflowFlags enum value (default: RUNNING_INSTANCES)

        Returns:
            List of (instance_no, token_no) tuples
        """
        if workflow_flags is None:
            workflow_flags = self.DEFAULT_WORKFLOW_FLAG

        data = {
            "ProcessNo": process_no,
            "WorkflowFlags": int(workflow_flags),
            "MaxRows": max_rows
        }
        
        result = await self._post("ExecuteWorkflowQueryForProcess", data)
        if not result:
            return []
        
        instances = []
        query_result = result.get("WorkflowQueryResult", {})
        rows = query_result.get("ResultRows", [])
        for row in rows:
            instance_no = row.get("InstanceNo")
            token_no = row.get("TokenNo", 0)
            if instance_no:
                instances.append((instance_no, token_no))
        
        return instances
    
    async def get_workflow_instance(self, instance_no: int) -> Optional[WorkflowInstance]:
        """Get details for a workflow instance.
        
        Args:
            instance_no: The instance number
            
        Returns:
            WorkflowInstance or None if not found
        """
        data = {
            "InstanceNo": instance_no,
            "TokenNo": 0
        }
        
        result = await self._post("GetWorkflowInstance", data)
        if not result:
            return None

        wf_instance = result.get("WorkflowInstance", {})
        linked_docs_raw = result.get("LinkedDocuments", [])

        # Parse linked documents into structured objects
        linked_documents = []
        for doc in linked_docs_raw:
            index_str = doc.get("IndexDataString", "")
            if index_str:
                linked_documents.append(LinkedDocument.from_index_string(
                    doc_no=doc.get("DocNo", 0),
                    category_no=doc.get("CategoryNo", 0),
                    index_data_string=index_str
                ))

        # Get assigned users
        assigned_user_ids = wf_instance.get("AssignedToUsers", [])
        assigned_users = []
        for user_id in assigned_user_ids:
            user_detail = await self.get_user_details(user_id)
            if user_detail:
                assigned_users.append(user_detail)
        
        # Parse dates
        task_due_raw = wf_instance.get("TaskDueDate")
        task_due = parse_dotnet_date(task_due_raw)
        # If year is 1900 or earlier, treat as no due date
        if task_due and task_due.year <= 1900:
            task_due = None
        
        task_start = parse_dotnet_date(wf_instance.get("TaskStartDate")) or datetime(2000, 1, 1)
        process_start_date = parse_dotnet_date(wf_instance.get("ProcessStartDate")) or datetime(2000, 1, 1)
        
        return WorkflowInstance(
            instance_no=wf_instance.get("InstanceNo", instance_no),
            process_no=wf_instance.get("ProcessNo", 0),
            process_name=wf_instance.get("ProcessName", ""),
            task_name=wf_instance.get("CurrTaskName", ""),
            task_start=task_start,
            task_due=task_due,
            process_start_date=process_start_date,
            linked_documents=linked_documents,
            assigned_to_users=assigned_users
        )
    
    async def get_user_details(self, user_or_group_id: int) -> Optional[UserDetail]:
        """Get user details.
        
        Args:
            user_or_group_id: The user or group ID
            
        Returns:
            UserDetail or None if not found
        """
        data = {
            "UserOrGroupId": user_or_group_id
        }
        
        result = await self._post("GetUserDetails", data)
        if not result:
            return None
        
        user_details = result.get("UserDetails", {})
        raw_user_type = user_details.get("UserType")
        
        # Handle both string and integer user types
        if isinstance(raw_user_type, str):
            user_type_map = {
                "SingleUser": UserType.SINGLE_USER,
                "UserGroup": UserType.USER_GROUP,
                "SystemUser": UserType.SYSTEM_USER
            }
            user_type = user_type_map.get(raw_user_type, UserType.SINGLE_USER)
        else:
            try:
                user_type = UserType(int(raw_user_type)) if raw_user_type is not None else UserType.SINGLE_USER
            except (ValueError, TypeError):
                user_type = UserType.SINGLE_USER
        
        return UserDetail(
            user_id=user_details.get("UserId", user_or_group_id),
            display_name=user_details.get("DisplayName", ""),
            smtp=user_details.get("SMTP", ""),
            user_type=user_type,
            disabled=user_details.get("Disabled", False)
        )
    
    async def get_users_from_group(self, group_id: int) -> List[UserDetail]:
        """Get users from a group.
        
        Args:
            group_id: The group ID
            
        Returns:
            List of UserDetail objects
        """
        data = {
            "GroupId": group_id
        }
        
        try:
            result = await self._post("GetUsersFromGroup", data)
            if not result:
                return []
            
            users = []
            user_list = result.get("Users", [])
            for user in user_list:
                if not user.get("Disabled", False):
                    users.append(UserDetail(
                        user_id=user.get("UserId", 0),
                        display_name=user.get("DisplayName", ""),
                        smtp=user.get("SMTP", ""),
                        user_type=UserType(user.get("UserType", UserType.SINGLE_USER)),
                        disabled=False
                    ))
            
            return users
        except httpx.HTTPStatusError as e:
            if "User has wrong type" in str(e.response.text):
                # Not a group, return empty list
                print(f"Warning: ID {group_id} is not a group, skipping")
                return []
            raise
    
    async def get_all_workflow_instances(
        self, 
        process_nos: Optional[List[int]] = None,
        max_rows: int = 10000,
        progress_callback=None,
        workflow_flags: Optional[WorkflowFlags] = None,
        skip_user_expansion: bool = False
    ) -> List[InstanceForUser]:
        """Get all workflow instances with flattened user assignments.
        
        This is the main method that:
        1. Queries for workflow instances (all or filtered by process)
        2. Gets details for each instance
        3. Expands groups to individual users
        4. Flattens the results to one row per user per instance
        
        Args:
            process_nos: Optional list of process numbers to filter by
            max_rows: Maximum rows to return
            progress_callback: Optional callback function(current, total, instance_no)
            workflow_flags: Optional WorkflowFlags enum (default: RUNNING_INSTANCES)
            skip_user_expansion: If True, return one row per instance without expanding users
            
        Returns:
            List of InstanceForUser objects
        """
        # Step 1: Get all instance numbers
        if process_nos:
            # De-duplicate process numbers before querying
            unique_process_nos = list(dict.fromkeys(process_nos))
            
            # Optimization: Use statistics query to pre-filter processes with active instances
            # This avoids querying processes that have no workflows (saving API calls)
            active_processes = await self._get_active_processes_from_stats()
            if active_processes is not None:
                # Filter to only processes that have active instances
                original_count = len(unique_process_nos)
                unique_process_nos = [p for p in unique_process_nos if p in active_processes]
                skipped = original_count - len(unique_process_nos)
                if skipped > 0:
                    print(f"[THEREFORE] Pre-filtered {skipped} processes with no active instances")
            
            instance_nos = []
            for process_no in unique_process_nos:
                instances = await self.execute_workflow_query_for_process(
                    process_no, max_rows, workflow_flags
                )
                instance_nos.extend(instances)
        else:
            # Use fallback method for "all processes" to handle corrupted workflows
            instance_nos = await self.execute_workflow_query_with_fallback(max_rows, workflow_flags)
        
        # Remove duplicates while preserving order (based on instance_no + token_no)
        seen = set()
        unique_instances = []
        for inst_tuple in instance_nos:
            # inst_tuple is (instance_no, token_no)
            key = inst_tuple  # Tuple is hashable
            if key not in seen:
                seen.add(key)
                unique_instances.append(inst_tuple)
        instance_nos = unique_instances
        
        # Step 2: Get details for each instance concurrently (with limit of 10)
        results = []
        total = len(instance_nos)
        completed_count = 0

        # Use a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(10)

        async def fetch_instance(instance_no: int, token_no: int):
            nonlocal completed_count
            async with semaphore:
                instance = await self.get_workflow_instance(instance_no)
                completed_count += 1
                if progress_callback:
                    await progress_callback(completed_count, total, instance_no)
                return instance, token_no

        # Fetch all instances concurrently
        tasks = [fetch_instance(no, token) for no, token in instance_nos]
        instances_with_tokens = await asyncio.gather(*tasks)

        # Step 3: Process results - expand groups and flatten to users
        for instance, token_no in instances_with_tokens:
            if not instance:
                continue
            
            if skip_user_expansion:
                # For error reports: return one row per instance without user expansion
                results.append(InstanceForUser(
                    instance_no=instance.instance_no,
                    process_no=instance.process_no,
                    process_name=instance.process_name,
                    task_name=instance.task_name,
                    task_start=instance.task_start,
                    task_due=instance.task_due,
                    process_start_date=instance.process_start_date,
                    user_id=0,
                    user_display_name="SYSTEM",
                    user_smtp="",
                    linked_documents=instance.linked_documents,
                    tenant_base_url=self.base_url,
                    token_no=token_no
                ))
            else:
                # Expand groups to users
                all_users = []
                await self._expand_users(instance.assigned_to_users, all_users)

                # Step 4: Flatten to one row per user (grouping by instance_no + user + token_no)
                for user in all_users:
                    if user.user_type == UserType.SINGLE_USER and not user.disabled:
                        results.append(InstanceForUser(
                            instance_no=instance.instance_no,
                            process_no=instance.process_no,
                            process_name=instance.process_name,
                            task_name=instance.task_name,
                            task_start=instance.task_start,
                            task_due=instance.task_due,
                            process_start_date=instance.process_start_date,
                            user_id=user.user_id,
                            user_display_name=user.display_name,
                            user_smtp=user.smtp,
                            linked_documents=instance.linked_documents,
                            tenant_base_url=self.base_url,
                            token_no=token_no
                        ))

        return results
    
    async def _expand_users(
        self, 
        users: List[UserDetail], 
        result: List[UserDetail]
    ) -> None:
        """Recursively expand groups to individual users.
        
        Args:
            users: List of UserDetail objects (may include groups)
            result: List to append expanded users to
        """
        for user in users:
            if user.user_type == UserType.USER_GROUP:
                # Get users from group and recursively expand
                group_users = await self.get_users_from_group(user.user_id)
                await self._expand_users(group_users, result)
            elif user.user_type == UserType.SINGLE_USER and not user.disabled:
                result.append(user)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
