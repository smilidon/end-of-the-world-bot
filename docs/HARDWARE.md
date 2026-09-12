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
