from langchain_core.tools import tool
import httpx

@tool
async def github_tool(repo: str, action: str = "info") -> str:
    """Inspect a public GitHub repository (e.g. 'owner/repo'). Actions: 'info', 'releases', 'commits'."""
    url = f"https://api.github.com/repos/{repo}"
    if action == "releases":
        url += "/releases"
    elif action == "commits":
        url += "/commits"
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"User-Agent": "FastAPI-Agent"}, timeout=10.0)
            if resp.status_code != 200:
                return f"GitHub API error ({resp.status_code}): {resp.text[:200]}"
            data = resp.json()
            if action == "info":
                return f"Repo {data.get('full_name')}: {data.get('description')} | Stars: {data.get('stargazers_count')} | Forks: {data.get('forks_count')} | Language: {data.get('language')}"
            elif action in ("releases", "commits") and isinstance(data, list):
                summary = [item.get("name") or item.get("commit", {}).get("message", "")[:50] for item in data[:5]]
                return f"Latest {action} for {repo}: {summary}"
            return str(data)[:1000]
    except Exception as e:
        return f"GitHub tool error: {e}"
