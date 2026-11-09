# Security policy

## Supported deployment model

PhD Atlas is a public static application plus an optional single-user, loopback-only Python runtime. Neither the GitHub Pages deployment nor the local runtime constitutes a hosted multi-user SaaS product.

| Component | Security boundary |
| --- | --- |
| GitHub Pages | Public HTML, JavaScript and committed evidence projections only |
| Private backend | HTTP on loopback; not suitable for direct Internet exposure |
| Provider credentials | Environment variables or a user-owned local file; never committed |
| Local state | SQLite outside the repository; not synced automatically |
| Cloud inference | Explicit provider approval before sending application context |

Do not put API keys, tokens, personal correspondence, unredacted candidate documents, or sensitive research material in GitHub Issues, pull requests, screenshots, or committed `data/` files. Check source excerpts and publication artifacts for private information before merging.

## Report a security issue

Do not open a public issue containing a working exploit, secret, or sensitive personal data. Use the repository's private vulnerability reporting feature under **Security** if it is enabled; otherwise contact the maintainer through a non-public channel before disclosing details.

## Deployment hardening

Keep the private service bound to `127.0.0.1`. Do not expose its API with an unauthenticated reverse proxy. Publicly hosting it requires independent work on authentication, authorization, TLS, CSRF controls, user isolation, audit access and secure secret storage.

The presence of automated tests or successful deployment workflows does not establish a complete security review.
