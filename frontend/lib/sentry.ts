// frontend/lib/sentry.ts
// Sentry is opt-in — only initialises if NEXT_PUBLIC_SENTRY_DSN is set.
// Add to your .env.local: NEXT_PUBLIC_SENTRY_DSN=https://xxx@sentry.io/yyy

import * as Sentry from '@sentry/nextjs'

export function initSentry() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
  if (!dsn) return

  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0.1,   // 10% of transactions — free tier friendly
    replaysSessionSampleRate: 0,  // disable replays (costs quota)
    replaysOnErrorSampleRate: 0,
  })
}
