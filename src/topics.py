"""오늘의 주제 고르기: 여행 → 숙소 → 캠핑 순서로 돌아가며, 주제 뱅크를 먼저 쓰고
다 쓰면 (ANTHROPIC_API_KEY가 있으면) Claude로 새 주제를 만들거나 처음부터 다시 돕니다."""
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BANK = ROOT / "data" / "topics.json"
STATE = ROOT / "data" / "state.json"
CATEGORIES = ["여행", "숙소", "캠핑"]


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"vol": 0, "used": [], "round": 1}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_with_claude(category: str, used_titles: list[str]) -> dict | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = (
        f"인스타그램 카드뉴스 주제를 하나 만들어줘. 카테고리: {category}.\n"
        "쿠팡에서 살 수 있는 상품 5개를 추천하는 형식이야. 아래 JSON만 출력해.\n"
        '{"sub":"15자 이내 서브 문구","title1":"7자 이내 제목 첫 줄","title2":"7자 이내 둘째 줄(예: TOP 5)",'
        '"items":[{"name":"8자 이내 상품명","keyword":"쿠팡 검색 키워드","tip":"24자 이내 한 줄 팁"}]}\n'
        "items는 정확히 5개. 과장이나 효능 주장은 쓰지 마.\n"
        f"이미 쓴 제목(겹치지 않게): {', '.join(used_titles[-40:])}"
    )
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            "max_tokens": 1200,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = "".join(b.get("text", "") for b in resp.json().get("content", []))
    start, end = text.find("{"), text.rfind("}")
    topic = json.loads(text[start : end + 1])
    if len(topic.get("items", [])) != 5:
        return None
    topic["category"] = category
    topic["id"] = f"ai-{len(used_titles) + 1}"
    return topic


def next_topic() -> tuple[dict, dict]:
    """(topic, state) 반환. state는 게시가 끝난 뒤 save_state로 저장합니다."""
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    state = load_state()
    category = CATEGORIES[state["vol"] % len(CATEGORIES)]
    used = set(state["used"])
    candidates = [t for t in bank if t["category"] == category and t["id"] not in used]

    topic = candidates[0] if candidates else None
    if topic is None:
        used_titles = [f'{t["title1"]} {t["title2"]}' for t in bank] + state.get("ai_titles", [])
        try:
            topic = _generate_with_claude(category, used_titles)
        except Exception as exc:  # 생성 실패 시 뱅크 재사용으로 넘어갑니다
            print(f"[topics] Claude 주제 생성 실패, 뱅크를 다시 씁니다: {exc}")
            topic = None
        if topic:
            state.setdefault("ai_titles", []).append(f'{topic["title1"]} {topic["title2"]}')
        else:
            # 해당 카테고리 뱅크를 다 썼으면 그 카테고리만 처음부터 다시 (상품은 그날 검색 결과로 새로 바뀝니다)
            state["used"] = [u for u in state["used"] if not any(t["id"] == u and t["category"] == category for t in bank)]
            state["round"] = state.get("round", 1) + 1
            topic = [t for t in bank if t["category"] == category][0]

    state["vol"] += 1
    state["used"].append(topic["id"])
    topic = dict(topic, vol=state["vol"])
    return topic, state
