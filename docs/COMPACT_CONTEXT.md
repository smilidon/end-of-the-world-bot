# Compact-context local assistance

No-model operation is first-class: static browser search, CLI retrieval, reindex,
scoped document editing/printing, arithmetic and diagnostics do not need inference.
The chat adapter routes `Read:`, `Search:`, `Reference:`, `Files:` and `Calc:` to
explicit deterministic handlers. Existing route/print handlers remain deterministic.
Document and diagnostic actions are dedicated explicit CLI/API operations, never
a model-controlled tool catalog. No history or tool definitions are sent to a model.

```sh
sh launch.sh calc '(8 + 4) / 3'
sh launch.sh ask 'Where is the beacon?' --model YOUR_INSTALLED_MODEL --profile tiny
sh launch.sh ask 'Where is the beacon?' --model YOUR_INSTALLED_MODEL --profile standard
```

| Profile | Context | Conservative input budget | Selected excerpts | Output-token ceiling |
| --- | --- | --- | --- | --- |
| `tiny` (default) | 2048 | 1536 | At most 2 × 400 characters | 128 |
| `standard` | 4096 | 3072 | At most 3 × 700 characters | 192 |

The serialized prompt contains exactly two messages: one short fixed instruction
and the **current question plus whitelisted source IDs, short file/location labels
and selected excerpts**. Never whole documents, full histories, all-tools catalogs,
large schemas or diagnostic raw logs. Source excerpts are labeled if partial;
source text cannot add prompt keys or tools. Questions retain the 400-character
limit. The instruction requires citations, preserved caveats and UNKNOWN when
insufficient, and rules out tool execution/medical/navigation decisions.

Budget checking counts serialized UTF-8 bytes plus a conservative 64-token template
allowance before any model request. This is intentionally pessimistic, not an exact
measurement for every tokenizer/template. Add `--prompt-budget N` to reduce the cap;
it cannot exceed the selected profile. Excerpts are removed until the request fits.
If no cited evidence fits, return **“Answer may be limited”** with a concise, labeled
source excerpt and make no model call. Request metadata reports the profile, bytes
and conservative bound. The context/output limits are also sent to Ollama.

Generated output is never silently sliced to fit. A model length stop, output
ceiling, oversized response or reported excessive prompt count causes the generated
answer to be withheld and replaced by the visibly limited source fallback. Normal
answers request at most two short cited sentences. The existing bounded timeout,
numeric-loopback endpoint, disabled proxies/redirects and no-download policy remain.
The model's own tokenizer/template and tiny-model correctness remain limitations.

Arithmetic uses a small AST whitelist (+, -, *, /, //, %, parentheses/signs), not
eval or shell; expressions have length/node/magnitude bounds. Diagnostics proposes
only code-reviewed reversible checks, not model-created commands. A small model may
rephrase cited excerpts, but it is never relied on for safety-critical reasoning.

## Hardware and prior observation

See HARDWARE.md for planning estimates. The owner reports that an earlier 4B setup
with **4096 context and 8 GPU + 25 CPU layers** was usable at roughly **29–61 seconds**
for **955–2457 input tokens**. Approximately **17.5K prompt/context inflation** caused
multi-minute slowness. This is a reported baseline from the prior trial, not a new
benchmark reproduced by this PR, and does not establish performance on other hosts.
The design prevents that kind of unbounded prompt growth rather than promising
real-time inference. Slower CPU-only operation is acceptable; retrieval remains
available when a model is too slow.
