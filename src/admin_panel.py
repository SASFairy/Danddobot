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
        llm_info = f"**Provider**: `{provider}`\n**Model**: `{model}`"

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

    embed = discord.Embed(
        title="🤖 Danddobot 관리 대시보드",
        description="단또봇의 실시간 상태를 모니터링하고 설정을 변경할 수 있는 전용 채널 콘솔입니다.",
        color=0x2ECC71  # Emerald green
    )
    embed.add_field(name="🟢 시스템 상태", value=f"`{status_msg}`", inline=True)
    embed.add_field(name="💬 활성 대화 채널", value=channel_mention, inline=True)
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


class AdminChannelSelect(ui.Select):
    """
    Dropdown menu listing only the pre-registered channels from config/channels.txt.
    Allows the admin to switch the active chat channel between registered options.
    """
    def __init__(self, client: discord.Client):
        registered: dict = getattr(client, "registered_channels", {})
        active_id: int = getattr(client, "active_channel_id", None)

        options = []
        for channel_id, alias in list(registered.items())[:25]:
            options.append(discord.SelectOption(
                label=alias[:100],
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
            custom_id="danddobot_admin_channel_select"
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


class AdminDashboardView(ui.View):
    """
    Interactive button view attached to the admin dashboard embed.
    """
    def __init__(self, client: discord.Client):
        super().__init__(timeout=None)  # Make it persistent (does not timeout)
        self.client = client
        # Add the channel select dropdown menu to the view
        self.add_item(AdminChannelSelect(client))

    @ui.button(label="✏️ 페르소나 편집", style=discord.ButtonStyle.success, custom_id="danddobot_admin_edit")
    async def edit_persona_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Edit persona modal requested by user {interaction.user} in {interaction.channel}")
        modal = PersonaEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="🩺 시스템 진단", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_diagnose")
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
