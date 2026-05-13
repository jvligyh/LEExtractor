"""Citation network graph building, analysis, and visualization."""

import math
from collections import defaultdict

import networkx as nx

from litsearch.models import Paper, CitationNetwork


class CitationGraphEngine:
    """Builds and analyzes directed citation networks using NetworkX.

    Edges are directed: A -> B means paper A *cites* paper B.
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def build_network(
        self, papers: dict[str, Paper], seed_id: str
    ) -> nx.DiGraph:
        """Build a DiGraph from a dict of papers, adding nodes and citation edges."""
        self.graph = nx.DiGraph()
        for paper_id, paper in papers.items():
            self.graph.add_node(
                paper_id,
                title=paper.title[:120],
                year=paper.year,
                citations=paper.citation_count,
                relevance=paper.relevance_score,
                venue=paper.venue,
                authors=", ".join(a.name for a in paper.authors[:3]),
            )
        for paper_id, paper in papers.items():
            for ref_id in paper.reference_ids:
                if ref_id in papers:
                    self.graph.add_edge(paper_id, ref_id, type="references")
        if seed_id not in self.graph:
            self.graph.add_node(seed_id, title="Seed Paper", year=None,
                                citations=0, relevance=1.0, venue="")
        return self.graph

    def compute_centrality(self, top_n: int = 10) -> list[tuple[str, float]]:
        """Compute PageRank centrality; return top-N nodes."""
        if len(self.graph) == 0:
            return []
        pr = nx.pagerank(self.graph, alpha=0.85)
        sorted_pr = sorted(pr.items(), key=lambda x: x[1], reverse=True)
        return sorted_pr[:top_n]

    def detect_communities(self) -> dict[int, list[str]]:
        """Detect communities using Louvain (if available) or label propagation."""
        if len(self.graph) == 0:
            return {}
        # Use undirected copy for community detection
        ug = self.graph.to_undirected()
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(ug)
            return {i: list(c) for i, c in enumerate(comms)}
        except ImportError:
            from networkx.algorithms.community import label_propagation_communities
            comms = label_propagation_communities(ug)
            return {i: list(c) for i, c in enumerate(comms)}

    def find_paths(
        self, source_id: str, target_id: str, max_length: int = 3
    ) -> list[list[str]]:
        """Find all simple paths between two papers up to max_length edges."""
        if source_id not in self.graph or target_id not in self.graph:
            return []
        try:
            return list(
                nx.all_simple_paths(self.graph, source_id, target_id,
                                    cutoff=max_length)
            )[:20]
        except nx.NetworkXNoPath:
            return []

    def find_all_paths_to_centrals(
        self, seed_id: str, central_ids: list[str], max_length: int = 3
    ) -> dict[str, list[list[str]]]:
        """Find paths from the seed paper to each central paper."""
        result = {}
        for cid in central_ids:
            if cid == seed_id:
                continue
            paths = self.find_paths(seed_id, cid, max_length)
            if paths:
                result[cid] = paths
        return result

    def prune_network(self, min_relevance: float = 0.05):
        """Remove nodes with very low relevance from the graph."""
        to_remove = [
            n for n, d in self.graph.nodes(data=True)
            if d.get("relevance", 0) < min_relevance and d.get("relevance", 0) > 0
        ]
        self.graph.remove_nodes_from(to_remove)

    def to_node_link(self) -> dict:
        """Export graph as node-link JSON for serialization."""
        return nx.node_link_data(self.graph)

    def to_mermaid(self, max_nodes: int = 80) -> str:
        """Generate a Mermaid flowchart of the citation network."""
        lines = ["graph LR"]
        nodes = list(self.graph.nodes(data=True))
        shown = set()
        for i, (nid, ndata) in enumerate(nodes[:max_nodes]):
            title = (ndata.get("title") or nid)[:50].replace('"', "'")
            year = ndata.get("year", "")
            label = f"{year} {title}" if year else title
            lines.append(f'    n{i}["{label}"]')
            shown.add(nid)
        edge_idx = 0
        for u, v, edata in self.graph.edges(data=True):
            if u in shown and v in shown and edge_idx < 200:
                lines.append(f"    n{list(shown).index(u)} --> n{list(shown).index(v)}")
                edge_idx += 1
        return "\n".join(lines)

    def to_pyvis_html(
        self, seed_id: str = "", height: str = "600px", width: str = "100%"
    ) -> str:
        """Generate an interactive pyvis HTML graph."""
        from pyvis.network import Network

        nodes = list(self.graph.nodes(data=True))
        net = Network(height=height, width=width, directed=True, notebook=False)
        # Use physics options for better layout
        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "centralGravity": 0.01,
              "springLength": 100,
              "springConstant": 0.08
            },
            "maxVelocity": 50,
            "solver": "forceAtlas2Based",
            "timestep": 0.35,
            "stabilization": {"iterations": 150}
          },
          "nodes": {
            "font": {"size": 12, "face": "Arial"},
            "borderWidth": 2
          },
          "edges": {
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
            "smooth": {"type": "continuous"}
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """)

        # Compute node sizes and colors
        max_cite = max((d.get("citations", 1) or 1) for _, d in nodes) or 1

        for nid, ndata in nodes:
            cite_count = ndata.get("citations", 0) or 0
            relevance = ndata.get("relevance", 0) or 0
            size = 5 + 40 * (math.log(cite_count + 1) / math.log(max_cite + 2))
            is_seed = nid == seed_id
            if is_seed:
                color = "#e74c3c"
                size = max(size, 25)
            elif relevance > 0.3:
                color = "#2ecc71"
            elif relevance > 0.1:
                color = "#3498db"
            else:
                color = "#95a5a6"

            title_parts = [ndata.get("title", nid)[:80]]
            if ndata.get("year"):
                title_parts.append(f"Year: {ndata['year']}")
            title_parts.append(f"Citations: {cite_count}")
            title_parts.append(f"Relevance: {relevance:.3f}")
            if ndata.get("venue"):
                title_parts.append(f"Venue: {ndata['venue'][:60]}")
            authors = ndata.get("authors", "")
            if authors:
                title_parts.append(f"Authors: {authors}")

            net.add_node(
                nid,
                label=ndata.get("title", nid)[:40],
                title="\n".join(title_parts),
                size=size,
                color=color,
                borderWidth=3 if is_seed else 1,
                borderWidthSelected=4,
            )

        for u, v in self.graph.edges():
            net.add_edge(u, v, color="#cccccc", width=1, arrows="to")

        return net.generate_html()
