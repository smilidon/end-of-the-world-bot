# License audit — public source distribution

Audited 2026-09-13 against main at
`f0d6908310632e909bf141a96c1743e5f4dc6267` (merged PRs #1–#3), with the
license/documentation corrections described here. Unmerged PR #4 is outside scope.

## Repository license and boundaries

**GPL-3.0-only** covers this project's software and original repository
documentation, including scripts, tests, the repository-authored Open WebUI Pipe
and catalog metadata. The full GNU GPL version 3 text is in [LICENSE](../LICENSE);
SPDX headers select version 3 only, not “or later”. Commercial use is permitted
under the GPL; manual-download terms do not add software-use restrictions.

The prior publication audit recorded the owner's authorization to license the
selected local source and the absence of original license/copyright headers.
This audit preserves that recorded provenance and existing attributions; it does
not independently establish the ownership of unpublished originals. No private
source was accessed and no new copyright owner has been invented.

User-imported documents, models, maps and archives remain separate works under
their own terms. None is bundled. `manuals.json` contains publisher references,
historical hashes and per-entry rights, not the manuals themselves. Its personal/
noncommercial download scope is not a restriction on this software. Publicly
accessible content is not necessarily open-licensed or redistributable.

## Direct dependencies and optional integrations

These are dependency references, not vendored packages. Installed Python metadata
and available license files were inspected on 2026-09-13; ranges in the optional
requirements do not pin every future install or transitive dependency.

| Component | Evidence / license | Use and distribution boundary |
| --- | --- | --- |
| Python / SQLite | [PSF and bundled notices](https://docs.python.org/3/license.html) / [public domain](https://www.sqlite.org/copyright.html) | System runtime and FTS5; not bundled |
| ReportLab 5.0.0 | Installed metadata and license: BSD terms | PDF generation/tests; requirements reference only |
| Pillow 12.3.0 | Installed metadata and license: MIT-CMU | Images/tests; requirements reference only |
| CairoSVG 2.9.0 | Installed metadata: LGPL-3.0-or-later | Optional SVG rendering; requirements reference only |
| PyMuPDF 1.28.0 / MuPDF | [Pinned COPYING](https://github.com/pymupdf/PyMuPDF/blob/1.28.0/COPYING) and installed metadata: AGPLv3, with a separate commercial alternative | `fitz` import in `local_visuals/print_routes.py` for PDF checking/previews; pinned in both requirements files, not bundled |
| Poppler | [Upstream](https://poppler.freedesktop.org/), GPL family; exact system build unpinned | External `pdftotext`; no binary |
| Kiwix tools / libzim | [Kiwix](https://github.com/kiwix/kiwix-tools) / [libzim](https://github.com/openzim/libzim), GPL family; builds unpinned | Optional external ZIM tools; no tools or archives |
| Ollama | [Upstream LICENSE](https://github.com/ollama/ollama/blob/main/LICENSE): MIT | Optional loopback inference runtime; neither runtime nor weights bundled |
| OsmAnd / OsmAnd-tools | [Upstream LICENSE](https://github.com/osmandapp/OsmAnd/blob/master/LICENSE) read 2026-09-13: GPL-3.0-or-later code with third-party exceptions; artwork separately restricted | Java calling bridges only; no engine, native library or artwork |
| Java runtime / Cairo / fonts | Distribution-specific Java notices; [Cairo COPYING](https://gitlab.freedesktop.org/cairo/cairo/-/blob/master/COPYING) LGPL-2.1/MPL-1.1 options; each font's own license | Optional external map/rendering stack, unpinned and not bundled |
| Open WebUI 0.11.3 | [Versioned LICENSE](https://github.com/open-webui/open-webui/blob/v0.11.3/LICENSE), clause 4 branding restrictions | Optional separately installed frontend; project Pipe included, upstream UI code absent |
| OpenStreetMap | [ODbL and attribution](https://www.openstreetmap.org/copyright) | No database; derived maps require attribution |
| Documents / model weights / ZIM contents | Publisher/model/collection-specific terms; manual references in `manuals.json` | User supplied or explicitly downloaded separately; not relicensed by the software |

PyMuPDF's free option is AGPLv3, not a permissive license and not a paid-only
dependency. GPLv3 section 13 permits combination with AGPLv3 code: the GPL still
covers this project's part, while AGPLv3's network-interaction source requirements
apply to the combination as such. Redistribution of such a combination must also
satisfy the applicable source and notice obligations. This is not a claim that a
combined runtime is exclusively GPL-3.0-only.

Open WebUI 0.11.3 is the Pipe's declared minimum. Its license restricts changing
branding, subject to stated exceptions; it must not be represented as an
unrestricted GPL-compatible open-source component of this distribution. Its
separate installation is optional, and the standard-library CLI needs neither
Open WebUI nor model weights. No authenticated UI or later-version compatibility
qualification is implied. Likewise, do not bundle restricted OsmAnd artwork under
the assumption that its software license covers it.

## Headers, manifests and GitHub metadata

- All 37 tracked Python, Java and shell source files carry
  `SPDX-License-Identifier: GPL-3.0-only`. The Pipe header was the missing one;
  it is now added after its existing metadata docstring, without runtime changes.
- [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json) records 21 selected-source
  provenance entries, not the full release inventory. `source_sha256` values are
  historical original-source receipts, not independently revalidated here.
  `staged_sha256` values identify the current destination bytes; stale entries for
  `model_query.py` and `openwebui_pipe.py` are refreshed. Git retains prior values.
- [RELEASE_FILES.txt](../RELEASE_FILES.txt) is the complete package allowlist;
  [FILE_MANIFEST.sha256](../FILE_MANIFEST.sha256) hashes every allowlisted file
  except itself. Neither manifest imports runtime data or grants content rights.
- `bootstrap.py` deliberately retains the published v0.1.0-alpha.2 executable/
  catalog pins. They identify that release, not this amended branch. No version,
  published asset, release checksum or bootstrap pin is changed by this audit.
  A future release needs a new version and matching bootstrap pins before upload.
- GitHub reports a public repository, default branch `main`, and detected license
  `GPL-3.0`. That generic detection does not distinguish “only” from “or later”;
  the explicit repository grant and SPDX headers do. The current description
  accurately labels a Linux-first source alpha; homepage and topics are empty.
  No hosting metadata change is needed.

## Remaining qualification limits

The shipped software source has an open-source license; this is not blanket
approval of every optional frontend, native dependency, asset or model. A combined
binary/offline appliance needs an inventory of the exact shipped versions,
transitive dependencies and assets, with corresponding notices and source
compliance. Original ownership evidence remains the prior publication record;
manual rights and live publisher availability were not independently rechecked.
See [NOTICE](../NOTICE.md) and [verification](VERIFICATION.md).
