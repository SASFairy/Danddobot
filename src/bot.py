import json
import logging
import os
import asyncio
import io
import discord
import time
from typing import Dict, List, Optional
from src.state_manager import StateManager
from src.llm_client import BaseLLMClient
from src.utils.text_helper import split_message

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
                 cerebras_api_key: Optional[str] = None,
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
        self.cerebras_api_key = cerebras_api_key

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
        self.debug_mode: bool = self.state_manager.get_value("debug_mode", False)
        self.distinguish_users: bool = self.state_manager.get_value("distinguish_users", True)

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

        # Initialize cached persona prompt
        self.persona_prompt: str = self.load_persona()

        # Initialize CommandTree for application commands (slash commands)
        self.tree = discord.app_commands.CommandTree(self)

        # Initialize settings controller (Composition / Alternative 1)
        from src.bot_settings import BotSettingsController
        self.settings = BotSettingsController(self)

        logger.info(
            f"DanddobotClient initialized. Active channel: {self.active_channel_id}, "
            f"Registered channels: {list(self.registered_channels.keys())}, "
            f"Admin channel: {self.admin_channel_id}, "
            f"Log channel: {self.log_channel_id}, "
            f"Memory Enabled: {self.use_memory} (Max capacity: {self.max_memory_length}), "
            f"Debug Mode Enabled: {self.debug_mode}, "
            f"Distinguish Users Enabled: {self.distinguish_users}"
        )

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
        from src.admin import AdminDashboardView, build_dashboard_embed
        
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
            # If debug mode is active, the rich debug embed log is already sent to the log channel.
            # We skip sending this redundant raw text error message to prevent duplication.
            if self.debug_mode:
                logger.debug("Skipping redundant raw error message in log channel since debug mode is active.")
                return

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

            # Determine the user content prefix based on config
            if self.distinguish_users:
                user_content_for_llm = f"[{message.author.display_name}]: {user_content}"
            else:
                user_content_for_llm = user_content

            # Use cached system prompt (hot-reloaded dynamically from memory)
            system_prompt = self.persona_prompt

            # Load history context if memory is enabled
            history = None
            if self.use_memory:
                history = self.channel_history.get(message.channel.id, [])

            # Display typing status while LLM generates response
            llm_error = None
            response = None
            start_time = time.perf_counter()
            async with message.channel.typing():
                try:
                    response = await self.llm_client.generate_response(user_content_for_llm, system_prompt, history=history)
                except Exception as e:
                    logger.error(f"Failed to generate LLM response: {e}")
                    llm_error = e
            latency = time.perf_counter() - start_time

            # Dispatch debug log in background if debug mode is active
            if self.debug_mode:
                if llm_error is not None:
                    asyncio.create_task(
                        self.send_debug_log(
                            message=message,
                            prompt=user_content_for_llm,
                            response=None,
                            latency=latency,
                            is_error=True,
                            error_message=str(llm_error)
                        )
                    )
                else:
                    asyncio.create_task(
                        self.send_debug_log(
                            message=message,
                            prompt=user_content_for_llm,
                            response=response,
                            latency=latency,
                            is_error=False
                        )
                    )

            if llm_error is not None:
                await self._handle_llm_error(message, llm_error)
            else:
                # Save dialog to conversational history if memory is enabled
                if self.use_memory:
                    if message.channel.id not in self.channel_history:
                        self.channel_history[message.channel.id] = []
                    self.channel_history[message.channel.id].append({"role": "user", "content": user_content_for_llm})
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
                chunks = split_message(response)
                for idx, chunk in enumerate(chunks):
                    try:
                        if has_newer_messages and idx == 0:
                            await message.reply(chunk)
                        else:
                            await message.channel.send(chunk)
                    except Exception as e:
                        logger.error(f"Failed to send message chunk {idx}: {e}")


    async def send_debug_log(self, message: discord.Message, prompt: str, response: Optional[str], latency: float, is_error: bool = False, error_message: Optional[str] = None):
        """
        Builds and sends a premium Discord Embed log to the configured log channel.
        This must be safe, sliced, non-blocking, and handled gracefully.
        """
        if not self.log_channel_id:
            logger.debug("Debug logging triggered, but no log channel ID is configured.")
            return

        try:
            log_channel = self.get_channel(self.log_channel_id)
            if not log_channel:
                log_channel = await self.fetch_channel(self.log_channel_id)
            
            if not log_channel:
                logger.warning(f"Could not find or fetch log channel with ID: {self.log_channel_id}")
                return

            provider = "Unknown"
            model_name = "Unknown"
            if hasattr(self, "llm_client") and self.llm_client:
                provider = self.state_manager.get_value("llm_provider", "Unknown")
                model_name = getattr(self.llm_client, "model", "Unknown")

            # Create lists for any fallback text attachments
            files = []
            
            # Slice prompt for Discord Embed limits (1024 characters max per field value)
            if len(prompt) > 1000:
                prompt_bytes = io.BytesIO(prompt.encode('utf-8'))
                files.append(discord.File(fp=prompt_bytes, filename="full_prompt.txt"))
                safe_prompt = prompt[:1000] + "\n\n⚠️ 프롬프트가 너무 길어 전문은 첨부파일을 참조하십시오."
            else:
                safe_prompt = prompt
            
            if is_error:
                safe_response = f"❌ **오류 발생**: `{error_message}`"
                color = 0xE74C3C  # Red for error
                title = "🔧 디버그 로그 (실패)"
            else:
                raw_response = response or ""
                if len(raw_response) > 1000:
                    resp_bytes = io.BytesIO(raw_response.encode('utf-8'))
                    files.append(discord.File(fp=resp_bytes, filename="full_response.txt"))
                    safe_response = raw_response[:1000] + "\n\n⚠️ 답변이 너무 길어 전문은 첨부파일을 참조하십시오."
                else:
                    safe_response = raw_response
                color = 0x3498DB  # Blue for success
                title = "🔧 디버그 로그 (성공)"

            # Create Discord Embed
            embed = discord.Embed(
                title=title,
                color=color
            )

            # Metadata fields
            embed.add_field(name="👤 작성자", value=f"{message.author.mention} ({message.author.name})", inline=True)
            embed.add_field(name="💬 채널", value=f"{message.channel.mention} (ID: {message.channel.id})", inline=True)
            embed.add_field(name="⏱️ 소요 시간", value=f"`{latency:.3f}초`", inline=True)
            embed.add_field(name="🤖 백엔드 엔진", value=f"`{provider}`", inline=True)
            embed.add_field(name="📦 모델", value=f"`{model_name}`", inline=True)
            embed.add_field(name="🧠 메모리(대화 기록)", value=f"`{'활성화' if self.use_memory else '비활성화'}` (길이: {len(self.channel_history.get(message.channel.id, []))}/{self.max_memory_length})", inline=True)

            # Retrieve dynamic hyperparameters
            temp_val = getattr(self.llm_client, "temperature", None)
            temp_str = "기본값 (Default)" if temp_val is None else f"{temp_val}"
            max_tokens_val = getattr(self.llm_client, "max_tokens", None)
            max_tokens_str = "기본값 (Default)" if max_tokens_val is None else f"{max_tokens_val}"
            rep_penalty_val = getattr(self.llm_client, "repeat_penalty", None)
            rep_penalty_str = "기본값 (Default)" if rep_penalty_val is None else f"{rep_penalty_val}"
            top_p_val = getattr(self.llm_client, "top_p", None)
            top_p_str = "기본값 (Default)" if top_p_val is None else f"{top_p_val}"
            top_k_val = getattr(self.llm_client, "top_k", None)
            top_k_str = "기본값 (Default)" if top_k_val is None else f"{top_k_val}"
            
            hyperparams_summary = (
                f"🌡️ **온도 (Temperature)**: `{temp_str}`  |  🪙 **최대 토큰 (Max Tokens)**: `{max_tokens_str}`  |  🔁 **반복 패널티 (Repeat Penalty)**: `{rep_penalty_str}`\n"
                f"🎯 **Top-P (Nucleus)**: `{top_p_str}`  |  📦 **Top-K (Candidates)**: `{top_k_str}`"
            )
            embed.add_field(name="⚙️ 생성 하이퍼파라미터 (Generation Parameters)", value=hyperparams_summary, inline=False)

            # Prompt & Response fields
            embed.add_field(name="📝 프롬프트 (Raw Prompt)", value=f"```\n{safe_prompt}\n```", inline=False)
            embed.add_field(name="📤 생성된 답변 (Response)", value=f"```\n{safe_response}\n```", inline=False)

            if files:
                await log_channel.send(embed=embed, files=files)
            else:
                await log_channel.send(embed=embed)
            logger.debug("Successfully dispatched debug log embed to log channel.")
        except Exception as e:
            logger.error(f"Failed to send debug log embed: {e}")

    async def close(self):
        """Disposes of persistent client pools and logs out from Discord gateway."""
        if hasattr(self, "llm_client") and self.llm_client:
            await self.llm_client.close()
            logger.info("Closed LLM client connection pool.")
        await super().close()
