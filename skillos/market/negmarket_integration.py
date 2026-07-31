"""NegMarket 集成 — 反模式 Skill 自动注册到技能市场。"""

from sqlalchemy.orm import Session

from skillos.market.registry import SkillRegistry


def register_antipattern_as_market_skill(
    db_session: Session,
    antipattern_skill_id: str,
    name: str,
    author: str,
    category: str = "security",
    price_per_call: float = 0.01,
) -> dict:
    reg = SkillRegistry(db_session)
    listing = reg.register(
        skill_id=antipattern_skill_id,
        name=name,
        version="1.0.0",
        author=author,
        description=f"NegMarket anti-pattern skill: {name}",
        category=category,
        tags=["antipattern", "security", "negmarket"],
        price_per_call=price_per_call,
    )
    return {
        "market_listing_id": listing.id,
        "skill_id": antipattern_skill_id,
        "status": "registered",
        "category": category,
        "price_per_call": price_per_call,
    }
