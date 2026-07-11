import os
import logging
import discord
from discord import ui
from .embeds import build_dashboard_embed

logger = logging.getLogger("danddobot.admin.modals")

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
            
            # Update the cached prompt dynamically
            await self.client.settings.update_persona_prompt(new_content)
            
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
        await client.settings.set_llm_timeout(new_timeout)

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
        await client.settings.set_max_memory_length(new_val)

        # Rebuild dashboard view & edit message
        # Use local import to break circular dependency
        from .views import AdminDashboardView
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
        current_top_p = getattr(getattr(client, "llm_client", None), "top_p", None)
        current_top_k = getattr(getattr(client, "llm_client", None), "top_k", None)
        
        # Fetch active LLM client's supported parameter ranges
        ranges = {}
        if hasattr(client, "llm_client") and client.llm_client:
            ranges = client.llm_client.get_supported_parameter_ranges()

        # 1. Temperature field setup
        if "temperature" in ranges and ranges["temperature"] is not None:
            t_min, t_max = ranges["temperature"]
            t_label = f"온도 (Temperature, {t_min} ~ {t_max} / 빈칸시 기본)"
            t_placeholder = "예: 0.7 (낮을수록 일관적, 높을수록 창의적)"
        else:
            t_label = "[지원 안 함] 온도 (Temperature)"
            t_placeholder = "현재 프로바이더에서는 지원하지 않습니다."

        # 2. Max Tokens field setup
        if "max_tokens" in ranges and ranges["max_tokens"] is not None:
            m_min, m_max = ranges["max_tokens"]
            m_label = f"최대 토큰 (Max Tokens, {m_min} ~ {m_max} / 빈칸시 기본)"
            m_placeholder = "예: 1024 (답변의 최대 길이 제한)"
        else:
            m_label = "[지원 안 함] 최대 토큰 (Max Tokens)"
            m_placeholder = "현재 프로바이더에서는 지원하지 않습니다."

        # 3. Repeat Penalty field setup
        if "repeat_penalty" in ranges and ranges["repeat_penalty"] is not None:
            r_min, r_max = ranges["repeat_penalty"]
            r_label = f"반복 패널티 (Repeat Penalty, {r_min} ~ {r_max} / 빈칸시 기본)"
            r_placeholder = "예: 1.1 (높을수록 중복 표현 억제)"
        else:
            r_label = "[지원 안 함] 반복 패널티 (Repeat Penalty)"
            r_placeholder = "현재 프로바이더에서는 지원하지 않습니다."

        # 4. Top-P field setup
        if "top_p" in ranges and ranges["top_p"] is not None:
            p_min, p_max = ranges["top_p"]
            p_label = f"Top-P (Nucleus Sampling, {p_min} ~ {p_max} / 빈칸시 기본)"
            p_placeholder = "예: 0.9 (낮을수록 상위 확률 단어만 선택)"
        else:
            p_label = "[지원 안 함] Top-P (Nucleus Sampling)"
            p_placeholder = "현재 프로바이더에서는 지원하지 않습니다."

        # 5. Top-K field setup
        if "top_k" in ranges and ranges["top_k"] is not None:
            k_min, k_max = ranges["top_k"]
            k_label = f"Top-K (Candidates count, {k_min} ~ {k_max} / 빈칸시 기본)"
            k_placeholder = "예: 40 (높을수록 더 다양한 어휘 탐색)"
        else:
            k_label = "[지원 안 함] Top-K (Candidates)"
            k_placeholder = "현재 프로바이더에서는 지원하지 않습니다."

        self.temp_input = ui.TextInput(
            label=t_label,
            placeholder=t_placeholder,
            default="" if current_temp is None else str(current_temp),
            required=False,
            max_length=5
        )
        self.max_tokens_input = ui.TextInput(
            label=m_label,
            placeholder=m_placeholder,
            default="" if current_max_tokens is None else str(current_max_tokens),
            required=False,
            max_length=6
        )
        self.repeat_penalty_input = ui.TextInput(
            label=r_label,
            placeholder=r_placeholder,
            default="" if current_repeat_penalty is None else str(current_repeat_penalty),
            required=False,
            max_length=5
        )
        self.top_p_input = ui.TextInput(
            label=p_label,
            placeholder=p_placeholder,
            default="" if current_top_p is None else str(current_top_p),
            required=False,
            max_length=5
        )
        self.top_k_input = ui.TextInput(
            label=k_label,
            placeholder=k_placeholder,
            default="" if current_top_k is None else str(current_top_k),
            required=False,
            max_length=5
        )
        
        self.add_item(self.temp_input)
        self.add_item(self.max_tokens_input)
        self.add_item(self.repeat_penalty_input)
        self.add_item(self.top_p_input)
        self.add_item(self.top_k_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        
        temp_val = None
        max_tokens_val = None
        rep_penalty_val = None
        top_p_val = None
        top_k_val = None
        
        # Fetch active LLM client's supported parameter ranges for validation
        ranges = {}
        if hasattr(client, "llm_client") and client.llm_client:
            ranges = client.llm_client.get_supported_parameter_ranges()

        # 1. Parse Temperature
        temp_str = self.temp_input.value.strip()
        if temp_str:
            if "temperature" not in ranges or ranges["temperature"] is None:
                await interaction.response.send_message("❌ 현재 프로바이더/모델은 온도(Temperature) 설정을 지원하지 않습니다.", ephemeral=True)
                return
            try:
                temp_val = float(temp_str)
                t_min, t_max = ranges["temperature"]
                if temp_val < t_min or temp_val > t_max:
                    await interaction.response.send_message(f"❌ 온도는 {t_min}에서 {t_max} 사이의 숫자여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 온도는 올바른 실수여야 합니다.", ephemeral=True)
                return
                
        # 2. Parse Max Tokens
        max_tokens_str = self.max_tokens_input.value.strip()
        if max_tokens_str:
            if "max_tokens" not in ranges or ranges["max_tokens"] is None:
                await interaction.response.send_message("❌ 현재 프로바이더/모델은 최대 토큰(Max Tokens) 설정을 지원하지 않습니다.", ephemeral=True)
                return
            try:
                max_tokens_val = int(max_tokens_str)
                m_min, m_max = ranges["max_tokens"]
                if max_tokens_val < m_min or max_tokens_val > m_max:
                    await interaction.response.send_message(f"❌ 최대 토큰은 {m_min}에서 {m_max} 사이의 정수여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 최대 토큰은 올바른 정수여야 합니다.", ephemeral=True)
                return
                
        # 3. Parse Repeat Penalty
        rep_penalty_str = self.repeat_penalty_input.value.strip()
        if rep_penalty_str:
            if "repeat_penalty" not in ranges or ranges["repeat_penalty"] is None:
                await interaction.response.send_message("❌ 현재 프로바이더/모델은 반복 패널티(Repeat Penalty) 설정을 지원하지 않습니다.", ephemeral=True)
                return
            try:
                rep_penalty_val = float(rep_penalty_str)
                r_min, r_max = ranges["repeat_penalty"]
                if rep_penalty_val < r_min or rep_penalty_val > r_max:
                    await interaction.response.send_message(f"❌ 반복 패널티는 {r_min}에서 {r_max} 사이의 숫자여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ 반복 패널티는 올바른 실수여야 합니다.", ephemeral=True)
                return

        # 4. Parse Top-P
        top_p_str = self.top_p_input.value.strip()
        if top_p_str:
            if "top_p" not in ranges or ranges["top_p"] is None:
                await interaction.response.send_message("❌ 현재 프로바이더/모델은 Top-P 설정을 지원하지 않습니다.", ephemeral=True)
                return
            try:
                top_p_val = float(top_p_str)
                p_min, p_max = ranges["top_p"]
                if top_p_val < p_min or top_p_val > p_max:
                    await interaction.response.send_message(f"❌ Top-P는 {p_min}에서 {p_max} 사이의 숫자여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Top-P는 올바른 실수여야 합니다.", ephemeral=True)
                return
                
        # 5. Parse Top-K
        top_k_str = self.top_k_input.value.strip()
        if top_k_str:
            if "top_k" not in ranges or ranges["top_k"] is None:
                await interaction.response.send_message("❌ 현재 프로바이더/모델은 Top-K 설정을 지원하지 않습니다.", ephemeral=True)
                return
            try:
                top_k_val = int(top_k_str)
                k_min, k_max = ranges["top_k"]
                if top_k_val < k_min or top_k_val > k_max:
                    await interaction.response.send_message(f"❌ Top-K는 {k_min}에서 {k_max} 사이의 정수여야 합니다.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Top-K는 올바른 정수여야 합니다.", ephemeral=True)
                return
                
        # Update and persist parameters
        await client.settings.update_llm_parameters(
            temperature=temp_val,
            max_tokens=max_tokens_val,
            repeat_penalty=rep_penalty_val,
            top_p=top_p_val,
            top_k=top_k_val
        )
        
        # Rebuild dashboard view & edit message
        # Use local import to break circular dependency
        from .views import AdminDashboardView
        embed = build_dashboard_embed(client, status_msg="LLM 생성 옵션 변경 완료")
        new_view = AdminDashboardView(client)
        await interaction.message.edit(embed=embed, view=new_view)
        
        # Prepare success message text
        status_lines = []
        status_lines.append(f"• **Temperature**: `{temp_val if temp_val is not None else '기본값'}`")
        status_lines.append(f"• **Max Tokens**: `{max_tokens_val if max_tokens_val is not None else '기본값'}`")
        status_lines.append(f"• **Repeat Penalty**: `{rep_penalty_val if rep_penalty_val is not None else '기본값'}`")
        status_lines.append(f"• **Top-P**: `{top_p_val if top_p_val is not None else '기본값'}`")
        status_lines.append(f"• **Top-K**: `{top_k_val if top_k_val is not None else '기본값'}`")
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
            embed = build_dashboard_embed(client, status_msg="메시지 대리 전송 완료")
            await interaction.message.edit(embed=embed)
            
            await interaction.response.send_message(f"✅ 활성 채널({channel.mention})로 메시지가 성공적으로 전송되었습니다!", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send arbitrary message to active channel: {e}")
            await interaction.response.send_message(f"❌ 메시지 전송 중 오류가 발생했습니다: `{e}`", ephemeral=True)


class RagParametersEditModal(ui.Modal, title="📖 RAG 지능형 지식 엔진 설정"):
    """
    Discord Modal to dynamically configure the RAG search and chunking parameters.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        current_top_k = getattr(client.rag_manager, "top_k", 3)
        current_max_chars = getattr(client.rag_manager, "max_chars", 1500)
        current_chunk_size = getattr(client.rag_manager, "chunk_size", 500)
        
        self.top_k_input = ui.TextInput(
            label="RAG 검색 문서 수 (Top-K: 1~10)",
            placeholder="기본값: 3 (매칭율이 가장 높은 상위 문서 조각 수)",
            default=str(current_top_k),
            required=True,
            max_length=2
        )
        self.max_chars_input = ui.TextInput(
            label="최대 전달 글자수 (Max Chars: 50~4000)",
            placeholder="기본값: 1500 (LLM 페르소나에 주입될 총 최대 글자 제한)",
            default=str(current_max_chars),
            required=True,
            max_length=4
        )
        self.chunk_size_input = ui.TextInput(
            label="청크 제한 크기 (Chunk Size: 10~1000)",
            placeholder="기본값: 500 (문서를 쪼갤 때의 타겟 개별 글자 제한 크기)",
            default=str(current_chunk_size),
            required=True,
            max_length=4
        )
        
        self.add_item(self.top_k_input)
        self.add_item(self.max_chars_input)
        self.add_item(self.chunk_size_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        
        top_k_str = self.top_k_input.value.strip()
        max_chars_str = self.max_chars_input.value.strip()
        chunk_size_str = self.chunk_size_input.value.strip()
        
        try:
            top_k = int(top_k_str)
            if top_k < 1 or top_k > 10:
                await interaction.response.send_message("❌ RAG Top-K는 1에서 10 사이의 정수여야 합니다.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Top-K 수치로 올바른 정수를 입력해 주세요.", ephemeral=True)
            return

        try:
            max_chars = int(max_chars_str)
            if max_chars < 50 or max_chars > 4000:
                await interaction.response.send_message("❌ 최대 글자수는 50자에서 4000자 사이여야 합니다.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ 최대 글자수 수치로 올바른 정수를 입력해 주세요.", ephemeral=True)
            return

        try:
            chunk_size = int(chunk_size_str)
            if chunk_size < 10 or chunk_size > 1000:
                await interaction.response.send_message("❌ 청크 제한 크기는 10자에서 1000자 사이여야 합니다.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ 청크 크기로 올바른 정수를 입력해 주세요.", ephemeral=True)
            return

        # Invoke Settings Controller to update and persist
        await client.settings.update_rag_parameters(
            top_k=top_k,
            max_chars=max_chars,
            chunk_size=chunk_size
        )
        
        # Determine actual applied values (since chunk_size might get clamped to max_chars)
        applied_chunk_size = client.rag_manager.chunk_size

        # Rebuild dashboard view & edit message
        # We import here locally to bypass circular imports
        from .views import AdminDashboardView
        embed = build_dashboard_embed(client, status_msg="RAG 지식 엔진 설정 변경 완료")
        new_view = AdminDashboardView(client)
        await interaction.message.edit(embed=embed, view=new_view)
        
        await interaction.response.send_message(
            f"✅ **RAG 지능형 지식 엔진 설정이 업데이트되었습니다!**\n"
            f"• **Top-K**: `{top_k}개` (상위 조각 매칭)\n"
            f"• **최대 글자수 (Max Chars)**: `{max_chars}자`\n"
            f"• **청크 제한 크기 (Chunk Size)**: `{applied_chunk_size}자` (요청값: `{chunk_size}자`" + 
            (f", 최대 글자수 한도에 맞춰 자동 캡핑됨)" if applied_chunk_size != chunk_size else ")"),
            ephemeral=True
        )


class RagFileCreateModal(ui.Modal, title="➕ 신규 지식 직접 작성"):
    """
    Discord Modal to directly write and create a new RAG .txt knowledge document.
    """
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        
        self.filename_input = ui.TextInput(
            label="파일명 입력 (반드시 .txt로 끝나야 함)",
            placeholder="예: server_rules.txt",
            required=True,
            max_length=50
        )
        self.content_input = ui.TextInput(
            label="지식 본문 입력 (최대 4000자)",
            style=discord.TextStyle.paragraph,
            placeholder="챗봇에게 참고시킬 지식을 정갈하게 적어 주세요...",
            required=True,
            max_length=4000
        )
        self.add_item(self.filename_input)
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        import re
        client = self.client
        filename = self.filename_input.value.strip()
        content = self.content_input.value
        
        # 1. Filename validation
        if not filename.endswith(".txt"):
            filename += ".txt"
            
        # Alphanumeric, underscores, hyphens, and dots only for security (Directory traversal guard)
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
            await interaction.response.send_message("❌ 파일명에는 영문, 숫자, 밑줄(_), 하이픈(-), 마침표(.)만 포함할 수 있습니다.", ephemeral=True)
            return

        knowledge_dir = getattr(client.rag_manager, "knowledge_dir", "config/knowledge")
        file_path = os.path.join(knowledge_dir, filename)
        
        try:
            # 2. Check if file already exists
            if os.path.exists(file_path):
                await interaction.response.send_message(f"⚠️ `{filename}` 파일이 이미 존재합니다. 덮어쓰려면 파일 선택 드롭다운에서 해당 파일을 고르고 수정 버튼을 이용해 주세요.", ephemeral=True)
                return
                
            os.makedirs(knowledge_dir, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            # 3. Reload knowledge base in memory
            doc_cnt, chunk_cnt = client.rag_manager.reload_knowledge()
            
            # Rebuild dashboard view & edit message
            from .views import AdminDashboardView
            embed = build_dashboard_embed(client, status_msg=f"신규 지식 추가 완료: {filename}")
            new_view = AdminDashboardView(client)
            new_view.current_category = "rag"  # Keep active tab
            new_view.selected_rag_file = filename  # Pre-select the newly created file
            new_view.refresh_components()
            await interaction.message.edit(embed=embed, view=new_view)
            
            await interaction.response.send_message(
                f"✅ **새로운 RAG 지식 문서가 작성되었습니다!**\n"
                f"• 파일명: `{filename}`\n"
                f"• 글자 수: `{len(content)}자`\n\n"
                f"전체 지식 리로드도 자동 완료되었습니다. 📚",
                ephemeral=True
            )
            logger.info(f"New RAG knowledge file '{filename}' created via Modal by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to create new RAG knowledge file: {e}")
            await interaction.response.send_message(f"❌ 신규 지식 생성 중 치명적 오류가 발생했습니다: `{e}`", ephemeral=True)


class RagFileEditModal(ui.Modal):
    """
    Discord Modal to directly edit the text of an existing RAG .txt knowledge document.
    Prefills current contents.
    """
    def __init__(self, client: discord.Client, filename: str):
        super().__init__(title=f"✏️ 지식 수정: {filename[:20]}")
        self.client = client
        self.filename = filename
        
        knowledge_dir = getattr(client.rag_manager, "knowledge_dir", "config/knowledge")
        file_path = os.path.join(knowledge_dir, filename)
        
        # Load current content
        current_content = ""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
            except Exception as e:
                logger.error(f"Failed to read file for prefilling EditModal: {e}")
                
        self.content_input = ui.TextInput(
            label="지식 본문 수정",
            style=discord.TextStyle.paragraph,
            placeholder="수정할 내용을 기입하세요...",
            default=current_content,
            required=True,
            max_length=4000
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        content = self.content_input.value
        
        knowledge_dir = getattr(client.rag_manager, "knowledge_dir", "config/knowledge")
        file_path = os.path.join(knowledge_dir, self.filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            # Reload knowledge base in memory
            doc_cnt, chunk_cnt = client.rag_manager.reload_knowledge()
            
            # Rebuild dashboard view & edit message
            from .views import AdminDashboardView
            embed = build_dashboard_embed(client, status_msg=f"지식 내용 수정 완료: {self.filename}")
            new_view = AdminDashboardView(client)
            new_view.current_category = "rag"
            new_view.selected_rag_file = self.filename
            new_view.refresh_components()
            await interaction.message.edit(embed=embed, view=new_view)
            
            await interaction.response.send_message(
                f"✅ **RAG 지식 문서 수정이 정상 완료되었습니다!**\n"
                f"• 파일명: `{self.filename}`\n"
                f"• 새로운 글자 수: `{len(content)}자`\n\n"
                f"전체 지식 리로드도 자동 완료되었습니다. 📚",
                ephemeral=True
            )
            logger.info(f"RAG knowledge file '{self.filename}' modified via Modal by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to edit RAG knowledge file: {e}")
            await interaction.response.send_message(f"❌ 지식 수정 중 오류가 발생했습니다: `{e}`", ephemeral=True)
