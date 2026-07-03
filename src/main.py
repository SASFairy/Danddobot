import sys
import os
import logging
from src.state_manager import StateManager
from src.config import AppConfig
from src.llm_client import LLMClientFactory
from src.bot import DanddobotClient

# 1. Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("danddobot.main")

def main():
    logger.info("Starting Danddobot application bootstrap...")

    # 2. Initialize Centralized State Manager
    state_manager = StateManager()

    # 3. Load Configurations
    config = AppConfig(state_manager)

    # 4. Validate Discord Token
    if not config.discord_token:
        logger.critical("DISCORD_TOKEN environment variable is missing! Program exiting.")
        sys.exit(1)

    logger.info(f"LLM Configuration: Provider={config.llm_provider}, API_Url={config.llm_api_url}, Model={config.llm_model}, Timeout={config.llm_timeout}")
    logger.info(f"Persona Prompt Path: {config.persona_file_path}")
    logger.info(f"Channels Config Path: {config.channels_file_path}")

    # Check Cerebras API key warning
    if config.llm_provider.upper() == "CEREBRAS" and not config.cerebras_api_key:
        logger.warning("CEREBRAS_API_KEY is not configured, but CEREBRAS is selected as the LLM provider. Generation requests will likely fail.")

    # 5. Initialize LLM Adapter Client
    llm_client = LLMClientFactory.get_client(
        provider=config.llm_provider,
        api_url=config.llm_api_url,
        model=config.llm_model,
        timeout=config.llm_timeout,
        api_key=config.cerebras_api_key if config.llm_provider.upper() == "CEREBRAS" else None,
        temperature=config.llm_temperature,
        max_tokens=config.llm_max_tokens,
        repeat_penalty=config.llm_repeat_penalty,
        top_p=config.llm_top_p,
        top_k=config.llm_top_k
    )

    # 6. Initialize Discord Client
    bot = DanddobotClient(
        channels_file_path=config.channels_file_path,
        llm_client=llm_client,
        persona_file_path=config.persona_file_path,
        admin_channel_id=config.admin_channel_id,
        log_channel_id=config.log_channel_id,
        state_manager=state_manager,
        provider_urls=config.provider_urls,
        cerebras_api_key=config.cerebras_api_key
    )

    # 7. Run the Bot
    try:
        bot.run(config.discord_token)
    except Exception as e:
        logger.critical(f"Failed to start Discord Bot process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
