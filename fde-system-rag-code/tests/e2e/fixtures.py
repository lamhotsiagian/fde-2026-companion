"""Robust test dataset for Playwright E2E tests."""

TEST_USERS = [
    {
        "username": "alice",
        "email": "alice@example.com",
        "password": "Password123!",
        "first_name": "Alice",
        "last_name": "Demo",
        "role": "admin",
    },
    {
        "username": "bob",
        "email": "bob@example.com",
        "password": "Password123!",
        "first_name": "Bob",
        "last_name": "Demo",
        "role": "member",
    },
]

TEST_TENANTS = [
    {"name": "Tenant Alpha", "slug": "tenant-alpha"},
    {"name": "Tenant Beta", "slug": "tenant-beta"},
]

SAMPLE_DOCUMENTS = {
    "txt": {
        "filename": "quarterly_report.txt",
        "content": "Quarterly Performance Report Q3 2026.\nRevenue grew by 24% year-over-year.\nKey growth drivers: Enterprise AI RAG platform adoption and multi-tenant security features.",
    },
    "md": {
        "filename": "system_architecture.md",
        "content": "# System Architecture\n\n## Tech Stack\n- LLM: llama3.2:1b\n- Embedding: nomic-embed-text:latest\n- Vector Database: PostgreSQL + pgvector\n- Agent Framework: LangGraph StateGraph\n- Realtime: WebSockets & SSE",
    },
    "csv": {
        "filename": "metrics_sample.csv",
        "content": "Metric,Value,Target\nUptime,99.95%,99.90%\nAvg Latency (ms),320,350\nFaithfulness,0.95,0.90",
    },
}

TEST_CHAT_QUERIES = [
    {
        "id": "sample_1_concept",
        "prompt": "What is Retrieval-Augmented Generation (RAG) and how does PostgreSQL pgvector enable vector search?",
        "expected_keywords": ["rag", "vector", "postgres", "search", "embedding"],
    },
    {
        "id": "sample_2_report",
        "prompt": "What were the key growth drivers in the Q3 2026 performance report?",
        "expected_keywords": ["revenue", "growth", "adoption", "rag"],
    },
    {
        "id": "sample_3_metrics",
        "prompt": "What is the latency target and faithfulness metric in the metrics sample?",
        "expected_keywords": ["latency", "faithfulness", "target", "metric"],
    },
    {
        "id": "sample_4_architecture",
        "prompt": "List the core components of the system architecture tech stack.",
        "expected_keywords": ["llama", "embed", "postgres", "langgraph", "redis"],
    },
    {
        "id": "sample_5_multitenancy",
        "prompt": "Explain multi-tenant isolation and role-based access control (RBAC) in enterprise AI architectures.",
        "expected_keywords": ["tenant", "isolation", "access", "role", "rbac"],
    },
]
