import os
import sys
import logging
from dotenv import load_dotenv
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

    # 3. Read and validate environment variables
    discord_token = os.getenv("DISCORD_TOKEN")
    discord_channel_id_raw = os.getenv("DISCORD_CHANNEL_ID")
    
    if not discord_token:
        logger.critical("DISCORD_TOKEN environment variable is missing! Program exiting.")
        sys.exit(1)
        
    if not discord_channel_id_raw:
        logger.critical("DISCORD_CHANNEL_ID environment variable is missing! Program exiting.")
        sys.exit(1)

    try:
        discord_channel_id = int(discord_channel_id_raw)
    except ValueError:
        logger.critical(
            f"DISCORD_CHANNEL_ID must be a valid integer. Received: '{discord_channel_id_raw}'. Program exiting."
        )
        sys.exit(1)

    # Read LLM Configuration
    llm_provider = os.getenv("LLM_PROVIDER", "OLLAMA")
    llm_api_url = os.getenv("LLM_API_URL", "http://localhost:11434")
    llm_model = os.getenv("LLM_MODEL", "llama3")
    persona_file_path = os.getenv("PERSONA_FILE_PATH", "config/persona.txt")
    
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

    logger.info(f"Target Discord Channel ID: {discord_channel_id}")
    logger.info(f"LLM Configuration: Provider={llm_provider}, API_Url={llm_api_url}, Model={llm_model}")
    logger.info(f"Persona Prompt Path: {persona_file_path}")

    # 4. Initialize LLM Adapter Client
    llm_client = LLMClientFactory.get_client(
        provider=llm_provider,
        api_url=llm_api_url,
        model=llm_model
    )

    # 5. Initialize Discord Client
    bot = DanddobotClient(
        channel_id=discord_channel_id,
        llm_client=llm_client,
        persona_file_path=persona_file_path,
        admin_channel_id=admin_channel_id
    )

    # 6. Run the Bot
    try:
        bot.run(discord_token)
    except Exception as e:
        logger.critical(f"Failed to start Discord Bot process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
