"""LangGraph agent 工作流：抓取题目 → 算法解析 → Mermaid 流程图 → 代码生成。

每个阶段都是一个独立的 agent（LLM + 专用提示词），由 LangGraph StateGraph
编排。各节点互相隔离、可独立失败：某个节点出错不会让整个流程中断。
"""
import re
from typing import Callable, Optional, TypedDict

from langgraph.graph import END, StateGraph

from . import leetcode
from .llm import create_llm

StageCallback = Callable[[str, str], None]


class AgentState(TypedDict, total=False):
    url: str
    slug: str
    title: str
    problem: dict
    problem_zh: str
    analysis: str
    flowchart: str
    code: dict
    errors: dict


ANALYZE_PROMPT = """你是一位资深算法教练，正在为力扣（LeetCode）学习者撰写题解。

题目信息：
- 标题：{title}
- 难度：{difficulty}
- 标签：{tags}
- 题目链接：{url}

题目原文：
{content}

{fetch_note}

请输出一份**中文**的算法解析，包含以下小节（用 Markdown 标题组织）：
1. ## 题目概述 —— 用自己的话复述题意与输入输出
2. ## 思路分析 —— 解题的核心思路、为什么这样做、关键观察
3. ## 算法步骤 —— 分步骤描述算法过程（可直接对应流程图）
4. ## 复杂度分析 —— 时间复杂度和空间复杂度，并简要说明理由
5. ## 边界情况 —— 需要特别注意的输入与易错点
6. ## 举一反三 —— 同类题目的变体或延伸

要求：逻辑清晰、循序渐进，让初学者能看懂；不要贴完整代码（代码由其他模块负责）。
"""

FLOWCHART_PROMPT = """你是一位算法可视化专家。请为下面的力扣算法题生成一张 **Mermaid flowchart** 流程图，
描述该算法从输入到输出的完整执行流程（包括关键判断分支、循环与边界处理）。

题目：{title}（{difficulty}）
算法解析参考：
{analysis}

要求：
1. 使用 `flowchart TD` 语法，节点文字用中文，简洁准确（每个节点不超过 15 个字）。
2. 用菱形节点表示判断（如 `是否满足条件{{"..."}}`），矩形表示操作，圆角矩形表示开始/结束。
3. 必须包含：开始 → 初始化 → 主逻辑（含循环/分支）→ 返回结果 → 结束。
4. 所有节点文本一律用双引号包裹，例如：`A["初始化哈希表"]`、`B{{"补数是否存在?"}}`、`C(["结束"])`。
5. 节点文本中**不要**使用方括号 [ ]、圆括号 ( )、花括号 {{ }}、等号 =、尖括号 < > 等特殊符号（必要时用中文文字描述，例如用“下标i”代替 [i]）。
6. 只输出 Mermaid 代码，放在 ```mermaid 代码块中，不要输出任何解释文字。
"""

CODE_PROMPT = """你是一位严谨的算法工程师，为力扣题目生成可直接运行的题解代码。

题目：{title}（{difficulty}）
题目链接：{url}

题目原文：
{content}

{fetch_note}

算法思路（供参考，实现必须与之一致）：
{analysis}

请严格按照以下格式输出三个语言的代码（不要输出任何额外解释）：

## Python3
```python
# 代码（含必要注释，函数签名与 LeetCode 模板一致）
```

## Java
```java
// 代码（含必要注释，类与函数签名与 LeetCode 模板一致）
```

## C++
```cpp
// 代码（含必要注释，函数签名与 LeetCode 模板一致）
```
"""


TRANSLATE_PROMPT = """你是一位专业翻译。请把下面的力扣（LeetCode）题目信息翻译成**简体中文**，
并整理为清晰的结构化文本，严格按照以下格式输出（不要输出其他内容）：

题目描述：
（中文翻译的题目描述，保留数学符号与代码标识符原样）

示例：
示例 1：
输入：...
输出：...
（解释：...，如有）

示例 2：
输入：...
输出：...

约束：
- ...
- ...

题目原文（英文）：
{content}

注意：
1. 输入/输出中的数组、变量名、函数名等代码标识符保持英文原样；
2. 如果有“进阶/Follow up”说明，翻译后在末尾追加“进阶：...”小节；
3. 如果原文没有示例或约束，就省略对应小节。
"""


def _call_llm(llm, prompt: str) -> str:
    """调用 LLM，失败时重试一次。"""
    try:
        resp = llm.invoke(prompt)
        return (resp.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] LLM 调用失败，重试: {exc}")
        resp = llm.invoke(prompt)
        return (resp.content or "").strip()


def _extract_mermaid(text: str) -> str:
    """从 LLM 输出中提取 mermaid 代码块；没有代码块则整体作为 mermaid 处理。"""
    blocks = re.findall(r"```mermaid\s*\n(.*?)```", text, re.S)
    if blocks:
        return blocks[-1].strip()
    # 宽松匹配：任意 fenced code block
    blocks = re.findall(r"```(?:mermaid)?\s*\n(.*?)```", text, re.S)
    if blocks:
        return blocks[-1].strip()
    return text.strip()


# ---------------- Mermaid 消毒 ----------------

def _quote_mermaid_text(text: str) -> str:
    """给节点文本加双引号并转义内部引号；已加引号的保持不变。"""
    text = text.strip()
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return text
    return '"' + text.replace('"', '#quot;') + '"'


def _find_matching(s: str, start: int, open_ch: str, close_ch: str) -> int:
    """从 start 起找到与 open_ch 配对的 close_ch 下标（支持嵌套）。"""
    depth = 0
    for idx in range(start, len(s)):
        if s[idx] == open_ch:
            depth += 1
        elif s[idx] == close_ch:
            depth -= 1
            if depth == 0:
                return idx
    return -1


def _quote_node_texts(line: str) -> str:
    """把行内所有节点定义（ID[...] ID{...} ID((...)) ID([...]) ID>...]）的文本加引号。"""
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if ch.isascii() and (ch.isalnum() or ch == "_"):
            j = i
            while j < n and line[j].isascii() and (line[j].isalnum() or line[j] == "_"):
                j += 1
            ident = line[i:j]
            k = j
            while k < n and line[k] == " ":
                k += 1
            if k < n and line[k] in "[{(>":
                shape = line[k]
                if shape == "(":
                    if k + 1 < n and line[k + 1] == "(":
                        close = _find_matching(line, k + 1, "(", ")")
                        if close != -1 and close + 1 < n and line[close + 1] == ")":
                            out.append(f"{ident}(({_quote_mermaid_text(line[k+2:close])}))")
                            i = close + 2
                            continue
                    elif k + 1 < n and line[k + 1] == "[":
                        close = _find_matching(line, k + 1, "[", "]")
                        if close != -1 and close + 1 < n and line[close + 1] == ")":
                            out.append(f"{ident}([{_quote_mermaid_text(line[k+2:close])}])")
                            i = close + 2
                            continue
                    else:
                        close = _find_matching(line, k, "(", ")")
                        if close != -1:
                            out.append(f"{ident}({_quote_mermaid_text(line[k+1:close])})")
                            i = close + 1
                            continue
                elif shape == "[":
                    close = _find_matching(line, k, "[", "]")
                    if close != -1:
                        out.append(f"{ident}[{_quote_mermaid_text(line[k+1:close])}]")
                        i = close + 1
                        continue
                elif shape == "{":
                    close = _find_matching(line, k, "{", "}")
                    if close != -1:
                        out.append(f"{ident}{{{_quote_mermaid_text(line[k+1:close])}}}")
                        i = close + 1
                        continue
                elif shape == ">":
                    close = _find_matching(line, k, ">", "]")
                    if close != -1:
                        out.append(f"{ident}>{_quote_mermaid_text(line[k+1:close])}]")
                        i = close + 1
                        continue
            out.append(ident)
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def sanitize_mermaid(code: str) -> str:
    """清洗 LLM 生成的 Mermaid 代码：给所有节点文本加引号，避免特殊字符导致语法错误。"""
    lines: list[str] = []
    for raw in (code or "").splitlines():
        line = raw.strip()
        if not line or re.match(r"^(flowchart|graph|subgraph|end|style|classDef|class |%%|direction)\b", line):
            lines.append(raw)
            continue
        lines.append(_quote_node_texts(line))
    return "\n".join(lines)


def _extract_code(text: str) -> dict:
    """解析 `## 语言` + 代码块的输出，返回 {语言: 代码}。"""
    result: dict = {}
    pattern = re.compile(
        r"##\s*(Python3|Python|Java|C\+\+|Cpp)\s*\n```(?:\w+)?\s*\n(.*?)```", re.S
    )
    for m in pattern.finditer(text):
        lang, code = m.group(1), m.group(2).rstrip()
        key = {"Python3": "Python3", "Python": "Python3", "Java": "Java", "C++": "C++", "Cpp": "C++"}[lang]
        result[key] = code
    # 兜底：如果完全没解析出来，保留原始输出供前端展示
    if not result and text.strip():
        result["Python3"] = text.strip()
    return result


def _problem_context(state: AgentState) -> tuple[str, str]:
    """返回 (content_text, fetch_note)。抓取失败时提示模型自行补全。"""
    problem = state.get("problem") or {}
    content = problem.get("content_text") or ""
    if problem.get("source") == "llm":
        note = (
            "【注意】无法从力扣在线抓取本题原文，请根据你的知识补全题目描述。"
            "如果对题目细节不确定，请明确标注你的假设，并给出最可能的解法。"
        )
    else:
        note = ""
    return content, note


# ---------------- 节点实现 ----------------

def fetch_node(state: AgentState) -> dict:
    slug = state.get("slug")
    problem = leetcode.fetch_problem(slug) if slug else None
    if problem is None:
        problem = leetcode.fallback_problem(slug or "", state.get("url", ""))
    return {"problem": problem, "title": problem["title"]}


def translate_node(state: AgentState, llm) -> dict:
    """把抓取的英文题目信息翻译整理成结构化中文（供“题目信息”标签页展示）。"""
    problem = state.get("problem") or {}
    content = problem.get("content_text") or ""
    if not content:
        return {"problem_zh": ""}
    prompt = TRANSLATE_PROMPT.format(content=content)
    return {"problem_zh": _call_llm(llm, prompt)}


def analyze_node(state: AgentState, llm) -> dict:
    problem = state.get("problem") or {}
    content, note = _problem_context(state)
    prompt = ANALYZE_PROMPT.format(
        title=problem.get("title", state.get("title", "")),
        difficulty=problem.get("difficulty", "未知"),
        tags=", ".join(problem.get("tags") or []),
        url=problem.get("url", state.get("url", "")),
        content=content or "（题目原文缺失）",
        fetch_note=note,
    )
    return {"analysis": _call_llm(llm, prompt)}


def flowchart_node(state: AgentState, llm) -> dict:
    prompt = FLOWCHART_PROMPT.format(
        title=state.get("title", ""),
        difficulty=(state.get("problem") or {}).get("difficulty", "未知"),
        analysis=state.get("analysis", "（暂无解析）"),
    )
    raw = _call_llm(llm, prompt)
    return {"flowchart": sanitize_mermaid(_extract_mermaid(raw))}


def code_node(state: AgentState, llm) -> dict:
    problem = state.get("problem") or {}
    content, note = _problem_context(state)
    prompt = CODE_PROMPT.format(
        title=problem.get("title", state.get("title", "")),
        difficulty=problem.get("difficulty", "未知"),
        url=problem.get("url", state.get("url", "")),
        content=content or "（题目原文缺失）",
        fetch_note=note,
        analysis=state.get("analysis", "（暂无解析）"),
    )
    return {"code": _extract_code(_call_llm(llm, prompt))}


def run_pipeline(url: str, set_stage: Optional[StageCallback] = None) -> dict:
    """执行完整 agent 工作流，返回包含全部产物的字典。"""
    slug = leetcode.extract_slug(url)
    if not slug:
        raise ValueError(f"无法从链接中解析题目：{url}")

    def stage(name: str, msg: str = ""):
        if set_stage:
            set_stage(name, msg)

    llm = create_llm()
    errors: dict = {}

    builder = StateGraph(AgentState)
    builder.add_node("fetch", fetch_node)
    builder.add_node("translate", lambda s: translate_node(s, llm))
    builder.add_node("analyze", lambda s: analyze_node(s, llm))
    builder.add_node("flowchart", lambda s: flowchart_node(s, llm))
    builder.add_node("code", lambda s: code_node(s, llm))
    builder.set_entry_point("fetch")
    builder.add_edge("fetch", "translate")
    builder.add_edge("translate", "analyze")
    builder.add_edge("analyze", "flowchart")
    builder.add_edge("flowchart", "code")
    builder.add_edge("code", END)
    graph = builder.compile()

    initial: AgentState = {"url": url, "slug": slug}
    stage("fetch", "正在从力扣获取题目信息…")

    # 用 graph.stream 逐节点执行并实时上报进度。
    # 默认 stream_mode="updates"：每个 chunk 是 {节点名: 该节点的增量状态更新}。
    # 把每个节点的增量更新合并进 final_state，即得到完整最终状态。
    final_state: AgentState = {}
    try:
        for chunk in graph.stream(initial, {"recursion_limit": 20}):
            for node_name, update in chunk.items():
                if isinstance(update, dict):
                    final_state.update(update)
                if node_name == "fetch":
                    stage("translate", "正在翻译整理中文题目信息…")
                elif node_name == "translate":
                    stage("analyze", "算法分析 agent 正在撰写解析…")
                elif node_name == "analyze":
                    stage("flowchart", "流程图 agent 正在绘制算法流程…")
                elif node_name == "flowchart":
                    stage("code", "代码 agent 正在生成多语言题解…")
                elif node_name == "code":
                    stage("done", "生成完成，正在保存记录…")
    except Exception as exc:  # noqa: BLE001
        # 某个节点失败时，用已累积的状态兜底，不让整个流程白跑
        errors["graph"] = str(exc)

    problem = final_state.get("problem") or leetcode.fallback_problem(slug, url)
    if problem.get("source") == "llm":
        errors["fetch"] = "无法在线抓取题目原文，已回退为模型根据知识生成"

    result = {
        "url": url,
        "slug": slug,
        "title": final_state.get("title") or problem["title"],
        "problem": problem,
        "problem_zh": final_state.get("problem_zh", ""),
        "analysis": final_state.get("analysis", ""),
        "flowchart": final_state.get("flowchart", ""),
        "code": final_state.get("code", {}),
        "errors": errors,
    }
    return result
