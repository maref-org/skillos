#!/usr/bin/env python3
"""Storage — 负样本加密存储层

使用 AES-256-GCM 加密原始文本后存入 SQLite。
密钥派生: HKDF(contributor_secret, sample_id)。
"""

import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from pathlib import Path

from skillos.negmarket.models import AntiPatternSkill, NegativeSample

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "data/negmarket.db"


def _aes_encrypt(plaintext: str, key: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return b64encode(nonce + ciphertext).decode()


def _aes_decrypt(encrypted: str, key: bytes) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def _derive_key(contributor_secret: str, sample_id: str) -> bytes:
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    hkdf = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=sample_id.encode(),
    )
    return hkdf.derive(contributor_secret.encode())


class StorageBackend(ABC):
    @abstractmethod
    def save_sample(self, sample: NegativeSample) -> None: ...

    @abstractmethod
    def get_sample(self, sample_id: str) -> NegativeSample | None: ...

    @abstractmethod
    def list_samples(self, category: str | None = None, risk_level: str | None = None) -> list[NegativeSample]: ...

    @abstractmethod
    def save_anti_pattern(self, skill: AntiPatternSkill) -> None: ...

    @abstractmethod
    def get_anti_pattern(self, skill_id: str) -> AntiPatternSkill | None: ...

    @abstractmethod
    def discover_anti_patterns(
        self, category: str | None = None, risk_level: str | None = None
    ) -> list[AntiPatternSkill]: ...

    @abstractmethod
    def update_call_stats(self, skill_id: str, revenue: float = 0.0) -> None: ...


class SQLiteNegMarketStorage(StorageBackend):
    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS negative_samples (
                    id TEXT PRIMARY KEY,
                    contributor_id TEXT NOT NULL,
                    original_hash TEXT NOT NULL,
                    encrypted_blob TEXT NOT NULL DEFAULT '',
                    desensitized_pattern TEXT NOT NULL DEFAULT '{}',
                    category TEXT NOT NULL DEFAULT 'general',
                    risk_level TEXT NOT NULL DEFAULT 'medium',
                    verification_status TEXT NOT NULL DEFAULT 'pending',
                    price_per_call REAL NOT NULL DEFAULT 0.1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS anti_pattern_skills (
                    id TEXT PRIMARY KEY,
                    sample_id TEXT NOT NULL,
                    skill_manifest TEXT NOT NULL DEFAULT '{}',
                    generated_by TEXT NOT NULL DEFAULT '',
                    call_count INTEGER NOT NULL DEFAULT 0,
                    revenue REAL NOT NULL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (sample_id) REFERENCES negative_samples(id)
                );

                CREATE INDEX IF NOT EXISTS idx_negmarket_category ON negative_samples(category);
                CREATE INDEX IF NOT EXISTS idx_negmarket_risk ON negative_samples(risk_level);
                CREATE INDEX IF NOT EXISTS idx_anti_pattern_sample ON anti_pattern_skills(sample_id);
            """)

    def _row_to_sample(self, row: sqlite3.Row) -> NegativeSample:
        return NegativeSample(
            id=row["id"],
            contributor_id=row["contributor_id"],
            original_hash=row["original_hash"],
            encrypted_blob=row["encrypted_blob"],
            desensitized_pattern=json.loads(row["desensitized_pattern"]),
            category=row["category"],
            risk_level=row["risk_level"],
            verification_status=row["verification_status"],
            price_per_call=row["price_per_call"],
            created_at=row["created_at"],
        )

    def _row_to_skill(self, row: sqlite3.Row) -> AntiPatternSkill:
        return AntiPatternSkill(
            id=row["id"],
            sample_id=row["sample_id"],
            skill_manifest=json.loads(row["skill_manifest"]),
            generated_by=row["generated_by"],
            call_count=row["call_count"],
            revenue=row["revenue"],
            created_at=row["created_at"],
        )

    def save_sample(self, sample: NegativeSample) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO negative_samples
                   (id, contributor_id, original_hash, encrypted_blob,
                    desensitized_pattern, category, risk_level,
                    verification_status, price_per_call, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sample.id,
                    sample.contributor_id,
                    sample.original_hash,
                    sample.encrypted_blob,
                    json.dumps(sample.desensitized_pattern),
                    sample.category,
                    sample.risk_level,
                    sample.verification_status,
                    sample.price_per_call,
                    sample.created_at,
                ),
            )

    def get_sample(self, sample_id: str) -> NegativeSample | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM negative_samples WHERE id = ?", (sample_id,)).fetchone()
            return self._row_to_sample(row) if row else None

    def list_samples(self, category: str | None = None, risk_level: str | None = None) -> list[NegativeSample]:
        query = "SELECT * FROM negative_samples WHERE 1=1"
        params: list[str] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level)
        query += " ORDER BY created_at DESC"
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_sample(r) for r in rows]

    def save_anti_pattern(self, skill: AntiPatternSkill) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO anti_pattern_skills
                   (id, sample_id, skill_manifest, generated_by,
                    call_count, revenue, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    skill.id,
                    skill.sample_id,
                    json.dumps(skill.skill_manifest),
                    skill.generated_by,
                    skill.call_count,
                    skill.revenue,
                    skill.created_at,
                ),
            )

    def get_anti_pattern(self, skill_id: str) -> AntiPatternSkill | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM anti_pattern_skills WHERE id = ?", (skill_id,)).fetchone()
            return self._row_to_skill(row) if row else None

    def discover_anti_patterns(
        self, category: str | None = None, risk_level: str | None = None
    ) -> list[AntiPatternSkill]:
        query = """SELECT a.* FROM anti_pattern_skills a
                   JOIN negative_samples n ON a.sample_id = n.id
                   WHERE 1=1"""
        params: list[str] = []
        if category:
            query += " AND n.category = ?"
            params.append(category)
        if risk_level:
            query += " AND n.risk_level = ?"
            params.append(risk_level)
        query += " ORDER BY a.call_count DESC"
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_skill(r) for r in rows]

    def update_call_stats(self, skill_id: str, revenue: float = 0.0) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE anti_pattern_skills SET call_count = call_count + 1, revenue = revenue + ? WHERE id = ?",
                (revenue, skill_id),
            )

    def encrypt_for_sample(self, sample: NegativeSample, contributor_secret: str) -> str:
        key = _derive_key(contributor_secret, sample.id)
        return _aes_encrypt(sample.original_hash, key)

    def decrypt_sample(self, encrypted_blob: str, contributor_secret: str, sample_id: str) -> str:
        key = _derive_key(contributor_secret, sample_id)
        return _aes_decrypt(encrypted_blob, key)
