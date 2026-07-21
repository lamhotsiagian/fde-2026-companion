import json
import re
from typing import Dict, Any, Optional
from uuid import UUID, uuid4
from loguru import logger
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUserDep
from app.db.main import SessionDep, async_session
from app.course.schemas import CourseChatRequest, CommandRequest, CommandResponse, CourseProgressResponse
from app.course.commands import (
    execute_classify_feedback,
    execute_sample_similar_users,
    execute_tenant_similar_users,
    execute_sample_content_similar,
    execute_memory_user_profile,
    execute_sample_hybrid_mix,
    execute_hybrid_mix_full,
    execute_new_user_sim,
    execute_warm_start_sim,
    execute_sample_evaluate,
    execute_tenant_evaluate,
    execute_sample_train_two_tower,
    execute_memory_sequence_train,
    execute_sample_ann_vs_bruteforce,
    execute_tenant_scoped_ann,
    execute_capstone_train,
    execute_capstone_recommend,
    execute_capstone_report,
    execute_progress,
    execute_memory_report
)
from app.chat.schemas import PromptInput

course_router = APIRouter()

# Map command names to execution handlers
COMMANDS_REGISTRY = {
    "classify-feedback": execute_classify_feedback,
    "sample-similar-users": execute_sample_similar_users,
    "tenant-similar-users": execute_tenant_similar_users,
    "sample-content-similar": execute_sample_content_similar,
    "memory-user-profile": execute_memory_user_profile,
    "sample-hybrid-mix": execute_sample_hybrid_mix,
    "hybrid-mix-full": execute_hybrid_mix_full,
    "new-user-sim": execute_new_user_sim,
    "warm-start-sim": execute_warm_start_sim,
    "sample-evaluate": execute_sample_evaluate,
    "tenant-evaluate": execute_tenant_evaluate,
    "sample-train-two-tower": execute_sample_train_two_tower,
    "memory-sequence-train": execute_memory_sequence_train,
    "sample-ann-vs-bruteforce": execute_sample_ann_vs_bruteforce,
    "tenant-scoped-ann": execute_tenant_scoped_ann,
    "capstone-train": execute_capstone_train,
    "capstone-recommend": execute_capstone_recommend,
    "capstone-report": execute_capstone_report,
    "progress": execute_progress,
    "memory-report": execute_memory_report,
}

def parse_slash_command(prompt: str) -> tuple[Optional[str], dict]:
    prompt = prompt.strip()
    if not prompt.startswith("/"):
        return None, {}

    parts = prompt.split(maxsplit=1)
    command = parts[0][1:]  # strip leading slash
    if len(parts) == 1:
        return command, {}

    args_str = parts[1].strip()
    params = {}

    # Parse key=value pairs, handling double or single quotes
    pattern = re.compile(r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|(\S+))')
    matches = pattern.findall(args_str)

    if matches:
        for match in matches:
            key = match[0]
            val = match[1] or match[2] or match[3]
            params[key] = val
    else:
        # Fallback: treat the entire string as a text parameter
        params["text"] = args_str
        params["query"] = args_str

    return command, params

async def run_command_by_name(command_name: str, params: dict, session: AsyncSession, user_id: UUID) -> CommandResponse:
    if command_name not in COMMANDS_REGISTRY:
        supported = ", ".join(f"/{cmd}" for cmd in COMMANDS_REGISTRY.keys())
        return CommandResponse(
            status="error",
            message=f"Unknown command: /{command_name}. Supported commands: {supported}"
        )
    handler = COMMANDS_REGISTRY[command_name]
    try:
        return await handler(session, user_id, params)
    except Exception as e:
        logger.error(f"Error executing command {command_name}: {e}")
        return CommandResponse(
            status="error",
            message=f"Error executing command: {str(e)}"
        )

@course_router.post("/chat")
async def course_chat_endpoint(
    req: CourseChatRequest,
    current_user: CurrentUserDep,
    session: SessionDep
):
    command_name, params = parse_slash_command(req.prompt)
    
    if command_name:
        # 1. Route slash commands through commands router
        async def command_stream_generator():
            res = await run_command_by_name(command_name, params, session, current_user.id)
            # Yield as a formatted single chunk that the frontend can parse
            chunk = {
                "type": "command_result",
                "status": res.status,
                "content": res.message,
                "data": res.data,
                "suggested_command": res.suggested_command,
                "reason": res.reason
            }
            yield json.dumps(chunk) + "\n"
        
        return StreamingResponse(command_stream_generator(), media_type="text/event-stream")
    
    else:
        # 2. Route plain messages through the existing stateful RAG pipeline
        thread_id = req.thread_id or uuid4()
        prompt_input = PromptInput(prompt=req.prompt, model_name=req.model_name)
        
        async def wrap_chat_stream():
            from app.chat import service as chat_service
            stream = await chat_service.chat_stream(thread_id, prompt_input, current_user.id)
            async for chunk_type, val in stream:
                # Format to match the frontend expectations
                if chunk_type == "messages":
                    msg = val[0]
                    if msg.content:
                        yield json.dumps({"type": "llm_chunk", "content": str(msg.content)}) + "\n"
                elif chunk_type == "updates":
                    for node_output in val.values():
                        if "messages" not in node_output:
                            continue
                        msg = node_output["messages"][-1]
                        if msg.content:
                            yield json.dumps({"type": "llm_chunk", "content": str(msg.content)}) + "\n"
                            
        return StreamingResponse(wrap_chat_stream(), media_type="text/event-stream")

@course_router.post("/commands/{command}", response_model=CommandResponse)
async def direct_command_endpoint(
    command: str,
    req: CommandRequest,
    current_user: CurrentUserDep,
    session: SessionDep
):
    return await run_command_by_name(command, req.params, session, current_user.id)

@course_router.get("/progress", response_model=CourseProgressResponse)
async def get_progress_endpoint(
    current_user: CurrentUserDep,
    session: SessionDep
):
    from sqlalchemy import func, select
    from app.db.models import CatalogItem, Interaction, MemoryRecord
    
    # 1. Catalog count
    res_cat = await session.execute(select(func.count(CatalogItem.id)))
    catalog_count = res_cat.scalar() or 0
    
    # 2. Interactions count
    res_int = await session.execute(select(func.count(Interaction.id)).where(Interaction.user_id == current_user.id))
    interactions_count = res_int.scalar() or 0
    
    # 3. Memory records count
    res_mem = await session.execute(select(func.count(MemoryRecord.id)).where(MemoryRecord.user_id == current_user.id))
    memory_count = res_mem.scalar() or 0
    
    res = await execute_progress(session, current_user.id, {})
    completed = res.data["completed_chapters"]
    completion_percentage = (len(completed) / 9.0) * 100
    
    details = {
        "catalog_count": catalog_count,
        "interactions_count": interactions_count,
        "memory_count": memory_count,
        "completion_percentage": completion_percentage
    }
    
    return CourseProgressResponse(
        completed_chapters=completed,
        total_chapters=9,
        details=details
    )

# --- Seed, Generate, and Reset Endpoints ---

from app.db.models import Tenant, TenantUser, CatalogItem, Interaction, MemoryRecord, User
from app.auth.utils import hash_password
from sqlalchemy import delete, select

@course_router.post("/seed/{seed_type}")
async def seed_endpoint(
    seed_type: str,
    current_user: CurrentUserDep,
    session: SessionDep
):
    from app.db.fixtures_loader import (
        seed_catalog_fixture,
        seed_tenant_demo_fixture,
        seed_memory_demo_fixture,
        seed_ads_fixture
    )
    if seed_type == "catalog":
        c_count = await seed_catalog_fixture(session)
        a_count = await seed_ads_fixture(session)
        return {"status": "success", "message": f"Seeded {c_count} catalog items and {a_count} ads."}
    elif seed_type == "tenant-demo":
        res = await seed_tenant_demo_fixture(session)
        return {"status": "success", "message": f"Seeded tenant demo: {res['tenants']} tenants, {res['tenant_users']} users, {res['interactions']} interactions."}
    elif seed_type == "memory-demo":
        m_count = await seed_memory_demo_fixture(session)
        return {"status": "success", "message": f"Seeded {m_count} memory records."}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown seed type '{seed_type}'. Supported: 'catalog', 'tenant-demo', 'memory-demo'"
        )

@course_router.post("/generate/{generate_type}")
async def generate_endpoint(
    generate_type: str,
    current_user: CurrentUserDep,
    session: SessionDep,
    count: int = 10,
    seed: Optional[int] = None
):
    # Enforce strict server-side rate and scale caps
    if generate_type == "catalog-scale":
        if count > 10000:
            raise HTTPException(status_code=400, detail="Scale count exceeds maximum server cap of 10,000 items.")
        if count <= 0:
            raise HTTPException(status_code=400, detail="Count must be greater than zero.")
            
        import random
        if seed is not None:
            random.seed(seed)
            
        # Resolve active tenant
        stmt_tu = select(TenantUser).where(TenantUser.user_id == current_user.id)
        res_tu = await session.execute(stmt_tu)
        mapping = res_tu.scalars().first()
        tenant_id = mapping.tenant_id if mapping else None

        # Bulk insert scaled items with deterministic mock vectors
        for i in range(count):
            item_id = uuid4()
            embedding = [((i * 17 + j) % 100) / 1000.0 for j in range(768)]
            item = CatalogItem(
                id=item_id,
                tenant_id=tenant_id,
                name=f"Synthetic Scaled Product {i}",
                tags="synthetic,scale,test",
                description=f"Automated test product for scale checks index {i}",
                category=random.choice(["Electronics", "Books", "Clothing"]),
                price=round(random.uniform(5.0, 500.0), 2),
                embedding=embedding
            )
            session.add(item)
        await session.commit()
        return {"status": "success", "message": f"Generated {count} scaled catalog items for tenant."}
        
    elif generate_type == "tenant-users":
        if count > 1000:
            raise HTTPException(status_code=400, detail="User count exceeds maximum server cap of 1,000 users.")
        if count <= 0:
            raise HTTPException(status_code=400, detail="Count must be greater than zero.")

        # Resolve active tenant
        stmt_tu = select(TenantUser).where(TenantUser.user_id == current_user.id)
        res_tu = await session.execute(stmt_tu)
        mapping = res_tu.scalars().first()
        if not mapping:
            raise HTTPException(status_code=400, detail="You must be mapped to a tenant first. Run /seed-tenant-demo.")
        tenant_id = mapping.tenant_id

        import random
        if seed is not None:
            random.seed(seed)

        # Get existing catalog items to link interactions
        stmt_items = select(CatalogItem)
        res_items = await session.execute(stmt_items)
        items = res_items.scalars().all()
        if not items:
            raise HTTPException(status_code=400, detail="Catalog is empty. Please seed catalog first.")

        user_count = 0
        interaction_count = 0
        for i in range(count):
            uid = uuid4()
            username = f"synth_u_{str(uid)[:8]}"
            email = f"{username}@example.com"
            
            user = User(
                id=uid,
                username=username,
                email=email,
                password_hash=hash_password("Password123!"),
                is_verified=True,
                is_active=True
            )
            session.add(user)
            
            tu = TenantUser(
                tenant_id=tenant_id,
                user_id=uid,
                role="member"
            )
            session.add(tu)
            user_count += 1

            # Seed 2 random interactions for this user
            for _ in range(2):
                item = random.choice(items)
                interaction = Interaction(
                    id=uuid4(),
                    user_id=uid,
                    tenant_id=tenant_id,
                    item_id=item.id,
                    type=random.choice(["view", "click", "rating", "purchase"]),
                    value=random.choice([1.0, 3.0, 4.0, 5.0]),
                    source="generated"
                )
                session.add(interaction)
                interaction_count += 1

        await session.commit()
        return {"status": "success", "message": f"Generated {user_count} tenant users and {interaction_count} interactions."}

    elif generate_type == "memory-session":
        # Generate one session of logs
        import random
        categories = ["Electronics", "Books", "Clothing"]
        chosen = random.choice(categories)
        
        recs = [
            MemoryRecord(
                id=uuid4(),
                user_id=current_user.id,
                session_id=f"session_{str(uuid4())[:8]}",
                type="preference",
                content=f"User stated a strong preference for {chosen} items.",
                embedding=[random.uniform(-0.1, 0.1) for _ in range(768)],
                source="generated"
            ),
            MemoryRecord(
                id=uuid4(),
                user_id=current_user.id,
                session_id=f"session_{str(uuid4())[:8]}",
                type="event",
                content=f"User browsed products in the {chosen} category.",
                embedding=[random.uniform(-0.1, 0.1) for _ in range(768)],
                source="generated"
            )
        ]
        for r in recs:
            session.add(r)
        await session.commit()
        return {"status": "success", "message": f"Generated 1 memory session logs in category '{chosen}'."}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown generate type '{generate_type}'. Supported: 'catalog-scale', 'tenant-users', 'memory-session'"
        )

@course_router.post("/reset/{scope}")
async def reset_endpoint(
    scope: str,
    current_user: CurrentUserDep,
    session: SessionDep,
    include_organic: bool = False
):
    if scope == "tenant-data":
        # Resolve user's active tenant
        stmt_tu = select(TenantUser).where(TenantUser.user_id == current_user.id)
        res_tu = await session.execute(stmt_tu)
        mapping = res_tu.scalars().first()
        if not mapping:
            return {"status": "success", "message": "No active tenant mapped. Nothing to reset."}
        tenant_id = mapping.tenant_id

        # 1. Delete interactions
        if include_organic:
            stmt = delete(Interaction).where(Interaction.tenant_id == tenant_id)
        else:
            stmt = delete(Interaction).where(
                Interaction.tenant_id == tenant_id,
                Interaction.source.in_(["seed-demo", "generated"])
            )
        res_int = await session.execute(stmt)

        # 2. Delete synthetic tenant users
        # Fetch users associated with this tenant that have synthetic emails/source
        if not include_organic:
            stmt_users = select(User).join(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                User.email.like("%@example.com")  # Matches seeded/generated emails
            )
            res_users = await session.execute(stmt_users)
            users_to_delete = res_users.scalars().all()
            user_ids = [u.id for u in users_to_delete if u.id != current_user.id]
            
            if user_ids:
                # Delete TenantUser records
                stmt_tu_del = delete(TenantUser).where(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.user_id.in_(user_ids)
                )
                await session.execute(stmt_tu_del)
                
                # Delete User records
                stmt_u_del = delete(User).where(User.id.in_(user_ids))
                await session.execute(stmt_u_del)

        await session.commit()
        return {"status": "success", "message": f"Tenant '{tenant_id}' data successfully reset."}

    elif scope == "memory":
        if include_organic:
            stmt = delete(MemoryRecord).where(MemoryRecord.user_id == current_user.id)
        else:
            stmt = delete(MemoryRecord).where(
                MemoryRecord.user_id == current_user.id,
                MemoryRecord.source.in_(["seed-demo", "generated"])
            )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success", "message": "Memory records successfully reset."}
        
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown reset scope '{scope}'. Supported: 'tenant-data', 'memory'"
        )

