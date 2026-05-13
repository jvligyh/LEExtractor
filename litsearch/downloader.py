"""PDF downloader with multi-source fallback: Sci-Hub → OA → arXiv."""

import os
import re
import time
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from litsearch.models import Paper

logger = logging.getLogger(__name__)

# Sci-Hub domains to try (ordered by reliability)
SCI_HUB_DOMAINS = [
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
]


class PaperDownloader:
    """Download PDFs from multiple sources with automatic fallback."""

    def __init__(self, download_dir: str = ""):
        self._download_dir = (
            Path(download_dir) if download_dir
            else Path.home() / "Downloads" / "litsearch_pdfs"
        )
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_download_url(self, paper: Paper) -> str | None:
        """Find a downloadable PDF URL for a paper.

        Priority: Open Access → arXiv → Sci-Hub.
        Returns None if no source found.
        """
        # 1. Direct OA URL from paper metadata
        if paper.url and self._is_pdf_url(paper.url):
            return paper.url

        # 2. arXiv preprint
        arxiv_id = self._extract_arxiv_id(paper)
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # 3. Check OpenAlex for OA link
        oa_url = self._check_openalex_oa(paper)
        if oa_url:
            return oa_url

        # 4. Sci-Hub (last resort)
        if paper.doi:
            return self._scihub_url(paper.doi)

        return None

    def download_pdf(
        self, paper: Paper, filename: str | None = None, skip_existing: bool = True
    ) -> str | None:
        """Download a paper PDF. Returns the file path or None on failure.

        Args:
            paper: Paper to download.
            filename: Custom filename (without extension). Auto-generated if None.
            skip_existing: Skip if file already exists.
        """
        if filename is None:
            filename = self._sanitize_filename(paper)

        filepath = self._download_dir / f"{filename}.pdf"
        if skip_existing and filepath.exists():
            logger.info("Already downloaded: %s", filepath)
            return str(filepath)

        url = self.get_download_url(paper)
        if url is None:
            logger.warning("No download URL for: %s", paper.title[:60])
            return None

        try:
            resp = self._session.get(url, timeout=60, stream=True)
            if resp.status_code == 200 and len(resp.content) > 10000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                logger.info("Downloaded: %s (%d KB)", filename, len(resp.content) // 1024)
                return str(filepath)
            else:
                logger.warning(
                    "Download failed for %s: HTTP %d, size=%d",
                    paper.doi, resp.status_code, len(resp.content)
                )
                return None
        except Exception as e:
            logger.warning("Download error for %s: %s", paper.doi or paper.title[:40], e)
            return None

    def batch_download(
        self, papers: list[Paper], max_workers: int = 3
    ) -> list[tuple[Paper, str | None]]:
        """Download multiple papers sequentially. Returns (paper, path_or_None)."""
        results = []
        for paper in papers:
            path = self.download_paper(paper)
            results.append((paper, path))
            time.sleep(1.0)  # Be polite
        return results

    def get_download_dir(self) -> str:
        return str(self._download_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scihub_url(self, doi: str) -> str | None:
        """Try to get a Sci-Hub direct PDF link for a DOI."""
        for base in SCI_HUB_DOMAINS:
            try:
                # Fetch the Sci-Hub page for this DOI
                resp = self._session.get(
                    f"{base}/{doi}", timeout=20, allow_redirects=True
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                # Sci-Hub embeds the PDF in an <iframe> or <embed>
                for tag in soup.find_all(["iframe", "embed"]):
                    src = tag.get("src", "")
                    if src and ("pdf" in src.lower() or "download" in src.lower()):
                        if src.startswith("//"):
                            src = "https:" + src
                        elif src.startswith("/"):
                            src = urljoin(base, src)
                        return src

                # Alternate: look for direct PDF link
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if ".pdf" in href.lower():
                        if href.startswith("//"):
                            href = "https:" + href
                        return href

                # If the response itself is PDF
                if "application/pdf" in resp.headers.get("content-type", ""):
                    return resp.url

            except Exception:
                continue

        return None

    def _check_openalex_oa(self, paper: Paper) -> str | None:
        """Check OpenAlex for an open-access PDF URL."""
        if not paper.doi:
            return None
        try:
            resp = self._session.get(
                f"https://api.openalex.org/works/https://doi.org/{paper.doi}",
                params={"select": "open_access,primary_location"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                oa = data.get("open_access", {})
                if oa.get("is_oa") and oa.get("oa_url"):
                    return oa["oa_url"]
                loc = data.get("primary_location", {})
                if loc.get("pdf_url"):
                    return loc["pdf_url"]
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_arxiv_id(paper: Paper) -> str | None:
        """Extract arXiv ID from paper metadata."""
        # Check abstract and URL for arXiv IDs
        text_sources = [paper.abstract or "", paper.url or "", paper.id]
        for text in text_sources:
            m = re.search(r"arxiv[:\s]*(\d{4}\.\d{4,5})", text, re.IGNORECASE)
            if m:
                return m.group(1)
            # Old arXiv format
            m = re.search(
                r"arxiv[:\s]*([a-z\-]+/\d{7})", text, re.IGNORECASE
            )
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _is_pdf_url(url: str) -> bool:
        return url.lower().endswith(".pdf") or "/pdf/" in url.lower()

    @staticmethod
    def _sanitize_filename(paper: Paper) -> str:
        """Generate a clean filename: Year_FirstAuthor_ShortTitle."""
        year = paper.year or "XXXX"
        author = paper.authors[0].name.split()[-1] if paper.authors else "Unknown"
        title_words = re.sub(r"[^\w\s]", "", paper.title)[:60]
        title_words = re.sub(r"\s+", "_", title_words.strip())
        return f"{year}_{author}_{title_words}"[:200]
