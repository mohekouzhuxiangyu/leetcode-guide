"""LeetCode 题目抓取器：从题目链接提取 slug，通过官方 GraphQL API 获取题目信息。

支持 leetcode.com 与 leetcode.cn。抓取失败时返回 None，由 agent 工作流
回退到"模型根据已知知识重建题目"。
"""
import json
import re
import time
from html.parser import HTMLParser
from typing import Optional

import requests

GRAPHQL_ENDPOINTS = [
    "https://leetcode.com/graphql",
    "https://leetcode.cn/graphql",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/",
}

QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    titleSlug
    difficulty
    content
    topicTags { name slug }
    codeSnippets { lang langSlug code }
    stats
    hints
    metaData
  }
}
"""


def extract_slug(url: str) -> Optional[str]:
    """从链接中提取题目 slug，如 https://leetcode.cn/problems/two-sum/ -> two-sum"""
    if not url:
        return None
    m = re.search(r"problems/([A-Za-z0-9\-_]+)", url)
    return m.group(1) if m else None


class _HTMLToText(HTMLParser):
    """把 LeetCode 题目的 HTML 内容转成接近 Markdown 的纯文本。"""

    BLOCK_TAGS = {"p", "div", "br", "pre", "li", "tr", "h1", "h2", "h3", "h4", "table"}
    HEAD_TAGS = {"h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._in_pre = False

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self._in_pre = True
            self.parts.append("\n```\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag == "strong":
            self.parts.append("**")
        elif tag == "em":
            self.parts.append("*")
        elif tag == "code" and not self._in_pre:
            self.parts.append("`")

    def handle_endtag(self, tag):
        if tag == "pre":
            self._in_pre = False
            self.parts.append("\n```\n")
        elif tag == "strong":
            self.parts.append("**")
        elif tag == "em":
            self.parts.append("*")
        elif tag == "code" and not self._in_pre:
            self.parts.append("`")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html or "")
    text = "".join(parser.parts)
    # 压缩多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _query_graphql(endpoint: str, slug: str) -> Optional[dict]:
    payload = {"query": QUESTION_QUERY, "variables": {"titleSlug": slug}}
    resp = requests.post(endpoint, json=payload, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    question = (data.get("data") or {}).get("question")
    return question if question else None


def fetch_problem(slug: str) -> Optional[dict]:
    """抓取题目，返回结构化字典；失败返回 None。"""
    last_err: Optional[Exception] = None
    for endpoint in GRAPHQL_ENDPOINTS:
        for attempt in range(3):
            try:
                q = _query_graphql(endpoint, slug)
                if q is None:
                    return None
                return _normalize(q)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(1.0 + attempt * 1.5)
    print(f"[leetcode] 抓取失败: {slug} -> {last_err}")
    return None


def _normalize(q: dict) -> dict:
    def _parse_json_field(field):
        if isinstance(field, (dict, list)):
            return field
        if isinstance(field, str):
            try:
                return json.loads(field)
            except json.JSONDecodeError:
                return {}
        return {}

    stats = _parse_json_field(q.get("stats")) or {}
    meta = _parse_json_field(q.get("metaData")) or {}

    snippets = {}
    for s in q.get("codeSnippets") or []:
        lang = (s.get("lang") or "").lower()
        if lang in ("python3", "python"):
            snippets["Python3"] = s.get("code", "")
        elif lang in ("java",):
            snippets["Java"] = s.get("code", "")
        elif lang in ("cpp", "c++"):
            snippets["C++"] = s.get("code", "")

    slug = q.get("titleSlug") or ""
    return {
        "id": q.get("questionId"),
        "title": q.get("title", slug),
        "slug": slug,
        "difficulty": q.get("difficulty", "Medium"),
        "tags": [t.get("name") for t in (q.get("topicTags") or [])],
        "content_text": html_to_text(q.get("content", "")),
        "code_snippets": snippets,
        "stats": {
            "totalAcceptedRaw": stats.get("totalAcceptedRaw"),
            "totalSubmissionRaw": stats.get("totalSubmissionRaw"),
            "acRate": stats.get("acRate"),
        },
        "hints": q.get("hints") or [],
        "meta": {
            "functionName": meta.get("functionName"),
            "params": meta.get("params"),
            "return": meta.get("return"),
        },
        "url": f"https://leetcode.com/problems/{slug}/",
        "source": "leetcode",
    }


def fallback_problem(slug: str, url: str) -> dict:
    """抓取失败时的回退：交给模型基于已知知识生成。"""
    return {
        "id": None,
        "title": slug.replace("-", " ").title(),
        "slug": slug,
        "difficulty": "Unknown",
        "tags": [],
        "content_text": "",
        "code_snippets": {},
        "stats": {},
        "hints": [],
        "meta": {},
        "url": url or f"https://leetcode.com/problems/{slug}/",
        "source": "llm",
    }
