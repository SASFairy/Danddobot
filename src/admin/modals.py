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


class GameUserQueryModal(ui.Modal, title="🔍 미니게임 유저 정보 조회"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        self.user_input = ui.TextInput(
            label="디스코드 유저 ID 또는 유저명 입력",
            style=discord.TextStyle.short,
            placeholder="예: 123456789012345678 또는 SASFairy",
            required=True
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ DB 연결이 끊어져 있습니다옹!", ephemeral=True)
            return
            
        search_val = self.user_input.value.strip()
        user_info = None
        
        try:
            user_id = int(search_val)
            user_info = await db.get_user(user_id)
        except ValueError:
            user_info = await db.get_user_by_name(search_val)
            
        if not user_info:
            await interaction.response.send_message(f"❌ '{search_val}'에 매칭되는 유저 정보가 존재하지 않습니다옹!", ephemeral=True)
            return
            
        # Parse items JSON
        import json
        try:
            items_list = json.loads(user_info["items"])
        except Exception:
            items_list = []
        items_display = ", ".join(items_list) if items_list else "없음"
        
        detail_msg = (
            f"👤 **단또봇 미니게임 유저 상세 정보**\n"
            f"• **디스코드 이름**: `{user_info['username']}`\n"
            f"• **유저 고유 ID**: `{user_info['user_id']}`\n"
            f"• **보유 자산**: `{user_info['money']:,}원`\n"
            f"• **연속 출석 기록**: `{user_info['checkin_streak']}일 연속`\n"
            f"• **마지막 출석일**: `{user_info['last_checkin'] or '기록 없음'}`\n"
            f"• **가방 아이템**: `{items_display}`\n"
            f"• **최초 가입 일자**: `{user_info['created_at']}`"
        )
        await interaction.response.send_message(detail_msg, ephemeral=True)


class GameBalanceAdjustModal(ui.Modal, title="💵 미니게임 유저 자산 조정"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        self.user_input = ui.TextInput(
            label="대상 디스코드 유저 ID",
            style=discord.TextStyle.short,
            placeholder="숫자 고유 ID만 입력 가능합니다.",
            required=True
        )
        self.amount_input = ui.TextInput(
            label="조정할 금액 설정 (+/- 부호 가능)",
            style=discord.TextStyle.short,
            placeholder="예: +50000, -25000, 100000 (설정)",
            required=True
        )
        self.add_item(self.user_input)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ DB 연결 실패", ephemeral=True)
            return
            
        try:
            user_id = int(self.user_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 유저 고유 ID는 숫자로만 입력해 주세요!", ephemeral=True)
            return
            
        user_info = await db.get_user(user_id)
        if not user_info:
            await interaction.response.send_message(f"❌ 해당 ID `{user_id}`는 미가입 사용자입니다.", ephemeral=True)
            return
            
        amount_str = self.amount_input.value.strip()
        current_money = user_info["money"]
        new_money = current_money
        
        try:
            if amount_str.startswith("+"):
                diff = int(amount_str[1:])
                new_money = current_money + diff
            elif amount_str.startswith("-"):
                diff = int(amount_str[1:])
                new_money = current_money - diff
            else:
                new_money = int(amount_str)
        except ValueError:
            await interaction.response.send_message("❌ 기호 정수 또는 일반 정수만 기입하세요옹!", ephemeral=True)
            return
            
        if new_money < 0:
            await interaction.response.send_message(f"❌ 유저 자산은 0원 아래로 떨어질 수 없습니다. (연산액: {new_money:,}원)", ephemeral=True)
            return
            
        success = await db.admin_update_user(user_id, {"money": new_money})
        if success:
            logger.warning(f"Admin {interaction.user} adjusted user {user_id} assets: {current_money} -> {new_money}")
            from .embeds import build_game_admin_embed
            embed = await build_game_admin_embed(client)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(
                f"✅ `{user_info['username']}`님의 소지 잔액이 조정되었습니다옹!\n"
                f"• **기존 잔액**: {current_money:,}원\n"
                f"• **변경 잔액**: {new_money:,}원 (변동: {new_money - current_money:+,}원)",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ DB 업데이트 실패", ephemeral=True)


class GameStreakAdjustModal(ui.Modal, title="📅 미니게임 출석 및 Streak 관리"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        self.user_input = ui.TextInput(
            label="대상 디스코드 유저 ID",
            style=discord.TextStyle.short,
            placeholder="숫자 고유 ID만 입력하세요.",
            required=True
        )
        self.streak_input = ui.TextInput(
            label="연속 출석일 수 설정 (정수)",
            style=discord.TextStyle.short,
            placeholder="예: 0, 3, 7",
            required=True
        )
        self.date_input = ui.TextInput(
            label="최종 출석 일자 입력 (YYYY-MM-DD)",
            style=discord.TextStyle.short,
            placeholder="예: 2026-07-11 (밀어내려면 '초기화' 기입)",
            required=True
        )
        self.add_item(self.user_input)
        self.add_item(self.streak_input)
        self.add_item(self.date_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ DB 연결 실패", ephemeral=True)
            return
            
        try:
            user_id = int(self.user_input.value.strip())
            streak = int(self.streak_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 유저 ID와 연속 출석일은 반드시 정수형 정수여야 합니다옹!", ephemeral=True)
            return
            
        user_info = await db.get_user(user_id)
        if not user_info:
            await interaction.response.send_message(f"❌ 해당 ID `{user_id}` 유저를 찾지 못했습니다.", ephemeral=True)
            return
            
        date_str = self.date_input.value.strip()
        if date_str == "초기화":
            last_checkin_val = None
        else:
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                await interaction.response.send_message("❌ 날짜는 YYYY-MM-DD 격식에 맞게 입력해 주세요!", ephemeral=True)
                return
            last_checkin_val = date_str
            
        updates = {
            "checkin_streak": streak,
            "last_checkin": last_checkin_val
        }
        
        success = await db.admin_update_user(user_id, updates)
        if success:
            from .embeds import build_game_admin_embed
            embed = await build_game_admin_embed(client)
            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(
                f"✅ `{user_info['username']}`님의 출석 세부 내용이 갱신되었습니다옹!\n"
                f"• **연속 출석일**: {user_info['checkin_streak']}일 -> {streak}일\n"
                f"• **최근 출석일**: `{user_info['last_checkin']}` -> `{last_checkin_val}`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ DB 업데이트 실패", ephemeral=True)


class GameItemManageModal(ui.Modal, title="🎒 미니게임 유저 인벤토리 관리"):
    def __init__(self, client: discord.Client):
        super().__init__()
        self.client = client
        self.user_input = ui.TextInput(
            label="대상 디스코드 유저 ID",
            style=discord.TextStyle.short,
            placeholder="숫자 고유 ID만 기입하세요.",
            required=True
        )
        self.items_input = ui.TextInput(
            label="가방 속 소유 아이템 입력 (쉼표 구분)",
            style=discord.TextStyle.paragraph,
            placeholder="예: 츄르, 참치캔, 슬롯머신티켓 (비우려면 비운 채로 등록)",
            required=False,
            max_length=1000
        )
        self.add_item(self.user_input)
        self.add_item(self.items_input)

    async def on_submit(self, interaction: discord.Interaction):
        client = self.client
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ DB 연결 실패", ephemeral=True)
            return
            
        try:
            user_id = int(self.user_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ 유저 고유 ID 형식이 잘못되었습니다옹!", ephemeral=True)
            return
            
        user_info = await db.get_user(user_id)
        if not user_info:
            await interaction.response.send_message(f"❌ 해당 ID `{user_id}` 유저를 데이터베이스에서 찾을 수 없습니다옹!", ephemeral=True)
            return
            
        items_raw = self.items_input.value.strip()
        if items_raw:
            items_list = [item.strip() for item in items_raw.split(",") if item.strip()]
        else:
            items_list = []
            
        import json
        items_json = json.dumps(items_list, ensure_ascii=False)
        
        success = await db.admin_update_user(user_id, {"items": items_json})
        if success:
            items_display = ", ".join(items_list) if items_list else "없음"
            await interaction.response.send_message(
                f"✅ `{user_info['username']}`님의 인벤토리를 성공적으로 조정했습니다옹!\n"
                f"• **보관함 아이템**: `{items_display}`",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ DB 업데이트 실패", ephemeral=True)

