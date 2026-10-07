# v0.6.0 本轮优化

以群里 v0.5.0 为基础，统一跨来源身份与发现记录，修正缓存、年份过滤、扩展恢复、BC / CC 预算、下载与 PRISMA 计数，重整中英文 Streamlit 导航和筛选交互；新增有依据的引文图、证据包与 MCP 探索接口。修正 setuptools 包发现，避免安装时误收测试产物目录。完整版本对照和测试结论见「优化说明_版本对照与验收.md」。

以下为原有 v0.5.0 改动说明，保留作历史记录，其「结果可信」等结论不替代本轮验证，也不构成科研质量 benchmark。

# 改动说明：从最初版本到 v0.5.0

> **基线说明**：本文以 `git` 提交 `8c1a5fb`（v0.3.0，"Rebuild to 4-phase systematic review workflow"）为「最初版本」，\
> 即本次改造开始前的状态。git 历史中还有一个更早的提交 `692ade3`，那是作者自己在 v0.3.0 中重构掉的老版本，\
> 不在本文对比范围内。
>
> 一句话概括：**最初版本能跑起来，但四个核心功能里有三个静默返回空结果**——不报错、不崩溃，\
> 只是结果恒为 0。本次改造修掉了这些，并把「能跑」推进到「结果可信、可追溯、可复现」。

---

## 一、最重要的结论

最初版本最大的问题不是缺少功能，而是**失败时没有声音**。以下四个功能在最初版本里都在正常执行，\
但结果永远是空的：

| 功能                | 最初版本表现       | 根本原因                                      | 现在         |
| ----------------- | ------------ | ----------------------------------------- | ---------- |
| 引文追溯（snowballing） | 恒发现 0 篇      | S2 端点要求 `DOI:10.xxx` 前缀，代码传裸 DOI → 全部 404 | 实测发现 118 篇 |
| OpenAlex 检索       | 整条链路失败、摘要全空  | 请求里带了 `abstract` 字段，该字段已从 API 移除 → 400    | 恢复正常       |
| 自动筛选              | 100% 判为「不相关」 | `add_papers` 没传递 `relevance_score`，分数全是 0 | 正常筛选       |
| 相似文献              | 恒为空          | 依赖 `reference_ids`，但 S2 检索不返回该字段          | 实测返回 10 条  |

这四处都属于「静默失败」：程序不报错，日志也不明显，使用时会以为是自己检索词没写好。\
**本次改造最核心的价值就是把这几处变成可见的**。

---

## 二、致命缺陷修复（第一轮）

### P0-1 · 引文追溯端点拼错

`get_citations` / `get_references` 直接把 `Paper.id`（通常是裸 DOI）拼进\
`/paper/{id}/citations`。Semantic Scholar 要求 `DOI:10.xxxx` 形式，裸 DOI 一律 404。\
现在统一走 `s2_paper_id()` 做规范化。

### P0-2 · OpenAlex 字段失效

`select` 参数里的 `abstract` 已被 OpenAlex 移除（只保留 `abstract_inverted_index`），\
带它整个请求 400。现在改为请求 `abstract_inverted_index`，再用 `_reconstruct_abstract()` 还原成文本。

### P0-3 · 相关性分数丢失

`PRISMATracker.add_papers` 不复制 `paper.relevance_score`，导致 `auto_screen` 时所有分数为 0，\
全部被判为不相关。现在分数正确透传，并建立 id/doi 双索引。

### P0-4 · 相似文献依赖缺失字段

`similar.py` 依赖 `reference_ids` 计算文献耦合，但 S2 检索接口不返回该字段。\
改为按需补拉 references，并加了 API 预算控制。

### P0-5 · MCP 服务启动即崩

`FastMCP(name, description=...)` 在 fastmcp 4.x 下抛 TypeError。改为 `instructions=` 参数。

### P0-6 · 年份硬编码

6 处写死 2026。抽到 `litsearch/config.py` 的 `current_year()` 统一处理。

### P0-7 · 入口点指向不存在的函数

`pyproject.toml` 的 `litsearch-mcp = litsearch.server:main` 无法导入（`server.py` 在包外）。\
已将 `server.py` 移入包内，根目录保留 shim。

---

## 三、合规处理

最初版本的 PDF 下载器第一优先源是 **Sci-Hub**（`downloader.py` 开头就写着\
`PDF downloader with multi-source fallback: Sci-Hub → OA → arXiv`，内置 sci-hub.se / .st / .ru 域名列表）。

这属于在多数司法辖区构成版权侵权的行为，且镜像站极不稳定。**已整层移除**，\
替换为纯合法来源：arXiv → OpenAlex OA → Unpaywall（需配置邮箱）。\
拿不到全文时明确报告「没有」，而不是去影子图书馆抓。

---

## 四、第二轮：三个架构级问题

### 4.1 PRISMA 拆成两阶段 ✅

最初版本把「标题摘要排除」和「全文评估」混为一谈，`full_text_excluded` 恒为 0，\
只能算"PRISMA-shaped"，达不到投稿要求。

现在引入 `ScreeningStage` 枚举（TITLE_ABSTRACT / FULL_TEXT），两阶段各有独立的决策字段，\
补齐了 PRISMA 2020 真正要求的 `reports_sought`、`reports_not_retrieved`、\
`full_text_assessed`、`full_text_excluded` 及排除原因分布，Mermaid 流程图重画为标准形状。

未做过全文决策时自动退回旧行为，不破坏既有流程。

### 4.2 S2 限流治理 ✅

最初版本无 key 时共享配额极紧，首次检索就大量 429。当时代码里是\
`if 429: sleep(5); continue`，在持续限流时会空转。

现在所有 S2 请求走统一的 `_request()`：按配额自适应限速（有 key 0.2s / 无 key 1.2s），\
429 时优先读 `Retry-After`，否则指数退避（3→6→12s）最多 3 次。\
支持 `.env` 配置，GUI 侧边栏可直接粘贴保存 `S2_API_KEY`，被限流时页面弹黄条警告。

### 4.3 状态持久化 ✅

最初版本进度只存在内存里，浏览器刷新即丢，而一次 3 轮 snowball 要几分钟。

新增 `litsearch/persistence.py`，把整个 `ReviewState` 序列化为 JSON 原子写入\
`.sessions/autosave.json`。每完成一个阶段、每做一次筛选决策都自动存盘，\
下次打开自动恢复。snowball 增加 `on_round` 回调，每轮存盘并显示进度。

---

## 五、第三轮：清理、打分、错误分级

### 5.1 legacy 清理 ✅

删除 `path_miner.py`(307 行)、`engine.py`(205 行)、`LiteratureExplorer` 兼容层，\
共约 580 行死代码（删除前逐一确认无引用）。连带移除 4 个已无使用者的依赖：\
`networkx`、`pyvis`、`lxml`、`beautifulsoup4`。

### 5.2 相关性打分升级 ✅

最初版本是单一 TF-IDF 余弦，对短查询区分度差，且阈值 0.15 没有任何标定依据。

改为三路混合：词级 TF-IDF(0.45) + 字符 3-5gram(0.30) + 查询词覆盖率(0.25)，\
归一化后加权融合，失效信号自动降权。新增 `calibrate_threshold()`：\
给已知结论文献打标，自动算出有依据的阈值。GUI 增加「标定筛选阈值」面板。

### 5.3 错误分级 ✅

最初版本 sources 层遍布 `except Exception: logger.warning(...)`，\
把 400（API 契约错误）和网络抖动同等对待——**这正是上述 P0 缺陷长期没被发现的根本原因**。

新增 `litsearch/diagnostics.py`，按「重试有没有用」分类：\
429→限流 / 5xx+超时→可重试 / 400,401,403,422→参数错误（走 `logger.error`）/ 404→预期内 / 解析失败→我方 bug。\
契约类错误现在会在 GUI 顶部弹红色横幅并列出具体请求。

### 5.4 CI 与 lint ✅

最初版本 `pyproject` 里写了 pytest 依赖但**一个测试用例都没有**，也没有任何 CI。\
现在有 34 个离线测试 + `.github/workflows/ci.yml`（Python 3.10/3.13 × Ubuntu/Windows，ruff + pytest）。

---

## 六、文件级改动清单

### 新增文件

```
litsearch/config.py          环境变量、.env 加载、年份与路径助手
litsearch/persistence.py     会话存盘与恢复
litsearch/diagnostics.py     数据源错误分级与运行诊断
litsearch/prisma.py          （v0.3.0 已有，本次重写）
litsearch/snowball.py        （v0.3.0 已有，本次增强）
litsearch/similar.py         （v0.3.0 已有，本次修复）
tests/test_offline.py        34 个离线回归用例
scripts/smoke.py             真实联网端到端冒烟
.github/workflows/ci.yml     CI 配置
REVIEW.md                    代码评审报告
ONBOARDING.md                新手上手指南
```

### 删除文件

```
litsearch/path_miner.py      307 行，已被新流程取代
litsearch/engine.py          205 行，无任何引用
```

### 修改文件（行数变化）

```
app.py                        +575 / 大幅重写（两阶段筛选、诊断面板、阈值标定）
litsearch/sources.py          +438 / S2 DOI 修复、OpenAlex 重建、限流、错误分级
litsearch/prisma.py           +293 / 两阶段重写
litsearch/filters.py          +289 / 打分算法重写
litsearch/search.py           +149 / 兼容层删除、年份动态化
litsearch/downloader.py       +150 / 移除 Sci-Hub、PDF 魔数校验
litsearch/__init__.py          +36 / 导出清理
pyproject.toml                 +34 / 依赖精简、ruff 与 pytest 配置
```

---

## 七、数字对比

| 指标                   | 最初版本（v0.3.0） | 现在（v0.5.0）                 |
| -------------------- | ------------ | -------------------------- |
| 测试数量                 | **0**        | **34**（全部通过）               |
| lint                 | 无配置          | ruff 全绿                    |
| CI                   | 无            | 3.10/3.13 × Ubuntu/Windows |
| 引文追溯发现量              | **0**        | 118（1 轮）                   |
| 相似文献                 | **0**        | 10                         |
| `full_text_excluded` | 恒为 **0**     | 5（含原因分布）                   |
| 刷新页面                 | 进度丢失         | 自动恢复                       |
| 无 key 时 429          | 首次检索即退化      | 自动退避重试，仍可完成                |
| PDF 来源               | Sci-Hub 优先   | 仅合法 OA 来源                  |
| 依赖数量                 | 9 个          | 6 个                        |

---

## 八、已知的剩余局限

诚实地说，以下问题**尚未解决**：

1. **相关性打分是词汇法**：抓不到「语义相关但字面不重合」的文献。\
   实测「Vision transformers for crop trait estimation」因只命中一个查询词而排在第 4 位。\
   要突破需换成 embedding 相似度（如 sentence-transformers），会引入新依赖和模型下载。
2. **打分是相对值**：分数只在同一次检索内可比，不同检索之间 0.3 的含义不同。\
   所以才需要阈值标定流程，而不是固定阈值。
3. **无 S2 key 时仍会限流**：47 次请求里 10 次 429。配 key 是唯一根治办法。
4. **PDF 只下开放获取**：付费文献不会去影子图书馆拿，会直接报告「没有」。

---

## 九、如何验证改动

```bash
# 离线测试（不联网，秒级）
python -m pytest tests -q          # → 34 passed

# lint
ruff check .                       # → All checks passed

# 真实联网端到端（约 1-2 分钟）
python scripts/smoke.py "plant phenotyping deep learning" --max-papers 20 --rounds 1

# GUI
streamlit run app.py
```
