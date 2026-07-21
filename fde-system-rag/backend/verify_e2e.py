import sys
from unittest.mock import MagicMock, AsyncMock, Mock

# Mock out psycopg and langgraph checkpointer to bypass Cython compile issues on Python 3.13
sys.modules['psycopg'] = MagicMock()
sys.modules['psycopg_binary'] = MagicMock()
sys.modules['langgraph.checkpoint.postgres'] = MagicMock()
sys.modules['langgraph.checkpoint.postgres.aio'] = MagicMock()
sys.modules['langchain_postgres'] = MagicMock()

import asyncio
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import main as db_main
from app.db.models import CatalogItem, MemoryRecord, Interaction, User, TenantUser, Tenant

# Shared dummy databases representing active database state for E2E mocks
ITEMS_DB = []
MEMORY_DB = []
INTERACTIONS_DB = []
USERS_DB = []
TENANT_USERS_DB = []
TENANTS_DB = []

async def test_e2e_flow():
    print("Starting Comprehensive E2E Verification...")
    user_id = uuid4()
    tenant_id = uuid4()

    # Seed initial test data structures
    TENANTS_DB.append(Tenant(id=tenant_id, name="Verify Retailer"))
    
    user_mock = Mock()
    user_mock.id = user_id
    user_mock.username = "verify_admin"
    user_mock.email = "admin@verify.com"
    
    USERS_DB.append(user_mock)
    TENANT_USERS_DB.append(TenantUser(tenant_id=tenant_id, user_id=user_id, role="admin"))

    # Database Session mocks
    session_mock = Mock()
    
    # Mock commit
    async def mock_commit():
        pass
    session_mock.commit = mock_commit

    # Mock add
    def mock_add(obj):
        if isinstance(obj, CatalogItem):
            ITEMS_DB.append(obj)
        elif isinstance(obj, MemoryRecord):
            MEMORY_DB.append(obj)
        elif isinstance(obj, Interaction):
            INTERACTIONS_DB.append(obj)
        elif isinstance(obj, User):
            USERS_DB.append(obj)
        elif isinstance(obj, TenantUser):
            TENANT_USERS_DB.append(obj)
    session_mock.add = mock_add

    # Mock execute
    async def mock_execute(stmt):
        execute_result = Mock()
        
        # Parse statement class from query target
        stmt_str = str(stmt).lower()
        if "catalog_items" in stmt_str:
            execute_result.scalars.return_value.all.return_value = ITEMS_DB
            execute_result.scalars.return_value.first.return_value = ITEMS_DB[0] if ITEMS_DB else None
        elif "memory_records" in stmt_str or "memoryrecords" in stmt_str:
            execute_result.scalars.return_value.all.return_value = MEMORY_DB
            execute_result.scalars.return_value.first.return_value = MEMORY_DB[0] if MEMORY_DB else None
        elif "tenant_users" in stmt_str or "tenantusers" in stmt_str:
            execute_result.scalars.return_value.all.return_value = TENANT_USERS_DB
            execute_result.scalars.return_value.first.return_value = TENANT_USERS_DB[0] if TENANT_USERS_DB else None
        elif "interactions" in stmt_str:
            execute_result.scalars.return_value.all.return_value = INTERACTIONS_DB
            execute_result.scalars.return_value.first.return_value = INTERACTIONS_DB[0] if INTERACTIONS_DB else None
        elif "users" in stmt_str:
            execute_result.scalars.return_value.all.return_value = USERS_DB
            execute_result.scalars.return_value.first.return_value = USERS_DB[0] if USERS_DB else None
        else:
            execute_result.scalars.return_value.all.return_value = []
            execute_result.scalars.return_value.first.return_value = None
            
        return execute_result
    session_mock.execute = mock_execute

    # Mock session get
    async def mock_get(model_cls, pk):
        if model_cls == Tenant:
            return TENANTS_DB[0] if TENANTS_DB else None
        return None
    session_mock.get = mock_get

    # 1. Verify Catalog Seeding
    print("Step 1: Ingesting Catalog fixtures...")
    from app.course.routes import generate_endpoint
    res_gen_cat = await generate_endpoint("catalog-scale", current_user=user_mock, session=session_mock, count=120, seed=42)
    print("Catalog generation result:", res_gen_cat["message"])
    assert len(ITEMS_DB) == 120
    assert ITEMS_DB[0].category in ["Electronics", "Books", "Clothing"]

    # 2. Verify Memory Seeding
    print("Step 2: Appending Memory logs...")
    res_gen_mem = await generate_endpoint("memory-session", current_user=user_mock, session=session_mock, count=2)
    print("Memory generation result:", res_gen_mem["message"])
    assert len(MEMORY_DB) == 2

    # 3. Verify Collaborative Filtering user matching
    # Insert mock tenant interactions
    INTERACTIONS_DB.append(Interaction(id=uuid4(), user_id=user_id, tenant_id=tenant_id, item_id=ITEMS_DB[0].id, type="rating", value=5.0))
    other_user = uuid4()
    INTERACTIONS_DB.append(Interaction(id=uuid4(), user_id=other_user, tenant_id=tenant_id, item_id=ITEMS_DB[0].id, type="rating", value=4.5))

    print("Step 3: Evaluating User-User similarity CF...")
    from app.course.commands import execute_tenant_similar_users
    res_sim = await execute_tenant_similar_users(session_mock, user_id, {})
    print("CF Result message:\n", res_sim.message)
    assert res_sim.status == "success"
    assert len(res_sim.data["similarities"]) > 0

    # 4. Verify Content-Based personal profiling
    print("Step 4: Compiling Content-based user profiling matches...")
    from app.course.commands import execute_memory_user_profile
    res_profile = await execute_memory_user_profile(session_mock, user_id, {})
    print("Memory profile recommendations:\n", res_profile.message)
    assert res_profile.status == "success"

    # 5. Verify Chapter 9: Matrix Factorization SVD Training and Personalized predictions
    print("Step 5: Training Capstone SVD Matrix Factorization...")
    from app.course.commands import execute_capstone_train, execute_capstone_recommend
    res_train = await execute_capstone_train(session_mock, user_id, {})
    print("Capstone SVD Training message:\n", res_train.message)
    assert res_train.status == "success"

    res_rec = await execute_capstone_recommend(session_mock, user_id, {})
    print("Capstone Personalized predictions:\n", res_rec.message)
    assert res_rec.status == "success"
    assert len(res_rec.data["recommendations"]) > 0

    # 6. Verify Chapter 8: ANN search performance benchmarks
    print("Step 6: Executing Candidate Generation ANN benchmark comparison...")
    from app.course.commands import execute_sample_ann_vs_bruteforce
    res_ann = await execute_sample_ann_vs_bruteforce(session_mock, user_id, {})
    print("ANN Performance message:\n", res_ann.message)
    assert res_ann.status == "success"

    # 7. Verify dynamic course progress tracker
    print("Step 7: Tracking progress tracker metrics...")
    from app.course.commands import execute_progress
    res_prog = await execute_progress(session_mock, user_id, {})
    print("Course completion checklists:\n", res_prog.message)
    assert 1 in res_prog.data["completed_chapters"]
    assert 2 in res_prog.data["completed_chapters"]
    assert 3 in res_prog.data["completed_chapters"]

    print("\n✅ E2E Course Pipeline verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_e2e_flow())
