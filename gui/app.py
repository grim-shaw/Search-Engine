"""Talash desktop search window.

`TalashApp` owns the window and switches between two views:

  * the "hero" view: a centered logo + search box, shown before any search
    (and again if the user clears their query) -- no results, no scrollbar.
  * the "results" view: a small logo + search box docked into a left-aligned
    header row (Google-style), with a full-width, page-level scrollable area
    below it for results / status messages.

Each view is rebuilt fresh into the window (destroying the previous one)
rather than kept alive and hidden, since the two layouts share little beyond
the search box, and tearing down a few dozen widgets is cheap.

Search and indexing both touch disk (and indexing can be slow), so both run
on a background thread; results are marshalled back to the main thread via
`window.after(...)` since tkinter widgets may only be touched from there.
"""

from __future__ import annotations

import json
import os
import re
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from typing import Optional

import ttkbootstrap as tb
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer
from ttkbootstrap.constants import BOTH, LEFT, X, Y

from gui import theme
from gui.components import EmptyState, PlaceholderEntry, ScrollableFrame, build_result_cards, open_in_browser
from indexer import generate_forward_index
from searcher import search_words
from sorter import inverted_index_generator

STOP_WORDS = set(stopwords.words("english"))
STEMMER = SnowballStemmer(language="english")

DOCUMENT_INDEX_PATH = "document_index.txt"
LOGO_PATH = "./assets/talash_png_2.png"
LOGO_SMALL_SUBSAMPLE = 2

IDLE_SUBTITLE = "Search your indexed documents"
SEARCH_PLACEHOLDER = "Enter your search query and press Enter"


def _stem_query(raw_query: str) -> list[str]:
    """Lowercases, strips punctuation, drops stop words and stems what's left."""

    words = re.sub("[^a-zA-Z]", " ", raw_query).lower().split()
    return [STEMMER.stem(word) for word in words if word not in STOP_WORDS]


class TalashApp:
    def __init__(self) -> None:
        self.window = tb.Window(title="Talash", themename=theme.THEME_NAME)
        self.window.geometry(theme.WINDOW_SIZE)
        self.window.minsize(*theme.WINDOW_MIN_SIZE)
        # Force the requested geometry to actually take effect before any
        # `place(relx=...)` call below: otherwise the first such call (the
        # Index Data button) computes against the window's tiny pre-realized
        # size instead of its real one, landing the button off-screen.
        self.window.update_idletasks()

        style = tb.Style()
        colors = style.colors
        self._normal_text_color = colors.get("inputfg")
        self._muted_text_color = colors.get("secondary")
        # Give the search box some horizontal breathing room around the text;
        # ttk's default entry padding (5px) reads as cramped at our search
        # font size. Vertical padding is kept small on purpose: this app's
        # ttkbootstrap window applies extra Tk display scaling (DPI-driven),
        # which inflates the font's rendered pixel height well beyond its
        # nominal point size, so generous vertical padding here clips text
        # against the entry's fixed row height (see SEARCH_ROW_HEIGHT).
        style.configure(f"{theme.ACCENT}.TEntry", padding=(theme.PAD_SM, 2))

        self._logo_image = self._load_logo()
        self._logo_image_small = self._load_logo(subsample=LOGO_SMALL_SUBSAMPLE)

        self._busy = False
        self._showing_results_view = False
        self._current_cards: list = []

        self.search_box: Optional[PlaceholderEntry] = None
        self.search_button: Optional[tb.Button] = None
        self.index_button: Optional[tb.Button] = None
        self.status_label: Optional[tb.Label] = None
        self.results: Optional[ScrollableFrame] = None

        # Search shows its busy state as a spinner inside the search button
        # itself rather than a separate loading bar.
        self._spinner_after_id: Optional[str] = None
        self._spinner_index = 0

        # Index Data's message + progress bar live on the hero screen (see
        # `_build_index_status`) rather than the results view: indexing never
        # navigates to results, only an actual search does.
        self.index_title_label: Optional[tb.Label] = None
        self.index_subtitle_label: Optional[tb.Label] = None
        self.index_progress: Optional[tb.Progressbar] = None

        self.window.bind("<Return>", self.on_search)
        self.window.bind("<Configure>", lambda _event: self._sync_card_wraplength())

        self.show_hero_view()

    # -- logo -----------------------------------------------------------------------

    def _load_logo(self, subsample: Optional[int] = None) -> Optional[tk.PhotoImage]:
        try:
            image = tk.PhotoImage(file=LOGO_PATH)
        except tk.TclError:
            return None
        return image.subsample(subsample, subsample) if subsample else image

    def _build_logo_label(self, parent: tb.Frame, small: bool) -> tb.Label:
        image = self._logo_image_small if small else self._logo_image
        if image is not None:
            label = tb.Label(parent, image=image)
        else:
            font = theme.FONT_LOGO_FALLBACK_SMALL if small else theme.FONT_LOGO_FALLBACK
            label = tb.Label(parent, text="Talash", font=font, bootstyle=theme.ACCENT)

        if small:
            # In the compact header, the logo doubles as a "go home" control,
            # same as clicking a site's logo on any real search results page.
            label.configure(cursor="hand2")
            label.bind("<Button-1>", lambda _event: self.show_hero_view())

        return label

    # -- shared building blocks -------------------------------------------------------

    def _index_exists(self) -> bool:
        return os.path.isfile(DOCUMENT_INDEX_PATH)

    def _build_index_button(self) -> None:
        """Only offered before a first index exists; once indexed, the
        control is removed entirely rather than just disabled."""

        if self._index_exists():
            self.index_button = None
            return
        self.index_button = tb.Button(
            self.window,
            text="⚙ Index Data",
            bootstyle=f"{theme.MUTED}-outline",
            command=self.on_index_data,
            cursor="hand2",
        )
        self.index_button.place(relx=1.0, x=-theme.PAGE_MARGIN, y=theme.PAGE_MARGIN, anchor="ne")

    def _build_search_row(self, parent: tb.Frame) -> tb.Frame:
        """A fixed-size row holding the search entry + search button, so both
        always end up exactly the same height (and the row is identically
        sized whether it's centered on the hero screen or docked into the
        compact header) regardless of ttk theme padding quirks."""

        row = tb.Frame(parent, width=theme.SEARCH_ROW_WIDTH, height=theme.SEARCH_ROW_HEIGHT)
        row.pack_propagate(False)

        entry = tb.Entry(row, font=theme.FONT_SEARCH, bootstyle=theme.ACCENT)
        entry.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, theme.HEADER_ITEM_GAP))
        entry.bind("<Escape>", lambda _event: self.show_hero_view())
        self.search_box = PlaceholderEntry(entry, SEARCH_PLACEHOLDER, self._normal_text_color, self._muted_text_color)

        self.search_button = tb.Button(
            row, text="Search", width=8, bootstyle=theme.ACCENT, command=self.on_search, cursor="hand2"
        )
        self.search_button.pack(side=LEFT, fill=Y)

        return row

    def _build_status_row(self, parent: tb.Frame) -> tb.Frame:
        status_row = tb.Frame(parent)
        self.status_label = tb.Label(status_row, text="", font=theme.FONT_STATUS, bootstyle=theme.MUTED)
        self.status_label.pack(side=LEFT)
        return status_row

    def _set_button_spinner(self, spinning: bool) -> None:
        """Search has no separate loading bar; its button label spins instead."""

        self._cancel_button_spinner()
        if spinning:
            self._spinner_index = 0
            self._advance_spinner()
        else:
            self.search_button.configure(text="Search")

    def _advance_spinner(self) -> None:
        frame = theme.SPINNER_FRAMES[self._spinner_index % len(theme.SPINNER_FRAMES)]
        self.search_button.configure(text=frame)
        self._spinner_index += 1
        self._spinner_after_id = self.window.after(theme.SPINNER_INTERVAL_MS, self._advance_spinner)

    def _cancel_button_spinner(self) -> None:
        if self._spinner_after_id is not None:
            self.window.after_cancel(self._spinner_after_id)
            self._spinner_after_id = None

    def _build_index_status(self, parent: tb.Frame) -> None:
        """Index Data's message + progress bar, stacked below the search row
        on the hero screen. Both stay unpacked (zero height) until there's
        actually something to show."""

        container = tb.Frame(parent)
        container.pack(pady=(theme.INDEX_STATUS_TOP_MARGIN, 0))

        self.index_title_label = tb.Label(container, text="", font=theme.FONT_EMPTY_TITLE, justify="center")
        self.index_subtitle_label = tb.Label(
            container,
            text="",
            font=theme.FONT_BODY,
            bootstyle=theme.MUTED,
            justify="center",
            wraplength=theme.SEARCH_ROW_WIDTH,
        )
        self.index_progress = tb.Progressbar(
            container, mode="indeterminate", bootstyle=f"{theme.ACCENT}-striped", length=240
        )

    def _set_index_message(self, title: str, subtitle: str = "", tone: str = theme.MUTED) -> None:
        self.index_title_label.configure(text=title, bootstyle=tone)
        self.index_title_label.pack()
        if subtitle:
            self.index_subtitle_label.configure(text=subtitle)
            self.index_subtitle_label.pack(pady=(theme.PAD_XS, 0))
        else:
            self.index_subtitle_label.pack_forget()

    def _clear_window(self) -> None:
        # A spinner `after` callback referencing a search_button that's about
        # to be destroyed would error on its next tick otherwise.
        self._cancel_button_spinner()
        for child in self.window.winfo_children():
            child.destroy()

    # -- hero view: centered logo + search box, no results -------------------------------

    def show_hero_view(self) -> None:
        self._showing_results_view = False
        self._current_cards = []
        self._clear_window()
        self.results = None

        self._build_index_button()

        hero = tb.Frame(self.window)
        hero.place(relx=0.5, rely=0.5, anchor="center")

        self._build_logo_label(hero, small=False).pack()
        tb.Label(hero, text=IDLE_SUBTITLE, font=theme.FONT_SUBTITLE, bootstyle=theme.MUTED).pack(
            pady=(theme.PAD_SM, theme.PAD_MD)
        )
        self._build_search_row(hero).pack()
        self._build_index_status(hero)
        # Deliberately not auto-focusing the entry: focusing it immediately
        # fires <FocusIn>, which clears the placeholder before it's ever seen.

    # -- results view: compact left-aligned header + page-level scrollable results -----------

    def show_results_view(self) -> None:
        self._showing_results_view = True
        self._clear_window()

        self._build_index_button()

        header = tb.Frame(self.window)
        header.pack(fill=X, padx=theme.PAGE_MARGIN, pady=(theme.PAGE_MARGIN, theme.PAD_XS))

        self._build_logo_label(header, small=True).pack(side=LEFT, padx=(0, theme.HEADER_ITEM_GAP))
        self._build_search_row(header).pack(side=LEFT)

        self._build_status_row(self.window).pack(fill=X, padx=theme.PAGE_MARGIN, pady=(0, theme.PAD_SM))

        results_container = tb.Frame(self.window)
        results_container.pack(fill=BOTH, expand=True)
        self.results = ScrollableFrame(results_container)
        self.results.pack(fill=BOTH, expand=True)

    def _ensure_results_view(self) -> None:
        if not self._showing_results_view:
            self.show_results_view()

    # -- state helpers ------------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.search_box.entry.configure(state=state)
        self.search_button.configure(state=state)
        if self.index_button is not None:
            self.index_button.configure(state=state)

        # Search shows a spinner in its own button; Index Data still uses an
        # inline progress bar centered below the hero search box. Only one of
        # the two views is ever on screen at a time.
        if self._showing_results_view:
            self._set_button_spinner(busy)
            return

        if busy:
            self.index_progress.pack(pady=(theme.PAD_SM, 0))
            self.index_progress.start(12)
        else:
            self.index_progress.stop()
            self.index_progress.pack_forget()

    def show_message(self, title: str, subtitle: str = "", tone: str = theme.MUTED) -> None:
        self.results.clear()
        self._current_cards = []
        EmptyState(self.results.body, title, subtitle, tone=tone).pack(fill=BOTH, expand=True)

    def _sync_card_wraplength(self) -> None:
        """Keeps result URLs wrapped to the window's current width.

        Driven by the window's own size rather than each label reacting to its
        own <Configure> event, which would create a feedback loop (a label's
        unwrapped width influences the size that's supposed to constrain it).
        """

        if not self._current_cards:
            return
        available = self.window.winfo_width() - theme.PAGE_MARGIN - theme.RESULT_RIGHT_GUTTER
        for card in self._current_cards:
            card.set_wraplength(available)

    # -- search ---------------------------------------------------------------------

    def on_search(self, _event: tk.Event | None = None) -> None:
        if self._busy or self.search_box is None:
            return

        query = self.search_box.get()
        if not query:
            if self._showing_results_view:
                self.show_hero_view()
            return

        self._ensure_results_view()
        self.search_box.set(query)

        self._set_busy(True)
        self._set_status(f"Searching for “{query}”…")
        threading.Thread(target=self._run_search, args=(query,), daemon=True).start()

    def _run_search(self, query: str) -> None:
        start = datetime.now()
        ranked_documents, document_index, error = [], {}, None

        try:
            stemmed_words = _stem_query(query)
            with open(DOCUMENT_INDEX_PATH) as doc_index_file:
                document_index = json.load(doc_index_file)
            ranked_documents = search_words(stemmed_words)
        except FileNotFoundError:
            error = "missing_index"
        except Exception:
            error = "unknown"

        elapsed = (datetime.now() - start).total_seconds()
        self.window.after(0, self._handle_search_result, query, ranked_documents, document_index, elapsed, error)

    def _handle_search_result(
        self, query: str, ranked_documents: list, document_index: dict, elapsed: float, error: str | None
    ) -> None:
        self._set_busy(False)

        if error == "missing_index":
            self.show_message(
                "No index found yet",
                "Click “Index Data” and choose a folder of JSON articles to build one first.",
            )
            self._set_status("")
            return
        if error:
            self.show_message(
                "Something went wrong",
                "The search couldn't be completed. Check the console for details.",
                tone="danger",
            )
            self._set_status("")
            return

        if not ranked_documents:
            self.show_message("No results found", f"Nothing matched “{query}”. Try different or fewer keywords.")
            self._set_status(f"0 results · {elapsed:.3f}s")
            return

        urls = [document_index[doc_id] for doc_id, _ in ranked_documents]
        self.results.clear()
        self._current_cards = build_result_cards(self.results.body, urls, on_open=open_in_browser)
        self._sync_card_wraplength()
        self._set_status(f"{len(urls)} result{'s' if len(urls) != 1 else ''} · {elapsed:.3f}s")

    # -- indexing ---------------------------------------------------------------------

    def on_index_data(self) -> None:
        if self._busy:
            return

        folder = filedialog.askdirectory(title="Select a folder of JSON articles to index")
        if not folder:
            return

        # Indexing always plays out on the hero screen; only an actual
        # search navigates to the results view.
        if self._showing_results_view:
            self.show_hero_view()

        self._set_busy(True)
        self._set_index_message("Indexing articles…", f"Building a search index from {folder}.")
        threading.Thread(target=self._run_indexing, args=(folder,), daemon=True).start()

    def _run_indexing(self, folder: str) -> None:
        index_info, error = None, None
        try:
            index_info = generate_forward_index(folder)
            if index_info[0]:
                index_info.append(inverted_index_generator())
        except Exception:
            error = "unknown"

        self.window.after(0, self._handle_index_result, folder, index_info, error)

    def _handle_index_result(self, folder: str, index_info: Optional[list], error: Optional[str]) -> None:
        self._set_busy(False)
        self._refresh_index_button()

        if error or index_info is None:
            self._set_index_message(
                "Indexing failed",
                f"Could not build an index from {folder}. Check the console for details.",
                tone="danger",
            )
            return

        added_new_documents = index_info[0]
        if added_new_documents:
            summary = (
                f"Indexed {index_info[1]} new document(s).\n"
                f"Forward index: {index_info[2]} · Inverted index: {index_info[3]}"
            )
            self._set_index_message("Indexing complete", summary, tone=theme.ACCENT)
        else:
            self._set_index_message("Nothing to index", "No JSON articles were found, or they were already indexed.")

    def _refresh_index_button(self) -> None:
        """Drops the Index Data button the moment an index exists, even
        without a full view rebuild (e.g. right after indexing finishes)."""

        if self.index_button is not None and self._index_exists():
            self.index_button.destroy()
            self.index_button = None

    # -- lifecycle ---------------------------------------------------------------------

    def run(self) -> None:
        self.window.mainloop()


def create_search_window() -> None:
    """Entry point used by main.py."""

    TalashApp().run()
