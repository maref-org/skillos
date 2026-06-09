#!/usr/bin/env python3
"""skillos.db.repository — 数据访问对象（Repository 模式）

为各核心模块提供类型安全的 CRUD 接口，屏蔽 ORM 细节。
"""


from sqlalchemy.orm import Session

from skillos.db.models import (
    ContributorModel,
    DistributionRecordModel,
    SessionModel,
    SkillModel,
    SkillNFTModel,
)


class SkillRepository:
    """Skill 数据访问对象。"""

    def __init__(self, db: Session):
        self._db = db

    def get(self, skill_id: str) -> SkillModel | None:
        return self._db.get(SkillModel, skill_id)

    def list_all(self, status: str | None = None) -> list[SkillModel]:
        query = self._db.query(SkillModel)
        if status:
            query = query.where(SkillModel.status == status)
        return query.all()

    def save(self, skill: SkillModel) -> SkillModel:
        self._db.merge(skill)
        self._db.commit()
        return skill

    def delete(self, skill_id: str) -> bool:
        obj = self.get(skill_id)
        if obj:
            self._db.delete(obj)
            self._db.commit()
            return True
        return False


class SkillNFTRepository:
    """SkillNFT 数据访问对象。"""

    def __init__(self, db: Session):
        self._db = db

    def get_by_skill(self, skill_id: str) -> list[SkillNFTModel]:
        return self._db.query(SkillNFTModel).where(SkillNFTModel.skill_id == skill_id).all()

    def save(self, nft: SkillNFTModel) -> SkillNFTModel:
        self._db.merge(nft)
        self._db.commit()
        return nft


class SessionRepository:
    """Session 数据访问对象。"""

    def __init__(self, db: Session):
        self._db = db

    def get(self, session_id: str) -> SessionModel | None:
        return self._db.get(SessionModel, session_id)

    def list_by_user(self, user_id: str, status: str | None = None) -> list[SessionModel]:
        query = self._db.query(SessionModel).where(SessionModel.user_id == user_id)
        if status:
            query = query.where(SessionModel.status == status)
        return query.order_by(SessionModel.updated_at.desc()).all()

    def list_all(self, status: str | None = None) -> list[SessionModel]:
        query = self._db.query(SessionModel)
        if status:
            query = query.where(SessionModel.status == status)
        return query.order_by(SessionModel.updated_at.desc()).all()

    def save(self, session: SessionModel) -> SessionModel:
        self._db.merge(session)
        self._db.commit()
        return session

    def delete(self, session_id: str) -> bool:
        obj = self.get(session_id)
        if obj:
            self._db.delete(obj)
            self._db.commit()
            return True
        return False


class DistributionRepository:
    """DistributionRecord 数据访问对象。"""

    def __init__(self, db: Session):
        self._db = db

    def get(self, record_id: str) -> DistributionRecordModel | None:
        return self._db.get(DistributionRecordModel, record_id)

    def list_by_skill(self, skill_id: str, limit: int = 100) -> list[DistributionRecordModel]:
        return (
            self._db.query(DistributionRecordModel)
            .where(DistributionRecordModel.skill_id == skill_id)
            .order_by(DistributionRecordModel.timestamp.desc())
            .limit(limit)
            .all()
        )

    def list_all(self, limit: int = 10000) -> list[DistributionRecordModel]:
        return (
            self._db.query(DistributionRecordModel)
            .order_by(DistributionRecordModel.timestamp.desc())
            .limit(limit)
            .all()
        )

    def save(self, record: DistributionRecordModel) -> DistributionRecordModel:
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    def get_period_revenue(self, period_key: str) -> float:
        """period_key 格式: YYYY-MM-DD 或 YYYY-MM。"""
        from sqlalchemy import func

        result = (
            self._db.query(func.sum(DistributionRecordModel.total_amount))
            .where(DistributionRecordModel.timestamp.startswith(period_key))  # type: ignore[attr-defined]
            .scalar()
        )
        return float(result or 0.0)


class ContributorRepository:
    """Contributor 数据访问对象。"""

    def __init__(self, db: Session):
        self._db = db

    def get(self, contributor_id: str) -> ContributorModel | None:
        return self._db.get(ContributorModel, contributor_id)

    def list_all(self) -> list[ContributorModel]:
        return self._db.query(ContributorModel).all()

    def save(self, contributor: ContributorModel) -> ContributorModel:
        self._db.merge(contributor)
        self._db.commit()
        return contributor
