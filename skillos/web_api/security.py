from __future__ import annotations

from fastapi import APIRouter, Body

from skillos.audit import AuditEventType, get_audit_logger
from skillos.security.hallucination_detector import HallucinationDetector
from skillos.security.message_signer import MessageSigner
from skillos.security.prompt_guard import detect_prompt_injection, sanitize_user_input

router = APIRouter(tags=["安全审计"])


@router.get("/audit/log")
async def audit_log(event_type: str | None = None, limit: int = 50):
    logger = get_audit_logger()
    evt = AuditEventType(event_type) if event_type else None
    records = logger.query(event_type=evt, limit=limit)
    return {
        "records": [
            {
                "id": r.get("record_id", ""),
                "event_type": r.get("event_type", ""),
                "actor_id": r.get("actor_id", ""),
                "resource_id": r.get("resource_id", ""),
                "timestamp": str(r.get("timestamp", "")),
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/audit/verify")
async def audit_verify():
    logger = get_audit_logger()
    result = logger.verify_chain()
    return {"status": "intact" if result else "broken", "verified": result}


@router.post("/security/detect-injection")
async def detect_injection(text: str = Body(..., embed=True)):
    result = detect_prompt_injection(text)
    return {
        "is_injection": result.is_injection,
        "risk_score": result.risk_score,
        "matched_patterns": result.matched_patterns,
    }


@router.post("/security/sanitize")
async def sanitize_input(text: str = Body(..., embed=True)):
    sanitized = sanitize_user_input(text)
    return {"original": text, "sanitized": sanitized}


@router.post("/security/sign")
async def sign_message(payload: dict = Body(...)):
    signer = MessageSigner("api-signer")
    headers = signer.sign_headers(payload)
    return {"headers": headers}


@router.post("/security/detect-hallucination")
async def detect_hallucination(text: str = Body(..., embed=True)):
    detector = HallucinationDetector()
    result = detector.analyze_output(text)
    return {
        "risk_level": str(getattr(result, "risk_level", "unknown")),
        "score": getattr(result, "score", 0),
        "reasons": getattr(result, "reasons", []),
    }
