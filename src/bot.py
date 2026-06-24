import json
import logging
import os
import asyncio
import discord
from typing import Dict, List, Optional
from src.state_manager import StateManager
from src.llm_client import BaseLLMClient

logger = logging.getLogger("danddobot.bot")

def load_registered_channels(channels_file_path: str) -> Dict[int, str]:
    """
    Parses the channels config file and returns a dict of {channel_id: alias}.
    Format: one channel ID per line, with optional # alias comment.
    Example: 1234567890 # 개발 서버 - 일반
    """
    channels: Dict[int, str] = {}
    if not channels_file_path or not os.path.exists(channels_file_path):
        logger.warning(f"Channels file not found at: {channels_file_path}. No channels registered.")
        return channels
    try:
        with open(channels_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Split on '#' to separate ID and optional alias
                parts = line.split("#", 1)
                try:
                    channel_id = int(parts[0].strip())
                    alias = parts[1].strip() if len(parts) > 1 else f"채널 {channel_id}"
                    channels[channel_id] = alias
                except ValueError:
                    logger.warning(f"Invalid channel ID in channels file: '{parts[0].strip()}'. Skipping.")
        logger.info(f"Loaded {len(channels)} registered channel(s) from {channels_file_path}")
    except Exception as e:
        logger.error(f"Failed to read channels file at {channels_file_path}: {e}")
    return channels


class DanddobotClient(discord.Client):
    """
    Discord Client for Danddobot. Handles receiving messages in a registered active channel,
    calling the local LLM with a live persona system prompt, and returning responses.
    """
    def __init__(self, channels_file_path: str, llm_client: BaseLLMClient, persona_file_path: str,
                 state_manager: StateManager, admin_channel_id: Optional[int] = None, 
                 log_channel_id: Optional[int] = None, provider_urls: Optional[Dict[str, str]] = None,
                 *args, **kwargs):
        # We require message_content intents to read user messages
        intents = discord.Intents.default()
        intents.message_content = True
        kwargs["intents"] = intents
        
        super().__init__(*args, **kwargs)

        self.channels_file_path = channels_file_path
        self.llm_client = llm_client
        self.persona_file_path = persona_file_path
        self.admin_channel_id = admin_channel_id
        self.log_channel_id = log_channel_id
        self.provider_urls = provider_urls if provider_urls is not None else {}

        # Centralized configurations cache
        self.state_manager = state_manager

        # Load the registered channels list from config file
        self.registered_channels: Dict[int, str] = load_registered_channels(channels_file_path)

        # Initialize history context and concurrency execution lock
        self.channel_history: Dict[int, List[dict]] = {}
        self.lock = asyncio.Lock()

        # Retrieve configurations from state_manager
        self.use_memory: bool = self.state_manager.get_value("use_memory", False)
        self.max_memory_length: int = self.state_manager.get_value("max_memory_length", 10)
        self.active_channel_id: Optional[int] = self.state_manager.get_value("channel_id")

        if self.active_channel_id and int(self.active_channel_id) in self.registered_channels:
            self.active_channel_id = int(self.active_channel_id)
        else:
            self.active_channel_id = None

        if self.active_channel_id is None and self.registered_channels:
            self.active_channel_id = next(iter(self.registered_channels))
            logger.info(f"No persisted active channel found. Defaulting to first registered: {self.active_channel_id}")
        elif self.active_channel_id is None:
            logger.warning("No registered channels found. Bot will not respond to any channel messages.")

        # Keep legacy alias for backward compatibility
        self.channel_id = self.active_channel_id

        # Initialize available models list with currently loaded model as default
        current_model = getattr(self.llm_client, "model", "unknown")
        self.available_models: List[str] = [current_model] if current_model != "unknown" else []

        # Initialize CommandTree for application commands (slash commands)
        self.tree = discord.app_commands.CommandTree(self)

        logger.info(
            f"DanddobotClient initialized. Active channel: {self.active_channel_id}, "
            f"Registered channels: {list(self.registered_channels.keys())}, "
            f"Admin channel: {self.admin_channel_id}, "
            f"Log channel: {self.log_channel_id}, "
            f"Memory Enabled: {self.use_memory} (Max capacity: {self.max_memory_length})"
        )

    async def update_active_channel(self, new_channel_id: int):
        """Update the active chat channel and persist the change using StateManager."""
        self.active_channel_id = new_channel_id
        self.channel_id = new_channel_id  # Keep alias in sync
        await self.state_manager.set_value("channel_id", new_channel_id)
        logger.info(f"Active channel updated and persisted: {new_channel_id}")

    async def toggle_memory(self) -> bool:
        """Toggles conversational memory and persists the state using StateManager."""
        self.use_memory = not self.use_memory
        await self.state_manager.set_value("use_memory", self.use_memory)
        logger.info(f"Conversational memory toggled and persisted: {self.use_memory}")
        
        # Clear history when toggled off
        if not self.use_memory:
            self.channel_history.clear()
        return self.use_memory

    async def set_max_memory_length(self, limit: int):
        """Sets the conversational memory history size and persists using StateManager."""
        self.max_memory_length = limit
        await self.state_manager.set_value("max_memory_length", limit)
        logger.info(f"Max memory capacity updated and persisted: {limit}")

    async def set_llm_timeout(self, timeout: Optional[float]):
        """Sets the LLM client timeout and persists using StateManager."""
        if hasattr(self, "llm_client") and self.llm_client:
            self.llm_client.timeout = timeout
        await self.state_manager.set_value("llm_timeout", timeout)
        logger.info(f"LLM Client Timeout updated and persisted: {timeout}")

    async def update_llm_model(self, new_model: str):
        """Updates the LLM client model and persists the change using StateManager."""
        if hasattr(self, "llm_client") and self.llm_client:
            self.llm_client.model = new_model
        await self.state_manager.set_value("llm_model", new_model)
        logger.info(f"LLM model updated and persisted: {new_model}")

    async def update_llm_provider(self, new_provider: str):
        """Gracefully updates the LLM provider, re-instantiating the LLM Client using the pre-configured URL."""
        new_provider_upper = new_provider.upper()
        new_api_url = self.provider_urls.get(new_provider_upper)
        if not new_api_url:
            raise ValueError(f"Provider {new_provider_upper} has no configured API URL in environment variables.")

        old_client = self.llm_client

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
            timeout=current_timeout
        )
        self.llm_client = new_client

        # 4. Fetch available models for the new client
        try:
            fetched_models = await new_client.get_available_models()
            if fetched_models:
                self.available_models = fetched_models
                # If current model is not in fetched models, switch to first available
                if current_model not in fetched_models:
                    new_model = fetched_models[0]
                    self.llm_client.model = new_model
                    await self.state_manager.set_value("llm_model", new_model)
                    logger.info(f"Model auto-swapped to {new_model} because current model wasn't found in new provider.")
            else:
                self.available_models = [current_model]
        except Exception as e:
            logger.error(f"Failed to fetch models for new provider: {e}")
            self.available_models = [current_model]

        # 5. Persist provider and URL in StateManager
        await self.state_manager.set_value("llm_provider", new_provider_upper)
        await self.state_manager.set_value("llm_api_url", new_api_url)
        logger.info(f"LLM Provider updated and persisted: {new_provider_upper} with URL {new_api_url}")

    def reload_channels(self):
        """Reload the registered channels list from the config file."""
        self.registered_channels = load_registered_channels(self.channels_file_path)
        logger.info(f"Channels reloaded: {self.registered_channels}")

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        
        # Fetch available models from backend on startup
        logger.info("Fetching available LLM models from backend...")
        try:
            fetched_models = await self.llm_client.get_available_models()
            if fetched_models:
                self.available_models = fetched_models
                logger.info(f"Successfully loaded available models: {self.available_models}")
            else:
                logger.warning("Backend returned empty model list. Fallback to currently active model.")
        except Exception as e:
            logger.error(f"Failed to fetch available models on startup: {e}")
        
        # 1. Setup Persistent View and Send/Update Admin Dashboard
        from src.admin_panel import AdminDashboardView, build_dashboard_embed
        
        # Register persistent view for button interaction handling
        self.add_view(AdminDashboardView(self))
        
        if self.admin_channel_id:
            admin_channel = self.get_channel(self.admin_channel_id)
            if admin_channel:
                logger.info(f"Initializing admin dashboard in channel {admin_channel.name} (ID: {self.admin_channel_id})")
                
                # Delete past bot messages to clean up the channel history
                try:
                    async for msg in admin_channel.history(limit=50):
                        if msg.author == self.user:
                            await msg.delete()
                    logger.info("Successfully cleaned up history in admin channel.")
                except Exception as history_err:
                    logger.warning(f"Could not fully clean history in admin channel: {history_err}")
                
                # Post the fresh dashboard embed
                try:
                    embed = build_dashboard_embed(self)
                    view = AdminDashboardView(self)
                    await admin_channel.send(embed=embed, view=view)
                    logger.info("Admin dashboard posted successfully.")
                except Exception as send_err:
                    logger.error(f"Failed to send admin dashboard: {send_err}")
            else:
                logger.warning(f"Could not find admin channel with ID: {self.admin_channel_id}. Is the bot member of that server?")
        else:
            logger.info("Admin channel ID not configured. Dashboard is disabled.")

        # 3. Setup Log Channel Status Verification
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                logger.info(f"Log channel configured and verified: {log_channel.name} (ID: {self.log_channel_id})")
            else:
                logger.warning(f"Could not find log channel with ID: {self.log_channel_id}. Is the bot member of that server?")
        else:
            logger.info("Log channel ID not configured. System errors will be sent to the active chat channel.")

        logger.info("Bot is active and listening for messages.")

    def should_respond(self, message: discord.Message) -> bool:
        """
        Determines whether the bot should respond to a given message.
        """
        # 1. Ignore messages sent by the bot itself
        if message.author == self.user:
            return False

        # 2. Ignore messages in the admin channel
        if self.admin_channel_id and message.channel.id == self.admin_channel_id:
            return False

        # 3. Only respond in the currently active chat channel
        if not self.active_channel_id or message.channel.id != self.active_channel_id:
            return False

        return True

    def load_persona(self) -> str:
        """
        Dynamically reads the persona prompt file to allow real-time prompt editing.
        """
        default_persona = (
            "당신은 디스코드 채널의 친절한 AI 어시스턴트입니다. "
            "사용자의 질문에 한국어로 성실히 답변하십시오."
        )

        if not self.persona_file_path:
            return default_persona

        try:
            if os.path.exists(self.persona_file_path):
                with open(self.persona_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        logger.debug(f"Loaded persona successfully from {self.persona_file_path}")
                        return content
            else:
                logger.warning(f"Persona file not found at: {self.persona_file_path}. Using default persona.")
        except Exception as e:
            logger.error(f"Error reading persona file at {self.persona_file_path}: {e}. Using default persona.")

        return default_persona

    async def _handle_llm_error(self, message: discord.Message, llm_error: Exception):
        """
        Gracefully formats and dispatches LLM API failure notifications to the logging
        or active conversation channel.
        """
        log_channel = None
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if not log_channel:
                try:
                    log_channel = await self.fetch_channel(self.log_channel_id)
                except Exception as fetch_err:
                    logger.error(f"Failed to fetch log channel {self.log_channel_id}: {fetch_err}")

        user_content = message.content
        if log_channel:
            error_msg = (
                f"❌ **챗봇 시스템 오류 발생**\n"
                f"• **채널**: {message.channel.mention} (ID: {message.channel.id})\n"
                f"• **사용자**: {message.author.mention} (ID: {message.author.id})\n"
                f"• **메시지 내용**: {user_content[:100]}\n"
                f"• **오류 내용**: `{llm_error}`"
            )
            try:
                await log_channel.send(error_msg)
            except Exception as send_err:
                logger.error(f"Failed to send error message to log channel: {send_err}")
                try:
                    await message.reply(f"❌ {llm_error}")
                except Exception as reply_err:
                    logger.error(f"Failed to send fallback reply: {reply_err}")
        else:
            try:
                await message.reply(f"❌ {llm_error}")
            except Exception as reply_err:
                logger.error(f"Failed to send reply to active channel: {reply_err}")

    async def on_message(self, message: discord.Message):
        # Verify if we should handle this message
        if not self.should_respond(message):
            return

        # Acquire sequential processing lock (Option A)
        async with self.lock:
            user_content = message.content
            logger.info(f"Received message from {message.author} in target channel: '{user_content[:50]}...'")

            # Load system prompt dynamically
            system_prompt = self.load_persona()

            # Load history context if memory is enabled
            history = None
            if self.use_memory:
                history = self.channel_history.get(message.channel.id, [])

            # Display typing status while LLM generates response
            llm_error = None
            response = None
            async with message.channel.typing():
                try:
                    response = await self.llm_client.generate_response(user_content, system_prompt, history=history)
                except Exception as e:
                    logger.error(f"Failed to generate LLM response: {e}")
                    llm_error = e

            if llm_error is not None:
                await self._handle_llm_error(message, llm_error)
            else:
                # Save dialog to conversational history if memory is enabled
                if self.use_memory:
                    if message.channel.id not in self.channel_history:
                        self.channel_history[message.channel.id] = []
                    self.channel_history[message.channel.id].append({"role": "user", "content": user_content})
                    self.channel_history[message.channel.id].append({"role": "assistant", "content": response})
                    # Cap sliding history window using the dynamic limit
                    if len(self.channel_history[message.channel.id]) > self.max_memory_length:
                        self.channel_history[message.channel.id] = self.channel_history[message.channel.id][-self.max_memory_length:]

                # Check if there are any newer messages in the channel after our prompt message
                has_newer_messages = False
                try:
                    async for _ in message.channel.history(after=message, limit=1):
                        has_newer_messages = True
                        break
                except Exception as history_err:
                    logger.warning(f"Failed to check newer messages: {history_err}")

                # Send the response (handling Discord's 2000 character limit using Option A)
                chunks = self.split_message(response)
                for idx, chunk in enumerate(chunks):
                    try:
                        if has_newer_messages and idx == 0:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                    except Exception as e:
                        logger.error(f"Failed to send message chunk {idx}: {e}")

    @staticmethod
    def split_message(text: str, limit: int = 2000) -> List[str]:
        """
        Splits a text response into chunks of up to 2000 characters to fit Discord's limits.
        Avoids breaking mid-line if possible.
        """
        if len(text) <= limit:
            return [text]

        chunks = []
        lines = text.split("\n")
        current_chunk = ""

        for line in lines:
            if len(line) > limit:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                temp_line = line
                while len(temp_line) > limit:
                    chunks.append(temp_line[:limit])
                    temp_line = temp_line[limit:]
                current_chunk = temp_line + "\n"
            elif len(current_chunk) + len(line) + 1 > limit:
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def close(self):
        """Disposes of persistent client pools and logs out from Discord gateway."""
        if hasattr(self, "llm_client") and self.llm_client:
            await self.llm_client.close()
            logger.info("Closed LLM client connection pool.")
        await super().close()
