// frontend/instrumentation.ts
// Next.js loads this on startup — where we init Sentry server-side.
export async function register() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
  if (!dsn) return

  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { init } = await import('@sentry/nextjs')
    init({ dsn, environment: process.env.NODE_ENV, tracesSampleRate: 0.05 })
  }
}
