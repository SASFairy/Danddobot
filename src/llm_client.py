import logging
import httpx
from typing import Optional

logger = logging.getLogger("danddobot.llm_client")

class BaseLLMClient:
    """
    Abstract Base Class for local LLM integration.
    Allows easy porting by ensuring all clients expose the same async interface.
    """
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Sends the prompt and an optional system prompt to the local LLM and returns the generated answer.
        """
        raise NotImplementedError("generate_response must be implemented by subclasses.")


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama's direct HTTP Chat API (/api/chat).
    """
    def __init__(self, api_url: str, model: str, timeout: Optional[float] = 300.0):
        # Ensure the api_url doesn't end with a slash for clean endpoint appending
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        logger.info(f"OllamaClient initialized with URL: {self.api_url}, model: {self.model}, timeout: {self.timeout}")

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        endpoint = f"{self.api_url}/api/chat"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"Sending request to Ollama endpoint: {endpoint}")
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                
                result = response.json()
                answer = result.get("message", {}).get("content", "")
                return answer
        except httpx.TimeoutException as e:
            logger.error(f"Timeout occurred while contacting Ollama: {e}")
            raise RuntimeError(f"로컬 LLM 응답 요청 시간이 초과되었습니다. (Timeout: {e})") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while contacting Ollama: {e}")
            raise RuntimeError(f"로컬 LLM 통신 중 오류가 발생했습니다. (HTTP Error: {e})") from e
        except Exception as e:
            logger.error(f"Unexpected error in Ollama client: {e}")
            raise RuntimeError(f"예기치 못한 오류가 발생했습니다. (Error: {e})") from e


class OpenAICompatibleClient(BaseLLMClient):
    """
    Client for OpenAI-compatible local APIs (vLLM, Llama.cpp, LocalAI, etc.)
    hitting the /v1/chat/completions endpoint.
    """
    def __init__(self, api_url: str, model: str, provider_name: str = "OpenAICompatible", timeout: Optional[float] = 300.0):
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        logger.info(f"{provider_name}Client initialized with URL: {self.api_url}, model: {self.model}, timeout: {self.timeout}")

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        endpoint = f"{self.api_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"Sending request to OpenAI-compatible endpoint: {endpoint}")
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                
                result = response.json()
                choices = result.get("choices", [])
                if choices:
                    answer = choices[0].get("message", {}).get("content", "")
                    return answer
                raise ValueError("API가 올바른 대답 형식을 반환하지 않았습니다.")
        except httpx.TimeoutException as e:
            logger.error(f"Timeout occurred while contacting LLM: {e}")
            raise RuntimeError(f"로컬 LLM 응답 요청 시간이 초과되었습니다. (Timeout: {e})") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while contacting LLM: {e}")
            raise RuntimeError(f"로컬 LLM 통신 중 오류가 발생했습니다. (HTTP Error: {e})") from e
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI-compatible client: {e}")
            raise RuntimeError(f"예기치 못한 오류가 발생했습니다. (Error: {e})") from e


class LLMClientFactory:
    """
    Factory to resolve the concrete BaseLLMClient instance dynamically.
    """
    @staticmethod
    def get_client(provider: str, api_url: str, model: str, timeout: Optional[float] = 300.0) -> BaseLLMClient:
        prov = provider.upper()
        if prov == "OLLAMA":
            return OllamaClient(api_url, model, timeout=timeout)
        elif prov == "OPENAI_COMPATIBLE":
            return OpenAICompatibleClient(api_url, model, "OpenAICompatible", timeout=timeout)
        elif prov == "LLAMA_CPP":
            return OpenAICompatibleClient(api_url, model, "LlamaCpp", timeout=timeout)
        elif prov == "VLLM":
            return OpenAICompatibleClient(api_url, model, "vLLM", timeout=timeout)
        elif prov == "LM_STUDIO":
            return OpenAICompatibleClient(api_url, model, "LMStudio", timeout=timeout)
        else:
            logger.warning(f"Unknown LLM provider: {provider}. Defaulting to OLLAMA client.")
            return OllamaClient(api_url, model, timeout=timeout)
