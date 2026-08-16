# 🧠 力扣算法学习助手 (LeetCode Algorithm Learning Assistant)

输入任意力扣题目链接（Hot 100 或任意题目），由 **LangChain / LangGraph + DeepSeek** 搭建的多 Agent
工作流自动生成算法解析、动画演示、流程图与多语言代码。

## ✨ 功能总览

| 功能 | 说明 |
|---|---|
| 📥 单条 / 批量生成 | 输入链接自动生成：中文题目、算法解析、逐步动画演示、流程图、Python/Java/C++ 代码、答题模板 |
| 🆓 hot100 免费浏览 | 游客可查看全部 100 道热题（只读）；登录后管理自己的题目 |
| 🗂️ 分组 / 分类 / 难度 / 搜索 | 题目按算法分类、难度、自定义分组管理，支持关键词搜索 |
| 🎬 动画演示 | 具体示例逐步推演（数组/指针/哈希表可视化，可播放） |
| 📋 答题模板库 | 21 类算法固定 Python 模板，支持标签筛选与搜索 |
| 📝 题目心得 | 每道题可写 Markdown 心得（富文本预览） |
| 👤 用户系统 | 注册 / 登录 / 邮箱验证（SMTP，未配置时开发模式直出验证链接） |
| 👑 VIP / 计费 | 普通 1 元/题，VIP 0.1 元/题；扫码捐赠 ≥1 元自助开通永久 VIP（诚信制） |
| 💰 支持本站 | 微信/支付宝收款码自愿捐赠，含维护运维费用说明页 |
| 🌙/☀️ 主题 | 暗夜/白日两套独立 CSS，一键切换 |
| 🐘 存储 | PostgreSQL（`db/init.sql` 建库建表脚本） |

## 🏗️ 技术架构

```
浏览器前端 (frontend/：原生 HTML/JS + Mermaid + highlight.js + marked)
      │  REST API
FastAPI 后端 (backend/)
  ├── LangGraph 多 Agent 工作流 (graph.py)
  │     抓取题目 → 中文翻译 → 算法解析 → 动画演示 → 流程图 → 代码
  ├── LeetCode GraphQL 抓取器 (leetcode.py)  含中文标题与插图
  ├── 用户系统 (auth.py)   注册/登录/邮箱验证/会话
  ├── VIP 计费 (vip.py)    永久VIP/次数充值/自助开通
  └── 历史存储 (history.py) PostgreSQL（共享目录 + 按用户隔离）
数据库：PostgreSQL（users / sessions / records / groups / vip_orders / user_notes）
```

## 🚀 一键部署

### 方式一：Docker（推荐，最省事）

```bash
# 1. 准备配置
cp .env.example .env        # 填入 DEEPSEEK_API_KEY（必填）
# 2. 一键启动（自动拉起 PostgreSQL + 应用，自动建表）
docker compose up -d --build
# 3. 打开
open http://127.0.0.1:8001
```

- 自带 PostgreSQL 16，数据持久化在 `pgdata` 卷
- 收款码目录 `./frontend/qrcodes` 已挂载进容器，上传后即时生效
- 停止：`docker compose down`（加 `-v` 删除数据卷）

### 方式二：脚本部署（本机已有 Python + PostgreSQL）

```bash
./deploy.sh          # 安装依赖 + 初始化数据库 + 启动服务
./deploy.sh --setup  # 只做环境准备
./deploy.sh --start  # 只启动服务
```

### 方式三：手动部署

```bash
# 0. 初始化数据库（新环境只需一次）
createdb leetcode_guide
psql -d leetcode_guide -f db/init.sql

# 1. 配置
cp .env.example .env   # 填入 DEEPSEEK_API_KEY、DATABASE_URL 等

# 2. 依赖与启动
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8001
```

## ⚙️ 配置项（.env）

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | | 默认 `deepseek-chat` |
| `DATABASE_URL` | ✅ | PostgreSQL 连接串，如 `postgresql://localhost:5432/leetcode_guide` |
| `APP_BASE_URL` | | 部署地址，用于生成验证链接等 |
| `SMTP_HOST/PORT/USER/PASS/FROM` | | 邮箱验证；留空 = 开发模式（验证链接打印日志并返回前端） |
| `ADMIN_EMAIL` | | 管理员邮箱（备用 VIP 管理） |
| `ALIPAY_*` / `PAYJS_*` | | 官方/第三方支付参数（当前为扫码捐赠自助开通模式，可留空） |

## 💰 计费与 VIP

| 身份 | 生成价格 | 获取方式 |
|---|---|---|
| 普通用户 | **1 元/题**（10 次） | 注册即默认 |
| VIP | **0.1 元/题**（1 次） | 右上角「💖 升级 VIP」→ 扫码捐赠 ≥1 元 → 点「我已支付」自动开通（永久，诚信制） |

- 1 次 = 0.1 元；捐赠 1 元 = 10 次
- 生成按题扣次（单条/批量），次数不足自动提示
- 管理员（`ADMIN_EMAIL`）可手动开通 VIP / 充值次数（备用）

## 📍 收款码放置

把微信/支付宝收款码图片放入（**不入 git 仓库**，已 gitignore）：

```
frontend/qrcodes/wechat.png   或  wechat.jpg
frontend/qrcodes/alipay.png   或  alipay.jpg
```

## 📚 使用说明

1. 右上角注册/登录（邮箱验证；未配置 SMTP 时弹窗直接给验证链接）
2. 输入区「⚡ 单条生成 / 🚀 批量生成」粘贴力扣链接（`leetcode.com` 或 `leetcode.cn`）
3. 生成后查看：顶部固定题目信息 · 算法解析 · 🎬 动画演示 · 🔄 流程图（可缩放）· 💻 代码 · 📋 答题模板 · 📝 心得
4. 左侧：分组 / 算法分类 / 难度筛选 + 搜索；点击题目整行切换
5. 「📋 算法模板库」按算法找模板；「💖 升级 VIP」页含计费与运维费用说明

## 📁 项目结构

```
leetcode-guide/
├── backend/
│   ├── app.py            # FastAPI 主应用（接口 + 前端托管）
│   ├── graph.py          # LangGraph 多 Agent 工作流
│   ├── leetcode.py       # LeetCode 抓取（中文标题/插图）
│   ├── auth.py           # 用户系统（注册/登录/邮箱验证）
│   ├── vip.py            # VIP 计费/自助开通/备用支付通道
│   ├── history.py        # PostgreSQL 存储（共享+用户隔离）
│   ├── db.py             # 数据库连接
│   └── templates.py      # 21 类算法模板
├── frontend/             # 前端（index.html / app.js / style.css / 双主题 CSS）
│   └── qrcodes/          # 收款码（gitignore，自行上传）
├── db/init.sql           # 建库建表脚本（幂等）
├── deploy.sh             # 一键部署脚本
├── Dockerfile / docker-compose.yml
└── requirements.txt
```

## ❓ 常见问题

- **邮箱验证收不到**：未配置 SMTP 时为开发模式，验证链接会显示在注册弹窗并打印到服务器日志
- **生成提示余额不足**：普通 1 元/题、VIP 0.1 元/题，按次扣费；升级 VIP 或联系管理员充值
- **收款码不显示**：确认文件在 `frontend/qrcodes/` 且名为 `wechat.png` / `alipay.png`（或 .jpg）
- **Docker 部署**：`docker compose up -d --build`，`docker compose logs -f app` 看日志
