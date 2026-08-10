# TODO

## Short links

- [ ] Make short-link creation idempotent for the same active source content.
  - Normalize source URLs before lookup (for example remove tracking-only parameters such as `utm_*` and `fbclid`, while preserving parameters that affect content).
  - Reuse the existing active short code instead of creating a duplicate row for every submission of the same source URL.
  - Keep the initial implementation on a fixed TTL: reuse the code while it is active; after expiry, create a new code.
  - Add a canonical source/content key and database index/constraint strategy that remains safe under concurrent requests.
  - Avoid unnecessary repeat adapter resolution/fetching when an active canonical short link already exists.
  - Add tests for equivalent tracking URLs, meaningful query parameters, expiry, and concurrent duplicate creation.
