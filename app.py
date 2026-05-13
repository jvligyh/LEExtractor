"""LEExtractor — Systematic Literature Review Toolkit (Streamlit GUI).

4-Phase gold-standard workflow:
1. Scoping — field landscape exploration
2. Systematic Search — multi-database keyword search
3. Snowballing — citation tracing + similar paper discovery
4. PRISMA — screening + flow diagram + PDF download
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="LEExtractor — Literature Review Toolkit",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from litsearch.search import LiteratureReviewWorkflow, ReviewPhase
from litsearch.prisma import ScreeningDecision
from litsearch.sources import ImpactFactorLookup


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar():
    st.sidebar.title("📚 LEExtractor")
    st.sidebar.caption("Systematic Literature Review Toolkit")
    st.sidebar.caption("系统文献综述工具 · PRISMA 2020 · TARCiS")

    st.sidebar.divider()

    # Global settings
    st.sidebar.subheader("Global Settings / 全局设置")

    years_back = st.sidebar.slider(
        "Years Back / 回溯年数",
        5, 50, 20,
    )

    st.sidebar.divider()

    max_papers = st.sidebar.slider(
        "Max Search Papers / 最大检索论文数",
        50, 500, 200, 50,
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "Sources / 数据源: Semantic Scholar · OpenAlex · arXiv · Crossref\n"
        "Download / 下载: Sci-Hub · arXiv · OpenAccess"
    )
    st.sidebar.caption("v0.3.0 — PRISMA + TARCiS workflow")

    return years_back, max_papers


# ---------------------------------------------------------------------------
# Phase indicator
# ---------------------------------------------------------------------------


PHASE_LABELS = {
    ReviewPhase.SCOPING: "1. Scoping / 领域概览",
    ReviewPhase.SYSTEMATIC_SEARCH: "2. Systematic Search / 系统检索",
    ReviewPhase.SNOWBALLING: "3. Snowballing / 引文追溯",
    ReviewPhase.SCREENING: "4. Screening & PRISMA / 筛选与报告",
    ReviewPhase.COMPLETE: "✓ Complete / 完成",
}


def render_phase_indicator(phase):
    """Show current phase with progress-style indicators."""
    phase_order = {
        ReviewPhase.SCOPING: 0,
        ReviewPhase.SYSTEMATIC_SEARCH: 1,
        ReviewPhase.SNOWBALLING: 2,
        ReviewPhase.SCREENING: 3,
        ReviewPhase.COMPLETE: 4,
    }
    cols = st.columns(4)
    phases = [
        (ReviewPhase.SCOPING, "1", "Scoping"),
        (ReviewPhase.SYSTEMATIC_SEARCH, "2", "Search"),
        (ReviewPhase.SNOWBALLING, "3", "Snowball"),
        (ReviewPhase.SCREENING, "4", "PRISMA"),
    ]
    current_idx = phase_order.get(phase, 0)
    for i, (ph, num, label) in enumerate(phases):
        with cols[i]:
            this_idx = phase_order.get(ph, 0)
            if current_idx == this_idx:
                st.markdown(f"**🔵 {num}. {label}**")
            elif current_idx > this_idx:
                st.markdown(f"✅ {num}. {label}")
            else:
                st.markdown(f"⚪ {num}. {label}")


# ---------------------------------------------------------------------------
# Phase 1: Scoping
# ---------------------------------------------------------------------------


def render_scoping(workflow, years_back):
    st.subheader("Phase 1: Scoping / 领域概览")
    st.caption("Explore the field landscape before committing to a full search.")

    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input(
            "Research Topic / 研究课题",
            value=st.session_state.get("topic", ""),
            placeholder="e.g. mint essential oil biosynthesis, plant phenotyping deep learning...",
            key="scoping_topic",
        )
    with col2:
        direction = st.text_input(
            "Research Direction / 研究方向 (for relevance scoring)",
            value=st.session_state.get("direction", ""),
            placeholder="Describe your focus, e.g. terpenoid biosynthesis pathway...",
            key="scoping_direction",
        )

    if st.button("🔍 Start Scoping / 开始概览", type="primary", use_container_width=True, disabled=not topic.strip()):
        with st.spinner("Searching and analyzing field landscape..."):
            state = workflow.scope_topic(
                topic=topic.strip(),
                research_direction=direction.strip(),
                years_back=years_back,
                initial_limit=50,
            )
            st.session_state["review_state"] = state
            st.session_state["topic"] = topic.strip()
            st.session_state["direction"] = direction.strip()
            st.rerun()

    state = st.session_state.get("review_state")
    if state is None or state.phase != ReviewPhase.SCOPING:
        return

    st.divider()

    # Show scoping results
    if not state.scoping_papers:
        st.info("No scoping results yet. Enter a topic and click 'Start Scoping'.")
        return

    # Stats bar
    cols = st.columns(4)
    cols[0].metric("Papers Found / 检索到文献", len(state.scoping_papers))
    cols[1].metric("Key Journals / 主要期刊", len(state.key_journals))
    cols[2].metric("Key Authors / 主要作者", len(state.key_authors))
    cols[3].metric("Topic Clusters / 主题簇", len(state.topic_clusters))

    st.divider()

    # Topic clusters
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Topic Clusters / 主题簇")
        for cluster_name, keywords in list(state.topic_clusters.items())[:6]:
            st.markdown(f"**{cluster_name}**: {', '.join(keywords)}")

    with col2:
        # Year distribution chart
        if state.year_distribution:
            st.subheader("Publication Timeline / 发表时间分布")
            fig, ax = plt.subplots(figsize=(5, 2.5))
            years = list(state.year_distribution.keys())
            counts = list(state.year_distribution.values())
            ax.bar(years, counts, color="#3498db", alpha=0.8)
            ax.set_xlabel("Year")
            ax.set_ylabel("Count")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    st.divider()

    # Key journals and authors
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Key Journals / 主要期刊")
        for journal, count in state.key_journals[:10]:
            st.markdown(f"- {journal} ({count})")

    with col2:
        st.subheader("Key Authors / 主要作者")
        for author, count in state.key_authors[:10]:
            st.markdown(f"- {author} ({count})")

    st.divider()
    st.info("👉 Go to the **Systematic Search** tab (tab 2) to run the multi-database search.\n\n👉 转到 **系统检索** 标签页（第2个标签）执行多数据库检索。")


# ---------------------------------------------------------------------------
# Phase 2: Systematic Search
# ---------------------------------------------------------------------------


def render_systematic_search(workflow, max_papers, years_back):
    st.subheader("Phase 2: Systematic Search / 系统检索")
    st.caption("Multi-database search: S2 + OpenAlex + arXiv + Crossref")

    state = st.session_state.get("review_state")

    if state is None:
        st.warning("Complete scoping first (Tab 1).")
        return

    # Search config
    col1, col2 = st.columns(2)
    with col1:
        min_cit = st.number_input("Min Citations / 最低引用数", 0, 1000, 0, 10, key="sys_min_cit")
    with col2:
        st.caption("")

    # Show run button only if search hasn't been done yet
    search_not_done = state.phase.value in {ReviewPhase.SCOPING.value}

    if search_not_done:
        if st.button("🔍 Run Systematic Search / 执行系统检索", type="primary", use_container_width=True):
            with st.spinner(f"Searching across all databases for '{state.topic}'..."):
                state = workflow.systematic_search(
                    state,
                    max_papers=max_papers,
                    years_back=years_back,
                    min_citations=min_cit,
                )
                st.session_state["review_state"] = state
                st.rerun()
        st.info("Configure search parameters above, then click the button.")
        return

    st.divider()

    papers = state.search_papers
    if not papers:
        st.warning("Search returned no results. Try broader keywords or increase years back.")
        # Let user re-run with the button even if phase has advanced
        if st.button("🔄 Retry Search / 重新检索", use_container_width=True):
            state = workflow.systematic_search(
                state,
                max_papers=max_papers,
                years_back=years_back,
                min_citations=min_cit,
            )
            st.session_state["review_state"] = state
            st.rerun()
        return

    cols = st.columns(3)
    cols[0].metric("Total Found / 检索结果", len(papers))
    cols[1].metric(
        "Avg Relevance / 平均相关度",
        f"{sum(p.relevance_score for p in papers) / max(len(papers), 1):.3f}",
    )
    cols[2].metric(
        "Avg Citations / 平均引用",
        f"{sum(p.citation_count for p in papers) / max(len(papers), 1):.0f}",
    )

    st.divider()

    # Top papers table
    st.subheader(f"Top 20 Papers / 前20篇文献")
    if_lookup = ImpactFactorLookup()

    for idx, paper in enumerate(papers[:20]):
        with st.container():
            col1, col2 = st.columns([6, 1])
            with col1:
                venue_str = f" | {paper.venue}" if paper.venue else ""
                if_val = if_lookup.get_if_display(paper.venue or "")
                if "N/A" not in if_val:
                    venue_str += f" | {if_val}"
                preprint_tag = " [Preprint]" if paper.source == "arxiv" else ""

                st.markdown(
                    f"**{idx + 1}.** *{paper.title[:200]}*  "
                    f"({paper.year or '?'}){preprint_tag}"
                )
                st.caption(
                    f"👥 {', '.join(a.name for a in paper.authors[:3])}  |  "
                    f"📖 {paper.citation_count} citations  |  "
                    f"🎯 Relevance: {paper.relevance_score:.3f}"
                    f"{venue_str}"
                )
            with col2:
                if paper.url and paper.url.startswith("http"):
                    st.link_button("📥 PDF", paper.url, use_container_width=True)
                if paper.doi:
                    st.link_button("🔗 DOI", f"https://doi.org/{paper.doi}", use_container_width=True)

            if paper.abstract:
                with st.expander("Abstract / 摘要"):
                    st.write(paper.abstract[:500])

            st.divider()

    st.divider()
    st.info("👉 Go to the **Snowballing** tab (tab 3) for citation tracing and similar paper discovery.\n\n👉 转到 **引文追溯** 标签页（第3个标签）执行引文追溯和相似文献发现。")


# ---------------------------------------------------------------------------
# Phase 3: Snowballing
# ---------------------------------------------------------------------------


def render_snowballing(workflow):
    st.subheader("Phase 3: Snowballing + Similar Papers / 引文追溯与相似文献")
    st.caption(
        "TARCiS-aligned citation tracing: forward (cited-by) + backward (references). "
        "Plus bibliographic coupling and co-citation analysis."
    )

    state = st.session_state.get("review_state")
    if state is None or not state.search_papers:
        st.warning("Complete systematic search first.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        num_seeds = st.number_input("Seed Papers / 种子论文数", 3, 30, 10)
    with col2:
        max_rounds = st.number_input("Snowball Rounds / 追溯轮次", 1, 5, 3)
    with col3:
        max_per_dir = st.number_input("Max per Direction / 每方向最多", 10, 100, 50)

    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("🔄 Run Snowballing / 执行引文追溯", type="primary", use_container_width=True):
            with st.spinner("Running iterative forward+backward snowballing..."):
                state = workflow.run_snowballing(
                    state,
                    num_seeds=num_seeds,
                    max_rounds=max_rounds,
                    max_per_direction=max_per_dir,
                )
                st.session_state["review_state"] = state
                st.rerun()

    with btn_col2:
        if st.button("🔗 Find Similar Papers / 查找相似文献", type="secondary", use_container_width=True):
            with st.spinner("Finding similar papers via bibliographic coupling + co-citation..."):
                state = workflow.find_similar(state, num_seeds=num_seeds)
                st.session_state["review_state"] = state
                st.rerun()

    # Show snowball results
    sn_result = state.snowball_result
    if sn_result and sn_result.rounds:
        st.divider()
        st.subheader("Snowballing Results / 引文追溯结果")

        cols = st.columns(3)
        cols[0].metric("Total Rounds / 追溯轮次", len(sn_result.rounds))
        cols[1].metric("Papers Discovered / 新发现文献", sn_result.total_discovered)
        cols[2].metric("Saturated / 是否饱和", "Yes" if sn_result.saturated else "No")

        for rnd in sn_result.rounds:
            with st.expander(
                f"Round {rnd.round_number}: {rnd.count} new papers / {rnd.count} 篇新文献"
            ):
                for p in rnd.new_papers[:10]:
                    st.markdown(
                        f"- **{p.title[:120]}** ({p.year or '?'}) — "
                        f"Cited {p.citation_count}x | Rel: {p.relevance_score:.3f}"
                    )

    # Show similar papers
    similar = state.similar_papers
    if similar:
        st.divider()
        st.subheader(f"Similar Papers / 相似文献 ({len(similar)} found)")

        for paper, score, method in similar[:15]:
            method_label = "BC" if method == "bibliographic_coupling" else "CC"
            st.markdown(
                f"- **{paper.title[:120]}** ({paper.year or '?'}) — "
                f"Score: {score:.2f} ({method_label})"
            )

    if state.phase in {ReviewPhase.SNOWBALLING, ReviewPhase.SCREENING, ReviewPhase.COMPLETE}:
        st.divider()
        st.info("👉 Go to the **PRISMA** tab (tab 4) to screen papers and generate the PRISMA flow diagram.\n\n👉 转到 **PRISMA** 标签页（第4个标签）筛选文献并生成PRISMA流程图。")


# ---------------------------------------------------------------------------
# Phase 4: PRISMA + Screening
# ---------------------------------------------------------------------------


def render_prisma(workflow):
    st.subheader("Phase 4: Screening & PRISMA / 筛选与PRISMA报告")
    st.caption("Screen papers by title/abstract and generate a PRISMA 2020 flow diagram.")

    state = st.session_state.get("review_state")
    if state is None:
        st.warning("Complete earlier phases first.")
        return

    report = state.prisma.generate_report()

    # Stats
    cols = st.columns(4)
    cols[0].metric("Total Tracked / 追踪文献", report.records_after_dedup)
    cols[1].metric("Screened / 已筛选", report.records_screened)
    cols[2].metric("Included / 已纳入", report.studies_included)
    cols[3].metric("Pending / 待筛选", report.records_after_dedup - report.records_screened)

    st.divider()

    # Screening controls
    col1, col2 = st.columns(2)
    with col1:
        threshold = st.slider(
            "Auto-Screen Threshold / 自动筛选阈值",
            0.0, 1.0, 0.15, 0.01,
            help="Papers with relevance score >= threshold are auto-accepted, below are rejected.",
        )
    with col2:
        st.caption("")
        if st.button("⚡ Auto-Screen / 自动筛选", type="primary", use_container_width=True):
            with st.spinner("Auto-screening papers by relevance..."):
                state = workflow.auto_screen(state, relevance_threshold=threshold)
                st.session_state["review_state"] = state
                st.rerun()

    st.divider()

    # Manual screening queue
    queue = workflow.get_screening_queue(state)
    if queue:
        st.subheader(f"Manual Screening Queue / 手动筛选队列 ({len(queue)} remaining)")

        for record in queue[:20]:
            paper = record.paper
            with st.container():
                col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
                with col1:
                    st.markdown(
                        f"**{paper.title[:150]}** ({paper.year or '?'})"
                    )
                    st.caption(
                        f"Source: {record.source} | "
                        f"Citations: {paper.citation_count} | "
                        f"Relevance: {record.relevance_score:.3f}"
                    )
                with col2:
                    if st.button("✅ Accept", key=f"acc_{paper.id[:30]}", use_container_width=True):
                        workflow.screen_paper(state, paper.id, ScreeningDecision.ACCEPT)
                        st.session_state["review_state"] = state
                        st.rerun()
                with col3:
                    if st.button("❓ Maybe", key=f"may_{paper.id[:30]}", use_container_width=True):
                        workflow.screen_paper(state, paper.id, ScreeningDecision.MAYBE)
                        st.session_state["review_state"] = state
                        st.rerun()
                with col4:
                    if st.button("❌ Reject", key=f"rej_{paper.id[:30]}", use_container_width=True):
                        workflow.screen_paper(state, paper.id, ScreeningDecision.REJECT)
                        st.session_state["review_state"] = state
                        st.rerun()

    # Accepted papers
    included = workflow.get_included_papers(state)
    if included:
        st.divider()
        st.subheader(f"Included Papers / 已纳入文献 ({len(included)})")

        for paper in included[:15]:
            with st.container():
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(
                        f"- **{paper.title[:150]}** ({paper.year or '?'}) — "
                        f"Cited {paper.citation_count}x"
                    )
                with col2:
                    if paper.url and paper.url.startswith("http"):
                        st.link_button("📥 PDF", paper.url, use_container_width=True)

    st.divider()

    # Generate PRISMA report
    if st.button("📊 Generate PRISMA Report / 生成PRISMA流程图", type="primary", use_container_width=True):
        report = workflow.generate_prisma_report(state)
        st.session_state["review_state"] = state
        st.rerun()

    # Show PRISMA diagram
    if state.phase == ReviewPhase.COMPLETE or report.studies_included > 0:
        st.divider()
        st.subheader("PRISMA 2020 Flow Diagram / PRISMA流程图")

        report = state.prisma.generate_report()
        mermaid = report.to_mermaid()
        st.markdown(mermaid)

        # Flow data as expandable JSON
        with st.expander("Flow Data / 流程数据"):
            st.json(report.to_flow_dict())

    # Download section
    if included:
        st.divider()
        st.subheader("📦 Batch Download / 批量下载")

        st.info(
            f"{len(included)} papers ready for download. "
            f"PDFs saved to: `{workflow.downloader.get_download_dir()}`"
        )

        if st.button("📥 Download All Included PDFs / 下载全部纳入文献", type="primary", use_container_width=True):
            progress = st.progress(0)
            status_text = st.empty()

            results = []
            for i, paper in enumerate(included):
                status_text.text(f"Downloading ({i + 1}/{len(included)}): {paper.title[:80]}...")
                path = workflow.downloader.download_pdf(paper)
                results.append((paper, path))
                progress.progress((i + 1) / len(included))

            success = [r for r in results if r[1] is not None]
            status_text.text(f"Done: {len(success)}/{len(included)} succeeded")
            st.success(
                f"Download complete! {len(success)} PDFs saved to "
                f"`{workflow.downloader.get_download_dir()}`"
            )

            failures = [r for r in results if r[1] is None]
            if failures:
                with st.expander(f"⚠️ {len(failures)} failed / 下载失败"):
                    for p, _ in failures:
                        st.write(f"- {p.title[:100]}")

    # Export buttons
    if included:
        st.divider()
        st.subheader("Export / 导出")

        col1, col2 = st.columns(2)
        with col1:
            csv_data = workflow.export_included_csv(state)
            st.download_button(
                "📄 Download CSV",
                csv_data,
                file_name=f"literature_review_{state.topic[:30]}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            ris_data = workflow.export_included_ris(state)
            st.download_button(
                "📚 Download RIS (EndNote/Zotero)",
                ris_data,
                file_name=f"literature_review_{state.topic[:30]}.ris",
                mime="application/x-research-info-systems",
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.title("📚 LEExtractor")
    st.caption(
        "Systematic Literature Review Toolkit — "
        "Scoping → Systematic Search → Snowballing → PRISMA → PDF Download\n"
        "系统文献综述工具 — 领域概览→系统检索→引文追溯→PRISMA筛选→PDF下载"
    )

    years_back, max_papers = render_sidebar()

    # Initialize workflow
    if "workflow" not in st.session_state:
        st.session_state["workflow"] = LiteratureReviewWorkflow()

    workflow = st.session_state["workflow"]
    state = st.session_state.get("review_state")

    # Phase indicator
    if state is not None:
        render_phase_indicator(state.phase)
        st.divider()

    # Tabs for the 4 phases
    tab1, tab2, tab3, tab4 = st.tabs([
        "1. Scoping / 领域概览",
        "2. Systematic Search / 系统检索",
        "3. Snowballing / 引文追溯",
        "4. PRISMA & Export / 筛选与导出",
    ])

    with tab1:
        render_scoping(workflow, years_back)

    with tab2:
        render_systematic_search(workflow, max_papers, years_back)

    with tab3:
        render_snowballing(workflow)

    with tab4:
        render_prisma(workflow)

    # Footer
    st.divider()
    st.caption(
        "Methodology: Gusenbauer (2024) + TARCiS statement + PRISMA 2020 | "
        "Sources: Semantic Scholar · OpenAlex · arXiv · Crossref | "
        "PDF: Sci-Hub · arXiv · OpenAccess"
    )


if __name__ == "__main__":
    main()
