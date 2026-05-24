# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| main | ✅ |

## Scope

In scope:
- Authentication and authorisation bypasses
- SQL injection, XSS, CSRF
- Data exposure (other users' books, API keys)
- Remote code execution
- Insecure direct object references

Out of scope:
- Denial of service via rate limit exhaustion (rate limits are intentionally conservative)
- Issues requiring physical access
- Social engineering

## Security measures

- API keys encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before storage
- Passwords hashed with HMAC-SHA256 pepper + bcrypt
- JWT tokens: 60-minute expiry, HS256, with aud/iss/iat/jti claims
- All secrets in AWS Secrets Manager in production
- Rate limiting on auth endpoints (5/min/IP)
- Correlation IDs for tracing without exposing internals
- CloudWatch logs with 7-day retention

## Known accepted risks

### JWT stored in localStorage (v1 accepted risk)

The frontend stores the JWT access token in `localStorage`. This means any XSS
vulnerability — in this codebase or a transitive frontend dependency — can read
the token.

**Mitigations in place:**
- 60-minute token expiry (`JWT_EXPIRE_MINUTES=60`) limits blast radius
- CSP headers block inline scripts and unknown sources
- `Authorization` header (not cookie) means no CSRF exposure
- Dependabot + CodeQL scan dependencies weekly

**The real fix** (deferred to v2): move the access token to an
`httpOnly; Secure; SameSite=Lax` cookie with a refresh-token endpoint.
This eliminates the XSS-to-token-theft path entirely.

Until that migration is done, treat any XSS finding as critical severity.
