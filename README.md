# LEExtractor

科研文献发现、引文扩展和证据组织工具。当前版本 **0.6.0** 以群里 v0.5.0 为基础修复运行问题，保留混合词法排序、Snowball、BC / CC、两阶段筛选与状态恢复，并新增可解释发现记录、引文证据图和完整证据包。

这是一轮可运行性与体验改进，尚未实现演进报告所规划的完整 v2.0。具体版本取舍、已修问题与待开发内容见 [优化说明](优化说明_版本对照与验收.md)。

## 启动

需要 Python 3.10 或以上。Windows 可双击 `启动LEExtractor.bat`；首次运行会创建虚拟环境并安装依赖。手动方式：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

访问 [本机界面](http://127.0.0.1:8501)。所有依赖以 `pyproject.toml` 为唯一声明来源，`requirements.txt` 直接安装该项目。

## 使用

1. 在「研究探索」填写关键词和研究问题，直接检索或先做小规模概览。
2. 在「文献结果」按相关度、来源、年份和标题/摘要筛选，并按页查看论文及发现依据。
3. 在「引文扩展」追溯参考文献与后续引用，或使用文献耦合 / 共被引寻找关联论文。每轮统计明确区分返回记录、去重新增、保留量与累计新增，并保存检查点。
4. 在「证据版图」查看当前样本的引文网络、PageRank、社群和有向证据路径。
5. 在「保存与导出」导出 CSV、RIS、BibTeX、会话 JSON 或完整证据包。RIS / BibTeX 可导入 Zotero。

需要系统综述时勾选侧栏的「系统综述模式（PRISMA）」。默认科研探索不要求筛选或制作 PRISMA 报告。全文纳入需要人工评估；未尝试获取、获取失败和已阅读全文分别处理。

中英文界面通过侧栏切换。当前排序仍是词法方法，**不自动翻译，不提供跨语言语义检索**。中文研究问题配英文关键词时会使用英文关键词排序，同时保留中文原始问题。

## 数据源与全文

- 检索：Semantic Scholar、OpenAlex、arXiv。
- Crossref：DOI / 元数据解析，未作为第四主搜索源。
- 全文：直接 PDF、arXiv、OpenAlex 开放获取、Unpaywall。一个链接失败后继续尝试其他可用来源，检查 PDF 文件头与结束标记。

可在界面设置 `S2_API_KEY` 和 `OPENALEX_API_KEY`，或把 `.env.example` 复制为 `.env`。Unpaywall 可通过 `LEEXTRACTOR_UNPAYWALL_EMAIL` 配置联系邮箱。不要把 `.env` 加入版本控制。

API 的实时可用性取决于网络和配额。未配置密钥时，限流可能导致结果不完整；诊断面板会显示原因。拿不到开放全文时可通过机构渠道手动获取，系统不会自动把下载失败当作科研排除理由。

## 离线演示

「研究探索 → 离线演示」可加载模拟文献，并在本机运行模拟引文扩展、筛选、图分析和导出。所有模拟记录都明确标注 **SYNTHETIC DEMO**，不能作为真实科研证据。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\python.exe scripts\mcp_smoke.py
```

测试默认禁止外网，覆盖适配器、身份合并、缓存、雪球恢复、BC / CC 预算、PDF 下载、PRISMA 计数、证据导出和 Streamlit 交互。真实接口探测单独运行：

```powershell
.\.venv\Scripts\python.exe scripts\provider_probe.py
```

每个请求最多等待 12 秒，S2 不重试；结果写入 `artifacts/provider_probe.json`。它验证接口连通与解析，不证明检索召回率或科研结论。

## MCP

```powershell
.\.venv\Scripts\python.exe server.py
```

安装后的入口为 `litsearch-mcp`。配置 MCP 客户端时，使用虚拟环境 Python 的绝对路径和 `server.py` 的绝对路径。

保留 5 个兼容工具，新增 `search_literature`、`explain_paper`、`build_research_landscape`、`get_evidence_path`、`export_research_bundle`。新探索接口不自动筛选或下载全文，返回可传递给后续工具的会话数据。

## 证据包

ZIP 包包含：

```text
AGENT_HANDOFF.md
papers.csv
papers.jsonl
references.ris
references.bib
discovery_trace.jsonl
evidence_graph.json
search_manifest.json
session.json
```

引文边定义为「引用论文 → 被引论文」。没有来源证据的关系不会被补造；图指标描述的是当前样本，不能替代质量评估、创新性判断或完整领域分析。

## 后续开发

Research Intent 自动解析、embedding 语义检索与融合、真实 benchmark、BC / CC 多类型图边、创新性覆盖分析、Zotero 双向同步、机构访问和结构化全文解析仍需后续开发。当前为单用户本机工作流，不是多人共享服务。

`CHANGES.md`、`REVIEW.md` 中旧版评审保留作历史材料；本轮验收以 `优化说明_版本对照与验收.md` 和实际测试结果为准。
