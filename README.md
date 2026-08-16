# 🧠 力扣算法学习助手 (LeetCode Algorithm Learning Assistant)

输入任意力扣题目链接（Hot 100 或任意题目），由 **LangChain / LangGraph + DeepSeek** 搭建的多 Agent
工作流自动生成：

1. 📝 **算法解析** — 中文题解：题目概述、思路分析、算法步骤、复杂度、边界情况、举一反三
2. 🔄 **算法流程图** — Mermaid 流程图（浏览器实时渲染）
3. 💻 **多语言代码** — Python3 / Java / C++ 三种语言的 LeetCode 模板题解
4. 📚 **历史记录** — 已生成的题目自动保存，可随时回看、重新生成、删除；支持开新页面问新题

## 架构

```
用户输入题目链接
      │
      ▼
┌─────────────────────────────┐
│  FastAPI 后端 (backend/)     │
│  ┌────────────────────────┐ │
│  │ LangGraph Agent 工作流  │ │
│  │  fetch_node ──► analyze │ │
│  │   ──► flowchart ──► code│ │
│  └────────────────────────┘ │
│  LeetCode GraphQL 抓取器     │
│  DeepSeek (deepseek-chat)    │
│  JSON 历史记录存储 (data/)    │
└─────────────────────────────┘
      │
      ▼
┌─────────────────────────────┐
│  前端 (frontend/)            │
│  输入链接 · 进度展示 · 标签页  │
│  Mermaid 渲染 · 代码高亮      │
│  历史侧栏 · 深链 ?slug=       │
└─────────────────────────────┘
```

- **backend/graph.py** — LangGraph `StateGraph`：4 个节点（抓取 → 分析 → 流程图 → 代码），
  每个节点是一个独立 Agent（专用提示词 + DeepSeek LLM），逐节点上报进度，单节点失败不影响整体。
- **backend/leetcode.py** — 通过 LeetCode 官方 GraphQL API 抓取题目原文/难度/标签/模板，
  支持 `leetcode.com` 与 `leetcode.cn`；抓取失败自动回退为「模型知识生成」。
- **backend/history.py** — 按题目 slug 去重的 JSON 持久化。
- **backend/app.py** — FastAPI：`POST /api/generate`（后台任务）→ `GET /api/jobs/{id}`（轮询进度）→
  历史 CRUD + 静态前端托管。

## 快速开始

前置依赖：**PostgreSQL**（数据存储）。新环境部署步骤：

```bash
# 0. 初始化数据库（新环境只需一次）
createdb leetcode_guide
psql -U <你的用户> -d leetcode_guide -f db/init.sql   # 创建表结构

# 1. 配置 API Key 与数据库连接（已包含 .env，按需修改）
cp .env.example .env
#    .env 需包含：
#      DEEPSEEK_API_KEY=sk-xxx
#      DATABASE_URL=postgresql://localhost:5432/leetcode_guide

# 2. 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. 启动服务（默认端口 8001，可用 PORT 环境变量修改）
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001
# 或
./start.sh
```

打开浏览器访问 **http://127.0.0.1:8001**

> 从旧 JSON 存储迁移：`data/history.json` 是旧版存储（现仅作备份），
> 迁移命令：`.venv/bin/python -m backend.migrate_json_to_pg`

## 使用说明

0. **用户系统**：首次使用请先注册（需邮箱验证）。注册后自动认领历史遗留数据；
   未配置 SMTP 时（开发模式），注册响应与服务器日志会直接给出验证链接。

1. 在输入框粘贴力扣题目链接（`leetcode.com` 或 `leetcode.cn` 均可），点击「⚡ 生成解析」；
2. 等待 Agent 工作流执行（约 30~90 秒），可实时看到 5 个阶段进度；
3. 生成完成后在四个标签页查看：**题目信息 / 算法解析 / 流程图 / 代码**；
4. 流程图支持一键复制 Mermaid 源码；代码支持 Python3/Java/C++ 切换与复制；
5. 左侧「历史记录」保存所有问过的题目，点击即可回看；🗑 可删除；
6. **开新页面问新题**：直接新开一个浏览器标签页访问同一地址即可（互不影响），
   也可用 `http://127.0.0.1:8001/?slug=two-sum` 深链直达某题记录。

## 项目结构

```
leetcode-guide/
├── backend/
│   ├── app.py          # FastAPI 主应用
│   ├── graph.py        # LangGraph 多 Agent 工作流
│   ├── leetcode.py     # LeetCode GraphQL 抓取器
│   ├── llm.py          # DeepSeek LLM 工厂
│   ├── config.py       # 配置（.env）
│   └── history.py      # 历史记录存储
├── frontend/
│   ├── index.html      # 页面
│   ├── app.js          # 交互逻辑
│   └── style.css       # 样式
├── data/history.json   # 历史记录（自动生成）
├── .env                # DeepSeek API Key
├── requirements.txt
└── start.sh
```

## 说明

- 生成过程调用 DeepSeek API（默认模型 `deepseek-chat`），会产生 token 费用；
- 题目原文优先从力扣在线抓取，抓取失败时由模型根据知识补全（页面会有标注）；
- 所有文件均可自由修改：更换模型、调整提示词、增加语言等都在 `backend/` 下完成。

## VIP 会员与支付宝支付

- **hot100 免费**：共享目录（只读），所有注册用户可查看
- **VIP 权限**：新增题目、批量生成、删除/编辑题目、分组管理需开通 VIP
- **开通方式**：侧栏「开通 VIP」→ 选择套餐（月卡 ¥9.9 / 年卡 ¥99）→ 支付宝支付
- 生产环境配置（`.env`）：
  ```
  ALIPAY_APP_ID=你的支付宝应用 app_id
  ALIPAY_PRIVATE_KEY=应用私钥（RSA2）
  ALIPAY_PUBLIC_KEY=支付宝公钥
  ALIPAY_NOTIFY_URL=https://你的域名/api/vip/alipay/notify
  ALIPAY_RETURN_URL=https://你的域名/?vip=ok
  ```
- 未配置支付宝时为**开发模式**：点击支付直接模拟成功（重定向回 `/?vip=ok`），便于本地联调
