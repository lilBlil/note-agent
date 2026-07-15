"""Dark, low-saturation theme + layout CSS. ChatGPT / Notion / Linear feel."""

from __future__ import annotations

import streamlit as st

# Neutral greys + a single restrained accent. Status colours used ONLY for
# success / running / error, never as decoration.
COLORS = {
    "bg": "#111214",
    "panel": "#191a1d",
    "panel_alt": "#1e2024",
    "border": "#2a2c31",
    "text": "#e6e7ea",
    "muted": "#8b8e96",
    "accent": "#6b8afd",
    "success": "#3fb779",
    "running": "#e0a44b",
    "error": "#e0605e",
}

# Height (px) of the two independently-scrolling main panes. Tuned to fit a
# single ~900px viewport alongside the task header and pinned input.
PANE_HEIGHT = 500
STATUS_HEIGHT = 500

_CSS = """
<style>
:root {
  --na-bg: #111214; --na-panel: #191a1d; --na-panel-alt: #1e2024;
  --na-border: #2a2c31; --na-text: #e6e7ea; --na-muted: #8b8e96;
  --na-accent: #6b8afd; --na-ok: #3fb779; --na-run: #e0a44b; --na-err: #e0605e;
}
.stApp { background: var(--na-bg); color: var(--na-text); }

/* Tighten the top padding so the workspace fits one screen. */
.block-container { padding-top: 2.2rem; padding-bottom: 6.5rem; max-width: 1500px; }

/* Sidebar: quiet panel. */
section[data-testid="stSidebar"] { background: var(--na-panel); border-right: 1px solid var(--na-border); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
</style>
"""

_CSS_INPUT = """
<style>
/* ChatGPT-style pinned input bar. */
div[data-testid="stBottomBlockContainer"], div[data-testid="stBottom"] > div {
  background: var(--na-bg);
}
div[data-testid="stChatInput"] {
  background: var(--na-panel-alt);
  border: 1px solid var(--na-border);
  border-radius: 22px;
  padding: 4px 6px;
  box-shadow: 0 2px 18px rgba(0,0,0,.35);
}
div[data-testid="stChatInput"] textarea { color: var(--na-text); font-size: 0.96rem; }
div[data-testid="stChatInput"] textarea::placeholder { color: var(--na-muted); }
div[data-testid="stChatInput"]:focus-within { border-color: var(--na-accent); }
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
.na-step { display: flex; gap: .55rem; align-items: baseline; padding: 3px 0;
  font-size: .9rem; color: var(--na-text); }
.na-step .ic { width: 1.1rem; flex: none; text-align: center; }
.na-step.pending { color: var(--na-muted); }
.na-step.running { color: var(--na-run); }
.na-step.done .ic { color: var(--na-ok); }
.na-react-block { border-left: 2px solid var(--na-border); padding: .1rem 0 .1rem .7rem;
  margin: .2rem 0 .7rem; }
.na-react-tag { color: var(--na-muted); font-size: .72rem; font-weight: 700;
  letter-spacing: .06em; text-transform: uppercase; }
</style>
"""


def inject() -> None:
    """Inject the full theme. Call once, first thing in the app."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_CSS_INPUT, unsafe_allow_html=True)
    st.markdown(_CSS_PANELS, unsafe_allow_html=True)
