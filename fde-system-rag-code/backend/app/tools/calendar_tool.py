from langchain_core.tools import tool
from datetime import datetime

@tool
def calendar_tool(action: str, title: str = "", start_time: str = "", duration_mins: int = 30) -> str:
    """Manage calendar events. Actions: 'create', 'list'."""
    if action == "create":
        return f"Calendar event created: '{title}' starting at {start_time} (Duration: {duration_mins}m)."
    elif action == "list":
        return f"Upcoming events for today ({datetime.now().strftime('%Y-%m-%d')}): 1) Team Sync (10:00 AM), 2) RAG Review (2:00 PM)."
    return f"Unknown calendar action: {action}"
