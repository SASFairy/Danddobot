import os
import time
import discord

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
        top_p_val = getattr(client.llm_client, "top_p", None)
        top_p_str = "기본값" if top_p_val is None else f"{top_p_val}"
        top_k_val = getattr(client.llm_client, "top_k", None)
        top_k_str = "기본값" if top_k_val is None else f"{top_k_val}"
        
        llm_info = (
            f"**Provider**: `{provider}`\n"
            f"**Model**: `{model}`\n"
            f"**Timeout**: `{timeout_str}`\n"
            f"**Temperature**: `{temp_str}`\n"
            f"**Max Tokens**: `{max_tokens_str}`\n"
            f"**Repeat Penalty**: `{rep_penalty_str}`\n"
            f"**Top-P**: `{top_p_str}`\n"
            f"**Top-K**: `{top_k_str}`"
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

    distinguish_users = getattr(client, "distinguish_users", True)
    distinguish_status = "🟢 활성화" if distinguish_users else "🔴 비활성화"

    rag_status = "🔴 비활성화"
    if hasattr(client, "rag_manager") and client.rag_manager:
        if client.rag_manager.is_enabled:
            chunk_cnt = len(client.rag_manager.retriever.documents) if hasattr(client.rag_manager.retriever, "documents") else 0
            rag_status = (
                f"🟢 활성화 (색인 청크: `{chunk_cnt}개`)\n"
                f"• **Top-K**: `{client.rag_manager.top_k}` | **최대 글자수**: `{client.rag_manager.max_chars}자`\n"
                f"• **청크 제한 크기**: `{client.rag_manager.chunk_size}자`"
            )

    embed = discord.Embed(
        title="🤖 Danddobot 관리 대시보드",
        description="단또봇의 실시간 상태를 모니터링하고 설정을 변경할 수 있는 전용 채널 콘솔입니다.",
        color=0x2ECC71  # Emerald green
    )
    embed.add_field(name="🟢 시스템 상태", value=f"`{status_msg}`", inline=True)
    embed.add_field(name="💬 활성 대화 채널", value=channel_mention, inline=True)
    embed.add_field(name="⏱️ Discord API 지연 시간", value=f"`{round(client.latency * 1000)}ms`", inline=True)
    embed.add_field(name="🧠 대화 기억 상태", value=f"`{memory_status}`", inline=True)
    embed.add_field(name="🔧 디버그 모드", value=f"`{debug_status}`", inline=True)
    embed.add_field(name="👤 사용자 구분", value=f"`{distinguish_status}`", inline=True)
    embed.add_field(name="📖 RAG 지식 엔진 상태", value=rag_status, inline=False)
    embed.add_field(name="🧠 LLM 엔진 설정", value=llm_info, inline=False)
    embed.add_field(name="📄 페르소나 설정", value=persona_status, inline=False)
    embed.set_footer(text=f"마지막 업데이트: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed
