# MARK Frontend

Vite + React + React Router + TypeScript app for the MARK HR AI platform.

## Quick start

```bash
npm install
npm run dev          # http://localhost:8080
```

Set `VITE_API_URL` in `.env` (defaults to `http://127.0.0.1:8000`).

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Vite dev server on port 8080 |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the production build |
| `npm run lint` | ESLint |
| `npm test` | Vitest run |
| `npm run test:watch` | Vitest watch mode |

## Layout

```
src/
├── App.tsx                 — Router + global providers + ChatWidget mount
├── contexts/
│   ├── AuthContext.tsx     — JWT auth, session, role
│   └── ChatContext.tsx     — Chat state, SSE streaming, attachments
├── pages/                  — Route components (Landing, Login, Employee,
│                             Dashboard, Tickets, Employees, EmployeeProfile,
│                             Manager, Surveys, EmailAssistant, Admin,
│                             Billing, KnowledgeBase, ChatPage, NotFound)
├── components/
│   ├── auth/               — ProtectedRoute
│   ├── chat/               — ChatWidget, ChatPanel, ChatLauncher
│   ├── analytics/          — Charts, KPI cards
│   ├── employee/, tickets/, layout/, ui/
├── lib/
│   ├── api/                — Per-domain API clients (work, leave, portal,
│   │                          people, rag, email, admin, client)
│   ├── chat-api.ts         — Chat bridge + SSE stream parser
│   ├── chat-session-storage.ts
│   ├── services.ts         — Manager-page trend calls
│   └── domain-types.ts
└── hooks/, types/, test/
```

## Auth

Login posts to `POST /api/v1/auth/login` and stores the JWT in `localStorage`.
`AuthContext` validates the token via `/api/v1/auth/me` on app boot.
`ProtectedRoute` enforces role-based access.

## Chat

`ChatContext` calls:
- `POST /api/v1/chat/conversations/start` to open a conversation
- `POST /api/v1/chat/conversations/{id}/respond/stream` for token streaming via SSE
- Falls back to `POST /api/v1/chat/message` if streaming fails
- `POST /api/v1/feedback/csat` after conversation close
- `GET  /api/v1/chat/memory-cards` to surface persistent memory

The widget mounted in `App.tsx` is persistent across routes.

## Seeded test accounts

After running `cd backend && python -m scripts.seed_dummy_users`:

| Role | Email | Password |
| --- | --- | --- |
| HR | `hr1@mark.ai` | `password123` |
| Employee | `emp1@mark.ai` | `password123` |
