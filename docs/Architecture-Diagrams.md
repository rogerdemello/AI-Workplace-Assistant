# AI Workplace Assistant
## Architecture Diagrams (Mermaid)

Version: 1.0  
Date: March 27, 2026

## 1. High-Level System Architecture

```mermaid
flowchart TD
  A[Employee via Web Slack Teams] --> B[API Gateway]
  B --> C[Auth Service]
  B --> D[Chat Service]
  D --> E[AI Orchestrator]
  E --> F[RAG Retrieval]
  E --> G[Intent and Policy Guardrails]
  D --> H[Ticketing Service]
  D --> I[Calendar Service]
  D --> J[Room Booking Service]
  D --> K[Email Draft Service]
  E --> L[(Vector DB)]
  D --> M[(PostgreSQL)]
  D --> N[(Redis)]
  H --> M
  I --> O[Google Calendar API]
  I --> P[Microsoft Graph API]
  J --> M
  Q[Analytics and Risk Engine] --> M
  Q --> R[Admin Dashboard]
```

## 2. Chat and RAG Sequence

```mermaid
sequenceDiagram
  participant U as Employee
  participant UI as Chat UI
  participant API as Backend API
  participant ORC as AI Orchestrator
  participant RET as Retrieval Service
  participant VDB as Vector DB
  participant LLM as LLM

  U->>UI: Ask HR question
  UI->>API: Send message
  API->>ORC: Build context and intent
  ORC->>RET: Retrieve relevant policy chunks
  RET->>VDB: Similarity search
  VDB-->>RET: Top context chunks
  RET-->>ORC: Grounding context
  ORC->>LLM: Prompt with retrieved context
  LLM-->>ORC: Draft response with confidence
  ORC-->>API: Response plus citations
  API-->>UI: Final assistant reply
  UI-->>U: Friendly grounded answer
```

## 3. Low-Confidence Escalation Flow

```mermaid
flowchart LR
  A[User Query] --> B[Intent and Confidence Check]
  B -->|Confidence High| C[Return Auto-Resolved Answer]
  B -->|Confidence Low| D[Create Ticket]
  D --> E[Route by Category and Severity]
  E --> F[Assign HR Owner]
  F --> G[Notify User with Ticket ID]
```

## 4. Sentiment and Risk Pipeline

```mermaid
flowchart TD
  A[Chat and Survey Inputs] --> B[Sentiment Classifier]
  B --> C[(Sentiment Store)]
  C --> D[Trend Aggregator]
  D --> E[Risk Signal Engine]
  E --> F[Alerts]
  E --> G[Analytics Dashboard]
```

## 5. Deployment View

```mermaid
flowchart LR
  A[Client Apps] --> B[Ingress]
  B --> C[Kubernetes Cluster]
  C --> D[API Pods]
  C --> E[AI Worker Pods]
  C --> F[Scheduler and Queue Workers]
  D --> G[(PostgreSQL)]
  D --> H[(Redis)]
  E --> I[(Vector DB)]
  D --> J[External APIs]
  E --> K[LLM Provider]
  C --> L[Monitoring and Logging]
```
