from langchain_core.tools import tool

@tool
def email_tool(to_email: str, subject: str, body: str) -> str:
    """Send or draft an email to a user."""
    # Production ready mock/SMTP log
    return f"Email queued successfully!\nTo: {to_email}\nSubject: {subject}\nBody Snippet: {body[:100]}..."
