"""쿠팡파트너스 Open API 클라이언트 (HMAC 서명)."""
import hashlib
import hmac
import os
import time
from time import gmtime, strftime
from urllib.parse import urlencode

import requests

DOMAIN = "https://api-gateway.coupang.com"
SEARCH_PATH = "/v2/providers/affiliate_open_api/apis/openapi/products/search"


class CoupangError(RuntimeError):
    pass


def _authorization(method: str, path: str, query: str, access_key: str, secret_key: str) -> str:
    signed_date = strftime("%y%m%d", gmtime()) + "T" + strftime("%H%M%S", gmtime()) + "Z"
    message = signed_date + method + path + query
    signature = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={access_key}, "
        f"signed-date={signed_date}, signature={signature}"
    )


class CoupangClient:
    def __init__(self, access_key: str | None = None, secret_key: str | None = None, sub_id: str | None = None):
        self.access_key = access_key or os.environ.get("COUPANG_ACCESS_KEY", "")
        self.secret_key = secret_key or os.environ.get("COUPANG_SECRET_KEY", "")
        self.sub_id = sub_id if sub_id is not None else os.environ.get("COUPANG_SUB_ID", "")
        if not self.access_key or not self.secret_key:
            raise CoupangError("COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 환경변수가 없습니다.")

    def search(self, keyword: str, limit: int = 5) -> list[dict]:
        """키워드로 상품 검색. 각 상품의 productUrl은 이미 파트너스 수익 링크입니다."""
        params = {"keyword": keyword, "limit": limit}
        if self.sub_id:
            params["subId"] = self.sub_id
        query = urlencode(params)
        headers = {
            "Authorization": _authorization("GET", SEARCH_PATH, query, self.access_key, self.secret_key),
            "Content-Type": "application/json;charset=UTF-8",
        }
        resp = requests.get(f"{DOMAIN}{SEARCH_PATH}?{query}", headers=headers, timeout=20)
        if resp.status_code == 403 or resp.status_code == 429:
            # 검색 API는 호출 한도가 작습니다. 한도 초과가 반복되면 API 사용이 막힐 수 있으니 즉시 멈춥니다.
            raise CoupangError(f"쿠팡 API 호출 한도 초과 또는 권한 없음 ({resp.status_code}): {resp.text[:200]}")
        resp.raise_for_status()
        body = resp.json()
        if str(body.get("rCode")) != "0":
            raise CoupangError(f"쿠팡 API 오류: {body.get('rCode')} {body.get('rMessage')}")
        return (body.get("data") or {}).get("productData") or []

    def pick(self, keyword: str) -> dict | None:
        """검색 결과 중 이미지가 있는 상품 하나를 고릅니다 (로켓배송 우선)."""
        products = [p for p in self.search(keyword) if p.get("productImage") and p.get("productUrl")]
        if not products:
            return None
        products.sort(key=lambda p: (not p.get("isRocket"), p.get("rank", 99)))
        p = _prefer_clean_image(products[:4])
        return {
            "keyword": keyword,
            "productId": p.get("productId"),
            "productName": p.get("productName"),
            "productPrice": p.get("productPrice"),
            "productImage": p.get("productImage"),
            "productUrl": p.get("productUrl"),
            "isRocket": bool(p.get("isRocket")),
        }


def _prefer_clean_image(candidates: list[dict]) -> dict:
    """상위 후보 중 흰 배경(광고 문구가 적은) 대표 이미지를 가진 상품을 우선 고릅니다.
    이미지 서버 호출이라 쿠팡 API 호출 한도와는 무관합니다."""
    from .images import CLEAN_RATIO, fetch, white_ratio

    for p in candidates:
        img = fetch(p.get("productImage"))
        if img is not None and white_ratio(img) >= CLEAN_RATIO:
            return p
    return candidates[0]


def pick_products(keywords: list[str], delay: float = 2.0) -> list[dict | None]:
    client = CoupangClient()
    results = []
    for i, kw in enumerate(keywords):
        if i:
            time.sleep(delay)
        results.append(client.pick(kw))
    return results
