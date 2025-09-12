# debug.py
from qdrant_client import QdrantClient

COLLECTION_NAME = "laws"

def main():
    qdrant = QdrantClient(host="localhost", port=6333)
    info = qdrant.get_collection(COLLECTION_NAME)

    print("📂 컬렉션 상태 확인")
    print(f" - Status: {info.status}")  # RED / YELLOW / GREEN
    print(f" - Vectors: {info.vectors_count}")
    print(f" - Points: {info.points_count}")
    print(f" - Segments: {info.segments_count}")
    print(f" - Vector size: {info.config.params.vectors.size}")
    print(f" - Distance: {info.config.params.vectors.distance}")

    if info.status.value.lower() == "red":
        print("\n⚠️ 상태가 RED → 뭔가 잘못 올라간 거임 (벡터 크기 불일치나 내부 에러).")
    elif info.status.value.lower() == "green":
        print("\n✅ 상태가 GREEN → 정상적으로 동작 중.")
    else:
        print("\n⏳ 인덱싱 중이거나 최적화 대기 상태일 수 있음.")

if __name__ == "__main__":
    main()
