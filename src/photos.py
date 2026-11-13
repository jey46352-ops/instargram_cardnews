"""카드에 넣을 무료 분위기 사진을 자동으로 찾아 data/photos/vol-NN/ 에 저장합니다.

- 표지(cover.jpg): 주제의 "photo" 키워드
- 항목(01.jpg~05.jpg): 각 항목의 "photo" 키워드 (광고 없는 정보형 카드에서 사용)

사진 출처는 Pexels(무료·상업적 사용 가능, 환경변수 PEXELS_API_KEY 필요)를 먼저 쓰고,
키가 없거나 실패하면 Openverse의 CC0(퍼블릭 도메인) 사진을 찾습니다.
이미 저장된 사진은 다시 받지 않으므로, 마음에 안 드는 사진은 파일을 지우거나 직접 바꿔 넣으면 됩니다.
"""
import io
import json
import os
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "data" / "photos"
USED = PHOTOS / "used.json"          # 이미 쓴 사진 (다른 Vol에 같은 사진이 또 나오지 않게)
UA = {"User-Agent": "cardnews-bot/1.0"}
MAX_SIDE = 1600


def _load_used() -> set[str]:
    return set(json.loads(USED.read_text(encoding="utf-8"))) if USED.exists() else set()


def _pexels(query: str, orientation: str) -> list[dict]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        params={"query": query, "orientation": orientation, "per_page": 15},
        headers={"Authorization": key, **UA},
        timeout=20,
    )
    resp.raise_for_status()
    return [
        {"id": f'pexels:{p["id"]}', "url": p["src"]["large2x"], "source": p["url"], "license": "Pexels License"}
        for p in resp.json().get("photos", [])
    ]


def _openverse(query: str, orientation: str) -> list[dict]:
    aspect = {"landscape": "wide", "portrait": "tall"}.get(orientation, "")
    resp = requests.get(
        "https://api.openverse.org/v1/images/",
        # 엉뚱한 기록 사진이 섞이지 않도록 스톡 사진 사이트만 검색합니다.
        params={"q": query, "license": "cc0", "page_size": 15, "mature": "false", "aspect_ratio": aspect,
                "source": "stocksnap,rawpixel"},
        headers=UA,
        timeout=20,
    )
    resp.raise_for_status()
    return [
        {"id": f'openverse:{r["id"]}', "url": r["url"], "source": r.get("foreign_landing_url") or r["url"], "license": "CC0"}
        for r in resp.json().get("results", [])
        if (r.get("width") or 0) >= 900
    ]


def _download(url: str) -> Image.Image | None:
    try:
        resp = requests.get(url, headers=UA, timeout=30)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img.load()
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        return img
    except Exception as exc:
        print(f"[photos] 다운로드 실패 {url}: {exc}")
        return None


def find(query: str, orientation: str, used: set[str]) -> tuple[Image.Image, dict] | None:
    for search in (_pexels, _openverse):
        try:
            candidates = search(query, orientation)
        except Exception as exc:
            print(f"[photos] {search.__name__[1:]} 검색 실패 '{query}': {exc}")
            continue
        for c in candidates:
            if c["id"] in used:
                continue
            img = _download(c["url"])
            if img is not None:
                return img, c
    return None


def ensure(topic: dict, items: bool = True) -> None:
    """표지 사진과 (items=True면) 항목 사진이 없으면 찾아서 저장합니다. 실패해도 카드는 사진 없이 만들어집니다."""
    jobs = [("cover", topic.get("photo"), "portrait")]
    if items:
        jobs += [(f"{i:02d}", it.get("photo"), "landscape") for i, it in enumerate(topic["items"], start=1)]

    out = PHOTOS / f'vol-{topic["vol"]:02d}'
    credits_path = out / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else {}
    used = _load_used()
    changed = False
    for key, query, orientation in jobs:
        if not query or (out / f"{key}.jpg").exists():
            continue
        time.sleep(2)  # 무료 API 요청 제한에 걸리지 않게 조금씩 쉬어 갑니다.
        found = find(query, orientation, used)
        if not found:
            print(f"[photos] Vol.{topic['vol']:02d} {key}: '{query}' 사진을 찾지 못해 사진 없이 만듭니다.")
            continue
        img, meta = found
        out.mkdir(parents=True, exist_ok=True)
        img.save(out / f"{key}.jpg", quality=88)
        credits[key] = {"query": query, "source": meta["source"], "license": meta["license"]}
        used.add(meta["id"])
        changed = True
        print(f"[photos] Vol.{topic['vol']:02d} {key}: {meta['source']}")
    if changed:
        credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
        USED.write_text(json.dumps(sorted(used), indent=0), encoding="utf-8")
