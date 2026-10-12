# Integration notes

OpenAPI: `/docs`. Default mock ServiceNow records have `MOCK-` references and are not real ServiceNow records. The basic `sc_request` Table API is a prototype equivalent; real catalog fulfillment usually requires catalog-specific APIs and configured catalog item IDs. Validate ACLs, fields, assignment groups, and instance policies.

Offline classification is rule-based. Offline embeddings use feature hashing. Similarity scores are not calibrated confidence probabilities. The displayed classification confidence is a heuristic, not a statistical guarantee.
