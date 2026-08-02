#!/usr/bin/env python3
"""NegMarket FastAPI 路由适配器（可选）

需要额外安装: pip install skillos[web]
提供 REST API:
  - POST /negmarket/upload      上传负样本
  - POST /negmarket/{id}/call   调用反模式 Skill
  - GET  /negmarket/discover    发现反模式 Skill
"""

try:
    from fastapi import APIRouter, Body, Depends, HTTPException
except ImportError:
    raise ImportError("FastAPI is not installed. Install with: pip install skillos[web]")

import logging

from skillos.negmarket.anti_pattern import AntiPatternGenerator
from skillos.negmarket.desensitizer import DesensitizationPipeline
from skillos.negmarket.storage import StorageBackend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/negmarket", tags=["negmarket"])


def get_storage() -> StorageBackend:
    from skillos.negmarket.storage import SQLiteNegMarketStorage

    return SQLiteNegMarketStorage()


def get_pipeline() -> DesensitizationPipeline:
    return DesensitizationPipeline()


def get_generator() -> AntiPatternGenerator:
    return AntiPatternGenerator()


@router.post("/upload")
async def upload_negative_sample(
    raw_text: str = Body(..., min_length=1, max_length=100000),
    category: str = Body("general"),
    contributor_id: str = Body(...),
    contributor_secret: str = Body(...),
    storage: StorageBackend = Depends(get_storage),
    pipeline: DesensitizationPipeline = Depends(get_pipeline),
):
    # contributor_secret 以明文传输，生产环境必须使用 HTTPS
    sample = pipeline.process(raw_text, contributor_id, category)
    encrypted = storage.encrypt_for_sample(sample, contributor_secret)
    sample.encrypted_blob = encrypted
    storage.save_sample(sample)
    generator = AntiPatternGenerator()
    skill = generator.generate(sample, contributor_id)
    storage.save_anti_pattern(skill)
    logger.info("Negative sample %s uploaded by %s", sample.id, contributor_id)
    return {
        "sample_id": sample.id,
        "risk_level": sample.risk_level,
        "anti_pattern_skill_id": skill.id,
    }


@router.post("/{sample_id}/call")
async def call_anti_pattern(
    sample_id: str,
    params: dict = Body(default={}),
    storage: StorageBackend = Depends(get_storage),
    generator: AntiPatternGenerator = Depends(get_generator),
):
    sample = storage.get_sample(sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")
    skill = storage.get_anti_pattern(sample_id)
    if not skill:
        skills = storage.discover_anti_patterns()
        skill = next((s for s in skills if s.sample_id == sample_id), None)
        if not skill:
            skill = generator.generate(sample, "system")
            storage.save_anti_pattern(skill)
    result = generator.call(skill, params)
    storage.update_call_stats(skill.id)
    return {
        "risk_level": result.risk_level,
        "warning": result.warning,
        "anti_pattern_id": result.anti_pattern_id,
    }


@router.get("/discover")
async def discover_anti_patterns(
    category: str | None = None,
    risk_level: str | None = None,
    storage: StorageBackend = Depends(get_storage),
):
    skills = storage.discover_anti_patterns(category, risk_level)
    results = []
    for s in skills:
        manifest = s.skill_manifest
        results.append(
            {
                "id": s.id,
                "name": manifest.get("name", ""),
                "description": manifest.get("description", ""),
                "risk_level": manifest.get("metadata", {}).get("risk_level", "medium"),
                "category": manifest.get("metadata", {}).get("category", "general"),
                "price_per_call": manifest.get("price_per_call", 0.1),
                "call_count": s.call_count,
            }
        )
    return {"skills": results, "total": len(results)}
