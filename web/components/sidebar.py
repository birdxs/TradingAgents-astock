"""Sidebar: stock input, LLM config, and history list."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.checkpointer import clear_checkpoint
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
from web.history import (
    clear_incomplete_task,
    get_history,
    get_incomplete_history,
    record_incomplete_task,
)

_PROVIDERS: list[tuple[str, str]] = [
    ("MiniMax（推荐·国内直连）", "minimax"),
    ("DeepSeek", "deepseek"),
    ("通义千问 Qwen", "qwen"),
    ("智谱 GLM", "glm"),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Google Gemini", "google"),
    ("xAI Grok", "xai"),
    ("OpenRouter（聚合·填 vendor/model 形式 ID）", "openrouter"),
    ("OpenAI 兼容（自定义 base_url·9Router/AI Router/自建代理）", "openai_compatible"),
    ("Ollama（本地）", "ollama"),
]

_PROVIDER_DISPLAY = [name for name, _ in _PROVIDERS]
_PROVIDER_KEYS = [key for _, key in _PROVIDERS]


def _resolve_user_input(raw: str) -> tuple[str, str | None]:
    from tradingagents.dataflows.a_stock import resolve_ticker
    try:
        code = resolve_ticker(raw)
        return code, None
    except ValueError as e:
        return "", str(e)


def _clear_analysis_artifacts(ticker: str, trade_date: str) -> None:
    clear_incomplete_task(ticker, trade_date)
    clear_checkpoint(DEFAULT_CONFIG["data_cache_dir"], ticker, trade_date)


def _render_analysis_controls(raw_ticker: str, trade_date_value: date) -> None:
    tracker = st.session_state.get("tracker")
    is_running = tracker is not None and tracker.is_running
    trade_date = trade_date_value.strftime("%Y-%m-%d")

    pause_col, resume_col, stop_col = st.columns(3)

    pause_disabled = not is_running or tracker.is_paused or tracker.stop_requested
    if pause_col.button("暂停", key="sidebar_pause_analysis", use_container_width=True, disabled=pause_disabled):
        if tracker.pause():
            record_incomplete_task(tracker.ticker, tracker.trade_date, status="paused",
                                   completed_stages=tracker.completed_stages)
        st.rerun()

    resume_disabled = not is_running or not tracker.is_paused or tracker.stop_requested
    if resume_col.button("恢复", key="sidebar_resume_analysis", use_container_width=True, disabled=resume_disabled):
        if tracker.resume():
            record_incomplete_task(tracker.ticker, tracker.trade_date, status="running",
                                   completed_stages=tracker.completed_stages)
        st.rerun()

    can_stop = tracker is not None or bool(raw_ticker.strip())
    if stop_col.button("停止", key="sidebar_stop_analysis", use_container_width=True, disabled=not can_stop):
        target_ticker = tracker.ticker if tracker is not None and tracker.ticker else ""
        target_date = tracker.trade_date if tracker is not None and tracker.trade_date else trade_date

        if not target_ticker:
            target_ticker, err = _resolve_user_input(raw_ticker)
            if err:
                st.error(f"❌ {err}")
                return

        if tracker is not None and tracker.is_running:
            tracker.request_stop()
            clear_incomplete_task(target_ticker, target_date)
        else:
            if tracker is not None:
                tracker.mark_stopped()
                st.session_state["tracker"] = None
            _clear_analysis_artifacts(target_ticker, target_date)

        st.session_state["viewing_history"] = None
        st.success("已清空当前进度；下一次开始分析会从头生成。")
        st.rerun()

    if tracker is not None and tracker.stop_requested:
        st.caption("正在停止并清空，收尾完成后可重新开始。")


def _render_llm_config() -> None:
    """Render LLM provider and model selection controls."""
    provider_idx = st.selectbox(
        "LLM 供应商", range(len(_PROVIDERS)),
        format_func=lambda i: _PROVIDER_DISPLAY[i],
        key="llm_provider_idx", help="选择你配置了 API Key 的供应商",
    )
    provider_key = _PROVIDER_KEYS[provider_idx]
    st.session_state["llm_provider"] = provider_key

    if provider_key in MODEL_OPTIONS:
        quick_options = MODEL_OPTIONS[provider_key]["quick"]
        deep_options = MODEL_OPTIONS[provider_key]["deep"]
        quick_labels = [label for label, _ in quick_options]
        quick_values = [value for _, value in quick_options]
        deep_labels = [label for label, _ in deep_options]
        deep_values = [value for _, value in deep_options]

        quick_idx = st.selectbox("快速思考模型", range(len(quick_options)),
                                 format_func=lambda i: quick_labels[i],
                                 key="quick_model_idx", help="用于常规分析任务，速度优先")
        st.session_state["quick_think_llm"] = quick_values[quick_idx]

        deep_idx = st.selectbox("深度思考模型", range(len(deep_options)),
                                format_func=lambda i: deep_labels[i],
                                key="deep_model_idx", help="用于辩论/决策等需要深度推理的任务")
        st.session_state["deep_think_llm"] = deep_values[deep_idx]
    else:
        custom_quick = st.text_input("快速思考模型 ID", key="custom_quick_model")
        custom_deep = st.text_input("深度思考模型 ID", key="custom_deep_model")
        st.session_state["quick_think_llm"] = custom_quick
        st.session_state["deep_think_llm"] = custom_deep

    base_url_required = provider_key == "openai_compatible"
    st.text_input(
        "API Base URL（第三方/代理" + ("·必填" if base_url_required else "，可选") + "）",
        key="llm_base_url", placeholder="例: https://your-relay.example/v1",
        help="通过第三方中转/代理访问模型时填写网关地址；留空则用所选供应商的官方地址。",
    )
    if base_url_required:
        st.caption("已选「OpenAI 兼容（自定义）」：**Base URL 必填**")

    _scope_labels = ["关闭（走上面选的供应商）", "仅深度节点（Research/Portfolio）", "所有节点（含 7 个工具分析师）"]
    _scope_values = ["off", "deep", "all"]
    scope_idx = st.selectbox(
        "个人 Claude 订阅覆盖 (Agent SDK)", range(len(_scope_labels)),
        format_func=lambda i: _scope_labels[i], key="subscription_scope_idx",
        help="让部分/全部节点经 Claude Agent SDK 走你个人 Pro/Max 订阅额度",
    )
    scope = _scope_values[scope_idx]
    st.session_state["subscription_scope"] = scope
    if scope != "off":
        st.session_state.setdefault("agent_sdk_model", "opus")
        st.text_input("订阅使用的 Claude 模型", key="agent_sdk_model",
                      help="填别名 opus / sonnet（恒指向最新模型，推荐）或完整模型 id。")
        if scope == "all":
            st.caption("⚠️ 「所有节点」会把 7 个分析师全部压到订阅上，订阅是按额度限流的。")
        if os.getenv("ANTHROPIC_API_KEY"):
            st.info("检测到 ANTHROPIC_API_KEY。它**不会**泄进 Agent SDK 子进程。")


def render_sidebar() -> None:
    """Render the sidebar with input controls and history.
    
    所有颜色通过 CSS 变量（var(--text), var(--text-secondary)）动态适配主题，
    组件代码不感知当前是明亮还是暗黑模式。
    """

    st.markdown(
        """
        <div style="text-align:center; margin-bottom:1.5rem;">
            <span style="font-size:2rem; font-weight:800; color:#ff5a1f;">Trading</span>
            <span style="font-size:2rem; font-weight:800; color:var(--text);">Agents</span>
            <span style="font-size:2rem; font-weight:800; color:var(--text);">-</span>
            <span style="font-size:2rem; font-weight:800; color:#ff5a1f;">Astock</span>
            <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:0.2rem;">
                A股多Agent投研系统
            </div>
            <div style="font-size:0.7rem; color:var(--text-secondary); margin-top:0.3rem;">
                by <a href="https://github.com/simonlin1212" style="color:#ff5a1f; text-decoration:none;">simonlin1212</a>
            </div>
        </div>
        """, unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### 新建分析")

    ticker = st.text_input("股票代码", placeholder="例: 300750 或 宁德时代", key="input_ticker",
                           help="输入6位A股代码或中文股票全称")
    trade_date = st.date_input("分析日期", value=date.today(), key="input_date")
    start_date = st.date_input("数据起始日期", value=trade_date.replace(day=1), key="input_start_date",
                               help="技术分析回溯到该日期（默认本月第一天）。")
    st.session_state["market_lookback_days"] = max((trade_date - start_date).days, 5)
    if start_date >= trade_date:
        st.caption("⚠️ 起始日期应早于分析日期，已按最小窗口（5 天）处理。")

    with st.expander("⚙️ 模型配置", expanded=False):
        _render_llm_config()

    tracker = st.session_state.get("tracker")
    is_busy = tracker is not None and tracker.is_running
    is_stopping = is_busy and tracker.stop_requested

    if st.button(
        "开始分析" if not is_busy else "停止中..." if is_stopping else "分析进行中...",
        use_container_width=True, disabled=is_busy or not ticker, type="primary",
    ):
        resolved_code, err = _resolve_user_input(ticker)
        if err:
            st.error(f"❌ {err}")
        else:
            if resolved_code != ticker.strip():
                st.success(f"✅ {ticker.strip()} → {resolved_code}")
            st.session_state["start_analysis"] = {
                "ticker": resolved_code, "trade_date": trade_date.strftime("%Y-%m-%d"), "fresh": True,
            }
            st.session_state["viewing_history"] = None

    _render_analysis_controls(ticker, trade_date)

    st.markdown("---")
    st.markdown("#### 未完成任务")
    incomplete = get_incomplete_history()
    if not incomplete:
        st.caption("暂无未完成任务")
    else:
        for entry in incomplete[:10]:
            t, d = entry["ticker"], entry["trade_date"]
            status_label = {"error": "出错", "paused": "已暂停", "running": "进行中"}.get(entry.get("status"), "可继续")
            step = entry.get("checkpoint_step")
            step_label = f" · step {step}" if step is not None else ""
            label = f"{t}  ·  {d}  ·  {status_label}{step_label}"
            if st.button(label, key=f"resume_{t}_{d}", use_container_width=True, disabled=is_busy):
                st.session_state["start_analysis"] = {"ticker": t, "trade_date": d}
                st.session_state["viewing_history"] = None

    st.markdown("---")
    st.markdown("#### 历史记录")
    history = get_history()
    if not history:
        st.caption("暂无历史记录")
        return
    for entry in history[:20]:
        t, d = entry["ticker"], entry["date"]
        label = f"{t}  ·  {d}"
        if st.button(label, key=f"hist_{t}_{d}", use_container_width=True):
            st.session_state["viewing_history"] = entry["path"]
            st.session_state["start_analysis"] = None

    st.markdown("---")
    st.caption("⚠️ 仅供学习研究，不构成投资建议")
