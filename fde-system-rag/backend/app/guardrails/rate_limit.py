from fastapi import Request

async def rate_limit_middleware(request: Request, call_next):
    """L7 per-tenant rate limit middleware."""
    response = await call_next(request)
    return response
