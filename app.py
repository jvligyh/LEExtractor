"""Literature Evolution Explorer — Streamlit GUI.

Search a research topic → discover evolution paths → download key papers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="Literature Evolution Explorer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar():
    st.sidebar.title("🧬 Literature Evolution Explorer")
    st.sidebar.caption("知识演化路径 · 文献发现 · PDF 下载")

    mode = st.sidebar.radio(
        "搜索模式 Search Mode",
        ["⚡ 快速 Fast", "🔬 全面 Comprehensive"],
        index=0,
        help=(
            "**快速**: 浅层广域搜索，快速勾勒演化主线 (~100篇)\n\n"
            "**全面**: 多源深度搜索，完整引文挖掘，精细演化链路 (~500篇)"
        ),
    )

    st.sidebar.divider()

    years_back = st.sidebar.slider(
        "回溯年数 Years Back",
        5, 50, 20,
        help="搜索覆盖多少年内的文献",
    )

    max_papers = st.sidebar.slider(
        "最大论文数 Max Papers",
        50, 1000, 100 if "Fast" in mode else 500,
        50,
        help="Fast 模式推荐 50-200，Comprehensive 推荐 300-800",
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "数据源: Semantic Scholar / OpenAlex / arXiv / Crossref\n"
        "下载: Sci-Hub / arXiv / OpenAccess"
    )

    return mode, years_back, max_papers


# ---------------------------------------------------------------------------
# Main search
# ---------------------------------------------------------------------------


def run_search(topic: str, mode: str, years_back: int, max_papers: int):
    """Execute the search and cache result in session state."""
    from litsearch.search import LiteratureExplorer

    with st.spinner(f"正在分析 '{topic}' 的知识演化路径..."):
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
        st.warning("未找到足够的文献来构建演化路径。请尝试更具体的主题或扩大搜索范围。")
        return

    st.subheader(f"📜 知识演化路径: {path.topic}")

    # Stats bar
    total_papers = sum(e.total_papers for e in path.eras)
    total_hubs = sum(len(e.key_papers) for e in path.eras)
    cols = st.columns(4)
    cols[0].metric("时代窗口", f"{len(path.eras)} eras")
    cols[1].metric("枢纽论文", f"{total_hubs} hubs")
    cols[2].metric("分析文献", f"{total_papers}")
    cols[3].metric("演化链接", f"{len(path.links)} links")

    st.divider()

    # Render eras as a horizontal timeline
    eras = path.eras
    n = len(eras)

    for i, era in enumerate(eras):
        # Era header
        era_col, _ = st.columns([4, 1])
        with era_col:
            st.markdown(f"### 🕐 {era.era_label}")
            st.caption(
                f"{era.total_papers} papers in this era · "
                f"{len(era.key_papers)} hubs · "
                f"Keywords: {', '.join(era.keywords[:4]) if era.keywords else '—'}"
            )

        # Hub papers for this era — render as cards
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
                    f"font-size:1.2em'>⬇️ {desc[:120]}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center; padding:10px; color:#95a5a6'>"
                    f"⬇️  {era.era_label} → {eras[i + 1].era_label} (知识演变)</div>",
                    unsafe_allow_html=True,
                )

    # Link details in expander
    if path.links:
        with st.expander("🔗 演化链接详情 Evolution Links"):
            for link in path.links:
                st.markdown(
                    f"**{link.from_era}** → **{link.to_era}**  "
                    f"({link.citation_count} citations)  "
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
                    f"Cited: {paper.citation_count}{preprint_tag}"
                    f"{venue_extra}"
                )
                st.markdown(f"*{title}*")
                st.caption(authors)

                if paper.abstract:
                    with st.expander("Abstract"):
                        st.write(paper.abstract[:500])

            with c2:
                # Download button
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

                # DOI link
                if paper.doi:
                    st.link_button(
                        "🔗 DOI",
                        f"https://doi.org/{paper.doi}",
                        use_container_width=True,
                    )

            st.divider()


# ---------------------------------------------------------------------------
# Download all
# ---------------------------------------------------------------------------


def render_download_section(path, explorer):
    """Batch download section for all hub papers."""
    st.subheader("📦 批量下载 Batch Download")

    all_hubs = []
    for era in path.eras:
        all_hubs.extend(era.key_papers)

    # Deduplicate by DOI
    seen = set()
    unique_hubs = []
    for p in all_hubs:
        key = (p.doi or p.id).lower()
        if key not in seen:
            seen.add(key)
            unique_hubs.append(p)

    st.info(
        f"共 {len(unique_hubs)} 篇枢纽论文可下载。"
        f"PDF 将保存至: `{explorer.downloader.get_download_dir()}`"
    )

    if st.button("📥 下载全部枢纽论文 PDF", type="primary", use_container_width=True):
        progress = st.progress(0)
        status = st.empty()

        results = []
        for i, paper in enumerate(unique_hubs):
            status.text(f"下载中 ({i+1}/{len(unique_hubs)}): {paper.title[:80]}...")
            path_result = explorer.downloader.download_pdf(paper)
            results.append((paper, path_result))
            progress.progress((i + 1) / len(unique_hubs))

        success = [r for r in results if r[1] is not None]
        status.text(f"完成: {len(success)}/{len(unique_hubs)} 篇下载成功")
        st.success(
            f"下载完成! {len(success)} 篇 PDF 保存至 "
            f"`{explorer.downloader.get_download_dir()}`"
        )

        # Show failures
        failures = [r for r in results if r[1] is None]
        if failures:
            with st.expander(f"⚠️ {len(failures)} 篇下载失败"):
                for p, _ in failures:
                    st.write(f"- {p.title[:100]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.title("🧬 Literature Evolution Explorer")
    st.caption(
        "输入研究课题 → 自动发现知识演化路径 → 下载关键文献 PDF"
    )

    mode, years_back, max_papers = render_sidebar()

    # Search input
    topic = st.text_input(
        "研究课题 Research Topic",
        placeholder=(
            "e.g. Large Language Model, CRISPR gene editing, "
            "plant phenotyping deep learning, transformer attention mechanism..."
        ),
    )

    col1, col2, _ = st.columns([2, 2, 4])
    with col1:
        search_btn = st.button(
            "🔍 探索演化路径", type="primary", use_container_width=True
        )
    with col2:
        clear_btn = st.button("🗑 清除结果", use_container_width=True)

    if clear_btn:
        st.session_state.pop("evolution_path", None)
        st.session_state.pop("explorer", None)
        st.session_state.pop("last_topic", None)
        st.rerun()

    if search_btn and topic.strip():
        run_search(topic.strip(), mode, years_back, max_papers)

    # Show results
    if "evolution_path" in st.session_state:
        path = st.session_state["evolution_path"]
        explorer = st.session_state["explorer"]

        st.divider()
        render_timeline(path)
        st.divider()
        render_download_section(path, explorer)

    elif not topic.strip():
        # Show placeholder examples
        st.divider()
        st.markdown("### 💡 试试这些例子")
        examples = [
            "`Large Language Model` — 从传统NLP到GPT的演进",
            "`CRISPR gene editing` — 基因编辑技术的发展脉络",
            "`plant phenotyping deep learning` — 植物表型深度学习的方法演化",
            "`transformer attention mechanism` — 注意力机制的进化链",
            "`single cell RNA sequencing` — 单细胞测序技术路线",
        ]
        for ex in examples:
            st.markdown(f"- {ex}")

        st.info(
            "**快速模式**: 输入课题 → 数秒内获得演化主线 + 每阶段关键论文 + PDF 下载\n\n"
            "**全面模式**: 深度挖掘完整知识流变链路，适合写综述、开题报告"
        )


if __name__ == "__main__":
    main()
