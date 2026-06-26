<p align="center">
  <img src="assets/talash_png_2.png" alt="Talaash logo" width="220">
</p>

<h1 align="center">Talaash</h1>

<p align="center">
  A search engine built from scratch in Python, modeled on the original Google research paper.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Status" src="https://img.shields.io/badge/status-educational-orange">
</p>

---

## Table of Contents

- [About](#about)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Development](#development)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## About

Talaash is a search engine in Python. It uses JSON files as a corpus of data. It is created after studying the [Google research paper](http://infolab.stanford.edu/~backrub/google.html) and works in a similar manner. During the indexing stage, it builds a forward index, a lexicon, and a document index, then converts the forward index into an inverted index for fast searching. During searching, it also takes the relevance of each document into account: an IR score is calculated, which factors in where matches occur (title vs. content) and how close together multiple search words appear (proximity).

A deeper, mechanics-level explanation of indexing and ranking lives in [details.md](details.md).

## Features

- **Forward & inverted indexing** — classic two-phase index construction, partitioned into barrels so no single file or in-memory structure grows unbounded.
- **Text normalization** — stopword removal and stemming (Snowball stemmer) applied identically at index time and query time.
- **Relevance ranking (IR score)** — title hits are weighted more heavily than content hits, and an additional proximity bonus rewards documents where multi-word queries appear close together.
- **Incremental, idempotent indexing** — re-running the indexer over the same or overlapping data skips documents that are already indexed instead of duplicating them.
- **Desktop GUI** — a Tkinter interface for picking a dataset folder to index and for running searches, with clickable result links and timing feedback.

## Architecture

**Indexing pipeline** — run once per dataset (or incrementally, as new data shows up):

```
      ┌──────────────┐     ┌───────────────┐     ┌───────────────────┐
JSON  │ indexer      │ ──> │ Forward Index │ ──> │ sorter            │
      │ (normalize,  │     │  (Forward     │     │ (builds inverted  │
      │  stem, hash) │     │   Barrels)    │     │  index + lexicon) │
      └──────────────┘     └───────────────┘     └───────────────────┘
```

**Search pipeline** — run on every query, using the index built above:

```
      ┌────────────────┐     ┌────────────────┐
Query │ searcher       │ ──> │ gui (app.py)   │
      │ (lookup, rank, │     │ ranked results │
      │  proximity)    │     └────────────────┘
      └────────────────┘
```

See [details.md](details.md) for the full walkthrough of how each stage works.

## Tech Stack

| Category | Choice                                                      |
| -------- | ----------------------------------------------------------- |
| Language | Python 3                                                    |
| GUI      | Tkinter                                                     |
| NLP      | [NLTK](https://www.nltk.org/) (stopwords, Snowball stemmer) |
| Storage  | Flat JSON / text files (barrels, lexicon, document index)   |

## Project Structure

```
Search-Engine/
├── assets/                    # Static assets (logo, etc.)
├── data/                      # Sample JSON corpus
├── gui/
│   ├── app.py                 # Tkinter UI: search box, index button, results pane
│   └── tkHyperLinkManager.py
├── indexer.py                 # Builds the forward index from raw JSON articles
├── sorter.py                  # Converts the forward index into the inverted index
├── searcher.py                # Looks up query words and ranks matching documents
├── main.py                    # Entry point — launches the GUI
├── details.md                 # In-depth design and ranking explanation
├── pyproject.toml             # Ruff lint/import-sort/format configuration
├── .pre-commit-config.yaml    # Pre-commit hook wiring for Ruff
└── requirements.txt
```

`ForwardBarrels/`, `InvertedBarrels/`, `lexicon`, and `document_index.txt` are generated at indexing time and are not checked into the repo.

## Getting Started

### Prerequisites

- Python 3.10 or later
- `pip`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Grimmer107/Search-Engine.git
   cd Search-Engine
   ```
2. Create a virtual environment in the project root:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - Windows (PowerShell):

     ```powershell
     .\venv\Scripts\Activate.ps1
     ```

   - Windows (cmd):

     ```cmd
     venv\Scripts\activate.bat
     ```

   - macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

4. Install the required packages from `requirements.txt`:

   ```bash
   pip install -r requirements.txt
   ```

5. Create the `ForwardBarrels` and `InvertedBarrels` directories in the project root (if they don't already exist).

> When you're done, run `deactivate` to exit the virtual environment.

## Usage

1. Run the application:

   ```bash
   python main.py
   ```

2. In the app window, click **Index Data** and select the folder containing your JSON dataset (e.g. the `data` folder) to build the forward and inverted indices.
3. Once indexing finishes, type a search query in the search bar and press **Search** (or hit Enter) to see ranked results as clickable links, along with the time the search took.

> **Note:** The project folder must contain the directories named `ForwardBarrels` and `InvertedBarrels`. A portion of the dataset is given in the `data` folder, which contains files in JSON format. Each JSON article is expected to have an `id`, a `url`, a `title`, and a `content` field.

## Development

Linting, import sorting, and code formatting are all handled by [Ruff](https://docs.astral.sh/ruff/) (`ruff check` for lint/imports, `ruff format` as a Black-compatible formatter), enforced automatically on every commit via [pre-commit](https://pre-commit.com/). Both are already included in `requirements.txt`.

1. Install the git hook (one-time setup per clone):

   ```bash
   pre-commit install
   ```

2. From then on, `git commit` automatically runs Ruff's lint and format checks against staged files and blocks the commit if it finds unfixable issues. You can also run it manually at any time:

   ```bash
   ruff check .
   ruff format .
   pre-commit run --all-files
   ```

## Known Limitations

- The number of forward barrels and the per-barrel word capacity are fixed constants, which caps the total vocabulary size without code changes.
- Document identity relies on a CRC32 hash of the original article id — compact, but with a theoretical (very unlikely) risk of collisions.
- Per-word search results are capped at the first 30 matching documents found in the inverted barrel, which keeps searches fast but means very common words won't surface every possible match.
- Proximity scoring compares position lists index-by-index rather than finding each occurrence's true nearest neighbor, so it's an approximation rather than an exact nearest-position calculation.

See [details.md](details.md#known-limitations) for more context.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow (fork, branch, commit, PR) and our [Code of Conduct](CODE_OF_CONDUCT.md) before opening a pull request or issue.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

- Inspired by Sergey Brin and Lawrence Page's paper, ["The Anatomy of a Large-Scale Hypertextual Web Search Engine"](http://infolab.stanford.edu/~backrub/google.html).
- Built with [NLTK](https://www.nltk.org/) for text normalization.
