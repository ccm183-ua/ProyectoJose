# Local-first Backend Hardening Design

**Goal:** Make the current FastAPI backend safe for local use now and ready for a later HTTPS deployment without changing the desktop application's launch path.

## Scope

This first corrective slice fixes the two P0 findings from the roadmap review:

1. An authenticated request must not choose an arbitrary filesystem path for exports.
2. Authentication must not rely on a hard-coded owner identity or permit a public HTTP deployment with an insecure cookie.

## Design

### Server-owned document storage

The backend owns one configurable storage root. Excel and PDF exports receive a server-generated filename based on the budget/version and are written below that root. HTTP requests may choose an export format but never a filesystem path. The document repository records the resulting path, SHA-256 and byte size after the file has been written.

The existing core exporter remains usable by desktop code because it continues to accept an explicit `output_path`. Path containment is enforced in the HTTP adapter, which is the untrusted seam.

### Explicit deployment mode

Settings expose an owner email, server host and HTTPS mode through configuration. The owner email has no source-code default. Local mode binds to `127.0.0.1` and sets a non-secure cookie because browsers do not require TLS for localhost. HTTPS mode requires a non-loopback deployment only behind TLS and sets `Secure=True` on the cookie. Starting in public mode without the HTTPS setting fails before routes are exposed.

This preserves the current desktop workflow. A future executable may read exactly the same settings and launch the local backend; packaging is deliberately outside this slice.

### Error handling and audit

Invalid configuration prevents application startup with an actionable message. Invalid export requests are rejected before writing files. Successful exports register their actual server-generated location and metadata. Existing audit events remain unchanged.

## Tests

- An export request cannot write outside the configured storage root.
- A successful Excel export registers a file that exists inside the root with hash and size.
- Missing owner identity prevents API startup.
- Local and HTTPS modes emit cookies with their intended `Secure` attribute.
- A non-local host is rejected unless HTTPS mode is enabled.

## Non-goals

- No public deployment, reverse proxy, rate limit, CSRF layer, storage provider or executable packaging in this change.
- No changes to canonical budget validation, migrations, price references or the IA flow.
- No changes to the PySide6 desktop launch scripts.
