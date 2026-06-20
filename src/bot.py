import logging
import os
import discord
from typing import List
from src.llm_client import BaseLLMClient

logger = logging.getLogger("danddobot.bot")

class DanddobotClient(discord.Client):
    """
    Discord Client for Danddobot. Handles receiving messages in a target channel,
    calling the local LLM with a live persona system prompt, and returning responses.
    """
    def __init__(self, channel_id: int, llm_client: BaseLLMClient, persona_file_path: str, *args, **kwargs):
        # We require message_content intents to read user messages
        intents = discord.Intents.default()
        intents.message_content = True
        kwargs["intents"] = intents
        
        super().__init__(*args, **kwargs)
        self.channel_id = channel_id
        self.llm_client = llm_client
        self.persona_file_path = persona_file_path
        
        logger.info(f"DanddobotClient initialized for channel_id: {self.channel_id}")

    async def on_ready(self):
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
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

        # 2. Respond to all messages in the specified channel
        if message.channel.id != self.channel_id:
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
