# Security and launch gates

## Required before deployment

Historical repository commits contained deployable secrets and a private key. Removing files from the current tree does not invalidate those values or remove them from Git history.

1. Rotate every M-Pesa/Daraja and Kopo Kopo credential ever committed.
2. Rotate database, admin, RouterOS, VPN/RADIUS, JWT, and encryption secrets that may have appeared in repository files or logs.
3. Revoke and replace the committed private key/certificate material.
4. Verify GitHub secret-scanning alerts, then purge sensitive history in a coordinated maintenance window. History rewriting is intentionally not performed by this feature branch because it rewrites public commit IDs and every clone must be repaired.
5. Configure provider credentials only in the deployment secret store; never commit `.env`.
6. Test database backup and restore, provider callbacks, payment reconciliation, access expiry, and RouterOS rollback.
7. Restrict the database and RouterOS control network by firewall. API port 8728 must not be reachable from the public Internet.

## Reporting

Do not open a public issue containing credentials, customer phone numbers, router addresses, or payment payloads. Contact the repository owner privately and include only a request ID and redacted reproduction details.
