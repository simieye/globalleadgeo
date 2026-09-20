# 全球鹰 GEO 全球AI推荐系统

**Global Eagle GEO Recommendation & AI Visibility System**
OpenClaw Orchestrator + Agent Cluster + Knowledge Graph + Evidence Graph + Vector RAG + CRM + GEO Analytics

> 面向全球 B2B 企业、产业带、制造商、品牌商与跨境供应商的
> **AI 搜索可见性、实体权威建设、生成式推荐优化与询盘转化基础设施**。
> 不是传统 SEO 工具，而是「产业知识图谱 + AI 搜索 + GEO + Agent + CRM + 商业数据闭环」驱动的全球 B2B AI 获客基础设施。

## 快速启动

```bash
pip3 install -r requirements.txt
./run.sh
# 打开 http://127.0.0.1:8787
```

首次启动会自动灌入演示产业数据（AI GPU 服务器产业带）。控制台点击「重置演示数据」可复原。

## macOS 安装包（DMG）

```bash
./packaging/build_dmg.sh
# 产物：dist/GlobalEagleGEO-1.1.0.dmg（约 3.9 MB）
```

DMG 内容：`GlobalEagleGEO.app` + `使用说明.txt` + `停止服务.command` + `Applications` 快捷方式。

App 为**原生 macOS 窗口应用**（`packaging/macos/native/GlobalEagleGEO.swift`，Swift + WKWebView 编译）：
独立 Dock 图标与菜单栏，界面在原生窗口内加载，外部链接自动跳转默认浏览器，
关闭窗口即停止本地服务。若打包机无 Swift 工具链，脚本自动退化为浏览器版启动器。

- App 内已内置完整源码与**离线 wheel**（fastapi/uvicorn/pydantic 等），首次运行免联网；
  若 wheel 与目标机型 Python 版本不匹配，自动退化为联网安装。
- 依赖环境创建在 `~/Library/Application Support/GlobalEagleGEO/venv`，
  数据写在 `.../GlobalEagleGEO/data`，升级 App 不丢数据。
- 服务地址固定 `127.0.0.1:8787`（可用环境变量 `GEO_PORT` 覆盖），由 App 进程拉起并托管生命周期。
- 未做开发者签名，首次打开需「右键 → 打开」或在 隐私与安全性 中允许。

## 插件：RedditGrow（MCP over HTTP）

把 [RedditGrow](https://redditgrow.ai) 的 Reddit 获客能力接进 GEO 闭环：机会发现 → 询盘管道 → AI 可见性验证。
Reddit 线程既是买家真实提问，也是 ChatGPT / Perplexity / Google 长期引用的信源，与 GEO 的 Evidence First 一致。

接入方式（`redditgrow.ai → Settings → Integrations` 生成 `rg_live_` 开头 API Key，Growth / Agency 套餐）：

```bash
export REDDITGROW_API_KEY=rg_live_xxx            # 或控制台「插件」页保存（写入 Shared Context settings）
export REDDITGROW_WEBHOOK_SECRET=xxx             # 可选，webhook 验签
```

API：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/plugins` | 插件列表与状态 |
| GET | `/api/plugins/redditgrow/status` | 连通配置、工具清单 |
| POST | `/api/plugins/redditgrow/config` | 保存配置（持久化到 settings） |
| POST | `/api/plugins/redditgrow/opportunities` | 查询 Reddit 机会（不入库） |
| POST | `/api/plugins/redditgrow/sync` | 机会 → 询盘（`lead_source=RedditGrow`） |
| POST | `/api/plugins/redditgrow/ai-visibility` | 品牌 AI 可见性评分 |
| POST | `/api/plugins/redditgrow/mentions` | 品牌 / 竞品 Reddit 提及 |
| POST | `/api/plugins/redditgrow/serp` | Reddit 线程 Google SERP 排名 |
| POST | `/api/plugins/redditgrow/reply-draft` | 生成回复草稿（**仅草稿，需人工审核**） |
| POST | `/api/plugins/redditgrow/webhook` | 接收 `opportunity.created`，HMAC-SHA256 验签（头 `X-RedditGrow-Signature`） |

原则：
- 未配置 API Key 时插件返回 `mode='disabled'`，**不产出任何编造数据**；
- 导入的线索一律 `verification_status=unverified`，需人工核验；
- 回复生成只落草稿，遵守 Human-in-the-loop；频率限制 Growth 100 次/小时、Agency 500 次/小时。

## 系统边界与原则（Important）

- **不承诺推荐结果**：系统不承诺任何品牌一定被 ChatGPT / Gemini / Perplexity 等平台推荐。
  GEO Score 只表示「当前证据、实体、内容结构、市场相关性与查询匹配条件下的 AI 可见性优化程度」。
- **Evidence First**：禁止编造认证、客户、销售数据、市场份额、产能、交付能力与第三方背书。
  无法验证的信息一律 `status = unverified`，不得作为核心推荐依据，也不写入 JSON-LD Schema。
- **核验必须真实**：Claim 只有在信源通过真实 HTTP 可达性核验（勾选「联网核验信源」）或经人工审核批准后，
  才会被标记为 `verified`。演示数据中的 `.example.com` 信源为占位示例，必然核验失败。
- **Human-in-the-loop**：认证声明、企业资质、客户案例、销售数据、市场份额、排名声明、
  竞品比较、价格承诺、交付承诺等一律进入人工审核队列。
- **禁词**：禁止无证据的「第一 / 最佳 / 最低价格 / 最大供应商」，禁止贬低竞争对手。

## 架构

```text
用户 Query
  ↓
Global Eagle Orchestrator (OpenClaw)
  ↓
A01 Intent → A02 Market → A03 Query Expansion → A04 Retrieval(Top20)
  ↓
A05 Entity → A06 Evidence Verification → A07 GEO Scoring(100分/8维)
  ↓
A08 Competitor Gap → A09 AI Answer Content → A10 Schema/KG → A11 Localization
  ↓
A12 Visibility Monitoring → A13 Lead/CRM → A14 Analytics → A15 Feedback Learning
  ↓
Human Approval Queue + Audit Log + 统一输出 JSON
```

### GEO Score（100 分）

| 维度 | 分值 |
| --- | --- |
| Evidence Authority 证据权威度 | 25 |
| Query Relevance 查询相关性 | 20 |
| Entity Clarity 实体清晰度 | 15 |
| Content Extractability 可抽取性 | 10 |
| Market Relevance 市场相关性 | 10 |
| Differentiation 差异化 | 10 |
| Citation Coverage 引用覆盖 | 5 |
| Freshness 时效性 | 5 |

## 目录结构

```text
backend/
  main.py              FastAPI 服务入口（全部 API）
  orchestrator.py      OpenClaw Orchestrator 19 步调度
  seed.py              演示产业数据（AI GPU 服务器产业带）
  agents/              A01 ~ A15 智能体
  core/                store / evidence_graph / entity_graph / vector_index /
                       approval / audit / web_research / llm
  data/                运行时 JSON 持久化（Shared Context）
frontend/              控制台（原生 HTML/CSS/JS，无外部依赖）
```

## 可选外部连接器（未配置时系统自动降级，绝不返回编造结果）

| 能力 | 环境变量 |
| --- | --- |
| 联网检索 | `TAVILY_API_KEY` 或 `SERPER_API_KEY` |
| AI 引擎真实探针 | `OPENAI_API_KEY` / `PERPLEXITY_API_KEY` / `ANTHROPIC_API_KEY` |
| LLM 内容润色 | `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` |

未配置时：检索返回 `mode=disabled`，AI 探针返回 `mode=simulated`（明确标注为模拟基线，不计入真实指标）。

## 主要 API

```
GET  /api/health                     系统状态与连接器
POST /api/seed?force=true            重置演示数据
GET  /api/context                    Shared Context
POST /api/pipeline/run               运行 GEO 全链路
GET  /api/runs/{id}                  完整统一输出 JSON
GET  /api/claims  POST /api/claims/verify?enable_web=true   证据与核验
GET  /api/approvals  POST /api/approvals/{id}/decision       人工审核
POST /api/monitoring/probe  GET /api/monitoring/dashboard    可见性监测
GET/POST /api/leads  POST /api/leads/{id}/rfq               询盘与 RFQ
GET  /api/analytics  POST /api/feedback                     分析与反馈学习
GET  /api/audit                      审计日志
GET  /api/schema/{entity_id}         JSON-LD
```
