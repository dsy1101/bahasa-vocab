"""
database.py
SQLite 연동 계층. 사용자(users)와 단어(vocab_list)를 이원화해 관리한다.
사용자별로 학습 진도(review_level, next_review)가 섞이지 않도록 모든 단어 쿼리는
user_id 로 필터링한다. 외부 의존성 없이 표준 라이브러리 sqlite3 만 사용한다.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

# 배포 환경에서 경로를 바꿀 수 있도록 환경변수로 오버라이드 가능
DB_PATH = os.environ.get(
    "VOCAB_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocab.db"),
)

# 라이트너 복습 단계별 다음 복습까지의 간격(일).
# 레벨이 오를수록 복습 주기가 길어진다.
LEVEL_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}
MAX_LEVEL = 5


@contextmanager
def get_conn():
    """커밋/클로즈를 자동 처리하는 커넥션 컨텍스트."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """앱 기동 시 1회 호출. 테이블이 없으면 생성한다."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocab_list (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                word          TEXT NOT NULL,          -- 인도네시아어 단어 (Key)
                pronunciation TEXT DEFAULT '',        -- 괄호 안 한글 발음 (예: 쁨발룻)
                meaning       TEXT DEFAULT '',        -- 영어/한글 혼용 뜻
                examples      TEXT DEFAULT '',        -- '→' 포함 예문/해석 원문 전체
                tags          TEXT DEFAULT '',        -- '#비즈니스,#일상회화' 형태
                review_level  INTEGER NOT NULL DEFAULT 1,   -- 라이트너 단계 (1~5)
                next_review   TEXT NOT NULL,          -- 다음 복습 예정일 (YYYY-MM-DD)
                created_at    TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vocab_user ON vocab_list(user_id, next_review)"
        )


# ---------------------------------------------------------------------------
# 사용자(users)
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str, salt: str) -> int:
    """신규 사용자 생성. username 중복 시 sqlite3.IntegrityError 발생."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) "
            "VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, date.today().isoformat()),
        )
        return cur.lastrowid


def get_user_by_name(username: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row


# ---------------------------------------------------------------------------
# 단어(vocab_list)
# ---------------------------------------------------------------------------

def add_vocab_bulk(user_id: int, entries: list[dict]) -> tuple[int, int]:
    """
    파서가 만든 entries 리스트를 일괄 저장한다.
    동일 사용자가 이미 가진 단어(word)는 건너뛴다.
    반환: (추가된 개수, 중복으로 건너뛴 개수)
    """
    added = skipped = 0
    today = date.today().isoformat()
    with get_conn() as conn:
        existing = {
            r["word"]
            for r in conn.execute(
                "SELECT word FROM vocab_list WHERE user_id = ?", (user_id,)
            )
        }
        for e in entries:
            word = (e.get("word") or "").strip()
            if not word:
                continue
            if word in existing:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO vocab_list
                    (user_id, word, pronunciation, meaning, examples, tags,
                     review_level, next_review, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    word,
                    e.get("pronunciation", ""),
                    e.get("meaning", ""),
                    e.get("examples", ""),
                    e.get("tags", ""),
                    today,        # 등록 당일을 기본 복습일로
                    today,
                ),
            )
            existing.add(word)
            added += 1
    return added, skipped


def get_due_words(user_id: int, tag: str | None = None) -> list[sqlite3.Row]:
    """next_review 가 오늘이거나 과거인 단어만 모은다. tag 지정 시 해당 태그로 필터."""
    today = date.today().isoformat()
    sql = (
        "SELECT * FROM vocab_list "
        "WHERE user_id = ? AND date(next_review) <= date(?)"
    )
    params: list = [user_id, today]
    if tag:
        sql += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_all_tags(user_id: int) -> list[str]:
    """사용자가 보유한 단어들의 태그를 중복 없이 모아 정렬해 반환."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT tags FROM vocab_list WHERE user_id = ? AND tags != ''",
            (user_id,),
        ).fetchall()
    tags: set[str] = set()
    for r in rows:
        for t in r["tags"].split(","):
            t = t.strip()
            if t:
                tags.add(t)
    return sorted(tags)


def apply_review_result(word_id: int, known: bool):
    """
    자기주도 채점 결과를 라이트너 알고리즘으로 반영한다.
    - 알아요(known=True): 레벨업(최대 5) 후 해당 레벨 간격만큼 복습일 연장.
    - 헷갈려요(known=False): 즉시 레벨 1로 강등, 내일 다시 출제.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT review_level FROM vocab_list WHERE id = ?", (word_id,)
        ).fetchone()
        if row is None:
            return
        level = row["review_level"]
        if known:
            level = min(level + 1, MAX_LEVEL)
            next_day = date.today() + timedelta(days=LEVEL_INTERVALS[level])
        else:
            level = 1
            next_day = date.today() + timedelta(days=1)
        conn.execute(
            "UPDATE vocab_list SET review_level = ?, next_review = ? WHERE id = ?",
            (level, next_day.isoformat(), word_id),
        )


def get_stats(user_id: int) -> dict:
    """통계 화면용 집계."""
    today = date.today().isoformat()
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) c FROM vocab_list WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
        due = conn.execute(
            "SELECT COUNT(*) c FROM vocab_list "
            "WHERE user_id = ? AND date(next_review) <= date(?)",
            (user_id, today),
        ).fetchone()["c"]
        by_level = {
            r["review_level"]: r["c"]
            for r in conn.execute(
                "SELECT review_level, COUNT(*) c FROM vocab_list "
                "WHERE user_id = ? GROUP BY review_level",
                (user_id,),
            )
        }
    return {"total": total, "due": due, "by_level": by_level}
