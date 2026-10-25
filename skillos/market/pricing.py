import math

from sqlalchemy.orm import Session

from skillos.db.models import SkillListingModel


class PricingEngine:
    def __init__(self, db_session: Session):
        self._db = db_session

    def calculate_price(self, listing_id: str) -> dict:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if not model:
            return {"error": "Listing not found", "price": 0.0}

        base_price = model.price_per_call
        supply_factor = self._compute_supply_factor(model.category)
        demand_factor = self._compute_demand_factor(model)
        quality_factor = self._compute_quality_factor(model.quality_score)

        adjusted_price = base_price * supply_factor * demand_factor * quality_factor
        adjusted_price = max(0.001, round(adjusted_price, 6))

        return {
            "listing_id": listing_id,
            "base_price": base_price,
            "supply_factor": round(supply_factor, 4),
            "demand_factor": round(demand_factor, 4),
            "quality_factor": round(quality_factor, 4),
            "adjusted_price": adjusted_price,
        }

    def compute_optimal_price(self, listing_id: str, max_price: float | None = None) -> dict:
        current = self.calculate_price(listing_id)
        if "error" in current:
            return current

        base = current["base_price"]
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if model is None:
            return {"error": "Listing not found", "price": 0.0}

        competitor_count = (
            self._db.query(SkillListingModel)
            .filter(
                SkillListingModel.category == model.category,
                SkillListingModel.status == "active",
                SkillListingModel.id != listing_id,
            )
            .count()
        )

        optimal = base
        if competitor_count > 20:
            optimal = base * 0.70
        elif competitor_count > 5:
            optimal = base * 0.85
        elif competitor_count == 0:
            optimal = base * 1.15

        if model.quality_score > 0.8:
            optimal *= 1.10
        elif model.quality_score < 0.3:
            optimal *= 0.80

        if max_price is not None:
            optimal = min(optimal, max_price)

        optimal = max(0.001, round(optimal, 6))

        return {
            "listing_id": listing_id,
            "current_adjusted": current["adjusted_price"],
            "optimal_price": optimal,
            "competitor_count": competitor_count,
            "quality_score": model.quality_score,
        }

    def _compute_supply_factor(self, category: str) -> float:
        count = (
            self._db.query(SkillListingModel)
            .filter(
                SkillListingModel.category == category,
                SkillListingModel.status == "active",
            )
            .count()
        )
        if count <= 1:
            return 1.5
        return max(0.5, 1.0 - math.log(count) * 0.1)

    def _compute_demand_factor(self, model: SkillListingModel) -> float:
        calls = model.total_calls or 0
        if calls <= 0:
            return 0.8
        return min(2.0, 1.0 + math.log10(calls + 1) * 0.15)

    def _compute_quality_factor(self, quality_score: float) -> float:
        return 0.5 + quality_score
