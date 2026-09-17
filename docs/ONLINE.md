# Online when available, useful when disconnected

These commands are in the unreleased Stage 2 source, not the published alpha.2
ZIP. They supplement the offline library; ordinary `launch.sh search`, indexing,
and static reading do not probe the Internet. No paid API key is required by this
integration. DuckDuckGo is accessed through the optional third-party `ddgs`
library, not a guaranteed official full-results API. Provider changes, throttling,
blocked access and outages can make search unavailable.

## Prepare the optional search dependency while connected

Use your existing isolated Python environment, then install:

```sh
python3 -m pip install -r requirements-online.txt
```

The connectivity check and downloader use the standard library and do not need
`ddgs`. No dependency or model is downloaded automatically by a bot command.
Upstream API reference: https://github.com/deedy5/ddgs

Run these commands from the extracted source/installation directory. The default
application directory is beside `online_library.py`; `--app /path/to/installed-bot`
selects another existing installation without changing its application code.

```sh
# Try an existing Internet connection. No joining Wi-Fi or changing settings.
python3 online_library.py check

# Search DuckDuckGo, saving a small result cache for the same query.
python3 online_library.py search 'solar panel maintenance manual filetype:pdf'

# Read a previous query's cache without attempting ANY network request.
python3 online_library.py search 'solar panel maintenance manual filetype:pdf' --offline

# Download one owner-selected document; publish a new offline generation.
python3 online_library.py download 'https://example.com/manual.pdf' --name manual.pdf --reindex
```

The example download URL is a placeholder, not a real manual. Choose a real
publisher URL whose terms permit your intended use. Search results are never
automatically downloaded or treated as authoritative evidence. The current
command interface is standalone; Open WebUI does not automatically invoke these
operations. No background network monitor, automatic software updater, or
automatic connection to unconfigured wireless networks is installed.

## Behavior and bounds

`check` attempts an HTTPS request to DuckDuckGo within an 8-second parent-worker
budget. A refusal response is distinguished from an unavailable endpoint.
Reachability of one endpoint is not a guarantee that every service works.

`search` uses `backend='duckduckgo'` explicitly, returns at most five results and
has a 30-second parent-worker budget including DNS and provider retries. No
fallback to another search provider is requested. If the operation fails or yields
no new results, a matching cache can still be used. Cached results retain their
original retrieval date and are prominently labeled; they are not live answers.
Cache files are under `data/web-cache/`. A missing dependency, failed connection,
or malformed cache must not break the ordinary offline library. Queries and
snippets are saved locally; remove that cache deliberately when no longer needed.

`download` accepts an explicit HTTP(S) URL and a new `.pdf`, `.txt` or `.md`
filename. It follows bounded redirects, applies the existing publisher robots,
pacing and Retry-After logic, and has a 120-second parent-worker budget. Downloads
are capped at 16 MiB; stored text is capped at 2 MiB. HTML pages can be saved as
plain text, with scripts/styles and markup removed. PDFs retain original bytes.
No downloaded content is executed. Interrupted downloads leave no final intake
file and can be retried from the start; byte-range resume is not implemented.
Existing documents are never overwritten. A PDF signature is not proof that all
its pages are extractable: `--reindex` separately validates extraction.

Completed documents go to `data/intake/`. A receipt under `data/downloads/`
records the requested/final URL, download date, content type, original-byte hash
and stored-byte hash. A matching receipt is included in the generation's
provenance manifest; editing the document breaks that association. Saving a
receipt can fail independently of saving a document; the result explicitly
reports that condition and retains the receipt in console output.

Without `--reindex`, the result says `saved: true, published: false`. With it,
publication succeeds only after the complete generation is validated. A failed
reindex keeps both the downloaded original and the previous usable browser/index
publication. A successfully downloaded but broken PDF may need to be moved out
of `data/intake/` before the next rebuild. Do not remove a previously indexed
original without following the existing recovery workflow.

## Verification boundary

Synthetic tests exercise provider selection, offline cache fallback, corrupt
cache handling, limits, HTML-to-text conversion, existing-file protection,
provenance, download-to-reindex integration and failed-publication preservation.
Network workers use the same bounded subprocess runner as document extraction.
These tests are not a successful live DuckDuckGo search, publisher download,
physical USB test, or a claim of Internet availability. Commit-specific executed
checks are recorded in the pull request and Actions results.
