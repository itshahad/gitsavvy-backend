# GitSavvy

GitSavvy is a backend system for analyzing GitHub repositories, generating structured documentation, and enabling intelligent code-aware conversations through a chatbot. It combines static analysis, embeddings, and large language models to provide deep insights into software projects.

---

## Overview

GitSavvy is built around three core capabilities:

- **GitHub Integration**: Fetch and process repository data including files, issues, and metadata.
- **Documentation Generation**: Automatically generate structured documentation using a bottom-up approach.
- **Chatbot Interaction**: Allow users to query repositories using natural language with context-aware responses.

---

## Features

- GitHub repository ingestion
- File filtering and processing
- Text-based and AST-based code chunking
- Semantic embeddings generation
- Multi-level documentation:
  - Function-level documentation
  - Class-level summaries
  - File-level summaries
- Context-aware chatbot using vector search
- Issue and comment synchronization
- Real-time response streaming

---

## System Architecture

The system is composed of the following modules:

### Repository Service
Handles repository ingestion, file selection, and integration with GitHub or uploaded archives.

### Indexer
Processes files into chunks:
- Text chunking for general content
- AST-based chunking for code structure

### Embedding Service
Generates vector embeddings for each chunk to enable semantic search.

### Documentation Generator
Uses a bottom-up approach:
- Generates detailed documentation for functions
- Produces summaries for higher-level components
- Aggregates results into class and file documentation

### Chatbot Service
- Retrieves relevant chunks using vector similarity (L2 distance)
- Builds contextual prompts
- Streams responses from the language model

---

## Technologies

- **Backend**: Python, FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Embeddings Model**: BAAI/bge-code-v1
- **LLM**: Qwen/Qwen2.5-Coder-3B-Instruct
- **Vector Search**: L2 distance
- **Caching / Messaging**: Redis
- **Containerization**: Docker, Docker Compose
