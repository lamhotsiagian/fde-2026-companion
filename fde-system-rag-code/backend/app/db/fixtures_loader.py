import json
import logging
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, TenantUser, CatalogItem, Interaction, MemoryRecord, AdItem, User
from app.db.pgvector_utils import embeddings

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

async def get_embedding_resilient(text: str) -> list[float]:
    """Get embedding from the model, or fallback to a deterministic dummy vector if offline."""
    try:
        res = await embeddings.aembed_query(text)
        return res
    except Exception as e:
        logger.warning(f"Failed to generate embedding via model (Ollama offline?): {e}. Using deterministic fallback.")
        # Generate a deterministic mock vector based on the text hash
        val = sum(ord(c) for c in text) / 1000.0
        return [val * (i % 10 - 5) / 100.0 for i in range(768)]

async def get_or_create_user_by_email(session: AsyncSession, email: str) -> User:
    stmt = select(User).where(User.email == email)
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        from app.auth.utils import hash_password
        username = email.split("@")[0]
        user = User(
            id=uuid4(),
            username=username,
            email=email,
            hashed_password=hash_password("password123")
        )
        session.add(user)
        await session.flush()
        logger.info(f"Dynamically created seed user: {email}")
    return user

async def seed_catalog_fixture(session: AsyncSession) -> int:
    """Seed catalog items from fixture."""
    file_path = FIXTURES_DIR / "catalog.json"
    if not file_path.exists():
        logger.error(f"Catalog fixture file not found at {file_path}")
        return 0

    with open(file_path, "r") as f:
        items_data = json.load(f)

    count = 0
    for data in items_data:
        item_id = UUID(data["id"])
        # Check if already exists
        exists = await session.get(CatalogItem, item_id)
        if exists:
            continue

        embedding = await get_embedding_resilient(f"{data['name']} {data['description']}")
        
        item = CatalogItem(
            id=item_id,
            tenant_id=None,  # global catalog items have null tenant_id
            name=data["name"],
            tags=data["tags"],
            description=data["description"],
            category=data["category"],
            price=data["price"],
            image_url=data["image_url"],
            embedding=embedding
        )
        session.add(item)
        count += 1

    await session.commit()
    logger.info(f"Seeded {count} catalog items from fixture.")
    return count

async def seed_tenant_demo_fixture(session: AsyncSession) -> dict:
    """Seed tenants, tenant users, and interactions from fixture."""
    file_path = FIXTURES_DIR / "tenant_demo.json"
    if not file_path.exists():
        logger.error(f"Tenant demo fixture file not found at {file_path}")
        return {"tenants": 0, "tenant_users": 0, "interactions": 0}

    with open(file_path, "r") as f:
        demo_data = json.load(f)

    # 1. Seed Tenants
    tenants_seeded = 0
    for t_data in demo_data.get("tenants", []):
        tenant_id = UUID(t_data["id"])
        exists = await session.get(Tenant, tenant_id)
        if not exists:
            tenant = Tenant(id=tenant_id, name=t_data["name"])
            session.add(tenant)
            tenants_seeded += 1

    await session.flush()

    # 2. Seed Tenant Users (resolving email to User.id)
    users_seeded = 0
    for tu_data in demo_data.get("tenant_users", []):
        email = tu_data["user_email"]
        tenant_id = UUID(tu_data["tenant_id"])
        
        user = await get_or_create_user_by_email(session, email)

        # Check if already mapped
        stmt_tu = select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.user_id == user.id
        )
        res_tu = await session.execute(stmt_tu)
        exists_tu = res_tu.scalar_one_or_none()

        if not exists_tu:
            tu = TenantUser(
                tenant_id=tenant_id,
                user_id=user.id,
                role=tu_data["role"]
            )
            session.add(tu)
            users_seeded += 1

    await session.flush()

    # 3. Seed Interactions (resolving user email)
    interactions_seeded = 0
    for int_data in demo_data.get("interactions", []):
        int_id = UUID(int_data["id"])
        exists = await session.get(Interaction, int_id)
        if exists:
            continue

        email = int_data["user_email"]
        user = await get_or_create_user_by_email(session, email)

        interaction = Interaction(
            id=int_id,
            user_id=user.id,
            tenant_id=UUID(int_data["tenant_id"]),
            item_id=UUID(int_data["item_id"]),
            type=int_data["type"],
            value=int_data["value"],
            source="seed-demo"
        )
        session.add(interaction)
        interactions_seeded += 1

    await session.commit()
    logger.info(f"Seeded {tenants_seeded} tenants, {users_seeded} tenant-user mappings, and {interactions_seeded} interactions.")
    return {"tenants": tenants_seeded, "tenant_users": users_seeded, "interactions": interactions_seeded}

async def seed_memory_demo_fixture(session: AsyncSession) -> int:
    """Seed memory records from fixture."""
    file_path = FIXTURES_DIR / "memory_demo.json"
    if not file_path.exists():
        logger.error(f"Memory demo fixture file not found at {file_path}")
        return 0

    with open(file_path, "r") as f:
        records_data = json.load(f)

    count = 0
    for data in records_data:
        email = data["user_email"]
        user = await get_or_create_user_by_email(session, email)

        # Check if identical record already exists for this user to ensure idempotency
        stmt_mem = select(MemoryRecord).where(
            MemoryRecord.user_id == user.id,
            MemoryRecord.content == data["content"]
        )
        res_mem = await session.execute(stmt_mem)
        exists = res_mem.scalar_one_or_none()
        if exists:
            continue

        embedding = await get_embedding_resilient(data["content"])

        record = MemoryRecord(
            id=uuid4(),
            user_id=user.id,
            session_id=data["session_id"],
            type=data["type"],
            content=data["content"],
            embedding=embedding,
            source="seed-demo"
        )
        session.add(record)
        count += 1

    await session.commit()
    logger.info(f"Seeded {count} memory records from fixture.")
    return count

async def seed_ads_fixture(session: AsyncSession) -> int:
    """Seed ads from fixture."""
    file_path = FIXTURES_DIR / "ads.json"
    if not file_path.exists():
        logger.error(f"Ads fixture file not found at {file_path}")
        return 0

    with open(file_path, "r") as f:
        ads_data = json.load(f)

    count = 0
    for data in ads_data:
        ad_id = UUID(data["id"])
        exists = await session.get(AdItem, ad_id)
        if exists:
            continue

        embedding = await get_embedding_resilient(f"{data['name']} {data['description']}")

        ad = AdItem(
            id=ad_id,
            tenant_id=None,
            name=data["name"],
            tags=data["tags"],
            description=data["description"],
            category=data["category"],
            price=data["price"],
            image_url=data["image_url"],
            embedding=embedding
        )
        session.add(ad)
        count += 1

    await session.commit()
    logger.info(f"Seeded {count} ad items from fixture.")
    return count
