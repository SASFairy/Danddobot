import logging
import httpx
from typing import Optional

logger = logging.getLogger("danddobot.llm_client")

class BaseLLMClient:
    """
    Abstract Base Class for local LLM integration.
    Allows easy porting by ensuring all clients expose the same async interface.
    """
    def __init__(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None, repeat_penalty: Optional[float] = None):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.repeat_penalty = repeat_penalty

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, history: Optional[list[dict]] = None) -> str:
        """
        Sends the prompt, an optional system prompt, and optional context history to the local LLM and returns the generated answer.
        """
        raise NotImplementedError("generate_response must be implemented by subclasses.")

    async def get_available_models(self) -> list[str]:
        """
        Retrieves the list of available models from the LLM provider.
        """
        return []

    async def close(self):
        """
        Closes any long-lived persistent HTTP connection pools.
        """
        pass


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama's direct HTTP Chat API (/api/chat).
    """
    def __init__(self, api_url: str, model: str, timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None):
        super().__init__(temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        # Ensure the api_url doesn't end with a slash for clean endpoint appending
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"OllamaClient initialized with URL: {self.api_url}, model: {self.model}, timeout: {self.timeout}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily instantiates and returns a persistent shared httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()  # Single shared instance
            logger.info("Shared persistent connection pool initialized for OllamaClient.")
        return self._client

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, history: Optional[list[dict]] = None) -> str:
        endpoint = f"{self.api_url}/api/chat"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        # Inject hyperparameters dynamically if configured
        options = {}
        if self.temperature is not None:
            options["temperature"] = self.temperature
        if self.max_tokens is not None:
            options["num_predict"] = self.max_tokens
        if self.repeat_penalty is not None:
            options["repeat_penalty"] = self.repeat_penalty

        if options:
            payload["options"] = options

        try:
            client = await self._get_client()
            logger.debug(f"Sending request to Ollama endpoint: {endpoint}")
            # Dynamically pass self.timeout on each request to allow real-time changes
            response = await client.post(endpoint, json=payload, timeout=self.timeout)
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

    async def get_available_models(self) -> list[str]:
        """
        Fetches available models from Ollama's /api/tags endpoint.
        """
        endpoint = f"{self.api_url}/api/tags"
        try:
            client = await self._get_client()
            logger.debug(f"Fetching Ollama models from {endpoint}")
            response = await client.get(endpoint, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            models = [model.get("name") for model in result.get("models", []) if model.get("name")]
            logger.info(f"Fetched available Ollama models: {models}")
            return models
        except Exception as e:
            logger.error(f"Failed to fetch available models from Ollama: {e}")
            return []

    async def close(self):
        """Disposes of the long-lived client connection pool gracefully."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Shared persistent connection pool closed for OllamaClient.")


class OpenAICompatibleClient(BaseLLMClient):
    """
    Client for OpenAI-compatible local APIs (vLLM, Llama.cpp, LocalAI, etc.)
    hitting the /v1/chat/completions endpoint.
    """
    def __init__(self, api_url: str, model: str, provider_name: str = "OpenAICompatible", timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None):
        super().__init__(temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.provider_name = provider_name
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"{provider_name}Client initialized with URL: {self.api_url}, model: {self.model}, timeout: {self.timeout}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily instantiates and returns a persistent shared httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()  # Single shared instance
            logger.info(f"Shared persistent connection pool initialized for {self.provider_name}Client.")
        return self._client

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, history: Optional[list[dict]] = None) -> str:
        endpoint = f"{self.api_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        # Inject hyperparameters dynamically if configured
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.repeat_penalty is not None:
            # Map repeat_penalty (1.0 to 2.0+) to frequency_penalty (0.0 to 2.0)
            freq_penalty = max(0.0, min(2.0, (self.repeat_penalty - 1.0)))
            payload["frequency_penalty"] = freq_penalty

        try:
            client = await self._get_client()
            logger.debug(f"Sending request to OpenAI-compatible endpoint: {endpoint}")
            # Dynamically pass self.timeout on each request to allow real-time changes
            response = await client.post(endpoint, json=payload, timeout=self.timeout)
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

    async def get_available_models(self) -> list[str]:
        """
        Fetches available models from OpenAI-compatible /v1/models endpoint.
        """
        endpoint = f"{self.api_url}/v1/models"
        try:
            client = await self._get_client()
            logger.debug(f"Fetching {self.provider_name} models from {endpoint}")
            response = await client.get(endpoint, timeout=10.0)
            response.raise_for_status()
            result = response.json()
            models = [model.get("id") for model in result.get("data", []) if model.get("id")]
            logger.info(f"Fetched available {self.provider_name} models: {models}")
            return models
        except Exception as e:
            logger.error(f"Failed to fetch available models from {self.provider_name}: {e}")
            return []

    async def close(self):
        """Disposes of the long-lived client connection pool gracefully."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info(f"Shared persistent connection pool closed for {self.provider_name}Client.")


class LLMClientFactory:
    """
    Factory to resolve the concrete BaseLLMClient instance dynamically.
    """
    @staticmethod
    def get_client(provider: str, api_url: str, model: str, timeout: Optional[float] = 300.0,
                   temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                   repeat_penalty: Optional[float] = None) -> BaseLLMClient:
        prov = provider.upper()
        if prov == "OLLAMA":
            return OllamaClient(api_url, model, timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        elif prov == "OPENAI_COMPATIBLE":
            return OpenAICompatibleClient(api_url, model, "OpenAICompatible", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        elif prov == "LLAMA_CPP":
            return OpenAICompatibleClient(api_url, model, "LlamaCpp", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        elif prov == "VLLM":
            return OpenAICompatibleClient(api_url, model, "vLLM", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        elif prov == "LM_STUDIO":
            return OpenAICompatibleClient(api_url, model, "LMStudio", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
        else:
            logger.warning(f"Unknown LLM provider: {provider}. Defaulting to OLLAMA client.")
            return OllamaClient(api_url, model, timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty)
