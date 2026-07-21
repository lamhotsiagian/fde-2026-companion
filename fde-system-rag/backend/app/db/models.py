from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(16), unique=True)
    email: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(25), nullable=True)
    last_name: Mapped[str] = mapped_column(String(25), nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User {self.username}>"


class Thread(Base):
    __tablename__ = "threads"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(100), default="New Chat")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)

    def __repr__(self):
        return f"<Thread {self.title}>"


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file_name: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    thread_id: Mapped[UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)

    def __repr__(self):
        return f"<Document {self.file_name}>"


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), nullable=True)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(50))  # episodic, semantic, procedural, entity
    content: Mapped[str] = mapped_column(String(1000))
    importance_score: Mapped[float] = mapped_column(default=0.5)
    access_count: Mapped[int] = mapped_column(default=1)
    last_accessed_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    decay_rate: Mapped[float] = mapped_column(default=0.05)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_shared: Mapped[bool] = mapped_column(default=False)
    metadata_json: Mapped[str] = mapped_column(String(2000), default="{}")

    def __repr__(self):
        return f"<Memory type={self.memory_type} content={self.content[:30]}>"


class MemoryConsolidation(Base):
    __tablename__ = "memory_consolidations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    level: Mapped[str] = mapped_column(String(50))  # session, daily, long-term
    summary: Mapped[str] = mapped_column(String(2000))
    source_memory_ids: Mapped[str] = mapped_column(String(2000))  # comma-separated uuids
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MemoryConflict(Base):
    __tablename__ = "memory_conflicts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    memory_id_old: Mapped[UUID] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    memory_id_new: Mapped[UUID] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"))
    conflict_type: Mapped[str] = mapped_column(String(100))
    resolution: Mapped[str] = mapped_column(String(500), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime] = mapped_column(nullable=True)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    attributes_json: Mapped[str] = mapped_column(String(2000), default="{}")
    last_updated: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self):
        return f"<Tenant {self.name}>"


class TenantUser(Base):
    __tablename__ = "tenant_users"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(50), default="member")  # e.g., admin, member

    def __repr__(self):
        return f"<TenantUser tenant={self.tenant_id} user={self.user_id} role={self.role}>"


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    tags: Mapped[str] = mapped_column(String(1000), default="")  # comma-separated
    description: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    price: Mapped[float] = mapped_column(default=0.0)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)

    def __repr__(self):
        return f"<CatalogItem {self.name}>"


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    item_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(50))  # view/rating/click/purchase
    value: Mapped[float] = mapped_column(default=1.0)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    source: Mapped[str] = mapped_column(String(50), default="organic")  # organic | seed-demo | generated

    def __repr__(self):
        return f"<Interaction user={self.user_id} item={self.item_id} type={self.type}>"


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    type: Mapped[str] = mapped_column(String(50))  # fact/preference/event
    content: Mapped[str] = mapped_column(String(1000))
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="organic")  # organic | seed-demo | generated

    def __repr__(self):
        return f"<MemoryRecord user={self.user_id} content={self.content[:30]}>"


class AdItem(Base):
    __tablename__ = "ad_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    tags: Mapped[str] = mapped_column(String(1000), default="")  # comma-separated
    description: Mapped[str] = mapped_column(String(2000), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    price: Mapped[float] = mapped_column(default=0.0)
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)

    def __repr__(self):
        return f"<AdItem {self.name}>"


class AdClick(Base):
    __tablename__ = "ad_clicks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    ad_id: Mapped[UUID] = mapped_column(ForeignKey("ad_items.id", ondelete="CASCADE"))
    clicked: Mapped[bool] = mapped_column(default=False)
    timestamp: Mapped[datetime] = mapped_column(server_default=func.now())
    source: Mapped[str] = mapped_column(String(50), default="organic")  # organic | seed-demo | generated

    def __repr__(self):
        return f"<AdClick user={self.user_id} ad={self.ad_id} clicked={self.clicked}>"

