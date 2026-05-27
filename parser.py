"""
parser.py
대량 텍스트 인제스천 엔진 (블록 기반).

메모장/워드에서 수십 장 분량을 통째로 붙여넣어도 유연하게 단어 단위로 쪼갠다.

파싱 규칙 (정리 규칙)
  1) 단어 한 개 = 한 덩어리(블록). 블록과 블록 사이는 '빈 줄 1칸' 으로 구분한다.
  2) 블록의 '첫 줄' 이 단어 줄이다.
       - '단어(발음) = 뜻'  또는  '단어 → 뜻'  (구분 기호는 '=' 우선, 없으면 '→')
       - 괄호 안은 한글 발음 가이드(예: 믈르닥)로 분리한다.
       - 뜻에 '=' 가 더 있어도(예: it's like = 말하자면) 그대로 보존한다.
  3) 블록의 '둘째 줄부터'는 전부 예문/해석(examples)으로 묶는다.
       - 여기서는 '=' 든 '→' 든 자유 형식이며 모두 예문으로 처리된다.
  4) 블록 어디에 있든 '#태그' 는 tags 필드로, '@연관단어' 는 meaning 필드로 연동한다.
"""

import re

# 한글/영문/숫자/언더스코어를 토큰 문자로 인정 (공백/문장부호에서 끊김)
_TAG_RE = re.compile(r"#[\w가-힣]+")
_REL_RE = re.compile(r"@[\w가-힣]+")
# '단어(발음)' 분리용
_WORD_PRON_RE = re.compile(r"^\s*(.+?)\s*\(\s*([^)]*?)\s*\)\s*$")
# 블록 구분: 한 줄 이상의 공백 줄
_BLOCK_SPLIT_RE = re.compile(r"\n[ \t]*\n+")


def _split_word_pron(left: str) -> tuple[str, str]:
    """단어부를 받아 (단어, 발음)으로 분리. 괄호가 없으면 발음은 빈 문자열."""
    m = _WORD_PRON_RE.match(left)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return left.strip(), ""


def _split_headword(line: str) -> tuple[str, str, str]:
    """단어 줄을 (단어, 발음, 뜻)으로 분리. 구분 기호는 '=' 우선, 없으면 '→'."""
    if "=" in line:
        left, right = line.split("=", 1)
    elif "→" in line:
        left, right = line.split("→", 1)
    else:
        left, right = line, ""
    word, pron = _split_word_pron(left.strip())
    return word, pron, right.strip()


def _finalize(word: str, pron: str, meaning: str, example_lines: list[str]) -> dict | None:
    """한 블록을 최종 스키마 dict 로 정리한다."""
    word = (word or "").strip()
    if not word:
        return None

    examples = "\n".join(example_lines).strip()

    # 블록 전체(뜻 + 예문)에서 태그/연관단어 수집
    blob = meaning + "\n" + examples
    tags = list(dict.fromkeys(_TAG_RE.findall(blob)))   # 중복 제거, 순서 유지
    rels = list(dict.fromkeys(_REL_RE.findall(blob)))

    # 본문에서는 태그/연관 토큰을 제거해 깔끔하게 보관
    meaning = _REL_RE.sub("", _TAG_RE.sub("", meaning)).strip()
    examples = _REL_RE.sub("", _TAG_RE.sub("", examples)).strip()

    # 연관단어는 뜻 필드 끝에 연동 표기
    if rels:
        rel_str = ", ".join(r[1:] for r in rels)  # 앞의 '@' 제거
        meaning = (meaning + (" " if meaning else "") + f"🔗 연관: {rel_str}").strip()

    return {
        "word": word,
        "pronunciation": pron,
        "meaning": meaning,
        "examples": examples,
        "tags": ",".join(tags),
    }


def parse(text: str) -> list[dict]:
    """대량 텍스트를 단어 entry 리스트로 변환한다 (빈 줄로 블록 분리)."""
    entries: list[dict] = []

    for block in _BLOCK_SPLIT_RE.split((text or "").strip()):
        lines = block.splitlines()
        # 블록 내 첫 번째 비어있지 않은 줄 = 단어 줄
        head_idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
        if head_idx is None:
            continue
        word, pron, meaning = _split_headword(lines[head_idx].strip())
        example_lines = [ln for ln in lines[head_idx + 1:]]

        done = _finalize(word, pron, meaning, example_lines)
        if done:
            entries.append(done)

    return entries
