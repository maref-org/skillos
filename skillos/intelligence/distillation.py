import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeChunk:
    title: str
    content: str
    source: str
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0


class KnowledgeDistiller:
    def __init__(self):
        self.knowledge_store: dict[str, KnowledgeChunk] = {}

    async def distill_from_skill_execution(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        success: bool,
    ) -> str:
        status = "成功" if success else "失败"
        chunk = KnowledgeChunk(
            title=f"执行记录: {skill_id}",
            content=f"Skill {skill_id} 执行{status}, 执行模式: {input_data} -> {output_data}",
            source=skill_id,
        )
        self.knowledge_store[chunk.chunk_id] = chunk
        return chunk.chunk_id

    async def distill_from_failure(self, skill_id: str, error_data: dict[str, Any]) -> str:
        chunk = KnowledgeChunk(
            title=f"错误修复: {skill_id}",
            content=f"Skill {skill_id} 错误: {error_data}",
            source=skill_id,
            tags=["error-fix"],
        )
        self.knowledge_store[chunk.chunk_id] = chunk
        return chunk.chunk_id

    async def search_knowledge(self, query: str) -> list[KnowledgeChunk]:
        results: list[KnowledgeChunk] = []
        q = query.lower()
        for chunk in self.knowledge_store.values():
            if q in chunk.title.lower() or q in chunk.content.lower():
                results.append(chunk)
        return results

    def get_chunk(self, chunk_id: str) -> KnowledgeChunk | None:
        return self.knowledge_store.get(chunk_id)

    def increment_usage(self, chunk_id: str) -> None:
        chunk = self.knowledge_store.get(chunk_id)
        if chunk:
            chunk.usage_count += 1
