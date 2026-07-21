from langchain_core.tools import tool
import httpx
import json

@tool
async def rest_api_tool(method: str, url: str, headers_json: str = "{}", body_json: str = "") -> str:
    """Make HTTP REST API requests. Method: GET, POST, PUT, DELETE."""
    try:
        headers = json.loads(headers_json) if headers_json else {}
        data = json.loads(body_json) if body_json else None
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(method=method.upper(), url=url, headers=headers, json=data)
            return f"Status {response.status_code}\nResponse: {response.text[:2000]}"
    except Exception as e:
        return f"REST API error: {e}"
