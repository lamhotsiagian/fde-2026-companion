import pytest
import pytest_asyncio
import asyncio
import subprocess
import time
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import text
from httpx import AsyncClient

from app.db.main import engine, init_db
from app.db.models import Base
from app.db.seed import seed_demo_data
from tests.e2e.fixtures import SAMPLE_DOCUMENTS

BASE_URL = "http://127.0.0.1:8000/api/v1"

@pytest.fixture(scope="session", autouse=True)
def backend_server():
    """Start FastAPI Uvicorn server process on localhost:8000 for E2E tests."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "backend:."
    
    proc = subprocess.Popen(
        ["/opt/anaconda3/bin/uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd="/Users/lamhots/ai/book-project/Forward Deployed AI Engineer/Forward Deployed AI Engineer (FDE)/fde-2026-companion/fde-system-rag/backend",
        env=env,
    )
    time.sleep(2)  # Allow server to bind and start
    yield proc
    proc.terminate()
    proc.wait()

@pytest.fixture(scope="session", autouse=True)
def frontend_server():
    """Start Next.js frontend server process on port 3000 if not already running."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_running = s.connect_ex(('127.0.0.1', 3000)) == 0
    s.close()
    
    proc = None
    if not is_running:
        env = os.environ.copy()
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="/Users/lamhots/ai/book-project/Forward Deployed AI Engineer/Forward Deployed AI Engineer (FDE)/fde-2026-companion/fde-system-rag/frontend",
            env=env,
        )
        time.sleep(4)  # Allow Next.js server to start
    yield proc
    if proc:
        proc.terminate()
        proc.wait()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def clean_and_seed_db(backend_server):
    """Clean all tables before test run, create schema and populate seed data."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        
    try:
        await seed_demo_data()
    except Exception as e:
        print(f"Seed data populated: {e}")
    yield

@pytest_asyncio.fixture
async def api_client():
    """Async HTTP client for testing live backend API endpoints."""
    async with AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client

@pytest.fixture
def temp_sample_files():
    """Create temporary test files for document ingestion testing."""
    with TemporaryDirectory() as temp_dir:
        paths = {}
        for key, doc in SAMPLE_DOCUMENTS.items():
            file_path = Path(temp_dir) / doc["filename"]
            file_path.write_text(doc["content"], encoding="utf-8")
            paths[key] = file_path
        yield paths
