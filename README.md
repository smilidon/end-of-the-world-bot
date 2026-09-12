# End of the World Bot

A Linux-first, local reference assistant for an offline document library, with
source citations and optional OsmAnd routing and printable directions.

This is a cleaned snapshot of an existing working offline project, not a new
hosted service. It preserves the project's bounded lexical retrieval, PDF page
references, archive ranking, street-resolution fallback, route geometry,
native-basemap bridge and PDF formatter. No documents, maps, models, binaries,
personal history or cloud monitoring are bundled.

**Verified here:** synthetic offline retrieval, PDF citations, protected paths,
street fallback/parser, geometry checks and PDF printing; see [verification](docs/VERIFICATION.md).
**Not verified here:** fresh Ollama inference, ZIM extraction, real-map routing,
native rendering, Windows/macOS, or authenticated Open WebUI use. Chat integration
requires separate setup. The original Pipe and a minimal compatible HTTP adapter
are now included and tested through localhost with synthetic references and fake
Ollama. This is a **source alpha, not the complete original chat appliance**.
Illustrated `Guide:` exports and legacy `Map:` dispatch remain omitted; see
[chat setup and exact API limits](docs/CHAT.md).


## Chat interface

See [Open WebUI Pipe setup](docs/CHAT.md). The CLI below is also available for
indexing and direct diagnostics; it is not a replacement for the chat interface.

## Quickstart: no model needed

Python 3.11+ with SQLite FTS5. The core uses the standard library.
PDF ingestion additionally needs Poppler's `pdftotext` on PATH.
Use a dedicated library directory containing only documents you intend to search.

```sh
mkdir -p library/guides
printf '%s\n' 'SYNTHETIC: The amber beacon batteries belong in the blue cabinet. This is a software fixture.' > library/guides/example.txt
python3 bot.py --root library index
python3 bot.py --root library search 'Where are the beacon batteries?'
python3 bot.py --root library search 'Read: guides/example.txt'
```

Results contain verbatim excerpts with application-generated IDs and file/page
locations. They are retrieval results, not generated answers. Indexing refuses to
overwrite an existing index. The bounded scan can miss material; no match does
not prove absence. Indexing caps each file at 5 MB extracted text and chunks at
3,600 characters; search has smaller read/time bounds.

For your own PDF, put it under `library/guides/`, explicitly rebuild the index
as described in [recovery](docs/RECOVERY.md), and query its contents. Citation links
are optional and require a separate explicit file allowlist:

```sh
printf '%s\n' '["guides/your-document.pdf"]' > documents.json
python3 bot.py --root library serve --allowlist documents.json
```

Open `http://127.0.0.1:8769/documents/guides/your-document.pdf#page=1`.
The server binds only to loopback; it is not a general filesystem browser.
CLI JSON reports source locations, not an integrated chat UI.

## Optional local AI

Install [Ollama](https://ollama.com/) and download a model while online, checking
its own license and disk requirements. Model downloads are **not** part of offline
runtime. Start Ollama locally using its official instructions, then:

```sh
python3 bot.py --root library ask 'Where are the beacon batteries?' --model YOUR_INSTALLED_MODEL
```

The model name is required; no model is silently downloaded. CPU mode is the
default (`--num-gpu 0`); `--threads` and `--num-gpu` are configurable.
The optional query retains the original 4,096-token context and short 64-token
answer budget. It sends evidence only to numeric loopback, disables proxies and
redirects, and supplies source IDs separately. Generated text may still be wrong.

## Optional maps and printable directions

See [routing prerequisites and limits](docs/ROUTING.md). Source is included,
but the existing OsmAnd Java/native setup is not a portable one-command install.
The renderer explicitly labels a geometry-only fallback when native context fails.
No town center is silently substituted for an unresolved street.

## Tests

Install test/export dependencies using your normal isolated Python environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Poppler must already supply `pdftotext`. Tests create synthetic data in temporary
directories; they do not need the real library, maps, model or adapter.
A minimal standard-library subset is `python3 -m unittest discover -s tests -p test_core.py -k Core -v`.
Dependency installation needs network unless wheels/packages were cached first.

## Planning and reuse

- [Hardware estimates versus observed baseline](docs/HARDWARE.md)
- [Architecture, offline boundary and existing projects](docs/ARCHITECTURE.md)
- [Security](SECURITY.md), [recovery](docs/RECOVERY.md), [known limits](docs/LIMITS.md)
- [License audit](docs/LICENSE_AUDIT.md), [attribution](NOTICE.md),
  [source allowlist](SOURCE_MANIFEST.json)

GPL-3.0-only for this staged code. Independent dependencies and datasets keep their
own licenses; no bundled dataset rights are implied. This is a reference tool,
not medical advice or a guarantee of safe treatment, navigation or emergency readiness.
