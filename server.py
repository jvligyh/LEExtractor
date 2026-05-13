"""MCP server for Literature Evolution Explorer.

Exposes tools for research topic evolution exploration and PDF download.

Usage:
    python server.py
    # or: fastmcp run server.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP

mcp = FastMCP(
    "Literature Evolution Explorer",
    description="Research topic evolution path discovery with PDF download",
)


# ---------------------------------------------------------------------------
# Tool: evolution_search
# ---------------------------------------------------------------------------


@mcp.tool()
def evolution_search(
    topic: str,
    mode: str = "fast",
    years_back: int = 20,
    max_papers: int = 200,
) -> dict:
    """
    Explore the knowledge evolution path of a research topic.

    Discovers how ideas evolved over time by analyzing citation patterns
    and extracting the backbone evolution chain (e.g., ML→CNN→RNN→Transformer→LLM).

    Use this when you need to: understand how a research field developed,
    find key papers at each stage of evolution, discover paradigm shifts.

    Args:
        topic: Research topic or keywords.
        mode: "fast" (quick overview, ~100 papers) or "comprehensive"
              (deep analysis, ~500 papers).
        years_back: How many years back to search.
        max_papers: Maximum papers to analyze.

    Returns:
        Evolution path with eras, hub papers, and download URLs.
    """
    from litsearch.search import LiteratureExplorer

    explorer = LiteratureExplorer()

    if mode == "fast":
        path = explorer.fast_search(topic, years_back=years_back, max_papers=max_papers)
    else:
        path = explorer.comprehensive_search(topic, years_back=years_back, max_papers=max_papers)

    eras_out = []
    for era in path.eras:
        hubs = []
        for p in era.key_papers:
            dl_url = p.url if p.url and p.url.startswith("http") else None
            hubs.append({
                "title": p.title,
                "year": p.year,
                "venue": p.venue,
                "doi": p.doi,
                "citation_count": p.citation_count,
                "is_preprint": p.source == "arxiv",
                "download_url": dl_url,
                "authors": [a.name for a in p.authors[:3]],
                "abstract_snippet": (p.abstract or "")[:300],
            })
        eras_out.append({
            "era": era.era_label,
            "start_year": era.start_year,
            "end_year": era.end_year,
            "total_papers": era.total_papers,
            "keywords": era.keywords,
            "hub_papers": hubs,
        })

    links_out = []
    for link in path.links:
        links_out.append({
            "from_era": link.from_era,
            "to_era": link.to_era,
            "description": link.description or "",
            "citation_count": link.citation_count,
        })

    return {
        "topic": path.topic,
        "mode": path.coverage,
        "eras": eras_out,
        "evolution_links": links_out,
        "total_papers_analyzed": path.total_papers_analyzed,
        "tip": "Use download_paper(doi) to download a specific paper PDF.",
    }


# ---------------------------------------------------------------------------
# Tool: download_paper
# ---------------------------------------------------------------------------


@mcp.tool()
def download_paper(paper_doi_or_title: str) -> dict:
    """
    Download a paper PDF by DOI or title.

    Tries multiple sources in order: OpenAccess → arXiv → Sci-Hub.

    Args:
        paper_doi_or_title: DOI (e.g. "10.1038/nature12345") or paper title.

    Returns:
        Download result with file path or error.
    """
    from litsearch.sources import SourceManager
    from litsearch.downloader import PaperDownloader

    sources = SourceManager()

    # Resolve to paper
    if paper_doi_or_title.startswith("10."):
        paper = sources.resolve_doi(paper_doi_or_title)
    else:
        papers = sources.search_papers(paper_doi_or_title, limit=1)
        paper = papers[0] if papers else None

    if paper is None:
        return {"error": f"Paper not found: {paper_doi_or_title}"}

    downloader = PaperDownloader()
    filepath = downloader.download_pdf(paper)

    return {
        "title": paper.title,
        "doi": paper.doi,
        "year": paper.year,
        "venue": paper.venue,
        "downloaded": filepath is not None,
        "file_path": filepath or "",
        "download_dir": downloader.get_download_dir(),
    }


# ---------------------------------------------------------------------------
# Tool: batch_download
# ---------------------------------------------------------------------------


@mcp.tool()
def batch_download(dois: list[str]) -> dict:
    """
    Download multiple papers by DOI list.

    Args:
        dois: List of DOIs to download.

    Returns:
        Summary of downloads (success count, failures, file paths).
    """
    from litsearch.sources import SourceManager
    from litsearch.downloader import PaperDownloader

    sources = SourceManager()
    downloader = PaperDownloader()

    success = []
    failed = []

    for doi in dois:
        paper = sources.resolve_doi(doi.strip())
        if paper is None:
            failed.append({"doi": doi, "reason": "Not found"})
            continue
        filepath = downloader.download_pdf(paper)
        if filepath:
            success.append({"doi": doi, "title": paper.title[:100], "path": filepath})
        else:
            failed.append({"doi": doi, "title": paper.title[:100], "reason": "Download failed"})

    return {
        "success_count": len(success),
        "failed_count": len(failed),
        "success": success,
        "failed": failed,
        "download_dir": downloader.get_download_dir(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    mcp.run()


if __name__ == "__main__":
    main()
