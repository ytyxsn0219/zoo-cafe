# Multi-Model PRD Generation System

A collaborative PRD (Product Requirements Document) generation system using multiple AI models with discussion-based collaboration.

## Features

- **Multi-Model Collaboration**: Multiple AI agents discuss and collaborate to generate PRD
- **Moderator-Guided**: Built-in moderator guides the discussion through 4 stages
- **Configurable**: Easy to configure models, agents, and discussion parameters
- **Memory**: Short-term (Redis) and long-term (ChromaDB) memory for sessions and history
- **API**: FastAPI-based REST API with SSE support for real-time updates
- **Export**: Support for Markdown and PDF output

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  UI Layer                        │
│         Streamlit / Next.js / FastAPI SSE        │
├──────────────────────────────────────────────────┤
│               Orchestration Layer                │
│       LangGraph  ─  Discussion Engine            │
├──────────────────────────────────────────────────┤
│                Agent Layer                        │
│  Universal Agents │  Moderator Agent             │
├──────────────────────────────────────────────────┤
│             Infrastructure Layer                │
│  Model Gateway │ Redis │ ChromaDB                │
└──────────────────────────────────────────────────┘
```

## Stages

1. **Elicitation**: Clarify requirements with key questions
2. **Design**: Collaboratively design feature list
3. **Writing**: Write PRD document sections
4. **Finalizing**: Generate final formatted PRD

## Quick Start

### Prerequisites

- Python 3.11+
- Redis
- ChromaDB (optional)
- API keys for LLM providers

### Installation

```bash
# Clone the repository
cd multi-model-prd

# Install dependencies
pip install -e .

# Copy environment file
cp .env.example .env

# Edit .env with your API keys
```

### Running

#### Local Development

```bash
# Start Redis (optional, for session storage)
docker run -d -p 6379:6379 redis:7-alpine

# Start the API server
uvicorn src.main:app --reload
```

#### Docker Compose

```bash
docker-compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/sessions` | Create new PRD session |
| GET | `/api/v1/sessions/{id}` | Get session status |
| POST | `/api/v1/sessions/{id}/messages` | Send message |
| GET | `/api/v1/sessions/{id}/output` | Get PRD output |
| GET | `/api/v1/health` | Health check |

## Configuration

### Models (`config/models.yaml`)

Configure available LLM models:

```yaml
models:
  - name: "gpt4o_model"
    provider: "openai"
    model: "gpt-4o"
    config:
      temperature: 0.7
      max_tokens: 4096
```

### Agents (`config/agents.yaml`)

Configure discussion agents:

```yaml
agents:
  - name: "agent_01"
    model_ref: "gpt4o_model"
    display_name: "Agent 01"
```

### Settings (`config/settings.yaml`)

Configure discussion parameters:

```yaml
discussion:
  max_turns_per_stage:
    elicitation: 5
    design: 10
    writing: 10
  consensus_threshold: 0.8
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
ruff check src/
ruff format src/
```

## License

MIT
