# Production deployment — region co-location

**Why this doc exists:** in local dev the backend runs on your laptop while
Azure OpenAI (~900ms first-connect) and Supabase (~360ms first-connect) are in
distant cloud regions. That alone puts a ~5s floor on chat time-to-first-token
no matter how well the code is tuned. The fix is **co-location**: run the
backend in the same cloud region as Azure OpenAI and Supabase. RTT drops from
hundreds of milliseconds to ~1–10ms and chat becomes sub-second.

Azure Container Apps is the simplest production target — it runs the existing
`backend/Dockerfile`, autoscales, and lives in any Azure region. App Service or
a VM work too.

## 1. Pick the region

The region must match the **Azure OpenAI resource** that your `.env` points at.

```bash
# Inspect your OpenAI resource (replace with the actual resource name)
az cognitiveservices account show \
  --name <openai-resource-name> \
  --resource-group <rg> \
  --query location -o tsv
```

That value (e.g. `eastus`, `westeurope`, `centralindia`) is the region to
deploy the backend in. If your **Supabase** project is in a different region,
either move/recreate the Supabase project closer or accept the Supabase RTT
(usually still much faster than going through your laptop).

## 2. Build and push the image

```bash
# One-time: create a container registry
az acr create -n <acrname> -g <rg> --sku Basic --location <region>
az acr login -n <acrname>

# Build and push (run from repo root)
docker build -t <acrname>.azurecr.io/mark-backend:latest backend/
docker push <acrname>.azurecr.io/mark-backend:latest
```

## 3. Deploy to Container Apps in the chosen region

```bash
# Environment (Log Analytics workspace is auto-created)
az containerapp env create \
  -n mark-env -g <rg> --location <region>

# The app itself
az containerapp create \
  -n mark-backend -g <rg> \
  --environment mark-env \
  --image <acrname>.azurecr.io/mark-backend:latest \
  --registry-server <acrname>.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 --max-replicas 3 \
  --cpu 0.5 --memory 1Gi \
  --command "uvicorn" \
  --args "app.main:app --host 0.0.0.0 --port 8000 --workers 2"
```

`--workers 2` (NOT `--reload`) gives gunicorn-style request concurrency on a
0.5-CPU instance. Bump replicas/CPU as load grows.

## 4. Secrets and environment

Pull everything from your `.env` into Container App secrets — never bake
credentials into the image:

```bash
az containerapp secret set -n mark-backend -g <rg> --secrets \
  database-url="$DATABASE_URL" \
  azure-openai-key="$AZURE_OPENAI_API_KEY" \
  secret-key="$SECRET_KEY"

az containerapp update -n mark-backend -g <rg> \
  --set-env-vars \
    DATABASE_URL=secretref:database-url \
    AZURE_OPENAI_API_KEY=secretref:azure-openai-key \
    SECRET_KEY=secretref:secret-key \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_DEPLOYMENT="$AZURE_OPENAI_DEPLOYMENT" \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT="$AZURE_OPENAI_EMBEDDING_DEPLOYMENT" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
    FAST_CHAT_MODE=true \
    CHAT_SYNC_LEXICON_SENTIMENT=true \
    CHAT_SKIP_INTELLIGENCE_SNAPSHOT=true \
    CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS=true \
    REDIS_URL="$REDIS_URL"
```

## 5. Redis in the same region

Don't keep using a remote/unreachable Redis. Either:

- Run **Azure Cache for Redis** (Basic C0) in the same region — managed, ~ms RTT.
- Or attach a sidecar Redis container to the Container App environment.

With Redis up, the cache breaker stays closed, intent classifications cache,
and RAG embeddings are reused — measurable latency improvement on its own.

## 6. Production tweaks before going live

These already ship in code but are worth verifying once you have warm intra-region
connections (the tight free-tier pool from dev no longer makes sense):

- `backend/app/database.py` — `pool_size`/`max_overflow` were capped at 2/3 for
  Supabase free-tier. With a larger Supabase plan and intra-region connections,
  raise to 10/20 to keep more warm connections in hand.
- `--reload` must **not** be in the production `command` (compose dev only).
- Apply pending alembic migrations on each deploy:
  `python -m alembic upgrade head` as a pre-start step or release hook.
- Run an `alembic current` check at boot — `alembic/env.py` now reads the same
  `.env` the app does, so this just works.

## 7. Frontend

Build `frontend/` with the production API URL pointing at the Container App
ingress:

```bash
cd frontend
VITE_API_URL=https://mark-backend.<region>.azurecontainerapps.io npm run build
```

Host the resulting `dist/` on Azure Static Web Apps (free tier), Vercel,
Netlify, or any static host. Static hosting region matters less than backend
region — the long-RTT calls happen backend → OpenAI/Supabase, not browser → backend.

## Sanity check after deploy

```bash
# Once the app is live, hit /readyz from inside the same region (or
# Cloud Shell) to confirm DB + Azure OpenAI report ok with low latency.
curl https://mark-backend.<region>.azurecontainerapps.io/readyz
```

Then run a couple of chat messages. Expect TTFT well under 1s on the streaming
endpoint — that's the real test that the co-location fix worked.
