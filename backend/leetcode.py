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
from curl_cffi import requests as cr

GRAPHQL_ENDPOINTS = [
    # leetcode.com 优先：cn 站的 GraphQL 对无登录请求有 Cloudflare 拦截（403），
    # 且匿名返回的内容是英文。中文题目信息由 agent 工作流中的“翻译节点”生成。
    "https://leetcode.com/graphql",
    "https://leetcode.cn/graphql",
]

CN_GRAPHQL_URL = "https://leetcode.cn/graphql"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
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
    """把 LeetCode 题目的 HTML 内容转成接近 Markdown 的纯文本（更干净的格式）。

    - 代码块（<pre>）原样保留在 ``` 围栏内
    - 普通段落压缩多余空白，<sup>/<sub> 转为 ^ / _
    - 列表项转为 "- " 前缀
    """

    BLOCK_TAGS = {"p", "div", "li", "tr", "ul", "ol", "table", "h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._in_pre = False

    def _newline(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self._in_pre = True
            self._newline()
            self.parts.append("```\n")
        elif tag == "br":
            self._newline()
        elif tag == "li":
            self._newline()
            self.parts.append("- ")
        elif tag in ("h1", "h2", "h3", "h4"):
            self._newline()
        elif tag == "sup":
            self.parts.append("^")
        elif tag == "sub":
            self.parts.append("_")
        elif tag == "strong":
            self.parts.append("**")
        elif tag == "em":
            self.parts.append("*")
        elif tag == "code" and not self._in_pre:
            self.parts.append("`")
        elif tag in self.BLOCK_TAGS:
            self._newline()

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
            self._newline()

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html or "")
    text = "".join(parser.parts)
    # 逐行整理：代码块内保持原样，普通行压缩空白
    out_lines: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.strip() == "```":
            in_code = not in_code
            out_lines.append(line)
        elif in_code:
            out_lines.append(line.rstrip())
        else:
            out_lines.append(re.sub(r"[ \t]+", " ", line).strip())
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _query_graphql(endpoint: str, slug: str) -> Optional[dict]:
    payload = {"query": QUESTION_QUERY, "variables": {"titleSlug": slug}}
    resp = requests.post(endpoint, json=payload, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    question = (data.get("data") or {}).get("question")
    return question if question else None


def fetch_cn_title(slug: str) -> Optional[str]:
    """通过 leetcode.cn GraphQL 获取中文标题（translatedTitle）。"""
    try:
        q = "query q($s: String!) { question(titleSlug: $s) { translatedTitle } }"
        r = cr.post(
            CN_GRAPHQL_URL,
            json={"query": q, "variables": {"s": slug}},
            impersonate="chrome",
            timeout=15,
        )
        r.raise_for_status()
        title = ((r.json().get("data") or {}).get("question") or {}).get("translatedTitle")
        return title or None
    except Exception:  # noqa: BLE001
        return None


def fetch_problem(slug: str) -> Optional[dict]:
    """抓取题目，返回结构化字典；失败返回 None。"""
    last_err: Optional[Exception] = None
    for endpoint in GRAPHQL_ENDPOINTS:
        for attempt in range(3):
            try:
                q = _query_graphql(endpoint, slug)
                if q is not None:
                    problem = _normalize(q)
                    problem["title_cn"] = fetch_cn_title(slug)
                    return problem
                break  # 该端点返回空题目，换下一个端点
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
        "url": f"https://leetcode.cn/problems/{slug}/",
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
        "url": url or f"https://leetcode.cn/problems/{slug}/",
        "source": "llm",
    }
