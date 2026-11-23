"""이 PC에서 브라우저 창을 띄워 인스타그램에 카드뉴스를 하루 한 번 올립니다.

    python -m src.web_upload           # 오늘 아직 안 올렸으면, 안 올린 가장 오래된 Vol을 게시
    python -m src.web_upload 5         # Vol.05를 게시 (오늘 이미 올렸어도)
    python -m src.web_upload --force   # 오늘 이미 올렸어도 다음 Vol 게시

Windows 작업 스케줄러가 매일 20:00에 upload_instagram.bat 를 실행합니다.
PC가 꺼져 있었다면 켜진 뒤 실행됩니다. 로그인이 안 돼 있으면 창에서 로그인할 때까지 기다립니다.
로그인 정보는 전용 브라우저 프로필(%LOCALAPPDATA%\\cardnews_ig\\profile)에 저장됩니다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from . import main as cn

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "cardnews_ig"
PROFILE = HOME / "profile"
STATE = HOME / "state.json"          # {"last_date": "YYYY-MM-DD", "last_vol": N}
LOG = HOME / "upload.log"
LOGIN_WAIT_MIN = 60                   # 로그인 기다리는 최대 시간(분)


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    HOME.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def git(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GH_CONFIG_DIR=str(Path.home() / ".gh-personal"))
    return subprocess.run(["git", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def rx(*words: str) -> re.Pattern:
    return re.compile("^(" + "|".join(re.escape(w) for w in words) + ")$")


def click_if_visible(page: Page, pattern: re.Pattern, timeout: int = 1500) -> bool:
    btn = page.get_by_role("button", name=pattern).first
    try:
        btn.wait_for(state="visible", timeout=timeout)
        btn.click()
        return True
    except Exception:
        return False


def logged_in(page: Page) -> bool:
    return page.locator('svg[aria-label="새로운 게시물"], svg[aria-label="New post"]').count() > 0


def wait_for_login(page: Page) -> None:
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if logged_in(page):
        return
    log(f"인스타그램 로그인이 필요합니다. 열린 창에서 로그인해 주세요 (최대 {LOGIN_WAIT_MIN}분 기다림).")
    deadline = time.time() + LOGIN_WAIT_MIN * 60
    while time.time() < deadline:
        page.wait_for_timeout(3000)
        click_if_visible(page, rx("나중에 하기", "Not now", "Not Now"), 500)
        if logged_in(page):
            log("로그인 확인됨.")
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            return
    raise RuntimeError("로그인 대기 시간이 지났습니다.")


def paste_caption(page: Page, text: str) -> None:
    box = page.locator('div[role="dialog"] div[contenteditable="true"]').first
    box.wait_for(state="visible", timeout=20000)
    box.click()
    # 인스타 캡션 입력칸(Lexical)은 붙여넣기 이벤트로 넣어야 줄바꿈이 그대로 들어갑니다.
    box.evaluate(
        """(el, text) => { el.focus(); const dt = new DataTransfer(); dt.setData('text/plain', text);
             el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""",
        text,
    )
    page.wait_for_timeout(1000)
    if len(box.inner_text().strip()) < 10:
        log("붙여넣기가 안 돼서 직접 입력합니다.")
        box.click()
        page.keyboard.insert_text(text)
        page.wait_for_timeout(1000)


def open_post_dialog(page: Page) -> None:
    """'새로운 게시물' 창을 열고, 여러 장을 받는 파일 입력칸이 생길 때까지 기다립니다."""
    multi = page.locator('input[type="file"][multiple]')
    for attempt in range(3):
        if attempt:
            log(f"게시물 창이 안 열려서 다시 시도합니다 ({attempt + 1}/3)")
            page.keyboard.press("Escape")
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
        for _ in range(3):
            click_if_visible(page, rx("나중에 하기", "Not now", "Not Now"), 800)
        page.locator('svg[aria-label="새로운 게시물"], svg[aria-label="New post"]').first.click()
        page.wait_for_timeout(1500)
        if multi.count() == 0:
            # 메뉴(게시물 / AI)가 뜨는 경우 '게시물' 선택.
            # 페이지 이동 링크(프로필의 '게시물' 탭 등)는 누르지 않도록 실제 주소가 있는 a 는 제외합니다.
            sub = page.locator('a[href="#"], a:not([href]), div[role="button"], div[role="menuitem"], span') \
                .filter(has_text=rx("게시물", "Post")).first
            try:
                if sub.is_visible(timeout=1500):
                    sub.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass
        try:
            multi.first.wait_for(state="attached", timeout=10000)
            return
        except Exception:
            continue
    raise RuntimeError("게시물 만들기 창(여러 장 업로드 칸)을 찾지 못했습니다.")


def post(page: Page, files: list[Path], cap: str) -> None:
    open_post_dialog(page)
    page.locator('input[type="file"][multiple]').first.set_input_files([str(f) for f in files])
    log(f"이미지 {len(files)}장 선택")
    crop = page.locator('svg[aria-label="자르기 선택"], svg[aria-label="Select crop"]').first
    crop.wait_for(state="visible", timeout=60000)
    crop.click()
    page.wait_for_timeout(800)
    page.get_by_text("4:5", exact=True).first.click()
    page.wait_for_timeout(800)
    for step in ("자르기", "편집"):
        page.get_by_role("button", name=rx("다음", "Next")).first.click()
        log(f"{step} 단계 다음")
        page.wait_for_timeout(2500)
    paste_caption(page, cap)
    log("캡션 입력 완료, 공유합니다.")
    page.get_by_role("button", name=rx("공유하기", "Share")).first.click()
    page.get_by_text(re.compile("게시물이 공유되었습니다|Your post has been shared|공유되었습니다")).first.wait_for(
        timeout=300000)
    page.wait_for_timeout(2000)


def record_published(vol: int) -> None:
    pub = sorted(set(cn._published()) | {vol})
    cn.PUBLISHED.write_text(json.dumps(pub), encoding="utf-8")
    # 게시한 Vol까지 상품 링크가 보이도록 링크 페이지를 다시 만듭니다 (push되면 pages.yml이 배포).
    cn.linkpage.build(json.loads(cn.linkpage.POSTS.read_text(encoding="utf-8")))
    files = ["data/published.json", "docs/index.html"]
    git("add", *files)
    r = git("commit", "-m", f"Vol.{vol:02d} 인스타 게시 기록 + 링크 페이지 갱신 (PC 업로드)", "--", *files)
    if r.returncode == 0:
        p1 = git("pull", "--rebase", "--autostash", "origin", "main")
        p2 = git("push", "origin", "main")
        log("GitHub에 게시 기록 push " + ("완료" if p2.returncode == 0 else f"실패: {p1.stderr[-300:]} {p2.stderr[-300:]}"))


def run(vol: int | None, force: bool) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    state = load_state()
    if vol is None and not force and state.get("last_date") == today:
        log(f"오늘은 이미 Vol.{state.get('last_vol', 0):02d}을 올렸습니다. 건너뜁니다.")
        return
    r = git("pull", "--ff-only", "origin", "main")
    log("최신 카드 받기 " + ("완료" if r.returncode == 0 else f"실패(로컬 그대로 진행): {r.stderr.strip()[-200:]}"))
    if vol is None:
        queue = cn.unposted_vols()
        if not queue:
            log("올릴 카드가 없습니다.")
            return
        vol = queue[0]
    card_dir = ROOT / "docs" / "cards" / f"vol-{vol:02d}"
    files = sorted(card_dir.glob("*.jpg"))
    if not files:
        raise RuntimeError(f"Vol.{vol:02d} 카드 이미지가 없습니다: {card_dir}")
    cap = (card_dir / "caption.txt").read_text(encoding="utf-8")
    log(f"Vol.{vol:02d} 게시 시작 ({len(files)}장)")

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        kw = dict(headless=False, viewport={"width": 1280, "height": 900}, locale="ko-KR",
                  args=["--disable-blink-features=AutomationControlled"])
        try:
            ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", **kw)
        except Exception:
            ctx = p.chromium.launch_persistent_context(str(PROFILE), **kw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            wait_for_login(page)
            post(page, files, cap)
        except Exception:
            shot = HOME / f"error_{datetime.now():%Y%m%d_%H%M%S}.png"
            try:
                page.screenshot(path=str(shot))
                log(f"오류 화면 저장: {shot}")
            except Exception:
                pass
            raise
        finally:
            ctx.close()

    STATE.write_text(json.dumps({"last_date": today, "last_vol": vol}), encoding="utf-8")
    log(f"Vol.{vol:02d} 인스타 게시 완료")
    record_published(vol)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        run(int(args[0]) if args else None, force="--force" in sys.argv)
    except Exception as e:
        log(f"실패: {e!r}")
        sys.exit(1)
