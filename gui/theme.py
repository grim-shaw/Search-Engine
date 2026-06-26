"""Visual constants shared across the Talash GUI.

Centralizing fonts, spacing and the ttkbootstrap theme/accent here means a
future screen (settings, history, pagination, ...) can stay visually
consistent by importing from this module instead of hardcoding values.
"""

from __future__ import annotations

# ttkbootstrap theme: "darkly" already ships a teal/green "success" accent
# that's close to the original Talash brand color, so the rest of the app
# leans on bootstyle="success" wherever an accent is needed.
THEME_NAME = "darkly"
ACCENT = "success"
MUTED = "secondary"

WINDOW_SIZE = "1000x720"
WINDOW_MIN_SIZE = (760, 560)

PAD_XS = 4
PAD_SM = 8
PAD_MD = 16
PAD_LG = 32

# Left/top margin shared by the header row, the results list and the Index
# Data button, so nothing sits flush against the window's edge.
PAGE_MARGIN = 48

# Gap between the logo / search box / search button once they're docked in
# the compact top header (post-search), per the 12px spacing the UI calls for.
HEADER_ITEM_GAP = 12

# Fixed size (px) for the search box + search button row, so the box and
# button always match height exactly regardless of ttk theme padding quirks,
# and so the row is the same size whether it's centered (hero view) or
# docked into the compact header (results view).
SEARCH_ROW_HEIGHT = 42
SEARCH_ROW_WIDTH = 680

# Space reserved to the right of result text for the page scrollbar.
RESULT_RIGHT_GUTTER = 40

# Minimum gap between the search row and the Index Data status message/
# progress bar shown below it on the hero screen.
INDEX_STATUS_TOP_MARGIN = 60

# Search has no separate loading bar: the button's own label cycles through
# these frames (a spinning quarter-circle) while a search is in flight.
SPINNER_FRAMES = ("◐", "◓", "◑", "◒")
SPINNER_INTERVAL_MS = 130

# Tk silently substitutes a platform default if this family isn't installed,
# so no runtime detection is needed (and tkinter.font.families() requires a
# root window to already exist, which isn't true at import time).
FONT_FAMILY = "Segoe UI"

FONT_LOGO_FALLBACK = (FONT_FAMILY, 26, "bold")
FONT_LOGO_FALLBACK_SMALL = (FONT_FAMILY, 16, "bold")
FONT_SEARCH = (FONT_FAMILY, 11)
FONT_SUBTITLE = (FONT_FAMILY, 12)
FONT_LINK = (FONT_FAMILY, 13)
FONT_LINK_HOVER = (FONT_FAMILY, 13, "underline")
FONT_BODY = (FONT_FAMILY, 11)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_STATUS = (FONT_FAMILY, 9)
FONT_EMPTY_TITLE = (FONT_FAMILY, 13, "bold")
