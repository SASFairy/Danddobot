import os
import re
import logging
from typing import List, Dict, Optional
from src.rag.base import BaseRetriever
from src.rag.keyword_retriever import SimpleKeywordRetriever

logger = logging.getLogger("danddobot.rag_manager")

class RAGManager:
    """
    RAG 라이프사이클 관리자. 
    지식 폴더 내의 .txt 파일들을 읽어 적정 크기(chunk_size)로 안전하게 분할하고, 등록된 Retriever에 색인합니다.
    """
    def __init__(self, is_enabled: bool, knowledge_dir: str, top_k: int = 3, max_chars: int = 1500, chunk_size: int = 500, retriever: Optional[BaseRetriever] = None):
        self.is_enabled = is_enabled
        self.knowledge_dir = knowledge_dir
        self.top_k = top_k
        self.max_chars = max_chars
        self.chunk_size = chunk_size
        # 주입받은 검색기가 없다면 방안 B(SimpleKeywordRetriever)를 기본 장착
        self.retriever: BaseRetriever = retriever or SimpleKeywordRetriever()
        
        if self.is_enabled:
            self.reload_knowledge()

    def _split_text(self, text: str) -> List[str]:
        """
        문단을 설정된 chunk_size 이하의 조각들로 안전하게 분할합니다.
        가급적 문장 종결 기호(.!? 뒤 공백) 단위로 끊어 문맥상 올바른 문장 형태를 보존합니다.
        """
        if len(text) <= self.chunk_size:
            return [text]

        # 문장 종결 부호를 기준으로 분할 (후방 탐색으로 문장 부호 자체는 보존)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 만약 문장 단일 길이가 청크 제한 크기보다 더 큰 예외적인 경우 (글자 수 강제 분할)
            if len(sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                for i in range(0, len(sentence), self.chunk_size):
                    chunks.append(sentence[i:i + self.chunk_size])
                continue

            # 현재 빌드 중인 청크에 이 문장을 합쳤을 때 한도를 넘어가는 경우
            if len(current_chunk) + len(sentence) + (1 if current_chunk else 0) > self.chunk_size:
                chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def reload_knowledge(self):
        """지식 폴더 내의 모든 .txt 파일을 읽어 청킹 후 인덱싱을 수행합니다."""
        if not os.path.exists(self.knowledge_dir):
            try:
                os.makedirs(self.knowledge_dir, exist_ok=True)
                logger.info(f"Created empty knowledge directory at {self.knowledge_dir}")
            except Exception as e:
                logger.error(f"Failed to create knowledge directory at {self.knowledge_dir}: {e}")
            return

        documents: List[Dict[str, str]] = []
        doc_count = 0
        chunk_count = 0
        
        try:
            for filename in os.listdir(self.knowledge_dir):
                if filename.endswith(".txt"):
                    file_path = os.path.join(self.knowledge_dir, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                            if not content:
                                continue
                            
                            # 1차: 줄바꿈 단락 기준 대분할
                            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                            for p_idx, para in enumerate(paragraphs):
                                # 2차: 청크 사이즈에 따라 한도 보장 재분할
                                sub_chunks = self._split_text(para)
                                for c_idx, chunk in enumerate(sub_chunks):
                                    documents.append({
                                        "id": f"{filename}_{p_idx}_{c_idx}",
                                        "text": chunk
                                    })
                                    chunk_count += 1
                            doc_count += 1
                    except Exception as e:
                        logger.error(f"Failed to read knowledge file {filename}: {e}")
        except Exception as e:
            logger.error(f"Failed to scan knowledge directory {self.knowledge_dir}: {e}")

        if documents:
            self.retriever.index_documents(documents)
            logger.info(f"Successfully loaded {doc_count} files and indexed {chunk_count} safe chunks (Chunk size limit: {self.chunk_size}).")
        else:
            logger.warning(f"No valid knowledge documents found in {self.knowledge_dir}")

    def retrieve_context(self, query: str) -> str:
        """사용자 질문에 대응하는 참고 문맥을 무결한 문단들의 결합 텍스트로 합쳐 반환합니다."""
        if not self.is_enabled:
            return ""
        
        results = self.retriever.retrieve(query, top_k=self.top_k)
        if not results:
            return ""
            
        valid_chunks = []
        current_length = 0
        
        for res in results:
            # 문단 간 결합할 때의 줄바꿈('\n\n') 길이까지 감안한 계산
            added_len = len(res) + (2 if valid_chunks else 0)
            
            # 이 문단을 더했을 때 최대 글자 수 한도를 넘어간다면
            if current_length + added_len > self.max_chars:
                # 소형 모델을 교란하는 말꼬리 생략 태그 없이 이 시점에서 정숙하게 중단합니다.
                break
                
            valid_chunks.append(res)
            current_length += added_len
            
        return "\n\n".join(valid_chunks)
