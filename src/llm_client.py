import logging
import httpx
from typing import Optional

logger = logging.getLogger("danddobot.llm_client")

class BaseLLMClient:
    """
    Abstract Base Class for local/external LLM integration.
    Allows easy porting by ensuring all clients expose the same async interface.
    """
    def __init__(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None, repeat_penalty: Optional[float] = None,
                 top_p: Optional[float] = None, top_k: Optional[int] = None):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.repeat_penalty = repeat_penalty
        self.top_p = top_p
        self.top_k = top_k

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

    def get_supported_parameter_ranges(self) -> dict:
        """
        Returns a dict mapping hyperparameter names to their valid (min, max) ranges,
        or None if not supported by the provider/client.
        """
        return {
            "temperature": (0.0, 2.0),
            "max_tokens": (1, 16384),
            "repeat_penalty": (0.0, 2.0),
            "top_p": (0.0, 1.0),
            "top_k": (1, 100)
        }


class BaseOpenAICompatibleClient(BaseLLMClient):
    """
    Base client encapsulating OpenAI-compatible /v1 API structure,
    connection pooling, and optional API key authentication.
    """
    def __init__(self, api_url: str, model: str, api_key: Optional[str] = None, provider_name: str = "OpenAICompatible", timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None, top_p: Optional[float] = None,
                 top_k: Optional[int] = None):
        super().__init__(temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        self.api_url = api_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.provider_name = provider_name
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info(f"{provider_name}Client initialized with URL: {self.api_url}, model: {self.model}, timeout: {self.timeout}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily instantiates and returns a persistent shared httpx.AsyncClient."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()  # Single shared instance
            logger.info(f"Shared persistent connection pool initialized for {self.provider_name}Client.")
        return self._client

    def _get_headers(self) -> dict:
        """Constructs headers, injecting the Authorization bearer token if api_key is present."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
        if self.top_p is not None:
            payload["top_p"] = self.top_p

        try:
            client = await self._get_client()
            headers = self._get_headers()
            logger.debug(f"Sending request to {self.provider_name} endpoint: {endpoint}")
            # Dynamically pass self.timeout on each request to allow real-time changes
            response = await client.post(endpoint, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            choices = result.get("choices", [])
            if choices:
                answer = choices[0].get("message", {}).get("content", "")
                return answer
            raise ValueError("API가 올바른 대답 형식을 반환하지 않았습니다.")
        except httpx.TimeoutException as e:
            logger.error(f"Timeout occurred while contacting {self.provider_name}: {e}")
            raise RuntimeError(f"로컬/외부 LLM 응답 요청 시간이 초과되었습니다. (Timeout: {e})") from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while contacting {self.provider_name}: {e}")
            raise RuntimeError(f"로컬/외부 LLM 통신 중 오류가 발생했습니다. (HTTP Error: {e})") from e
        except Exception as e:
            logger.error(f"Unexpected error in {self.provider_name} client: {e}")
            raise RuntimeError(f"예기치 못한 오류가 발생했습니다. (Error: {e})") from e

    async def get_available_models(self) -> list[str]:
        """
        Fetches available models from OpenAI-compatible /v1/models endpoint.
        """
        endpoint = f"{self.api_url}/v1/models"
        try:
            client = await self._get_client()
            headers = self._get_headers()
            logger.debug(f"Fetching {self.provider_name} models from {endpoint}")
            response = await client.get(endpoint, headers=headers, timeout=10.0)
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

    def get_supported_parameter_ranges(self) -> dict:
        """
        Returns a dict mapping hyperparameter names to their valid (min, max) ranges,
        or None if not supported by the OpenAI spec.
        """
        return {
            "temperature": (0.0, 2.0),
            "max_tokens": (1, 16384),
            "repeat_penalty": (1.0, 3.0),  # Maps to frequency_penalty [0.0, 2.0]
            "top_p": (0.0, 1.0),
            "top_k": None  # Not supported by OpenAI-compatible APIs
        }


class OllamaClient(BaseLLMClient):
    """
    Client for Ollama's direct HTTP Chat API (/api/chat).
    """
    def __init__(self, api_url: str, model: str, timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None, top_p: Optional[float] = None,
                 top_k: Optional[int] = None):
        super().__init__(temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
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
        if self.top_p is not None:
            options["top_p"] = self.top_p
        if self.top_k is not None:
            options["top_k"] = self.top_k

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

    def get_supported_parameter_ranges(self) -> dict:
        """
        Returns a dict mapping hyperparameter names to their valid (min, max) ranges,
        or None if not supported by Ollama.
        """
        return {
            "temperature": (0.0, 2.0),
            "max_tokens": (1, 16384),
            "repeat_penalty": (0.0, 2.0),
            "top_p": (0.0, 1.0),
            "top_k": (1, 100)
        }


class OpenAICompatibleClient(BaseOpenAICompatibleClient):
    """
    Client for OpenAI-compatible local APIs (vLLM, Llama.cpp, LocalAI, etc.)
    that does not require an API key by default.
    """
    def __init__(self, api_url: str, model: str, provider_name: str = "OpenAICompatible", timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None, top_p: Optional[float] = None,
                 top_k: Optional[int] = None):
        super().__init__(
            api_url=api_url,
            model=model,
            api_key=None,
            provider_name=provider_name,
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
            top_k=top_k
        )


class CerebrasClient(BaseOpenAICompatibleClient):
    """
    Client for Cerebras Cloud Inference API (OpenAI Compatible with API Key authentication).
    Supports multi-key rotation and failover on rate limits or failures.
    """
    def __init__(self, api_url: str, model: str, api_key: str, timeout: Optional[float] = 300.0,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                 repeat_penalty: Optional[float] = None, top_p: Optional[float] = None,
                 top_k: Optional[int] = None):
        super().__init__(
            api_url=api_url or "https://api.cerebras.ai",
            model=model,
            api_key=api_key,
            provider_name="Cerebras",
            timeout=timeout,
            temperature=temperature,
            max_tokens=max_tokens,
            repeat_penalty=repeat_penalty,
            top_p=top_p,
            top_k=top_k
        )
        self.api_keys = [k.strip() for k in api_key.split(",") if k.strip()] if api_key else []
        self.current_key_index = 0
        logger.info(f"CerebrasClient initialized with {len(self.api_keys)} registered API keys.")

    def _get_headers(self) -> dict:
        headers = {}
        if self.api_keys:
            # Safely clamp index
            idx = self.current_key_index % len(self.api_keys)
            active_key = self.api_keys[idx]
            redacted = active_key[:4] + "..." + active_key[-4:] if len(active_key) > 8 else "..."
            logger.debug(f"Using Cerebras API key index {idx}: {redacted}")
            headers["Authorization"] = f"Bearer {active_key}"
        return headers

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, history: Optional[list[dict]] = None) -> str:
        if not self.api_keys:
            raise RuntimeError("등록된 Cerebras API 키가 없습니다. .env 파일을 확인해 주세요.")

        attempts = len(self.api_keys)
        last_exception = None

        for attempt in range(attempts):
            idx = self.current_key_index % len(self.api_keys)
            self.current_key_index = idx  # Keep it clean
            
            try:
                # Call the base class generate_response, which will use our overridden _get_headers()
                return await super().generate_response(prompt, system_prompt, history)
            except Exception as e:
                last_exception = e
                redacted_key = self.api_keys[idx][:4] + "..." + self.api_keys[idx][-4:] if len(self.api_keys[idx]) > 8 else "..."
                logger.warning(
                    f"[Cerebras Failover] API key index {idx} ({redacted_key}) failed (Attempt {attempt + 1}/{attempts}). "
                    f"Error: {e}. Rotating to next key..."
                )
                # Rotate key index
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)

        logger.critical("[Cerebras Failover] All registered Cerebras API keys have failed.")
        raise RuntimeError(f"모든 등록된 Cerebras API 키 호출에 실패했습니다. (최종 에러: {last_exception})") from last_exception

    async def get_available_models(self) -> list[str]:
        if not self.api_keys:
            return []

        attempts = len(self.api_keys)
        for attempt in range(attempts):
            idx = self.current_key_index % len(self.api_keys)
            self.current_key_index = idx
            
            try:
                return await super().get_available_models()
            except Exception as e:
                logger.warning(f"[Cerebras Failover] Failed to fetch models with key index {idx}: {e}. Rotating...")
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return []


class LLMClientFactory:
    """
    Factory to resolve the concrete BaseLLMClient instance dynamically.
    """
    @staticmethod
    def get_client(provider: str, api_url: str, model: str, timeout: Optional[float] = 300.0, api_key: Optional[str] = None,
                   temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                   repeat_penalty: Optional[float] = None, top_p: Optional[float] = None,
                   top_k: Optional[int] = None) -> BaseLLMClient:
        prov = provider.upper()
        if prov == "OLLAMA":
            return OllamaClient(api_url, model, timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        elif prov == "CEREBRAS":
            return CerebrasClient(api_url, model, api_key=api_key, timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        elif prov == "OPENAI_COMPATIBLE":
            return OpenAICompatibleClient(api_url, model, "OpenAICompatible", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        elif prov == "LLAMA_CPP":
            return OpenAICompatibleClient(api_url, model, "LlamaCpp", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        elif prov == "VLLM":
            return OpenAICompatibleClient(api_url, model, "vLLM", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        elif prov == "LM_STUDIO":
            return OpenAICompatibleClient(api_url, model, "LMStudio", timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
        else:
            logger.warning(f"Unknown LLM provider: {provider}. Defaulting to OLLAMA client.")
            return OllamaClient(api_url, model, timeout=timeout, temperature=temperature, max_tokens=max_tokens, repeat_penalty=repeat_penalty, top_p=top_p, top_k=top_k)
