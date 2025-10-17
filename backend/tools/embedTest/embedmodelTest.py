import json
from tqdm import tqdm
from qdrant_client import QdrantClient
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from FlagEmbedding import BGEM3FlagModel
from dotenv import load_dotenv
import os
import matplotlib.pyplot as plt

import matplotlib
matplotlib.rc('font', family='Malgun Gothic')  # Windows
matplotlib.rcParams['axes.unicode_minus'] = False

# ============================
# 환경 설정
# ============================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

QDRANT_HOST = "localhost"
PORT = 6333

# ✅ 각 컬렉션명
COLLECTION_OPENAI = "laws"              # text-embedding-3-large
COLLECTION_SBERT = "laws_sbert"         # woong0322/ko-legal-sbert-finetuned
COLLECTION_BGE = "laws_bge_m3"          # BAAI/bge-m3
COLLECTION_BGE_KO = "laws_bge_ko_m3"    # upskyy/bge-m3-korean 등

TOP_K = 5

# ============================
# 모델 로드
# ============================
print("🧠 모델 로딩 중...")
sbert = SentenceTransformer("woong0322/ko-legal-sbert-finetuned")
bge = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
bge_ko = BGEM3FlagModel("upskyy/bge-m3-korean", use_fp16=True)
print("✅ 모든 모델 로드 완료")

qdrant = QdrantClient(host=QDRANT_HOST, port=PORT)

# ============================
# 평가 데이터 로드
# ============================
with open("test_queries.json", "r", encoding="utf-8") as f:
    test_queries = json.load(f)

# ============================
# 유틸 함수
# ============================
def get_openai_embedding(text):
    return client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    ).data[0].embedding

def get_sbert_embedding(text):
    return sbert.encode(text, normalize_embeddings=True).tolist()

def get_bge_embedding(text):
    return bge.encode([text])["dense_vecs"][0].tolist()

def get_bge_ko_embedding(text):
    return bge_ko.encode([text])["dense_vecs"][0].tolist()

def recall_at_k(results, answers, k=TOP_K):
    """정답(법령명 + 제{조문번호}조) 비교"""
    for p in results[:k]:
        law = str(p.payload.get("law_name", "")).strip()
        num = str(p.payload.get("article_number", "")).strip()

        # 이미 "제1조" 형태로 들어가 있는 경우 중복 방지
        if num.startswith("제"):
            formatted = f"{law} {num}"
        else:
            formatted = f"{law} 제{num}조"

        if any(ans.strip() == formatted for ans in answers):
            return 1
    return 0


def reciprocal_rank(results, answers):
    for i, p in enumerate(results, start=1):
        law = str(p.payload.get("law_name", "")).strip()
        num = str(p.payload.get("article_number", "")).strip()

        if num.startswith("제"):
            formatted = f"{law} {num}"
        else:
            formatted = f"{law} 제{num}조"

        if any(ans.strip() == formatted for ans in answers):
            return 1 / i
    return 0

def avg(lst):
    return round(sum(lst) / len(lst), 3) if lst else 0

# ============================
# 평가 루프
# ============================
scores = {
    "openai": {"recall": [], "mrr": []},
    "sbert": {"recall": [], "mrr": []},
    "bge": {"recall": [], "mrr": []},
    "bge_ko": {"recall": [], "mrr": []},
}

for item in tqdm(test_queries, desc="🔎 평가 중"):
    query = item["query"]
    answers = item["answer_ids"]

    # --- OpenAI ---
    emb = get_openai_embedding(query)
    res = qdrant.query_points(collection_name=COLLECTION_OPENAI, query=emb, limit=TOP_K).points

    # 🔍 디버깅용 출력
    print("\n==============================")
    print(f"[Query] {query}")
    print(f"[정답] {answers}")
    for p in res[:3]:
        law = str(p.payload.get("law_name", ""))
        num = str(p.payload.get("article_number", ""))
        print(f"[검색결과] {law} 제{num}조")
    print("==============================\n")


    scores["openai"]["recall"].append(recall_at_k(res, answers))
    scores["openai"]["mrr"].append(reciprocal_rank(res, answers))

    # --- SBERT ---
    emb = get_sbert_embedding(query)
    res = qdrant.query_points(collection_name=COLLECTION_SBERT, query=emb, limit=TOP_K).points
    scores["sbert"]["recall"].append(recall_at_k(res, answers))
    scores["sbert"]["mrr"].append(reciprocal_rank(res, answers))

    # --- BGE-M3 ---
    emb = get_bge_embedding(query)
    res = qdrant.query_points(collection_name=COLLECTION_BGE, query=emb, limit=TOP_K).points
    scores["bge"]["recall"].append(recall_at_k(res, answers))
    scores["bge"]["mrr"].append(reciprocal_rank(res, answers))

    # --- BGE-M3 Korean ---
    emb = get_bge_ko_embedding(query)
    res = qdrant.query_points(collection_name=COLLECTION_BGE_KO, query=emb, limit=TOP_K).points
    scores["bge_ko"]["recall"].append(recall_at_k(res, answers))
    scores["bge_ko"]["mrr"].append(reciprocal_rank(res, answers))

# ============================
# 결과 출력
# ============================
print("\n=== 📊 평가 결과 요약 ===")
print(f"총 {len(test_queries)}개 질문 평가\n")

for col in [COLLECTION_OPENAI, COLLECTION_SBERT, COLLECTION_BGE, COLLECTION_BGE_KO]:
    print(col, qdrant.count(collection_name=col))

for name, data in scores.items():
    print(f"🔹 {name.upper()}")
    print(f"Recall@{TOP_K}: {avg(data['recall'])}")
    print(f"MRR: {avg(data['mrr'])}\n")

# ============================
# 📈 시각화
# ============================
models = ["OpenAI", "SBERT", "BGE-M3", "BGE-KO-M3"]
recalls = [avg(scores[k]["recall"]) for k in ["openai", "sbert", "bge", "bge_ko"]]
mrrs = [avg(scores[k]["mrr"]) for k in ["openai", "sbert", "bge", "bge_ko"]]

for item in test_queries[:3]:
    query = item["query"]
    emb = get_openai_embedding(query)
    res = qdrant.query_points(collection_name=COLLECTION_OPENAI, query=emb, limit=3).points
    print(f"\n[Query] {query}")
    for p in res:
        print(f"→ {p.payload.get('law_name')} {p.payload.get('article_number')}")

x = range(len(models))
plt.figure(figsize=(8,5))
plt.bar(x, recalls, width=0.4, label=f"Recall@{TOP_K}", alpha=0.7)
plt.bar([i+0.4 for i in x], mrrs, width=0.4, label="MRR", alpha=0.7)
plt.xticks([i+0.2 for i in x], models)
plt.ylabel("Score")
plt.title("모델별 검색 성능 비교 (Recall & MRR)")
plt.legend()
plt.tight_layout()
plt.show()
