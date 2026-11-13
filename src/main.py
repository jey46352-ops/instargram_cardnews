"""사용법
  python -m src.main generate          # 주제 선정 → 쿠팡 검색 → 카드 렌더 → 링크 페이지 갱신
  python -m src.main generate --mock   # 쿠팡 API 없이 디자인만 확인
  python -m src.main publish           # 아직 안 올린 가장 오래된 Vol을 인스타그램에 게시
  python -m src.main publish 3         # Vol.03을 지정해서 게시
  python -m src.main adfree 2 3        # Vol.02, 03을 광고 없는 정보형으로 다시 만들기 (adon 은 되돌리기)
  광고 없는 기간은 data/adfree.json {"until": "YYYY-MM-DD"} 로 정합니다.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import linkpage, photos, render, topics

ROOT = Path(__file__).resolve().parent.parent

# 로컬 실행용: .env 파일(KEY=값)이 있으면 환경변수로 읽습니다. GitHub Actions에서는 secrets를 씁니다.
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8-sig").splitlines():
        _k, _sep, _v = _line.partition("=")
        if _sep and not _line.lstrip().startswith("#"):
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
# 이미 만든 Vol을 새 디자인으로 다시 그릴 때: [2, 3, 4] 처럼 적어 두면 다음 generate 때 한 번 실행되고 지워집니다.
RERENDER = ROOT / "data" / "rerender.json"
# 인스타에 올라간 Vol 번호 목록. publish는 여기 없는 가장 오래된 Vol부터 하루 하나씩 올립니다.
PUBLISHED = ROOT / "data" / "published.json"
# 광고 없는 기간: {"until": "2026-11-16"} 이면 그날까지 만드는 카드는 쿠팡 광고·링크 없이 정보만 담습니다.
ADFREE = ROOT / "data" / "adfree.json"
KST = timezone(timedelta(hours=9))
PUBLISH_HOUR_KST = 12    # 매일 12:40 (한국 시간)에 게시
PUBLISH_MINUTE_KST = 40

HASHTAGS = {
    "여행": "#여행준비물 #여행꿀팁 #해외여행준비 #여행필수템 #여행가방싸기 #국내여행 #여행템 #여행스타그램",
    "숙소": "#호캉스 #숙소추천 #호텔꿀팁 #여행준비물 #숙소필수템 #에어비앤비 #여행꿀템 #호캉스준비물",
    "캠핑": "#캠핑용품 #캠핑필수템 #캠핑초보 #캠핑꿀템 #차박 #캠핑장비 #캠핑스타그램 #감성캠핑",
}


def ad_free_until() -> str:
    """광고 없는 기간의 마지막 날(YYYY-MM-DD, 한국 시간). 파일이 없으면 빈 문자열."""
    if not ADFREE.exists():
        return ""
    return json.loads(ADFREE.read_text(encoding="utf-8")).get("until", "")


def ad_free_now() -> bool:
    return datetime.now(KST).strftime("%Y-%m-%d") <= ad_free_until()


def caption(topic: dict, ad: bool = True) -> str:
    if not ad:
        lines = [f'{topic["sub"]} {topic["title1"]} {topic["title2"]}', ""]
        lines += [f'{n}. {it["name"]} — {it["tip"]}' for n, it in enumerate(topic["items"], start=1)]
        lines += [
            "",
            "도움이 됐다면 저장하고, 같이 갈 사람에게 공유해 주세요.",
            f'매일 새 {topic["category"]} 꿀팁을 올려요. 팔로우하고 받아보세요.',
            "",
            HASHTAGS.get(topic["category"], ""),
        ]
        return "\n".join(lines)[:2200]
    # 광고 표시는 '더보기' 없이 보이는 첫 줄에 둡니다 (공정위 추천·보증 심사지침).
    lines = ["[광고] 쿠팡 파트너스 수수료를 받는 추천 게시물이에요", "", f'{topic["sub"]} {topic["title1"]} {topic["title2"]}', ""]
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


def set_adfree(vols: list[int], adfree: bool = True) -> None:
    """이미 만든(아직 안 올린) Vol을 광고 없는 정보형으로 바꾸거나(adfree) 광고형으로 되돌린 뒤 다시 그립니다."""
    posts = json.loads(linkpage.POSTS.read_text(encoding="utf-8"))
    for p in posts:
        if p["vol"] in vols:
            p["adfree"] = adfree
    linkpage.POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    rerender(vols)
    linkpage.build(posts)


def rerender(vols: list[int]) -> None:
    """posts.json에 저장된 상품으로 지난 Vol 카드와 캡션을 다시 만듭니다 (쿠팡 API 호출 없음)."""
    posts = {p["vol"]: p for p in json.loads(linkpage.POSTS.read_text(encoding="utf-8"))}
    bank = json.loads(topics.BANK.read_text(encoding="utf-8"))
    for vol in vols:
        post = posts.get(vol)
        topic = next(
            (t for t in bank if post and t["category"] == post["category"] and f'{t["title1"]} {t["title2"]}' == post["title"]),
            None,
        )
        if not topic:
            print(f"[rerender] Vol.{vol:02d}: 주제 뱅크에서 찾지 못해 건너뜁니다.")
            continue
        topic = dict(topic, vol=vol)
        products = [
            {"productImage": it.get("productImage"), "productUrl": it.get("url"), "productName": it.get("productName")}
            for it in post["items"]
        ]
        ad = not post.get("adfree")
        photos.ensure(topic, items=not ad)
        out_dir = linkpage.DOCS / "cards" / f"vol-{vol:02d}"
        render.render_all(topic, products, out_dir, ad=ad)
        (out_dir / "caption.txt").write_text(caption(topic, ad=ad), encoding="utf-8")
        print(f"[rerender] Vol.{vol:02d} 다시 만듦 ({'광고' if ad else '광고 없음'})")


def generate(mock: bool = False) -> None:
    if RERENDER.exists():
        rerender(json.loads(RERENDER.read_text(encoding="utf-8")))
        RERENDER.unlink()
        linkpage.build(json.loads(linkpage.POSTS.read_text(encoding="utf-8")))

    backlog = unposted_vols()
    if backlog and not mock:
        # 아직 안 올린 Vol이 있으면 새로 만들지 않습니다 (게시가 계속 밀리는 것과 쿠팡 API 낭비를 막음).
        print(f"[generate] 게시 대기 중인 Vol {backlog} 이 있어 오늘은 새 Vol을 만들지 않습니다.")
        return

    topic, state = topics.next_topic()
    print(f'[generate] Vol.{topic["vol"]:02d} {topic["category"]} · {topic["title1"]} {topic["title2"]}')

    adfree = ad_free_now()
    if adfree:
        # 광고 없는 기간: 쿠팡 API를 부르지 않고 정보형 카드만 만듭니다.
        print(f"[generate] 광고 없는 기간({ad_free_until()}까지): 쿠팡 링크 없이 만듭니다.")
        products = [None] * len(topic["items"])
    elif mock:
        products = _mock_products(topic)
    else:
        from .coupang import pick_products

        products = pick_products([it["keyword"] for it in topic["items"]])
        found = sum(1 for p in products if p)
        print(f"[generate] 쿠팡 상품 {found}/5개 찾음")
        if found < 3:
            sys.exit("상품을 3개 이상 찾지 못해 오늘은 건너뜁니다 (state는 저장하지 않음).")

    # 표지 배경 사진은 항상, 항목 사진은 상품 사진이 없는 정보형 카드에서만 씁니다.
    photos.ensure(topic, items=adfree)
    out_dir = linkpage.DOCS / "cards" / f'vol-{topic["vol"]:02d}'
    files = render.render_all(topic, products, out_dir, ad=not adfree)
    (out_dir / "caption.txt").write_text(caption(topic, ad=not adfree), encoding="utf-8")

    date = datetime.now(KST).strftime("%Y-%m-%d")
    linkpage.add_post(topic, products, date, adfree=adfree)
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


def _published() -> list[int]:
    return json.loads(PUBLISHED.read_text(encoding="utf-8")) if PUBLISHED.exists() else []


def unposted_vols() -> list[int]:
    """카드가 만들어졌지만 아직 인스타에 안 올린 Vol 번호 (오래된 순)."""
    posts = json.loads(linkpage.POSTS.read_text(encoding="utf-8")) if linkpage.POSTS.exists() else []
    done = set(_published())
    return sorted(p["vol"] for p in posts if p["vol"] not in done)


def _wait_until_publish_time() -> None:
    """예약 실행이 일찍 시작되면 낮 12시 40분(한국 시간)까지 기다립니다. 늦게 시작되면 바로 올립니다."""
    now = datetime.now(KST)
    target = now.replace(hour=PUBLISH_HOUR_KST, minute=PUBLISH_MINUTE_KST, second=0, microsecond=0)
    wait = (target - now).total_seconds()
    if 0 < wait <= 3 * 3600:
        print(f"[publish] {target:%H:%M}까지 {int(wait // 60)}분 기다립니다.")
        time.sleep(wait)


def publish(vol: int | None = None) -> None:
    from . import instagram

    queue = unposted_vols()
    if vol is None:
        if not queue:
            print("[publish] 게시할 카드가 없습니다.")
            return
        vol = queue[0]
    card_dir = linkpage.DOCS / "cards" / f"vol-{vol:02d}"
    files = sorted(card_dir.glob("*.jpg"))
    if not files:
        sys.exit(f"Vol.{vol:02d} 카드 이미지가 없습니다: {card_dir}")
    cap = (card_dir / "caption.txt").read_text(encoding="utf-8")
    base = _pages_base()
    # 같은 파일명으로 다시 렌더링된 경우 인스타가 옛 이미지를 가져가지 않도록 버전 쿼리를 붙입니다.
    ver = int(max(f.stat().st_mtime for f in files))
    urls = [f"{base}/{f.relative_to(linkpage.DOCS).as_posix()}?v={ver}" for f in files]
    instagram.wait_until_public(urls)
    if os.environ.get("WAIT_FOR_PUBLISH_TIME") == "true":
        _wait_until_publish_time()
    media_id = instagram.publish_carousel(urls, cap)
    print(f"[publish] Vol.{vol:02d} 게시 완료 (media id {media_id})")
    PUBLISHED.write_text(json.dumps(sorted(set(_published()) | {vol})), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        generate(mock="--mock" in sys.argv)
    elif cmd == "rerender":
        rerender([int(v) for v in sys.argv[2:]])
    elif cmd in ("adfree", "adon"):
        set_adfree([int(v) for v in sys.argv[2:]], adfree=cmd == "adfree")
    elif cmd == "publish":
        publish(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        print(__doc__)
        sys.exit(1)
