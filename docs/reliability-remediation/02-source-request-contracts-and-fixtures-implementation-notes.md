# Plan 02 implementation notes

## Raw payload retention decision

Raw response payload retention is deferred. The typed collection result retains response metadata and normalized source documents, while `persist_raw_artifact` continues to receive `payload=None`. This avoids claiming immutable payload evidence until a bounded storage locator, encryption policy, size budget, and retention lifecycle are implemented. The content hash, response metadata, source URL, retrieval timestamp, and processing outcome remain persisted for provenance and deduplication.

A future retention change must add an explicit storage policy and integration coverage before enabling payload writes.
