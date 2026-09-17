# Merged changes and contributions

This summary covers work actually merged into `main` through
`f0d6908310632e909bf141a96c1743e5f4dc6267`. Dates below are UTC.

- **2026-09-13 — v0.1.0-alpha.2 ([#3](https://github.com/smilidon/end-of-the-world-bot/pull/3)):**
  Added the publisher-referenced manual catalog and terminal-agent setup
  documentation. The source package contains no manuals or model weights.
- **2026-09-13 — v0.1.0-alpha.1 ([#2](https://github.com/smilidon/end-of-the-world-bot/pull/2)):**
  Added the Linux source ZIP, user-local installer, portable launcher and synthetic
  packaging/install tests. This is not a bootable image or bundled runtime.
- **2026-09-12 — resource cleanup ([#1](https://github.com/smilidon/end-of-the-world-bot/pull/1)):**
  Closed query locks and HTTP error responses deterministically, with regression
  tests for repeated failures and recovery.
- **2026-09-12 — initial public source:**
  Published bounded offline retrieval, source/page citations, optional routing and
  printing bridges, the Pipe/loopback adapter, and synthetic tests. Linked the
  public project introduction.

Open PRs are not release history. This summary does not include PR #4 or claim
new update feeds, live external-data integrations, additional hardware support,
real-model/native-map qualification or safety guarantees.

## Contributing

Open an issue or a focused pull request against `main`. Keep contributions under
GPL-3.0-only with existing attribution intact; identify any third-party code and
its license. Use synthetic fixtures rather than personal libraries or model/data
bundles. Run the tests, privacy scan and manifest checks in
[the publication guide](docs/PUBLISH.md), and describe exactly what was verified.
