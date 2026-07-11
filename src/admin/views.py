import time
import logging
import httpx
import discord
from discord import ui

from .embeds import build_dashboard_embed
from .selects import AdminChannelSelect, AdminProviderSelect, AdminModelSelect, AdminCategorySelect
from .modals import (
    PersonaEditModal,
    LlmTimeoutEditModal,
    MemoryLimitEditModal,
    LlmParametersEditModal,
    AdminMessageSendModal,
    RagParametersEditModal
)

logger = logging.getLogger("danddobot.admin.views")

class AdminDashboardView(ui.View):
    """
    Dynamic category-tabbed button view attached to the admin dashboard embed.
    Allows clean categorization of features without reaching Discord's 5-row limits.
    """
    def __init__(self, client: discord.Client):
        super().__init__(timeout=None)  # Make it persistent (does not timeout)
        self.client = client
        self.current_category = "llm"  # Default tab on load
        
        # Populate components for the first time
        self.refresh_components()

    def refresh_components(self):
        """
        Clears existing items and dynamically populates appropriate components 
        based on the selected tab (current_category).
        """
        self.clear_items()
        
        # 1. Row 0: Category select dropdown (Always visible at the top)
        self.add_item(AdminCategorySelect(self.current_category))
        
        # 2. Dynamic loading based on the selected tab
        if self.current_category == "llm":
            # Select menus for channels and model selections (take Row 1, 2, 3)
            self.add_item(AdminChannelSelect(self.client, row=1))
            self.add_item(AdminProviderSelect(self.client, row=2))
            self.add_item(AdminModelSelect(self.client, row=3))
            
            # Action buttons for LLM generation parameters (Row 4)
            edit_timeout = ui.Button(
                label="⏱️ 타임아웃 설정", 
                style=discord.ButtonStyle.primary, 
                custom_id="danddobot_admin_timeout", 
                row=4
            )
            edit_timeout.callback = self.edit_timeout_btn
            self.add_item(edit_timeout)
            
            edit_params = ui.Button(
                label="📊 생성 옵션 설정", 
                style=discord.ButtonStyle.success, 
                custom_id="danddobot_admin_parameters", 
                row=4
            )
            edit_params.callback = self.edit_parameters_btn
            self.add_item(edit_params)

        elif self.current_category == "memory":
            # State-based memory toggle buttons (Row 1)
            use_mem = getattr(self.client, "use_memory", False)
            toggle_memory = ui.Button(
                label="🧠 대화 기억: On" if use_mem else "🧠 대화 기억: Off",
                style=discord.ButtonStyle.success if use_mem else discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_toggle_memory",
                row=1
            )
            toggle_memory.callback = self.toggle_memory_btn
            self.add_item(toggle_memory)

            dist_users = getattr(self.client, "distinguish_users", True)
            toggle_distinguish = ui.Button(
                label="👤 사용자 구분: On" if dist_users else "👤 사용자 구분: Off",
                style=discord.ButtonStyle.success if dist_users else discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_toggle_distinguish",
                row=1
            )
            toggle_distinguish.callback = self.toggle_distinguish_btn
            self.add_item(toggle_distinguish)

            # Capacity and diagnostics buttons (Row 2)
            edit_memory_limit = ui.Button(
                label="🔢 기억 용량 설정",
                style=discord.ButtonStyle.primary,
                custom_id="danddobot_admin_memory_limit",
                row=2
            )
            edit_memory_limit.callback = self.edit_memory_limit_btn
            self.add_item(edit_memory_limit)

            view_memory = ui.Button(
                label="📋 기억 내역 조회",
                style=discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_view_memory",
                row=2
            )
            view_memory.callback = self.view_memory_btn
            self.add_item(view_memory)

        elif self.current_category == "rag":
            # RAG Engine Activation Switch (Row 1)
            rag_enabled = self.client.rag_manager.is_enabled if hasattr(self.client, "rag_manager") else False
            toggle_rag = ui.Button(
                label="📖 RAG 엔진: On" if rag_enabled else "📖 RAG 엔진: Off",
                style=discord.ButtonStyle.success if rag_enabled else discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_toggle_rag",
                row=1
            )
            toggle_rag.callback = self.toggle_rag_btn
            self.add_item(toggle_rag)

            # Action button to trigger dyn-reloading of knowledge files (Row 1)
            reload_rag = ui.Button(
                label="🔄 RAG 지식 리로드",
                style=discord.ButtonStyle.primary,
                custom_id="danddobot_admin_reload_rag",
                row=1
            )
            reload_rag.callback = self.reload_rag_btn
            self.add_item(reload_rag)

            # Modal triggers for tuning top-k, chunk limits etc. (Row 1)
            edit_rag_limit = ui.Button(
                label="⚙️ RAG 상세설정",
                style=discord.ButtonStyle.success,
                custom_id="danddobot_admin_edit_rag_limit",
                row=1
            )
            edit_rag_limit.callback = self.edit_rag_limit_btn
            self.add_item(edit_rag_limit)

        elif self.current_category == "tools":
            # Debug switch and system diagnostics (Row 1)
            debug_mode = getattr(self.client, "debug_mode", False)
            toggle_debug = ui.Button(
                label="🔧 디버그 모드: On" if debug_mode else "🔧 디버그 모드: Off",
                style=discord.ButtonStyle.success if debug_mode else discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_toggle_debug",
                row=1
            )
            toggle_debug.callback = self.toggle_debug_btn
            self.add_item(toggle_debug)

            diagnose_system = ui.Button(
                label="🩺 시스템 진단",
                style=discord.ButtonStyle.secondary,
                custom_id="danddobot_admin_diagnose",
                row=1
            )
            diagnose_system.callback = self.diagnose_system_btn
            self.add_item(diagnose_system)

            send_message = ui.Button(
                label="📣 메시지 전송",
                style=discord.ButtonStyle.primary,
                custom_id="danddobot_admin_send_message",
                row=1
            )
            send_message.callback = self.send_message_btn
            self.add_item(send_message)

            # Persona direct edit modal trigger (Row 2)
            edit_persona = ui.Button(
                label="✏️ 페르소나 편집",
                style=discord.ButtonStyle.success,
                custom_id="danddobot_admin_edit",
                row=2
            )
            edit_persona.callback = self.edit_persona_btn
            self.add_item(edit_persona)

    # ==================== CALLBACKS ====================

    async def edit_persona_btn(self, interaction: discord.Interaction):
        logger.info(f"Edit persona modal requested by user {interaction.user}")
        modal = PersonaEditModal(self.client)
        await interaction.response.send_modal(modal)

    async def edit_timeout_btn(self, interaction: discord.Interaction):
        logger.info(f"Edit timeout modal requested by user {interaction.user}")
        modal = LlmTimeoutEditModal(self.client)
        await interaction.response.send_modal(modal)

    async def edit_parameters_btn(self, interaction: discord.Interaction):
        logger.info(f"Edit LLM parameters modal requested by user {interaction.user}")
        modal = LlmParametersEditModal(self.client)
        await interaction.response.send_modal(modal)

    async def diagnose_system_btn(self, interaction: discord.Interaction):
        logger.info(f"Diagnostics requested by user {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        discord_latency = round(self.client.latency * 1000)
        llm_status = "연결 실패"
        llm_latency_str = "N/A"
        
        if hasattr(self.client, "llm_client") and self.client.llm_client:
            llm_url = getattr(self.client.llm_client, "api_url", None)
            if llm_url:
                start_time = time.time()
                try:
                    async with httpx.AsyncClient(timeout=3.0) as http_client:
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

    async def toggle_memory_btn(self, interaction: discord.Interaction):
        logger.info(f"Toggle memory requested by user {interaction.user}")
        new_state = await self.client.settings.toggle_memory()
        state_str = "활성화" if new_state else "비활성화"
        
        # Re-render view to adapt label/style instantly
        self.refresh_components()
        
        embed = build_dashboard_embed(self.client, status_msg=f"대화 기억 {state_str}")
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ 대화 기억 기능이 **{state_str}** 되었습니다!", ephemeral=True)

    async def toggle_debug_btn(self, interaction: discord.Interaction):
        logger.info(f"Toggle debug requested by user {interaction.user}")
        new_state = await self.client.settings.toggle_debug_mode()
        state_str = "활성화" if new_state else "비활성화"
        
        self.refresh_components()
        
        embed = build_dashboard_embed(self.client, status_msg=f"디버그 모드 {state_str}")
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ 디버그 모드가 **{state_str}** 되었습니다!", ephemeral=True)

    async def edit_memory_limit_btn(self, interaction: discord.Interaction):
        logger.info(f"Edit memory limit modal requested by user {interaction.user}")
        modal = MemoryLimitEditModal(self.client)
        await interaction.response.send_modal(modal)

    async def view_memory_btn(self, interaction: discord.Interaction):
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
                if len(content) > 100:
                    content = content[:100] + "..."
                content_escaped = content.replace("`", "'").replace("\n", " ")
                report_lines.append(f"  • {role_label}: `{content_escaped}`")
            report_lines.append("")

        report_text = "\n".join(report_lines)
        if len(report_text) > 2000:
            report_text = report_text[:1990] + "\n...(이하 생략)..."

        await interaction.response.send_message(content=report_text, ephemeral=True)

    async def send_message_btn(self, interaction: discord.Interaction):
        logger.info(f"Arbitrary message send requested by user {interaction.user}")
        modal = AdminMessageSendModal(self.client)
        await interaction.response.send_modal(modal)

    async def toggle_distinguish_btn(self, interaction: discord.Interaction):
        logger.info(f"Toggle distinguish requested by user {interaction.user}")
        new_state = await self.client.settings.toggle_distinguish_users()
        state_str = "활성화" if new_state else "비활성화"
        
        self.refresh_components()
        
        embed = build_dashboard_embed(self.client, status_msg=f"사용자 구분 {state_str}")
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ 사용자 구분 기능이 **{state_str}** 되었습니다!", ephemeral=True)

    async def toggle_rag_btn(self, interaction: discord.Interaction):
        logger.info(f"Toggle RAG engine requested by user {interaction.user}")
        new_state = await self.client.settings.toggle_rag()
        state_str = "활성화" if new_state else "비활성화"
        
        self.refresh_components()
        
        embed = build_dashboard_embed(self.client, status_msg=f"RAG 지식 엔진 {state_str}")
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ RAG 지능형 지식 엔진이 **{state_str}** 되었습니다!", ephemeral=True)

    async def reload_rag_btn(self, interaction: discord.Interaction):
        logger.info(f"RAG knowledge reload requested by user {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        try:
            doc_cnt, chunk_cnt = self.client.rag_manager.reload_knowledge()
            
            self.refresh_components()
            embed = build_dashboard_embed(self.client, status_msg=f"RAG 지식 문서 ({doc_cnt}개) 동적 새로고침 완료")
            await interaction.message.edit(embed=embed, view=self)
            
            await interaction.followup.send(
                f"✅ **RAG 지식이 실시간으로 동적 리로드 되었습니다!**\n"
                f"• 로드된 지식 파일: `{doc_cnt}개`\n"
                f"• 색인된 검색용 청크: `{chunk_cnt}개` (청크 크기 한도: `{self.client.rag_manager.chunk_size}자`)\n\n"
                f"이제부터 사용자의 모든 대화는 새로 로딩된 지식 문서를 토대로 동작합니다. 📚",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Failed to reload RAG documents: {e}")
            await interaction.followup.send(f"❌ RAG 지식 새로고침 중 치명적 오류가 발생했습니다: `{e}`", ephemeral=True)

    async def edit_rag_limit_btn(self, interaction: discord.Interaction):
        logger.info(f"Edit RAG limits modal requested by user {interaction.user}")
        modal = RagParametersEditModal(self.client)
        await interaction.response.send_modal(modal)
