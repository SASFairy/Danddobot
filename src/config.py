import os
import logging
from typing import Dict, Optional
from dotenv import load_dotenv
from src.state_manager import StateManager

logger = logging.getLogger("danddobot.config")

class AppConfig:
    """
    Centralized configurations manager that handles loading environment variables
    from .env and overlaying saved settings from StateManager.
    """
    def __init__(self, state_manager: StateManager):
        # 1. Load environment variables from .env if present
        load_dotenv()

        # 2. Discord configuration
        self.discord_token = os.getenv("DISCORD_TOKEN")

        # 3. LLM Configuration
        self.llm_provider = os.getenv("LLM_PROVIDER", "OLLAMA")
        self.llm_api_url = os.getenv("LLM_API_URL", "http://localhost:11434")
        self.llm_model = os.getenv("LLM_MODEL", "llama3")
        self.persona_file_path = os.getenv("PERSONA_FILE_PATH", "config/persona.txt")
        self.channels_file_path = os.getenv("CHANNELS_FILE_PATH", "config/channels.txt")

        # Override LLM Provider from State Manager if present
        persisted_provider = state_manager.get_value("llm_provider")
        if persisted_provider:
            self.llm_provider = persisted_provider
            logger.info(f"Loaded persisted llm_provider from StateManager: {self.llm_provider}")

        # Override LLM API URL from State Manager if present
        persisted_api_url = state_manager.get_value("llm_api_url")
        if persisted_api_url:
            self.llm_api_url = persisted_api_url
            logger.info(f"Loaded persisted llm_api_url from StateManager: {self.llm_api_url}")

        # Read LLM Engine-specific API URLs from .env
        self.provider_urls: Dict[str, str] = {}
        for prov in ["OLLAMA", "OPENAI_COMPATIBLE", "LLAMA_CPP", "VLLM", "LM_STUDIO", "CEREBRAS"]:
            url = os.getenv(f"{prov}_API_URL")
            if url and url.strip():
                self.provider_urls[prov] = url.strip()

        # Add Cerebras default endpoint if not explicitly configured in *_API_URL
        if "CEREBRAS" not in self.provider_urls:
            self.provider_urls["CEREBRAS"] = os.getenv("CEREBRAS_API_URL", "https://api.cerebras.ai").strip()

        # Ensure current provider and API URL is represented in provider_urls
        if self.llm_provider not in self.provider_urls:
            self.provider_urls[self.llm_provider] = self.llm_api_url

        # Load Cerebras API key
        self.cerebras_api_key = os.getenv("CEREBRAS_API_KEY", "").strip()

        # Override LLM Model from State Manager if present
        persisted_model = state_manager.get_value("llm_model")
        if persisted_model:
            self.llm_model = persisted_model
            logger.info(f"Loaded persisted llm_model from StateManager: {self.llm_model}")

        # Parse LLM Timeout
        llm_timeout_raw = os.getenv("LLM_TIMEOUT")
        self.llm_timeout: Optional[float] = 300.0
        if llm_timeout_raw and llm_timeout_raw.strip():
            try:
                val = float(llm_timeout_raw)
                if val <= 0:
                    self.llm_timeout = None
                    logger.info("LLM Timeout is configured to be unlimited (None)")
                else:
                    self.llm_timeout = val
                    logger.info(f"LLM Timeout configured: {self.llm_timeout} seconds")
            except ValueError:
                logger.warning(
                    f"LLM_TIMEOUT must be a valid number or blank. Received: '{llm_timeout_raw}'. Defaulting to 300.0 seconds."
                )

        # Override LLM Timeout from State Manager if present
        persisted_timeout = state_manager.get_value("llm_timeout")
        if persisted_timeout is not None or "llm_timeout" in state_manager._cache:
            self.llm_timeout = persisted_timeout
            logger.info(f"Loaded persisted llm_timeout from StateManager: {self.llm_timeout} seconds")

        # Load LLM Hyperparameters from State Manager
        self.llm_temperature = state_manager.get_value("llm_temperature")
        self.llm_max_tokens = state_manager.get_value("llm_max_tokens")
        self.llm_repeat_penalty = state_manager.get_value("llm_repeat_penalty")
        self.llm_top_p = state_manager.get_value("llm_top_p")
        self.llm_top_k = state_manager.get_value("llm_top_k")
        logger.info(f"Loaded hyperparameters from StateManager: Temperature={self.llm_temperature}, MaxTokens={self.llm_max_tokens}, RepeatPenalty={self.llm_repeat_penalty}, TopP={self.llm_top_p}, TopK={self.llm_top_k}")

        # Read Admin Channel Configuration
        admin_channel_id_raw = os.getenv("ADMIN_CHANNEL_ID")
        self.admin_channel_id: Optional[int] = None
        if admin_channel_id_raw and admin_channel_id_raw.strip():
            try:
                self.admin_channel_id = int(admin_channel_id_raw)
                logger.info(f"Target Admin Channel ID: {self.admin_channel_id}")
            except ValueError:
                logger.warning(
                    f"ADMIN_CHANNEL_ID must be a valid integer or blank. Received: '{admin_channel_id_raw}'. Admin dashboard will be disabled."
                )

        # Read Log Channel Configuration
        log_channel_id_raw = os.getenv("LOG_CHANNEL_ID")
        self.log_channel_id: Optional[int] = None
        if log_channel_id_raw and log_channel_id_raw.strip():
            try:
                self.log_channel_id = int(log_channel_id_raw)
                logger.info(f"Target Log Channel ID: {self.log_channel_id}")
            except ValueError:
                logger.warning(
                    f"LOG_CHANNEL_ID must be a valid integer or blank. Received: '{log_channel_id_raw}'. Dedicated log channel will be disabled."
                )
