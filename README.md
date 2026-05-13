# 📚 LEExtractor — Systematic Literature Review Toolkit

**Research topic → Scoping → Multi-database search → Citation tracing → PRISMA → PDF**

LEExtractor implements the **gold-standard systematic literature review methodology** (Gusenbauer 2024 + TARCiS + PRISMA 2020). Given a research topic, it automatically executes the complete review pipeline — from field scoping through multi-database keyword search, iterative citation tracing, bibliographic coupling / co-citation discovery, title/abstract screening, PRISMA 2020 flow diagram generation, and one-click PDF download.

## Features

**4-Phase Gold-Standard Workflow:**
1. **Scoping** — Broad field landscape exploration: topic clusters, key journals, key authors, publication timeline
2. **Systematic Search** — Multi-database keyword search (Semantic Scholar + OpenAlex + arXiv + Crossref) with TF-IDF relevance scoring
3. **Snowballing** — TARCiS-aligned iterative forward+backward citation tracing until saturation, plus bibliographic coupling and co-citation similar paper discovery
4. **PRISMA 2020** — Title/abstract screening (manual accept/maybe/reject or auto by relevance threshold), auto-generated PRISMA flow diagram (Mermaid), batch PDF download, CSV/RIS export

**Other:**
- Journal Impact Factors — 300+ journals (JCR 2023 hardcoded) + OpenAlex dynamic estimation
- Preprint support via arXiv native API
- PDF download — 3-tier fallback: OpenAccess → arXiv → Sci-Hub (sci-hub.se/.st/.ru)
- SQLite disk cache with 24h TTL for API responses
- Streamlit GUI with 4-tab workflow interface
- MCP server for AI assistant integration (Claude Desktop / Cursor)

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

| Tab | What you do |
|-----|-------------|
| **1. Scoping** | Enter topic + research direction → see field landscape |
| **2. Systematic Search** | Configure + run multi-database search → review ranked results |
| **3. Snowballing** | Run citation tracing + find similar papers → review discoveries |
| **4. PRISMA** | Screen papers → generate PRISMA flow diagram → download PDFs |

## MCP Server

Configure in `claude_desktop_config.json`:

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

### Tools

| Tool | Description |
|------|-------------|
| `literature_review_search` | Full 4-phase systematic review workflow |
| `snowball_from_seeds` | Forward+backward citation tracing from seed DOIs |
| `find_similar_papers` | Bibliographic coupling + co-citation analysis |
| `download_paper` | Download PDF by DOI or title |
| `batch_download` | Download multiple papers by DOI list |

## Project Structure

```
litsearch/
├── models.py          # Paper, Author, CitationNetwork, SearchResult
├── sources.py         # S2 + OpenAlex + arXiv + Crossref API clients + ImpactFactorLookup
├── filters.py         # TF-IDF relevance scoring, deduplication, noise filtering
├── cache.py           # SQLite disk cache with TTL
├── engine.py          # NetworkX DiGraph, PageRank, Louvain communities, pyvis HTML
├── search.py          # LiteratureReviewWorkflow: 4-phase orchestrator
├── snowball.py        # SnowballEngine: TARCiS iterative citation tracing
├── similar.py         # SimilarPaperFinder: bibliographic coupling + co-citation
├── prisma.py          # PRISMATracker: PRISMA 2020 pipeline + Mermaid flow diagram
├── path_miner.py      # EvolutionPathMiner (legacy)
├── downloader.py      # PaperDownloader: Sci-Hub / arXiv / OA PDF fallback
├── export.py          # CSV, JSON, RIS, Mermaid export
├── __init__.py        # Package exports
app.py                 # Streamlit GUI (4-tab interface)
server.py              # FastMCP server (5 tools)
requirements.txt       # Dependencies
```

## Architecture

```
topic → scoping (field landscape: clusters, journals, authors, timeline)
     → systematic search (multi-database: S2 + OpenAlex + arXiv + Crossref)
     → snowballing (forward + backward citation tracing, TARCiS)
     → similar papers (bibliographic coupling + co-citation)
     → PRISMA screening → PRISMA 2020 flow diagram → PDF download
```

**Methodology references:**
- Gusenbauer (2024): *The best search strategies for systematic reviews*
- TARCiS statement (2024): *Citation searching for systematic reviews*
- PRISMA 2020: *Preferred Reporting Items for Systematic Reviews and Meta-Analyses*

## Data Sources

| Source | Purpose | Rate Limit |
|--------|---------|------------|
| Semantic Scholar | Primary search, citations, references | 100 req/5min |
| OpenAlex | Deep search, citation completeness, IF proxy | ~10 req/s |
| arXiv | Preprint search and PDF | ~1 req/3s |
| Crossref | DOI resolution, journal metadata | 50 req/s |
| Sci-Hub | PDF for paywalled papers | Use responsibly |

## Dependencies

```
networkx>=3.0          # Citation graph analysis
streamlit>=1.50        # GUI framework
fastmcp>=3.0           # MCP server framework
scikit-learn>=1.3      # TF-IDF relevance scoring
pyvis>=0.3             # Interactive network visualization
matplotlib>=3.7        # Publication timeline charts
requests>=2.28         # HTTP client
lxml>=5.0              # XML parsing (arXiv, Sci-Hub)
beautifulsoup4>=4.12   # HTML parsing (Sci-Hub)
```

## Author

**hchow26zijinport** · [@hchow26zijinport](https://github.com/hchow26zijinport) · he/him

## License

MIT
