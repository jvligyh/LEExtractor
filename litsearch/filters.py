"""Relevance scoring, noise filtering, and deduplication for search results."""

import re
import math
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from litsearch.models import Paper


class RelevanceFilter:
    """Scores papers against a research direction description using TF-IDF."""

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )

    def _paper_to_text(self, paper: Paper) -> str:
        parts = [paper.title]
        if paper.abstract:
            parts.append(paper.abstract)
        if paper.topics:
            parts.append(" ".join(paper.topics))
        return " ".join(parts)

    def compute_relevance(
        self, papers: list[Paper], direction_text: str
    ) -> list[Paper]:
        """Score each paper by TF-IDF cosine similarity to research direction."""
        if not papers or not direction_text.strip():
            return papers

        direction_text = direction_text.strip()
        docs = [self._paper_to_text(p) for p in papers]
        try:
            tfidf_matrix = self._vectorizer.fit_transform([direction_text] + docs)
            dir_vec = tfidf_matrix[0:1]
            paper_vecs = tfidf_matrix[1:]
            scores = cosine_similarity(dir_vec, paper_vecs).flatten()
            for paper, score in zip(papers, scores):
                paper.relevance_score = float(score)
        except ValueError:
            for paper in papers:
                paper.relevance_score = 0.0
        return papers

    def filter_noise(
        self,
        papers: list[Paper],
        min_relevance: float = 0.05,
        min_citations: int = 0,
        max_papers: int = 200,
    ) -> list[Paper]:
        """Remove low-relevance papers, zero-citation papers, and trim to max."""
        filtered = [
            p for p in papers
            if p.relevance_score >= min_relevance
            and p.citation_count >= min_citations
        ]
        # Sort by composite score: relevance * log(citations + 2)
        filtered.sort(
            key=lambda p: p.relevance_score * math.log(p.citation_count + 2),
            reverse=True,
        )
        return filtered[:max_papers]

    def deduplicate_by_doi(self, papers: list[Paper]) -> list[Paper]:
        """Merge papers from different sources with the same DOI."""
        seen: dict[str, Paper] = {}
        for p in papers:
            key = (p.doi or p.id).lower()
            if key in seen:
                existing = seen[key]
                # Merge: take the richer metadata
                if not existing.abstract and p.abstract:
                    existing.abstract = p.abstract
                if p.citation_count > existing.citation_count:
                    existing.citation_count = p.citation_count
                if p.reference_count > existing.reference_count:
                    existing.reference_count = p.reference_count
                if p.relevance_score > existing.relevance_score:
                    existing.relevance_score = p.relevance_score
                if p.topics:
                    existing.topics = list(set(existing.topics + p.topics))
                existing.citation_ids = list(
                    set(existing.citation_ids + p.citation_ids)
                )
                existing.reference_ids = list(
                    set(existing.reference_ids + p.reference_ids)
                )
            else:
                seen[key] = p
        return list(seen.values())

    @staticmethod
    def extract_keywords(text: str, top_n: int = 10) -> list[str]:
        """Extract likely keywords from a text snippet for display."""
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        stopwords = {
            "the", "and", "for", "from", "with", "that", "this", "are",
            "was", "were", "have", "has", "been", "its", "not", "but",
            "can", "may", "also", "using", "based", "used", "use", "via",
            "into", "such", "each", "more", "however", "within", "than",
            "which", "these", "their", "both", "between", "other",
        }
        words = [w for w in words if w not in stopwords and len(w) > 2]
        return [w for w, _ in Counter(words).most_common(top_n)]
