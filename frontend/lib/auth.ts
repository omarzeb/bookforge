/**
 * Token storage — currently uses localStorage.
 *
 * SECURITY NOTE: localStorage is readable by any JavaScript on the page.
 * An XSS vulnerability in this app or any dependency could steal the token.
 *
 * Accepted risk for v1 — mitigated by:
 *   - 60-minute token expiry (JWT_EXPIRE_MINUTES=60)
 *   - CSP headers in Caddyfile limiting script sources
 *   - No eval(), no dynamic script injection in this codebase
 *
 * Future improvement: migrate to httpOnly + Secure + SameSite=Lax cookies
 * with a refresh-token endpoint to eliminate the XSS-to-takeover path entirely.
 */

const TOKEN_KEY = 'bf_token'

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function isAuthenticated(): boolean {
  return !!getToken()
}
