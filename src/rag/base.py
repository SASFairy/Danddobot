from abc import ABC, abstractmethod
from typing import List, Dict

class BaseRetriever(ABC):
    """
    RAG 검색기의 추상 베이스 클래스.
    이후 어떠한 RAG 알고리즘(벡터 DB, Ollama, 하이브리드)을 도입하더라도 이 규격을 따릅니다.
    """
    @abstractmethod
    def index_documents(self, documents: List[Dict[str, str]]):
        """
        문서 세트를 검색 엔진에 색인(인덱싱)합니다.
        documents 형식: [{'id': 'unique_id', 'text': '문서 본문'}]
        """
        pass

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """
        사용자 질문(query)과 가장 연관성이 높은 문서 본문 top_k 개를 반환합니다.
        """
        pass
