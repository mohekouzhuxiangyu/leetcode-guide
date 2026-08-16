"""算法归类：把力扣官方标签映射为中文算法类别，并选出主类别。"""
from typing import Optional

# 力扣标签 -> 中文算法类别
TAG_CATEGORY = {
    "Hash Table": "哈希表",
    "Two Pointers": "双指针",
    "Sliding Window": "滑动窗口",
    "Dynamic Programming": "动态规划",
    "Binary Search": "二分查找",
    "Backtracking": "回溯",
    "Depth-First Search": "深度优先搜索",
    "Breadth-First Search": "广度优先搜索",
    "Linked List": "链表",
    "Stack": "栈",
    "Monotonic Stack": "单调栈",
    "Heap (Priority Queue)": "堆",
    "Greedy": "贪心",
    "Sorting": "排序",
    "Divide and Conquer": "分治",
    "Bit Manipulation": "位运算",
    "Prefix Sum": "前缀和",
    "Union Find": "并查集",
    "Graph": "图",
    "Topological Sort": "拓扑排序",
    "Trie": "字典树",
    "Queue": "队列",
    "Recursion": "递归",
    "Memoization": "记忆化搜索",
    "Binary Tree": "二叉树",
    "Binary Search Tree": "二叉搜索树",
    "Matrix": "矩阵",
    "Simulation": "模拟",
    "Design": "设计",
    "Data Stream": "数据流",
    "String": "字符串",
    "Math": "数学",
    "Tree": "树",
}

# 主类别优先级：越靠前越优先作为该题的主类别（覆盖更有区分度的算法思想）
CATEGORY_PRIORITY = [
    "动态规划", "贪心", "二分查找", "回溯", "滑动窗口", "双指针", "前缀和",
    "单调栈", "拓扑排序", "并查集", "分治", "位运算", "深度优先搜索", "广度优先搜索",
    "哈希表", "堆", "栈", "链表", "排序", "字典树", "字符串", "数学", "树", "图", "其他",
]


def classify(tags: Optional[list]) -> tuple[str, list]:
    """根据力扣标签返回 (主类别, 全部中文类别列表)。"""
    cats: list[str] = []
    for t in tags or []:
        c = TAG_CATEGORY.get(t)
        if c and c not in cats:
            cats.append(c)
    if not cats:
        return "其他", []
    cats.sort(key=lambda c: CATEGORY_PRIORITY.index(c) if c in CATEGORY_PRIORITY else 99)
    return cats[0], cats
