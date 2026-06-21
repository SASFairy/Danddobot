import json
import logging
import os
import discord
from typing import Dict, List, Optional
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
                 admin_channel_id: Optional[int] = None, *args, **kwargs):
        # We require message_content intents to read user messages
        intents = discord.Intents.default()
        intents.message_content = True
        kwargs["intents"] = intents
        
        super().__init__(*args, **kwargs)

        self.channels_file_path = channels_file_path
        self.llm_client = llm_client
        self.persona_file_path = persona_file_path
        self.admin_channel_id = admin_channel_id

        # Load the registered channels list from config file
        self.registered_channels: Dict[int, str] = load_registered_channels(channels_file_path)

        # Load persisted active channel from state.json, defaulting to first registered channel
        self.active_channel_id: Optional[int] = None
        state_path = "config/state.json"
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    saved_id = state.get("channel_id")
                    if saved_id and int(saved_id) in self.registered_channels:
                        self.active_channel_id = int(saved_id)
                        logger.info(f"Loaded persisted active_channel_id from state.json: {self.active_channel_id}")
            except Exception as e:
                logger.error(f"Failed to read state file: {e}")

        if self.active_channel_id is None and self.registered_channels:
            self.active_channel_id = next(iter(self.registered_channels))
            logger.info(f"No persisted state found. Defaulting active channel to first registered: {self.active_channel_id}")
        elif self.active_channel_id is None:
            logger.warning("No registered channels found. Bot will not respond to any channel messages.")

        # Keep a legacy alias for convenience in embed/should_respond
        self.channel_id = self.active_channel_id

        # Initialize CommandTree for application commands (slash commands) cleanup
        self.tree = discord.app_commands.CommandTree(self)

        logger.info(
            f"DanddobotClient initialized. Active channel: {self.active_channel_id}, "
            f"Registered channels: {list(self.registered_channels.keys())}, "
            f"Admin channel: {self.admin_channel_id}"
        )

    async def update_active_channel(self, new_channel_id: int):
        """Update the active chat channel and persist the change to state.json."""
        self.active_channel_id = new_channel_id
        self.channel_id = new_channel_id  # Keep alias in sync
        state_path = "config/state.json"
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"channel_id": new_channel_id}, f)
            logger.info(f"Persisted active_channel_id: {new_channel_id}")
        except Exception as e:
            logger.error(f"Failed to write state file: {e}")

    def reload_channels(self):
        """Reload the registered channels list from the config file."""
        self.registered_channels = load_registered_channels(self.channels_file_path)
        logger.info(f"Channels reloaded: {self.registered_channels}")



    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        
        # 1. Clean up existing slash commands (delete from all guilds and globally)
        logger.info("Cleaning up registered slash commands...")
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            logger.info("Cleared and synced global slash commands.")
            
            for guild in self.guilds:
                try:
                    self.tree.clear_commands(guild=guild)
                    await self.tree.sync(guild=guild)
                    logger.info(f"Cleared and synced slash commands for guild: {guild.name} (ID: {guild.id})")
                except Exception as guild_err:
                    logger.error(f"Failed to clear commands for guild {guild.name}: {guild_err}")
            logger.info("Slash command cleanup completed successfully.")
        except Exception as e:
            logger.error(f"Failed to complete slash command cleanup: {e}")

        # 2. Setup Persistent View and Send/Update Admin Dashboard
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

        logger.info("Bot is active and listening for messages.")

    def should_respond(self, message: discord.Message) -> bool:
        """
        Determines whether the bot should respond to a given message.
        This design isolates message filtering logic, allowing easy future additions
        such as role validation, blacklists, or rate limiting.
        """
        # 1. Ignore messages sent by the bot itself
        if message.author == self.user:
            return False

        # 2. Ignore messages in the admin channel (it is only for dashboard controls)
        if self.admin_channel_id and message.channel.id == self.admin_channel_id:
            return False

        # 3. Only respond in the currently active chat channel
        if not self.active_channel_id or message.channel.id != self.active_channel_id:
            return False

        # (Future extensions can be added here, e.g.)
        # - Ignore messages from specific roles
        # - Add message rate-limiting/throttling
        # - Ignore bots

        return True

    def load_persona(self) -> str:
        """
        Dynamically reads the persona prompt file to allow real-time prompt editing
        without restarting the container. If the file is missing or fails to load,
        returns a default system prompt.
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

    async def on_message(self, message: discord.Message):
        # Verify if we should handle this message
        if not self.should_respond(message):
            return

        user_content = message.content
        logger.info(f"Received message from {message.author} in target channel: '{user_content[:50]}...'")

        # Load system prompt dynamically (allows host-side modifications)
        system_prompt = self.load_persona()

        # Display typing status to the user while LLM generates the response
        async with message.channel.typing():
            try:
                # Call the local LLM via the adapted client
                response = await self.llm_client.generate_response(user_content, system_prompt)
            except Exception as e:
                logger.error(f"Failed to generate LLM response: {e}")
                response = "❌ 답변을 생성하는 동안 오류가 발생했습니다."

        # Send the response (handling Discord's 2000 character limit)
        chunks = self.split_message(response)
        for chunk in chunks:
            try:
                await message.reply(chunk)
            except Exception as e:
                logger.error(f"Failed to send message chunk: {e}")

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
            # If a single line is longer than the limit, break it by character count
            if len(line) > limit:
                # Flush the current chunk first if it exists
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Split the long line into limit-sized pieces
                temp_line = line
                while len(temp_line) > limit:
                    chunks.append(temp_line[:limit])
                    temp_line = temp_line[limit:]
                current_chunk = temp_line + "\n"
            # If adding this line exceeds the limit, flush the current chunk
            elif len(current_chunk) + len(line) + 1 > limit:
                chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
