/**
 * Optional Sentry wiring for the frontend.
 *
 * Both the DSN and the SDK are optional. `initSentry()` is safe to call
 * unconditionally — it no-ops when `VITE_SENTRY_DSN` is unset or `@sentry/react`
 * is not installed, and it never throws.
 *
 * Env vars:
 *   VITE_SENTRY_DSN          required to enable
 *   VITE_SENTRY_ENVIRONMENT  defaults to import.meta.env.MODE
 *   VITE_SENTRY_RELEASE      optional release tag
 */
export async function initSentry(): Promise<boolean> {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) return false;

  try {
    const Sentry = await import("@sentry/react");
    Sentry.init({
      dsn,
      environment:
        (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) ??
        import.meta.env.MODE,
      release: import.meta.env.VITE_SENTRY_RELEASE as string | undefined,
      tracesSampleRate: 0.1,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,
    });
    return true;
  } catch (err) {
    // Either @sentry/react isn't installed or init failed. Either way, do
    // not block app startup — Sentry is best-effort.
    // eslint-disable-next-line no-console
    console.warn("Sentry init skipped:", err);
    return false;
  }
}
