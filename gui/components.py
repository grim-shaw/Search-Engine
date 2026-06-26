"""Reusable widgets for the Talash search window.

Kept separate from app.py so new UI pieces (e.g. a history panel or
paginated results) can reuse `ScrollableFrame` / `EmptyState` without
touching the window-wiring code.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from typing import Callable, Iterable, List, Optional

import ttkbootstrap as tb
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X, Y

from gui import theme

SCROLLBAR_WIDTH = 12
SCROLLBAR_MIN_THUMB_HEIGHT = 24


class FlatScrollbar(tb.Frame):
    """A minimal, fully self-drawn vertical scrollbar.

    ttk's themed Scrollbar fought us on both ends: the "round" bootstyle
    paints the thumb and trough in the same color (an invisible handle), and
    the plain bootstyle draws unstyled black arrow buttons at each end and
    makes the thumb easy to miss, which reads as a confusing jump-to-click
    bug when a click lands on the trough instead. Drawing the thumb
    ourselves means the visible shape is exactly the clickable/draggable one
    and there are no arrow buttons to leave unstyled.
    """

    def __init__(self, parent: tb.Frame, command: Callable[..., None]) -> None:
        super().__init__(parent, width=SCROLLBAR_WIDTH)
        self.pack_propagate(False)
        self._command = command
        self._first = 0.0
        self._last = 1.0
        self._drag_anchor: Optional[int] = None

        colors = tb.Style().colors
        self._canvas = tb.Canvas(self, width=SCROLLBAR_WIDTH, highlightthickness=0, borderwidth=0, background=colors.bg)
        self._canvas.pack(fill=BOTH, expand=True)
        self._thumb = self._canvas.create_rectangle(0, 0, SCROLLBAR_WIDTH, 0, fill=colors.get("selectbg"), width=0)

        self._canvas.bind("<Configure>", lambda _event: self._redraw())
        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

    def set(self, first: str, last: str) -> None:
        """Standard Tk scrollbar protocol: called by the canvas's yscrollcommand."""

        self._first, self._last = float(first), float(last)
        self._redraw()

    def _thumb_rect(self) -> tuple[float, float]:
        height = self._canvas.winfo_height()
        top, bottom = self._first * height, self._last * height
        if bottom - top < SCROLLBAR_MIN_THUMB_HEIGHT:
            center = (top + bottom) / 2
            half = SCROLLBAR_MIN_THUMB_HEIGHT / 2
            top, bottom = center - half, center + half
        return top, bottom

    def _redraw(self) -> None:
        top, bottom = self._thumb_rect()
        self._canvas.coords(self._thumb, 0, top, self._canvas.winfo_width(), bottom)

    def _on_press(self, event: tk.Event) -> None:
        top, bottom = self._thumb_rect()
        if top <= event.y <= bottom:
            self._drag_anchor = event.y - int(top)
        else:
            self._drag_anchor = None
            self._jump_to(event.y)

    def _on_drag(self, event: tk.Event) -> None:
        if self._drag_anchor is None:
            return
        height = self._canvas.winfo_height()
        thumb_height = self._thumb_rect()[1] - self._thumb_rect()[0]
        top = max(0, min(event.y - self._drag_anchor, height - thumb_height))
        self._command("moveto", top / height if height else 0)

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_anchor = None

    def _jump_to(self, y: int) -> None:
        height = self._canvas.winfo_height()
        self._command("moveto", max(0.0, min(y / height, 1.0)) if height else 0)


class ScrollableFrame(tb.Frame):
    """A vertically scrollable, edge-to-edge container.

    Add children to `.body` instead of `self`. The scrollbar is meant to sit
    flush against the window's own edge (a single page-level scrollbar)
    rather than being inset into a boxed sub-panel, so callers shouldn't wrap
    this in extra padding on the scrollbar side.
    """

    def __init__(self, parent: tb.Frame) -> None:
        super().__init__(parent)

        background = tb.Style().colors.bg
        self._canvas = tb.Canvas(self, highlightthickness=0, borderwidth=0, background=background)
        scrollbar = FlatScrollbar(self, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.body = tb.Frame(self._canvas)
        self._body_id = self._canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_resize)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Enter>", lambda _event: self._bind_mousewheel())
        self._canvas.bind("<Leave>", lambda _event: self._unbind_mousewheel())

    def _on_body_resize(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event) -> None:
        self._canvas.itemconfigure(self._body_id, width=event.width)

    def _bind_mousewheel(self) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self) -> None:
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event) -> None:
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def clear(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self._canvas.yview_moveto(0)


class ResultCard(tb.Frame):
    """A single search result: just the clickable URL, left-aligned.

    Wrapping the URL text is driven explicitly via `set_wraplength` (called by
    whoever owns the layout, e.g. on window resize) rather than the label's
    own <Configure> event — letting a label react to its own size creates a
    feedback loop in Tk (the unwrapped text's natural width drives the size
    that's supposed to constrain it), which made long URLs overflow the window.
    """

    def __init__(self, parent: tb.Frame, url: str, on_open: Callable[[str], None]) -> None:
        super().__init__(parent)

        self._link = tb.Label(self, text=url, font=theme.FONT_LINK, bootstyle=theme.ACCENT, anchor="w", justify="left")
        self._link.pack(fill=X)

        for widget in (self, self._link):
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _event, target=url: on_open(target))
            widget.bind("<Enter>", lambda _event: self._link.configure(font=theme.FONT_LINK_HOVER))
            widget.bind("<Leave>", lambda _event: self._link.configure(font=theme.FONT_LINK))

    def set_wraplength(self, pixels: int) -> None:
        self._link.configure(wraplength=max(pixels, 200))


def open_in_browser(url: str) -> None:
    webbrowser.open(url)


class EmptyState(tb.Frame):
    """Centered placeholder shown when there is nothing to display yet.

    Deliberately text-only, no icon glyph: emoji presentation depends on the
    fonts installed on the user's machine, and a missing/mismatched fallback
    glyph (e.g. a misaligned plain "i" instead of an info icon) reads as
    broken UI. A colored title is a simpler, font-independent way to signal
    tone (error / success / informational).
    """

    def __init__(self, parent: tb.Frame, title: str, subtitle: str | None = None, tone: str = theme.MUTED) -> None:
        super().__init__(parent)

        tb.Label(self, text=title, font=theme.FONT_EMPTY_TITLE, bootstyle=tone).pack(pady=(theme.PAD_LG, 0))
        if subtitle:
            tb.Label(
                self, text=subtitle, font=theme.FONT_BODY, bootstyle=theme.MUTED, wraplength=420, justify="center"
            ).pack(pady=(theme.PAD_XS, 0))


def build_result_cards(
    parent: tb.Frame, urls: Iterable[str], on_open: Callable[[str], None] = open_in_browser
) -> List[ResultCard]:
    """Renders one left-aligned ResultCard per URL, stacked with breathing room, inside `parent`."""

    cards = []
    for index, url in enumerate(urls):
        card = ResultCard(parent, url, on_open)
        top_pad = theme.PAD_SM if index == 0 else 0
        card.pack(fill=X, padx=(theme.PAGE_MARGIN, theme.PAD_MD), pady=(top_pad, theme.PAD_MD))
        cards.append(card)
    return cards


class PlaceholderEntry:
    """Wraps a ttk Entry with greyed-out placeholder text.

    The placeholder is literally inserted into the widget (Tk entries have no
    native placeholder support), so `get()` is the safe way to read the real
    value — it returns "" while the placeholder is showing instead of the
    placeholder text itself.
    """

    def __init__(self, entry: tb.Entry, placeholder: str, normal_color: str, muted_color: str) -> None:
        self.entry = entry
        self._placeholder = placeholder
        self._normal_color = normal_color
        self._muted_color = muted_color
        self._showing_placeholder = False

        entry.bind("<FocusIn>", self._on_focus_in)
        entry.bind("<FocusOut>", self._on_focus_out)
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, self._placeholder)
        self.entry.configure(foreground=self._muted_color)
        self._showing_placeholder = True

    def _on_focus_in(self, _event=None) -> None:
        if self._showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(foreground=self._normal_color)
            self._showing_placeholder = False

    def _on_focus_out(self, _event=None) -> None:
        if not self.entry.get().strip():
            self._show_placeholder()

    def get(self) -> str:
        return "" if self._showing_placeholder else self.entry.get().strip()

    def set(self, value: str) -> None:
        self.entry.delete(0, "end")
        if not value:
            self._show_placeholder()
            return
        self.entry.insert(0, value)
        self.entry.configure(foreground=self._normal_color)
        self._showing_placeholder = False
