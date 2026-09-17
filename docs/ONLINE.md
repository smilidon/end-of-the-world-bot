# Online with permission, useful when disconnected

These commands are in the unreleased Stage 3 source, not the published alpha.2
ZIP. Ordinary `launch.sh search`, indexing, local inference and static reading do
not start an Internet check. A network connection is optional, never required to
use the prepared offline library.

## Permission before connecting

The public connection-check, web-search, document-download and update-check
commands first show what they will contact and ask:

```text
Allow network access for this operation? [y/N]
```

Only an interactive `y` or `yes` authorizes that operation. Enter, `no`, EOF,
Ctrl-C or non-interactive input keeps the operation offline. Permission is not
saved and does not carry over to the next command. No DNS lookup, network worker
or reachability probe is started before approval. A command such as `search`
is not, by itself, permission to connect. There is no unattended bypass flag.

Declining a search or update check can still show an existing, clearly dated
cache. Declining a download saves nothing. `--offline` reads only the appropriate
cache: it neither prompts nor attempts a connection. Cache reads do not require
an installed model or the optional search dependency.

The current catalog downloader also asks before `--fetch` contacts publishers.
The current bootstrap asks before fetching a pinned release; its optional manual
fetch has a separate prompt. Historical release assets are unchanged until a new
release is published. `bootstrap.py --from-source` uses the selected source's
installer; dry-runs do not connect. The external `curl`/`pip` commands a user runs
to obtain source or dependencies are outside the program's permission mechanism.

This uses an **already configured connection**. It never joins a Wi-Fi network,
changes settings, installs a service or enables background monitoring. Approval
covers the displayed operation's bounded robots checks, redirects and retries;
it is not a separate prompt for every HTTP request. Localhost-only Ollama calls
are not Internet operations. Open WebUI does not automatically run online tools.

## Optional search dependency

No paid API key is required by this integration. DuckDuckGo is accessed through
optional third-party `ddgs`, not a guaranteed official full-results API. Provider
changes, throttling and outages can make search unavailable. In your existing
isolated Python environment, while connected:

```sh
python3 -m pip install -r requirements-online.txt
```

The connection checker, downloader and program update checker use the standard
library. No bot command automatically installs this dependency or a model.
Upstream reference: https://github.com/deedy5/ddgs

## Search and download commands

Run these from the source/installation directory. The application directory
normally sits beside `online_library.py`. `--app /path/to/installed-bot` before
the subcommand selects another existing installation.

```sh
# Each online operation asks before connecting.
python3 online_library.py check
python3 online_library.py search 'solar panel maintenance manual filetype:pdf'

# Saved results only: no prompt or connection.
python3 online_library.py search 'solar panel maintenance manual filetype:pdf' --offline

# Replace this placeholder with a real publisher URL.
python3 online_library.py download 'https://example.com/manual.pdf' --name manual.pdf --reindex
```

Search results are never automatically downloaded or treated as verified
answers. Choose publisher documents whose terms permit your intended use.

`check` has an 8-second parent-worker budget. Reachability of DuckDuckGo is not
proof that every service works. `search` explicitly selects the DuckDuckGo backend,
returns up to five results, and has a 30-second parent-worker budget including
DNS/provider work. If no new results are available, the same query's saved results
can be shown with their original retrieval date. Queries/snippets are stored
locally in `data/web-cache/`; they are not downloaded source documents.

`download` accepts HTTP(S) URLs and new `.pdf`, `.txt` or `.md` names. Existing
publisher robots, pacing, Retry-After and bounded redirect handling are retained.
The parent-worker limit is 120 seconds; input is capped at 16 MiB, stored text at
2 MiB. HTML becomes plain text with script/style contents removed. PDFs retain
original bytes. No document is executed or overwritten. Interrupted transfers
restart at the file level; byte-range resume is not implemented.

Documents are saved in `data/intake/`; receipts in `data/downloads/` contain the
requested/final URL, retrieval date and original/stored hashes. Matching receipts
are carried into generation provenance. Receipt-write failures are reported
separately. `--reindex` publishes only after the new generation is validated:
`saved: true, published: false` means the document is saved but the old index is
still active. A broken newly downloaded PDF may need to be moved out of intake
before retrying. Follow the recovery workflow for previously indexed originals.

## Check for program updates

These equivalent entry points check **published GitHub releases**, not branches:

```sh
sh launch.sh updates
python3 update_checker.py
python3 online_library.py updates

# Offline cache only, or explicitly choose a release channel.
sh launch.sh updates --offline
sh launch.sh updates --channel stable
sh launch.sh updates --channel prerelease
```

The checker reads local `VERSION`, asks permission, then requests release metadata
only from this project's fixed GitHub API endpoint. It needs no account or API
key. It does not download release archives, install updates, execute release text,
change application files, or overwrite the library. To update, review the returned
release link and install separately into a new folder; preserve existing data.
There is no startup check or periodic task unless separately implemented later.

Versions are compared numerically, including `alpha.10` after `alpha.2`, and a
stable version after its prereleases. `auto` follows prereleases for a prerelease
installation and stable releases for a stable installation. `prerelease` includes
both channels. Drafts and unrecognized version tags are ignored. An empty channel,
failed/rate-limited request, invalid local version or incomplete bounded listing
never establishes that the program is up to date.

Successful metadata is cached in `data/update-cache/releases.json`. Denial,
connection failure or `--offline` can use this cache, labeled `cached: true`, with
its original `checked_at` and an explicit not-live notice. No cache means the
update status is unknown, not "up to date". The parent-worker budget is 20 seconds,
with up to three pages of 100 release records and 512 KiB per response.

The development branch still has the historical alpha.2 `VERSION`. A version-only
check cannot identify unversioned source commits or assert that a checkout matches
a release. Its output says this explicitly. A release/version bump is separate
work; this stage does not replace any existing release assets.

## Verification boundary

Tests use synthetic providers/release listings, network-call traps, and real local
cache/intake/reindex operations. Permission denial, EOF, non-interactive input,
per-operation prompts, offline caches, version/channel ordering, malformed data,
rate limits and bounded pagination have regression coverage. These tests do not
qualify a live DuckDuckGo search, publisher download, physical USB or real model.
Exact executed results are recorded against the commit in the PR and Actions.
See [retrieval behavior and source freshness](RETRIEVAL.md) for Stage 3 search fixes.
