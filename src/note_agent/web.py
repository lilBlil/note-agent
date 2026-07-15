"""Streamlit entry point for Note Agent.

The UI lives in the `note_agent.ui` package (presentation layer only). This
module stays as a thin, stable entry point so `note-agent-ui` and
`streamlit run app.py` keep working.
"""

from __future__ import annotations

from note_agent.ui.app import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
