# Architecture and decisions

- `main.py`: REST routes, HTTP validation and status codes.
- `workflows.py`: orchestration of chat, incident, self-healing, and software provisioning.
- `knowledge.py`: approved document ingestion, chunking, embedding, retrieval, source attribution.
- `servicenow.py`: isolated real/mock ServiceNow adapter.
- `storage.py`: local JSON and optional MongoDB Atlas repositories.
- `audit.py`: structured audit events.
- `ai.py`: deterministic offline classification and optional Hugging Face generation.

The prototype is intentionally easy to run locally. Offline embeddings are deterministic feature hashing and are not equivalent to transformer embeddings. The mock ServiceNow adapter does not create records in a real instance. Production use would require identity/RBAC, stronger storage concurrency, monitoring, secrets management, and instance-specific catalog/approval integration.
