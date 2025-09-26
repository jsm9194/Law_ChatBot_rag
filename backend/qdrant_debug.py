from qdrant_client import QdrantClient
qdrant = QdrantClient(url="http://localhost:6333")
qdrant.recover_collection("laws")   # REST에서 동작하면 복구 시도
