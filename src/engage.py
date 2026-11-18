"""비슷한 주제 계정 찾기 + 좋아요·팔로우는 직접 누르는 반자동 도우미 (하루 1회).

    python -m src.engage            # 오늘 아직 안 했으면 후보 계정 7~12개를 차례로 띄움
    python -m src.engage --force    # 오늘 이미 했어도 다시

후보 찾기(해시태그 검색, 계정 정보 확인)만 자동으로 하고, 좋아요와 팔로우 클릭은 사람이 직접 합니다.
인스타그램 약관상 자동 좋아요·팔로우는 계정 제한 위험이 있어 이 스크립트는 절대 클릭하지 않습니다.
화면 오른쪽 아래 패널의 [다음] / [건너뛰기] / [그만하기] 로 진행합니다.
기록: %LOCALAPPDATA%\\cardnews_ig\\engage.json
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime
from urllib.parse import quote

from playwright.sync_api import Page, sync_playwright

from .web_upload import HOME, PROFILE, log

MY_HANDLE = "shashasha_0708"
RECORD = HOME / "engage.json"   # {"last_date": "...", "accounts": {"user": {"date":..., "status": "done|skip|filtered", "followers": N}}}
TARGET_MIN, TARGET_MAX = 7, 12
FOLLOWERS_MIN, FOLLOWERS_MAX = 300, 50_000   # 맞팔 가능성이 높은 작은~중간 계정
TAGS = [
    "캠핑준비물", "캠핑꿀템", "캠핑초보", "감성캠핑", "차박",
    "여행준비물", "여행꿀팁", "여행필수템", "짐싸기", "해외여행준비",
    "호캉스", "숙소추천", "호텔추천", "여행정보", "카드뉴스",
]


def load() -> dict:
    try:
        return json.loads(RECORD.read_text(encoding="utf-8"))
    except Exception:
        return {"accounts": {}}


def save(rec: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")


def pause(a: float = 2.0, b: float = 4.5) -> None:
    time.sleep(random.uniform(a, b))


def parse_count(s: str) -> int | None:
    s = s.replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([만천KkMm]?)", s)
    if not m:
        return None
    n = float(m.group(1))
    mult = {"만": 10_000, "천": 1_000, "K": 1_000, "k": 1_000, "M": 1_000_000, "m": 1_000_000}.get(m.group(2), 1)
    return int(n * mult)


def followers_of(page: Page, user: str) -> tuple[int | None, bool]:
    """(팔로워 수, 비공개 여부)"""
    page.goto(f"https://www.instagram.com/{user}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    desc = ""
    for sel in ('meta[property="og:description"]', 'meta[name="description"]'):
        if page.locator(sel).count():
            desc = page.locator(sel).first.get_attribute("content") or ""
            break
    m = re.search(r"팔로워\s*([\d.,]+\s*[만천KkMm]?)", desc) or re.search(r"([\d.,]+\s*[KkMm]?)\s*Followers", desc)
    private = page.get_by_text(re.compile("비공개 계정입니다|This account is private")).count() > 0
    return (parse_count(m.group(1)) if m else None), private


def already_following(page: Page) -> bool:
    return page.get_by_role("button", name=re.compile("^(팔로잉|Following|요청됨|Requested)")).count() > 0


def find_candidates(page: Page, rec: dict, want: int) -> list[tuple[str, str, int]]:
    """[(user, 해시태그에서 찾은 게시물 경로, 팔로워 수)]"""
    seen = set(rec["accounts"]) | {MY_HANDLE}
    out: list[tuple[str, str]] = []
    tags = random.sample(TAGS, len(TAGS))
    for tag in tags:
        if len(out) >= want:
            break
        page.goto("https://www.instagram.com/explore/tags/" + quote(tag) + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        posts = []
        for a in page.locator('a[href*="/p/"]').all():
            h = a.get_attribute("href")
            if h and h not in posts:
                posts.append(h)
        log(f"#{tag}: 게시물 {len(posts)}개")
        for h in posts[:8]:
            if len(out) >= want:
                break
            page.goto("https://www.instagram.com" + h, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            show_status(page, f"후보 계정 찾는 중… {len(out)}/{want}<br>창을 닫지 말고 기다려 주세요.<br>다 찾으면 이 자리에 [다음] 버튼이 나와요.")
            og = page.locator('meta[property="og:url"]')
            url = og.first.get_attribute("content") if og.count() else ""
            m = re.match(r"https://www\.instagram\.com/([^/]+)/p/", url or "")
            if not m:
                continue
            user = m.group(1)
            if user in seen:
                continue
            seen.add(user)
            pause(1, 2.5)
            n, private = followers_of(page, user)
            show_status(page, f"후보 계정 찾는 중… {len(out)}/{want}<br>창을 닫지 말고 기다려 주세요.")
            ok = (not private and n is not None and FOLLOWERS_MIN <= n <= FOLLOWERS_MAX
                  and not already_following(page))
            log(f"  @{user}: 팔로워 {n}, 비공개 {private} → {'후보' if ok else '제외'}")
            if ok:
                out.append((user, h, n))
            else:
                rec["accounts"][user] = {"date": datetime.now().strftime("%Y-%m-%d"), "status": "filtered", "followers": n}
            pause()
    return out


def show_status(page: Page, html: str) -> None:
    try:
        page.evaluate("""(h) => { let d = document.getElementById('__engage_wait');
          if (!d) { d = document.createElement('div'); d.id = '__engage_wait';
            d.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;background:#111;color:#fff;padding:14px 16px;border-radius:14px;font:14px/1.5 sans-serif;width:260px;box-shadow:0 6px 24px rgba(0,0,0,.35)';
            document.body.appendChild(d); }
          d.innerHTML = '<b>맞팔 도우미</b><br>' + h; }""", html)
    except Exception:
        pass


PANEL_JS = """([i, total, user, n]) => {
  if (document.getElementById('__engage')) return;
  const d = document.createElement('div'); d.id = '__engage';
  d.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483647;background:#111;color:#fff;padding:14px 16px;border-radius:14px;font:14px sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.35);width:260px';
  d.innerHTML = `<div style="font-weight:700;margin-bottom:6px">맞팔 도우미 ${i}/${total}</div>
    <div style="margin-bottom:4px">@${user} · 팔로워 ${n.toLocaleString()}</div>
    <div style="opacity:.8;margin-bottom:10px;line-height:1.4">❤️ 좋아요와 <b>팔로우</b>를 직접 누른 뒤 [다음]</div>
    <div style="display:flex;gap:6px">
      <button data-a="done" style="flex:1;padding:8px;border:0;border-radius:8px;background:#0095f6;color:#fff;font-weight:700;cursor:pointer">다음 ▶</button>
      <button data-a="skip" style="padding:8px;border:0;border-radius:8px;background:#444;color:#fff;cursor:pointer">건너뛰기</button>
      <button data-a="stop" style="padding:8px;border:0;border-radius:8px;background:#444;color:#fff;cursor:pointer">그만</button>
    </div>`;
  d.querySelectorAll('button').forEach(b => b.onclick = () => { window.__engageAction = b.dataset.a; });
  document.body.appendChild(d);
}"""


def wait_action(page: Page, i: int, total: int, user: str, n: int) -> str:
    page.evaluate("() => { window.__engageAction = null; }")
    while True:
        try:
            page.evaluate(PANEL_JS, [i, total, user, n])
            a = page.evaluate("() => window.__engageAction")
            if a:
                return a
        except Exception:
            pass  # 페이지 이동 중
        if page.is_closed():
            return "stop"
        page.wait_for_timeout(500)


def run(force: bool) -> None:
    rec = load()
    today = datetime.now().strftime("%Y-%m-%d")
    if not force and rec.get("last_date") == today:
        log("맞팔 도우미: 오늘은 이미 했습니다.")
        return
    want = random.randint(TARGET_MIN, TARGET_MAX)
    with sync_playwright() as p:
        kw = dict(headless=False, viewport={"width": 1280, "height": 900}, locale="ko-KR",
                  args=["--disable-blink-features=AutomationControlled"])
        try:
            ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", **kw)
        except Exception:
            ctx = p.chromium.launch_persistent_context(str(PROFILE), **kw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            log(f"맞팔 도우미: 후보 {want}개 찾는 중...")
            cands = find_candidates(page, rec, want)
            save(rec)
            log(f"후보 {len(cands)}개. 창에서 좋아요·팔로우를 직접 눌러 주세요.")
            done = 0
            for i, (user, post, n) in enumerate(cands, start=1):
                page.goto("https://www.instagram.com" + post, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                a = wait_action(page, i, len(cands), user, n)
                if a == "stop":
                    log("그만하기 선택.")
                    break
                rec["accounts"][user] = {"date": today, "status": "done" if a == "done" else "skip", "followers": n}
                done += a == "done"
                save(rec)
            rec["last_date"] = today
            save(rec)
            log(f"맞팔 도우미 끝: {done}개 완료")
        except Exception as e:
            save(rec)
            if "closed" in repr(e).lower():
                log("창이 닫혀서 맞팔 도우미를 끝냅니다.")
                return
            raise
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        run(force="--force" in sys.argv)
    except Exception as e:
        log(f"맞팔 도우미 실패: {e!r}")
        sys.exit(1)
