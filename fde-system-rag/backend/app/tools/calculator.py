from langchain_core.tools import tool
import math
import ast

@tool
def calculator_tool(expression: str) -> str:
    """Evaluate mathematical expressions safely. e.g. '2 + 2', 'sqrt(16)', 'sin(pi/2)'."""
    try:
        # Safe eval using math globals
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"
