import logging
import discord
from discord import ui
from .embeds import build_dashboard_embed

logger = logging.getLogger("danddobot.admin.selects")

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
            # Use local import to break circular dependency
            from .views import AdminDashboardView
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
            # Use local import to break circular dependency
            from .views import AdminDashboardView
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
            # Use local import to break circular dependency
            from .views import AdminDashboardView
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
