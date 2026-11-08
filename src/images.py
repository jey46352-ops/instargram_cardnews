"""상품 이미지 분석·정리.

- 흰 배경(누끼) 이미지: 바깥 흰 여백을 잘라내고 박스 안에 크게 배치 (kind="clean")
- 사진형 이미지(배경·모델·광고 배경이 있는 것): 박스를 꽉 채우게 배치 (kind="photo")
이미지는 data URI로 바꿔 카드에 직접 넣으므로 렌더링 중 로딩 실패가 없습니다.
"""
import base64
import io

import requests
from PIL import Image, ImageChops

WHITE = 235          # 이 값 이상이면 '흰색'으로 봅니다 (0~255)
CLEAN_RATIO = 0.6    # 테두리의 60% 이상이 흰색이면 흰 배경 이미지


def fetch(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img.load()
        return img.convert("RGB")
    except Exception as exc:
        print(f"[images] 이미지 다운로드 실패: {exc}")
        return None


def white_ratio(img: Image.Image) -> float:
    """이미지 바깥 테두리(각 변 4%) 중 흰색 픽셀 비율."""
    small = img.copy()
    small.thumbnail((200, 200))
    w, h = small.size
    band = max(2, int(min(w, h) * 0.04))
    px = small.load()
    total = white = 0
    for y in range(h):
        for x in range(w):
            if x < band or x >= w - band or y < band or y >= h - band:
                r, g, b = px[x, y]
                total += 1
                if r >= WHITE and g >= WHITE and b >= WHITE:
                    white += 1
    return white / total if total else 0.0


def classify(img: Image.Image) -> str:
    return "clean" if white_ratio(img) >= CLEAN_RATIO else "photo"


def trim_white(img: Image.Image, pad: float = 0.04) -> Image.Image:
    """흰 여백을 잘라내고 약간의 여유만 남깁니다."""
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 255 - WHITE + 5 else 0)
    box = diff.getbbox()
    if not box:
        return img
    left, top, right, bottom = box
    p = int(max(right - left, bottom - top) * pad)
    return img.crop((max(0, left - p), max(0, top - p), min(img.width, right + p), min(img.height, bottom + p)))


def to_data_uri(img: Image.Image, max_side: int = 1000) -> str:
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def prepare(url: str | None) -> tuple[str | None, str]:
    """(src, kind) 반환. 다운로드에 실패하면 원래 URL을 그대로 쓰고 clean으로 둡니다."""
    img = fetch(url) if url else None
    if img is None:
        return url, "clean"
    kind = classify(img)
    if kind == "clean":
        img = trim_white(img)
    return to_data_uri(img), kind
