# License audit — staged source only

Selected license: **GPL-3.0-only**, full text in LICENSE. This is compatible with
the intended GPLv3 OsmAnd integration; it does not relicense independent upstream
assets. Original selected local source files did not contain license/copyright
headers; the owner's explicit publication/licensing instruction authorizes this
staged choice. Existing text/attribution is retained; new SPDX headers identify
the staged license. No upstream source tree or binary package was copied.

| Component | Evidence / license | Distribution here |
| --- | --- | --- |
| Local project source / minimal ask.py functions | Explicit owner instruction; SOURCE_MANIFEST.json hashes | Modified GPL-3.0-only source |
| OsmAnd | Upstream master LICENSE read 2026-09-12: GPLv3 code, separately restricted artwork | Java calling bridges only; no engine code/binary/artwork |
| ReportLab 5.0.0 | Installed metadata and LICENSE inspected: BSD terms | Dependency reference only |
| Pillow 12.3.0 | Installed metadata: MIT-CMU | Dependency reference only |
| CairoSVG 2.9.0 | Installed metadata: LGPL-3.0-or-later | Optional dependency reference only |
| Python / SQLite | PSF / public domain upstream | System dependency only |
| Poppler | GPL family; inspect chosen distribution's package notices | External pdftotext, no binary |
| Kiwix / libzim | GPL family upstream; exact optional tool build unpinned | No tools or ZIMs |
| Ollama / model weights | Ollama MIT; each model has separate terms | No runtime or weights |
| Open WebUI | Separate upstream licensing, version dependent | Not redistributed or integrated |
| OpenStreetMap | ODbL and attribution | No datasets |

Official source/license references:
https://raw.githubusercontent.com/osmandapp/OsmAnd/master/LICENSE
https://github.com/osmandapp/OsmAnd-tools
https://github.com/Distrotech/poppler
https://poppler.freedesktop.org/
https://github.com/openzim/libzim
https://github.com/kiwix/kiwix-tools
https://github.com/ollama/ollama
https://github.com/python-pillow/Pillow
https://github.com/Kozea/CairoSVG
https://www.reportlab.com/
https://www.sqlite.org/copyright.html

Scope: source-package audit, not a claim that every transitive dependency of an
unpinned native OsmAnd distribution was audited. A future binary/offline appliance
release needs its own full dependency inventory, source-offer compliance and
asset rights review. No copyrighted data bundles, solar documents, maps, ZIMs,
models, APKs, fonts or restricted artwork are included.
