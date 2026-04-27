# Medium RAG Chatbot

A serverless chatbot embedded in an AI/ML portfolio website that answers questions about Medium articles using Retrieval Augmented Generation (RAG). The system ingests articles automatically from Medium RSS feeds, builds a searchable vector knowledge base in S3, and exposes a chat interface powered by Amazon Bedrock.

---

## Architecture Overview

The system is split into three decoupled pipelines: ingestion, indexing, and chat.

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION  (runs every 6 hours via EventBridge)                    │
│                                                                     │
│  Medium RSS Feeds (110 feeds)                                       │
│    └─→ Ingestion Lambda                                             │
│           └─→ Deduplicates articles by ID                           │
│           └─→ Appends new / updates existing                        │
│           └─→ S3: medium-rss-data/medium_articles_master.json       │
└─────────────────────────────────────────────────────────────────────┘
                              │ S3 ObjectCreated event
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  INDEXING  (triggered automatically on each ingestion)              │
│                                                                     │
│  Indexer Lambda (2GB RAM, 15-min timeout)                           │
│    └─→ Reads articles from S3                                       │
│    └─→ MD5 hash per article → skips unchanged articles              │
│    └─→ Sends new/changed article text to Bedrock Titan Embeddings   │
│    └─→ Stores updated vector index                                  │
│           └─→ S3: embeddings/article_embeddings.pkl                 │
└─────────────────────────────────────────────────────────────────────┘
                              │ user submits query
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CHAT  (on demand)                                                  │
│                                                                     │
│  Portfolio Website (React/Vite, hosted on Vercel)                   │
│    └─→ POST /chat  →  API Gateway HTTP API                          │
│           └─→ Chat Lambda (1GB RAM, 60-sec timeout)                 │
│                  └─→ Embeds query via Bedrock Titan                 │
│                  └─→ Cosine similarity search over cached vectors   │
│                  └─→ Retrieves top-5 matching articles              │
│                  └─→ Constructs prompt + context                    │
│                  └─→ Calls Claude 3 Haiku via Bedrock               │
│                  └─→ Saves interaction to DynamoDB (30-day TTL)     │
│                  └─→ Returns response + source citations            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Knowledge Base (S3)

The knowledge base lives entirely in S3 and is organized into two layers.

### Article Store

**Path:** `medium-rss-data/medium_articles_master.json`

A single, incrementally updated JSON file. Each ingestion run appends new articles and updates the `last_seen` timestamp on existing ones — no duplicates, no new files per run.

```json
{
  "metadata": {
    "last_updated": "2026-04-26T15:30:00",
    "total_articles": 3000
  },
  "articles": [
    {
      "id": "article-unique-id",
      "title": "Article Title",
      "link": "https://medium.com/...",
      "author": "Author Name",
      "published": "2026-01-15T09:00:00",
      "summary": "Article summary...",
      "tags": ["python", "machine-learning"],
      "source_feed": "https://medium.com/feed/tag/python",
      "first_seen": "2026-01-15T10:00:00",
      "last_seen": "2026-04-26T15:30:00"
    }
  ]
}
```

The ingestion Lambda pulls from 110 Medium RSS feeds across 84 topics (AI, Python, JavaScript, cloud, databases, etc.) and 26 publications (Towards Data Science, Better Programming, etc.). Running every 6 hours, the knowledge base grows to roughly 3,000–5,000 articles over the first month.

### Vector Index

**Path:** `embeddings/article_embeddings.pkl`

Each article is embedded as a 1536-dimension vector using Amazon Titan Embeddings (V1). The indexer converts each article into a searchable text string:

```
Title: {title}  Author: {author}  Summary: {summary}  Tags: {tags}
```

The vector index is stored as a serialized dictionary containing:
- `embeddings` — list of float vectors, one per article
- `article_ids` — parallel list of article IDs
- `article_hashes` — MD5 hash per article for change detection

The indexer only calls Bedrock for articles that are new or whose content has changed, keeping embedding costs near zero on subsequent runs.

---

## Website Integration

The chatbot is embedded directly inside the portfolio as a React route — no iframe, no separate deployment.

**Route:** `/projects/chat` in the Vite/React portfolio

**Component:** `src/pages/ChatBot.jsx`

The component communicates with the API Gateway over HTTPS. On page load it fetches the session's previous messages. Each user query is sent as:

```json
{
  "action": "chat",
  "sessionId": "session-<timestamp>",
  "query": "What are the latest AI trends?",
  "includeHistory": true
}
```

The Lambda returns a Markdown-formatted response alongside source citations (title, author, publication date, link, and cosine similarity score). The frontend renders these using `react-markdown` with syntax highlighting via `react-syntax-highlighter`.

Session IDs are generated client-side (`session-<Date.now()>`) and scoped to the browser tab, so each visitor gets an independent conversation. Chat history is loaded from DynamoDB on mount to restore context within a session.

---

## Infrastructure

Deployed via a single CloudFormation template (`rag-cloudformation.yaml`).

| Resource | Purpose |
|----------|---------|
| S3 (data bucket) | Stores articles JSON and embeddings |
| Lambda — Chat Handler | Processes queries, calls Bedrock, returns responses |
| Lambda — Indexer | Generates and updates the vector index |
| API Gateway HTTP API | `POST /chat` endpoint consumed by the portfolio frontend |
| DynamoDB — ChatHistory | Persists conversations (partition: `sessionId`, sort: `timestamp`) |
| IAM Roles | Least-privilege roles scoped to only the required S3 keys, DynamoDB table, and Bedrock models |

The CloudFormation stack wires the S3 bucket notification directly to the Indexer Lambda so the index stays in sync automatically whenever ingestion runs — no polling, no cron needed on the indexing side.

---

## Cost Optimization

The entire stack is optimized to run under **$3–5/month** for portfolio-scale traffic.

**Claude 3 Haiku instead of Sonnet/Opus**
Haiku is the most cost-efficient Claude model on Bedrock. At ~100 queries/month, the LLM cost is under $0.50.

**Lambda container reuse (in-memory caching)**
The embeddings and articles JSON are loaded from S3 once per Lambda container lifecycle and cached in module-level globals. Subsequent invocations on the same warm container skip the S3 reads entirely, cutting both latency and cost on back-to-back queries.

**Incremental indexing**
The indexer hashes each article's text before calling Bedrock. On a typical run where 90%+ of articles are unchanged, only new and updated articles generate Bedrock API calls. This keeps embedding costs near zero after the initial index build.

**In-memory cosine similarity instead of a managed vector database**
OpenSearch Serverless has a $24/month floor. For a knowledge base under 100k articles, cosine similarity over NumPy arrays in Lambda memory is fast enough and costs nothing beyond the Lambda invocation itself.

**DynamoDB on-demand with TTL**
No provisioned capacity means zero cost when idle. The 30-day TTL on chat history automatically purges old sessions, keeping storage costs flat.

**API Gateway HTTP API**
The HTTP API (v2) is ~70% cheaper per request than the REST API (v1) with equivalent functionality for this use case.

**CloudFront PriceClass_100**
Restricts edge distribution to North America and Europe — the lowest-cost tier — which covers the expected audience without paying for global edge locations.

### Estimated Monthly Cost

| Service | Cost |
|---------|------|
| S3 storage (~5GB) | $0.12 |
| CloudFront (10GB transfer) | $0.85 |
| API Gateway (1,000 requests) | $0.00 |
| Lambda (1,000 invocations, 30s avg, 1GB) | $0.20 |
| Bedrock — Claude 3 Haiku (100 queries) | $0.50 |
| Bedrock — Titan Embeddings (indexing) | $0.01 |
| DynamoDB on-demand | $0.25 |
| **Total** | **~$2–3/month** |

---

## Deployment

**Prerequisites:** AWS CLI configured, Bedrock model access enabled for `anthropic.claude-3-haiku-20240307-v1:0` and `amazon.titan-embed-text-v1`.

```bash
# 1. Deploy infrastructure
aws cloudformation create-stack \
  --stack-name medium-rag-chatbot \
  --template-body file://rag-cloudformation.yaml \
  --parameters \
    ParameterKey=S3BucketName,ParameterValue=your-bucket-name \
  --capabilities CAPABILITY_IAM

aws cloudformation wait stack-create-complete --stack-name medium-rag-chatbot

# 2. Build and upload the chat Lambda
python build_lambda.py
aws lambda update-function-code \
  --function-name MediumRAG-ChatHandler \
  --zip-file fileb://lambda_deployment.zip

# 3. Upload the indexer Lambda
aws lambda update-function-code \
  --function-name MediumRAG-Indexer \
  --zip-file fileb://indexer.zip

# 4. Set the API endpoint in the portfolio
# Add VITE_API_ENDPOINT=<ApiEndpoint from stack outputs> to .env.production
```

**Get the API endpoint:**
```bash
aws cloudformation describe-stacks \
  --stack-name medium-rag-chatbot \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text
```

---

## Related Repositories

- **aws-medium-ingestion** — EventBridge-scheduled Lambda that populates the article knowledge base in S3
- **ai-ml-portfolio** — The React/Vite portfolio website that embeds this chatbot at `/projects/chat`
