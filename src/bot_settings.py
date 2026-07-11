import logging
from typing import Dict, List, Optional

logger = logging.getLogger("danddobot.bot_settings")

class BotSettingsController:
    """
    Centralized controller for DanddobotClient runtime settings and persistence.
    Implements Alternative 1 (Composition).
    """
    def __init__(self, client):
        self.client = client
        # Keep a handy reference to state_manager
        self.state_manager = client.state_manager

    async def update_active_channel(self, new_channel_id: int):
        """Update the active chat channel and persist the change using StateManager."""
        self.client.active_channel_id = new_channel_id
        self.client.channel_id = new_channel_id  # Keep alias in sync
        await self.state_manager.set_value("channel_id", new_channel_id)
        logger.info(f"Active channel updated and persisted: {new_channel_id}")

    async def toggle_memory(self) -> bool:
        """Toggles conversational memory and persists the state using StateManager."""
        self.client.use_memory = not self.client.use_memory
        await self.state_manager.set_value("use_memory", self.client.use_memory)
        logger.info(f"Conversational memory toggled and persisted: {self.client.use_memory}")
        
        # Clear history when toggled off
        if not self.client.use_memory:
            self.client.channel_history.clear()
        return self.client.use_memory

    async def toggle_debug_mode(self) -> bool:
        """Toggles real-time debug logging mode and persists the state using StateManager."""
        self.client.debug_mode = not self.client.debug_mode
        await self.state_manager.set_value("debug_mode", self.client.debug_mode)
        logger.info(f"Debug logging mode toggled and persisted: {self.client.debug_mode}")
        return self.client.debug_mode

    async def toggle_distinguish_users(self) -> bool:
        """Toggles user prefix/distinction and persists the state using StateManager."""
        self.client.distinguish_users = not self.client.distinguish_users
        await self.state_manager.set_value("distinguish_users", self.client.distinguish_users)
        logger.info(f"User distinction toggled and persisted: {self.client.distinguish_users}")
        return self.client.distinguish_users

    async def set_max_memory_length(self, limit: int):
        """Sets the conversational memory history size and persists using StateManager."""
        self.client.max_memory_length = limit
        await self.state_manager.set_value("max_memory_length", limit)
        logger.info(f"Max memory capacity updated and persisted: {limit}")

    async def set_llm_timeout(self, timeout: Optional[float]):
        """Sets the LLM client timeout and persists using StateManager."""
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            self.client.llm_client.timeout = timeout
        await self.state_manager.set_value("llm_timeout", timeout)
        logger.info(f"LLM Client Timeout updated and persisted: {timeout}")

    async def update_llm_model(self, new_model: str):
        """Updates the LLM client model and persists the change using StateManager."""
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            self.client.llm_client.model = new_model
        await self.state_manager.set_value("llm_model", new_model)
        logger.info(f"LLM model updated and persisted: {new_model}")

    async def update_llm_parameters(self, temperature: Optional[float], max_tokens: Optional[int], repeat_penalty: Optional[float],
                                    top_p: Optional[float], top_k: Optional[int]):
        """
        Dynamically updates the LLM generation hyperparameters and persists them using StateManager.
        """
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            self.client.llm_client.temperature = temperature
            self.client.llm_client.max_tokens = max_tokens
            self.client.llm_client.repeat_penalty = repeat_penalty
            self.client.llm_client.top_p = top_p
            self.client.llm_client.top_k = top_k
        
        await self.state_manager.set_value("llm_temperature", temperature)
        await self.state_manager.set_value("llm_max_tokens", max_tokens)
        await self.state_manager.set_value("llm_repeat_penalty", repeat_penalty)
        await self.state_manager.set_value("llm_top_p", top_p)
        await self.state_manager.set_value("llm_top_k", top_k)
        logger.info(f"LLM parameters updated and persisted: Temperature={temperature}, MaxTokens={max_tokens}, RepeatPenalty={repeat_penalty}, TopP={top_p}, TopK={top_k}")

    async def reset_llm_parameters(self):
        """
        Resets all LLM generation hyperparameters to None (forcing model-native defaults) and persists them using StateManager.
        """
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            self.client.llm_client.temperature = None
            self.client.llm_client.max_tokens = None
            self.client.llm_client.repeat_penalty = None
            self.client.llm_client.top_p = None
            self.client.llm_client.top_k = None
        
        await self.state_manager.set_value("llm_temperature", None)
        await self.state_manager.set_value("llm_max_tokens", None)
        await self.state_manager.set_value("llm_repeat_penalty", None)
        await self.state_manager.set_value("llm_top_p", None)
        await self.state_manager.set_value("llm_top_k", None)
        logger.info("LLM parameters reset to model defaults and persisted.")

    async def update_llm_provider(self, new_provider: str):
        """Gracefully updates the LLM provider, re-instantiating the LLM Client using the pre-configured URL."""
        new_provider_upper = new_provider.upper()
        new_api_url = self.client.provider_urls.get(new_provider_upper)
        if not new_api_url:
            raise ValueError(f"Provider {new_provider_upper} has no configured API URL in environment variables.")

        old_client = self.client.llm_client

        # 1. Close old client's connection pool
        if old_client:
            try:
                await old_client.close()
                logger.info("Successfully closed old LLM client connection pool.")
            except Exception as e:
                logger.error(f"Error while closing old LLM client: {e}")

        # 2. Get current model & timeout
        current_model = getattr(old_client, "model", "llama3")
        current_timeout = getattr(old_client, "timeout", 300.0)

        # 3. Instantiate new client using factory
        from src.llm_client import LLMClientFactory
        new_client = LLMClientFactory.get_client(
            provider=new_provider_upper,
            api_url=new_api_url,
            model=current_model,
            timeout=current_timeout,
            api_key=self.client.cerebras_api_key if new_provider_upper == "CEREBRAS" else None,
            temperature=getattr(old_client, "temperature", None),
            max_tokens=getattr(old_client, "max_tokens", None),
            repeat_penalty=getattr(old_client, "repeat_penalty", None),
            top_p=getattr(old_client, "top_p", None),
            top_k=getattr(old_client, "top_k", None)
        )
        self.client.llm_client = new_client

        # 4. Fetch available models for the new client
        try:
            fetched_models = await new_client.get_available_models()
            if fetched_models:
                self.client.available_models = fetched_models
                # If current model is not in fetched models, switch to first available
                if current_model not in fetched_models:
                    new_model = fetched_models[0]
                    self.client.llm_client.model = new_model
                    await self.state_manager.set_value("llm_model", new_model)
                    logger.info(f"Model auto-swapped to {new_model} because current model wasn't found in new provider.")
            else:
                self.client.available_models = [current_model]
        except Exception as e:
            logger.error(f"Failed to fetch models for new provider: {e}")
            self.client.available_models = [current_model]

        # 5. Persist provider and URL in StateManager
        await self.state_manager.set_value("llm_provider", new_provider_upper)
        await self.state_manager.set_value("llm_api_url", new_api_url)
        logger.info(f"LLM Provider updated and persisted: {new_provider_upper} with URL {new_api_url}")

    async def update_persona_prompt(self, new_prompt: str):
        """Updates the cached persona system prompt dynamically in-memory."""
        self.client.persona_prompt = new_prompt
        logger.info("Persona cache successfully updated in-memory.")

    def reload_channels(self):
        """Reload the registered channels list from the config file."""
        from src.bot import load_registered_channels
        self.client.registered_channels = load_registered_channels(self.client.channels_file_path)
        logger.info(f"Channels reloaded: {self.client.registered_channels}")

    async def toggle_rag(self) -> bool:
        """Toggles the RAG engine and persists the state using StateManager."""
        is_enabled = not self.client.rag_manager.is_enabled
        self.client.rag_manager.is_enabled = is_enabled
        await self.state_manager.set_value("rag_enabled", is_enabled)
        logger.info(f"RAG engine toggled and persisted: {is_enabled}")
        
        # Trigger reloading of knowledge on enabling RAG
        if is_enabled:
            self.client.rag_manager.reload_knowledge()
            
        return is_enabled

    async def update_rag_parameters(self, top_k: int, max_chars: int, chunk_size: int):
        """Updates and persists RAG operational hyperparameters."""
        # Safety clamp
        if chunk_size > max_chars:
            logger.warning(f"RAG_CHUNK_SIZE ({chunk_size}) is greater than RAG_MAX_CHARS ({max_chars}). Automatically capping chunk_size to {max_chars}.")
            chunk_size = max_chars
            
        self.client.rag_manager.top_k = top_k
        self.client.rag_manager.max_chars = max_chars
        self.client.rag_manager.chunk_size = chunk_size
        
        await self.state_manager.set_value("rag_top_k", top_k)
        await self.state_manager.set_value("rag_max_chars", max_chars)
        await self.state_manager.set_value("rag_chunk_size", chunk_size)
        
        # Reload/re-index documents using the updated chunk size
        self.client.rag_manager.reload_knowledge()
        logger.info(f"RAG parameters updated, persisted, and knowledge re-indexed: Top-K={top_k}, MaxChars={max_chars}, ChunkSize={chunk_size}")
