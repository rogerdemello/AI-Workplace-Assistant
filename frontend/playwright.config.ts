import { defineConfig, devices } from "@playwright/test";

// E2E config — assumes backend on :8099 and Vite dev server on :8080 are
// already running. No webServer block so we don't double-start. To reproduce:
//   1. Backend:  DATABASE_URL=sqlite:///./smoke.db AZURE_OPENAI_API_KEY=mock-key \
//        python -m scripts.seed_dummy_users && python -m uvicorn app.main:app --port 8099
//   2. Frontend: VITE_API_URL=http://127.0.0.1:8099 vite --port 8080   (or .env.local)
//   3. npm run test:e2e
// The backend's default CORS allowlist covers localhost + 127.0.0.1 on :8080.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8080",
    headless: true,
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
