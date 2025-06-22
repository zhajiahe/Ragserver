# RagBackend
[中文](./README_zh.md)

RagBackend is a RAG (Retrieval-Augmented Generation) service built with FastAPI that provides a REST API for managing collections and documents, using PostgreSQL with pgvector for vector storage.

## TODO

### Phase 1: Infrastructure ✅
- [x] Implement configuration management (`config.py`)
- [x] Implement database connection and model definitions
- [x] Implement basic FastAPI application and server setup (`server.py`)
- [x] Implement health check API

### Phase 2: Core Features
- [x] Implement collection management API and database operations
- [ ] Implement file upload API with MinIO integration
- [ ] Implement document processing service (parsing, chunking, vectorization)
- [ ] Implement vector search functionality

### Phase 3: Enhancement
- [ ] Error handling and logging
- [ ] Asynchronous task processing for document processing
- [ ] API documentation and testing
- [ ] Performance optimization

### Supported Features
- [x] Multiple document formats (TXT, PDF, MD, DOCX, etc.)
- [x] Multiple embedding models:
  - [x] Ollama (local deployment)
  - [x] OpenAI API
  - [x] SiliconFlow (free API)
- [x] Dynamic vector table creation per collection
- [ ] Asynchronous document processing
- [x] Container deployment with Docker Compose

## Features
- FastAPI-based REST API
- Document storage and vector embeddings using PostgreSQL and pgvector
- Docker support for easy deployment
- File storage integration with MinIO
- Multi-format document processing (TXT, PDF, MD, DOCX, etc.)
- Vector similarity semantic search
- Real-time document indexing and retrieval
- Multiple embedding options: Ollama (local), SiliconFlow (free API), OpenAI

## Quick Start

### Requirements

- Docker and Docker Compose
- Python 3.12 or higher

### Run with Docker

1. Clone the repository:
   ```bash
   # Replace with your repository URL
   git clone https://github.com/zhajiahe/RagBackend.git
   cd RagBackend
   ```

2. Start services:
   ```bash
   docker-compose up -d
   ```

   This will:
   - Start a PostgreSQL database with pgvector extension
   - Build and start the RagBackend API service

3. Access the API:
   - API Documentation: http://localhost:8080/docs
   - Health Check: http://localhost:8080/health
   - MinIO Management Console (file management): http://localhost:9001 (minioadmin/minioadmin123)

### Development Mode

To run the service in development mode with live reloading:

```bash
docker-compose up
```

## Usage
Create Collection (auto-create vectorstore table) -> Upload Files (store in MinIO, parse, chunk, store in vectorstore) -> Vector Query

## API Endpoints

### Collections
- `POST /collections` - Create a new collection
- `GET /collections` - List all collections
- `GET /collections/{id}` - Get collection details
- `DELETE /collections/{id}` - Delete a collection

### Files
- `POST /collections/{id}/files` - Upload files to a collection
- `GET /collections/{id}/files` - List files in a collection
- `DELETE /files/{id}` - Delete a file

### Search
- `POST /collections/{id}/search` - Perform vector similarity search

### System
- `GET /health` - Health check endpoint

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Embedding Model Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
SILICONFLOW_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=postgres

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=ragbackend-documents
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   PostgreSQL    │    │     MinIO       │
│                 │    │   + pgvector    │    │  File Storage   │
│  - REST API     │◄──►│  - Collections  │    │  - Documents    │
│  - Document     │    │  - Files        │    │  - Metadata     │
│    Processing   │    │  - Vectors      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
