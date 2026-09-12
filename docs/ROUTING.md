# Optional routing and native maps

Preserved source: named_routing, multistate_routing, corridor_routing, the Java
bridges, local_visuals/route_map and print_route_formatter. Synthetic parser,
fallback, geometry and PDF tests are verified; real OBF routing/native rendering
were not rerun in the clean repository. No binaries or maps are shipped.

## Existing dependency contract, not a new installation recipe

The bridges expect a compatible Java runtime supporting source-file launch, an
OsmAnd MapCreator build with OsmAndMapCreator.jar and lib/*, and an owner-created
navigation manifest. Native rendering additionally needs compatible bundled native
libraries, Pillow, CairoSVG/system Cairo and a configured font directory.

Use [official OsmAnd tools source](https://github.com/osmandapp/OsmAnd-tools)
and its build instructions. The prior setup used a master-snapshot API, which is
not pinned here; a fresh upstream build is not guaranteed compatible. Do not
download an arbitrary jar and assume qualification.

Expected tree beneath the directory supplied via --nav or EOTWB_NAV:

```text
navigation/
  manifest.json
  maps/<chosen-region>.obf
  tools/MapCreator/OsmAndMapCreator.jar
  tools/MapCreator/lib/<upstream runtime libraries>
```

Manifest items consumed by the source require: obf_file (maps/ relative path),
status=verified_download, zip_crc_verified=true, unpacked_bytes, obf_sha256,
version and url. Those are integrity receipts, not flags to set without checking.
Never place signed URLs or credentials in the manifest. Source/runtime outputs
can include paths, coordinates and map feature identifiers: keep outputs private.

Existing settlement CLI, only after satisfying and checking that contract:

```sh
python3 named_routing.py --nav YOUR_NAV_DIRECTORY --region YOUR_REGION --origin YOUR_TOWN --destination YOUR_OTHER_TOWN
```

This returns route JSON; it does not auto-print. Street requests are parsed by
multistate_routing.parse and executed explicitly with multistate_routing.execute.
Missing/ambiguous streets require clarification, not a town-center substitute.
Exact building, interpolated number and approximate street location are labeled
separately; none proves an entrance. Current corridor selection is limited to
Michigan, Ohio, Indiana, Illinois and Missouri, up to five maps / 4.4 GB total.
It is not continent-wide routing.

EOTWB_CACHE controls coverage cache storage, EOTWB_ARTIFACTS the generated files,
EOTWB_FONTS the font directory. Outputs default under runtime/, not source history.
The native renderer checks exact 31-bit projection alignment; failure produces a
clearly labeled geometry-only map. Optional rendering dependencies are listed in
requirements-optional.txt. Native dependencies remain an integration blocker for
a newly provisioned machine.

For an existing locally validated print-format route JSON and PNG:

```sh
python3 -m local_visuals.print_route_formatter route.json route.pdf
```

The formatter's validate() documents the required fields. verified_source=true is
a caller assertion, not cryptographic proof: only supply reviewed engine results.
The synthetic test uses that schema solely to test printing, not to prove a route.
Native OBF data and derived maps need OpenStreetMap attribution; fuel services,
traffic, road openings, entrances and safe passage are not live-verified.

Official map/download instructions: https://osmand.net/docs/user/personal/maps-resources/
OpenStreetMap data/license: https://www.openstreetmap.org/copyright
No maps, APKs, map artwork or copyrighted dataset bundles are included.
