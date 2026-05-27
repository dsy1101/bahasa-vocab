# 🇮🇩 인니어 스마트 복습 (Streamlit)

라이트너(Leitner) 알고리즘 기반 인도네시아어 단어 복습 모바일 웹앱.
다중 사용자 분리 · 대량 텍스트 파싱 · 가변 글자 힌트 · 음성 답변(id-ID) · 가벼운 PWA.

## 파일 구조
| 파일 | 역할 |
|------|------|
| `app.py` | 메인 Streamlit UI / 모바일 뷰 라우팅 |
| `database.py` | SQLite 연동 (users / vocab_list, 사용자별 데이터) |
| `parser.py` | 대량 불규칙 텍스트 파싱 엔진 |
| `auth.py` | 회원가입 / 로그인 (PBKDF2 해싱) |
| `requirements.txt` | 배포 의존성 |
| `.streamlit/config.toml` | 테마 · 정적 서빙(PWA) 설정 |
| `static/` | PWA manifest · 아이콘 |

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
브라우저에서 열린 뒤 회원가입 → 로그인 → [➕ 단어 추가]에서 텍스트 붙여넣기 → [📚 오늘의 복습].

## 입력 텍스트 형식 (정리 규칙)
**단어끼리 빈 줄 1칸으로 구분**하는 것이 유일한 규칙. 나머지는 자유 형식.
```
Meledak(믈르닥) = 터지다  #일상회화
Bom meledak = 폭탄이 터지다
balon meledak = 풍선이 터지다

produsen = 생산자, 제조사

Tindakan → action  @sikap
Harus dibuktikan dengan tindakan.
→ 행동으로 보여줘야 해요
```
- **블록(단어) 사이는 빈 줄 1칸**으로 구분한다.
- 블록의 **첫 줄 = 단어**: `단어(발음) = 뜻` 또는 `단어 → 뜻` (구분 기호 `=` 우선, 없으면 `→`).
  - 뜻에 `=` 가 더 있어도(예: `it's like = 말하자면`) 그대로 보존.
- 블록의 **둘째 줄부터는 전부 예문/해석**. 여기선 `=`·`→` 자유롭게 써도 모두 예문 처리됨.
- `#태그` → `tags`, `@연관단어` → `meaning` 에 자동 연동.

## 라이트너 복습 주기
| 레벨 | 1 | 2 | 3 | 4 | 5 |
|------|---|---|---|---|---|
| 다음 복습(일) | +1 | +2 | +4 | +7 | +15 |
- **👍 알아요**: 레벨업(최대 5) + 주기 연장
- **👎 헷갈려요**: 즉시 Lv.1 강등 → 내일 재출제

## 힌트 시스템
- 단어 글자 수만큼 `_ _ _ _` 동적 마스킹.
- 1차: 첫 글자 공개 / 2차: 나머지 빈칸 중 랜덤 1개.
- 글자 수 4 이하(예: `ragu`)는 힌트 1회로 제한.

## 음성 답변 (Web Speech API)
- 브라우저 `webkitSpeechRecognition`, 언어 `id-ID`. 클릭 시 `🔴 인식 중...` 표시.
- 인식 결과를 정답과 즉시 비교(✅/❌). Chrome/Edge(모바일 포함) 권장, 일부 브라우저 미지원.

## PWA (홈 화면 추가)
`config.toml`의 `server.enableStaticServing=true` 로 `static/manifest.json` 을 서빙하고,
앱이 부모 문서에 manifest/메타 태그를 주입한다. 모바일 브라우저 메뉴 →
"홈 화면에 추가" 로 아이콘 설치 가능.

> 참고: Streamlit은 `<head>` 직접 제어가 제한적이라 본 구성은 **가벼운(애드투홈) PWA** 수준입니다.
> 완전한 오프라인 캐시(Service Worker scope)는 별도 리버스 프록시 배포 시 확장하세요.

## 배포 (Streamlit Community Cloud)
저장소를 GitHub에 올리고 `app.py` 를 진입점으로 지정하면 됩니다.
DB 경로는 환경변수 `VOCAB_DB_PATH` 로 변경 가능. (클라우드는 임시 디스크이므로
영구 보존이 필요하면 외부 DB/스토리지 연동을 권장합니다.)
