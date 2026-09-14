# Hardware: estimates, not guarantees

Portable planning guidance; no particular manufacturer is required. Linux is the
verified host family. macOS and Windows are untested; Unix process controls,
file-descriptor operations and native Java libraries are nonportable dependencies.

| Tier (estimated planning floor) | CPU | RAM | Model and disk budget |
| --- | --- | --- | --- |
| Retrieval only | 2 modern 64-bit cores | 4 GB | No model; reserve 2 GB for Python/tools plus documents/index |
| Small local model | 4 modern cores | 8 GB | Quantized 1–3B; estimate 1–3 GB weights, reserve 10 GB tools/cache plus data |
| 4B reference assistant | 4–8 modern cores | 16 GB preferred | Quantized 4B; estimate 3–5 GB weights, reserve 15 GB tools/cache plus data |
| Larger library + optional maps | 8 cores preferred | 16–32 GB | Add selected OBF/ZIM sizes, indexes, extraction copies and backups |

GPU is optional. CPU-only correctness and speed on these estimated tiers have not
been benchmarked. Context/cache memory, quantization, model architecture, runtime
and concurrent apps change requirements. SSD storage helps; data collections can
dwarf model storage. Keep free space for an extracted copy and a separate backup.

## Qualification boundary

No model-capacity tier above was benchmarked in this release audit. Only Linux
synthetic retrieval, citation and print tests were exercised. The optional model
CLI uses a 4K context and defaults to CPU; model fit and throughput need separate
measurement on the selected device.

For a portable kit budget independently for power, cooling, storage reliability,
display/input and an offline copy of recovery instructions. No exact battery
runtime or untested hardware compatibility is promised.

## Cheap/old hardware and flash installation

Minimum software: Linux + Python 3.11 with SQLite FTS5 to install/prepare the
library. No pip packages or GPU are needed for text search, static browser export
or document printing. A recent browser alone can read a prepared `reference.html`
offline. The smallest practical planning target is 2 CPU cores / 2 GB available
RAM for a **small** text library and a lightweight browser; 4 GB is recommended.
This is an estimate, not a measured 2 GB qualification. Modern full desktop browsers
can dominate RAM usage. Export limits (10,000 chunks / 16 MiB text, plus JSON/browser
copies) keep memory bounded; larger collections use CLI retrieval instead.

Installer preflight requires 100 MiB free; reserve at least 1 GB for the small
eligible manual collection, indexes, snapshots and headroom. A 4–8 GB drive can
carry a small reference kit without models; plan separately for PDFs, archives,
maps, optional tools and backups. Model tiers above remain estimates. Slower
CPU-only inference is acceptable, but the existing bounded request can time out;
use search/database mode if a chosen model is impractical. No model was benchmarked
for this feature. Keep weights on the host SSD; USB model storage is opt-in,
empty until an explicit separate download, and may load extremely slowly.
FAT/exFAT permission semantics, physical USB reliability, power-loss recovery and
native Windows/macOS are unqualified; the shell launcher avoids executable-bit
requirements but does not bundle a host runtime.
