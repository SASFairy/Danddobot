import re
from typing import List, Dict, Set
from src.rag.base import BaseRetriever

class SimpleKeywordRetriever(BaseRetriever):
    """
    순수 파이썬으로 구현된 초경량 키워드 매칭 검색기 (TF-IDF/BM25 경량화 버전).
    문장 내 의미 있는 단어의 중첩 빈도를 계산하여 유사도를 측정합니다.
    """
    def __init__(self):
        self.documents: List[Dict[str, str]] = []
        # 한국어 조사, 어미 등 검색 효율을 위해 필터링할 불용어(Stopwords) 목록
        self.stopwords: Set[str] = {
            "은", "는", "이", "가", "을", "를", "의", "에", "게", "과", "와", "한", "합니다", "있습니다", "으로", "로"
        }

    def _tokenize(self, text: str) -> List[str]:
        """특수문자를 제거하고 단어 단위로 쪼갠 뒤 불용어를 필터링합니다."""
        clean_text = re.sub(r"[^\w\s]", " ", text)
        words = clean_text.lower().split()
        return [w for w in words if w not in self.stopwords and len(w) > 1]

    def index_documents(self, documents: List[Dict[str, str]]):
        self.documents = documents

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        if not self.documents:
            return []

        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return []

        scored_docs = []
        for doc in self.documents:
            doc_tokens = self._tokenize(doc["text"])
            if not doc_tokens:
                continue
            
            # 1. 단어 중첩도 계산 (교집합)
            intersection = query_tokens.intersection(set(doc_tokens))
            score = len(intersection)
            
            # 2. 본문에 중첩된 키워드가 여러 번 등장할 경우 가중 점수 추가
            for token in intersection:
                score += doc_tokens.count(token) * 0.5
                
            if score > 0:
                scored_docs.append((score, doc["text"]))

        # 점수가 높은 순으로 내림차순 정렬 후 최상위 K개 반환
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc[1] for _, doc in scored_docs[:top_k]]
