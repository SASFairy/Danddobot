import time
import logging
import httpx
import discord
from discord import ui

from .embeds import build_dashboard_embed
from .selects import AdminChannelSelect, AdminProviderSelect, AdminModelSelect
from .modals import (
    PersonaEditModal,
    LlmTimeoutEditModal,
    MemoryLimitEditModal,
    LlmParametersEditModal,
    AdminMessageSendModal
)

logger = logging.getLogger("danddobot.admin.views")

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

        dist_users = getattr(client, "distinguish_users", True)
        self.toggle_distinguish_btn.label = "👤 사용자 구분: On" if dist_users else "👤 사용자 구분: Off"
        self.toggle_distinguish_btn.style = discord.ButtonStyle.success if dist_users else discord.ButtonStyle.secondary

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
        new_state = await self.client.settings.toggle_memory()
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
        new_state = await self.client.settings.toggle_debug_mode()
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

    @ui.button(label="👤 사용자 구분: Off", style=discord.ButtonStyle.secondary, custom_id="danddobot_admin_toggle_distinguish", row=0)
    async def toggle_distinguish_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Toggle distinguish requested by user {interaction.user}")
        new_state = await self.client.settings.toggle_distinguish_users()
        state_str = "활성화" if new_state else "비활성화"
        
        # Update button text and style dynamically
        button.label = "👤 사용자 구분: On" if new_state else "👤 사용자 구분: Off"
        button.style = discord.ButtonStyle.success if new_state else discord.ButtonStyle.secondary
        
        # Update dashboard embed and re-render the view components
        embed = build_dashboard_embed(self.client, status_msg=f"사용자 구분 {state_str}")
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(f"✅ 사용자 구분 기능이 **{state_str}** 되었습니다!", ephemeral=True)
