"""Track Signal user interface: the Signal Hub entry point.

The only package under ``tracksignal`` that imports Streamlit. ``render()`` draws the whole app on the current
page and never calls ``st.set_page_config``; the standalone ``app.py`` or Signal Hub owns the page config.
"""

from tracksignal import __version__
from tracksignal.ui import signal_theme
from tracksignal.ui.app import render

APP_INFO = {"product": "Track Signal", "version": __version__, "repo": "brand-tracking", "slug": "track"}

__all__ = ["APP_INFO", "render", "signal_theme"]
