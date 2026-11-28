"""KC 影子掌握值：独立 SQLite 表，不写入正式 mastery。

表只服务教学链路；正式 BKT 仍由现有仓储路径维护。
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..config import db_path
from ..domain.bkt import BKTParams
from .attempts import TeachingAttempt, apply_attempt

SHADOW_DB_ENV = "MATHCOACH_KC_DB"
SHADOW_DB_NAME = "kc-shadow.sqlite3"
SHADOW_TABLE = "kc_mastery_shadow"
_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {SHADOW_TABLE} (
    kc_id TEXT PRIMARY KEY,
    probability REAL NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
)
"""


def shadow_db_path() -> Path:
    """返回影子库路径；默认与正式库同目录，文件名独立。"""
    override = os.getenv(SHADOW_DB_ENV)
    if override:
        return Path(override)
    return db_path().with_name(SHADOW_DB_NAME)


class KCMasteryStore:
    """KC 影子掌握值的 SQLite 存储。"""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else shadow_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def get(self, kc_id: str) -> float | None:
        """读取 KC 影子概率；没有记录时返回 None。"""
        row = self._connection.execute(
            f"SELECT probability FROM {SHADOW_TABLE} WHERE kc_id = ?",
            (kc_id,),
        ).fetchone()
        return float(row["probability"]) if row is not None else None

    def sample_size(self, kc_id: str) -> int:
        """返回 KC 的累计观测次数。"""
        row = self._connection.execute(
            f"SELECT sample_size FROM {SHADOW_TABLE} WHERE kc_id = ?",
            (kc_id,),
        ).fetchone()
        return int(row["sample_size"]) if row is not None else 0

    def load(self) -> dict[str, float]:
        """返回全部 KC 影子概率。"""
        rows = self._connection.execute(
            f"SELECT kc_id, probability FROM {SHADOW_TABLE}"
        ).fetchall()
        return {row["kc_id"]: float(row["probability"]) for row in rows}

    def load_with_samples(self) -> tuple[dict[str, float], dict[str, int]]:
        """一次查询返回全部影子概率与样本量，避免逐 KC 查询。"""
        rows = self._connection.execute(
            f"SELECT kc_id, probability, sample_size FROM {SHADOW_TABLE}"
        ).fetchall()
        mastery = {
            row["kc_id"]: float(row["probability"]) for row in rows
        }
        samples = {
            row["kc_id"]: int(row["sample_size"]) for row in rows
        }
        return mastery, samples

    def set(
        self,
        kc_id: str,
        probability: float,
        sample_size: int,
        now: datetime | None = None,
    ) -> None:
        """写入一条影子概率并截到 [0, 1]。"""
        value = max(0.0, min(1.0, float(probability)))
        moment = now or datetime.now(timezone.utc)
        with self._connection:
            self._connection.execute(
                f"""
                INSERT INTO {SHADOW_TABLE}(
                    kc_id, probability, sample_size, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(kc_id) DO UPDATE SET
                    probability = excluded.probability,
                    sample_size = excluded.sample_size,
                    updated_at = excluded.updated_at
                """,
                (kc_id, value, int(sample_size), moment.isoformat()),
            )

    def record(
        self,
        attempt: TeachingAttempt,
        *,
        params: BKTParams | None = None,
        count_pretest: bool = False,
    ) -> dict[str, float]:
        """按作答来源更新影子掌握值；前测默认不落库。

        Args:
            attempt: 一次教学相关作答。
            params: BKT 四参数；None 时读取 content/bkt_params.yaml。
            count_pretest: 是否允许前测计入影子 BKT。

        Returns:
            KC ID -> 更新后的影子概率。
        """
        current = self.load()
        priors = {
            kc_id: current[kc_id]
            for kc_id in attempt.kc_ids
            if kc_id in current
        }
        updates = apply_attempt(
            priors,
            attempt,
            params=params,
            count_pretest=count_pretest,
        )
        if attempt.source == "pretest" and not count_pretest:
            return updates
        now = datetime.now(timezone.utc)
        for kc_id, probability in updates.items():
            self.set(
                kc_id,
                probability,
                self.sample_size(kc_id) + 1,
                now,
            )
        return updates

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def __enter__(self) -> KCMasteryStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
