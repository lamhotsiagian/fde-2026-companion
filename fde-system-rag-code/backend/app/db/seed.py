"""Demo data seeding for the Memory-Augmented RAG Agent.

Creates a handful of demo users, each with their own threads, a realistic
spread of memories (episodic / semantic / procedural / entity) at varying
importance and age, and at least one unresolved memory conflict. This makes
every screen in the UI — the thread sidebar and the Memory dashboard — populated out of the box, for multiple users, so reviewers can log in
and immediately see the system working.

Design notes
------------
* **Idempotent.** If any users already exist the seed is skipped (unless
  ``force=True``), so it is safe to run on every startup.
* **Resilient.** Relational rows always commit. Pushing memory content into
  pgvector requires the embeddings backend (Ollama / OpenAI) to be reachable;
  if it is not, indexing is skipped with a warning and seeding still succeeds.
* **Time-aware.** ``created_at`` / ``last_accessed_at`` are backdated so the
  recency-decay retrieval strategies (Chapter 5) produce meaningful spreads.

Run standalone:  ``python -m app.db.seed``
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.auth.utils import hash_password
from app.db.main import async_session, init_db
from app.db.models import Memory, MemoryConflict, Thread, User

logger = logging.getLogger(__name__)

# Shared password for every demo account (meets the 8+ char rule).
DEMO_PASSWORD = "Password123!"

# --- Demo dataset -----------------------------------------------------------
# Each user has a profile, threads, memories, and optional conflicting facts.
# ``age_days`` backdates the memory; ``importance`` is the salience score.
DEMO_USERS: list[dict] = [
    {
        "username": "alice",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Nguyen",
        "threads": ["Onboarding to the platform", "Debugging the deploy script"],
        "memories": [
            ("semantic", "User is a senior backend engineer based in Boston.", 0.92, 12),
            ("semantic", "User strongly prefers Python over Java for services.", 0.88, 9),
            ("procedural", "User wants code answers formatted with type hints.", 0.80, 6),
            ("episodic", "User mentioned shipping a payments service on June 14.", 0.55, 5),
            ("entity", "Production API runs on port 8080.", 0.85, 4),
            ("episodic", "User asked about pgvector index tuning last week.", 0.40, 7),
        ],
        # (old_content_index, new_content, conflict_type)
        "conflicts": [
            (4, "Production API now runs on port 9090 after the migration.", "value_update"),
        ],
    },
    {
        "username": "bob",
        "email": "bob@example.com",
        "first_name": "Bob",
        "last_name": "Martinez",
        "threads": ["Weekly metrics review", "Model evaluation notes"],
        "memories": [
            ("semantic", "User is a data scientist who prefers results as tables.", 0.90, 15),
            ("procedural", "Always summarize findings as a markdown table first.", 0.82, 10),
            ("semantic", "User is allergic to peanuts — avoid food suggestions with nuts.", 0.95, 20),
            ("episodic", "User compared recall vs. precision for the retriever on Monday.", 0.50, 3),
            ("entity", "Primary dataset is named 'churn_q2_2026'.", 0.70, 8),
        ],
        "conflicts": [],
    },
    {
        "username": "carol",
        "email": "carol@example.com",
        "first_name": "Carol",
        "last_name": "Okafor",
        "threads": ["Roadmap planning"],
        "memories": [
            ("semantic", "User is a product manager in the PST timezone.", 0.88, 18),
            ("procedural", "Prefers concise bullet summaries, no more than five points.", 0.78, 11),
            ("episodic", "User scheduled the Q3 planning review for next Tuesday.", 0.60, 2),
            ("entity", "Team is called 'Atlas' and owns the search surface.", 0.72, 14),
            ("semantic", "User prefers Notion over Confluence for specs.", 0.45, 16),
        ],
        "conflicts": [],
    },
    {
        "username": "dave",
        "email": "dave@example.com",
        "first_name": "Dave",
        "last_name": "Schmidt",
        "threads": ["Infra incident postmortem", "Cost optimization"],
        "memories": [
            ("semantic", "User is a DevOps engineer responsible for the EU region.", 0.90, 25),
            ("procedural", "Wants infra commands shown for bash, not PowerShell.", 0.76, 13),
            ("entity", "Staging cluster lives in eu-west-1.", 0.80, 9),
            ("episodic", "User resolved a Postgres connection-pool incident on June 10.", 0.65, 19),
            ("semantic", "User prefers Terraform over manual console changes.", 0.84, 6),
        ],
        "conflicts": [
            (2, "Staging cluster was moved to eu-central-1 this quarter.", "value_update"),
        ],
    },
]


async def _index_memory_vector(mem: Memory) -> None:
    """Best-effort push of a memory into pgvector for semantic recall.

    Requires the embeddings backend to be reachable. Failures are logged and
    swallowed so seeding never depends on Ollama/OpenAI being up.
    """
    try:
        from langchain_core.documents import Document

        from app.db.pgvector_utils import vector_store

        doc = Document(
            page_content=mem.content,
            metadata={
                "id": str(mem.id),
                "memory_id": str(mem.id),
                "user_id": str(mem.user_id),
                "thread_id": str(mem.thread_id) if mem.thread_id else "",
                "type": "memory",
                "memory_type": mem.memory_type,
            },
        )
        await vector_store.aadd_documents([doc], ids=[str(mem.id)])
    except Exception as e:  # noqa: BLE001 - intentional best-effort
        logger.warning(f"[seed] vector index skipped for memory {mem.id}: {e}")


async def _seed_one_user(spec: dict) -> tuple[int, int, list[Memory]]:
    """Create one demo user + their threads/memories/conflicts in an isolated
    transaction. Idempotent: skips if the email OR username already exists.
    Returns (memories_created, conflicts_created, memory_objects)."""
    now = datetime.now()
    async with async_session() as session:
        # Per-user idempotency: skip if this demo account already exists, by
        # email OR username (username is unique in the schema).
        exists = await session.scalar(
            select(User).where(
                (User.email == spec["email"]) | (User.username == spec["username"])
            )
        )
        if exists:
            logger.info(f"[seed] demo user {spec['email']} already exists — skipping.")
            return (0, 0, [])

        try:
            user = User(
                username=spec["username"],
                email=spec["email"],
                first_name=spec["first_name"],
                last_name=spec["last_name"],
                password_hash=hash_password(DEMO_PASSWORD),
                is_verified=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()  # assign user.id

            threads: list[Thread] = []
            for title in spec["threads"]:
                t = Thread(title=title, user_id=user.id)
                session.add(t)
                threads.append(t)
            await session.flush()
            default_thread_id = threads[0].id if threads else None

            mem_objs: list[Memory] = []
            n_mem = 0
            for mem_type, content, importance, age_days in spec["memories"]:
                ts = now - timedelta(days=age_days)
                mem = Memory(
                    user_id=user.id, thread_id=default_thread_id,
                    memory_type=mem_type, content=content,
                    importance_score=importance, access_count=1, decay_rate=0.05,
                    is_active=True, is_shared=False,
                    metadata_json=json.dumps({"seeded": True}),
                    created_at=ts, last_accessed_at=ts,
                )
                session.add(mem)
                mem_objs.append(mem)
                n_mem += 1
            await session.flush()

            n_conf = 0
            for old_idx, new_content, ctype in spec["conflicts"]:
                old_mem = mem_objs[old_idx]
                new_mem = Memory(
                    user_id=user.id, thread_id=default_thread_id,
                    memory_type=old_mem.memory_type, content=new_content,
                    importance_score=old_mem.importance_score, access_count=1,
                    decay_rate=0.05, is_active=True,
                    metadata_json=json.dumps({"seeded": True}),
                    created_at=now, last_accessed_at=now,
                )
                session.add(new_mem)
                await session.flush()
                session.add(MemoryConflict(
                    user_id=user.id, memory_id_old=old_mem.id,
                    memory_id_new=new_mem.id, conflict_type=ctype, is_resolved=False,
                ))
                mem_objs.append(new_mem)
                n_mem += 1
                n_conf += 1

            await session.commit()
            logger.info(f"[seed] created demo user {spec['email']} "
                        f"({n_mem} memories, {n_conf} conflicts).")
            return (n_mem, n_conf, mem_objs)
        except Exception as e:  # noqa: BLE001 - one bad user must not abort the rest
            await session.rollback()
            logger.error(f"[seed] failed to create demo user {spec['email']}: {e}")
            return (0, 0, [])


async def seed_demo_data(force: bool = False) -> dict:
    """Ensure the demo users exist. Per-user idempotent: creates only the demo
    accounts that are missing, regardless of how many other users already exist,
    so the demo logins always work. (``force`` is accepted for API compatibility
    but seeding is naturally idempotent.)"""
    created_users = 0
    created_memories = 0
    created_conflicts = 0
    all_mems: list[Memory] = []

    for spec in DEMO_USERS:
        n_mem, n_conf, mems = await _seed_one_user(spec)
        if mems:
            created_users += 1
            created_memories += n_mem
            created_conflicts += n_conf
            all_mems.extend(mems)

    # Best-effort vector indexing for newly-created memories (after commit).
    for mem in all_mems:
        await _index_memory_vector(mem)

    # Seed course fixtures
    async with async_session() as session:
        from app.db.fixtures_loader import (
            seed_catalog_fixture,
            seed_tenant_demo_fixture,
            seed_memory_demo_fixture,
            seed_ads_fixture
        )
        await seed_catalog_fixture(session)
        await seed_tenant_demo_fixture(session)
        await seed_memory_demo_fixture(session)
        await seed_ads_fixture(session)

    summary = {
        "seeded": created_users > 0 or True,
        "users_created": created_users,
        "memories_created": created_memories,
        "conflicts_created": created_conflicts,
        "password": DEMO_PASSWORD,
        "accounts": [u["email"] for u in DEMO_USERS],
    }
    if created_users:
        logger.info(f"[seed] Demo data ensured: {summary}")
    else:
        logger.info("[seed] All demo users already present — nothing to create.")
    return summary


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    result = await seed_demo_data(force=False)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
