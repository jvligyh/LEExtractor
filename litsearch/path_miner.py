"""Knowledge evolution path mining from citation networks.

Core algorithm: given a set of papers on a topic, discover the temporal
evolution chain (e.g. ML→CNN→RNN→Transformer→LLM) by analyzing
citation flow across time windows and extracting backbone paths.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field

from litsearch.models import Paper


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class EraHub:
    """A key paper or group of papers representing a time window in evolution."""

    era_label: str  # e.g. "2015-2017"
    start_year: int
    end_year: int
    key_papers: list[Paper] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    total_papers: int = 0  # Total papers found in this era


@dataclass
class EvolutionLink:
    """A directed link between two eras showing knowledge flow."""

    from_era: str
    to_era: str
    from_paper: Paper | None = None
    to_paper: Paper | None = None
    citation_count: int = 0  # How many papers from to_era cite from_paper
    description: str = ""  # Human-readable description of the transition


@dataclass
class EvolutionPath:
    """A complete evolution chain from earliest to latest era."""

    topic: str
    eras: list[EraHub] = field(default_factory=list)
    links: list[EvolutionLink] = field(default_factory=list)
    total_papers_analyzed: int = 0
    coverage: str = ""  # "fast" | "comprehensive"


# ---------------------------------------------------------------------------
# Path Miner
# ---------------------------------------------------------------------------


class EvolutionPathMiner:
    """Mines knowledge evolution paths from citation-aware paper collections."""

    WINDOW_SIZE = 3  # years per era window

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Step 1: Group papers into time windows
    # ------------------------------------------------------------------

    def group_into_eras(
        self, papers: list[Paper], window_size: int = 3
    ) -> dict[str, list[Paper]]:
        """Group papers into time windows (eras).

        Returns dict like {"2013-2015": [...], "2016-2018": [...], ...}
        """
        # Filter out papers without years
        dated = [p for p in papers if p.year is not None]
        if not dated:
            return {}

        min_year = min(p.year for p in dated)
        max_year = max(p.year for p in dated)

        # Round min_year down to nearest window boundary
        min_window = (min_year // window_size) * window_size
        # Round max_year up to nearest window boundary
        max_window = ((max_year // window_size) + 1) * window_size

        eras: dict[str, list[Paper]] = defaultdict(list)
        for w_start in range(min_window, max_window, window_size):
            w_end = w_start + window_size - 1
            label = f"{w_start}-{w_end}"
            for p in dated:
                if w_start <= p.year <= w_end:
                    eras[label].append(p)

        # Remove empty eras (but keep gaps — they are informative)
        return {k: v for k, v in sorted(eras.items()) if v}

    # ------------------------------------------------------------------
    # Step 2: Identify hub papers per era
    # ------------------------------------------------------------------

    def identify_hubs(
        self,
        era_papers: dict[str, list[Paper]],
        top_k: int = 5,
        min_citations: int = 0,
    ) -> dict[str, list[Paper]]:
        """Within each era, select top-K hub papers by citation influence.

        Composite score: log(citation_count + 1) * (1 + relevance_score)
        """
        import math

        hubs: dict[str, list[Paper]] = {}
        for era_label, papers in era_papers.items():
            candidates = [p for p in papers if p.citation_count >= min_citations]
            candidates.sort(
                key=lambda p: math.log(p.citation_count + 2) * (1 + p.relevance_score),
                reverse=True,
            )
            hubs[era_label] = candidates[:top_k]
        return hubs

    # ------------------------------------------------------------------
    # Step 3: Discover evolution links between eras
    # ------------------------------------------------------------------

    def discover_evolution_links(
        self,
        era_hubs: dict[str, list[Paper]],
        all_papers: dict[str, Paper],
    ) -> list[EvolutionLink]:
        """Find citation flow between era hubs.

        A link from era A to era B exists when hub papers in era B
        cite hub papers in era A, indicating knowledge inheritance.
        """
        era_order = sorted(era_hubs.keys())
        links: list[EvolutionLink] = []

        for i in range(len(era_order) - 1):
            from_era = era_order[i]
            to_era = era_order[i + 1]
            from_hubs = era_hubs.get(from_era, [])
            to_hubs = era_hubs.get(to_era, [])

            best_link = None
            best_weight = 0

            for to_paper in to_hubs:
                to_ref_ids = set(to_paper.reference_ids)
                for from_paper in from_hubs:
                    if from_paper.id in to_ref_ids or from_paper.doi in to_ref_ids:
                        weight = math.log(to_paper.citation_count + 2) * (
                            1 + to_paper.relevance_score
                        )
                        if weight > best_weight:
                            best_weight = weight
                            best_link = EvolutionLink(
                                from_era=from_era,
                                to_era=to_era,
                                from_paper=from_paper,
                                to_paper=to_paper,
                                citation_count=to_paper.citation_count,
                            )

            if best_link:
                links.append(best_link)
            else:
                # No direct citation found — create a weak link with best available
                if from_hubs and to_hubs:
                    links.append(EvolutionLink(
                        from_era=from_era,
                        to_era=to_era,
                        from_paper=from_hubs[0],
                        to_paper=to_hubs[0],
                        citation_count=0,
                        description="(无直接引用 — 主题流变)",
                    ))

        return links

    # ------------------------------------------------------------------
    # Step 4: Extract backbone paths
    # ------------------------------------------------------------------

    def extract_backbone(
        self,
        era_hubs: dict[str, list[Paper]],
        links: list[EvolutionLink],
    ) -> list[list[str]]:
        """Extract all connected paths through eras.

        Returns list of paths, each being a list of era labels in order.
        """
        if not era_hubs:
            return []

        era_order = sorted(era_hubs.keys())
        link_map: dict[str, str] = {}
        for link in links:
            link_map[link.from_era] = link.to_era

        # Find connected components
        paths = []
        visited = set()
        for era in era_order:
            if era in visited:
                continue
            path = [era]
            visited.add(era)
            current = era
            while current in link_map:
                next_era = link_map[current]
                if next_era in visited:
                    break
                path.append(next_era)
                visited.add(next_era)
                current = next_era
            if len(path) >= 2:
                paths.append(path)

        return paths

    # ------------------------------------------------------------------
    # Step 5: Full pipeline
    # ------------------------------------------------------------------

    def mine_evolution(
        self,
        papers: list[Paper],
        topic: str,
        mode: str = "fast",
    ) -> EvolutionPath:
        """Run the full evolution mining pipeline.

        Args:
            papers: Papers from multi-source search.
            topic: The research topic being explored.
            mode: "fast" (top 3 hubs/era, 1-2 paths) or "comprehensive"
                  (top 8 hubs/era, full path network).

        Returns:
            EvolutionPath with eras, links, and structured evolution chain.
        """
        import math

        top_k = 3 if mode == "fast" else 8
        min_cit = 1 if mode == "fast" else 0

        # Step 1: Group into eras
        era_papers = self.group_into_eras(papers, self.WINDOW_SIZE)
        if not era_papers:
            return EvolutionPath(topic=topic, coverage=mode)

        # Step 2: Identify hub papers per era
        era_hubs = self.identify_hubs(era_papers, top_k=top_k, min_citations=min_cit)

        # Step 3: Build all-paper lookup
        all_papers: dict[str, Paper] = {}
        for plist in era_papers.values():
            for p in plist:
                all_papers[p.id] = p
                if p.doi:
                    all_papers[p.doi] = p

        # Step 4: Discover evolution links
        links = self.discover_evolution_links(era_hubs, all_papers)

        # Step 5: Build EraHub objects
        era_objects: list[EraHub] = []
        for era_label in sorted(era_hubs.keys()):
            hubs = era_hubs[era_label]
            keywords: list[str] = []
            for h in hubs[:3]:
                if h.topics:
                    keywords.extend(h.topics[:2])
            era_obj = EraHub(
                era_label=era_label,
                start_year=int(era_label.split("-")[0]),
                end_year=int(era_label.split("-")[1]),
                key_papers=hubs,
                keywords=list(set(keywords))[:5],
                total_papers=len(era_papers.get(era_label, [])),
            )
            era_objects.append(era_obj)

        # Step 6: Enrich links with descriptions
        for link in links:
            if link.from_paper and link.to_paper:
                link.description = (
                    f"{link.from_paper.title[:60]}"
                    f" → {link.to_paper.title[:60]}"
                )

        return EvolutionPath(
            topic=topic,
            eras=era_objects,
            links=links,
            total_papers_analyzed=len(papers),
            coverage=mode,
        )
