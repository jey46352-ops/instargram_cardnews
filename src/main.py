"""사용법
  python -m src.main generate          # 주제 선정 → 쿠팡 검색 → 카드 렌더 → 링크 페이지 갱신
  python -m src.main generate --mock   # 쿠팡 API 없이 디자인만 확인
  python -m src.main publish           # 만들어 둔 카드를 인스타그램에 게시
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import linkpage, render, topics

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / "data" / "pending.json"
KST = timezone(timedelta(hours=9))

HASHTAGS = {
    "여행": "#여행준비물 #여행꿀팁 #해외여행준비 #여행필수템 #여행가방싸기 #국내여행 #여행템 #여행스타그램",
    "숙소": "#호캉스 #숙소추천 #호텔꿀팁 #여행준비물 #숙소필수템 #에어비앤비 #여행꿀템 #호캉스준비물",
    "캠핑": "#캠핑용품 #캠핑필수템 #캠핑초보 #캠핑꿀템 #차박 #캠핑장비 #캠핑스타그램 #감성캠핑",
}


def caption(topic: dict) -> str:
    lines = [f'{topic["sub"]} {topic["title1"]} {topic["title2"]}', ""]
    for n, it in enumerate(topic["items"], start=1):
        lines.append(f'{n}. {it["name"]} — {it["tip"]}')
    lines += [
        "",
        f'제품 링크는 프로필 링크 → Vol.{topic["vol"]:02d}에 번호 순서대로 있어요.',
        "도움이 됐다면 저장하고, 같이 갈 사람에게 공유해 주세요.",
        "",
        render.DISCLOSURE,
        "",
        HASHTAGS.get(topic["category"], ""),
    ]
    return "\n".join(lines)[:2200]


def _mock_products(topic: dict) -> list[dict]:
    return [
        {"keyword": it["keyword"], "productName": f'[목업] {it["keyword"]}', "productImage": None, "productUrl": None}
        for it in topic["items"]
    ]


def generate(mock: bool = False) -> None:
    topic, state = topics.next_topic()
    print(f'[generate] Vol.{topic["vol"]:02d} {topic["category"]} · {topic["title1"]} {topic["title2"]}')

    if mock:
        products = _mock_products(topic)
    else:
        from .coupang import pick_products

        products = pick_products([it["keyword"] for it in topic["items"]])
        found = sum(1 for p in products if p)
        print(f"[generate] 쿠팡 상품 {found}/5개 찾음")
        if found < 3:
            sys.exit("상품을 3개 이상 찾지 못해 오늘은 건너뜁니다 (state는 저장하지 않음).")

    out_dir = linkpage.DOCS / "cards" / f'vol-{topic["vol"]:02d}'
    files = render.render_all(topic, products, out_dir)
    cap = caption(topic)
    (out_dir / "caption.txt").write_text(cap, encoding="utf-8")

    date = datetime.now(KST).strftime("%Y-%m-%d")
    linkpage.add_post(topic, products, date)
    PENDING.write_text(
        json.dumps(
            {"vol": topic["vol"], "files": [str(f.relative_to(linkpage.DOCS)) for f in files], "caption": cap},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    topics.save_state(state)
    print(f"[generate] 카드 {len(files)}장 → {out_dir.relative_to(ROOT)}")


def _pages_base() -> str:
    base = os.environ.get("PAGES_BASE_URL")
    if base:
        return base.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        sys.exit("PAGES_BASE_URL 또는 GITHUB_REPOSITORY가 필요합니다.")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def publish() -> None:
    from . import instagram

    if not PENDING.exists():
        print("[publish] 게시할 카드가 없습니다.")
        return
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    base = _pages_base()
    urls = [f"{base}/{f}" for f in pending["files"]]
    instagram.wait_until_public(urls)
    media_id = instagram.publish_carousel(urls, pending["caption"])
    print(f'[publish] Vol.{pending["vol"]:02d} 게시 완료 (media id {media_id})')
    PENDING.unlink()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        generate(mock="--mock" in sys.argv)
    elif cmd == "publish":
        publish()
    else:
        print(__doc__)
        sys.exit(1)
