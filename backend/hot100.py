"""力扣 Hot 100 列表抓取（通过 leetcode.cn GraphQL + curl_cffi 绕过 Cloudflare）。"""
from curl_cffi import requests as cr

HOT100_LIST_ID = "2cktkvj"  # leetcode.cn 「热题 HOT 100」 列表 id
GRAPHQL_URL = "https://leetcode.cn/graphql"

QUERY = """query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList(categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters) {
    total
    questions {
      frontendQuestionId
      titleSlug
      titleCn
      title
      difficulty
    }
  }
}"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://leetcode.cn/problem-list/2cktkvj/",
}


def fetch_hot100(limit: int = 100) -> list[dict]:
    """返回 Hot 100 题目列表 [{slug, title_cn, title, difficulty, id}]。"""
    payload = {
        "query": QUERY,
        "variables": {
            "categorySlug": "",
            "limit": limit,
            "skip": 0,
            "filters": {"listId": HOT100_LIST_ID},
        },
    }
    resp = cr.post(GRAPHQL_URL, json=payload, headers=HEADERS, impersonate="chrome", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    questions = (data.get("data") or {}).get("problemsetQuestionList", {}).get("questions") or []
    items = []
    for q in questions:
        items.append(
            {
                "slug": q.get("titleSlug", ""),
                "id": q.get("frontendQuestionId"),
                "title_cn": q.get("titleCn") or q.get("title", ""),
                "title": q.get("title", ""),
                "difficulty": (q.get("difficulty") or "MEDIUM").title(),
            }
        )
    return items
