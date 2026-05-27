"""
auth.py
다른 학습자와 공유하기 위한 가벼운 회원가입/로그인 모듈.
비밀번호는 평문 저장하지 않고 사용자별 salt + PBKDF2-HMAC(SHA256) 으로 해싱한다.
외부 의존성 없이 표준 라이브러리 hashlib 만 사용한다.
"""

import binascii
import hashlib
import os
import sqlite3

import database as db

_ITERATIONS = 100_000


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return binascii.hexlify(dk).decode("ascii")


def signup(username: str, password: str) -> tuple[bool, str]:
    """
    신규 가입. 반환: (성공여부, 메시지).
    """
    username = (username or "").strip()
    if len(username) < 2:
        return False, "아이디는 2글자 이상이어야 합니다."
    if len(password or "") < 4:
        return False, "비밀번호는 4글자 이상이어야 합니다."

    salt = os.urandom(16)
    pw_hash = _hash_password(password, salt)
    try:
        db.create_user(username, pw_hash, binascii.hexlify(salt).decode("ascii"))
    except sqlite3.IntegrityError:
        return False, "이미 사용 중인 아이디입니다."
    return True, "가입 완료! 로그인해 주세요."


def login(username: str, password: str):
    """
    로그인. 성공 시 사용자 정보 dict, 실패 시 None.
    """
    username = (username or "").strip()
    row = db.get_user_by_name(username)
    if row is None:
        return None
    salt = binascii.unhexlify(row["salt"])
    if _hash_password(password, salt) == row["password_hash"]:
        return {"id": row["id"], "username": row["username"]}
    return None


def ensure_user(username: str, password: str = "1234") -> dict:
    """
    자동 로그인용. 해당 계정이 없으면 기본 비밀번호로 생성하고 사용자 dict 를 반환한다.
    (수동 로그인도 가능하도록 비밀번호가 설정된 정상 계정을 만든다)
    """
    username = (username or "").strip()
    row = db.get_user_by_name(username)
    if row is None:
        signup(username, password)
        row = db.get_user_by_name(username)
    return {"id": row["id"], "username": row["username"]}
