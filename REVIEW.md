# LEExtractor 代码评审报告

> 历史评审：本文件保留原有分析。本轮又发现并修复了运行、计数与缓存问题；最新交付范围及验证结果以「优化说明_版本对照与验收.md」为准。

对象：`github.com/26Wesly3/LEExtractor` @ master（`Rebuild to 4-phase systematic review workflow (v0.3.0)`，8c1a5fb）
规模：约 4,200 行 Python，`litsearch/` 包 14 个模块 + Streamlit GUI + FastMCP server
评审日期：2026-10-03

---

## 一、总体判断

**项目立意很好**：把系统性文献综述（Gusenbauer 2024 + TARCiS + PRISMA 2020）工程化成一条可复现的流水线，四阶段划分、PRISMA 计数、Mermaid 流程图、MCP 暴露——方向是对的，模块切分也清晰（sources / filters / snowball / similar / prisma / downloader 职责分明）。

**但当前版本基本跑不通**：核心的 4 个阶段里有 3 个存在「静默失败」——代码不报错，只是永远返回空结果或把全部文献判为不相关。这些问题都是 API 契约细节级别的错误，不是架构问题，因此可修、且已修。

评级：**架构 B / 实现 C- / 可运行性 D（修复前）→ B（修复后）**

---

## 二、致命缺陷（已修复）

### P0-1 · Snowballing 实际上永远返回 0 —— Semantic Scholar 端点拼错

`SemanticScholarSource.get_citations/get_references` 直接把 `paper_id` 拼进路径：

```python
url_base = f"{S2_BASE}/paper/{paper_id}/citations"
```

而 `_paper_from_s2()` 里 `paper_id = doi or data["paperId"]` —— **只要论文有 DOI，`Paper.id` 就是 DOI**。S2 不接受裸 DOI，必须写成 `DOI:10.xxxx`。

实测：

```
GET /paper/10.1103/PhysRevLett.76.4051/citations   → 404
GET /paper/DOI:10.1145/3065386/citations           → 200 (+ data)
```

结果：绝大多数种子论文走 `/paper/{DOI}/...` → 404 → `break` → 返回空列表 → 第三阶段「引文追溯」产出恒为 0，且没有任何报错。

**修复**：新增 `s2_paper_id()` 归一化函数，前缀 `DOI:`。

---

### P0-2 · OpenAlex 检索整条链路失败 —— `abstract` 字段已从 API 移除

`OpenAlexSource.search_papers()` 的 `select` 里带了 `abstract`。OpenAlex 现在只提供 `abstract_inverted_index`，带 `abstract` 会直接 400：

```json
{"error":"Invalid query parameters error.",
 "message":"abstract is not a valid select field. Valid fields for select are: ..."}
```

异常被 `except → break` 吞掉，于是：**OpenAlex 这个「深度检索」数据源实际返回 0 条**，而且所有 OpenAlex 论文的摘要都是空的（TF-IDF 相关性打分也因此退化——没有摘要就只能靠标题）。

**修复**：改用 `abstract_inverted_index`，新增 `_reconstruct_abstract()` 还原成文本；`OA_SELECT` 常量统一维护字段列表。

---

### P0-3 · 自动筛选把 100% 的文献判为「不相关」

`PRISMATracker.add_papers()` 创建记录时从不复制 `paper.relevance_score`：

```python
self.records[key] = PRISMARecord(paper=p, source=source)   # relevance_score 保持 0.0
```

而 `auto_screen()` 的判断是 `record.relevance_score >= threshold`（默认 0.15）。0.0 >= 0.15 永远为假 → **全部 REJECT → PRISMA 报告里 `studies_included = 0`**，`get_screening_queue()` 的相关度排序也失去意义。

**修复**：`add_papers` 同步写入 `relevance_score`（并对已存在记录取较大值）。

---

### P0-4 · 相似论文发现（文献耦合 / 共被引）恒为空

- `by_bibliographic_coupling()` 依赖 `seed.reference_ids`，而 S2 的检索字段里没有 `references` → 该字段永远是空 list → `signature_refs` 为空 → 直接 `return []`
- `by_cocitation()` 依赖 `citer.reference_ids`，同理为空

**修复**：`SimilarPaperFinder` 增加 `_ensure_references()`，缺失时按需回源拉取，并加了 `api_budget`（默认 10 次）防止请求爆炸。

---

## 三、合规问题（已处理）

### P1-1 · Sci-Hub 抓取

`downloader.py` 内置三个 Sci-Hub 镜像，对付费文献抓 PDF。这属于版权侵权（多数司法辖区），且镜像域名频繁失效、在机构网络下基本不可用。

**处理**：整段移除，改为合法 OA 链路 **arXiv → OpenAlex OA → Unpaywall**（Unpaywall 是出版方授权的 OA 定位服务，需配置邮箱 `LEEXTRACTOR_UNPAYWALL_EMAIL`）。拿不到 OA 版本就明确返回「不可用」，而不是去影子图书馆拿。同时 `server.py`/`app.py`/README 中的 Sci-Hub 字样一并清理。

> 如果你确实需要保留这一层（例如机构有合法授权通道），告诉我，我可以改成默认关闭 + 显式开关的形式。

---

## 四、中等问题（已修复）

| # | 问题 | 说明 | 修复 |
|---|------|------|------|
| M1 | 年份硬编码为 2026 | `search.py` 的 `2026 - years_back`、`year_to=2026` 散落 6 处，跨年后整个时间窗失效 | 新增 `litsearch/config.py`，`current_year()` / `year_from_years_back()` |
| M2 | 控制台入口点不存在 | `pyproject.toml` 声明 `litsearch.server:main`，但 `server.py` 在仓库根目录，安装后 `litsearch-mcp` 直接报 ImportError | `server.py` 移入包内，根目录保留 shim 兼容 `python server.py` |
| M3 | 版本号不一致 | `pyproject` 写 0.1.0，`__init__.py` 写 0.3.0 | 统一为 0.3.0，描述同步更新 |
| M4 | OpenAlex 引文过滤非法 | DOI 走 `cites:{https://openalex.org/works?filter=doi:...}`，实测 `'doi:10.1145/3065386' is not a valid OpenAlex ID` | 新增 `_resolve_oa_id()`：DOI → `W…` ID 再查 |
| M5 | OpenAlex 参考文献过滤过期 | `openalex_id:` 已废弃 | 改为 `ids.openalex:W1\|W2` |
| M6 | Snowballing 去重大小写不一致 | `all_papers[sp.id]` 存原始大小写，查询用 `.lower()`，DOI 含大写时去重失效 | 统一 `paper_key()` |
| M7 | OpenAlex 检索结果从不写缓存 | 只读不写，每次全量重查；Crossref 同样 | 补 `_cache_set` + `_oa_to_dict()` |
| M8 | 下载的可能是 HTML 错误页 | 只判断 `len(content) > 10000`，200 + 大体积 HTML 会被存成 `.pdf` | 校验 `%PDF-` 魔数 / content-type |
| M9 | 影响因子估算值伪装成真实 IF | 非 JCR 期刊用 `cited/works*0.15` 硬算，UI 显示成 `IF: 8.3` | 估算值显示为 `IF: ~8.3 (est.)` |
| M10 | `batch_download(max_workers=3)` 参数无效 | 声明了却串行执行 | 改成明确语义的 `delay_seconds` |
| M11 | GUI 每次渲染新建 `ImpactFactorLookup()` | 每次都开 SQLite 连接 | 缓存进 `st.session_state` |
| M12 | MCP server 在 fastmcp 4.x 下直接崩溃 | `FastMCP(name, description=...)` 的 `description` 已被移除 → `TypeError` | 改用 `instructions=`；已用 stdio 握手验证 5 个工具全部注册 |
| M13 | OpenAlex 无 DOI 记录时崩溃 | `data.get("doi", "")` 在字段为 `null` 时返回 `None` → `'NoneType' has no attribute 'replace'` | 改为 `data.get("doi") or ""` |

---

## 五、遗留问题 → 第二轮已全部解决

### 5.1 PRISMA 两阶段拆分 ✅

原来 `full_text_assessed` 直接等于 ACCEPT 数、`full_text_excluded` 恒为 0。现在：

- `PRISMARecord` 拆成两套字段：`screening_decision/screening_reason`（标题摘要）与
  `full_text_retrieved/full_text_decision/full_text_reason`（全文评估）
- 新增 `ScreeningStage` 枚举，`screen_paper()`、`get_screening_queue()`、`auto_screen()`
  全部接受 `stage` 参数；`mark_full_text_retrieved()` 记录"取不到全文"这一种排除
- `PRISMAReport` 新增 `reports_sought` / `reports_not_retrieved` / `full_text_assessed` /
  `full_text_excluded` / `full_text_exclusion_reasons` / `duplicates_removed`，
  `to_flow_dict()` 的 identification 改为 PRISMA 2020 口径（database / citation searching / other）
- Mermaid 图重画为标准 PRISMA 2020 形状（含 sought / not retrieved / assessed / excluded / included）
- **兼容性**：没做过任何全文决策时 `full_text_stage_enabled=False`，`studies_included`
  退回标题摘要的 ACCEPT 数，旧行为不变

实测：`full_text_excluded=5`，原因分布 `{'全文无法获取': 2, '结局指标不符': 3}`，`studies_included=5`（不再等于初筛通过数 21）。

### 5.2 S2 限流与 API key ✅

- 新增 `_request()`：请求前按配额自适应限速（有 key 0.2s / 无 key 1.2s），
  429 时按 `Retry-After` 或指数退避（3→6→12s）重试，最多 3 次；超限后返回最后一次响应交由调用方降级，
  **不会像原来那样 `continue` 空转**
- 移除 S2 各方法里残留的 `if 429: sleep(5); continue`（会死循环）
- `s2_stats()` 统计请求数/被限流次数，GUI 在检索后弹告警告知"结果可能不完整"
- 支持 `.env`（`config.load_env_file()`）+ 环境变量；GUI 侧边栏显示密钥状态并可直接粘贴保存
- `S2_API_KEY` 通过 `semantic_scholar_api_key()` 注入请求头

实测：53 次请求中 12 次被限流，全部自动重试后仍拿到结果（未配 key 的极端情况）。

### 5.3 状态持久化与断点续跑 ✅

- 新增 `litsearch/persistence.py`：`ReviewState` ↔ JSON 全量序列化（论文、雪球结果、
  相似文献、PRISMA 两阶段决策），原子写入（`.tmp` + `os.replace`）
- GUI 每次阶段完成、每次筛选决策后自动落盘 `.sessions/autosave.json`；
  下次启动自动恢复并提示"已恢复上次进度（x 分钟前）"，侧边栏可丢弃
- `run_snowballing(on_round=...)` 回调：每轮结束触发保存 + 进度条，中断后可在下一轮继续
- `.gitignore` 已排除 `.sessions/`、`.env`

实测：序列化后恢复 18 篇文献、两阶段决策完整；无头渲染 GUI 无异常，指标显示正确。

---

## 五·旧、上一轮遗留的其他建议 → 第三轮已全部解决

### 5.4 legacy 模块清理 ✅

删除 `path_miner.py`（307 行）、`engine.py`（205 行）、`LiteratureExplorer` 兼容层共约 580 行死代码。
删除前逐一确认无引用（`app.py` / `server.py` / `scripts/` / `tests/` 均未使用），
连带从 `pyproject.toml` 移除四个已无使用者的依赖：`networkx`、`pyvis`、`lxml`、`beautifulsoup4`。

`models.py` 的 `CitationNetwork` 保留：它是纯数据类（不 import networkx），且 `SearchResult.network` 引用了它。

### 5.5 错误处理分级 ✅

新增 `litsearch/diagnostics.py`。核心是按**可操作性**分类，而不是按类型：

| 类别 | 含义 | 触发 | 日志级别 |
|------|------|------|---------|
| `RateLimitedError` | 429，配额不足 | 429 | warning |
| `TransientSourceError` | 网络抖动/5xx，**重试有用** | 5xx、Timeout | warning |
| `PermanentSourceError` | 请求本身写错了，**重试无用** | 400/401/403/405/409/413/422 | **error** |
| `NotFoundError` | 404，属预期结果 | 404 | info |
| `ParseError` | 响应解析失败，我方 bug | KeyError/ValueError | **error** |

- `raise_for_data()` 替代 `resp.raise_for_status()`（13 处），保留响应体与 URL 便于定位
- `log_source_failure()` 替代 18 处 `except Exception: logger.warning(...)`
- 契约类错误现在走 `logger.error` 并在 GUI 顶部弹红色横幅 —— 这正是 P0 缺陷当年被掩盖的原因
- 影响因子查询属于纯展示信息，降级到 `logger.debug`，避免噪音淹没真问题

### 5.6 相关性打分升级 ✅

TF-IDF 余弦对短查询区分度差，改成**三路混合**：

1. **词级 TF-IDF**（权重 0.45）—— 字面重合
2. **字符 3-5 gram**（0.30，用 `char_wb`）—— 抓形态变体：`phenotype` / `phenotyping` / `phenotypic`
3. **查询词覆盖率**（0.25）—— 长度无关，短查询的救星

三者 min-max 归一化后加权融合。**失效的信号会自动降权**，不会拖垮总分（原来的实现在词表为空时整批归零）。

同时提供 `calibrate_threshold()`：给几篇已知结论的文献打标，取「相关最低分」与「不相关最高分」的中点作为阈值，替代拍脑袋的 0.15。GUI 第 4 页签新增「标定筛选阈值」，含得分分布直方图和得分构成表（可解释每一分来自哪个信号）。

**已知上限**：词汇法无法识别语义相关但字面不重合的文献（实测「Vision transformers for crop trait estimation」因只命中一个查询词而排在第 4 位）。要突破需换 embedding 相似度，属下一步。

---

## 六、本次改动清单

```
新增  litsearch/config.py          年份/路径/密钥等环境变量集中管理
新增  tests/test_offline.py        15 个离线回归用例
新增  scripts/smoke.py             真实 API 端到端冒烟
新增  REVIEW.md                    本报告
移动  server.py → litsearch/server.py（根目录保留 shim）
修改  litsearch/sources.py         S2 DOI 前缀、OpenAlex 全部修复、缓存、IF 标注
修改  litsearch/snowball.py        paper_key 去重、年份默认值
修改  litsearch/prisma.py          relevance_score 透传 + id/doi 索引
修改  litsearch/similar.py         按需补拉 references + API 预算
修改  litsearch/downloader.py      移除 Sci-Hub，改 Unpaywall/OA，PDF 魔数校验
修改  litsearch/search.py          年份动态化
修改  app.py / server.py / pyproject.toml / README.md
```

---

## 六之二、第三轮实测结果（最新）

主题 `plant phenotyping deep learning`，max_papers=20，1 轮 snowball，未配置 S2 key：

```
Snowballing           rounds=1  discovered=118
Auto-screen (stage 1) screened=139  excluded_title_abstract=69  reports_sought=70
Stage 2 (full text)   full_text_assessed=10  full_text_excluded=5
                      原因: 全文无法获取×2, 结局指标不符×3
最终纳入              studies_included=5
持久化                save → restore 15 篇，match=True
S2 请求               47 次，其中 10 次 429
```

打分验证（7 篇构造样本，查询 "deep learning for plant phenotyping"）：

```
总分   词    字   覆盖  标题
1.000 1.00 1.00 1.00  Deep learning for plant phenotyping in wheat
0.789 0.68 0.78 1.00  Plant phenotyping using deep convolutional networks
0.449 0.40 0.49 0.50  A survey of supervised learning in plant science
0.163 0.05 0.26 0.25  Vision transformers for crop trait estimation   ← 词汇法上限
0.014 0.00 0.05 0.00  Soil organic carbon sequestration under cover cropping
0.008 0.00 0.03 0.00  CRISPR knockout screens in zebrafish
0.000 0.00 0.00 0.00  Marine snow flux in the Southern Ocean
```

4 篇相关全部排在 3 篇不相关之前，完全分离。标定流程给出的阈值 0.089（原默认 0.15）。

- `python -m pytest tests -q` → **34 passed**
- GUI 无头渲染 → 无异常；诊断面板正确捕获注入的契约错误并弹红色横幅；标定器 5 个打标框正常

## 六之三、第二轮实测结果

主题 `plant phenotyping deep learning`，max_papers=25，1 轮 snowball，**未配置 S2 key**（最坏情况）：

```
Auto-screen (stage 1)   screened=142  excluded_title_abstract=121  reports_sought=21
Stage 2 (full text)     full_text_assessed=10  full_text_excluded=5  ← 不再是 0
                        原因: 全文无法获取×2, 结局指标不符×3
最终纳入                studies_included=5  （初筛通过 21 → 全文后 5）
持久化                  save → restore 18 篇，两阶段决策完整匹配
S2 请求                 53 次，其中 12 次 429（全部自动重试后仍拿到结果）
GUI 无头渲染            无异常；指标 Screened=3 / Excluded=1 / Sought=2 / Included=2
```

- `python -m pytest tests -q` → **22 passed**（第一轮 15 个 + 两阶段/持久化/429 重试 7 个）
- `streamlit run app.py` → 200，`AppTest` 无头渲染无异常

---

## 六之三、第一轮实测结果

主题 `plant phenotyping deep learning`，max_papers=30，1 轮 snowball，未配置 S2 key：

```
Scoping           papers=51, journals=15, authors=15, clusters=16
                  有摘要 42/51（修复前 OpenAlex 论文摘要全空）
Systematic search found=51, top relevance 0.284
Snowballing       rounds=1, discovered=70        （修复前恒为 0）
Similar papers    10 条（文献耦合 5 + 共被引 5）   （修复前恒为 0）
Auto-screen       accepted=56 / screened=125      （修复前恒为 0）
PRISMA            identification total=125, included=56
```

其他验证：

- `python -m pytest tests -q` → **15 passed**
- `streamlit run app.py` → 启动正常，`/_stcore/health` 返回 200
- MCP stdio 握手 → `initialize` 正常，`tools/list` 返回 5 个工具
- S2 `/paper/DOI:10.1145/3065386/citations` → 10 条（修复前 404）
- OpenAlex `_resolve_oa_id('10.1145/3065386')` → `W2163605009`，`cites:` 查询 10 条

---

## 七、怎么跑

```bash
# 1. 装依赖
pip install -r requirements.txt
# 2.（强烈建议）配 S2 key，否则检索会大量 429
export S2_API_KEY=...
# 可选：OA 定位 + 下载目录
export LEEXTRACTOR_UNPAYWALL_EMAIL=you@example.com
export LEEXTRACTOR_DOWNLOAD_DIR=/path/to/pdfs

# 3. 冒烟
python scripts/smoke.py "plant phenotyping deep learning" --max-papers 30

# 4. GUI
streamlit run app.py

# 5. 测试
python -m pytest tests -q
```
