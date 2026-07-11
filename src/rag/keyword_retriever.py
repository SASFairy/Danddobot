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
            
            score = 0.0
            matched_tokens = set()
            
            # 1. 한국어 교착어(조사 결합)를 고려한 형태소 부분 일치 분석 ('동규에'와 '동규' 매칭)
            for q_token in query_tokens:
                for d_token in doc_tokens:
                    # 완전 일치하는 경우 최고 우선 점수 부여
                    if q_token == d_token:
                        score += 2.0
                        matched_tokens.add(q_token)
                    # 조사/어미가 달라지는 부분 일치 처리 (최소 2글자 이상 겹칠 때만 매칭하여 조사 오동작 방지)
                    elif q_token in d_token or d_token in q_token:
                        overlap_len = min(len(q_token), len(d_token))
                        if overlap_len >= 2:
                            score += 1.0
                            matched_tokens.add(q_token)
            
            # 2. 매칭된 키워드가 문서 내에 중복해서 등장할 경우 추가 빈도 가중치 부여
            for q_token in matched_tokens:
                for d_token in doc_tokens:
                    if q_token == d_token or q_token in d_token or d_token in q_token:
                        score += 0.5
                        
            if score > 0:
                scored_docs.append((score, doc["text"]))

        # 점수가 높은 순으로 내림차순 정렬 후 최상위 K개 반환
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc[1] for _, doc in scored_docs[:top_k]]
