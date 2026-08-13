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

# ── Theme configuration（CSS 变量架构）──────────────────────────────────────

# 主题配色方案：所有颜色通过 CSS 变量注入，一套模板适配两个主题。
# dark 配色与原项目暗黑主题完全一致。
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

# 主题持久化：存到 URL 参数，刷新页面不丢失
if "theme" not in st.session_state:
    saved = st.query_params.get("theme", "dark")
    if isinstance(saved, list):
        saved = saved[0] if saved else "dark"
    st.session_state["theme"] = saved if saved in ("light", "dark") else "dark"


def _get_theme() -> dict:
    """获取当前主题配色"""
    return _THEMES.get(st.session_state.get("theme", "dark"), _THEMES["dark"])


def _render_theme_css() -> None:
    """渲染主题 CSS：CSS 变量 + 精确 data-testid 选择器，适配所有组件。"""
    theme = _get_theme()
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

        /* ── CSS 变量（两个主题共用同一套变量名） ── */
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

        /* Hide Streamlit chrome for clean video recording. */
        #MainMenu, footer, div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"], div[data-testid="stToolbarActions"],
        div[data-testid="stAppDeployButton"], span[data-testid="stMainMenu"] {{ display: none !important; }}
        header[data-testid="stHeader"] {{
            background: transparent !important; box-shadow: none !important;
        }}
        button[data-testid="stExpandSidebarButton"],
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {{
            display: flex !important; visibility: visible !important; opacity: 1 !important;
        }}

        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, sans-serif;
        }}
        .stApp {{ background: var(--bg); }}
        section[data-testid="stSidebar"] {{
            background: var(--sidebar-bg);
            border-right: 1px solid var(--border);
        }}
        .stMetric label {{ color: var(--text-secondary) !important; font-size: 0.8rem !important; }}
        .stMetric [data-testid="stMetricValue"] {{
            color: #ff5a1f !important; font-weight: 700 !important;
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

        /* ── Expander（summary 选择器，完美覆盖折叠/展开/hover 所有状态）── */
        .stExpander {{
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            background: var(--sidebar-bg) !important;
        }}
        .stExpander summary {{
            background: var(--sidebar-bg) !important;
            color: var(--text) !important;
        }}
        .stExpander summary:hover {{
            background: var(--bg) !important;
        }}
        .stExpander [data-testid="stExpanderDetails"] {{
            background: var(--bg) !important;
        }}
        .stExpander [data-testid="stExpanderDetails"] p,
        .stExpander [data-testid="stExpanderDetails"] li,
        .stExpander [data-testid="stExpanderDetails"] span,
        .stExpander [data-testid="stExpanderDetails"] label {{
            color: var(--text) !important;
        }}

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab"] {{
            color: var(--text-secondary) !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: #ff5a1f !important;
            border-bottom-color: #ff5a1f !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            background: var(--sidebar-bg) !important;
            border-bottom: 1px solid var(--border) !important;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            background: var(--bg) !important;
            border: 1px solid var(--border) !important;
            border-top: none !important;
            padding: 1rem !important;
        }}

        /* ── Download button ── */
        div[data-testid="stDownloadButton"] button {{
            background: var(--sidebar-bg) !important;
            border: 1px solid #ff5a1f !important;
            color: #ff5a1f !important;
            font-weight: 600 !important;
        }}

        /* ── Text input ── */
        input[data-testid="stTextInputRootElement"] input, .stTextInput input {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}
        .stTextInput input:focus {{
            border-color: #ff5a1f !important;
            box-shadow: 0 0 0 1px #ff5a1f !important;
        }}
        .stTextInput label {{ color: var(--text) !important; }}

        /* ── Date input ── */
        .stDateInput input {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}
        .stDateInput label {{ color: var(--text) !important; }}

        /* ── Calendar popup (Baseweb Datepicker) ── */
        [data-baseweb="popover"] div[data-baseweb="calendar"] {{
            background: var(--bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.12) !important;
        }}
        [data-baseweb="calendar"] {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}
        [data-baseweb="calendar"] * {{ color: var(--text) !important; }}
        [data-baseweb="calendar-header"] {{ background: var(--bg) !important; }}
        [data-baseweb="calendar"] button {{
            background: transparent !important;
            color: var(--text) !important;
        }}
        [data-baseweb="calendar"] button:hover {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}
        [data-baseweb="calendar"] [role="columnheader"] {{
            background: var(--bg) !important;
            color: var(--text-secondary) !important;
        }}
        [data-baseweb="day"] {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}
        [data-baseweb="day"]:hover {{
            background: var(--button-secondary-hover) !important;
            color: var(--text) !important;
        }}
        [data-baseweb="day"][aria-selected="true"] {{
            background: #ff5a1f !important;
            color: #ffffff !important;
        }}
        [data-baseweb="day"][aria-selected="true"]:hover {{
            background: #e04d15 !important;
        }}
        [data-baseweb="day-highlighted"] {{
            background: var(--button-secondary-hover) !important;
        }}
        [data-baseweb="day-disabled"] {{
            background: var(--button-secondary_bg) !important;
            color: var(--text-secondary) !important;
        }}
        [data-baseweb="calendar"] [aria-current="date"] {{
            background: rgba(255, 90, 31, 0.1) !important;
            color: #ff5a1f !important;
        }}

        /* ── Selectbox dropdown ── */
        .stSelectbox > div > div {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}
        .stSelectbox label {{ color: var(--text) !important; }}
        div[data-baseweb="popover"] > div, div[data-baseweb="menu"],
        ul[role="listbox"] {{
            background: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
        }}
        ul[role="listbox"] li, div[data-baseweb="option"] span {{ color: var(--text) !important; }}
        ul[role="listbox"] li:hover, div[data-baseweb="option"]:hover {{
            background: var(--button-secondary-hover) !important;
        }}

        /* ── Textarea ── */
        .stTextArea textarea {{
            background: var(--input-bg) !important;
            border-color: var(--input-border) !important;
            color: var(--text) !important;
        }}

        /* ── Widget labels & markdown ── */
        div[data-testid="stWidgetLabel"] label,
        div[data-testid="stMarkdown"] p,
        div[data-testid="stMarkdown"] h1,
        div[data-testid="stMarkdown"] h2,
        div[data-testid="stMarkdown"] h3,
        div[data-testid="stCaption"] {{
            color: var(--text) !important;
        }}
        div[data-testid="stMarkdown"] {{ color: var(--text) !important; }}
        div[data-testid="stExpander"] [data-testid="stMarkdown"] {{ color: var(--text) !important; }}
        div[data-testid="stTabs"] [data-testid="stMarkdown"] {{ color: var(--text) !important; }}

        /* ── Placeholder ── */
        div[data-testid="stTextInputRootElement"] input::placeholder,
        div[data-testid="stDateInput"] input::placeholder {{
            color: var(--text-secondary) !important;
        }}

        /* ── Checkbox / Radio ── */
        div[data-testid="stCheckbox"] label,
        div[data-testid="stRadio"] label {{ color: var(--text) !important; }}

        /* ── Sidebar inner component text ── */
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {{
            color: var(--text) !important;
        }}

        /* ── Alerts ── */
        div[data-testid="stAlert"] {{
            background: rgba(255,90,31,0.08) !important;
            border-color: rgba(255,90,31,0.3) !important;
            color: var(--text) !important;
        }}
        div[data-testid="stSuccess"] {{
            background: rgba(34,197,94,0.08) !important;
            border-color: rgba(34,197,94,0.3) !important;
            color: var(--text) !important;
        }}
        div[data-testid="stError"] {{
            background: rgba(239,68,68,0.08) !important;
            border-color: rgba(239,68,68,0.3) !important;
            color: var(--text) !important;
        }}
        div[data-testid="stWarning"] {{
            background: rgba(234,179,8,0.08) !important;
            border-color: rgba(234,179,8,0.3) !important;
            color: var(--text) !important;
        }}

        /* ── Code ── */
        code {{
            background: var(--button-secondary-bg) !important;
            color: #ff5a1f !important;
            border: 1px solid var(--input-border) !important;
        }}
        pre {{
            background: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
        }}

        /* ── Scrollbar ── */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg) !important; }}
        ::-webkit-scrollbar-thumb {{ background: var(--border) !important; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-secondary) !important; }}

        /* ── Metric cards ── */
        div[data-testid="stMetric"] {{
            background: var(--bg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            padding: 0.8rem !important;
        }}

        /* ── Sidebar theme toggle button ── */
        button[data-testid="theme-toggle-btn"] {{
            background: var(--button-secondary-bg) !important;
            border: 1px solid var(--button-secondary-border) !important;
            color: var(--text) !important;
            width: 100% !important;
            padding: 8px !important;
            border-radius: 8px !important;
            font-size: 1.2rem !important;
            cursor: pointer !important;
            transition: all 0.2s ease !important;
        }}
        button[data-testid="theme-toggle-btn"]:hover {{
            background: var(--button-secondary-hover) !important;
            border-color: #ff5a1f !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Render theme CSS ─────────────────────────────────────────────────────────

_render_theme_css()


# ── Build config ─────────────────────────────────────────────────────────────

def _build_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = st.session_state.get("llm_provider", "minimax")
    config["deep_think_llm"] = st.session_state.get("deep_think_llm", "MiniMax-M2.7")
    config["quick_think_llm"] = st.session_state.get("quick_think_llm", "MiniMax-M2.7-highspeed")
    backend_url = (st.session_state.get("llm_base_url") or os.getenv("BACKEND_URL") or "").strip()
    config["backend_url"] = backend_url or None
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    config["market_lookback_days"] = st.session_state.get("market_lookback_days")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["checkpoint_enabled"] = True
    config["output_language"] = "Chinese"
    scope = st.session_state.get("subscription_scope", "off")
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
    # 主题切换按钮：仅图标，位于侧边栏底部
    theme = st.session_state["theme"]
    toggle_icon = "☀️" if theme == "dark" else "🌙"
    toggle_help = "切换到明亮模式" if theme == "dark" else "切换到暗黑模式"
    if st.button(toggle_icon, key="theme_toggle-btn", use_container_width=True, help=toggle_help):
        new_theme = "light" if theme == "dark" else "dark"
        st.session_state["theme"] = new_theme
        st.query_params["theme"] = new_theme
        st.rerun()


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

if viewing_history:
    try:
        state = load_analysis(viewing_history)
        signal = extract_signal(state)
        ticker = Path(viewing_history).parent.parent.name
        trade_date = Path(viewing_history).stem.replace("full_states_log_", "")
        render_report(state, ticker, trade_date, signal)
    except Exception as exc:
        st.error(f"加载失败: {exc}")

elif tracker and tracker.is_running:
    render_progress(tracker)
    time.sleep(2)
    st.rerun()

elif tracker and tracker.is_complete:
    render_report(
        tracker.final_state,
        tracker.ticker,
        tracker.trade_date,
        tracker.signal,
        elapsed=tracker.elapsed,
    )

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

else:
    # 首页欢迎区，使用 CSS 变量动态配色
    st.markdown(
        """
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
                <span style="color: #ff5a1f;">Trading</span><span style="color: var(--text);">Agents</span><span style="color: var(--text);">-</span><span style="color: #ff5a1f;">Astock</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 1.1rem; max-width: 500px; line-height: 1.6;">
                A股多Agent投研分析系统<br>
                7位AI分析师 → 质量门控 → 多空辩论 → 风控评估 → 最终决策
            </div>
            <div style="
                margin-top: 2rem;
                padding: 1rem 2rem;
                border: 1px solid var(--border);
                border-radius: 12px;
                color: var(--text-secondary);
                font-size: 0.9rem;
            ">
                ← 在左侧输入股票代码，开始分析
            </div>
            <div style="
                margin-top: 2.5rem;
                padding: 0.8rem 1.5rem;
                color: var(--text-secondary);
                font-size: 0.75rem;
                max-width: 500px;
                line-height: 1.6;
                border-top: 1px solid var(--border);
            ">
                ⚠️ 本项目仅供学习研究与技术演示，不构成任何投资建议。<br>
                投资决策请咨询持牌专业机构。作者不对使用本工具产生的任何损失承担责任。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
