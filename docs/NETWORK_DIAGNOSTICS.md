# Confirmed Linux network observations

Bot installs offer an **optional, deterministic, no-model** terminal workflow:

```sh
sh launch.sh network-diagnose
```

Database-only mode intentionally refuses this command. Its offline static reader
and reference search do not require or perform any network discovery.
Native Windows/macOS adapters are future work, not supported or qualified here.

## Consent and exact scope

1. The menu discovers **metadata only** for at most 64 interfaces under
   `/sys/class/net`, whose kernel links must resolve below `/sys/devices`.
   It previews each exact `type`/`operstate` path, `/proc/net/route`, and the
   approved resolver target. It does not read file contents yet.
2. Read the paths, byte limits and privacy notice. Type the displayed `SCAN …`
   phrase to read those sources, or Enter to cancel. Confirmation expires in
   five minutes; changed adapter/resolver metadata requires a new preview.
3. Inspect anonymous interface state, whether an IPv4 default route was observed,
   and the count of configured `nameserver` entries. These are observations of
   **current configuration at read time**, not historical logs or proof of working
   DNS/Internet. Sources can change during reads. Missing/unsafe/malformed sources
   are reported as unavailable rather than evidence of a healthy system.
4. If a wireless adapter was discovered, optionally select its listed name. A
   **separate second confirmation** previews `/usr/sbin/iw dev NAME scan` and
   warns that a Wi-Fi scan emits radio probes. Enter skips it. No scan is automatic.
5. Optionally name a new `.md` workspace report. Enter saves nothing. Reports
   never overwrite existing documents. Print using the confined document tool:

```sh
printf '%s\n' '{"action":"print","name":"Network observations.md"}' | sh launch.sh document
```

Open the resulting `workspace/Network observations.md.print.html` locally and use
Print/Save as PDF. Printing needs no model or network.

## What is read or executed

Local discovery reads **no home documents, browser profiles, authentication files,
network credentials, connection profiles or arbitrary paths**. Resolver reads are
limited to `/etc/resolv.conf` or its resolved target at one of:

- `/run/systemd/resolve/stub-resolv.conf`
- `/run/systemd/resolve/resolv.conf`
- `/run/NetworkManager/resolv.conf`

Other resolver targets are omitted, not followed. Content opens reject symlinks
in every component, nonregular files and multiple hard links. Adapter metadata is
bounded to 128 bytes per field; route/resolver files to 32 KiB each. The maximum
local payload is 80 KiB. An overflow rejects that source (a single extra byte is
read to detect overflow). These are size bounds, not a hard timeout on kernel
file reads. Preview and in-memory results are small; nothing is indexed.

Local observations execute **no commands** and make **no socket/DNS/Internet
requests**. The optional Wi-Fi adapter is the only command exception: fixed binary
and arguments, no shell, stdin disabled, minimal environment, stderr discarded,
32 KiB stdout limit and 10-second streaming timeout. Only the owned scan process
is stopped on timeout/overflow. Missing `iw`, insufficient permission, an absent
radio, or scan failure is reported without elevation or retry. `iw` is optional
and must already be installed at that exact path; the app never installs it or
sets capabilities. Many distributions do not allow unprivileged scans: use the
local observations or skip Wi-Fi; do not run this app as root.

No joining/disconnecting networks, SSID selection, credential entry, configuration
changes, routing changes, automatic repair, service restart, telemetry or model
invocation is provided. IPv6 route and VPN-policy analysis, reachability probes
and DNS queries are **not implemented**. Wi-Fi results count reported BSS entries;
that count is not a connectivity test or guaranteed inventory.

## Privacy and evidence

The on-screen consent preview lists local paths/interface names. Saved reports
omit interface names, paths, IP/MAC addresses, SSIDs, domains and raw source output.
Only whitelisted state values, counts, timestamps, fixed caveats and reversible
checks survive; heuristic secret redaction is additionally applied before report
persistence. Logs, SSIDs and other source content are untrusted, never instructions.
No raw network output is stored or passed to a model. No network diagnosis is
triggered by a document, model response, normal search or startup.

Reports explicitly say **insufficient evidence for a root cause**, give multiple
possible causes and suggest limited checks such as inspecting a cable/router's
indicators. They do not prescribe destructive commands or assert a definite cause.
A report usually occupies a few KiB; printing adds a similar-sized escaped HTML
file. Review even a redacted report before sharing it.

## Qualification

`tests/test_network_diagnostics.py` uses temporary synthetic sysfs/proc/resolver
fixtures and mocked Wi-Fi process/selector output. It covers consent, expiry,
cancellation, changed/forbidden sources, links/devices/FIFOs, bounds, privacy,
prompt-like data, fixed command arguments, timeout cleanup, report containment,
printing and launcher mode separation. The fresh-clone installer verifier runs
these tests from the **installed Bot package** and checks database-mode refusal.
No physical adapter, live host scan, root/elevated scan, or non-Linux device test
is claimed. URL import and software update drafts remain outside this milestone.
