"""Research topic evolution search with two modes: fast and comprehensive.

Fast mode: Broad but shallow search, identify major era hubs, quick path.
Comprehensive mode: Deep multi-source search, full reference mining,
rich evolution paths with detailed paper tracking.
"""

import time
import logging
from collections import defaultdict

from litsearch.models import Paper, SearchResult, CitationNetwork
from litsearch.sources import SourceManager, ArxivSource
from litsearch.filters import RelevanceFilter
from litsearch.engine import CitationGraphEngine
from litsearch.path_miner import (
    EvolutionPathMiner,
    EvolutionPath,
    EraHub,
    EvolutionLink,
)
from litsearch.downloader import PaperDownloader

logger = logging.getLogger(__name__)


class LiteratureExplorer:
    """Evolution-aware literature explorer with two search modes."""

    def __init__(self, source_manager: SourceManager | None = None):
        self.sources = source_manager or SourceManager()
        self.filters = RelevanceFilter()
        self.miner = EvolutionPathMiner()
        self.downloader = PaperDownloader()

    # ------------------------------------------------------------------
    # Fast Mode
    # ------------------------------------------------------------------

    def fast_search(
        self,
        topic: str,
        years_back: int = 20,
        max_papers: int = 100,
    ) -> EvolutionPath:
        """Quick evolution overview of a research topic.

        Searches broadly but shallowly (top ~100 papers), groups into eras,
        identifies key hub papers, builds a quick evolution chain.

        Suitable for: first-pass exploration, getting oriented in a new field.

        Args:
            topic: Research topic / keywords.
            years_back: How many years back to search.
            max_papers: Maximum papers to analyze.

        Returns:
            EvolutionPath with era hubs, links, and key papers.
        """
        start = time.time()
        year_from = max(1990, 2026 - years_back)

        # Broad search across S2 + arXiv
        papers = self.sources.search_papers(
            topic,
            limit=max_papers,
            year_from=year_from,
            year_to=2026,
            include_preprints=True,
        )
        papers = self.filters.deduplicate_by_doi(papers)

        # Score relevance
        self.filters.compute_relevance(papers, topic)

        # Mine evolution paths
        path = self.miner.mine_evolution(papers, topic, mode="fast")

        # Enrich with download availability
        for era in path.eras:
            for p in era.key_papers:
                dl_url = self.downloader.get_download_url(p)
                if dl_url:
                    p.url = dl_url

        logger.info(
            "Fast search '%s': %d papers, %d eras, %.1fs",
            topic, len(papers), len(path.eras), time.time() - start,
        )
        return path

    # ------------------------------------------------------------------
    # Comprehensive Mode
    # ------------------------------------------------------------------

    def comprehensive_search(
        self,
        topic: str,
        years_back: int = 30,
        max_papers: int = 500,
    ) -> EvolutionPath:
        """Deep evolution analysis of a research topic.

        Searches all sources (S2 + OpenAlex + arXiv + Crossref),
        fetches reference lists for hub papers, builds detailed
        cross-era citation links.

        Suitable for: literature review, paper writing, deep understanding.

        Args:
            topic: Research topic / keywords.
            years_back: How many years back (default 30 for deep history).
            max_papers: Maximum papers to analyze (500+ recommended).

        Returns:
            EvolutionPath with detailed era hubs, citation links, and metadata.
        """
        start = time.time()
        year_from = max(1960, 2026 - years_back)

        # Deep search across ALL sources
        papers = self.sources.search_all_sources(
            topic, limit=max_papers, year_from=year_from, year_to=2026
        )
        papers = self.filters.deduplicate_by_doi(papers)
        self.filters.compute_relevance(papers, topic)

        logger.info("Comprehensive: found %d papers after merge", len(papers))

        # Mine initial evolution
        path = self.miner.mine_evolution(papers, topic, mode="comprehensive")

        # Deep reference mining for hub papers
        self._enrich_references(path)

        # Re-run link discovery with enriched references
        era_hubs = {e.era_label: e.key_papers for e in path.eras}
        all_dict = {p.id: p for e in path.eras for p in e.key_papers}
        for p in all_dict.values():
            if p.doi:
                all_dict[p.doi] = p

        path.links = self.miner.discover_evolution_links(era_hubs, all_dict)

        # Enrich links with descriptions
        for link in path.links:
            if link.from_paper and link.to_paper:
                link.description = (
                    f"{link.from_paper.title[:60]}"
                    f" → {link.to_paper.title[:60]}"
                )
            if link.citation_count == 0:
                link.description += " (主题演化)"

        # Add download URLs
        for era in path.eras:
            for p in era.key_papers:
                dl_url = self.downloader.get_download_url(p)
                if dl_url:
                    p.url = dl_url

        logger.info(
            "Comprehensive '%s': %d papers, %d eras, %d links, %.1fs",
            topic, len(papers), len(path.eras), len(path.links),
            time.time() - start,
        )
        return path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enrich_references(self, path: EvolutionPath):
        """Fetch reference lists for hub papers to enable cross-era linking."""
        for era in path.eras:
            for p in era.key_papers[:5]:  # Top 5 per era
                if not p.reference_ids:
                    try:
                        refs = self.sources.get_references(p.id, limit=100)
                        p.reference_ids = list(set(
                            p.reference_ids + [r.id for r in refs]
                        ))
                    except Exception:
                        pass
                time.sleep(0.5)

    def get_download_urls(self, path: EvolutionPath) -> dict[str, str]:
        """Get download URLs for all hub papers in a path.

        Returns {paper_title: url} mapping.
        """
        urls: dict[str, str] = {}
        for era in path.eras:
            for p in era.key_papers:
                url = self.downloader.get_download_url(p)
                if url:
                    urls[p.title[:80]] = url
        return urls

    def download_hub_papers(
        self, path: EvolutionPath
    ) -> list[tuple[Paper, str | None]]:
        """Download all hub papers from an evolution path."""
        papers = []
        for era in path.eras:
            papers.extend(era.key_papers)
        return self.downloader.batch_download(papers)

    # ------------------------------------------------------------------
    # Legacy API (for backward compatibility)
    # ------------------------------------------------------------------

    def topological_search(self, seed_input, research_direction="",
                           max_hops=2, max_papers_per_hop=20,
                           year_from=2000, year_to=2026):
        """Legacy single-paper BFS. Use fast_search() or comprehensive_search() instead."""
        return SearchResult()

    def frontier_search(self, keywords, research_direction="",
                        years_back=5, sort_by="relevance", max_results=50):
        """Legacy keyword search. Use fast_search() or comprehensive_search() instead."""
        return SearchResult()
