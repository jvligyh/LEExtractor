"""LEExtractor — Literature Evolution Extractor (Streamlit GUI).

Search a research topic → discover evolution paths → download key papers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="LEExtractor — Literature Evolution Extractor",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar():
    st.sidebar.title("🧬 LEExtractor")
    st.sidebar.caption("Literature Evolution Extractor")
    st.sidebar.caption("文献综述写作 · 技术脉络梳理 · PDF下载")

    mode = st.sidebar.radio(
        "Search Mode / 搜索模式",
        ["⚡ Fast / 快速", "🔬 Comprehensive / 全面"],
        index=0,
        help=(
            "**Fast / 快速**: Broad shallow search, quick evolution outline (~100 papers)\n"
            "浅层广域搜索，快速勾勒演化主线\n\n"
            "**Comprehensive / 全面**: Deep multi-source search, full reference mining (~500 papers)\n"
            "多源深度搜索，完整引文挖掘，精细演化链路"
        ),
    )

    st.sidebar.divider()

    years_back = st.sidebar.slider(
        "Years Back / 回溯年数",
        5, 50, 20,
        help="How many years of literature to cover / 搜索覆盖多少年的文献",
    )

    max_papers = st.sidebar.slider(
        "Max Papers / 最大论文数",
        50, 1000, 100 if "Fast" in mode else 500,
        50,
        help="Fast: 50-200 recommended; Comprehensive: 300-800 recommended",
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "Sources / 数据源: Semantic Scholar · OpenAlex · arXiv · Crossref\n"
        "Download / 下载: Sci-Hub · arXiv · OpenAccess"
    )

    return mode, years_back, max_papers


# ---------------------------------------------------------------------------
# Main search
# ---------------------------------------------------------------------------


def run_search(topic: str, mode: str, years_back: int, max_papers: int):
    """Execute the search and cache result in session state."""
    from litsearch.search import LiteratureExplorer

    with st.spinner(f"Mapping evolution path for '{topic}'... / 正在分析演化路径..."):
        explorer = LiteratureExplorer()

        if "Fast" in mode:
            path = explorer.fast_search(
                topic=topic,
                years_back=years_back,
                max_papers=max_papers,
            )
        else:
            path = explorer.comprehensive_search(
                topic=topic,
                years_back=years_back,
                max_papers=max_papers,
            )

    st.session_state["evolution_path"] = path
    st.session_state["explorer"] = explorer
    st.session_state["last_topic"] = topic


# ---------------------------------------------------------------------------
# Timeline visualization
# ---------------------------------------------------------------------------


def render_timeline(path):
    """Render the evolution timeline as horizontal era cards connected by arrows."""
    from litsearch.path_miner import EvolutionPath

    if not path.eras:
        st.warning(
            "Not enough literature to build an evolution path. "
            "Try a more specific topic or broaden the search range.\n\n"
            "未找到足够文献构建演化路径，请尝试更具体的主题或扩大搜索范围。"
        )
        return

    st.subheader(f"📜 Evolution Path / 知识演化路径: {path.topic}")

    # Stats bar
    total_papers = sum(e.total_papers for e in path.eras)
    total_hubs = sum(len(e.key_papers) for e in path.eras)
    cols = st.columns(4)
    cols[0].metric("Eras / 时代窗口", f"{len(path.eras)}")
    cols[1].metric("Hub Papers / 枢纽论文", f"{total_hubs}")
    cols[2].metric("Papers Analyzed / 分析文献", f"{total_papers}")
    cols[3].metric("Evolution Links / 演化链接", f"{len(path.links)}")

    st.divider()

    # Render eras as a horizontal timeline
    eras = path.eras
    n = len(eras)

    for i, era in enumerate(eras):
        era_col, _ = st.columns([4, 1])
        with era_col:
            st.markdown(f"### 🕐 {era.era_label}")
            st.caption(
                f"{era.total_papers} papers in this era / 该时期共 {era.total_papers} 篇 · "
                f"{len(era.key_papers)} hubs / 枢纽论文 · "
                f"Keywords / 关键词: {', '.join(era.keywords[:4]) if era.keywords else '—'}"
            )

        _render_paper_cards(era.key_papers[:5], era.era_label)

        # Evolution arrow between eras
        if i < n - 1:
            link = next(
                (l for l in path.links
                 if l.from_era == era.era_label and l.to_era == eras[i + 1].era_label),
                None,
            )
            if link:
                desc = link.description or f"{era.era_label} → {eras[i + 1].era_label}"
                st.markdown(
                    f"<div style='text-align:center; padding:10px; color:#3498db; "
                    f"font-size:1.15em'>⬇️ {desc[:120]}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center; padding:10px; color:#95a5a6'>"
                    f"⬇️ {era.era_label} → {eras[i + 1].era_label} "
                    f"(conceptual shift / 知识演变)</div>",
                    unsafe_allow_html=True,
                )

    # Link details in expander
    if path.links:
        with st.expander("🔗 Evolution Links / 演化链接详情"):
            for link in path.links:
                st.markdown(
                    f"**{link.from_era}** → **{link.to_era}**  "
                    f"({link.citation_count} citations / 引用)  "
                )
                if link.description:
                    st.caption(link.description)


# ---------------------------------------------------------------------------
# Paper cards
# ---------------------------------------------------------------------------


def _render_paper_cards(papers, era_key: str):
    """Render paper info cards with IF and download."""
    from litsearch.sources import ImpactFactorLookup

    if_lookup = ImpactFactorLookup()

    for idx, paper in enumerate(papers):
        with st.container():
            c1, c2 = st.columns([5, 1])

            with c1:
                title = paper.title[:150]
                authors = ", ".join(a.name for a in paper.authors[:3])
                if len(paper.authors) > 3:
                    authors += " et al."

                venue_extra = ""
                if paper.venue:
                    if_val = if_lookup.get_if_display(paper.venue)
                    if "N/A" not in if_val:
                        venue_extra = f" | 📊 {if_val}"
                    venue_extra += f" | 🏷 {paper.venue[:60]}"
                else:
                    venue_extra = ""

                is_preprint = paper.source == "arxiv"
                preprint_tag = " 📝[Preprint]" if is_preprint else ""

                st.markdown(
                    f"**{paper.year or '?'}** · "
                    f"Cited / 引用: {paper.citation_count}{preprint_tag}"
                    f"{venue_extra}"
                )
                st.markdown(f"*{title}*")
                st.caption(authors)

                if paper.abstract:
                    with st.expander("Abstract / 摘要"):
                        st.write(paper.abstract[:500])

            with c2:
                dl_url = paper.url
                if dl_url and dl_url.startswith("http"):
                    st.link_button(
                        "📥 Download PDF",
                        dl_url,
                        use_container_width=True,
                    )
                else:
                    st.button(
                        "📥 No Link",
                        disabled=True,
                        use_container_width=True,
                        key=f"nodl_{era_key}_{idx}",
                    )

                if paper.doi:
                    st.link_button(
                        "🔗 DOI",
                        f"https://doi.org/{paper.doi}",
                        use_container_width=True,
                    )

            st.divider()


# ---------------------------------------------------------------------------
# Batch download
# ---------------------------------------------------------------------------


def render_download_section(path, explorer):
    """Batch download section for all hub papers."""
    st.subheader("📦 Batch Download / 批量下载")

    all_hubs = []
    for era in path.eras:
        all_hubs.extend(era.key_papers)

    seen = set()
    unique_hubs = []
    for p in all_hubs:
        key = (p.doi or p.id).lower()
        if key not in seen:
            seen.add(key)
            unique_hubs.append(p)

    st.info(
        f"{len(unique_hubs)} hub papers available for download.\n"
        f"PDFs saved to: `{explorer.downloader.get_download_dir()}`\n\n"
        f"共 {len(unique_hubs)} 篇枢纽论文可下载，PDF保存至上述路径。"
    )

    if st.button("📥 Download All Hub PDFs / 下载全部枢纽论文", type="primary", use_container_width=True):
        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, paper in enumerate(unique_hubs):
            status.text(f"Downloading ({i+1}/{len(unique_hubs)}): {paper.title[:80]}...")
            path_result = explorer.downloader.download_pdf(paper)
            results.append((paper, path_result))
            progress.progress((i + 1) / len(unique_hubs))

        success = [r for r in results if r[1] is not None]
        status.text(f"Done: {len(success)}/{len(unique_hubs)} succeeded / 下载成功")
        st.success(
            f"Download complete! {len(success)} PDFs saved to "
            f"`{explorer.downloader.get_download_dir()}`\n\n"
            f"下载完成！{len(success)} 篇PDF已保存。"
        )

        failures = [r for r in results if r[1] is None]
        if failures:
            with st.expander(f"⚠️ {len(failures)} failed / 下载失败"):
                for p, _ in failures:
                    st.write(f"- {p.title[:100]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.title("🧬 LEExtractor")
    st.caption(
        "Literature Evolution Extractor — "
        "Map technology evolution paths · Download key papers\n\n"
        "输入研究课题 → 自动梳理技术演化脉络 → 下载关键文献PDF"
    )

    mode, years_back, max_papers = render_sidebar()

    topic = st.text_input(
        "Research Topic / 研究课题",
        placeholder=(
            "e.g. Large Language Model, CRISPR gene editing, "
            "plant phenotyping deep learning, transformer attention mechanism..."
        ),
    )

    col1, col2, _ = st.columns([2, 2, 4])
    with col1:
        search_btn = st.button(
            "🔍 Explore Evolution / 探索演化路径", type="primary", use_container_width=True
        )
    with col2:
        clear_btn = st.button("🗑 Clear / 清除结果", use_container_width=True)

    if clear_btn:
        st.session_state.pop("evolution_path", None)
        st.session_state.pop("explorer", None)
        st.session_state.pop("last_topic", None)
        st.rerun()

    if search_btn and topic.strip():
        run_search(topic.strip(), mode, years_back, max_papers)

    if "evolution_path" in st.session_state:
        path = st.session_state["evolution_path"]
        explorer = st.session_state["explorer"]

        st.divider()
        render_timeline(path)
        st.divider()
        render_download_section(path, explorer)

    elif not topic.strip():
        st.divider()
        st.markdown("### 💡 Try these examples / 试试这些例子")
        examples = [
            "`Large Language Model` — From traditional NLP to GPT / 从传统NLP到GPT的演进",
            "`CRISPR gene editing` — Gene editing technology trajectory / 基因编辑技术发展脉络",
            "`plant phenotyping deep learning` — Method evolution in plant DL / 植物表型深度学习方法演化",
            "`transformer attention mechanism` — Attention mechanism lineage / 注意力机制进化链",
            "`single cell RNA sequencing` — scRNA-seq technology roadmap / 单细胞测序技术路线",
        ]
        for ex in examples:
            st.markdown(f"- {ex}")

        st.info(
            "**Fast mode / 快速模式**: Enter a topic → get the evolution backbone "
            "+ key papers per stage + PDF download in seconds.\n\n"
            "**Comprehensive mode / 全面模式**: Deep mining of the full intellectual "
            "lineage — ideal for literature reviews and proposal writing.\n\n"
            "快速模式输入课题即得演化主线与每阶段关键论文；"
            "全面模式深度挖掘完整知识流变链路，适合写综述、开题报告。"
        )


if __name__ == "__main__":
    main()
