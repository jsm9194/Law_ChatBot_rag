from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

client = QdrantClient("http://localhost:6333")

# 이미 존재하는지 확인
if not client.collection_exists("laws"):
    client.create_collection(
        collection_name="laws",
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )
    print("✅ 새 컬렉션 생성 완료")
else:
    print("ℹ️ 이미 'laws' 컬렉션이 존재합니다")

print("📂 현재 컬렉션:", client.get_collections())
