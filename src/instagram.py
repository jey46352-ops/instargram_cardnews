"""Instagram Graph API로 캐러셀(여러 장) 게시."""
import os
import time

import requests

GRAPH = os.environ.get("IG_GRAPH_BASE", "https://graph.facebook.com/v21.0")


class InstagramError(RuntimeError):
    pass


def _post(path: str, **params) -> dict:
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.post(f"{GRAPH}/{path}", data=params, timeout=60)
    body = resp.json()
    if resp.status_code >= 400 or "error" in body:
        raise InstagramError(f"{path}: {body.get('error', body)}")
    return body


def _status(container_id: str) -> str:
    resp = requests.get(
        f"{GRAPH}/{container_id}",
        params={"fields": "status_code", "access_token": os.environ["IG_ACCESS_TOKEN"]},
        timeout=30,
    )
    return resp.json().get("status_code", "")


def _wait(container_id: str, tries: int = 30) -> None:
    for _ in range(tries):
        code = _status(container_id)
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise InstagramError(f"컨테이너 {container_id} 처리 실패: {code}")
        time.sleep(5)
    raise InstagramError(f"컨테이너 {container_id} 처리 시간 초과")


def wait_until_public(urls: list[str], timeout: int = 600) -> None:
    """GitHub Pages 배포가 끝나 이미지가 공개 URL로 열릴 때까지 기다립니다."""
    deadline = time.time() + timeout
    pending = list(urls)
    while pending and time.time() < deadline:
        pending = [u for u in pending if requests.head(u, timeout=20).status_code != 200]
        if pending:
            time.sleep(15)
    if pending:
        raise InstagramError(f"이미지가 아직 공개되지 않았습니다: {pending[0]}")


def publish_carousel(image_urls: list[str], caption: str) -> str:
    user_id = os.environ["IG_USER_ID"]
    children = []
    for url in image_urls:
        c = _post(f"{user_id}/media", image_url=url, is_carousel_item="true")
        children.append(c["id"])
    for cid in children:
        _wait(cid)
    carousel = _post(f"{user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)
    _wait(carousel["id"])
    published = _post(f"{user_id}/media_publish", creation_id=carousel["id"])
    return published["id"]
