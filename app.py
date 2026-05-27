"""
app.py
인니어 스마트 복습 — 모바일 퍼스트 Streamlit UI / 뷰 라우팅.

화면 구성
  - 비로그인: 로그인 / 회원가입
  - 로그인: [📚 오늘의 복습] · [➕ 단어 추가] · [📊 통계] 탭
플래시카드 퀴즈는 가변 글자 수 마스킹, 2단계 힌트, Web Speech API(id-ID) 음성 답변,
자기주도 채점(라이트너)을 제공한다.
"""

import os
import random

import streamlit as st
import streamlit.components.v1 as components

import auth
import database as db
import parser as vp

st.set_page_config(
    page_title="인니어 복습",
    page_icon="🇮🇩",
    layout="centered",
    initial_sidebar_state="collapsed",
)

db.init_db()


# ---------------------------------------------------------------------------
# 모바일 퍼스트 스타일 + 가벼운 PWA 메타 주입
# ---------------------------------------------------------------------------

def inject_mobile_css():
    st.markdown(
        """
        <style>
        /* 한 화면 안에 들어오도록 여백·세로 간격을 최소화 */
        .block-container {padding: 0.5rem 0.7rem 1rem 0.7rem !important; max-width: 560px;}
        #MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {
            display: none !important;
        }
        /* Streamlit 기본 세로 간격 축소 (요소 사이가 뜨지 않게) */
        [data-testid="stVerticalBlock"] {gap: 0.35rem !important;}
        [data-testid="stHorizontalBlock"] {gap: 0.4rem !important;}
        .element-container {margin-bottom: 0 !important;}
        [data-testid="stIFrame"] {margin: 0 !important;}
        /* 버튼: 큼직 + 둥근 모서리, 글자 줄바꿈 허용해 잘림 방지 */
        div.stButton > button {
            border-radius: 13px; font-weight: 700; padding: 0.5rem 0.3rem;
            min-height: 46px; line-height: 1.15; white-space: normal; height: auto;
        }
        /* 정답 입력창 */
        div[data-testid="stTextInput"] input {font-size: 1.02rem; padding: 0.55rem;}
        /* 탭 라벨 컴팩트 */
        button[data-baseweb="tab"] {padding: 5px 9px; font-size: 0.92rem;}
        [data-baseweb="tab-list"] {gap: 4px;}
        /* 마스킹 단어 박스 — 화면 너비에 맞춰 글자 크기 가변 (clamp), 가로 넘침 방지 */
        .mask-box {
            text-align: center; font-family: 'Courier New', monospace;
            font-size: clamp(1.3rem, 7vw, 2.0rem); letter-spacing: 0.08em; font-weight: 700;
            background: #f4f6fa; border-radius: 14px; padding: 0.6rem 0.4rem;
            margin: 0.25rem 0; color: #1f2937; word-break: break-word; overflow-wrap: anywhere;
        }
        .meaning-box {
            text-align: center; font-size: clamp(1.0rem, 4.5vw, 1.2rem); font-weight: 600;
            color: #374151; margin: 0.15rem 0; line-height: 1.35;
        }
        .answer-box {
            text-align: center; background: #ecfdf5; border-radius: 14px;
            padding: 0.55rem; margin: 0.2rem 0;
        }
        .answer-word {font-size: clamp(1.4rem, 6.5vw, 1.9rem); font-weight: 800; color: #047857;
            word-break: break-word; overflow-wrap: anywhere;}
        .answer-pron {font-size: 1.0rem; color: #6b7280;}
        /* 예문이 길면 카드 안에서 스크롤 (전체 화면이 안 밀리게) */
        .examples-box {
            background: #fffbeb; border-radius: 12px; padding: 0.5rem 0.65rem;
            margin-top: 0.3rem; font-size: 0.92rem; white-space: pre-wrap;
            line-height: 1.45; color: #374151; max-height: 28vh; overflow-y: auto;
        }
        .prog {text-align: center; color: #9ca3af; font-size: 0.82rem; margin-bottom: 0.1rem;}
        .topbar {font-size: 1.05rem; font-weight: 800; margin: 0 0 0.2rem 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_pwa():
    """홈 화면 추가(Add to Home Screen)를 위한 가벼운 PWA 메타 태그를 부모 문서에 주입."""
    components.html(
        """
        <script>
        const head = window.parent.document.head;
        function setMeta(attr, key, val){
            let el = head.querySelector(`meta[${attr}="${key}"]`);
            if(!el){ el = window.parent.document.createElement('meta');
                     el.setAttribute(attr, key); head.appendChild(el); }
            el.setAttribute('content', val);
        }
        // iOS / Android 홈 화면 아이콘·전체화면 힌트
        setMeta('name','apple-mobile-web-app-capable','yes');
        setMeta('name','apple-mobile-web-app-status-bar-style','black-translucent');
        setMeta('name','apple-mobile-web-app-title','인니어 복습');
        setMeta('name','theme-color','#FF5A5F');
        setMeta('name','viewport','width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover');
        // 정적 서빙된 manifest 연결 (config: server.enableStaticServing=true)
        if(!head.querySelector('link[rel="manifest"]')){
            const l = window.parent.document.createElement('link');
            l.rel='manifest'; l.href='app/static/manifest.json'; head.appendChild(l);
        }
        </script>
        """,
        height=0,
    )


def inject_inapp_browser_warning():
    """
    카톡/인스타/페북/라인 등 '인앱 브라우저'에서는 음성(TTS/마이크)이 막힌다.
    해당 환경을 감지해 '크롬·사파리에서 열기' 안내 배너를 상단에 띄운다.
    (안드로이드는 크롬으로 바로 여는 버튼 제공 / iOS는 메뉴 안내)
    """
    components.html(
        """
        <script>
        (function(){
          const W = window.parent;
          if(!W) return;
          const ua = (W.navigator.userAgent || '');
          const inApp = /KAKAOTALK|Instagram|FBAN|FBAV|FB_IAB|Line\\/|NAVER|DaumApps|; wv\\)/i.test(ua);
          if(!inApp) return;
          if(W.document.getElementById('inapp-warn')) return;
          const d = W.document.createElement('div');
          d.id = 'inapp-warn';
          d.style.cssText = 'position:sticky;top:0;z-index:99999;background:#fff3cd;color:#7a5c00;'
            + 'padding:10px 12px;font-size:13px;line-height:1.45;border-bottom:1px solid #ffe08a;text-align:center;';
          d.innerHTML = '\\uD83D\\uDD0A 음성 기능은 <b>크롬·사파리</b>에서 열어야 작동해요.<br>'
            + '우측 메뉴(⋮ 또는 공유) → <b>“다른 브라우저로 열기 / Safari로 열기”</b>';
          if(/Android/i.test(ua)){
            const url = W.location.host + W.location.pathname + W.location.search;
            const a = W.document.createElement('a');
            a.href = 'intent://' + url + '#Intent;scheme=https;package=com.android.chrome;end';
            a.textContent = '👉 크롬으로 열기';
            a.style.cssText = 'display:inline-block;margin-top:7px;background:#2563eb;color:#fff;'
              + 'padding:7px 16px;border-radius:9px;text-decoration:none;font-weight:800;';
            d.appendChild(W.document.createElement('br'));
            d.appendChild(a);
          }
          W.document.body.insertBefore(d, W.document.body.firstChild);
        })();
        </script>
        """,
        height=0,
    )


# ---------------------------------------------------------------------------
# 세션 상태
# ---------------------------------------------------------------------------

def init_state():
    ss = st.session_state
    ss.setdefault("user_id", None)
    ss.setdefault("username", None)
    ss.setdefault("quiz_active", False)
    ss.setdefault("quiz_queue", [])      # 단어 dict 리스트
    ss.setdefault("quiz_idx", 0)
    ss.setdefault("card", None)          # 현재 카드 진행 상태
    ss.setdefault("_logged_out", False)  # 세션 내 수동 로그아웃 여부


def _autologin_user():
    """
    자동 로그인 대상 계정명을 찾는다.
    우선순위: .streamlit/secrets.toml 의 autologin_user → 환경변수 VOCAB_AUTOLOGIN.
    설정이 없으면 None (= 정상 로그인 화면).
    """
    try:
        u = st.secrets.get("autologin_user")  # secrets 파일 없으면 예외
    except Exception:
        u = None
    return u or os.environ.get("VOCAB_AUTOLOGIN")


def reset_card_state(word: str):
    """카드 진입 시 힌트/공개 상태 초기화."""
    letters = word.replace(" ", "")
    max_hints = 1 if len(letters) <= 4 else 2  # 4글자 이하(예: ragu)는 힌트 1회
    st.session_state.card = {
        "revealed": False,
        "hints_used": 0,
        "positions": set(),   # 공개된 글자 인덱스
        "max_hints": max_hints,
    }


# ---------------------------------------------------------------------------
# 로그인 / 회원가입
# ---------------------------------------------------------------------------

def render_auth():
    st.markdown("<h2 style='text-align:center'>🇮🇩 인니어 스마트 복습</h2>", unsafe_allow_html=True)
    st.caption("매일 라이트너 알고리즘으로 똑똑하게 복습하세요.")
    tab_login, tab_signup = st.tabs(["🔑 로그인", "📝 회원가입"])

    with tab_login:
        u = st.text_input("아이디", key="login_u")
        p = st.text_input("비밀번호", type="password", key="login_p")
        if st.button("로그인", use_container_width=True, type="primary"):
            user = auth.login(u, p)
            if user:
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with tab_signup:
        u2 = st.text_input("아이디 (2글자 이상)", key="su_u")
        p2 = st.text_input("비밀번호 (4글자 이상)", type="password", key="su_p")
        if st.button("가입하기", use_container_width=True):
            ok, msg = auth.signup(u2, p2)
            (st.success if ok else st.error)(msg)


# ---------------------------------------------------------------------------
# 퀴즈 — 마스킹 / 음성 컴포넌트
# ---------------------------------------------------------------------------

def render_mask(word: str, positions: set) -> str:
    """가변 글자 수를 실시간 계산해 언더바로 마스킹. 공개 인덱스는 글자 노출."""
    cells = []
    for i, ch in enumerate(word):
        if ch == " ":
            cells.append("&nbsp;&nbsp;")
        elif i in positions:
            cells.append(ch)
        else:
            cells.append("_")
    return " ".join(cells)


def _js_safe(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def inject_audio_engine():
    """
    앱(부모) 페이지에 '한 번 잠금 해제하면 세션 내내 유지되는' 오디오 엔진을 심는다.
    - 첫 사용자 탭에서 무음을 재생해 오디오를 잠금 해제 → 이후 카드마다 탭 없이 자동재생
    - window.parent.playIndo(word): 구글 TTS(id)로 인니 발음, 실패 시 내장 음성 폴백
    Streamlit 재실행마다 호출되지만 플래그(__indoAudioReady)로 1회만 설정한다.
    """
    components.html(
        """
        <script>
        (function(){
          const W = window.parent;
          if (!W || W.__indoReady) return;          // 이미 설정됨 → 중복 방지
          W.__indoReady = true;
          // 인도네시아어 음성 판별 (Android 레거시 'in', 음성 이름까지 폭넓게 인식)
          function isId(v){
            const l=(v.lang||'').toLowerCase().replace('_','-');
            const n=(v.name||'').toLowerCase();
            return l.startsWith('id')||l.startsWith('in-')||l==='in'
                 ||n.indexOf('indonesia')>=0||n.indexOf('bahasa')>=0;
          }
          function idVoice(){ return (W.speechSynthesis.getVoices()||[]).find(isId)||null; }
          function go(word, v){
            if(!v) return;                          // 인니 음성 없으면 무음 (한국어로 읽지 않음)
            try {
              W.speechSynthesis.cancel();
              const u = new W.SpeechSynthesisUtterance(word);
              u.lang='id-ID'; u.rate=0.95; u.voice=v;
              W.speechSynthesis.speak(u);
            } catch(e){}
          }
          W.playIndo = function(word){
            let v = idVoice();
            if(v){ go(word, v); return; }
            // 음성 목록 로딩 대기 후 재시도 (최대 ~1.8초)
            let n=0; const t=setInterval(()=>{ v=idVoice(); n++; if(v||n>15){ clearInterval(t); go(word, v); } }, 120);
          };
          // 첫 제스처(탭/클릭)에서 무음 발화로 음성 합성 잠금 해제 (이후 자동재생 허용)
          function unlock(){
            try { const u=new W.SpeechSynthesisUtterance(' '); u.volume=0; W.speechSynthesis.speak(u); } catch(e){}
            W.document.removeEventListener('click', unlock, true);
            W.document.removeEventListener('touchstart', unlock, true);
          }
          W.document.addEventListener('click', unlock, true);
          W.document.addEventListener('touchstart', unlock, true);
          // 음성 목록 미리 로드 트리거
          try { W.speechSynthesis.getVoices(); W.speechSynthesis.onvoiceschanged=function(){}; } catch(e){}
        })();
        </script>
        """,
        height=0,
    )


def speech_component(answer: str):
    """
    Web Speech API(webkitSpeechRecognition) 음성 인식 버튼.
    언어 id-ID 로 동작하며, 클릭 시 '🔴 인식 중...' 피드백을 보여준다.
    인식 결과를 정답과 비교해 ✅/❌ 표시 + 사운드 피드백:
      - 정답: '띵동' 상승 2음 차임
      - 오답: '삐-' 부저음
    """
    safe = _js_safe(answer)
    components.html(
        f"""
        <div style="display:flex;flex-direction:column;gap:4px;">
          <button id="mic" style="width:100%;min-height:46px;border:none;border-radius:13px;
                  background:#2563eb;color:#fff;font-weight:700;font-size:0.96rem;cursor:pointer;">
            🎤 말로 답변하기
          </button>
          <div id="out" style="text-align:center;font-size:0.88rem;color:#374151;min-height:16px;"></div>
        </div>
        <script>
        const btn = document.getElementById('mic');
        const out = document.getElementById('out');
        const ANSWER = '{safe}';
        let actx = null;
        function tone(freq, start, dur, type) {{
            const o = actx.createOscillator(), g = actx.createGain();
            o.type = type || 'sine'; o.frequency.value = freq;
            o.connect(g); g.connect(actx.destination);
            const t = actx.currentTime + start;
            g.gain.setValueAtTime(0.0001, t);
            g.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
            g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
            o.start(t); o.stop(t + dur + 0.02);
        }}
        function correctSound() {{ tone(784, 0, 0.16); tone(1047, 0.14, 0.32); }}  // 띵동(상승)
        function wrongSound()   {{ tone(196, 0, 0.18, 'square'); tone(146, 0.16, 0.30, 'square'); }}  // 삐- 부저
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if(!SR){{
            btn.disabled = true; btn.style.background='#9ca3af';
            out.textContent = '이 브라우저는 음성 인식을 지원하지 않아요';
        }} else {{
            const rec = new SR();
            rec.lang = 'id-ID';                 // 인도네시아어 발음 인식
            rec.interimResults = false; rec.maxAlternatives = 3;
            btn.onclick = () => {{
                // 사용자 제스처에서 오디오 컨텍스트 활성화(사운드 재생 허용)
                if(!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
                if(actx.state === 'suspended') actx.resume();
                out.textContent = '🔴 인식 중...'; btn.style.background='#dc2626';
                try {{ rec.start(); }} catch(e) {{}}
            }};
            rec.onresult = (ev) => {{
                let heard = '';
                for(let i=0;i<ev.results[0].length;i++){{
                    heard = ev.results[0][i].transcript.trim();
                    if(heard.toLowerCase() === ANSWER.toLowerCase()) break;
                }}
                const ok = heard.toLowerCase() === ANSWER.toLowerCase();
                if(ok) {{ correctSound(); out.innerHTML = '✅ 정답! (' + heard + ')'; }}
                else  {{ wrongSound();   out.innerHTML = '❌ 들린 말: <b>' + heard + '</b>'; }}
                btn.style.background = '#2563eb';
            }};
            rec.onerror = () => {{ out.textContent='⚠️ 다시 시도해 주세요'; btn.style.background='#2563eb'; }};
            rec.onend = () => {{ if(out.textContent==='🔴 인식 중...') out.textContent=''; btn.style.background='#2563eb'; }};
        }}
        </script>
        """,
        height=74,
    )


def tts_component(word: str):
    """
    정답 단어를 인도네시아어 발음으로 재생한다.
    1순위: 구글 번역 TTS(tl=id) MP3 — 기기에 인니 음성이 없어도 정확한 인니 발음 보장.
    2순위(폴백): 브라우저 내장 SpeechSynthesis(id-ID) — 구글 TTS 재생 실패 시.
    모바일은 자동재생이 차단되므로 🔊 버튼 '탭'으로 재생한다(탭 제스처면 확실히 들림).
    """
    safe = _js_safe(word)
    components.html(
        f"""
        <button id="spk" style="width:100%;min-height:48px;border:none;border-radius:12px;
                background:#047857;color:#fff;font-weight:800;font-size:1.02rem;cursor:pointer;">
          🔊 인니 발음 듣기
        </button>
        <script>
        const WORD = '{safe}';
        function isId(v){{
            const l=(v.lang||'').toLowerCase().replace('_','-');
            const n=(v.name||'').toLowerCase();
            return l.startsWith('id')||l.startsWith('in-')||l==='in'
                 ||n.indexOf('indonesia')>=0||n.indexOf('bahasa')>=0;
        }}
        function idVoice(){{ return (window.speechSynthesis.getVoices()||[]).find(isId)||null; }}
        function go(v){{
            if(!v) return;                 // 인니 음성 없으면 무음 (한국어로 읽지 않음)
            try {{
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(WORD);
                u.lang='id-ID'; u.rate=0.95; u.voice=v;
                window.speechSynthesis.speak(u);
            }} catch(e) {{}}
        }}
        function localSpeak(){{
            let v=idVoice(); if(v){{ go(v); return; }}
            let n=0; const t=setInterval(()=>{{ v=idVoice(); n++; if(v||n>15){{ clearInterval(t); go(v); }} }}, 120);
        }}
        function play(){{
            // 1순위: 부모 엔진(잠금 해제돼 있으면 탭 없이도 재생) → 실패 시 이 프레임에서 직접
            try {{ if (window.parent && window.parent.playIndo) {{ window.parent.playIndo(WORD); return; }} }} catch(e) {{}}
            localSpeak();
        }}
        document.getElementById('spk').onclick = play;
        setTimeout(play, 200);   // 잠금 해제돼 있으면 자동 재생
        </script>
        """,
        height=54,
    )


# ---------------------------------------------------------------------------
# 퀴즈 — 셋업 / 플래시카드
# ---------------------------------------------------------------------------

def render_quiz_setup():
    uid = st.session_state.user_id
    stats = db.get_stats(uid)
    st.markdown(f"<div class='prog'>오늘 복습 대기 단어 <b>{stats['due']}</b>개</div>", unsafe_allow_html=True)

    if stats["total"] == 0:
        st.info("아직 단어가 없어요. [➕ 단어 추가] 탭에서 텍스트를 붙여넣어 주세요.")
        return

    mode = st.radio(
        "복습 범위",
        ["🎲 전체 랜덤 복습", "🏷️ 특정 #태그 골라서 복습"],
        label_visibility="collapsed",
    )
    tag = None
    if mode.startswith("🏷️"):
        tags = db.get_all_tags(uid)
        if tags:
            tag = st.selectbox("태그 선택", tags)
        else:
            st.caption("등록된 태그가 없습니다. #태그가 포함된 단어를 추가해 보세요.")

    if st.button("▶️ 복습 시작", use_container_width=True, type="primary"):
        rows = db.get_due_words(uid, tag)
        if not rows:
            st.warning("복습할 단어가 없어요! 내일 다시 만나요 🎉")
            return
        queue = [dict(r) for r in rows]
        random.shuffle(queue)
        st.session_state.quiz_queue = queue
        st.session_state.quiz_idx = 0
        st.session_state.quiz_active = True
        reset_card_state(queue[0]["word"])
        st.rerun()


def _advance(known: bool):
    """채점 반영 후 다음 카드로."""
    ss = st.session_state
    card = ss.quiz_queue[ss.quiz_idx]
    db.apply_review_result(card["id"], known)
    ss.quiz_idx += 1
    if ss.quiz_idx < len(ss.quiz_queue):
        reset_card_state(ss.quiz_queue[ss.quiz_idx]["word"])
    st.rerun()


def render_flashcard():
    ss = st.session_state
    total = len(ss.quiz_queue)

    # 완료 화면
    if ss.quiz_idx >= total:
        st.success(f"🎉 오늘의 복습 {total}개 완료!")
        if st.button("🏠 처음으로", use_container_width=True, type="primary"):
            ss.quiz_active = False
            st.rerun()
        return

    card = ss.quiz_queue[ss.quiz_idx]
    cs = ss.card
    word = card["word"]

    st.markdown(f"<div class='prog'>{ss.quiz_idx + 1} / {total}</div>", unsafe_allow_html=True)

    # 문제: 뜻을 보여주고 인니어 단어를 떠올리게 함
    st.markdown(f"<div class='meaning-box'>{card['meaning'] or '(뜻 없음)'}</div>", unsafe_allow_html=True)

    # 가변 글자 수 마스킹
    st.markdown(f"<div class='mask-box'>{render_mask(word, cs['positions'])}</div>", unsafe_allow_html=True)

    if not cs["revealed"]:
        # 중단 조작부: 좌(힌트) / 우(음성) 한 줄 좌우 나란히
        left, right = st.columns([1, 1])
        with left:
            remaining = cs["max_hints"] - cs["hints_used"]
            disabled = remaining <= 0
            if st.button(
                f"💡 스펠링 힌트 (남은 횟수: {remaining}회)",
                use_container_width=True,
                disabled=disabled,
                key=f"hint_{ss.quiz_idx}",
            ):
                _apply_hint(word, cs)
                st.rerun()
        with right:
            speech_component(word)

        # 타이핑 입력창 + 가로 꽉 찬 정답 확인 버튼
        st.text_input("정답 입력", key=f"typed_{ss.quiz_idx}",
                      placeholder="머릿속 답을 입력해도 좋아요", label_visibility="collapsed")
        if st.button("👁️ 정답 확인하기", use_container_width=True, type="primary",
                     key=f"reveal_{ss.quiz_idx}"):
            cs["revealed"] = True
            st.rerun()
    else:
        # 정답 공개 + 자기주도 채점
        st.markdown(
            f"<div class='answer-box'><div class='answer-word'>{word}</div>"
            f"<div class='answer-pron'>{card['pronunciation']}</div></div>",
            unsafe_allow_html=True,
        )
        # 정답 단어를 인도네시아어 음성으로 자동 재생 (+ 다시 듣기 버튼)
        tts_component(word)
        if card["examples"]:
            st.markdown(f"<div class='examples-box'>{card['examples']}</div>", unsafe_allow_html=True)
        if card["tags"]:
            st.caption(card["tags"])

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("👎 헷갈려요", use_container_width=True, key=f"bad_{ss.quiz_idx}"):
                _advance(known=False)
        with c2:
            if st.button("👍 알아요", use_container_width=True, type="primary", key=f"ok_{ss.quiz_idx}"):
                _advance(known=True)


def _apply_hint(word: str, cs: dict):
    """1차: 첫 글자 / 2차: 첫 글자 제외 빈칸 중 랜덤 1개."""
    if cs["hints_used"] == 0:
        first = next((i for i, ch in enumerate(word) if ch != " "), 0)
        cs["positions"].add(first)
    elif cs["hints_used"] == 1 and cs["max_hints"] >= 2:
        candidates = [
            i for i, ch in enumerate(word)
            if ch != " " and i not in cs["positions"]
        ]
        if candidates:
            cs["positions"].add(random.choice(candidates))
    cs["hints_used"] += 1


# ---------------------------------------------------------------------------
# 단어 추가 / 통계
# ---------------------------------------------------------------------------

def render_add():
    uid = st.session_state.user_id
    st.caption("단어끼리 **빈 줄 1칸**으로 구분 · 첫 줄=단어(`단어=뜻` 또는 `단어→뜻`) · 둘째 줄부터=예문")
    text = st.text_area(
        "붙여넣기", height=220, label_visibility="collapsed",
        placeholder=(
            "Meledak(믈르닥) = 터지다  #일상회화\n"
            "Bom meledak = 폭탄이 터지다\n"
            "\n"
            "produsen = 생산자, 제조사\n"
            "\n"
            "Tindakan → action  @sikap\n"
            "Harus dibuktikan dengan tindakan.\n"
            "→ 행동으로 보여줘야 해요"
        ),
    )
    if st.button("🧠 분석 후 저장", use_container_width=True, type="primary"):
        entries = vp.parse(text)
        if not entries:
            st.warning("인식된 단어가 없어요. '단어 = 뜻' 형식이 포함됐는지 확인해 주세요.")
        else:
            added, skipped = db.add_vocab_bulk(uid, entries)
            st.session_state.add_result = {
                "added": added,
                "skipped": skipped,
                "count": len(entries),
                "preview": entries[:30],
            }
            # 다른 탭(오늘의 복습/통계)의 집계가 즉시 갱신되도록 전체 새로고침
            st.rerun()

    # 직전 저장 결과 표시 (rerun 후에도 유지)
    res = st.session_state.get("add_result")
    if res:
        st.success(
            f"✅ {res['added']}개 추가 완료"
            + (f" · {res['skipped']}개 중복 건너뜀" if res["skipped"] else "")
        )
        with st.expander(f"파싱 미리보기 ({res['count']}개 인식)"):
            for e in res["preview"]:
                pron = f" ({e['pronunciation']})" if e["pronunciation"] else ""
                st.markdown(f"**{e['word']}**{pron} = {e['meaning']}  \n`{e['tags']}`")


def render_stats():
    stats = db.get_stats(st.session_state.user_id)
    c1, c2 = st.columns(2)
    c1.metric("전체 단어", stats["total"])
    c2.metric("오늘 복습 대기", stats["due"])
    st.markdown("##### 라이트너 단계 분포")
    by_level = stats["by_level"]
    for lv in range(1, db.MAX_LEVEL + 1):
        cnt = by_level.get(lv, 0)
        bar = "▰" * min(cnt, 20)
        st.markdown(f"Lv.{lv} `{cnt:>3}` {bar}")


# ---------------------------------------------------------------------------
# 라우팅
# ---------------------------------------------------------------------------

def main():
    init_state()
    inject_mobile_css()
    inject_pwa()
    inject_inapp_browser_warning()  # 카톡 등 인앱 브라우저면 '크롬/사파리로 열기' 안내
    inject_audio_engine()  # 한 번 잠금 해제하면 세션 내내 발음 자동재생

    # 자동 로그인: 설정된 계정이 있고, 이 세션에서 수동 로그아웃하지 않았다면 로그인 화면을 건너뜀
    if not st.session_state.user_id and not st.session_state._logged_out:
        au = _autologin_user()
        if au:
            user = auth.ensure_user(au)
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]

    if not st.session_state.user_id:
        render_auth()
        return

    # 상단 바: 인사 + 로그아웃 (컴팩트)
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.markdown(f"<div class='topbar'>👋 {st.session_state.username}님</div>",
                    unsafe_allow_html=True)
    with top_r:
        if st.button("로그아웃", use_container_width=True):
            for k in ("user_id", "username", "quiz_active", "quiz_queue", "quiz_idx", "card", "add_result"):
                st.session_state.pop(k, None)
            st.session_state._logged_out = True  # 자동 로그인 일시 해제 → 로그인 화면 표시
            st.rerun()

    tab_quiz, tab_add, tab_stats = st.tabs(["📚 오늘의 복습", "➕ 단어 추가", "📊 통계"])
    with tab_quiz:
        if st.session_state.quiz_active:
            render_flashcard()
        else:
            render_quiz_setup()
    with tab_add:
        render_add()
    with tab_stats:
        render_stats()


if __name__ == "__main__":
    main()
