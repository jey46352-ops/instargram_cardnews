"""프로필 링크(링크인바이오) 페이지: GitHub Pages(docs/)에 게시물별 쿠팡 링크를 모아 보여줍니다."""
import html
import json
import os
from pathlib import Path

from .render import DISCLOSURE, accent_for

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
POSTS = DOCS / "posts.json"


def _e(s) -> str:
    return html.escape(str(s or ""))


def add_post(topic: dict, products: list[dict | None], date: str) -> None:
    posts = json.loads(POSTS.read_text(encoding="utf-8")) if POSTS.exists() else []
    posts = [p for p in posts if p["vol"] != topic["vol"]]
    posts.insert(
        0,
        {
            "vol": topic["vol"],
            "date": date,
            "category": topic["category"],
            "title": f'{topic["title1"]} {topic["title2"]}',
            "items": [
                {
                    "name": it["name"],
                    "tip": it["tip"],
                    "productName": (products[i] or {}).get("productName"),
                    "productImage": (products[i] or {}).get("productImage"),
                    "url": (products[i] or {}).get("productUrl"),
                }
                for i, it in enumerate(topic["items"])
            ],
        },
    )
    DOCS.mkdir(exist_ok=True)
    POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
    build(posts)


def build(posts: list[dict]) -> None:
    handle = os.environ.get("IG_HANDLE", "@your_account")
    sections = []
    for p in posts:
        rows = []
        for n, it in enumerate(p["items"], start=1):
            btn = (
                f'<a class="btn" href="{_e(it["url"])}" target="_blank" rel="sponsored nofollow noopener">쿠팡에서 보기</a>'
                if it.get("url")
                else '<span class="btn off">준비 중</span>'
            )
            img = f'<img src="{_e(it["productImage"])}" alt="" loading="lazy">' if it.get("productImage") else "<div></div>"
            rows.append(
                f'<li><span class="no">No.{n}</span>{img}<div class="txt"><b>{_e(it["name"])}</b>'
                f'<small>{_e(it.get("productName") or it["tip"])}</small></div>{btn}</li>'
            )
        sections.append(
            f'<section id="vol-{p["vol"]:02d}" style="--accent:{accent_for(p["category"])}"><header><span class="tag">{_e(p["category"])}</span>'
            f'<span class="meta">Vol.{p["vol"]:02d} · {_e(p["date"])}</span></header>'
            f'<h2>{_e(p["title"])}</h2><ol>{"".join(rows)}</ol></section>'
        )

    page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(handle)} 추천 링크</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{{--bg:#121212;--card:#1E1E1E;--fg:#FFF;--muted:#BDBDBD;--line:#333;--accent:#FFD43B}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font-family:Pretendard,'Noto Sans KR',sans-serif}}
main{{max-width:560px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:24px;margin:8px 0 4px}}.note{{color:var(--muted);font-size:13px;line-height:1.5;margin:0 0 24px}}
section{{background:var(--card);border-radius:16px;padding:20px 16px;margin-bottom:16px}}
header{{display:flex;justify-content:space-between;align-items:center}}
.tag{{background:var(--accent);color:#121212;font-weight:700;font-size:13px;padding:4px 12px;border-radius:999px}}
.meta{{color:var(--muted);font-size:13px}}h2{{font-size:20px;margin:12px 0}}
ol{{list-style:none;margin:0;padding:0}}li{{display:grid;grid-template-columns:44px 56px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid var(--line)}}
.no{{color:var(--accent);font-weight:800;font-size:14px}}li img{{width:56px;height:56px;object-fit:contain;background:#fff;border-radius:8px}}
.txt{{min-width:0}}.txt b{{display:block;font-size:15px}}.txt small{{display:block;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.btn{{background:var(--accent);color:#121212;font-weight:700;font-size:13px;padding:10px 12px;border-radius:10px;text-decoration:none;white-space:nowrap;min-height:44px;display:flex;align-items:center}}
.btn.off{{background:var(--line);color:var(--muted)}}
</style></head><body><main>
<h1>{_e(handle)} 추천 링크</h1>
<p class="note">게시물의 No. 번호와 같은 순서입니다. {DISCLOSURE}</p>
{"".join(sections)}
</main></body></html>"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
