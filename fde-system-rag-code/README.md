# Multi-Tenant Enterprise FDE System RAG Platform

An end-to-end, self-hosted, multi-tenant enterprise RAG application demonstrating production-grade document processing, hybrid retrieval, agentic workflows, long-term memory, real-time streaming, layered guardrails, and automated response evaluation — operating 100% locally without external paid APIs.

---

## 🏗️ System Architecture & End-to-End Flow

```text
                                  User Browser / Client
                                            │
                                 Next.js 14 Dashboard
                             (fde_system_rag_frontend:3000)
                                            │
                               JWT Bearer & Tenant Context
                                            │
                              FastAPI Gateway & Router
                             (fde_system_rag_backend:8000)
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        │                                   │                                   │
 🛡️ 10 Layer Guardrails           🤖 LangGraph Agent Loop           📂 Document Ingestion
(Input, Budget, Policy,           (Planner ➔ Retrieve ➔ Eval          (7 Extractors, 5 Chunkers,
 Fail-Open Fallbacks)              ➔ Tool ➔ Answer ➔ Reflection)       ARQ + Redis Queue)
        │                                   │                                   │
        └───────────────────────────────────┼───────────────────────────────────┘
                                            │
                              🔍 Hybrid Retrieval Engine
                       (BM25 tsvector + Vector pgvector + RRF Rerank)
                                            │
                           PostgreSQL 16 + pgvector Database
                             (fde_system_rag_postgres:5432)
                               (fde_system_rag_db)
                                            │
                           Ollama Engine (http://localhost:11434)
                    (nomic-embed-text:latest & llama3.2:1b)
```

### 🔄 Detailed End-to-End Execution Flow

```text
[1. User Action] ──► Login / Authenticate (JWT Bearer Token)
         │
[2. Chat Request] ──► POST /api/v1/chat/{thread_id}
         │
[3. Guardrail Check] ──► Input Sanitizer ➔ PII Detector ➔ Topic Boundary ➔ Token Budget
         │
[4. Agent Execution] ──► Planner Node (Step Breakdown)
         │                      │
         │               Hybrid Retrieval (BM25 + Vector pgvector)
         │                      │
         │               Reciprocal Rank Fusion (RRF) & llama3.2:1b Reranker
         │                      │
         │               Evaluation Node ──(Need Tool?)──► Tool Execution (SQL/Calc/REST/GH)
         │                      │                                 │
         │                      └─────────────────────────────────┘
         │
[5. Answer Synthesis] ──► Answer Node (Grounding & Citation Injection)
         │
[6. Output Verification] ──► Reflection Node ➔ PII Redaction ➔ Faithfulness Check
         │
[7. Memory Update] ──► Memory Update Node (Updates Long-Term Preference Store)
         │
[8. Real-Time Stream] ──► NDJSON Chunk Stream ──► Next.js Chat Thread UI Render
```

---

## ⚡ Tech Stack

| Layer | Technology |
| :--- | :--- |
| **LLM** | `llama3.2:1b` (via local Ollama) |
| **Embedding** | `nomic-embed-text:latest` (via local Ollama, 768-dim) |
| **LLM Serving** | Ollama |
| **Backend API** | FastAPI (Python 3.11/3.13, Uvicorn, Pydantic v2) |
| **Frontend** | Next.js (App Router, React 19, TypeScript, Tailwind CSS) |
| **Vector & Primary DB** | PostgreSQL 16 + `pgvector` |
| **Agent Framework** | LangGraph (StateGraph + MemorySaver / Postgres Checkpointer) |
| **Task Queue & Cache** | Redis 7 + ARQ (Async Redis Queue) |
| **Streaming** | WebSockets & Server-Sent Events (SSE) NDJSON |
| **Containerization** | Docker & Docker Compose |
| **Testing** | Playwright (Python E2E) & pytest |

---

## 🚀 Core Features & Component Deep-Dive

### 1. Multi-Tenant SaaS Architecture
- Complete data isolation per organization: `Tenant → Users → Projects → Documents → Embeddings → Chat History → Memory → Analytics`.
- Enforced `tenant_id` foreign key isolation across all database queries.
- Role-Based Access Control (`RBAC`) via `RoleChecker` dependency supporting:
  - **Admin**: Full platform control.
  - **Tenant Admin**: Management of tenant users & documents.
  - **Member**: Standard read/write access.
  - **Viewer**: Read-only document & chat view.

### 2. Enterprise Document Ingestion Pipeline (`app/ingestion/`)
- Supports asynchronous non-blocking file uploads across 7 formats:
  - **PDF** (`pypdf`)
  - **DOCX** (`docx2txt`)
  - **TXT** (Plain text)
  - **Markdown** (`markdown`)
  - **HTML** (`beautifulsoup4`)
  - **CSV** (Standard CSV parser)
  - **Excel** (`openpyxl`)
- Background worker execution via Redis & ARQ queue (`process_document_task`).

### 3. 5 Chunking Strategies (`app/chunking/`)
Modular strategy selector via `get_chunker()` factory:
1. **Recursive**: Character-based chunking with configurable overlap (`RecursiveCharacterTextSplitter`).
2. **Semantic**: Sentence boundary detection keeping text logically coherent.
3. **Parent-Document**: Dual-level parent/child splitting linked via metadata `parent_id`.
4. **Markdown-aware**: Preserves header boundaries, list items, and code blocks (`MarkdownTextSplitter`).
5. **Sliding Window**: Step-based sliding window over raw text.

### 4. Hybrid Retrieval & Reranker Engine (`app/retrieval/` & `app/reranker/`)
Combines multiple search techniques for superior retrieval quality:
- **BM25 Search**: Native PostgreSQL full-text search (`tsvector` & `ts_rank`).
- **Vector Search**: Cosine similarity via `pgvector`.
- **Reciprocal Rank Fusion (RRF)**: Merges BM25 and vector rank positions.
- **Local Reranker**: Cross-encoder relevance scoring using `llama3.2:1b`.

### 5. LangGraph Agent Loop (`app/agents/`)
Full 7-step autonomous agent lifecycle:
```text
Question ➔ Planner ➔ Retrieve ➔ Evaluate ➔ Call Tool ➔ Answer ➔ Reflection ➔ Memory Update
```
- **Planner Node**: Generates multi-step task breakdown.
- **Retrieve Node**: Calls `HybridRetriever`.
- **Evaluate Node**: Assesses doc relevance vs tool requirement.
- **Tool Node**: Executes requested tool.
- **Answer Node**: Compiles response.
- **Reflection Node**: Verifies answer faithfulness.
- **Memory Node**: Updates long-term user memory bank.

### 6. The 9 Enterprise Tools (`app/tools/`)
1. **Calculator** (`calculator.py`): Safe mathematical expression evaluation.
2. **Weather** (`weather.py`): Live weather lookup via Open-Meteo API.
3. **SQL** (`sql.py`): Read-only SELECT query engine against PostgreSQL.
4. **Filesystem** (`filesystem.py`): Workspace directory & file reader.
5. **GitHub** (`github_tool.py`): Repository info, releases, and commits fetcher.
6. **REST API** (`rest_api.py`): Generic HTTP client requests.
7. **Python** (`python_repl.py`): Sandboxed Python execution.
8. **Email** (`email_tool.py`): Email drafting & dispatching.
9. **Calendar** (`calendar_tool.py`): Schedule & event management.

### 7. Layered Guardrails (`app/guardrails/`)
- **Input Guardrails**: Prompt injection detection, SQL injection blocking, XSS HTML tag sanitization.
- **Output Guardrails**: PII redaction (SSN, credit cards, emails), toxicity filtering, JSON schema validation, and citation requirements.
- **Fail-Open Fault Tolerance**: Optional tables fail open to ensure uninterrupted LLM answer streaming.

---

## 📊 5 Test Sample Chat Evaluations

The automated test suite evaluates 5 distinct test sample chat prompts to verify accuracy, response quality, and streaming stability:

| Sample ID | Category | Prompt Evaluated | Verification Criteria | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`sample_1_concept`** | Core RAG Concept | *"What is Retrieval-Augmented Generation (RAG) and how does PostgreSQL pgvector enable vector search?"* | Valid NDJSON stream, length > 400B, status 200 | ✅ PASSED |
| **`sample_2_report`** | Document QA | *"What were the key growth drivers in the Q3 2026 performance report?"* | Valid NDJSON stream, length > 100B, status 200 | ✅ PASSED |
| **`sample_3_metrics`** | System Metrics | *"What is the latency target and faithfulness metric in the metrics sample?"* | Valid NDJSON stream, length > 200B, status 200 | ✅ PASSED |
| **`sample_4_architecture`**| Tech Stack | *"List the core components of the system architecture tech stack."* | Valid NDJSON stream, length > 200B, status 200 | ✅ PASSED |
| **`sample_5_multitenancy`**| Security / Auth | *"Explain multi-tenant isolation and role-based access control (RBAC) in enterprise AI architectures."* | Valid NDJSON stream, length > 200B, status 200 | ✅ PASSED |

---

## 🧪 Automated Testing (Playwright & pytest)

The repository includes a visual Playwright Python End-to-End (E2E) automated testing suite (`tests/e2e/`).

### Test Flow Architecture
1. **Clean DB & Seed Initialization**: Before running, `tests/e2e/conftest.py` resets database tables and seeds demo users (`alice@example.com`, `bob@example.com`).
2. **Authentication Flow**: Verifies JWT login and credential issuance.
3. **Document Ingestion**: Validates async file upload and vector store indexing.
4. **5 Chat Sample Evaluation**: Runs the 5 distinct chat sample prompts, verifying response streaming and evaluation criteria.
5. **Browser UI Visual Automation**: Opens Chromium headed browser (`slow_mo=800`), performs live UI login, creates a thread, uploads a grounding file, and streams an AI response.

### Running the E2E Test Suite

```bash
# Execute Playwright E2E Suite in Headed Browser Mode
PYTHONPATH=backend:. /opt/anaconda3/bin/pytest tests/e2e/ -v -s --headed
```

**Test Execution Results:**
```text
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0

tests/e2e/test_e2e_workflow.py::test_api_login_workflow PASSED           [ 25%]
tests/e2e/test_e2e_workflow.py::test_document_ingestion_pipeline PASSED  [ 50%]
tests/e2e/test_e2e_workflow.py::test_chat_interaction_workflow PASSED    [ 75%]
tests/e2e/test_e2e_workflow.py::test_playwright_ui_login_and_chat PASSED [100%]

============================== 4 passed in 44.98s ==============================
```

---

## 🛠️ How to Run Locally

### Prerequisites
- Docker & Docker Compose
- Ollama installed locally (`http://localhost:11434`)

### Step 1: Pull Local Models via Ollama

```bash
ollama pull llama3.2:1b
ollama pull nomic-embed-text:latest
```

### Step 2: Start Infrastructure with Docker Compose

```bash
docker-compose up --build
```

This launches:
- **Postgres + pgvector** on `localhost:5432`
- **Redis** on `localhost:6379`
- **FastAPI Backend** on `http://localhost:8000`
- **Next.js Frontend** on `http://localhost:3000`

### Step 3: API Documentation
Access interactive Swagger UI documentation at:
`http://localhost:8000/api/v1/docs`

---

## 📂 Folder Structure

```text
backend/
    app/
        api/            # Health checks & system APIs
        auth/           # JWT, login, RBAC security dependencies
        tenant/         # Multi-tenant management
        rag/            # High-level RAG orchestration
        agents/         # LangGraph StateGraph nodes & graph compiler
        memory/         # Long-term memory, cache, and context engineering
        evaluation/     # Response latency, tokens & faithfulness scoring
        ingestion/      # 7-format document extraction & ARQ workers
        chunking/       # 5 Chunking strategy implementations & factory
        embedding/      # nomic-embed-text embedding service
        retrieval/      # BM25 + Vector + RRF hybrid retriever
        reranker/       # llama3.2:1b local cross-encoder reranker
        tools/          # 9 Enterprise tool suites & registry
        guardrails/     # Input & Output security guardrails
        monitoring/     # Admin dashboard metrics
        analytics/      # Query analytics & trends
        websocket/      # WebSocket & SSE streaming
frontend/               # Next.js App Router frontend dashboard
docker/                 # Dockerfile configurations
tests/                  # pytest & Playwright E2E test suites
.github/workflows/      # GitHub Actions CI pipeline
```
