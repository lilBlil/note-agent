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
# single viewport alongside the app header, task card and bottom composer.
PANE_HEIGHT = 430
STATUS_HEIGHT = 430

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

/* Workspace header (right side, top): product name + version only. */
.na-appbar { display: flex; align-items: baseline; gap: .6rem; margin: 0 0 .6rem; }
.na-appbar .name { font-size: 1.15rem; font-weight: 700; color: var(--na-text); letter-spacing: .01em; }
.na-appbar .ver { font-size: .74rem; color: var(--na-muted); }
</style>
"""

_CSS_INPUT = """
<style>
/* ---- ChatGPT-style composer: one rounded dark box wrapping text + controls ---- */
.st-key-na_composer {
  background: var(--na-panel-alt);
  border: 1px solid var(--na-border);
  border-radius: 24px;
  padding: .5rem .6rem .4rem 1rem;
  box-shadow: 0 2px 20px rgba(0,0,0,.35);
}
.st-key-na_composer:focus-within { border-color: #3a3d44; }

/* Text area lives INSIDE the box: transparent, borderless, no double ring. */
.st-key-na_composer .stTextArea [data-baseweb="textarea"],
.st-key-na_composer .stTextArea [data-baseweb="base-input"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.st-key-na_composer .stTextArea [data-baseweb="textarea"]:focus-within {
  border: none !important; box-shadow: none !important;
}
.st-key-na_composer .stTextArea textarea {
  background: transparent !important;
  color: var(--na-text);
  font-size: .98rem;
  padding: .35rem .2rem;
  box-shadow: none !important;
  outline: none !important;
}
.st-key-na_composer .stTextArea textarea:focus,
.st-key-na_composer .stTextArea textarea:focus-visible {
  box-shadow: none !important; outline: none !important; border: none !important;
}
.st-key-na_composer .stTextArea textarea::placeholder { color: var(--na-muted); }
.st-key-na_composer .stTextArea label { display: none; }
/* Streamlit's "Press Enter" helper + the resize handle: hide for a clean box. */
.st-key-na_composer [data-testid="InputInstructions"] { display: none; }
.st-key-na_composer .stTextArea textarea { resize: none; }
</style>
"""

_CSS_COMPOSER_CTRL = """
<style>
/* Control row: mode selector (left) + upload (+) + send (arrow), right-aligned. */
.st-key-na_ctrlrow { align-items: center; }
.st-key-na_ctrlrow [data-testid="stHorizontalBlock"] { align-items: center; gap: .35rem; }

/* Segmented control -> compact pill sitting inside the box. */
.st-key-na_mode [data-baseweb="button-group"] { gap: 2px; }
.st-key-na_mode button {
  background: var(--na-panel) !important; border: 1px solid var(--na-border) !important;
  color: var(--na-muted) !important; border-radius: 999px !important;
  padding: 2px 12px !important; font-size: .8rem !important; min-height: 30px !important;
}
.st-key-na_mode button[aria-checked="true"], .st-key-na_mode button[kind="segmented_controlActive"] {
  background: var(--na-accent) !important; color: #fff !important; border-color: var(--na-accent) !important;
}
.st-key-na_mode label { display: none; }

/* Round icon buttons for upload / send. */
.st-key-na_up button, .st-key-na_send button {
  border-radius: 999px !important; min-height: 38px !important; height: 38px !important;
  width: 38px !important; padding: 0 !important; font-size: 1.1rem !important;
}
.st-key-na_up button { background: var(--na-panel) !important; border: 1px solid var(--na-border) !important; color: var(--na-text) !important; }
.st-key-na_send button { background: var(--na-text) !important; border: none !important; color: #111 !important; }
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
.na-step { display: flex; gap: .55rem; align-items: baseline; padding: 3px 0;
  font-size: .9rem; color: var(--na-text); }
.na-step .ic { width: 1.1rem; flex: none; text-align: center; }
.na-step.pending { color: var(--na-muted); }
.na-step.running { color: var(--na-run); }
.na-step.done .ic { color: var(--na-ok); }
.na-metric { color: var(--na-muted); font-size: .76rem; }
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
    st.markdown(_CSS_COMPOSER_CTRL, unsafe_allow_html=True)
    st.markdown(_CSS_PANELS, unsafe_allow_html=True)
