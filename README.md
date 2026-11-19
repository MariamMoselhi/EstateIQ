# EstateIQ

EstateIQ is an AI-powered real-estate assistant for questions about:

- DarGlobal luxury property projects
- Wasalt Saudi property listings

The application combines FastAPI, hybrid BM25/dense retrieval, and OpenRouter language models. Answers are grounded in the included public source data and include links back to the original pages.

## Features

- Browser-based chat interface
- Grounded answers with inline citations and source links
- Hybrid retrieval using BM25 and dense embeddings
- Conversation history with follow-up-query support
- Per-IP chat rate limiting
- Automatic fallback across configured OpenRouter models
- English and Arabic assistant replies
- Health endpoint for checking index and model state

## Technology

- FastAPI and Uvicorn
- Pydantic settings
- Hybrid BM25 and vector retrieval
- ONNX Runtime with the `all-MiniLM-L6-v2` embedding model
- OpenRouter chat completions API
- Static HTML, CSS, and JavaScript frontend

## Project Structure

```text
EstateIQ/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── chatbot.py           # Retrieval and OpenRouter integration
│   ├── config.py            # Environment-backed settings
│   ├── rag/                 # Chunking, embeddings, and retrieval
│   ├── scraping/            # Source collection utilities
│   └── static/index.html    # Chat web interface
├── data/
│   ├── processed/           # Source JSON and retrieval chunks
│   └── index/               # Generated dense embedding matrix
├── Dockerfile
├── requirements.txt
├── requirements-prod.txt
└── .env.example
```

## Requirements

- Python 3.12+
- An OpenRouter API key
- Internet access to download the embedding model and call OpenRouter

## Local Setup

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Set your API key in `.env`:

```dotenv
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=openrouter/free
```

The default model chain in `app/config.py` starts with `dots-studio/dots-3-note-preview:free`, then tries the other configured free models.

## Run the Application

Start the FastAPI server:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 10000 --reload
```

Open <http://localhost:10000>.

## Build the Retrieval Index

The repository includes processed source data and chunks. To regenerate chunks from the processed DarGlobal and Wasalt JSON files:

```powershell
python -m app.rag.preprocess
```

To generate dense embeddings:

```powershell
python -m app.rag.build_index
```

The first embedding build downloads the ONNX model to the user cache. A dense index is optional; BM25 retrieval remains available if `data/index/embeddings.npy` is absent.

To refresh DarGlobal source data:

```powershell
python -m app.scraping.darglobal
```

Then rerun preprocessing and index generation.

## Docker

Build the image:

```powershell
docker build -t estateiq .
```

Run it with your API key:

```powershell
docker run --rm -p 7860:7860 -e PORT=7860 -e OPENROUTER_API_KEY="your_api_key_here" estateiq
```

Open <http://localhost:7860>.

## API

### `GET /`

Returns the chat web interface.

### `GET /health`

Returns application status, chunk count, dense retrieval availability, and configured model chain.

Example:

```json
{
  "status": "healthy",
  "app": "EstateIQ",
  "version": "1.0.0",
  "chunks": 495,
  "dense_retrieval": true,
  "models": ["dots-studio/dots-3-note-preview:free"]
}
```

### `POST /chat`

Accepts a message and optional conversation history.

```json
{
  "message": "Show 3-bedroom apartments for sale in Jeddah",
  "history": []
}
```

Response:

```json
{
  "answer": "The assistant's grounded response.",
  "sources": [
    {
      "title": "Source title",
      "url": "https://example.com/source",
      "source": "Wasalt"
    }
  ]
}
```

The chat endpoint allows 10 requests per minute per client IP by default. Configure this with `RATE_LIMIT_PER_MIN`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Empty | OpenRouter API key |
| `OPENROUTER_MODEL` | `dots-studio/dots-3-note-preview:free` | Preferred model |
| `OPENROUTER_MODELS` | Comma-separated fallback chain | Additional models tried in order |
| `PORT` | `10000` | Local server port |
| `TOP_K` | `5` | Number of retrieval results sent to the model |
| `MAX_HISTORY_TURNS` | `4` | Maximum recent conversation turns used |
| `RATE_LIMIT_PER_MIN` | `10` | Chat requests allowed per minute per IP |
| `CHUNKS_PATH` | `data/processed/chunks.jsonl` | Retrieval chunk file |
| `EMBEDDINGS_PATH` | `data/index/embeddings.npy` | Dense embedding file |

## Data and Accuracy

EstateIQ answers only from retrieved source excerpts. It does not replace live real-estate searches or agent advice.

- DarGlobal content comes from public DarGlobal pages.
- Wasalt listings are a small sample collected from public pages and may be out of date.
- Prices and availability can change; users should verify them on the live Wasalt listing.
- The assistant avoids outside knowledge and prompts users to check the official sources when an answer is not available in the index.