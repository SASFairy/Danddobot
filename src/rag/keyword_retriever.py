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

    def _longest_common_substring_len(self, s1: str, s2: str) -> int:
        """두 문자열 간 가장 긴 공통 연속 부분 문자열(Longest Common Substring)의 길이를 계산합니다."""
        m = [[0] * (len(s2) + 1) for _ in range(len(s1) + 1)]
        longest = 0
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                if s1[i-1] == s2[j-1]:
                    m[i][j] = m[i-1][j-1] + 1
                    longest = max(longest, m[i][j])
                else:
                    m[i][j] = 0
        return longest

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
            
            # 1. 한국어 교착어 및 성씨 결합(예: 김동규 <-> 동규)을 고려한 최장 공통 부분 문자열(LCS) 어근 분석
            # (두 단어 간 연속 공통 글자가 2글자 이상이면 어근이 동일한 매칭으로 인정하여 강건성을 확보합니다)
            for q_token in query_tokens:
                for d_token in doc_tokens:
                    # 완전 일치하는 경우 최고 우선 점수 부여
                    if q_token == d_token:
                        score += 2.0
                        matched_tokens.add(q_token)
                    else:
                        lcs_len = self._longest_common_substring_len(q_token, d_token)
                        if lcs_len >= 2:
                            score += 1.0
                            matched_tokens.add(q_token)
            
            # 2. 매칭된 키워드가 문서 내에 중복해서 등장할 경우 추가 빈도 가중치 부여
            for q_token in matched_tokens:
                for d_token in doc_tokens:
                    lcs_len = self._longest_common_substring_len(q_token, d_token)
                    if q_token == d_token or lcs_len >= 2:
                        score += 0.5
                        
            if score > 0:
                scored_docs.append((score, doc["text"]))

        # 점수가 높은 순으로 내림차순 정렬 후 최상위 K개 반환
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored_docs[:top_k]]
