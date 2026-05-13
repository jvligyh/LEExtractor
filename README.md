# 🧬 LEExtractor — Literature Evolution Extractor

**Research topic → knowledge evolution path → key paper PDFs**

LEExtractor is a tool for **literature review writing** and **technology trajectory analysis**. Given a research topic, it automatically traces the intellectual lineage of ideas — from foundational work to state-of-the-art — by mining citation flow across time, identifying pivotal papers at each evolutionary stage, and providing one-click PDF downloads. Built for researchers who need to quickly map a field's conceptual genealogy before writing.

> *"How did we get from backpropagation to GPT-4? What are the inflection points?"* — LEExtractor answers this in seconds.

## Features

- **Evolution Path Mining** — extracts backbone knowledge evolution chains (e.g. ML → CNN → RNN → Transformer → LLM) by analyzing citation flow across time windows
- **Two Search Modes**:
  - ⚡ **Fast** — broad shallow search (~100 papers), quick evolution overview
  - 🔬 **Comprehensive** — deep multi-source search (~500 papers), full reference mining
- **Multi-Source** — Semantic Scholar + OpenAlex + arXiv + Crossref (all free, no API keys)
- **Journal Impact Factors** — 300+ journals hardcoded (JCR 2023) + OpenAlex dynamic estimation
- **Preprint Support** — arXiv API native integration
- **PDF Download** — 3-tier fallback: OpenAccess → arXiv → Sci-Hub
- **Streamlit GUI** — interactive timeline visualization, paper cards, batch download
- **MCP Server** — AI assistant integration (Claude Desktop / Cursor)

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Launch GUI
streamlit run app.py

# Or run MCP server
python server.py
```

## GUI

Open `http://localhost:8501` after launching:

1. Enter a research topic (e.g. "plant phenotyping deep learning")
2. Select mode: Fast or Comprehensive
3. Click **探索演化路径**
4. Browse the evolution timeline with hub papers per era
5. Download individual PDFs or batch download all hub papers

## MCP Server

Configure in Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "litsearch": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `evolution_search` | Discover knowledge evolution path for a topic |
| `download_paper` | Download PDF by DOI or title |
| `batch_download` | Download multiple papers by DOI list |

## Architecture

```
topic → multi-source search → time-window grouping → hub identification
    → cross-era citation flow → backbone path extraction → evolution chain
    → PDF download (Sci-Hub / arXiv / OA)
```

## Data Sources

| Source | Purpose | Rate Limit |
|--------|---------|-----------|
| Semantic Scholar | Primary search, citations, references | 100 req/5min |
| OpenAlex | Deep search, citation completeness, IF | ~10 req/s |
| arXiv | Preprint search and PDF | ~1 req/3s |
| Crossref | DOI validation, journal metadata | 50 req/s |
| Sci-Hub | PDF for paywalled papers | Use responsibly |

## Author

**Wise instone3** · [@Wise instone3](https://github.com/Wise instone3) · he/him

Bio: LLM development

## License

MIT
