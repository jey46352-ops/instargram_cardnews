"""카드뉴스 7장(표지 1 + 상품 5 + 마무리 1)을 1080×1350 JPEG로 렌더링합니다.
디자인 규칙: 여백 80px, 태그 32px Bold, 서브 48px Medium, 제목 136px Black, 하단 30px."""
import html
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

W, H = 1080, 1350
BG = "#121212"
FG = "#FFFFFF"
MUTED = "#BDBDBD"
ACCENT = os.environ.get("CARD_ACCENT", "#FFD43B")
FONT_CSS = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
FONT_STACK = "'Pretendard', 'Noto Sans CJK KR', 'Noto Sans KR', sans-serif"
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

ARROW = (
    '<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>'
)

BASE_CSS = f"""
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; width: {W}px; height: {H}px; }}
body {{ background: {BG}; color: {FG}; font-family: {FONT_STACK}; }}
.card {{ width: {W}px; height: {H}px; padding: 80px; display: flex; flex-direction: column; justify-content: space-between; }}
.top {{ display: flex; justify-content: space-between; align-items: center; }}
.tag {{ padding: 12px 28px; border-radius: 999px; background: {ACCENT}; color: #121212; font-size: 32px; font-weight: 700; letter-spacing: -0.02em; }}
.vol {{ font-size: 32px; font-weight: 500; color: {MUTED}; }}
.sub {{ margin: 0; font-size: 48px; font-weight: 500; line-height: 1.3; letter-spacing: -0.03em; color: #E0E0E0; }}
.fitline {{ display: block; white-space: nowrap; }}
.title {{ margin: 0; font-size: 136px; font-weight: 900; line-height: 1.15; letter-spacing: -0.04em; }}
.accent {{ color: {ACCENT}; }}
.rule {{ height: 2px; background: #3A3A3A; margin-bottom: 28px; }}
.bottom {{ display: flex; justify-content: space-between; align-items: center; font-size: 30px; }}
.handle {{ font-weight: 500; color: {MUTED}; }}
.swipe {{ display: flex; align-items: center; gap: 12px; font-weight: 700; }}
.num {{ font-size: 96px; font-weight: 900; color: {ACCENT}; letter-spacing: -0.04em; line-height: 1; }}
.of {{ font-size: 36px; font-weight: 500; color: {MUTED}; margin-left: 8px; }}
.photo {{ height: 600px; border-radius: 32px; background: #FFFFFF; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
.photo img {{ max-width: 88%; max-height: 88%; object-fit: contain; }}
.photo .ph {{ color: #777; font-size: 32px; }}
.name {{ margin: 0; font-size: 72px; font-weight: 900; letter-spacing: -0.04em; line-height: 1.2; }}
.tip {{ margin: 16px 0 0; font-size: 42px; font-weight: 500; line-height: 1.4; letter-spacing: -0.03em; color: #E0E0E0; }}
.small {{ font-size: 24px; color: {MUTED}; line-height: 1.5; }}
.cta {{ margin: 0; font-size: 96px; font-weight: 900; line-height: 1.2; letter-spacing: -0.04em; }}
.steps {{ display: flex; flex-direction: column; gap: 24px; font-size: 44px; font-weight: 700; letter-spacing: -0.03em; }}
.steps span {{ color: {ACCENT}; margin-right: 16px; }}
"""


# 제목이 한 줄 폭(920px)을 넘으면 글자 크기를 4px씩 줄여 맞춥니다.
FIT_JS = """
document.querySelectorAll('.fitline').forEach(el => {
  const box = el.closest('.card').clientWidth - 160;
  let size = parseFloat(getComputedStyle(el.parentElement).fontSize);
  while (el.scrollWidth > box && size > 40) { size -= 4; el.style.fontSize = size + 'px'; }
});
"""


def _e(s) -> str:
    return html.escape(str(s or ""))


def _page(body: str) -> str:
    return (
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f'<link rel="stylesheet" href="{FONT_CSS}"><style>{BASE_CSS}</style></head>'
        f"<body>{body}</body></html>"
    )


def _bottom(handle: str, right: str) -> str:
    return (
        f'<div><div class="rule"></div><div class="bottom"><span class="handle">{_e(handle)}</span>'
        f'<span class="swipe">{right}</span></div></div>'
    )


def cover(topic: dict, handle: str) -> str:
    return _page(
        f'<div class="card">'
        f'<div class="top"><span class="tag">{_e(topic["category"])}</span><span class="vol">Vol.{topic["vol"]:02d}</span></div>'
        f'<div style="display:flex;flex-direction:column;gap:32px">'
        f'<p class="sub">{_e(topic["sub"])}</p>'
        f'<h1 class="title"><span class="fitline">{_e(topic["title1"])}</span><span class="fitline accent">{_e(topic["title2"])}</span></h1></div>'
        f'{_bottom(handle, "옆으로 넘기기 " + ARROW)}</div>'
    )


def item(topic: dict, idx: int, it: dict, product: dict | None, handle: str) -> str:
    img = (
        f'<img src="{_e(product["productImage"])}" alt="">'
        if product and product.get("productImage")
        else '<span class="ph">[상품 이미지]</span>'
    )
    return _page(
        f'<div class="card">'
        f'<div class="top"><div><span class="num">{idx:02d}</span><span class="of">/ 05</span></div>'
        f'<span class="vol">{_e(topic["title1"])}</span></div>'
        f'<div class="photo">{img}</div>'
        f'<div><h2 class="name"><span class="fitline">{_e(it["name"])}</span></h2><p class="tip">{_e(it["tip"])}</p></div>'
        f'{_bottom(handle, "구매 링크는 프로필 링크 No." + str(idx))}</div>'
    )


def outro(topic: dict, handle: str) -> str:
    return _page(
        f'<div class="card">'
        f'<div class="top"><span class="tag">{_e(topic["category"])}</span><span class="vol">Vol.{topic["vol"]:02d}</span></div>'
        f'<div style="display:flex;flex-direction:column;gap:56px">'
        f'<h2 class="cta">떠나기 전에<br><span class="accent">저장해 두세요</span></h2>'
        f'<div class="steps"><div><span>01</span>저장해 두고 짐 쌀 때 꺼내보기</div>'
        f'<div><span>02</span>제품 링크는 프로필 링크에서</div>'
        f'<div><span>03</span>매일 새 {_e(topic["category"])} 꿀템, 팔로우</div></div></div>'
        f'<div><div class="rule"></div><p class="small" style="margin:0 0 16px">{DISCLOSURE}</p>'
        f'<div class="bottom"><span class="handle">{_e(handle)}</span><span class="swipe">Vol.{topic["vol"]:02d}</span></div></div></div>'
    )


def render_all(topic: dict, products: list[dict | None], out_dir: Path) -> list[Path]:
    handle = os.environ.get("IG_HANDLE", "@your_account")
    pages = [cover(topic, handle)]
    pages += [item(topic, i + 1, it, products[i], handle) for i, it in enumerate(topic["items"])]
    pages.append(outro(topic, handle))

    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for n, doc in enumerate(pages, start=1):
            page.set_content(doc, wait_until="networkidle", timeout=60000)
            page.evaluate("document.fonts.ready")
            page.evaluate(FIT_JS)
            path = out_dir / f"{n:02d}.jpg"
            # 인스타그램 Graph API는 JPEG만 받습니다.
            page.screenshot(path=str(path), type="jpeg", quality=92, full_page=False)
            files.append(path)
        browser.close()
    return files
