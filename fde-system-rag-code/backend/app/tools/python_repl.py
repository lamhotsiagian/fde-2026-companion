from langchain_core.tools import tool
import sys
import io

@tool
def python_tool(code: str) -> str:
    """Execute Python code and return stdout / return values."""
    buffer = io.StringIO()
    sys.stdout = buffer
    try:
        exec_globals = {"math": __import__("math")}
        exec(code, exec_globals)
        sys.stdout = sys.__stdout__
        output = buffer.getvalue()
        return output if output else "Code executed successfully (no stdout)."
    except Exception as e:
        sys.stdout = sys.__stdout__
        return f"Execution Error: {e}"
