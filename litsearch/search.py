"""Systematic literature review workflow: Scoping → Search → Snowballing → PRISMA.

Gold-standard review methodology:
- Gusenbauer (2024): multi-database systematic search
- TARCiS (2024): formal citation searching guidance
- PRISMA 2020: standard flow diagram for reporting
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter, defaultdict

from litsearch.models import Paper, SearchResult
from litsearch.sources import SourceManager
from litsearch.filters import RelevanceFilter
from litsearch.snowball import SnowballEngine, SnowballResult
from litsearch.similar import SimilarPaperFinder
from litsearch.prisma import PRISMATracker, PRISMAReport, ScreeningDecision
from litsearch.downloader import PaperDownloader

logger = logging.getLogger(__name__)


class ReviewPhase(Enum):
    SCOPING = "scoping"
    SYSTEMATIC_SEARCH = "systematic_search"
    SNOWBALLING = "snowballing"
    SCREENING = "screening"
    COMPLETE = "complete"


@dataclass
class ReviewState:
    """Complete mutable state of a literature review session."""

    topic: str
    research_direction: str
    phase: ReviewPhase = ReviewPhase.SCOPING

    # Phase 1 — Scoping
    scoping_papers: list[Paper] = field(default_factory=list)
    topic_clusters: dict[str, list[str]] = field(default_factory=dict)
    key_journals: list[tuple[str, int]] = field(default_factory=list)
    key_authors: list[tuple[str, int]] = field(default_factory=list)
    year_distribution: dict[int, int] = field(default_factory=dict)

    # Phase 2 — Systematic search
    search_papers: list[Paper] = field(default_factory=list)

    # Phase 3 — Snowballing + similar
    snowball_result: SnowballResult | None = None
    similar_papers: list[tuple[Paper, float, str]] = field(default_factory=list)

    # Phase 4 — PRISMA
    prisma: PRISMATracker = field(default_factory=PRISMATracker)

    # Stats
    start_time: float = 0.0

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0.0

    @property
    def total_papers_tracked(self) -> int:
        report = self.prisma.generate_report()
        return report.records_after_dedup

    @property
    def total_included(self) -> int:
        report = self.prisma.generate_report()
        return report.studies_included


class LiteratureReviewWorkflow:
    """4-phase systematic literature review workflow.

    Phase 1 — Scoping: Broad search, topic landscape, refine strategy
    Phase 2 — Systematic Search: Multi-database keyword search
    Phase 3 — Snowballing: Citation tracing + similar paper discovery
    Phase 4 — Screening + PRISMA: Title/abstract screening, flow diagram

    Implements the gold-standard review methodology described in
    Gusenbauer (2024) and the TARCiS statement, with PRISMA 2020 reporting.
    """

    def __init__(self, source_manager: SourceManager | None = None):
        self.sources = source_manager or SourceManager()
        self.filters = RelevanceFilter()
        self.downloader = PaperDownloader()

    # ------------------------------------------------------------------
    # Phase 1: Scoping
    # ------------------------------------------------------------------

    def scope_topic(
        self,
        topic: str,
        research_direction: str = "",
        years_back: int = 20,
        initial_limit: int = 50,
    ) -> ReviewState:
        """Phase 1: Broad scoping search to understand the field landscape.

        Returns a ReviewState with topic clusters, key journals/authors,
        and year distribution to help refine the search strategy.
        """
        state = ReviewState(
            topic=topic,
            research_direction=research_direction or topic,
            phase=ReviewPhase.SCOPING,
            start_time=time.time(),
        )

        year_from = max(1990, 2026 - years_back)

        papers = self.sources.search_all_sources(
            topic, limit=initial_limit, year_from=year_from, year_to=2026,
        )
        papers = self.filters.deduplicate_by_doi(papers)

        if research_direction:
            self.filters.compute_relevance(papers, research_direction)

        # Topic clusters from keyword co-occurrence
        state.topic_clusters = self._cluster_topics(papers)

        # Journal distribution
        journal_counts: Counter = Counter()
        for p in papers:
            if p.venue:
                journal_counts[p.venue.strip()] += 1
        state.key_journals = journal_counts.most_common(15)

        # Author distribution
        author_counts: Counter = Counter()
        for p in papers:
            for a in p.authors[:3]:
                author_counts[a.name] += 1
        state.key_authors = author_counts.most_common(15)

        # Year distribution
        year_dist: Counter = Counter()
        for p in papers:
            if p.year:
                year_dist[p.year] += 1
        state.year_distribution = dict(sorted(year_dist.items()))

        state.scoping_papers = papers
        logger.info(
            "Scoping complete: topic='%s', papers=%d, journals=%d, authors=%d",
            topic, len(papers), len(state.key_journals), len(state.key_authors),
        )
        return state

    def _cluster_topics(self, papers: list[Paper]) -> dict[str, list[str]]:
        """Simple keyword co-occurrence clustering for topic discovery."""
        keyword_graph: dict[str, Counter] = defaultdict(Counter)
        for p in papers:
            keywords = p.topics + self.filters.extract_keywords(
                (p.title + " " + (p.abstract or ""))[:500], top_n=5
            )
            for i, k1 in enumerate(keywords):
                for k2 in keywords[i + 1 :]:
                    keyword_graph[k1][k2] += 1

        clusters: dict[str, list[str]] = {}
        seen: set[str] = set()
        sorted_kw = sorted(
            keyword_graph.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True,
        )
        for kw, neighbors in sorted_kw[:20]:
            if kw in seen or sum(neighbors.values()) < 2:
                continue
            cluster = [kw] + [n for n, c in neighbors.most_common(5) if c >= 2]
            clusters[kw] = cluster
            seen.update(cluster)

        return clusters

    # ------------------------------------------------------------------
    # Phase 2: Systematic Search
    # ------------------------------------------------------------------

    def systematic_search(
        self,
        state: ReviewState,
        max_papers: int = 200,
        years_back: int = 20,
        min_citations: int = 0,
    ) -> ReviewState:
        """Phase 2: Execute multi-database systematic keyword search.

        Searches S2 + OpenAlex + arXiv + Crossref, deduplicates,
        scores relevance, and registers results in the PRISMA tracker.
        """
        year_from = max(1990, 2026 - years_back)

        papers = self.sources.search_all_sources(
            state.topic, limit=max_papers, year_from=year_from, year_to=2026,
        )
        papers = self.filters.deduplicate_by_doi(papers)
        self.filters.compute_relevance(papers, state.research_direction)

        if min_citations > 0:
            papers = [p for p in papers if p.citation_count >= min_citations]

        papers.sort(key=lambda p: p.relevance_score, reverse=True)
        state.search_papers = papers
        state.phase = ReviewPhase.SYSTEMATIC_SEARCH

        state.prisma.add_papers(papers, source="database_search")

        logger.info(
            "Systematic search: topic='%s', found=%d papers",
            state.topic, len(papers),
        )
        return state

    # ------------------------------------------------------------------
    # Phase 3: Snowballing + Similar Papers
    # ------------------------------------------------------------------

    def run_snowballing(
        self,
        state: ReviewState,
        num_seeds: int = 10,
        max_rounds: int = 3,
        max_per_direction: int = 50,
        min_citations: int = 0,
        year_from: int = 1900,
        year_to: int = 2026,
    ) -> ReviewState:
        """Phase 3a: Iterative forward+backward citation tracing (TARCiS-aligned).

        Uses the top-N most relevant papers from systematic search as seeds,
        then iteratively fetches references (backward) and citations (forward),
        stopping at saturation.
        """
        if not state.search_papers:
            # Auto-run phase 2 if needed
            self.systematic_search(state)

        seeds = state.search_papers[:num_seeds]

        engine = SnowballEngine(
            sources=self.sources,
            filters=self.filters,
        )

        result = engine.run(
            seed_papers=seeds,
            research_direction=state.research_direction,
            max_rounds=max_rounds,
            max_per_direction=max_per_direction,
            min_citations=min_citations,
            year_from=year_from,
            year_to=year_to,
        )

        state.snowball_result = result

        # Add newly discovered papers to PRISMA (skip those already in search results)
        existing_ids = {
            (p.doi or p.id).lower() for p in state.search_papers
        }
        for paper in result.all_papers.values():
            key = (paper.doi or paper.id).lower()
            if key not in existing_ids:
                state.prisma.add_papers([paper], source="snowballing")

        logger.info(
            "Snowballing: rounds=%d, discovered=%d, saturated=%s",
            len(result.rounds), result.total_discovered, result.saturated,
        )
        return state

    def find_similar(
        self,
        state: ReviewState,
        num_seeds: int = 10,
        top_k: int = 30,
    ) -> ReviewState:
        """Phase 3b: Find similar papers via bibliographic coupling + co-citation."""
        if not state.search_papers:
            self.systematic_search(state)

        seeds = state.search_papers[:num_seeds]

        finder = SimilarPaperFinder(sources=self.sources)
        similar = finder.find_similar(seeds, top_k=top_k)

        state.similar_papers = similar

        for paper, score, method in similar:
            state.prisma.add_papers([paper], source="similar")

        state.phase = ReviewPhase.SNOWBALLING

        logger.info(
            "Similar papers: found=%d (bc=%d, cc=%d)",
            len(similar),
            sum(1 for _, _, m in similar if m == "bibliographic_coupling"),
            sum(1 for _, _, m in similar if m == "co_citation"),
        )
        return state

    # ------------------------------------------------------------------
    # Phase 4: Screening + PRISMA
    # ------------------------------------------------------------------

    def get_screening_queue(self, state: ReviewState) -> list:
        """Get papers pending screening, sorted by relevance."""
        return state.prisma.get_screening_queue()

    def screen_paper(
        self,
        state: ReviewState,
        paper_id: str,
        decision: ScreeningDecision,
        reason: str = "",
    ) -> None:
        """Record a single screening decision."""
        state.prisma.screen_paper(paper_id, decision, reason)

    def auto_screen(
        self,
        state: ReviewState,
        relevance_threshold: float = 0.15,
    ) -> ReviewState:
        """Auto-screen by relevance: >= threshold → accept, < threshold → reject."""
        for record in state.prisma.get_screening_queue():
            if record.relevance_score >= relevance_threshold:
                state.prisma.screen_paper(record.paper.id, ScreeningDecision.ACCEPT)
            else:
                state.prisma.screen_paper(
                    record.paper.id,
                    ScreeningDecision.REJECT,
                    reason=f"Below relevance threshold ({record.relevance_score:.2f} < {relevance_threshold})",
                )
        state.phase = ReviewPhase.SCREENING

        accepted = len(state.prisma.get_accepted_ids())
        logger.info("Auto-screen: accepted=%d by threshold=%.2f", accepted, relevance_threshold)
        return state

    def generate_prisma_report(self, state: ReviewState) -> PRISMAReport:
        """Generate PRISMA 2020 flow diagram report."""
        report = state.prisma.generate_report()
        state.phase = ReviewPhase.COMPLETE
        return report

    def get_included_papers(self, state: ReviewState) -> list[Paper]:
        """Get all papers that passed screening."""
        return state.prisma.get_included_papers()

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run_full_workflow(
        self,
        topic: str,
        research_direction: str = "",
        years_back: int = 20,
        max_search_papers: int = 200,
        snowball_rounds: int = 3,
        auto_screen_threshold: float = 0.15,
    ) -> ReviewState:
        """Run the complete 4-phase workflow in one call.

        Returns the final ReviewState ready for PRISMA reporting and download.
        """
        t0 = time.time()
        direction = research_direction or topic

        state = self.scope_topic(topic, direction, years_back=years_back)
        self.systematic_search(state, max_papers=max_search_papers, years_back=years_back)
        self.run_snowballing(state, max_rounds=snowball_rounds)
        self.find_similar(state)
        self.auto_screen(state, relevance_threshold=auto_screen_threshold)
        self.generate_prisma_report(state)

        elapsed = time.time() - t0
        logger.info(
            "Full workflow: topic='%s', tracked=%d, included=%d, %.1fs",
            topic, state.total_papers_tracked, state.total_included, elapsed,
        )
        return state

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def download_included(self, state: ReviewState) -> list[tuple[Paper, str | None]]:
        """Download all papers that passed screening."""
        included = self.get_included_papers(state)
        return self.downloader.batch_download(included)

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_included_csv(self, state: ReviewState) -> str:
        from litsearch.export import to_csv
        return to_csv(self.get_included_papers(state))

    def export_included_ris(self, state: ReviewState) -> str:
        from litsearch.export import to_ris
        return to_ris(self.get_included_papers(state))


# ------------------------------------------------------------------
# Backward-compatible alias
# ------------------------------------------------------------------


class LiteratureExplorer:
    """Legacy wrapper: maps old fast_search/comprehensive_search to new workflow.

    Prefer LiteratureReviewWorkflow for new code.
    """

    def __init__(self):
        self.workflow = LiteratureReviewWorkflow()
        self.downloader = self.workflow.downloader

    def fast_search(self, topic, years_back=20, max_papers=100):
        """Quick search via the new 4-phase workflow (auto-screened)."""
        state = self.workflow.run_full_workflow(
            topic=topic,
            years_back=years_back,
            max_search_papers=max_papers,
            snowball_rounds=1,
            auto_screen_threshold=0.12,
        )
        return self._state_to_path(state)

    def comprehensive_search(self, topic, years_back=30, max_papers=500):
        """Deep search via the new 4-phase workflow."""
        state = self.workflow.run_full_workflow(
            topic=topic,
            years_back=years_back,
            max_search_papers=max_papers,
            snowball_rounds=3,
            auto_screen_threshold=0.10,
        )
        return self._state_to_path(state)

    def _state_to_path(self, state: ReviewState):
        """Convert ReviewState to a legacy EvolutionPath-compatible object."""
        from litsearch.path_miner import EvolutionPath, EraHub

        path = EvolutionPath()
        path.topic = state.topic
        path.coverage = "fast" if state.snowball_result and len(state.snowball_result.rounds) <= 1 else "comprehensive"
        path.total_papers_analyzed = state.total_papers_tracked

        # Group papers by year into era-like buckets
        included = self.workflow.get_included_papers(state)
        if not included:
            included = state.search_papers[:30]

        year_groups: dict[str, list[Paper]] = defaultdict(list)
        for p in included:
            decade = f"{(p.year or 2020) // 5 * 5}s"
            year_groups[decade].append(p)

        for era_label in sorted(year_groups.keys()):
            papers = year_groups[era_label]
            keywords = self.workflow.filters.extract_keywords(
                " ".join(p.title for p in papers), top_n=4
            )
            era = EraHub(
                era_label=era_label,
                start_year=int(era_label.replace("s", "")),
                end_year=int(era_label.replace("s", "")) + 4,
                key_papers=papers[:5],
                total_papers=len(papers),
                keywords=keywords,
            )
            path.eras.append(era)

        return path
