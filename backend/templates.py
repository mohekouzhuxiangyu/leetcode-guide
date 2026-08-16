"""各类算法的固定答题模板库（Python 骨架）。

每个模板包含：
- name: 模板名
- when: 适用场景（什么时候用这个模板）
- python: 可套用的 Python 代码骨架
"""

# 单调栈模板（「栈」与「单调栈」两个分类共用同一骨架）
_MONOTONIC_STACK_PY = '''class Solution:
    def solve(self, nums):
        n = len(nums)
        ans = [0] * n
        stack = []                           # 维护单调递减栈（存下标）
        for i, x in enumerate(nums):
            while stack and nums[stack[-1]] < x:   # 弹出条件按题目调整
                j = stack.pop()              # 栈顶的“下一个更大元素”就是 x
                ans[j] = i - j
            stack.append(i)
        return ans
'''

CATEGORY_TEMPLATES: dict[str, dict] = {
    "哈希表": {
        "name": "哈希表查重 / 配对",
        "when": "需要 O(1) 查询某个值是否出现过、找配对（两数之和）、统计频率",
        "python": '''class Solution:
    def solve(self, nums, target):
        seen = {}  # 值 -> 下标（或频率）
        for i, x in enumerate(nums):
            need = target - x            # 需要的配对值
            if need in seen:             # 先查后存，避免重复使用元素
                return [seen[need], i]
            seen[x] = i
        return []
''',
    },
    "双指针": {
        "name": "双指针（相向 / 同向）",
        "when": "有序数组找和、回文判断、链表快慢指针、去重",
        "python": '''class Solution:
    def solve(self, nums, target):
        nums.sort()
        left, right = 0, len(nums) - 1   # 相向双指针
        while left < right:
            s = nums[left] + nums[right]
            if s == target:
                return [left, right]
            elif s < target:
                left += 1                # 和太小，左指针右移
            else:
                right -= 1               # 和太大，右指针左移
        return []
''',
    },
    "滑动窗口": {
        "name": "滑动窗口",
        "when": "连续子数组/子串问题：求满足条件的最长/最短/个数（无重复字符最长子串、最小覆盖子串）",
        "python": '''class Solution:
    def solve(self, s):
        window = {}                      # 窗口内字符 -> 出现次数
        left = 0
        ans = 0
        for right, ch in enumerate(s):   # 右指针扩张
            window[ch] = window.get(ch, 0) + 1
            while self._invalid(window):  # 不满足条件时收缩左指针
                window[s[left]] -= 1
                left += 1
            ans = max(ans, right - left + 1)
        return ans

    def _invalid(self, window):          # 判断窗口是否合法（按题目实现）
        return False
''',
    },
    "二分查找": {
        "name": "二分查找",
        "when": "有序数组/满足单调性的搜索、求满足条件的最小/最大值（搜索旋转排序数组、爱吃香蕉的珂珂）",
        "python": '''class Solution:
    def solve(self, nums, target):
        left, right = 0, len(nums) - 1   # 左闭右闭
        while left <= right:
            mid = left + (right - left) // 2   # 防溢出
            if nums[mid] == target:
                return mid
            elif nums[mid] < target:
                left = mid + 1
            else:
                right = mid - 1
        return -1
''',
    },
    "贪心": {
        "name": "贪心",
        "when": "局部最优能推出全局最优：区间调度、跳跃游戏、买卖股票、分发饼干",
        "python": '''class Solution:
    def solve(self, intervals):
        intervals.sort(key=lambda x: x[1])   # 按结束时间排序
        count = 0
        end = float("-inf")
        for s, e in intervals:
            if s >= end:                     # 贪心选择：能选就选
                count += 1
                end = e
        return count
''',
    },
    "动态规划": {
        "name": "动态规划（1D / 2D）",
        "when": "有重叠子问题+最优子结构：爬楼梯、打家劫舍、背包、最长递增子序列、编辑距离",
        "python": '''class Solution:
    def solve(self, nums):
        n = len(nums)
        dp = [0] * n                         # dp[i] = 以 i 结尾的最优值
        for i in range(n):
            dp[i] = 1                        # 初始：单个元素
            for j in range(i):
                if nums[j] < nums[i]:        # 状态转移
                    dp[i] = max(dp[i], dp[j] + 1)
        return max(dp)
''',
    },
    "回溯": {
        "name": "回溯（组合/排列/子集）",
        "when": "需要枚举所有可能：组合、全排列、子集、N 皇后、分割回文串",
        "python": '''class Solution:
    def solve(self, candidates, target):
        res = []
        path = []

        def dfs(start, remaining):
            if remaining == 0:               # 找到一组解
                res.append(path[:])
                return
            for i in range(start, len(candidates)):
                x = candidates[i]
                if x > remaining:            # 剪枝
                    continue
                path.append(x)               # 做选择
                dfs(i, remaining - x)        # 递归（可重复选则传 i）
                path.pop()                   # 撤销选择

        dfs(0, target)
        return res
''',
    },
    "深度优先搜索": {
        "name": "深度优先搜索（DFS）",
        "when": "树/图的遍历、岛屿问题、连通分量、路径搜索",
        "python": '''class Solution:
    def solve(self, grid):
        rows, cols = len(grid), len(grid[0])
        visited = set()
        DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        def dfs(r, c):
            if (r, c) in visited or not (0 <= r < rows and 0 <= c < cols):
                return
            if grid[r][c] == 0:              # 剪枝条件按题目调整
                return
            visited.add((r, c))
            for dr, dc in DIRS:
                dfs(r + dr, c + dc)

        count = 0
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1 and (r, c) not in visited:
                    count += 1
                    dfs(r, c)
        return count
''',
    },
    "广度优先搜索": {
        "name": "广度优先搜索（BFS）",
        "when": "最短路径、层序遍历、二叉树最小深度、单词接龙",
        "python": '''from collections import deque

class Solution:
    def solve(self, start, target):
        q = deque([start])
        visited = {start}
        step = 0
        while q:
            for _ in range(len(q)):          # 按层遍历
                node = q.popleft()
                if node == target:
                    return step
                for nxt in self._neighbors(node):   # 按题目生成邻居
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append(nxt)
            step += 1
        return -1

    def _neighbors(self, node):
        return []
''',
    },
    "链表": {
        "name": "链表（哑结点 + 双指针）",
        "when": "链表翻转、合并有序链表、删除倒数第 N 个、环形链表、链表中点",
        "python": '''class Solution:
    def solve(self, head):
        dummy = ListNode(0)                  # 哑结点简化边界
        dummy.next = head
        slow = fast = dummy                  # 快慢指针
        while fast and fast.next:
            slow = slow.next
            fast = fast.next.next
        # 此时 slow 为中点/前驱，按题目继续操作
        return dummy.next
''',
    },
    "栈": {
        "name": "单调栈",
        "when": "下一个更大/更小元素、柱状图中最大矩形、每日温度、接雨水",
        "python": _MONOTONIC_STACK_PY,
    },
    "单调栈": {
        "name": "单调栈",
        "when": "下一个更大/更小元素、柱状图中最大矩形、每日温度、接雨水",
        "python": _MONOTONIC_STACK_PY,
    },
    "堆": {
        "name": "堆（优先队列）",
        "when": "Top-K 问题、合并 K 个有序链表、数据流中位数、贪心+堆",
        "python": '''import heapq

class Solution:
    def solve(self, nums, k):
        heap = []                            # 小顶堆维护 Top-K
        for x in nums:
            heapq.heappush(heap, x)
            if len(heap) > k:
                heapq.heappop(heap)
        return heap                          # 堆内即最大的 k 个
''',
    },
    "前缀和": {
        "name": "前缀和 + 哈希表",
        "when": "子数组和/积的计数（和为 K 的子数组）、二维前缀和、差分",
        "python": '''class Solution:
    def solve(self, nums, k):
        prefix = 0
        count = 0
        seen = {0: 1}                        # 前缀和 -> 出现次数
        for x in nums:
            prefix += x
            count += seen.get(prefix - k, 0) # 找到之前出现过的 prefix-k
            seen[prefix] = seen.get(prefix, 0) + 1
        return count
''',
    },
    "并查集": {
        "name": "并查集（Union-Find）",
        "when": "连通分量、冗余连接、岛屿数量、等式方程的可满足性",
        "python": '''class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):                       # 路径压缩
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):                   # 按大小合并
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return True
''',
    },
    "分治": {
        "name": "分治（归并排序思想）",
        "when": "归并排序、逆序对、最大子数组和、多数元素",
        "python": '''class Solution:
    def solve(self, nums):
        def merge_sort(arr):
            if len(arr) <= 1:
                return arr
            mid = len(arr) // 2
            left = merge_sort(arr[:mid])     # 分：拆成子问题
            right = merge_sort(arr[mid:])
            return self._merge(left, right)  # 治：合并结果

        return merge_sort(nums)

    def _merge(self, a, b):
        i = j = 0
        res = []
        while i < len(a) and j < len(b):     # 合并两个有序数组
            if a[i] <= b[j]:
                res.append(a[i]); i += 1
            else:
                res.append(b[j]); j += 1
        res.extend(a[i:]); res.extend(b[j:])
        return res
''',
    },
    "位运算": {
        "name": "位运算",
        "when": "只出现一次的数字、2 的幂、位计数、异或性质",
        "python": '''class Solution:
    def solve(self, nums):
        xor = 0
        for x in nums:
            xor ^= x                         # a^a=0，落单的数留下
        return xor
''',
    },
    "拓扑排序": {
        "name": "拓扑排序（Kahn 算法）",
        "when": "课程表、依赖关系、有向无环图排序",
        "python": '''from collections import deque

class Solution:
    def solve(self, numCourses, prerequisites):
        indeg = [0] * numCourses
        graph = [[] for _ in range(numCourses)]
        for a, b in prerequisites:           # b -> a
            graph[b].append(a)
            indeg[a] += 1
        q = deque([i for i in range(numCourses) if indeg[i] == 0])
        order = []
        while q:
            u = q.popleft()
            order.append(u)
            for v in graph[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        return order if len(order) == numCourses else []   # 非空则有环
''',
    },
    "排序": {
        "name": "排序（内置 + 自定义键）",
        "when": "按某种规则排序：区间合并、按频率排序、最大数拼接",
        "python": '''class Solution:
    def solve(self, items):
        # 内置排序 + 自定义 key（按题目调整）
        items.sort(key=lambda x: (x[0], x[1]))
        merged = []
        for s, e in items:
            if not merged or s > merged[-1][1]:
                merged.append([s, e])        # 新区间
            else:
                merged[-1][1] = max(merged[-1][1], e)   # 合并区间
        return merged
''',
    },
    "递归": {
        "name": "递归（树的遍历）",
        "when": "二叉树前/中/后序遍历、树的深度、对称、最近公共祖先",
        "python": '''class Solution:
    def solve(self, root):
        res = []

        def dfs(node):
            if not node:
                return
            # 前序：res.append(node.val)
            dfs(node.left)
            # 中序：res.append(node.val)
            dfs(node.right)
            # 后序：res.append(node.val)

        dfs(root)
        return res
''',
    },
    "字符串": {
        "name": "字符串（双指针 / 哈希）",
        "when": "回文串、变位词、子串匹配、压缩字符串",
        "python": '''class Solution:
    def solve(self, s):
        s = list(s)                          # 字符串不可变，转列表操作
        left, right = 0, len(s) - 1
        while left < right:                  # 原地反转/交换
            s[left], s[right] = s[right], s[left]
            left += 1
            right -= 1
        return "".join(s)
''',
    },
    "数学": {
        "name": "数学",
        "when": "质数、快速幂、最大公约数、阶乘、数字反转",
        "python": '''class Solution:
    def solve(self, x, n):
        # 快速幂 x^n
        res = 1
        base = x
        while n:
            if n & 1:
                res *= base
            base *= base
            n >>= 1
        return res
''',
    },
}


def get_template(category: str) -> dict:
    """按类别返回模板；无匹配返回 None。"""
    return CATEGORY_TEMPLATES.get(category)
