import os
import time
import logging
import httpx
import discord
from discord import ui
from typing import Optional

logger = logging.getLogger("danddobot.admin_panel")

def build_dashboard_embed(client: discord.Client, status_msg: str = "정상 작동 중") -> discord.Embed:
    """
    Builds a beautifully styled dashboard Embed with status and configuration details.
    """
    # Try to get channel names/mentions
    channel_mention = "미설정"
    if hasattr(client, "channel_id") and client.channel_id:
        channel_mention = f"<#{client.channel_id}>"

    llm_info = "미설정"
    if hasattr(client, "llm_client") and client.llm_client:
        provider = getattr(client.llm_client, "provider_name", client.llm_client.__class__.__name__.replace("Client", ""))
        model = getattr(client.llm_client, "model", "unknown")
        timeout_val = getattr(client.llm_client, "timeout", None)
        timeout_str = "무제한" if timeout_val is None else f"{timeout_val}초"
        
        temp_val = getattr(client.llm_client, "temperature", None)
        temp_str = "기본값" if temp_val is None else f"{temp_val}"
        max_tokens_val = getattr(client.llm_client, "max_tokens", None)
        max_tokens_str = "기본값" if max_tokens_val is None else f"{max_tokens_val}"
        rep_penalty_val = getattr(client.llm_client, "repeat_penalty", None)
        rep_penalty_str = "기본값" if rep_penalty_val is None else f"{rep_penalty_val}"
        
        llm_info = (
            f"**Provider**: `{provider}`\n"
            f"**Model**: `{model}`\n"
            f"**Timeout**: `{timeout_str}`\n"
            f"**Temperature**: `{temp_str}`\n"
            f"**Max Tokens**: `{max_tokens_str}`\n"
            f"**Repeat Penalty**: `{rep_penalty_str}`"
        )

    persona_path = getattr(client, "persona_file_path", "config/persona.txt")
    persona_status = "존재하지 않음"
    persona_size = 0
    if os.path.exists(persona_path):
        persona_size = os.path.getsize(persona_path)
        mtime = os.path.getmtime(persona_path)
        last_modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        persona_status = f"✅ 로드됨 ({persona_size} bytes)\n수정일: `{last_modified}`"
    else:
        persona_status = "❌ 파일 누락됨"

    max_mem = getattr(client, "max_memory_length", 10)
    turns = max_mem // 2
    memory_status = f"🟢 활성화 (최대 {max_mem}개 / {turns}회 대화)" if getattr(client, "use_memory", False) else "🔴 비활성화"

    debug_mode = getattr(client, "debug_mode", False)
    debug_status = "🟢 활성화" if debug_mode else "🔴 비활성화"

    embed = discord.Embed(
        title="🤖 Danddobot 관리 대시보드",
        description="단또봇의 실시간 상태를 모니터링하고 설정을 변경할 수 있는 전용 채널 콘솔입니다.",
        color=0x2ECC71  # Emerald green
    )
    embed.add_field(name="🟢 시스템 상태", value=f"`{status_msg}`", inline=True)
    embed.add_field(name="💬 활성 대화 채널", value=channel_mention, inline=True)
    embed.add_field(name="🧠 대화 기억 상태", value=f"`{memory_status}`", inline=True)
    embed.add_field(name="🔧 디버그 모드", value=f"`{debug_status}`", inline=True)
    embed.add_field(name="⏱️ Discord API 지연 시간", value=f"`{round(client.latency * 1000)}ms`", inline=True)
    embed.add_field(name="🧠 LLM 엔진 설정", value=llm_info, inline=False)
    embed.add_field(name="📄 페르소나 설정", value=persona_status, inline=False)
    embed.set_footer(text=f"마지막 업데이트: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed


class PersonaEditModal(ui.Modal, title="🤖 페르소나(시스템 프롬프트) 편집"):
    """
    Discord Modal to edit the persona file content directly in a popup.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        persona_path = getattr(client, "persona_file_path", "config/persona.txt")
        
        # Load current content
        current_content = ""
        if os.path.exists(persona_path):
            try:
                with open(persona_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
            except Exception as e:
                logger.error(f"Failed to read persona file: {e}")
        
        self.persona_input = ui.TextInput(
            label="페르소나 시스템 프롬프트 입력",
            style=discord.TextStyle.paragraph,
            placeholder="여기에 단또봇의 페르소나를 입력하세요...",
            default=current_content[:4000],  # Discord Modal text input limit is 4000 characters
            required=True,
            max_length=4000
        )
        self.add_item(self.persona_input)

    async def on_submit(self, interaction: discord.Interaction):
        persona_path = getattr(self.client, "persona_file_path", "config/persona.txt")
        new_content = self.persona_input.value
        
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(persona_path), exist_ok=True)
            with open(persona_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            logger.info(f"Persona updated via Modal by user {interaction.user} (ID: {interaction.user.id})")
            
            # Update the dashboard message
            embed = build_dashboard_embed(self.client, status_msg="페르소나 수정 및 재로드 완료")
            await interaction.message.edit(embed=embed)
            
            await interaction.response.send_message("✅ 페르소나가 성공적으로 수정 및 재로드되었습니다!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to write persona file: {e}")
            await interaction.response.send_message(f"❌ 페르소나 저장 중 오류가 발생했습니다: `{e}`", ephemeral=True)


class LlmTimeoutEditModal(ui.Modal, title="⏱️ LLM 타임아웃 시간 설정"):
    """
    Discord Modal to edit the LLM generation timeout value.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        current_timeout = getattr(getattr(client, "llm_client", None), "timeout", 300.0)
        default_val = "0" if current_timeout is None else str(current_timeout)
        
        self.timeout_input = ui.TextInput(
            label="타임아웃 시간 설정 (초 단위, 무제한은 0 이하 입력)",
            placeholder="예: 300.0 (기본값)",
            default=default_val,
            required=True,
            max_length=10
        )
        self.add_item(self.timeout_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        val_str = self.timeout_input.value.strip()
        
        try:
            new_val = float(val_str)
            if new_val <= 0:
                new_timeout = None
            else:
                new_timeout = new_val
        except ValueError:
            await interaction.response.send_message("❌ 올바른 숫자를 입력해 주세요.", ephemeral=True)
            return

        # Invoke encapsulated client API to update and persist
        await client.set_llm_timeout(new_timeout)

        # Update the dashboard message
        timeout_str = "무제한" if new_timeout is None else f"{new_timeout}초"
        embed = build_dashboard_embed(client, status_msg=f"타임아웃 변경 완료: {timeout_str}")
        await interaction.message.edit(embed=embed)
        
        await interaction.response.send_message(f"✅ LLM 타임아웃이 **{timeout_str}**(으)로 설정되었습니다!", ephemeral=True)


class MemoryLimitEditModal(ui.Modal, title="🔢 대화 기억 용량 설정"):
    """
    Discord Modal to edit the maximum memory context length (message count).
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        current_limit = getattr(client, "max_memory_length", 10)
        
        self.limit_input = ui.TextInput(
            label="기억할 최대 대화 메시지 수 (2~100 사이 입력)",
            placeholder="기본값: 10 (최근 5회 대화 기억)",
            default=str(current_limit),
            required=True,
            max_length=3
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        val_str = self.limit_input.value.strip()
        
        try:
            new_val = int(val_str)
            if new_val < 2 or new_val > 100:
                await interaction.response.send_message("❌ 대화 기억 용량은 2에서 100 사이의 숫자여야 합니다.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ 올바른 정수를 입력해 주세요.", ephemeral=True)
            return

        # Invoke encapsulated client API to update and persist
        await client.set_max_memory_length(new_val)

        # Rebuild dashboard view & edit message
        from src.admin_panel import build_dashboard_embed, AdminDashboardView
        embed = build_dashboard_embed(client, status_msg=f"기억 용량 변경 완료: {new_val}개")
        new_view = AdminDashboardView(client)
        await interaction.message.edit(embed=embed, view=new_view)
        
        await interaction.response.send_message(f"✅ 대화 기억 용량이 최대 **{new_val}개** (최근 {new_val // 2}회 대화)로 설정되었습니다!", ephemeral=True)


class LlmParametersEditModal(ui.Modal, title="⚙️ LLM 생성 옵션(하이퍼파라미터) 설정"):
    """
    Discord Modal to edit the LLM generation parameters dynamically.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        # Get current values
        current_temp = getattr(getattr(client, "llm_client", None), "temperature", None)
        current_max_tokens = getattr(getattr(client, "llm_client", None), "max_tokens", None)
        current_repeat_penalty = getattr(getattr(client, "llm_client", None), "repeat_penalty", None)
        
        self.temp_input = ui.TextInput(
            label="온도 (Temperature, 0.0 ~ 2.0 / 빈칸시 기본값)",
            placeholder="예: 0.7 (낮을수록 일관적, 높을수록 창의적)",
            default="" if current_temp is None else str(current_temp),
            required=False,
            max_length=5
        )
        self.max_tokens_input = ui.TextInput(
            label="최대 토큰 (Max Tokens / 빈칸시 기본값)",
            placeholder="예: 1024 (답변의 최대 길이 제한)",
            default="" if current_max_tokens is None else str(current_max_tokens),
            required=False,
            max_length=6
        )
        self.repeat_penalty_input = ui.TextInput(
            label="반복 패널티 (Repeat Penalty, 1.0 ~ 2.0 / 빈칸시 기본값)",
            placeholder="예: 1.1 (높을수록 중복 표현 억제)",
            default="" if current_repeat_penalty is None else str(current_repeat_penalty),
            required=False,
            max_length=5
        )
        
        self.add_item(self.temp_input)
        self.add_item(self.max_tokens_input)
        self.add_item(self.repeat_penalty_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        
        temp_val = None
        max_tokens_val = None
        rep_penalty_val = None
        
        # 1. Parse Temperature
        temp_str = self.temp_input.value.strip()
        if temp_str:
            try:
                temp_val = float(temp_str)
                if temp_val < 0.0 or temp_val > 2.0:
                    await interaction.response.send_message("❌ 온도는 0.0에서 2.0 사이의 숫자여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 온도는 올바른 실수여야 합니다.", ephemeral=True)
                return
                
        # 2. Parse Max Tokens
        max_tokens_str = self.max_tokens_input.value.strip()
        if max_tokens_str:
            try:
                max_tokens_val = int(max_tokens_str)
                if max_tokens_val <= 0:
                    await interaction.response.send_message("❌ 최대 토큰은 0보다 큰 정수여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 최대 토큰은 올바른 정수여야 합니다.", ephemeral=True)
                return
                
        # 3. Parse Repeat Penalty
        rep_penalty_str = self.repeat_penalty_input.value.strip()
        if rep_penalty_str:
            try:
                rep_penalty_val = float(rep_penalty_str)
                if rep_penalty_val < 1.0:
                    await interaction.response.send_message("❌ 반복 패널티는 1.0 이상의 숫자여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 반복 패널티는 올바른 실수여야 합니다.", ephemeral=True)
                return
                
        # Update and persist parameters
        await client.update_llm_parameters(
            temperature=temp_val,
            max_tokens=max_tokens_val,
            repeat_penalty=rep_penalty_val
        )
        
        # Rebuild dashboard view & edit message
        from src.admin_panel import build_dashboard_embed, AdminDashboardView
        embed = build_dashboard_embed(client, status_msg="LLM 생성 옵션 변경 완료")
        new_view = AdminDashboardView(client)
        await interaction.message.edit(embed=embed, view=new_view)
        
        # Prepare success message text
        status_lines = []
        status_lines.append(f"• **Temperature**: `{temp_val if temp_val is not None else '기본값'}`")
        status_lines.append(f"• **Max Tokens**: `{max_tokens_val if max_tokens_val is not None else '기본값'}`")
        status_lines.append(f"• **Repeat Penalty**: `{rep_penalty_val if rep_penalty_val is not None else '기본값'}`")
        status_summary = "\n".join(status_lines)
        
        await interaction.response.send_message(f"✅ LLM 생성 옵션이 성공적으로 변경되었습니다!\n{status_summary}", ephemeral=True)


class AdminMessageSendModal(ui.Modal, title="📣 활성 채널로 메시지 전송"):
    """
    Discord Modal to send an arbitrary message as Danddobot to the currently active channel.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        # Get active channel name
        active_id = getattr(client, "active_channel_id", None)
        active_name = "미설정"
        if active_id:
            discord_channel = client.get_channel(active_id)
            if discord_channel:
                active_name = f"#{discord_channel.name}"
            else:
                registered = getattr(client, "registered_channels", {})
                active_name = registered.get(active_id, f"채널 {active_id}")
                
        self.message_input = ui.TextInput(
            label=f"전송할 메시지 입력 (대상: {active_name})",
            style=discord.TextStyle.paragraph,
            placeholder="활성 대화 채널로 보낼 메시지를 입력하세요...",
            required=True,
            max_length=2000
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        active_id = getattr(client, "active_channel_id", None)
        
        if not active_id:
            await interaction.response.send_message("❌ 활성 대화 채널이 설정되어 있지 않습니다.", ephemeral=True)
            return
            
        channel = client.get_channel(active_id)
        if not channel:
            await interaction.response.send_message(f"❌ 활성 대화 채널(ID: {active_id})을 찾을 수 없거나 봇이 접근할 수 없습니다.", ephemeral=True)
            return
            
        content = self.message_input.value
        
        try:
            # Send the arbitrary message to the active channel
            await channel.send(content)
            logger.info(f"Admin {interaction.user} (ID: {interaction.user.id}) sent arbitrary message to active channel {active_id}: {content}")
            
            # Add to history if memory is active
            if getattr(client, "use_memory", False):
                if active_id not in client.channel_history:
                    client.channel_history[active_id] = []
                client.channel_history[active_id].append({"role": "assistant", "content": content})
                # Trim if needed
                max_len = getattr(client, "max_memory_length", 10)
                if len(client.channel_history[active_id]) > max_len:
                    client.channel_history[active_id] = client.channel_history[active_id][-max_len:]
            
            # Rebuild dashboard view & edit message to update status msg
            from src.admin_panel import build_dashboard_embed, AdminDashboardView
            embed = build_dashboard_embed(client, status_msg="메시지 대리 전송 완료")
            await interaction.message.edit(embed=embed)
            
            await interaction.response.send_message(f"✅ 활성 채널({channel.mention})로 메시지가 성공적으로 전송되었습니다!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send arbitrary message to active channel: {e}")
            await interaction.response.send_message(f"❌ 메시지 전송 중 오류가 발생했습니다: `{e}`", ephemeral=True)


class AdminChannelSelect(ui.Select):
    """
    Dropdown menu listing only the pre-registered channels from config/channels.txt.
    Allows the admin to switch the active chat channel between registered options.
    """
    def __init__(self, client: discord.Client):
        registered: dict = getattr(client, "registered_channels", {})
        active_id: int = getattr(client, "active_channel_id", None)

        options = []
        for channel_id in list(registered.keys())[:25]:
            discord_channel = client.get_channel(channel_id)
            if discord_channel and hasattr(discord_channel, "guild"):
                label = f"{discord_channel.guild.name} - #{discord_channel.name}"
            else:
                # Fallback to alias from txt if Discord can't resolve the channel
                label = registered.get(channel_id, f"채널 {channel_id}")

            options.append(discord.SelectOption(
                label=label[:100],
                value=str(channel_id),
                description=f"ID: {channel_id}",
                default=(channel_id == active_id)
            ))

        if not options:
            options.append(discord.SelectOption(
                label="등록된 채널 없음",
                value="none",
                description="config/channels.txt에 채널을 먼저 등록해 주세요."
            ))

        super().__init__(
            placeholder="💬 활성 대화 채널 선택...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="danddobot_admin_channel_select",
            row=2
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "⚠️ 등록된 채널이 없습니다. `config/channels.txt` 파일에 채널 ID를 먼저 등록해 주세요.",
                ephemeral=True
            )
            return

        client = interaction.client
        selected_channel_id = int(self.values[0])
        registered: dict = getattr(client, "registered_channels", {})
        alias = registered.get(selected_channel_id, f"채널 {selected_channel_id}")

        try:
            await client.update_active_channel(selected_channel_id)

            # Rebuild dashboard with updated view so dropdown default is refreshed
            from src.admin_panel import build_dashboard_embed, AdminDashboardView
            embed = build_dashboard_embed(client, status_msg=f"대화 채널 변경: {alias}")
            new_view = AdminDashboardView(client)
            await interaction.message.edit(embed=embed, view=new_view)

            discord_channel = client.get_channel(selected_channel_id)
            mention = discord_channel.mention if discord_channel else f"#{alias}"
            await interaction.response.send_message(
                f"✅ 활성 대화 채널이 **{alias}** ({mention})(으)로 변경되었습니다!",
                ephemeral=True
            )
            logger.info(f"Active channel switched to {selected_channel_id} ('{alias}') by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to change active channel: {e}")
            await interaction.response.send_message(
                f"❌ 대화 채널 변경 중 오류가 발생했습니다: `{e}`",
                ephemeral=True
            )


class AdminProviderSelect(ui.Select):
    """
    Dropdown menu listing available LLM providers configured in the environment (.env).
    Allows the admin to switch the active LLM provider dynamic and gracefully.
    """
    def __init__(self, client: discord.Client):
        provider_urls: dict[str, str] = getattr(client, "provider_urls", {})
        
        # Determine currently active provider name
        current_provider = "UNKNOWN"
        if hasattr(client, "llm_client") and client.llm_client:
            current_provider = getattr(client.llm_client, "provider_name", client.llm_client.__class__.__name__.replace("Client", "")).upper()

        options = []
        # provider_urls mapping has provider names as keys
        for provider_name, url in provider_urls.items():
            options.append(discord.SelectOption(
                label=provider_name.upper()[:100],
                value=provider_name.upper(),
                description=f"URL: {url[:100]}",
                default=(provider_name.upper() == current_provider)
            ))

        # Fallback if no provider URLs configured
        if not options:
            options.append(discord.SelectOption(
                label="설정된 프로바이더 없음",
                value="none",
                description="환경 설정(.env)에 API URL이 설정되어 있는지 확인해 주세요."
            ))

        super().__init__(
            placeholder="🧠 LLM 프로바이더 선택...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="danddobot_admin_provider_select",
            row=3
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "⚠️ 환경 변수에 설정된 다른 프로바이더가 없습니다.",
                ephemeral=True
            )
            return

        client = interaction.client
        selected_provider = self.values[0]

        try:
            # We defer since updating LLM client (closing pool and re-opening) might take a second or two
            await interaction.response.defer(ephemeral=True)

            await client.update_llm_provider(selected_provider)

            # Rebuild dashboard with updated view so dropdown default and model choices are refreshed
            from src.admin_panel import build_dashboard_embed, AdminDashboardView
            embed = build_dashboard_embed(client, status_msg=f"LLM 프로바이더 변경: {selected_provider}")
            new_view = AdminDashboardView(client)
            await interaction.message.edit(embed=embed, view=new_view)

            await interaction.followup.send(
                f"✅ LLM 프로바이더가 **{selected_provider}**(으)로 변경되었습니다!",
                ephemeral=True
            )
            logger.info(f"LLM provider switched to {selected_provider} by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to change LLM provider: {e}")
            await interaction.followup.send(
                f"❌ LLM 프로바이더 변경 중 오류가 발생했습니다: `{e}`",
                ephemeral=True
            )


class AdminModelSelect(ui.Select):
    """
    Dropdown menu listing available models fetched from the LLM backend on startup.
    Allows the admin to switch the active LLM model.
    """
    def __init__(self, client: discord.Client):
        available_models: list[str] = getattr(client, "available_models", [])
        current_model: str = "unknown"
        if hasattr(client, "llm_client") and client.llm_client:
            current_model = getattr(client.llm_client, "model", "unknown")

        # Fallback if available_models is empty
        if not available_models:
            available_models = [current_model] if current_model != "unknown" else ["llama3"]

        options = []
        for model_name in available_models[:25]:  # Discord selects allow up to 25 options
            options.append(discord.SelectOption(
                label=model_name[:100],
                value=model_name,
                description=f"Model: {model_name}",
                default=(model_name == current_model)
            ))

        super().__init__(
            placeholder="🧠 LLM 모델 선택...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="danddobot_admin_model_select",
            row=4
        )

    async def callback(self, interaction: discord.Interaction):
        client = interaction.client
        selected_model = self.values[0]

        try:
            await client.update_llm_model(selected_model)

            # Rebuild dashboard with updated view so dropdown default is refreshed
            from src.admin_panel import build_dashboard_embed, AdminDashboardView
            embed = build_dashboard_embed(client, status_msg=f"LLM 모델 변경: {selected_model}")
            new_view = AdminDashboardView(client)
            await interaction.message.edit(embed=embed, view=new_view)

            await interaction.response.send_message(
                f"✅ LLM 모델이 **{selected_model}**(으)로 변경되었습니다!",
                ephemeral=True
            )
            logger.info(f"LLM model switched to {selected_model} by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to change LLM model: {e}")
            await interaction.response.send_message(
                f"❌ LLM 모델 변경 중 오류가 발생했습니다: `{e}`",
                ephemeral=True
            )


class AdminDashboardView(ui.View):
    """
    Interactive button view attached to the admin dashboard embed.
    """
    def __init__(self, client: discord.Client):
        super().__init__(timeout=None)  # Make it persistent (does not timeout)
        self.client = client
        # Add the channel select dropdown menu to the view
        self.add_item(AdminChannelSelect(client))
        # Add the provider select dropdown menu to the view
        self.add_item(AdminProviderSelect(client))
        # Add the model select dropdown menu to the view
        self.add_item(AdminModelSelect(client))

        # Set dynamic initial button label and style based on state
        use_mem = getattr(client, "use_memory", False)
        self.toggle_memory_btn.label = "🧠 대화 기억: On" if use_mem else "🧠 대화 기억: Off"
        self.toggle_memory_btn.style = discord.ButtonStyle.success if use_mem else discord.ButtonStyle.secondary

        debug_mode = getattr(client, "debug_mode", False)
        self.toggle_debug_btn.label = "🔧 디버그 모드: On" if debug_mode else "🔧 디버그 모드: Off"
        self.toggle_debug_btn.style = discord.ButtonStyle.success if debug_mode else discord.ButtonStyle.secondary

    @ui.button(label="✏️ 페르소나 편집", style=discord.ButtonStyle.success, custom_id="danddobot_admin_edit", row=0)
    async def edit_persona_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Edit persona modal requested by user {interaction.user} in {interaction.channel}")
        modal = PersonaEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="⏱️ 타임아웃 설정", style=discord.ButtonStyle.primary, custom_id="danddobot_admin_timeout", row=0)
    async def edit_timeout_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Edit timeout modal requested by user {interaction.user} in {interaction.channel}")
        modal = LlmTimeoutEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="⚙️ 생성 옵션", style=discord.ButtonStyle.success, custom_id="danddobot_admin_parameters", row=0)
    async def edit_parameters_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Edit LLM parameters modal requested by user {interaction.user} in {interaction.channel}")
        modal = LlmParametersEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="🩺 시스템 진단", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_diagnose", row=0)
    async def diagnose_system_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Diagnostics requested by user {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        # 1. Check API Latency
        discord_latency = round(self.client.latency * 1000)
        
        # 2. Check LLM Server Connection
        llm_status = "연결 실패"
        llm_latency_str = "N/A"
        
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            llm_url = getattr(self.client.llm_client, "api_url", None)
            if llm_url:
                start_time = time.time()
                try:
                    # Let's perform a lightweight request to verify the server is listening
                    async with httpx.AsyncClient(timeout=3.0) as http_client:
                        # Depending on provider, check roots or health endpoint
                        response = await http_client.get(llm_url)
                        llm_latency = round((time.time() - start_time) * 1000)
                        llm_status = f"연결 성공 (HTTP {response.status_code})"
                        llm_latency_str = f"{llm_latency}ms"
                except Exception as e:
                    llm_status = f"연결 실패: {e.__class__.__name__}"
            else:
                llm_status = "LLM API URL 미설정"
        else:
            llm_status = "LLM 클라이언트 연결되지 않음"

        diagnostic_report = (
            "🛠️ **Danddobot 자가 진단 보고서**\n"
            f"• **Discord 게이트웨이 지연 시간**: `{discord_latency}ms`\n"
            f"• **로컬 LLM 서버 상태**: `{llm_status}`\n"
            f"• **로컬 LLM 서버 응답 속도**: `{llm_latency_str}`\n"
            f"• **최근 진단 시각**: `{time.strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        
        await interaction.followup.send(content=diagnostic_report, ephemeral=True)

    @ui.button(label="🧠 대화 기억: Off", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_toggle_memory", row=1)
    async def toggle_memory_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Toggle memory requested by user {interaction.user}")
        new_state = await self.client.toggle_memory()
        state_str = "활성화" if new_state else "비활성화"
        
        # Update button text and style dynamically
        button.label = "🧠 대화 기억: On" if new_state else "🧠 대화 기억: Off"
        button.style = discord.ButtonStyle.success if new_state else discord.ButtonStyle.secondary
        
        # Update dashboard embed and re-render the view components
        embed = build_dashboard_embed(self.client, status_msg=f"대화 기억 {state_str}")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"✅ 대화 기억 기능이 **{state_str}** 되었습니다!", ephemeral=True)

    @ui.button(label="🔧 디버그 모드: Off", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_toggle_debug", row=1)
    async def toggle_debug_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Toggle debug requested by user {interaction.user}")
        new_state = await self.client.toggle_debug_mode()
        state_str = "활성화" if new_state else "비활성화"
        
        # Update button text and style dynamically
        button.label = "🔧 디버그 모드: On" if new_state else "🔧 디버그 모드: Off"
        button.style = discord.ButtonStyle.success if new_state else discord.ButtonStyle.secondary
        
        # Update dashboard embed and re-render the view components
        embed = build_dashboard_embed(self.client, status_msg=f"디버그 모드 {state_str}")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"✅ 디버그 모드가 **{state_str}** 되었습니다!", ephemeral=True)

    @ui.button(label="🔢 기억 용량 설정", style=discord.ButtonStyle.primary, custom_id="danddobot_admin_memory_limit", row=1)
    async def edit_memory_limit_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Edit memory limit modal requested by user {interaction.user} in {interaction.channel}")
        modal = MemoryLimitEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="📋 기억 내역 조회", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_view_memory", row=1)
    async def view_memory_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Memory history lookup requested by user {interaction.user}")
        
        histories = getattr(self.client, "channel_history", {})
        if not histories or all(not msgs for msgs in histories.values()):
            await interaction.response.send_message(
                "🧠 **현재 저장된 대화 기억(Context Memory)이 비어 있습니다.**",
                ephemeral=True
            )
            return

        report_lines = ["🧠 **Danddobot 실시간 대화 기억 내역**\n"]
        for channel_id, messages in histories.items():
            if not messages:
                continue
            channel_name = f"<#{channel_id}>"
            report_lines.append(f"📍 **채널**: {channel_name} (ID: {channel_id})")
            
            for msg in messages:
                role_label = "👤 **User**" if msg["role"] == "user" else "🤖 **Bot**"
                content = msg["content"]
                # Limit the lines of content if too long
                if len(content) > 100:
                    content = content[:100] + "..."
                # Escape markdown formatting inside content to prevent mess
                content_escaped = content.replace("`", "'").replace("\n", " ")
                report_lines.append(f"  • {role_label}: `{content_escaped}`")
            report_lines.append("") # Spacer line

        report_text = "\n".join(report_lines)
        if len(report_text) > 2000:
            report_text = report_text[:1990] + "\n...(이하 생략)..."

        await interaction.response.send_message(content=report_text, ephemeral=True)

    @ui.button(label="📣 메시지 전송", style=discord.ButtonStyle.primary, custom_id="danddobot_admin_send_message", row=1)
    async def send_message_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Arbitrary message send requested by user {interaction.user}")
        modal = AdminMessageSendModal(self.client)
        await interaction.response.send_modal(modal)
