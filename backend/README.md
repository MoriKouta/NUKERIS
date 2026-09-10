# Global ranking backend

Source is ready for review and local tests. No production Worker, D1 database, secret, domain, DNS or billing setting has been created or changed. `wrangler.example.toml` is an example, not an active deployment configuration. The desktop client's `GLOBAL_ENDPOINT` is empty.

## Local tests

Use Node 24 (Node >=22.13 with node:sqlite is required):

```sh
node --test backend/test/worker.test.mjs
```

These tests execute the Worker handler and SQL against an in-memory SQLite adapter implementing the D1 methods used here. They cover token hashing/signing, tampering, expiry, validation, replay/duplicate rejection, PB updates, ranks, rate-limit denial and database failure. They are not a production Cloudflare or Workerd integration test. No socket/listening server or real credentials are needed.

## Human actions before online launch

1. Review this backend, privacy/retention policies, abuse handling and operating costs.
2. In a separately authorized deployment task, select the account/environment, create the D1 database, copy the example configuration, and set its real database ID and rate-limit namespaces.
3. Apply `migrations/0001_rankings.sql` through Wrangler D1 migrations in the selected environment. Back up existing data before any later schema change. Do not reset a database to rerun this migration.
4. Provision a cryptographically random `RUN_SIGNING_KEY` of at least 32 characters with Wrangler secrets. Do not put the secret in config, source, Issue or PR text.
5. Deploy and validate the HTTPS endpoint, TLS, bindings, quotas and platform logging/retention. The example disables Workers observability, preview URLs and workers.dev; explicitly select an approved route/domain.
6. Set the approved public HTTPS origin in `src/global_client.py`, rebuild the distribution and test the complete Nuke→Worker→D1 flow before distributing online functionality.

No deployment, migration application or secret commands are run automatically by build/tests. D1 stores players, run issuance, accepted submissions and directional PBs. There is no periodic cleanup job; retention/operational maintenance must be established before production. Token recovery/login is not in scope; losing the local token loses access to that identity until an operator handles recovery/removal.

## Official references checked for implementation

- [D1 prepared statements](https://developers.cloudflare.com/d1/worker-api/prepared-statements/): bind values instead of interpolating user data.
- [D1 batch transactions](https://developers.cloudflare.com/d1/worker-api/d1-database/): a failed statement rolls back the batch.
- [D1 migrations](https://developers.cloudflare.com/d1/reference/migrations/): versioned schema changes.
- [Workers Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/): HMAC signatures and hashing.
- [Rate Limiting binding](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/): explicit request limits with no IP collection by this Worker.

See `docs/ARCHITECTURE.md` for endpoints and `docs/SECURITY.md` for assumptions and limitations.
