import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    order = Column(Integer, default=0)

    templates = relationship("CategoryTemplate", back_populates="category")


class CategoryTemplate(Base):
    __tablename__ = "category_templates"

    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, default=0)

    __table_args__ = (PrimaryKeyConstraint("category_id", "template_id"),)

    category = relationship("Category", back_populates="templates")
    template = relationship("Template", back_populates="categories", passive_deletes=True)
