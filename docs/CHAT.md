# Original chat interface — source alpha

Install the existing optional requirements (including PyMuPDF for original route
print verification), index an owner-selected library with `bot.py`, and start:

```sh
python3 http_adapter.py --root library --model YOUR_INSTALLED_MODEL --artifacts runtime/artifacts --port 8769
```

In a separately installed Open WebUI, import `openwebui_pipe.py` as a Function/Pipe
and enable/select it using your administrator interface. Open WebUI is optional
and separately licensed; version 0.11.3 has branding restrictions. See the
[dependency license audit](LICENSE_AUDIT.md), also covering PyMuPDF's AGPLv3 terms.
No live UI was changed or authenticated import tested here. The Pipe declares Open WebUI 0.11.3 minimum,
as the original does; later version compatibility is not independently qualified.
Set `EOTWB_ADAPTER_URL` in the WebUI process if changing the adapter port; default
is `http://127.0.0.1:8769/trial`. WebUI must share the adapter's loopback network
namespace (an isolated container's loopback is not the host). Network deployment,
authentication gateways and remote bind are not added by this source release.

The adapter uses the original bounded HTTPServer /trial pattern. POST JSON:
`{"messages":[{"role":"user","content":"Where are the beacon batteries?"}]}`.
The optional `route_scope` is the original SHA-256 of JSON `[user_id, chat_id]`,
computed by the Pipe from injected authenticated user/chat metadata. Raw IDs and
profiles are not forwarded. A hash is isolation, not authentication: only trusted
local processes may access this loopback server. No state/history is imported.

Success returns `answer`, `context` with `memory`, `summary`, `tool_results`,
`prompt_tokens`, and `seconds`, exactly the keys consumed by the original Pipe.
Memory and summary are intentionally empty. Tool records have `id`, `source`,
`text`. Errors are sanitized `{error, request_id, answer}` with HTTP 400; the Pipe
recognizes the original error codes. Body limit is 180,000 bytes; original
normalization accepts up to 300 messages, 2,000 user / 12,000 assistant characters.
Inference uses only the current question (400 characters maximum) and bounded
existing retrieval evidence, not chat history. Ollama URL is configurable with
`--ollama-url` but must remain numeric HTTP loopback `/api/chat`; no redirects or
proxies. CPU/4 threads, 4,096 context and 64 output-token defaults are retained.

`GET /health` reports availability. Original bounded `GET/HEAD /artifacts/` serves
route PDFs/previews. Citation sources are plain locators here; the separate
allowlisted `bot.py serve` can run on a different port. This adapter does not serve
library files or expose original history/memory endpoints.

Named/multistate requests delegate to existing repository parsers and execution
functions. Verified completed route printing retains the original user/chat hash
scope, 24-hour expiry and 128-entry cap; absent scope never retrieves another
chat's selected route. A new route attempt clears the prior selection. Restart
clears selections. Original artifact generation may retain local route metadata;
keep the runtime directory private and outside publication. Maps, Java/native
runtime and genuine route generation were not exercised in this release test.

## Remaining gaps

Illustrated `Guide:` generation is explicitly unavailable. The original exporter
has project-specific document shortcuts and depends on a reviewed PDF allowlist;
only its bounded artifact reader/server was selected here. Legacy coordinate/map
lookup dispatch, private memory/recall, calculator and original history compression
are not ported. No full-parity, whole-bot, authenticated UI or real-model claim.
The original Pipe's `Trial:` footer is retained for wire/presentation compatibility.
