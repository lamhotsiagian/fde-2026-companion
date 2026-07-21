from .calculator import calculator_tool
from .weather import weather_tool
from .sql import sql_tool
from .filesystem import filesystem_tool
from .github_tool import github_tool
from .rest_api import rest_api_tool
from .python_repl import python_tool
from .email_tool import email_tool
from .calendar_tool import calendar_tool

ALL_TOOLS = [
    calculator_tool,
    weather_tool,
    sql_tool,
    filesystem_tool,
    github_tool,
    rest_api_tool,
    python_tool,
    email_tool,
    calendar_tool,
]

def get_all_tools():
    return ALL_TOOLS
