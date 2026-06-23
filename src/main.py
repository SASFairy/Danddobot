import os
import sys
import logging
from dotenv import load_dotenv
from src.state_manager import StateManager
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

    # 2. Load environment variables from .env if present
    load_dotenv()

    # 3. Initialize Centralized State Manager
    state_manager = StateManager()

    # 4. Read and validate environment variables
    discord_token = os.getenv("DISCORD_TOKEN")

    if not discord_token:
        logger.critical("DISCORD_TOKEN environment variable is missing! Program exiting.")
        sys.exit(1)

    # Read LLM Configuration
    llm_provider = os.getenv("LLM_PROVIDER", "OLLAMA")
    llm_api_url = os.getenv("LLM_API_URL", "http://localhost:11434")
    llm_model = os.getenv("LLM_MODEL", "llama3")
    persona_file_path = os.getenv("PERSONA_FILE_PATH", "config/persona.txt")
    channels_file_path = os.getenv("CHANNELS_FILE_PATH", "config/channels.txt")
    
    # Override LLM Model from State Manager if present
    persisted_model = state_manager.get_value("llm_model")
    if persisted_model:
        llm_model = persisted_model
        logger.info(f"Loaded persisted llm_model from StateManager: {llm_model}")
    
    llm_timeout_raw = os.getenv("LLM_TIMEOUT")
    llm_timeout = 300.0
    if llm_timeout_raw and llm_timeout_raw.strip():
        try:
            val = float(llm_timeout_raw)
            if val <= 0:
                llm_timeout = None
                logger.info("LLM Timeout is configured to be unlimited (None)")
            else:
                llm_timeout = val
                logger.info(f"LLM Timeout configured: {llm_timeout} seconds")
        except ValueError:
            logger.warning(
                f"LLM_TIMEOUT must be a valid number or blank. Received: '{llm_timeout_raw}'. Defaulting to 300.0 seconds."
            )

    # Override LLM Timeout from State Manager if present
    persisted_timeout = state_manager.get_value("llm_timeout")
    if persisted_timeout is not None or "llm_timeout" in state_manager._cache:
        llm_timeout = persisted_timeout
        logger.info(f"Loaded persisted llm_timeout from StateManager: {llm_timeout} seconds")

    # Read Admin Channel Configuration
    admin_channel_id_raw = os.getenv("ADMIN_CHANNEL_ID")
    admin_channel_id = None
    if admin_channel_id_raw and admin_channel_id_raw.strip():
        try:
            admin_channel_id = int(admin_channel_id_raw)
            logger.info(f"Target Admin Channel ID: {admin_channel_id}")
        except ValueError:
            logger.warning(
                f"ADMIN_CHANNEL_ID must be a valid integer or blank. Received: '{admin_channel_id_raw}'. Admin dashboard will be disabled."
            )

    # Read Log Channel Configuration
    log_channel_id_raw = os.getenv("LOG_CHANNEL_ID")
    log_channel_id = None
    if log_channel_id_raw and log_channel_id_raw.strip():
        try:
            log_channel_id = int(log_channel_id_raw)
            logger.info(f"Target Log Channel ID: {log_channel_id}")
        except ValueError:
            logger.warning(
                f"LOG_CHANNEL_ID must be a valid integer or blank. Received: '{log_channel_id_raw}'. Dedicated log channel will be disabled."
            )

    logger.info(f"LLM Configuration: Provider={llm_provider}, API_Url={llm_api_url}, Model={llm_model}, Timeout={llm_timeout}")
    logger.info(f"Persona Prompt Path: {persona_file_path}")
    logger.info(f"Channels Config Path: {channels_file_path}")

    # 5. Initialize LLM Adapter Client
    llm_client = LLMClientFactory.get_client(
        provider=llm_provider,
        api_url=llm_api_url,
        model=llm_model,
        timeout=llm_timeout
    )

    # 6. Initialize Discord Client, passing StateManager
    bot = DanddobotClient(
        channels_file_path=channels_file_path,
        llm_client=llm_client,
        persona_file_path=persona_file_path,
        admin_channel_id=admin_channel_id,
        log_channel_id=log_channel_id,
        state_manager=state_manager
    )

    # 7. Run the Bot
    try:
        bot.run(discord_token)
    except Exception as e:
        logger.critical(f"Failed to start Discord Bot process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
