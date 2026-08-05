"""TradingAgents A股分析 — Streamlit Web UI."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# override=True：让 .env 的值优先于进程里可能残留的空/旧环境变量（#66）。
# 注意：load_dotenv 仅在进程启动时执行一次，启动后修改 .env 仍需重启 Web 服务才生效。
load_dotenv(_PROJECT_ROOT / ".env", override=True)

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402

from web.components.progress_panel import render_progress  # noqa: E402
from web.components.report_viewer import render_report  # noqa: E402
from web.components.sidebar import render_sidebar  # noqa: E402
from web.history import clear_incomplete_task, extract_signal, load_analysis  # noqa: E402
from web.progress import ProgressTracker  # noqa: E402
from web.runner import run_analysis_in_thread  # noqa: E402

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TradingAgents-Astock A股分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme configuration ───────────────────────────────────────────────────────

# 主题配色方案
_THEMES = {
    "light": {
        "bg": "#ffffff",
        "sidebar_bg": "#f5f5f5",
        "text": "#1a1a1a",
        "text_secondary": "#666666",
        "border": "#e0e0e0",
        "input_bg": "#ffffff",
        "input_border": "#d0d0d0",
        "button_secondary_bg": "#f5f5f5",
        "button_secondary_border": "#d0d0d0",
        "button_secondary_hover": "#e8e8e8",
    },
    "dark": {
        "bg": "#0a0a0a",
        "sidebar_bg": "#0f0f0f",
        "text": "#f5f1eb",
        "text_secondary": "#888888",
        "border": "#1a1a1a",
        "input_bg": "#161616",
        "input_border": "#2a2a2a",
        "button_secondary_bg": "#161616",
        "button_secondary_border": "#2a2a2a",
        "button_secondary_hover": "#1e1e1e",
    },
}

# 初始化主题状态
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

def _get_theme() -> dict:
    """获取当前主题配色"""
    return _THEMES.get(st.session_state.get("theme", "light"), _THEMES["light"])

def _render_theme_css() -> None:
    """渲染主题相关的 CSS（使用 CSS 变量）"""
    theme = _get_theme()
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

        /* CSS 变量定义 */
        :root {{
            --bg: {theme['bg']};
            --sidebar-bg: {theme['sidebar_bg']};
            --text: {theme['text']};
            --text-secondary: {theme['text_secondary']};
            --border: {theme['border']};
            --input-bg: {theme['input_bg']};
            --input-border: {theme['input_border']};
            --button-secondary-bg: {theme['button_secondary_bg']};
            --button-secondary-border: {theme['button_secondary_border']};
            --button-secondary-hover: {theme['button_secondary_hover']};
        }}

        /* Hide Streamlit chrome for clean video recording.
           IMPORTANT: do NOT `display:none` the whole header OR the whole toolbar.
           In Streamlit >= 1.36 the "expand sidebar" button lives *inside* the
           toolbar (header > stToolbar > stExpandSidebarButton), so hiding either
           one makes a collapsed sidebar impossible to reopen (issue #36). Instead
           keep the header/toolbar in the DOM, make the header transparent, and
           hide only the individual chrome widgets we don't want on camera. */
        #MainMenu,
        footer,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        div[data-testid="stToolbarActions"],
        div[data-testid="stAppDeployButton"],
        span[data-testid="stMainMenu"] {{ display: none !important; }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
            box-shadow: none !important;
        }}
        /* Keep the sidebar collapse / expand controls always visible & clickable.
           Selector list spans multiple Streamlit versions. */
        button[data-testid="stExpandSidebarButton"],
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {{
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, sans-serif;
        }}
        .stApp {{
            background: var(--bg);
        }}
        section[data-testid="stSidebar"] {{
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border);
        }}
        .stMetric label {{ color: var(--text-secondary) !important; font-size: 0.8rem !important; }}
        .stMetric [data-testid="stMetricValue"] {{
            color: #ff5a1f !important;
            font-weight: 700 !important;
        }}
        .stProgress > div > div > div {{
            background: linear-gradient(90deg, #ff5a1f, #ff8c42) !important;
        }}
        button[kind="primary"] {{
            background: linear-gradient(135deg, #ff5a1f, #ff8c42) !important;
            border: none !important;
            font-weight: 700 !important;
            letter-spacing: 0.05em !important;
            box-shadow: 0 4px 15px rgba(255,90,31,0.3) !important;
            transition: all 0.2s ease !important;
        }}
        button[kind="primary"]:hover {{
            background: linear-gradient(135deg, #e04d15, #ff5a1f) !important;
            box-shadow: 0 6px 20px rgba(255,90,31,0.4) !important;
            transform: translateY(-1px) !important;
        }}
        /* Secondary buttons (history items) */
        button[kind="secondary"] {{
            background: var(--button-secondary-bg) !important;
            border: 1px solid var(--button-secondary-border) !important;
            color: var(--text) !important;
            transition: all 0.2s ease !important;
        }}
        button[kind="secondary"]:hover {{
            background: var(--button-secondary-hover) !important;
            border-color: #ff5a1f !important;
            color: #ff5a1f !important;
        }}
        .stExpander {{
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: var(--text-secondary) !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: #ff5a1f !important;
            border-bottom-color: #ff5a1f !important;
        }}
        div[data-testid="stDownloadButton"] button {{
            background: var(--sidebar-bg) !important;
            border: 1px solid #ff5a1f !important;
            color: #ff5a1f !important;
        }}
        /* Text input styling */
        input[data-testid="stTextInputRootElement"] input,
        .stTextInput input {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}
        .stTextInput input:focus {{
            border-color: #ff5a1f !important;
            box-shadow: 0 0 0 1px #ff5a1f !important;
        }}
        /* Date input styling */
        .stDateInput input {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def _render_theme_toggle() -> None:
    """渲染主题切换按钮"""
    current_theme = st.session_state.get("theme", "light")
    is_dark = current_theme == "dark"
    
    # 使用两列布局放置切换按钮
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            label="🌙 暗黑" if not is_dark else "🌙 已切换暗黑",
            key="theme_toggle_dark",
            use_container_width=True,
            type="secondary" if not is_dark else "primary",
        ):
            st.session_state["theme"] = "dark"
            st.rerun()
    with col2:
        if st.button(
            label="☀️ 明亮" if is_dark else "☀️ 已切换明亮",
            key="theme_toggle_light",
            use_container_width=True,
            type="primary" if not is_dark else "secondary",
        ):
            st.session_state["theme"] = "light"
            st.rerun()


# ── Render theme CSS ─────────────────────────────────────────────────────────

_render_theme_css()

# ── Build config ─────────────────────────────────────────────────────────────

def _build_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = st.session_state.get("llm_provider", "minimax")
    config["deep_think_llm"] = st.session_state.get("deep_think_llm", "MiniMax-M2.7")
    config["quick_think_llm"] = st.session_state.get("quick_think_llm", "MiniMax-M2.7-highspeed")
    # Optional third-party / proxy endpoint. Sidebar input wins, else .env BACKEND_URL.
    backend_url = (st.session_state.get("llm_base_url") or os.getenv("BACKEND_URL") or "").strip()
    config["backend_url"] = backend_url or None
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    # Analysis window (#16): start-date input in the sidebar → look-back days.
    config["market_lookback_days"] = st.session_state.get("market_lookback_days")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["checkpoint_enabled"] = True
    config["output_language"] = "Chinese"
    # Optional: route nodes through a personal Claude Pro/Max subscription (Agent
    # SDK). Scope: "deep" = Research/Portfolio only; "all" = + the 7 analysts.
    # Leaving the fallback keys None makes the graph fall back to the
    # sidebar-selected llm_provider + models on quota/failure.
    scope = st.session_state.get("subscription_scope", "off")
    # 侧栏那个输入框只配**深度节点**的模型。不要把它同时赋给 quick——
    # quick 节点有 7 个分析师 + 多空/交易员/风险辩手，把深度节点的 opus 复制过去
    # 会让订阅额度烧得极快，也与 README / 侧栏提示所说的「quick 默认 sonnet」矛盾。
    # quick 的模型交给 DEFAULT_CONFIG（默认 sonnet），需要时在 config 层单独覆盖。
    sub_model = st.session_state.get("agent_sdk_model")
    if scope in ("deep", "all"):
        config["deep_think_provider_override"] = "claude_agent_sdk"
        if sub_model:
            config["agent_sdk_model"] = sub_model
    if scope == "all":
        config["quick_think_provider_override"] = "claude_agent_sdk"
    return config


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    render_sidebar()
    # 在侧栏底部添加主题切换
    st.markdown("---")
    _render_theme_toggle()


# ── Handle "Start Analysis" trigger ──────────────────────────────────────────

start_req = st.session_state.pop("start_analysis", None)
if start_req:
    if start_req.get("fresh"):
        from tradingagents.graph.checkpointer import clear_checkpoint

        clear_incomplete_task(start_req["ticker"], start_req["trade_date"])
        clear_checkpoint(
            DEFAULT_CONFIG["data_cache_dir"],
            start_req["ticker"],
            start_req["trade_date"],
        )

    tracker = ProgressTracker(
        ticker=start_req["ticker"],
        trade_date=start_req["trade_date"],
    )
    st.session_state["tracker"] = tracker
    st.session_state["viewing_history"] = None
    run_analysis_in_thread(
        ticker=start_req["ticker"],
        trade_date=start_req["trade_date"],
        config=_build_config(),
        tracker=tracker,
    )


# ── Main area state machine ─────────────────────────────────────────────────

tracker: ProgressTracker | None = st.session_state.get("tracker")
viewing_history: str | None = st.session_state.get("viewing_history")

# State 1: Viewing a historical analysis
if viewing_history:
    try:
        state = load_analysis(viewing_history)
        signal = extract_signal(state)
        ticker = Path(viewing_history).parent.parent.name
        trade_date = Path(viewing_history).stem.replace("full_states_log_", "")
        render_report(state, ticker, trade_date, signal)
    except Exception as exc:
        st.error(f"加载失败: {exc}")

# State 2: Analysis running
elif tracker and tracker.is_running:
    render_progress(tracker)
    time.sleep(2)
    st.rerun()

# State 3: Analysis complete
elif tracker and tracker.is_complete:
    render_report(
        tracker.final_state,
        tracker.ticker,
        tracker.trade_date,
        tracker.signal,
        elapsed=tracker.elapsed,
    )

# State 4: Analysis errored
elif tracker and tracker.error:
    st.error(f"分析失败: {tracker.error}")
    st.caption("已完成阶段会保存在本地断点中；修复模型额度或配置后，可以继续未完成的部分。")
    if st.button("继续未完成任务", type="primary"):
        st.session_state["start_analysis"] = {
            "ticker": tracker.ticker,
            "trade_date": tracker.trade_date,
        }
        st.session_state["viewing_history"] = None
        st.rerun()

# State 0: Idle — welcome screen
else:
    theme = _get_theme()
    st.markdown(
        f"""
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
            text-align: center;
        ">
            <div style="font-size: 4rem; margin-bottom: 1rem;">📈</div>
            <div style="
                font-size: 2.5rem;
                font-weight: 900;
                margin-bottom: 0.5rem;
            ">
                <span style="color: #ff5a1f;">Trading</span><span style="color: {theme['text']};">Agents</span><span style="color: {theme['text']};">-</span><span style="color: #ff5a1f;">Astock</span>
            </div>
            <div style="color: {theme['text_secondary']}; font-size: 1.1rem; max-width: 500px; line-height: 1.6;">
                A股多Agent投研分析系统<br>
                7位AI分析师 → 质量门控 → 多空辩论 → 风控评估 → 最终决策
            </div>
            <div style="
                margin-top: 2rem;
                padding: 1rem 2rem;
                border: 1px solid {theme['border']};
                border-radius: 12px;
                color: {theme['text_secondary']};
                font-size: 0.9rem;
            ">
                ← 在左侧输入股票代码，开始分析
            </div>
            <div style="
                margin-top: 2.5rem;
                padding: 0.8rem 1.5rem;
                color: {theme['text_secondary']};
                font-size: 0.75rem;
                max-width: 500px;
                line-height: 1.6;
                border-top: 1px solid {theme['border']};
            ">
                ⚠️ 本项目仅供学习研究与技术演示，不构成任何投资建议。<br>
                投资决策请咨询持牌专业机构。作者不对使用本工具产生的任何损失承担责任。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
