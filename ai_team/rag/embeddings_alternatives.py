"""
RAG Embeddings 대안

OpenAI embeddings 대신 사용 가능한 옵션들
"""

# 옵션 1: Voyage AI Embeddings (추천)
# - 고품질, 저렴
# - API: https://www.voyageai.com/
def use_voyage_embeddings():
    from langchain_community.embeddings import VoyageEmbeddings

    embeddings = VoyageEmbeddings(
        voyage_api_key="your-voyage-api-key",
        model="voyage-2"
    )
    return embeddings


# 옵션 2: HuggingFace Embeddings (무료, 로컬)
# - 완전 무료
# - GPU 없어도 작동 (느림)
def use_huggingface_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return embeddings


# 옵션 3: Cohere Embeddings
# - 빠르고 정확
def use_cohere_embeddings():
    from langchain_community.embeddings import CohereEmbeddings

    embeddings = CohereEmbeddings(
        cohere_api_key="your-cohere-api-key",
        model="embed-english-v3.0"
    )
    return embeddings


# 옵션 4: Claude 없이 간단한 키워드 검색
# - 임베딩 없이 BM25 사용
def use_bm25_retriever():
    from langchain.retrievers import BM25Retriever
    from langchain.schema import Document

    docs = [
        Document(page_content="뉴스 내용 1"),
        Document(page_content="뉴스 내용 2"),
    ]

    retriever = BM25Retriever.from_documents(docs)
    return retriever
