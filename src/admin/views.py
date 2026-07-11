import time
import logging
import httpx
import os
import asyncio
import discord
from discord import ui

from .embeds import build_dashboard_embed
from .selects import AdminChannelSelect, AdminProviderSelect, AdminModelSelect, AdminCategorySelect, AdminRagFileSelect
from .modals import (
    PersonaEditModal,
    LlmTimeoutEditModal,
    MemoryLimitEditModal,
    LlmParametersEditModal,
    AdminMessageSendModal,
    RagParametersEditModal,
    RagFileCreateModal,
    RagFileEditModal
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
        self.selected_rag_file = None  # Currently selected RAG file for CRUD operations
        self.message = None  # Back-reference to the dashboard message
        
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

            # Dynamic RAG File Select Dropdown (Row 2)
            self.add_item(AdminRagFileSelect(self.client, selected_file=self.selected_rag_file, row=2))

            # Selected File Action Controls (Row 3 - visible only when a file is selected)
            if self.selected_rag_file and self.selected_rag_file != "none":
                edit_file = ui.Button(
                    label=f"✏️ [{self.selected_rag_file[:12]}] 내용 수정",
                    style=discord.ButtonStyle.success,
                    custom_id="danddobot_admin_edit_selected_rag_file",
                    row=3
                )
                edit_file.callback = self.edit_selected_rag_file_btn
                self.add_item(edit_file)

                delete_file = ui.Button(
                    label="🗑️ 파일 영구 삭제",
                    style=discord.ButtonStyle.danger,
                    custom_id="danddobot_admin_delete_selected_rag_file",
                    row=3
                )
                delete_file.callback = self.delete_selected_rag_file_btn
                self.add_item(delete_file)

            # File additions / Drag-and-Drop listeners (Row 4)
            create_file = ui.Button(
                label="➕ 신규 지식 직접 작성",
                style=discord.ButtonStyle.primary,
                custom_id="danddobot_admin_create_rag_file",
                row=4
            )
            create_file.callback = self.create_rag_file_btn
            self.add_item(create_file)

            upload_file = ui.Button(
                label="📤 대형 파일 업로드 (채팅)",
                style=discord.ButtonStyle.success,
                custom_id="danddobot_admin_upload_rag_file",
                row=4
            )
            upload_file.callback = self.upload_rag_file_btn
            self.add_item(upload_file)

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

    # ==================== RAG CRUD OPERATIONS ====================

    async def create_rag_file_btn(self, interaction: discord.Interaction):
        logger.info(f"Create RAG file modal requested by user {interaction.user}")
        modal = RagFileCreateModal(self.client)
        await interaction.response.send_modal(modal)

    async def upload_rag_file_btn(self, interaction: discord.Interaction):
        logger.info(f"Upload RAG file flow requested by user {interaction.user}")
        await self._handle_file_upload_flow(interaction)

    async def edit_selected_rag_file_btn(self, interaction: discord.Interaction):
        filename = self.selected_rag_file
        if not filename or filename == "none":
            await interaction.response.send_message("❌ 먼저 관리할 RAG 지식 파일을 드롭다운에서 선택해 주세요.", ephemeral=True)
            return
            
        knowledge_dir = getattr(self.client.rag_manager, "knowledge_dir", "config/knowledge")
        file_path = os.path.join(knowledge_dir, filename)
        
        if not os.path.exists(file_path):
            await interaction.response.send_message("❌ 지정된 지식 파일이 디스크에 존재하지 않습니다.", ephemeral=True)
            return
            
        # Inspect size of file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            char_count = len(content)
        except Exception as e:
            await interaction.response.send_message(f"❌ 파일을 읽는 중 오류가 발생했습니다: `{e}`", ephemeral=True)
            return

        if char_count <= 3800:
            # Safe size: Open standard direct editing modal
            modal = RagFileEditModal(self.client, filename)
            await interaction.response.send_modal(modal)
        else:
            # Over 3800 characters: Safety guard download / overwrite upload flow
            await interaction.response.defer(ephemeral=True)
            
            embed = discord.Embed(
                title="⚠️ 대형 지식 파일 직접 수정 제약 안내",
                description=(
                    f"선택하신 지식 파일 `{filename}`은 총 **{char_count:,}자**로, "
                    f"디스코드 입력 한계인 **4,000자**를 거의 초과하거나 상회합니다.\n\n"
                    f"디스코드 모달창으로 직접 편집할 경우 **텍스트 잘림으로 인한 지식 손실**이 발생할 수 있어 직접 편집이 안전하게 차단되었습니다.\n"
                    f"대신 아래의 다운로드/덮어쓰기 도구를 이용해 안전하게 다듬어 주세요! 🛡️"
                ),
                color=discord.Color.orange()
            )
            
            # Sub-view inside ephemeral message for downloading and uploading overwrites
            class LargeFileActionView(ui.View):
                def __init__(self, outer_view, filename, file_path):
                    super().__init__(timeout=120)
                    self.outer_view = outer_view
                    self.filename = filename
                    self.file_path = file_path
                    
                @ui.button(label="📥 지식 파일 다운로드", style=discord.ButtonStyle.primary)
                async def download_btn(self, btn_interaction: discord.Interaction, btn: ui.Button):
                    await btn_interaction.response.defer(ephemeral=True)
                    try:
                        file_to_send = discord.File(self.file_path, filename=self.filename)
                        await btn_interaction.followup.send(
                            content=f"📥 **`{self.filename}`** 지식 파일 다운로드 파일이 아래에 첨부되었습니다. PC에서 메모장 등으로 자유롭게 수정 후 덮어쓰기 업로드를 해주세요!",
                            file=file_to_send,
                            ephemeral=True
                        )
                    except Exception as e:
                        await btn_interaction.followup.send(f"❌ 파일 전송 중 오류 발생: `{e}`", ephemeral=True)
                        
                @ui.button(label="📤 수정본 덮어쓰기 (업로드)", style=discord.ButtonStyle.success)
                async def upload_overwrite_btn(self, btn_interaction: discord.Interaction, btn: ui.Button):
                    await self.outer_view._handle_file_upload_flow(btn_interaction, overwrite_filename=self.filename)
                    
            await interaction.followup.send(embed=embed, view=LargeFileActionView(self, filename, file_path), ephemeral=True)

    async def delete_selected_rag_file_btn(self, interaction: discord.Interaction):
        filename = self.selected_rag_file
        if not filename or filename == "none":
            await interaction.response.send_message("❌ 삭제할 지식 파일을 먼저 선택해 주세요.", ephemeral=True)
            return
            
        # Bind message reference to update main dashboard later
        self.message = interaction.message

        # Double-check confirmation subview (Red Confirm, Gray Cancel)
        class ConfirmDeleteView(ui.View):
            def __init__(self, outer_view, filename):
                super().__init__(timeout=30)
                self.outer_view = outer_view
                self.filename = filename
                
            @ui.button(label="💥 예, 영구 삭제합니다", style=discord.ButtonStyle.danger)
            async def confirm(self, btn_interaction: discord.Interaction, btn: ui.Button):
                client = self.outer_view.client
                knowledge_dir = getattr(client.rag_manager, "knowledge_dir", "config/knowledge")
                file_path = os.path.join(knowledge_dir, self.filename)
                
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        
                    # Reload knowledge
                    client.rag_manager.reload_knowledge()
                    
                    # Refresh outer dashboard view
                    self.outer_view.selected_rag_file = None
                    self.outer_view.refresh_components()
                    
                    from .embeds import build_dashboard_embed
                    embed = build_dashboard_embed(client, status_msg=f"지식 파일 영구 삭제 완료: {self.filename}")
                    await btn_interaction.response.edit_message(content=f"✅ `{self.filename}` 지식이 영구 삭제되었습니다.", embed=None, view=None)
                    await self.outer_view.message.edit(embed=embed, view=self.outer_view)
                except Exception as e:
                    await btn_interaction.response.send_message(f"❌ 파일 삭제 중 치명적 오류 발생: `{e}`", ephemeral=True)
                    
            @ui.button(label="취소", style=discord.ButtonStyle.secondary)
            async def cancel(self, btn_interaction: discord.Interaction, btn: ui.Button):
                await btn_interaction.response.edit_message(content="❌ 삭제 작업이 취소되었습니다.", embed=None, view=None)
                
        confirm_embed = discord.Embed(
            title="⚠️ RAG 지식 파일 영구 삭제 경고",
            description=(
                f"정말로 지식 문서 **`{filename}`**을 영구 삭제하시겠습니까?\n\n"
                f"삭제 시 디스크에서 파일이 즉시 제거되어 되돌릴 수 없으며, "
                f"RAG 검색 참고 정보에서 영구 격리됩니다."
            ),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=confirm_embed, view=ConfirmDeleteView(self, filename), ephemeral=True)

    async def _handle_file_upload_flow(self, interaction: discord.Interaction, overwrite_filename: str = None):
        """
        Handles the asynchronous wait_for file attachment upload loop in Discord.
        """
        await interaction.response.defer(ephemeral=True)
        
        prompt_text = (
            f"📤 **RAG 지식 파일 업로드 대기 시작**\n\n"
            f"**60초 이내**에 어드민 채널 채팅바 왼쪽에 있는 **(+) 버튼**을 눌러 컴퓨터의 `.txt` 파일을 전송해 주시거나, "
            f"이곳 채팅창으로 파일을 직접 끌어다(Drag & Drop) 던져 주세요!\n\n"
        )
        if overwrite_filename:
            prompt_text += f"⚠️ 완료 시 선택하신 기존 **`{overwrite_filename}`** 파일 내용이 새 파일로 즉시 덮어씌워집니다."
        else:
            prompt_text += f"📝 전송받은 텍스트 파일명 그대로 신규 RAG 지식 문서로 등록됩니다."
            
        prompt_msg = await interaction.followup.send(content=prompt_text, ephemeral=True)
        
        # Check function to filter correct message attachments
        def check(m):
            return (
                m.author.id == interaction.user.id and 
                m.channel.id == interaction.channel.id and 
                len(m.attachments) > 0
            )
            
        try:
            # Wait for file for up to 60 seconds
            message = await self.client.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ **업로드 시간이 초과되었습니다.** 작업을 취소합니다. 다시 시도해 주세요.", ephemeral=True)
            return
            
        attachment = message.attachments[0]
        filename = overwrite_filename or attachment.filename
        
        if not filename.endswith(".txt"):
            await interaction.followup.send("❌ **.txt 형식의 텍스트 파일만 RAG 지식으로 등록할 수 있습니다.**", ephemeral=True)
            return
            
        # Alphanumeric, underscores, hyphens, and dots only for security (Path traversal guard)
        import re
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
            await interaction.followup.send("❌ 파일명에 허용되지 않는 특수문자가 감지되었습니다. 영문, 숫자, -, _, . 만 사용해 주세요.", ephemeral=True)
            return
            
        # Download and save the file
        knowledge_dir = getattr(self.client.rag_manager, "knowledge_dir", "config/knowledge")
        file_path = os.path.join(knowledge_dir, filename)
        
        try:
            # Read attachment content
            file_bytes = await attachment.read()
            content = file_bytes.decode('utf-8')
            
            os.makedirs(knowledge_dir, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            # Try to delete the uploaded message from the admin channel to keep it clean!
            try:
                await message.delete()
            except Exception:
                pass
                
            # Reload knowledge base
            doc_cnt, chunk_cnt = self.client.rag_manager.reload_knowledge()
            
            # Save original dashboard message reference
            self.message = interaction.message
            
            # Refresh components & dashboard embed
            self.selected_rag_file = filename
            self.refresh_components()
            
            from .embeds import build_dashboard_embed
            embed = build_dashboard_embed(self.client, status_msg=f"파일 업로드 완료: {filename}")
            await self.message.edit(embed=embed, view=self)
            
            await interaction.followup.send(
                f"✅ **RAG 지식 파일 업로드 및 색인이 성공적으로 완료되었습니다!**\n"
                f"• 파일명: `{filename}`\n"
                f"• 글자 수: `{len(content):,}자`\n"
                f"• 적용 모드: `{'덮어쓰기(Overwrite)' if overwrite_filename else '신규 등록(Create)'}`\n\n"
                f"지식 베이스 리로드가 즉각 완료되었습니다! 📚",
                ephemeral=True
            )
            logger.info(f"RAG file '{filename}' uploaded/overwritten via chat attachment by {interaction.user}")
        except UnicodeDecodeError:
            await interaction.followup.send("❌ 파일 디코딩 실패: 반드시 **UTF-8** 인코딩 형식의 텍스트(.txt) 파일로 저장해 업로드해 주세요.", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to process uploaded file: {e}")
            await interaction.followup.send(f"❌ 파일 저장 중 내부 서버 오류가 발생했습니다: `{e}`", ephemeral=True)


class GameDbEditModal(ui.Modal, title="✏️ 미니게임 DB JSON 직접 수정"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        db = getattr(client, "db", None)
        current_json = "{}"
        if db and os.path.exists(db.db_path):
            try:
                with open(db.db_path, "r", encoding="utf-8") as f:
                    current_json = f.read()
            except Exception:
                pass
                
        self.json_input = ui.TextInput(
            label="JSON 데이터 수정 (주의해서 변경해 주세요!)",
            style=discord.TextStyle.paragraph,
            default=current_json,
            required=True,
            max_length=4000
        )
        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            import json
            new_data = json.loads(self.json_input.value)
            if not isinstance(new_data, dict) or "users" not in new_data:
                await interaction.followup.send("❌ **올바른 형식의 미니게임 DB JSON 구조가 아닙니다.** 최상위 레벨에 `\"users\"` 키가 포함되어야 합니다옹!", ephemeral=True)
                return
                
            db = getattr(self.client, "db", None)
            if db:
                async with db.get_lock():
                    db.data = new_data
                    await db._save_data()
                    
                from .embeds import build_game_admin_embed
                embed = await build_game_admin_embed(self.client)
                await interaction.message.edit(embed=embed, view=interaction.message.components[0].view if interaction.message.components else None)
                
                await interaction.followup.send(
                    f"✅ **미니게임 JSON 데이터베이스 직접 수정 성공!**\n"
                    f"• 등록된 총 사용자 수: `{len(new_data['users'])}명`\n"
                    f"• 변경된 데이터가 대시보드 및 서버 저장소에 즉시 적용되었습니다옹!",
                    ephemeral=True
                )
                logger.warning(f"Database manually edited via Discord modal by {interaction.user}")
        except json.JSONDecodeError as je:
            await interaction.followup.send(f"❌ **JSON 파일 문법 오류:** 입력하신 내용에 문법적 문제가 있습니다. 문장 부호(쉼표, 중괄호 등)를 다시 확인해 주세요!\n`오류: {je}`", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to process direct modal edit: {e}")
            await interaction.followup.send(f"❌ 데이터베이스 수정 적용 중 오류가 발생했습니다: `{e}`", ephemeral=True)


class GameItemDbEditModal(ui.Modal, title="🛍️ 아이템 DB JSON 직접 수정"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        item_db = getattr(client, "item_db", None)
        current_json = "{}"
        if item_db and os.path.exists(item_db.db_path):
            try:
                with open(item_db.db_path, "r", encoding="utf-8") as f:
                    current_json = f.read()
            except Exception:
                pass
                
        self.json_input = ui.TextInput(
            label="아이템 DB JSON 수정 (참치 통조림, 츄르 등)",
            style=discord.TextStyle.paragraph,
            default=current_json,
            required=True,
            max_length=4000
        )
        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            import json
            new_data = json.loads(self.json_input.value)
            if not isinstance(new_data, dict) or "items" not in new_data:
                await interaction.followup.send("❌ **올바른 형식의 아이템 DB JSON 구조가 아닙니다.** 최상위 레벨에 `\"items\"` 키가 포함되어야 합니다옹!", ephemeral=True)
                return
                
            item_db = getattr(self.client, "item_db", None)
            if item_db:
                async with item_db.get_lock():
                    item_db.data = new_data
                    await item_db._save_data()
                    
                await interaction.followup.send(
                    f"✅ **아이템 DB JSON 직접 수정 성공!**\n"
                    f"• 등록된 총 아이템 수: `{len(new_data['items'])}개`\n"
                    f"• 변경된 데이터가 상점 및 데이터베이스 파일에 즉시 적용되었습니다옹!",
                    ephemeral=True
                )
                logger.warning(f"Item Database manually edited via Discord modal by {interaction.user}")
        except json.JSONDecodeError as je:
            await interaction.followup.send(f"❌ **JSON 파일 문법 오류:** 입력하신 내용에 문법적 문제가 있습니다. 문장 부호(쉼표, 중괄호 등)를 다시 확인해 주세요!\n`오류: {je}`", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to process direct item modal edit: {e}")
            await interaction.followup.send(f"❌ 아이템 DB 수정 적용 중 오류가 발생했습니다: `{e}`", ephemeral=True)


class GameAdminDashboardView(ui.View):
    """
    Interactive button view attached to the mini-game admin dashboard embed.
    """
    def __init__(self, client: discord.Client):
        super().__init__(timeout=None)  # Persistent across bot reboots
        self.client = client

    @ui.button(label="✏️ DB 직접 수정", style=discord.ButtonStyle.primary, custom_id="danddobot_game_admin_db_edit", row=0)
    async def edit_db_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Admin JSON database direct edit requested by {interaction.user}")
        db = getattr(self.client, "db", None)
        if db and os.path.exists(db.db_path):
            file_len = os.path.getsize(db.db_path)
            if file_len > 3800:
                await interaction.response.send_message(
                    "⚠️ **DB 파일 용량이 너무 커서(4000자 초과) 모달에서 직접 수정할 수 없다냥!**\n"
                    "대신 옆에 있는 **`📤 DB 다운로드`**와 **`📥 DB 업로드`** 버튼을 이용해 안전하고 편리하게 편집해 주세요옹!",
                    ephemeral=True
                )
                return
        
        modal = GameDbEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="🛍️ 아이템 DB 수정", style=discord.ButtonStyle.success, custom_id="danddobot_game_admin_item_db_edit", row=0)
    async def edit_item_db_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Admin Item database direct edit requested by {interaction.user}")
        item_db = getattr(self.client, "item_db", None)
        if item_db and os.path.exists(item_db.db_path):
            file_len = os.path.getsize(item_db.db_path)
            if file_len > 3800:
                await interaction.response.send_message(
                    "⚠️ **아이템 DB 파일 용량이 너무 커서(4000자 초과) 모달에서 직접 수정할 수 없다냥!**\n"
                    "직접 서버 파일 호스트에서 편집해 주세요옹!",
                    ephemeral=True
                )
                return
                
        modal = GameItemDbEditModal(self.client)
        await interaction.response.send_modal(modal)

    @ui.button(label="📤 DB 다운로드", style=discord.ButtonStyle.secondary, custom_id="danddobot_game_admin_db_download", row=0)
    async def download_db_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Admin JSON database download requested by {interaction.user}")
        db = getattr(self.client, "db", None)
        if not db or not os.path.exists(db.db_path):
            await interaction.response.send_message("❌ 데이터베이스 파일이 존재하지 않는다냥!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        file = discord.File(db.db_path, filename="game_database.json")
        await interaction.followup.send(
            content="💾 **현재 미니게임 JSON 데이터베이스 파일입니다.**\n"
                    "다운로드하여 로컬에서 편집 후 '📥 DB 업로드' 버튼으로 덮어쓸 수 있습니다옹!",
            file=file,
            ephemeral=True
        )

    @ui.button(label="📥 DB 업로드", style=discord.ButtonStyle.danger, custom_id="danddobot_game_admin_db_upload", row=0)
    async def upload_db_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Admin JSON database upload flow requested by {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        prompt_text = (
            "📥 **미니게임 JSON 데이터베이스 파일 업로드 대기 시작**\n\n"
            "**60초 이내**에 어드민 채널 채팅바 왼쪽에 있는 **(+) 버튼**을 눌러 편집 완료된 `game_database.json` 파일을 전송해 주시거나, "
            "이곳 채팅창으로 파일을 직접 끌어다(Drag & Drop) 던져 주세요!\n\n"
            "⚠️ **주의:** 완료 시 기존의 모든 유저 데이터가 업로드된 새 파일 내용으로 완전히 덮어씌워집니다!"
        )
        await interaction.followup.send(content=prompt_text, ephemeral=True)
        
        def check(m):
            return (
                m.author.id == interaction.user.id and 
                m.channel.id == interaction.channel.id and 
                len(m.attachments) > 0
            )
            
        try:
            message = await self.client.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ **업로드 시간이 초과되었습니다.** 작업을 취소합니다. 다시 시도해 주세요옹.", ephemeral=True)
            return
            
        attachment = message.attachments[0]
        if not attachment.filename.endswith(".json"):
            await interaction.followup.send("❌ **.json 형식의 파일만 미니게임 DB로 등록할 수 있다냥!**", ephemeral=True)
            return
            
        try:
            file_bytes = await attachment.read()
            content = file_bytes.decode('utf-8')
            
            import json
            new_data = json.loads(content)
            if not isinstance(new_data, dict) or "users" not in new_data:
                await interaction.followup.send("❌ **올바른 형식의 미니게임 DB JSON 구조가 아닙니다.** 최상위 레벨에 `\"users\"` 키가 포함되어야 합니다옹!", ephemeral=True)
                return
                
            db = getattr(self.client, "db", None)
            if db:
                async with db.get_lock():
                    db.data = new_data
                    await db._save_data()
                    
                try:
                    await message.delete()
                except Exception:
                    pass
                    
                from .embeds import build_game_admin_embed
                embed = await build_game_admin_embed(self.client)
                await interaction.message.edit(embed=embed, view=self)
                
                await interaction.followup.send(
                    f"✅ **미니게임 JSON 데이터베이스 덮어쓰기 성공!**\n"
                    f"• 등록된 총 사용자 수: `{len(new_data['users'])}명`\n"
                    f"• 변경된 데이터가 실시간으로 어드민 대시보드 및 인메모리 저장소에 정상 반영되었습니다옹!",
                    ephemeral=True
                )
                logger.warning(f"Database fully replaced via admin file upload by {interaction.user}")
            else:
                await interaction.followup.send("❌ 데이터베이스 인스턴스가 존재하지 않습니다.", ephemeral=True)
        except json.JSONDecodeError as je:
            await interaction.followup.send(f"❌ **JSON 파일 문법 오류:** 업로드하신 파일에 문법적 문제가 있습니다. 문장 부호(쉼표, 중괄호 등)를 다시 확인해 주세요!\n`오류: {je}`", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to process uploaded DB file: {e}")
            await interaction.followup.send(f"❌ 데이터베이스 복원 중 치명적인 오류가 발생했습니다: `{e}`", ephemeral=True)

    @ui.button(label="🔄 패널 새로고침", style=discord.ButtonStyle.secondary, custom_id="danddobot_game_admin_refresh", row=0)
    async def refresh_panel_btn(self, interaction: discord.Interaction, button: ui.Button):
        logger.info(f"Admin game panel refresh requested by {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        from .embeds import build_game_admin_embed
        embed = await build_game_admin_embed(self.client)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send("✅ 미니게임 데이터베이스 현황 및 리더보드가 실시간으로 새로고침되었습니다옹!", ephemeral=True)
