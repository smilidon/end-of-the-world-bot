# End of the World Bot — Installation and Usage Guide

This guide ships with the project. It covers release
[v0.1.0-beta.1](https://github.com/smilidon/end-of-the-world-bot/releases/tag/v0.1.0-beta.1)
(2026-09-19) of [End of the World Bot](https://github.com/smilidon/end-of-the-world-bot): how to
download and verify it, index your own documents, add new files later without losing your existing
search, and optionally attach a small local AI model.

End of the World Bot is a Linux-first, offline document-search assistant that cites its sources. It
works with **no AI model at all** as a pure retrieval and citation search, or optionally with a local
model via Ollama for conversational answers grounded in your documents. Nothing is bundled. No
models, maps, or manuals ship with the release; you fetch those separately and explicitly.

This is an **alpha** release. Where the project's own documentation says something is verified, this
guide says so. Where it does not, this guide does not claim otherwise.

**Requirements:** Linux, Python 3.11 or newer with SQLite FTS5, and POSIX `sh`. PDF indexing needs
Poppler's `pdftotext` on PATH. Windows users run this inside WSL; see
[docs/WINDOWS_INSTALL.md](https://github.com/smilidon/end-of-the-world-bot/blob/main/docs/WINDOWS_INSTALL.md).
macOS is not supported by this release.

---

## 1. Download and verify

```sh
mkdir -p ~/eotwb && cd ~/eotwb
curl -L -o linux-python.zip \
  https://github.com/smilidon/end-of-the-world-bot/releases/download/v0.1.0-beta.1/end-of-the-world-bot-0.1.0-beta.1-linux-python.zip
curl -L -o SHA256SUMS \
  https://github.com/smilidon/end-of-the-world-bot/releases/download/v0.1.0-beta.1/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS
```

Confirm the ZIP reports `OK` before continuing. Do not extract an unverified archive.

```sh
python3 -m zipfile -e linux-python.zip .
cd end-of-the-world-bot-0.1.0-beta.1-linux-python   # folder name from the extracted ZIP
sh launch.sh doctor
```

`doctor` checks your Python version, SQLite FTS5 support, and whether `pdftotext` is available.
Fix anything it flags before moving on.

Full details: [START_HERE.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/START_HERE.md)

## 2. Install a local copy

This step is optional for plain indexing and search (section 3), but it is **required** for the
intake and reindex workflow in section 4: the installer creates the `data/intake/` and
`data/generations/` directories that `reindex` needs, and the extracted ZIP folder does not have
them.

```sh
sh install.sh --dest "$HOME/.local/share/end-of-world-bot/0.1.0-beta.1"
cd "$HOME/.local/share/end-of-world-bot/0.1.0-beta.1"
```

The installer refuses to overwrite an existing destination (even an empty one), so re-running it
against the same path fails rather than clobbering anything. For a fresh copy, choose a new folder.

## 3. Add documents and index them

No model is required for this step.

```sh
mkdir -p library/guides
# put your own .txt, .md, or .pdf files into library/guides/
sh launch.sh index
sh launch.sh search 'your question here'
```

If you want to see the output format before adding real documents, try a throwaway test file first:

```sh
printf '%s\n' 'SYNTHETIC: The amber beacon batteries belong in the blue cabinet.' > library/guides/example.txt
sh launch.sh index
sh launch.sh search 'Where are the beacon batteries?'
```

The result is a set of cited excerpts (source ID plus file and page location), not AI-generated
answers. This retrieval mode works fully offline with no setup beyond what is shown here.

Details: [README quickstart](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/README.md#quickstart-no-model-needed)

## 4. Adding new files later: intake and reindex

Once your library is indexed, you will want to add documents over time without risking the search
you already have. The project provides a separate intake path for this. Both the Bot install and
the database-only install have a `data/intake/` directory for owner-chosen documents.

Source for everything in this section:
[docs/DOCUMENT_INTAKE.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/docs/DOCUMENT_INTAKE.md).

### 4a. Workflow

Copy approved `.txt`, `.md`, or text-extractable `.pdf` files into `data/intake/`, then run inside
the installed copy from section 2 (from the bare extracted ZIP folder, `reindex` fails with
`No such file or directory: 'generations'` and leaves the prior search intact):

```sh
sh launch.sh intake-scan
sh launch.sh reindex
sh launch.sh search 'your reference question'
```

- `intake-scan` is read-only. It reports which entries were added, changed, skipped, or failed, so
  you can check what a rebuild would pick up before running one.
- `reindex` reads exactly two flat directories: `data/intake/` and the existing `library/guides/`.
  It does not recurse into subfolders, and it does not accept arbitrary path overrides.
- `search` then queries the newly published snapshot.

### 4b. Input limits and rejected files

Text files must be UTF-8. The rebuild enforces these limits:

| Limit | Value |
| --- | --- |
| Total directory entries | 256 |
| Per input file | 16 MiB |
| Combined raw input | 128 MiB |
| Extracted text per file | 2 MiB |
| Extracted text total | 16 MiB |
| Per-PDF extraction time | 12 seconds |
| Total extraction time per rebuild | 60 seconds |

The following are rejected: symlinks, hardlinks, devices and FIFOs, names involving path traversal,
hidden or protected names, config files, executable extensions, files with shebang, ELF, or PE
signatures, and binary content in text files. PDFs must carry a valid PDF signature and must extract
nonempty text.

### 4c. What a rebuild does, and what it never touches

A rebuild copies validated bytes into a **new** `data/generations/<id>/library/`, builds its FTS5
index there, validates it, generates a static reference page, and verifies that the inputs did not
change during the run. Each generation includes a `provenance.json` recording the source directory
and name, SHA-256, byte count, source modification time, and index timestamp for every file.

Publication is a single atomic replacement of the top-level `reference.html`. Anyone already
reading the old page keeps their old immutable documents and index; reload the browser to see the
new snapshot.

On **any** failure (missing sources, unsafe input, missing PDF tools, an extraction, index, or
export error, an input that changed mid-run, or a failed publication), the prior valid search and
page stay intact. Failed or unpublished generations are retained for inspection and never
auto-erased. The main `library/` originals and its existing index are never overwritten by this
workflow.

Each run also saves `data/intake-results-<id>.json` when storage allows.

### 4d. Storage and housekeeping

Generations accumulate. Back up and remove old ones deliberately, and never remove the active
generation. Budget storage for your inputs plus at least one copied generation, its index, the HTML
snapshot, and a backup.

Legacy HTML, ZIM, and map content is **not** migrated by this intake path. For those, keep using the
original library explicitly with `--library`.

### 4e. Optional: the curated manual downloader

Separately from intake, the project provides `download_manuals.py`, which fetches its curated
catalog of public-domain and otherwise eligible manuals (21 eligible PDFs, roughly 55 MB in this
release). It is optional, and nothing is downloaded unless you run it. See
[INSTALL_AND_DOWNLOAD.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/INSTALL_AND_DOWNLOAD.md)
for the details rather than relying on this guide.

---

## 5. Optional: add a local AI model

This section covers the smallest tier the project considers reasonably useful. The project's own
[docs/HARDWARE.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/docs/HARDWARE.md)
lays out planning tiers. The **0.5–1.5B tier is explicitly called out as unsuitable for real
answers** ("optional short routing/rephrasing only; never safety-critical reasoning"). The smallest
tier the project itself recommends for actually useful, cited assistance is:

| Tier | Model size | RAM | Notes |
| --- | --- | --- | --- |
| **Practical minimum** | 3–4B, 4-bit quantized | ~8–16 GB | "Practical lower target for useful cited assistance while deterministic retrieval does the work" |

**Recommended smallest model: `llama3.2:3b`** (Meta, 3B parameters, Ollama-native, about 2 GB
download). Alternatives in the same tier: `qwen2.5:3b` or `phi3:mini` (3.8B). Any of these fits the
project's stated floor.

### 5a. Install Ollama and pull the model

```sh
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &          # if not already running as a service
ollama pull llama3.2:3b
```

Official Ollama install docs: https://ollama.com/download
Model card and license: https://ollama.com/library/llama3.2

Check the model's license before using it. It is a separate download from the Bot and carries its
own terms (Llama 3.2 Community License).

### 5b. Ask questions against your indexed library

```sh
python3 bot.py --root library ask 'Where are the beacon batteries?' --model llama3.2:3b
```

- `--model` is **required**. Nothing downloads or runs automatically.
- Inference runs CPU-only by default (`--num-gpu 0`). Add `--num-gpu N` if you have a GPU and want
  to use it.
- The default context is a small 2,048 tokens with a 128-token output ceiling. Use
  `--profile standard` for 4,096/192 if you need longer answers and have the RAM for it.
- All inference stays on loopback (`127.0.0.1`). No data leaves your machine.

Full details: [README, Optional local AI](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/README.md#optional-local-ai)

### 5c. Optional: chat UI via Open WebUI

If you want a browser chat interface instead of the CLI:

```sh
python3 http_adapter.py --root library --model llama3.2:3b --artifacts runtime/artifacts --port 8769
```

Then install [Open WebUI](https://github.com/open-webui/open-webui) separately (its own license;
version 0.11.3 minimum per the project's Pipe), import `openwebui_pipe.py` as a Function/Pipe in its
admin interface, and point it at the adapter. This is genuinely optional. The CLI `ask` command
above is fully functional on its own.

Full details: [docs/CHAT.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/docs/CHAT.md)

---

## Notes and caveats

These come from the project's own documentation.

- This is an **alpha**. Retrieval, citations, and PDF handling are verified by the project's own
  test suite. Live Ollama inference and Open WebUI integration are documented but were not
  independently re-verified in this release's audit.
- No models, maps, or documents are bundled. Every download above is explicit and separate.
- The original index is never silently overwritten. Back up `library/local-qa/guides.sqlite` before
  reindexing changed documents in the main library (see
  [docs/RECOVERY.md](https://github.com/smilidon/end-of-the-world-bot/blob/v0.1.0-beta.1/docs/RECOVERY.md)).
  The intake path in section 4 writes to new generations instead and leaves the main library alone.
- License: GPL-3.0-only for the Bot itself. Ollama, models, and Open WebUI each carry their own
  separate licenses. Check them before use.
