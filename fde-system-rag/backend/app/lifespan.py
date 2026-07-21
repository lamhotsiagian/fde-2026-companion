from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from app.config import settings
from app.db.main import init_db
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running lifespan before the application startup!")
    await init_db()
    
    if settings.seed_demo_data:
        try:
            from app.db.seed import seed_demo_data
            await seed_demo_data()
        except Exception as e:  # never block startup on demo seeding
            logger.warning(f"Demo data seeding skipped: {e}")
            
    logger.info("Initializing checkpointer connection pool...")
    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_uri) as cp:
        await cp.setup()
        app.state.checkpointer = cp
        
        # Share it globally with the app.db.checkpointer module
        from app.db import checkpointer as cp_module
        cp_module.checkpointer = cp
        
        logger.info("✅ PostgresCheckpointer connection pool initialized successfully")
        yield
        
    logger.info("Running lifespan after the application shutdown!")
