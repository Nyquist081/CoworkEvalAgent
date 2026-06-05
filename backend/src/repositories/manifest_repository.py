from __future__ import annotations
from typing import Optional
import json
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from src.infrastructure.database import Base
from src.core.schemas import Manifest, QuestionItem


class ManifestModel(Base):
    __tablename__ = "manifests"

    benchmark_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    created_by = Column(String, default="")
    description = Column(Text, default="")
    total_questions = Column(Integer, default=0)
    questions_json = Column(Text, default="[]")

    def to_domain(self) -> Manifest:
        return Manifest(
            benchmark_id=self.benchmark_id,
            name=self.name,
            version=self.version,
            created_at=self.created_at,
            created_by=self.created_by,
            description=self.description,
            total_questions=self.total_questions,
            questions=[
                QuestionItem.model_validate(q)
                for q in json.loads(self.questions_json)
            ],
        )

    @classmethod
    def from_domain(cls, m: Manifest) -> "ManifestModel":
        return cls(
            benchmark_id=m.benchmark_id,
            name=m.name,
            version=m.version,
            created_at=m.created_at,
            created_by=m.created_by,
            description=m.description,
            total_questions=m.total_questions,
            questions_json=json.dumps(
                [q.model_dump() for q in m.questions], ensure_ascii=False
            ),
        )


class ManifestRepository:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def save(self, manifest: Manifest) -> Manifest:
        async with self.session_factory() as session:
            model = ManifestModel.from_domain(manifest)
            session.add(model)
            await session.commit()
            return manifest

    async def get(self, benchmark_id: str) -> Optional[Manifest]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(ManifestModel).where(ManifestModel.benchmark_id == benchmark_id)
            )
            model = result.scalar_one_or_none()
            return model.to_domain() if model else None

    async def list_all(self) -> list[Manifest]:
        async with self.session_factory() as session:
            result = await session.execute(select(ManifestModel))
            return [m.to_domain() for m in result.scalars().all()]
