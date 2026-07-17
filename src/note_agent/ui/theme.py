"""Dark, low-saturation theme + layout CSS. ChatGPT / Notion / Linear feel."""

from __future__ import annotations

import os
import streamlit as st

# Height (px) of the two independently-scrolling main panes. Tuned to fit a
# single viewport alongside the app header, task card and bottom composer.
PANE_HEIGHT = 430
STATUS_HEIGHT = 430

_CSS = """
<style>
:root {
  --na-bg: #111214; --na-panel: #191a1d; --na-panel-alt: #1e2024;
  --na-border: #2a2c31; --na-text: #e6e7ea; --na-muted: #8b8e96;
  --na-accent: #e6e7ea; --na-hover: #26282d;
  --na-ok: #3fb779; --na-run: #e0a44b; --na-err: #e0605e;
}
.stApp { background: var(--na-bg); color: var(--na-text); }

/* Tighten the top padding so the workspace fits one screen. */
.block-container { padding-top: 2.2rem; padding-bottom: 6.5rem; max-width: 1500px; }

/* Sidebar: quiet panel. */
section[data-testid="stSidebar"] { background: var(--na-panel); border-right: 1px solid var(--na-border); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

/* Project list: natural rows, no boxes; hover = rounded grey; selected stays lit. */
section[data-testid="stSidebar"] .stButton button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--na-text) !important; text-align: left !important; justify-content: flex-start !important;
  border-radius: 8px !important; padding: .34rem .55rem !important; font-weight: 400 !important;
  line-height: 1.25 !important; min-height: 0 !important;
}
section[data-testid="stSidebar"] .stButton button p {
  text-align: left !important; width: 100% !important; margin: 0 !important;
  white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
}
section[data-testid="stSidebar"] .stButton button > div {
  width: 100% !important; align-items: flex-start !important;
  justify-content: flex-start !important; text-align: left !important;
}
section[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"] {
  width: 100% !important; text-align: left !important;
}
/* Kill the extra vertical gap between list rows. */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .12rem !important; }
section[data-testid="stSidebar"] .stButton { margin: 0 !important; }
section[data-testid="stSidebar"] .stButton button:hover { background: var(--na-hover) !important; color: #fff !important; }
section[data-testid="stSidebar"] [class*="st-key-na_project_row_active_"] [class*="st-key-hist_"] button { background: var(--na-hover) !important; color: #fff !important; }
section[data-testid="stSidebar"] .st-key-na_newproj button { color: var(--na-muted) !important; }
section[data-testid="stSidebar"] .st-key-na_newproj button:hover { color: #fff !important; }
/* Project row actions: no-box arrow trigger + fixed-width floating menu. */
section[data-testid="stSidebar"] [class*="st-key-na_project_row_"] {
  position: relative !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_project_row_"] [class*="st-key-hist_"] button {
  padding-right: 2rem !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_rename_"] button,
section[data-testid="stSidebar"] [class*="st-key-na_delete_"] button {
  min-height: 34px !important; height: 34px !important;
  padding: 0 .65rem !important; justify-content: flex-start !important;
  text-align: left !important; font-size: .9rem !important;
  color: var(--na-text) !important; border-radius: 6px !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_project_actions_"] {
  position: absolute !important; right: .45rem !important; top: .2rem !important;
  width: 24px !important; min-width: 24px !important; max-width: 24px !important;
  z-index: 30 !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_project_actions_"] button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--na-muted) !important; min-height: 24px !important; height: 24px !important;
  width: 24px !important; padding: 0 !important; justify-content: center !important;
  text-align: center !important; border-radius: 0 !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_project_actions_"] button:hover {
  background: transparent !important; color: #fff !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_project_actions_"] button [data-testid="stMarkdownContainer"] {
  display: none !important;
}
div[data-testid="stPopoverBody"]:has([class*="st-key-na_rename_"]),
div[data-testid="stPopoverBody"]:has([class*="st-key-na_delete_"]) {
  min-width: 156px !important; max-width: 156px !important;
  padding: .42rem !important; background: #343434 !important;
  border: none !important; border-radius: 8px !important;
  box-shadow: 0 12px 30px rgba(0,0,0,.38) !important;
}
div[data-testid="stPopoverBody"] [class*="st-key-na_rename_"] button,
div[data-testid="stPopoverBody"] [class*="st-key-na_delete_"] button {
  width: 100% !important; opacity: 1 !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_delete_"] button,
[class*="st-key-na_delete_"] button,
[class*="st-key-na_delete_confirm_"] button {
  color: var(--na-err) !important;
}
section[data-testid="stSidebar"] [class*="st-key-na_delete_"] button:hover,
[class*="st-key-na_delete_"] button:hover,
[class*="st-key-na_delete_confirm_"] button:hover {
  background: rgba(224, 96, 94, .14) !important; color: #ff8583 !important;
}
/* '更多项目' expander: flat, borderless, matches the list. */
section[data-testid="stSidebar"] .stExpander { border: none !important; background: transparent !important; }
section[data-testid="stSidebar"] .stExpander summary { padding: .34rem .55rem !important; color: var(--na-muted) !important; font-size: .95rem !important; justify-content: flex-start !important; }
section[data-testid="stSidebar"] .stExpander summary span { text-align: left !important; }
section[data-testid="stSidebar"] .stExpander summary:hover { color: #fff !important; }
section[data-testid="stSidebar"] .stExpander [data-testid="stExpanderDetails"] { padding: 0 !important; }

/* Workspace header (right side, top): product name + version only. */
.na-appbar { display: flex; align-items: baseline; gap: .6rem; margin: 0 0 .6rem; }
.na-appbar .name { font-size: 1.8rem; font-weight: 700; color: var(--na-text); letter-spacing: .01em; }
.na-appbar .ver { font-size: 1.2rem; color: var(--na-muted); }
</style>
"""

_CSS_INPUT = """
<style>
/* ---- ChatGPT-style composer: ONE rounded pill, single row ---- */
.st-key-na_composer {
  background: var(--na-panel-alt);
  border: 1px solid var(--na-border);
  border-radius: 26px;
  padding: .2rem .45rem .2rem .6rem;
  box-shadow: 0 2px 20px rgba(0,0,0,.35);
}
.st-key-na_composer:focus-within { border-color: #3a3d44; }
.st-key-na_composer [data-testid="stForm"] {
  border: none !important; padding: 0 !important;
}
.st-key-na_composer [data-testid="stHorizontalBlock"] { align-items: center; gap: .2rem; }

/* Single-line text input inside the box: transparent, borderless. */
.st-key-na_composer .stTextInput [data-baseweb="input"],
.st-key-na_composer .stTextInput [data-baseweb="base-input"] {
  background: transparent !important; border: none !important; box-shadow: none !important;
}
.st-key-na_composer .stTextInput input {
  background: transparent !important; color: var(--na-text);
  font-size: 1rem; box-shadow: none !important; outline: none !important;
}
.st-key-na_composer .stTextInput input::placeholder { color: var(--na-muted); }
.st-key-na_composer .stTextInput label { display: none; }
.st-key-na_composer [data-testid="InputInstructions"] { display: none; }
</style>
"""

_CSS_COMPOSER_CTRL = """
<style>
/* '+' upload: bare white glyph, no box (popover trigger). */
.st-key-na_up button {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--na-text) !important; font-size: 1.5rem !important; font-weight: 300 !important;
  min-height: 40px !important; height: 40px !important; width: 40px !important; padding: 0 !important;
}
.st-key-na_up button:hover { color: #fff !important; background: rgba(255,255,255,.06) !important; border-radius: 999px !important; }
/* Drop the popover's default dropdown chevron next to the '+'. */
.st-key-na_up button [data-testid="stIconMaterial"],
.st-key-na_up button svg { display: none !important; }

/* Mode selector: compact grey dropdown (like ChatGPT '极速 ˅'), NO blue. */
.st-key-na_mode [data-baseweb="select"] > div {
  background: transparent !important; border: none !important; box-shadow: none !important;
  color: var(--na-muted) !important; min-height: 34px !important;
}
.st-key-na_mode [data-baseweb="select"] div { color: var(--na-muted) !important; }
.st-key-na_mode label { display: none; }
.st-key-na_mode [data-testid="stWidgetLabel"] { display: none; }

/* Send: white circle, black arrow. */
.st-key-na_send button {
  border-radius: 999px !important; min-height: 40px !important; height: 40px !important;
  width: 40px !important; padding: 0 !important; font-size: 1.4rem !important;
  background: var(--na-text) !important; border: none !important; color: #111 !important;
}
.st-key-na_send button:hover { background: #fff !important; }
.st-key-na_send button:disabled { background: var(--na-border) !important; color: var(--na-muted) !important; }
</style>
"""

_CSS_PANELS = """
<style>
/* Fixed-height panes scroll on their own; page never grows unbounded. */
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
.na-eyebrow { color: var(--na-muted); font-size: .72rem; letter-spacing: .08em;
  text-transform: uppercase; font-weight: 600; margin-bottom: .35rem; }
.na-task-card { background: var(--na-panel); border: 1px solid var(--na-border);
  border-radius: 12px; padding: .8rem 1rem; margin-bottom: .6rem; }
.na-chip { display: inline-block; background: var(--na-panel-alt);
  border: 1px solid var(--na-border); color: var(--na-muted); border-radius: 999px;
  padding: 1px 10px; font-size: .74rem; margin: 2px 4px 2px 0; }
/* Top block: current status. */
.na-now { margin: .1rem 0 .9rem; }
.na-now .k { color: var(--na-muted); font-size: .72rem; letter-spacing: .05em; margin-bottom: .15rem; }
.na-now .v { color: var(--na-text); font-size: 1.15rem; font-weight: 600; line-height: 1.3; }

/* Section label between blocks. */
.na-eyebrow2 { color: var(--na-muted); font-size: .72rem; letter-spacing: .05em;
  margin: .2rem 0 .4rem; }

/* Progress steps. */
.na-step { display: flex; gap: .5rem; align-items: baseline; padding: 3px 0;
  font-size: .92rem; color: var(--na-text); }
.na-step .ic { width: 1rem; flex: none; text-align: center; font-size: .8rem; }
.na-step.pending { color: var(--na-muted); }
.na-step.pending .ic { color: var(--na-muted); }
.na-step.running { color: var(--na-text); font-weight: 600; }
.na-step.running .ic { color: var(--na-text); }
.na-step.done { color: var(--na-muted); }
.na-step.done .ic { color: var(--na-text); }

/* ReAct fields: 当前动作 / 最近决策. */
.na-field { margin: 0 0 .7rem; }
.na-field .k { color: var(--na-muted); font-size: .72rem; letter-spacing: .05em; margin-bottom: .15rem; }
.na-field .t { color: var(--na-text); font-size: .95rem; line-height: 1.4; }

/* Aux (Iteration) — small, muted, not a heading. */
.na-aux { color: var(--na-muted); font-size: .78rem; margin: .5rem 0 0; }

/* Bottom fixed stat row: 运行时间 / Token. */
.na-stats { display: flex; gap: 1.6rem; margin: .9rem 0 .1rem;
  padding-top: .7rem; border-top: 1px solid var(--na-border); }
.na-stats .k { color: var(--na-muted); font-size: .72rem; letter-spacing: .05em; }
.na-stats .v { color: var(--na-text); font-size: 1.05rem; font-weight: 600; }
</style>
"""


def inject() -> None:
    """Inject the full theme. Call once, first thing in the app.

    A CSS comment keyed on this file's mtime is injected into each
    ``<style>`` block so that Streamlit's content hash changes after
    every source edit — without the comment the delta protocol may skip
    re-sending the style blocks and the browser shows stale CSS.
    """
    _mtime = int(os.path.getmtime(__file__)) if __file__ else 0
    _tag = f"/* theme.mtime:{_mtime} */"
    for block in (_CSS, _CSS_INPUT, _CSS_COMPOSER_CTRL, _CSS_PANELS):
        st.markdown(block.replace("<style>", f"<style>{_tag}", 1), unsafe_allow_html=True)
