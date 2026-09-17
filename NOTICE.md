# Attribution and license scope

End of the World Bot's software and original repository documentation are
licensed under **GPL-3.0-only**, with the full text in [LICENSE](LICENSE).
This includes the installer, launcher, tests, repository-authored Pipe and manual
catalog metadata; it does not license the publishers' referenced works.
There is no noncommercial restriction on the software.

The project is a cleaned, modified source snapshot of the existing
compact-offline-trial project, plus the explicitly selected bounded HTML/process
helpers and model query from its local-qa/ask.py helper. SOURCE_MANIFEST.json
records selected source provenance and current staged hashes. No private project
history is included. Original publication and subsequent modifications are
recorded in Git; [CHANGELOG.md](CHANGELOG.md) summarizes merged work and dates.
The 2026-09-13 licensing audit updates documentation, attribution and the Pipe's
SPDX header; it adds no runtime functionality.

The Java bridges call OsmAnd APIs. OsmAnd upstream identifies its code as GPLv3
or later: OsmAnd – OSM Automated Navigation Directions;
Copyright © 2010–2026 OsmAnd BV.
See https://github.com/osmandapp/OsmAnd and
https://github.com/osmandapp/OsmAnd-tools. No upstream binaries, artwork, fonts,
maps or native libraries are redistributed here. Some upstream artwork has
noncommercial/no-derivatives or proprietary terms; the code license does not
cover those assets. Retain applicable notices for any components you redistribute.

Derived maps must credit © OpenStreetMap contributors:
https://www.openstreetmap.org/copyright (ODbL data obligations apply).
No OpenStreetMap database is bundled.

Python, SQLite, Ollama, Kiwix/libzim, Poppler, ReportLab, Pillow, CairoSVG,
Cairo and PyMuPDF/MuPDF retain their own licenses. Open WebUI is a separately
installed frontend with branding restrictions, not bundled project software.
See [the dependency audit](docs/LICENSE_AUDIT.md), including PyMuPDF's AGPLv3
combined-work obligations. This notice grants no rights to third-party documents,
model weights or downloaded collections. Per-entry manual rights remain in
manuals.json; free access is not a blanket redistribution license.

## Redistribution

For this GPL-3.0-only source, retain LICENSE and applicable copyright/attribution
notices, identify modifications and their dates, and license distributed modified
covered works under GPLv3. If conveying object code, satisfy GPLv3 section 6
Corresponding Source requirements (and Installation Information where applicable).
A written source offer is not automatically required for a source-only
distribution. Do not impose additional restrictions.

Separately redistributed dependencies and assets need their own notices and
obligations, including source/relinking requirements where applicable. Review the
exact versions and assets you actually ship; this source inventory is not an
audit of a complete native runtime, frontend, model or content collection.
