# Security and privacy

NUKERIS is fully offline by default. Installing, importing or opening the panel sends no requests. Enabling ranking alone also sends no Global request. No telemetry, analytics, LAN/port scan, mDNS, broadcast discovery, listening ports, auto-update, background services or IP geolocation is implemented.

Nuke API use is limited to GUI detection and panel registration. NUKERIS does not inspect or modify current scripts, nodes, knobs, Viewer, frames, timeline, Undo, asset paths, project data, Foundry accounts or licenses. It does not collect hostname, OS username or environment variables for ranking. Standard home-directory expansion is used only to locate the requested local settings directory.

Public ranking data: nickname (2–16 ASCII letters/digits/underscore/hyphen/dot), manually selected country and manually entered region, mode/ruleset, score, elapsed milliseconds, lines, pieces and NUKERIS version. Protocol exchanges additionally carry the server-issued player credential and signed run token over HTTPS. No email, password or Foundry login is needed. Server signing secrets are never embedded in the client.

The player's token is a bearer credential saved in their local settings, not a server secret. POSIX-created files use mode 0600 and directories 0700. On Windows, access depends on the user's existing profile ACL; no ACL changes are made. Anyone who can read the file can use the online identity. Do not share settings.json, logs containing tokens, or personal backups publicly. The code does not print tokens or HTTP response bodies.

The Worker uses parameterized SQL, HMAC-SHA256 signed run tokens, token hashes, version/ruleset validation, bounded bodies, result and duration sanity checks, transactional unique run submissions and directional PB upserts. Unknown request fields are rejected. Database failures return a generic error without SQL/stack traces. Global registration is rate limited without reading IP addresses; authenticated requests also use a player key. Rate limiting is Cloudflare's binding and is local to its enforcement location, not a globally serialized quota.

This is friendly open-source competition, not authoritative anti-cheat: a modified Python client can fabricate plausible gameplay; no replay verification is in scope. Server duration checks allow 2 seconds of clock/start tolerance and up to 15 seconds for network/dispatch delay. Timely submission may fail after longer outages or a long-hidden finished run; the personal result is retained.

Studio is trust based and inherits existing share permissions. No NAS password is stored. Symlink checks and path containment reduce accidental escape but do not defend against a malicious share administrator racing filesystem replacements. OS/NAS behavior determines cross-machine locks and atomicity. Abrupt power loss and unavailable disks remain platform risks; no final file is deliberately truncated or unlinked before replacement.

Cloudflare inherently receives transport metadata for HTTPS service operation; this Worker does not query geolocation, persist IPs or enable request logging/analytics. Operators must review Cloudflare account-level logging and retention before publishing the service. There is no production deployment in this change.
