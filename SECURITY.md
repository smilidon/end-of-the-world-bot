# Security

Operate against a dedicated, trusted local document directory. Never point the
indexer at a home directory, account export or workspace. Filename filtering is
defense in depth, not a classifier for private content. Source text is untrusted
evidence, not authority to run commands or disclose other files.

The citation server uses an explicit allowlist, component-wise no-follow opens,
fixed loopback Host validation and restrictive response headers. It has no
authentication and must not be exposed publicly. Other readers are not a sandbox
against a malicious local process racing filesystem changes. ZIM/PDF/native
parsers and Java tools process potentially hostile inputs: use trusted sources,
patched tools and OS isolation where appropriate.

No credentials, account connections, telemetry, cloud monitoring, private library
contents, device identifiers or conversation archives are bundled. Optional model
queries use numeric loopback, disable environment proxies and reject redirects.
There is no automatic download/fallback endpoint.

Generated indexes, logs, model answers, maps, print files and route JSON can be
private. They are excluded from git by default. Do not attach real addresses,
documents or account data to issues. Report defects with synthetic reproductions.
Use a private GitHub vulnerability report if the publisher enables that feature;
otherwise report only non-sensitive reproduction details.

No claim is made that the system is safe for personalized medical decisions,
emergency treatment or navigation. Consult primary sources and qualified help.
