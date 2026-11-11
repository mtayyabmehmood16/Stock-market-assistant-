# AWS-Style System Architecture

## 1. High-Level AWS Service Topology

```mermaid
flowchart TB
    User(["Retail / Quant Analyst User"]) -->|HTTPS| CF["Amazon CloudFront + WAF"]
    CF -->|Static / SSR| Web["AWS Amplify / S3 + Next.js Frontend<br/>(Chat, Candlestick Charts, Tables, Job Tracker)"]
    CF -->|/api/* REST & SSE| ALB["Application Load Balancer (ALB)"]

    subgraph VPC["Amazon VPC (Private Subnets)"]
        subgraph ECS_App["ECS Fargate — API & AI Harness"]
            API["FastAPI Gateway"]
            Harness["AI Harness<br/>(Context, Permissions, Workflow)"]
            Tools["Tool Calling Router"]
        end

        subgraph ECS_MCP["ECS Fargate — MCP Integrations (AWS Cloud Map)"]
            MCP_Mkt["market-data-mcp<br/>(yfinance / Market APIs)"]
            MCP_Res["company-research-mcp<br/>(SEC EDGAR XBRL & Filings)"]
        end

        subgraph Async["Async Queue, Workers & Isolated Sandbox"]
            Redis[("Amazon ElastiCache for Redis<br/>Celery Broker & Progress Pub/Sub")]
            Worker["ECS Fargate — Celery Workers<br/>(Deep Analysis, Retries, Progress)"]
            Sandbox["Isolated Python Sandbox<br/>(Ephemeral Fargate / Firecracker,<br/>--network=none, --read-only, CPU/RAM caps)"]
        end

        subgraph Data["Persistence & Security"]
            RDS[("Amazon RDS for PostgreSQL<br/>Conversations, Jobs, Results")]
            S3[("Amazon S3<br/>Saved Reports & Chart Snapshots")]
            Secrets["AWS Secrets Manager<br/>(LLM & Data API Keys)"]
            CW["Amazon CloudWatch<br/>(Structured Logs, Metrics, Alarms)"]
        end
    end

    ALB --> API --> Harness --> Tools
    Tools -->|MCP Protocol| MCP_Mkt
    Tools -->|MCP Protocol| MCP_Res
    Tools -->|Sync Quant Script| Sandbox
    Tools -->|Enqueue Long Job| Redis
    Redis --> Worker
    Worker -->|Heavy Monte Carlo / DCF| Sandbox
    Worker -->|Progress Events| Redis
    Redis -->|SSE Stream| API
    API <--> RDS
    Worker --> RDS
    Worker --> S3
    Secrets -.-> API
    Secrets -.-> Worker
    API --> CW
    Worker --> CW
```

## 2. Conversational Request & Sandbox Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User (Next.js UI)
    participant API as FastAPI + AI Harness
    participant Pol as Permission Policy
    participant MCP as MCP Servers (Market & SEC)
    participant SB as Isolated Python Sandbox
    participant Q as Redis + Celery Worker
    participant DB as PostgreSQL / SQLite

    U->>API: POST /api/chat ("Compare AAPL vs NVDA & DCF what-if")
    API->>DB: Load conversation history & active tickers
    API->>Pol: Authorize planned tool calls & tickers
    Pol-->>API: Approved
    API->>MCP: get_ohlcv / get_financial_statements
    MCP-->>API: Normalized data + source citations + timestamps
    API->>SB: Execute comparison / DCF script (JSON stdin, no network)
    SB-->>API: Computed metrics + sensitivity grid + stdout
    alt Long-Running Deep Analysis Requested
        API->>Q: Enqueue run_deep_analysis_task(job_id)
        Q-->>U: SSE progress events (10% -> 45% -> 75% -> 100%)
        Q->>DB: Persist completed AnalysisResponse
    end
    API->>DB: Save conversation turn & citations
    API-->>U: AnalysisResponse (narrative + charts + tables + citations + assumptions)
```

## 3. Security & Sandbox Isolation Controls
1. **AST Pre-Execution Guard (`services/sandbox/ast_guard.py`):** Blocks dangerous imports (`os`, `subprocess`, `socket`, `sys`, `http`, `requests`), forbidden builtins (`open`, `eval`, `exec`, `__import__`), and dunder attribute tampering before a container ever starts.
2. **Container Runtime Hardening (`services/sandbox/runner.py`):** Launches ephemeral containers with `--network none`, `--read-only`, `--tmpfs /tmp:rw,noexec,nosuid,size=64m`, `--cpus 1.0`, `--memory 512m`, `--pids-limit 64`, `--user 65534:65534`, and strict timeout limits.
3. **AI Harness Policy (`apps/api/app/harness/permissions.py`):** Allowlists tool names, validates ticker format (`^[A-Z]{1,5}(\.[A-Z]{1,2})?$`), and enforces source/assumption metadata on all responses.
