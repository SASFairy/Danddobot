import random
import logging
import datetime
import asyncio
import discord
from discord import app_commands

logger = logging.getLogger("danddobot.game_commands")

def setup_game_commands(client: discord.Client):
    """
    Registers the game-related slash commands to the client's CommandTree.
    """
    
    @client.tree.command(name="가입", description="단또봇 미니게임에 가입하고 50,000원의 가입 지원금을 받습니다.")
    async def register(interaction: discord.Interaction):
        # Prevent actions if db is not initialized
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # Check if user is already registered
            existing_user = await db.get_user(user_id)
            if existing_user:
                # IMPORTANT: As per user preferences, the warning for duplicate registration is public (ephemeral=False)
                # as a "punishment" of making their status public to the server!
                await interaction.response.defer(ephemeral=False)
                
                # Request reactive LLM comment
                prompt = (
                    f"사용자 {username}님이 이미 가입된 상태에서 다시 /가입을 입력했습니다.\n"
                    f"• 보유 잔액: {existing_user['money']:,}원\n"
                    f"• 가입 일시: {existing_user['created_at']}\n\n"
                    f"이 상황에 대해 이미 가입된 단또봇 미니게임 회원인데 또 가입하려 한다며 어이없어하고, "
                    f"사용자의 어리석음을 놀리며 잔액({existing_user['money']:,}원)을 공개적으로 소문내는 유쾌하고 얄미운 무례한 '단또봇' 말투(츤데레, 야옹체)로 아주 짧게(2~3문장) 말해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)
                
                embed = discord.Embed(
                    title="🐱 바보냥?! 이미 가입되어 있다냥!",
                    description=f"이미 가입해서 웰컴 지원금을 챙겨갔다냥!\n\n"
                                f"💵 **보유 잔액:** {existing_user['money']:,}원\n"
                                f"📅 **가입 일시:** {existing_user['created_at']}",
                    color=0xE74C3C  # Red-ish
                )
                embed.add_field(name="🐱 단또봇의 고발 폭로", value=ai_reaction, inline=False)
                await interaction.followup.send(embed=embed)
                return

            # Register new user
            success = await db.register_user(user_id, username)
            if success:
                await interaction.response.defer(ephemeral=False)
                
                # Request reactive LLM comment for new signup
                prompt = (
                    f"사용자 {username}님이 단또봇 미니게임에 성공적으로 가입하여 지원금 50,000원을 지급받았습니다.\n\n"
                    f"신규 가입을 적당히 환영하면서, 지원금 50,000원으로 탕진하지 말고 잘 불려보라고 싸가지 없지만 츤데레 섞인 '단또봇' 말투(야옹체)로 짧고 귀엽게(2~3문장) 말해주세요. "
                    f"사용할 수 있는 미니게임 명령어는 /가입, /출석체크, /룰렛, /확인, /가위바위보, /구걸, /가르치기, /랭킹이 있다는 점도 넌지시 언급해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title="🎉 단또봇 미니게임 회원가입 완료!",
                    description=f"반갑다냥, **{username}**님! 가입 기념 지원금이 성공적으로 입금되었다냥.\n\n"
                                f"💵 **지급 금액:** `50,000원`\n\n"
                                f"🎮 **전체 명령어 가이드 (명령어가 더 풍성해졌다냥!):**\n"
                                f"• 📝 `/가입` : 미니게임 신규 등록 및 가입 처리\n"
                                f"• 📅 `/출석체크` : 매일 출석해 `10,000원` 획득 (7일 연속 출석 시 `100,000원` 보너스!)\n"
                                f"• 🎰 `/룰렛 [배팅금액]` : 0~9 무작위 숫자 3개를 맞추는 룰렛 게임 진행 (최소 배팅 500원)\n"
                                f"• ✊ `/가위바위보 [상대] [배팅금액]` : 다른 유저와 골드를 걸고 세기의 대결 (수수료 20%, 5분 쿨다운)\n"
                                f"• 🥺 `/구걸` : 가진 돈이 0원일 때 다른 유저들에게 처량하게 돈을 구걸하는 생존용 모금 (24시간 쿨다운)\n"
                                f"• 🎓 `/가르치기` : `100만~1000만원`을 내고 단또봇에게 커스텀 지식을 직접 교습 (24시간 쿨다운)\n"
                                f"• 🏆 `/랭킹` : 가장 골드가 많은 부자 유저 Top 5 조회 (3분 쿨타임, 1분 뒤 자동 폭파!)\n"
                                f"• 🔍 `/확인` : 내 소지금, 출석 현황, 쿨다운 상태 및 가방 속 아이템을 일괄 확인 (나만 보기)\n\n"
                                f"지금 바로 `/출석체크`를 해서 오늘 치 용돈을 챙기고, `/확인`으로 내 지갑 상태를 확인해 보라냥!",
                    color=0x2ECC71  # Green-ish
                )
                embed.add_field(name="🐱 단또봇의 환영 멘트", value=ai_reaction, inline=False)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message("❌ 가입 처리 중 알 수 없는 데이터베이스 오류가 발생했다냥!", ephemeral=True)

        except Exception as e:
            logger.error(f"Error handling register command for {username} ({user_id}): {e}")
            try:
                await interaction.followup.send("❌ 가입 처리 중 예상치 못한 치명적인 오류가 발생했다냥!")
            except Exception:
                await interaction.response.send_message("❌ 가입 처리 중 예상치 못한 치명적인 오류가 발생했다냥!", ephemeral=True)

    @client.tree.command(name="룰렛", description="숫자 3개를 무작위로 추첨하는 룰렛에 금액을 배팅합니다.")
    @app_commands.describe(betting_amount="배팅할 금액을 입력하세요 (보유 잔액 내에서 정수 입력, 최소 500원)")
    async def roulette(interaction: discord.Interaction, betting_amount: int):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Fetch user information
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("⚠️ 아직 미니게임에 가입하지 않았다냥!\n먼저 `/가입` 명령어를 입력해 가입하라냥!", ephemeral=True)
                return

            # 2. Check betting amount constraints
            if betting_amount < 500:
                await interaction.response.send_message("❌ 최소 배팅 금액은 **500원**이다냥!", ephemeral=True)
                return

            if user["money"] < betting_amount:
                await interaction.response.send_message(
                    f"❌ 잔액이 부족하다냥!\n"
                    f"• **보유 잔액:** {user['money']:,}원\n"
                    f"• **배팅 시도액:** {betting_amount:,}원",
                    ephemeral=True
                )
                return

            # Defer response to prevent Discord interaction timeout (3 seconds) while LLM is generating
            await interaction.response.defer(ephemeral=False)

            # 3. Spin roulette (Roll 3 random digits between 0 and 9)
            num1 = random.randint(0, 9)
            num2 = random.randint(0, 9)
            num3 = random.randint(0, 9)

            # Emoji map for numbers
            emoji_map = {
                0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣",
                5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣"
            }
            emojis_str = f"{emoji_map[num1]} {emoji_map[num2]} {emoji_map[num3]}"

            # Determine number of matching pairs
            if num1 == num2 == num3:
                matches = 3
            elif num1 == num2 or num1 == num3 or num2 == num3:
                matches = 2
            else:
                matches = 1

            payout = 0
            winnings_change = 0

            if matches == 3:
                # 3 matching: 4x payout
                payout = betting_amount * 4
                winnings_change = payout - betting_amount  # Net change is +3x betting amount
                result_title = "🎉 대박 잭팟! (3개 숫자 일치) 🎉"
                color = 0xF1C40F  # Gold/Yellow
                prompt = (
                    f"사용자 {username}님이 룰렛 게임에서 기적적으로 3개 숫자를 전부 일치시켰습니다!\n"
                    f"• 결과: [{num1}, {num2}, {num3}]\n"
                    f"• 배팅 금액: {betting_amount:,}원\n"
                    f"• 획득 당첨금: {payout:,}원 (배팅액의 4배)\n"
                    f"• 현재 사용자의 소지 잔고: {user['money'] + winnings_change:,}원\n\n"
                    f"이 소식에 대해 '단또봇'으로서 어안이 벙벙해하며 적당히 축하하고, "
                    f"인간 치고는 운이 좋다며 츤데레 섞인 장난스러운 축하 멘트를 단또봇 말투(야옹체)로 아주 짧게(2~3문장) 작성해주세요."
                )
            elif matches == 2:
                # 2 matching: 2x payout
                payout = betting_amount * 2
                winnings_change = payout - betting_amount  # Net change is +1x betting amount
                result_title = "✨ 당첨! (2개 숫자 일치) ✨"
                color = 0x2ECC71  # Green
                prompt = (
                    f"사용자 {username}님이 룰렛 게임에서 2개 숫자를 일치시켰습니다!\n"
                    f"• 결과: [{num1}, {num2}, {num3}]\n"
                    f"• 배팅 금액: {betting_amount:,}원\n"
                    f"• 획득 당첨금: {payout:,}원 (배팅액의 2배)\n"
                    f"• 현재 사용자의 소지 잔고: {user['money'] + winnings_change:,}원\n\n"
                    f"당첨을 마지못해 축하하면서도 다음엔 더 모험해보라며 허세를 피우거나 조언하는 싸가지 없는 츤데레 '단또봇' 말투(야옹체)의 멘트를 아주 짧게(2~3문장) 작성해주세요."
                )
            else:
                # No matches: Lose bet
                payout = 0
                winnings_change = -betting_amount
                result_title = "💥 꽝! (일치하는 숫자 없음) 💥"
                color = 0xE74C3C  # Red
                prompt = (
                    f"사용자 {username}님이 룰렛 게임에서 일치하는 숫자 없이 낙첨되어 꽝이 났습니다.\n"
                    f"• 결과: [{num1}, {num2}, {num3}]\n"
                    f"• 배팅 금액: {betting_amount:,}원\n"
                    f"• 현재 사용자의 소지 잔고: {user['money'] + winnings_change:,}원\n\n"
                    f"돈을 날린 사용자를 격하게 비웃고 한심해하며, 고소해 죽겠다는 듯한 얄미우면서도 싸가지 없는 '단또봇' 특유의 놀림 멘트를 야옹체로 아주 짧고 얄밉게(2~3문장) 작성해주세요."
                )

            # Update database
            new_money = await db.update_money(user_id, winnings_change)
            if new_money is None:
                await interaction.followup.send("❌ 정산 도중 데이터베이스 처리 오류가 발생했다냥!")
                return

            # Request LLM reaction
            ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

            # Build result embed
            embed = discord.Embed(
                title=f"🎰 {username}님의 룰렛 결과 🎰",
                color=color
            )
            embed.add_field(name="🎰 추첨 결과", value=f"## [  {emojis_str}  ]", inline=False)
            embed.add_field(name="📢 판정 결과", value=f"**{result_title}**", inline=False)
            embed.add_field(name="💵 배팅 금액", value=f"{betting_amount:,}원", inline=True)
            embed.add_field(name="💰 정산 금액", value=f"+{payout:,}원" if payout > 0 else "0원", inline=True)
            embed.add_field(name="💳 현재 잔액", value=f"**{new_money:,}원**", inline=True)
            embed.add_field(name="🐱 단또봇의 실시간 한마디", value=ai_reaction, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling roulette command for {username} ({user_id}): {e}")
            try:
                await interaction.followup.send("❌ 룰렛 게임 도중 예기치 못한 치명적인 오류가 발생했다냥!")
            except Exception:
                await interaction.response.send_message("❌ 룰렛 게임 도중 예기치 못한 치명적인 오류가 발생했다냥!", ephemeral=True)

    @client.tree.command(name="출석체크", description="하루에 한 번 출석체크하여 재화를 얻습니다. (7일 연속 출석 시 보너스)")
    async def checkin(interaction: discord.Interaction):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Date calculations for KST/local time
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            # 2. Check checkin status via DB
            result = await db.checkin_user(user_id, today_str, yesterday_str)
            status = result["status"]

            if status == "not_registered":
                await interaction.response.send_message("⚠️ 아직 가입하지 않았다냥!\n먼저 `/가입` 명령어를 통해 등록하라냥!", ephemeral=True)
                return

            if status == "already":
                await interaction.response.defer(ephemeral=False)
                
                # Already checked in today. Ask LLM to mock them
                prompt = (
                    f"사용자 {username}님이 오늘 이미 출석체크를 완료했는데, 돈을 받기 위해 혹은 실수로 욕심 부리며 한 번 더 /출석체크를 입력했습니다.\n"
                    f"• 현재 소지 잔고: {result['money']:,}원\n"
                    f"• 연속 출석일수: {result['streak']}일\n\n"
                    f"이 상황에 대해 오늘 이미 출석 보상을 받았으니 내일 다시 오라고 멍청하다고 타박하고, "
                    f"욕심쟁이라며 사용자에게 핀잔을 주고 쫓아내려는 싸가지 없는 '단또봇' 말투(츤데레, 야옹체)로 짧고 귀엽게(2~3문장) 말해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title="🛑 멍청한 인간이다냥, 중복 출석 불가다냥!",
                    description=f"오늘 이미 출석체크 스탬프를 도장을 쾅 찍으셨습니다!\n\n"
                                f"💵 **보유 잔고:** {result['money']:,}원\n"
                                f"📅 **연속 출석일:** {result['streak']}일 연속",
                    color=0xE74C3C
                )
                embed.add_field(name="🐱 단또봇의 폭풍 핀잔", value=ai_reaction, inline=False)
                await interaction.followup.send(embed=embed)
                return

            if status == "success":
                await interaction.response.defer(ephemeral=False)
                
                reward = result["reward"]
                new_money = result["money"]
                streak = result["streak"]
                is_bonus = result["is_bonus"]

                if is_bonus:
                    # 7 days streak bonus (100,000 won)
                    result_title = "🎉 7일 연속 출석 달성! 🎉"
                    color = 0xF1C40F  # Golden
                    prompt = (
                        f"사용자 {username}님이 기어코 '7일 연속 출석체크'를 달성하여 보너스 지원금 {reward:,}원(일반 금액의 10배!)을 획득했습니다!\n"
                        f"• 오늘 지급 보너스: {reward:,}원\n"
                        f"• 현재 사용자의 소지 잔고: {new_money:,}원\n\n"
                        f"기특하게도 매일같이 찾아온 사용자를 은근히 축하해주고, "
                        f"기분이 좋아졌으니 이참에 돈을 크게 불려보라거나 나에게 츄르나 생선을 쏘라는 장난기 어필과 축하를 버무린 '단또봇' 말투(야옹체)로 아주 신나게(2~3문장) 말해주세요."
                    )
                else:
                    # Regular checkin (10,000 won)
                    result_title = "📅 출석체크 완료! (일반 출석) 📅"
                    color = 0x2ECC71  # Green
                    prompt = (
                        f"사용자 {username}님이 일일 출석체크를 완료하여 출석금 {reward:,}원을 지급받았습니다.\n"
                        f"• 오늘 지급액: {reward:,}원\n"
                        f"• 현재 연속 출석 기록: {streak}일 연속\n"
                        f"• 현재 사용자의 소지 잔고: {new_money:,}원\n\n"
                        f"적당히 무례하게 아침/하루 인사를 건네며 오늘의 출석 정산금 10,000원을 지급했다는 사실을 알리고, "
                        f"이 돈을 룰렛으로 한순간에 날려먹지 말고 소중히 여기라는 츤데레 섞인 단또봇 말투(야옹체)로 짧게(2~3문장) 말해주세요."
                    )

                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title=f"🐱 {username}님 출석 도장 완료다냥!",
                    description=f"**{result_title}**\n\n"
                                f"💵 **지급 금액:** +{reward:,}원\n"
                                f"📅 **연속 출석:** {streak}일 연속\n"
                                f"💳 **현재 잔액:** **{new_money:,}원**",
                    color=color
                )
                embed.add_field(name="🐱 단또봇의 일일 인사", value=ai_reaction, inline=False)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error handling checkin command for {username} ({user_id}): {e}")
            try:
                await interaction.followup.send("❌ 출석체크 처리 도중 예기치 못한 치명적인 오류가 발생했다냥!")
            except Exception:
                await interaction.response.send_message("❌ 출석체크 처리 도중 예기치 못한 치명적인 오류가 발생했다냥!", ephemeral=True)

    @client.tree.command(name="확인", description="나의 보유 자산, 연속 출석일, 소유 아이템 등을 비밀스럽게 확인합니다. (나만 보기)")
    async def confirm_status(interaction: discord.Interaction):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # Strictly ephemeral = True, only visible to the user who ran the command
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("⚠️ 아직 가입하지 않았다냥!\n먼저 `/가입` 명령어를 입력해 등록하라냥!", ephemeral=True)
                return

            # Display parsing items (JSON parsed as list/list display)
            items_str = user["items"] or "[]"
            # Since items is currently '[]' by default, parse it if needed
            import json
            try:
                items_list = json.loads(items_str)
            except Exception:
                items_list = []
                
            items_display = ", ".join(items_list) if items_list else "소지 중인 아이템이 없다냥. 🎒"

            embed = discord.Embed(
                title=f"🎒 {username}님의 비밀 가방 정보 카드 🎒",
                description="해당 정보 카드는 오직 사용자에게만 보인다냥! (Secret/Ephemeral)",
                color=0x3498DB  # Blue-ish
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            embed.add_field(name="💵 보유 재고", value=f"**{user['money']:,}원**", inline=True)
            embed.add_field(name="📅 연속 출석", value=f"**{user['checkin_streak']}일 연속**", inline=True)
            embed.add_field(name="🕒 최근 출석", value=f"`{user['last_checkin'] or '기록 없음'}`", inline=True)
            embed.add_field(name="🎒 보유 아이템", value=f"```{items_display}```", inline=False)
            embed.add_field(name="📝 최초 가입일", value=f"`{user['created_at']}`", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error handling confirm_status command for {username} ({user_id}): {e}")
            await interaction.response.send_message("❌ 내 정보 확인 도중 치명적인 시스템 오류가 발생했다냥!", ephemeral=True)

    @client.tree.command(name="랭킹", description="단또봇 미니게임 부자 랭킹 Top 5를 조회합니다. (3분 쿨타임, 1분 뒤 삭제)")
    async def view_ranking(interaction: discord.Interaction):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Cooldown Check (3 minutes = 180s)
            import datetime
            now = datetime.datetime.now()
            if user_id in RANKING_COOLDOWNS:
                diff = now - RANKING_COOLDOWNS[user_id]
                if diff.total_seconds() < 180:
                    remaining = int(180 - diff.total_seconds())
                    await interaction.response.send_message(
                        f"❌ 아직 랭킹 확인 쿨다운이다냥! 그렇게나 재력이 궁금하냥?\n"
                        f"• 남은 재조회 대기시간: **{remaining}초**",
                        ephemeral=True
                    )
                    return

            # Apply Cooldown
            RANKING_COOLDOWNS[user_id] = now

            # 2. Check if user is registered to prevent unregistered ranking spam
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("⚠️ 아직 가입하지 않았다냥!\n먼저 `/가입` 명령어를 입력해 등록하라냥!", ephemeral=True)
                return

            # 3. Retrieve Top 5 Richest Users
            top_users = await db.get_top_users(5)
            if not top_users:
                await interaction.response.send_message("🐱 아직 미니게임에 가입한 회원이 한 명도 없다냥!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🏆 단또봇 미니게임 실시간 부자 랭킹 (Top 5) 🏆",
                description="현재 단또봇 나라에서 가장 자산이 풍족한 자산가 랭킹이다냥!\n"
                            "⚠️ *이 메시지는 도배 방지를 위해 1분(60초) 뒤에 폭파된다냥!*",
                color=0xF1C40F  # Gold
            )
            
            medals = ["🥇", "🥈", "🥉", "🏅", "🎗️"]
            leaderboard_lines = []
            for idx, u in enumerate(top_users):
                medal = medals[idx] if idx < len(medals) else "▫️"
                user_display = f"**{u['username']}**" if u['user_id'] == user_id else f"`{u['username']}`"
                leaderboard_lines.append(f"{medal} **{idx+1}위** | {user_display} — **{u['money']:,}원** (연속 `{u['streak']}일` 출석)")

            embed.add_field(name="💰 재산 순위표", value="\n".join(leaderboard_lines), inline=False)
            
            # Show requesting user's status below the rank
            user_rank_str = "순위권 외냥! 더 많은 골드를 획득하라냥!"
            all_users = await db.get_top_users(999999)
            user_idx = next((i for i, u in enumerate(all_users) if u['user_id'] == user_id), None)
            if user_idx is not None:
                user_rank_str = f"현재 **{user_idx + 1}위** / 총 `{len(all_users)}명`"
            
            embed.set_footer(text=f"내 순위: {user_rank_str} • 조회자: {username}")
            
            # Send public message
            await interaction.response.send_message(embed=embed, ephemeral=False)

            # 4. Asynchronously handle auto-deletion after 60s
            await asyncio.sleep(60)
            try:
                await interaction.delete_original_response()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error handling ranking command for {username} ({user_id}): {e}")
            try:
                await interaction.response.send_message("❌ 랭킹을 가져오는 도중 예기치 못한 시스템 오류가 발생했다냥!", ephemeral=True)
            except Exception:
                pass

    @client.tree.command(name="가위바위보", description="다른 사용자와 가위바위보 내기를 진행합니다. (수수료 20%, 5분 쿨다운)")
    @app_commands.describe(
        opponent="내기를 신청할 대상 디스코드 사용자",
        bet_amount="배팅할 판돈 금액 (500원 ~ 10,000,000원)"
    )
    async def play_rps(interaction: discord.Interaction, opponent: discord.Member, bet_amount: int):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        challenger = interaction.user
        
        # 1. Basic validations
        if bet_amount < 500 or bet_amount > 10000000:
            await interaction.response.send_message("❌ 배팅 금액은 **500원** 이상, **10,000,000원** 이하 범위에서만 정할 수 있다냥!", ephemeral=True)
            return
            
        if challenger.id == opponent.id:
            await interaction.response.send_message("❌ 스스로와 가위바위보를 할 순 없다냥! 너는 거울하고 가위바위보 해서 이길수 있겠냥?!", ephemeral=True)
            return
            
        if opponent.bot:
            await interaction.response.send_message("❌ 봇과는 대적할 수 없다냥!", ephemeral=True)
            return

        try:
            # 2. Registration validations
            u_challenger = await db.get_user(challenger.id)
            if not u_challenger:
                await interaction.response.send_message("⚠️ 아직 가입하지 않았다냥!\n먼저 `/가입` 명령어를 입력해 등록하라냥!", ephemeral=True)
                return
                
            u_opponent = await db.get_user(opponent.id)
            if not u_opponent:
                await interaction.response.send_message(f"⚠️ 상대방 `{opponent.display_name}`님은 아직 가입하지 않은 상태라 내기가 불가하다냥!", ephemeral=True)
                return

            # 3. Money balance checks
            if u_challenger["money"] < bet_amount:
                await interaction.response.send_message(
                    f"❌ 배팅할 소지금이 부족하다냥!\n"
                    f"• 내 잔액: {u_challenger['money']:,}원\n"
                    f"• 신청 배팅액: {bet_amount:,}원",
                    ephemeral=True
                )
                return
                
            if u_opponent["money"] < bet_amount:
                await interaction.response.send_message(
                    f"❌ 상대방 `{opponent.display_name}`님의 보유 골드가 부족하여 내기를 걸 수 없다냥!\n"
                    f"• 상대방 보유액: {u_opponent['money']:,}원",
                    ephemeral=True
                )
                return

            # 4. Active players checks
            if challenger.id in ACTIVE_RPS_PLAYERS:
                await interaction.response.send_message("❌ 현재 가위바위보 게임에 대기 중이거나 플레이 중이다냥!", ephemeral=True)
                return
                
            if opponent.id in ACTIVE_RPS_PLAYERS:
                await interaction.response.send_message(f"❌ 상대방 `{opponent.display_name}`님이 현재 이미 다른 유저와 대결 중이다냥!", ephemeral=True)
                return

            # 5. Cooldown checks (5 mins = 300s)
            now = datetime.datetime.now()
            
            # Clean up expired cooldowns to maintain dictionary hygiene
            expired_keys = [k for k, v in RPS_COOLDOWNS.items() if (now - v).total_seconds() >= 300]
            for ek in expired_keys:
                RPS_COOLDOWNS.pop(ek, None)
                
            # Log current cooldowns to the consolidated debug channel
            active_cooldown_seconds = {k: int(300 - (now - v).total_seconds()) for k, v in RPS_COOLDOWNS.items()}
            asyncio.create_task(send_rps_debug_log(
                client,
                f"[RPS-COOLDOWN-CHECK]\n"
                f"• Challenger: {challenger.display_name} (ID: {challenger.id})\n"
                f"• Opponent: {opponent.display_name} (ID: {opponent.id})\n"
                f"• Active Cooldowns (Remaining Sec): {active_cooldown_seconds}"
            ))
            
            if challenger.id in RPS_COOLDOWNS:
                diff = now - RPS_COOLDOWNS[challenger.id]
                if diff.total_seconds() < 300:
                    remaining = int(300 - diff.total_seconds())
                    await interaction.response.send_message(
                        f"❌ 아직 손가락 쿨다운이 풀리지 않았다냥! 그렇게나 승부가 좋냥?\n"
                        f"• 남은 재도전 대기시간: **{remaining}초**",
                        ephemeral=True
                    )
                    return

            # Lock players in active set
            ACTIVE_RPS_PLAYERS.add(challenger.id)
            ACTIVE_RPS_PLAYERS.add(opponent.id)

            # Build challenge accept view and send public notice
            embed = discord.Embed(
                title="✊✌️✋ 가위바위보 세기의 대결 신청 ⚔️",
                description=f"### {challenger.mention}님이 {opponent.mention}님에게 목숨 건 단판 가위바위보 내기를 걸었다냥!\n\n"
                            f"💰 **배팅 금액**: `{bet_amount:,}원`\n"
                            f"⚖️ **수수료**: `20%` (승자 실제 수령액: `{int(bet_amount * 1.8):,}원`)\n"
                            f"⏰ **대결 수락 대기시간**: `30초` (이내에 수락 버튼을 누르지 않으면 자동 취소)",
                color=0xE67E22
            )
            view = RPSAcceptView(client, challenger, opponent, bet_amount)
            await interaction.response.send_message(embed=embed, view=view)
            
            # Store the message reference in the view for timeout cleanup
            view.message = await interaction.original_response()

        except Exception as e:
            logger.error(f"Error initiating RPS challenge: {e}")
            ACTIVE_RPS_PLAYERS.discard(challenger.id)
            ACTIVE_RPS_PLAYERS.discard(opponent.id)
            await interaction.response.send_message("❌ 가위바위보 신청 진행 중 시스템 에러가 발생했다냥!", ephemeral=True)

    @client.tree.command(name="구걸", description="수중에 돈이 없을 때 비굴하게 손을 벌려 동전을 구걸합니다. (24시간 쿨다운, 10분 모금)")
    async def beg(interaction: discord.Interaction):
        # Prevent actions if db is not initialized
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Fetch user from database
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("❌ 아직 가입하지 않은 단또다냥! `/가입` 명령어부터 먼저 입력하라냥!", ephemeral=True)
                return

            user_money = user["money"]
            
            # 2. Check if user is actually poor/bankrupt (< 5000 won)
            if user_money >= 5000:
                await interaction.response.send_message(
                    f"❌ 아직 지갑에 `{user_money:,}원`이나 들어있으면서 구걸을 하려 드냥! 양심 어디 갔냥? 쫄딱 망해서 5,000원 미만이 되었을 때나 찾아오라냥!",
                    ephemeral=True
                )
                return

            # 3. Check 24-hour cooldown
            now = datetime.datetime.now()
            if user.get("last_begging"):
                try:
                    last_beg_dt = datetime.datetime.fromisoformat(user["last_begging"])
                    time_passed = now - last_beg_dt
                    if time_passed.total_seconds() < 86400:
                        remaining = int(86400 - time_passed.total_seconds())
                        hours = remaining // 3600
                        minutes = (remaining % 3600) // 60
                        seconds = remaining % 60
                        await interaction.response.send_message(
                            f"❌ 구걸은 하루에 딱 한 번만 할 수 있다냥!\n"
                            f"앞으로 `{hours:02d}시간 {minutes:02d}분 {seconds:02d}초` 뒤에 다시 구질구질하게 찾아와봐라냥!",
                            ephemeral=True
                        )
                        return
                except Exception as e:
                    logger.error(f"Error parsing last_begging timestamp: {e}")

            # 4. Defer response for generating LLM reaction public message
            await interaction.response.defer(ephemeral=False)

            # Generate tragic/mocking AI reaction prompt
            prompt = (
                f"사용자 {username}님이 현재 가진 돈이 {user_money:,}원밖에 없는 극심한 빈곤 상태에서 비굴하게 /구걸 명령어를 사용했습니다.\n"
                f"• 사용자의 현재 잔고: {user_money:,}원\n\n"
                f"이 사용자가 얼마나 병신같고 비참하고 하찮은 처지인지 엄청나게 비극적이고 과장되며, 무례하면서 얄밉게 묘사하고 조롱하면서, "
                f"서버의 다른 사용자들에게 🪙(동전) 반응을 달아 기부해달라고 구걸을 대행해주는 단또봇 말투(야옹체, 츤데레, 놀림조)로 아주 짧게(3~4문장) 작성해주세요."
            )
            ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

            # 5. Create Embed
            embed = discord.Embed(
                title=f"😭 {username}님의 처절한 구걸 판대기... 😭",
                description=f"### \"한 푼만 주십쇼... 제발 부탁드립니다...\"\n\n"
                            f"• **가련한 구걸자**: {interaction.user.mention}\n"
                            f"• **현재 보유 잔고**: `{user_money:,}원`\n"
                            f"• **모금된 금액**: `0원`\n\n"
                            f"⚠️ **기부 방법**: 아래에 **🪙 (동전) 이모지 반응**을 달면 본인의 자금 중 **500원**이 이 구걸자에게 실시간 기부(이체)된다냥!\n"
                            f"⏰ **모금 시간**: 앞으로 **10분** 동안만 모금이 열려있다냥!",
                color=0xE67E22 # Orange
            )
            embed.add_field(name="🐱 단또봇의 비극적 고발과 놀림", value=ai_reaction, inline=False)

            msg = await interaction.followup.send(embed=embed)
            await msg.add_reaction("🪙")

            # 6. Save begging session
            expires_at = now + datetime.timedelta(minutes=10)
            ACTIVE_BEGGING_SESSIONS[msg.id] = {
                "beggar_id": user_id,
                "beggar_name": username,
                "collected": 0,
                "donors": set(),
                "expires_at": expires_at,
                "message": msg,
                "is_active": True
            }

            # 7. Update database record for begging cooldown
            await db.update_begging_time(user_id, now.isoformat())

            # 8. Start background task to end the begging after 10 minutes (600 seconds)
            async def end_begging_after_delay(message_id: int, delay: float):
                await asyncio.sleep(delay)
                session = ACTIVE_BEGGING_SESSIONS.get(message_id)
                if session and session["is_active"]:
                    session["is_active"] = False
                    beg_id = session["beggar_id"]
                    beg_name = session["beggar_name"]
                    collected = session["collected"]
                    m = session["message"]

                    # Fetch final beggar balance
                    u_beg = await db.get_user(beg_id)
                    final_money = u_beg["money"] if u_beg else 0

                    prompt_end = (
                        f"사용자 {beg_name}님의 10분간의 구걸 모금 시간이 완전히 끝났습니다.\n"
                        f"• 기부받은 총 동전 개수: {collected // 500}개\n"
                        f"• 모인 총 금액: {collected:,}원\n"
                        f"• 구걸 후 최종 보유 잔액: {final_money:,}원\n\n"
                        f"구걸 모금 종료 결과를 전해 듣고, 기부자들의 적선 덕분에 겨우 입에 풀칠이나 하게 된 {beg_name}님을 향해 "
                        f"거지새끼가 드디어 목숨은 건졌다며 비웃고, 모인 푼돈({collected:,}원)을 보며 평생 구걸이나 하며 살라며 "
                        f"낄낄대고 격렬히 무시하고 쫓아내는 얄미운 단또봇 말투(야옹체, 츤데레)로 아주 짧게(2~3문장) 작성해주세요."
                    )
                    ai_reaction_end = await client.llm_client.generate_response(prompt_end, client.persona_prompt)

                    embed_end = discord.Embed(
                        title=f"🛑 {beg_name}님의 구걸 모금 종료! 🛑",
                        description=f"### \"꺼져라냥! 모금 시간 다 끝났다냥!\"\n\n"
                                    f"• **가련했던 구걸자**: <@{beg_id}>\n"
                                    f"• **모금 결과**: 총 `{collected:,}원` (+{collected // 500}개 동전 적선받음)\n"
                                    f"• **최종 보유 재잔고**: `{final_money:,}원`\n\n"
                                    f"💸 적선해 준 그나마 자비로운 인간들 덕분에 한 끼 식사값은 챙겼다냥! 짝짝짝!",
                        color=0x7F8C8D # Gray
                    )
                    embed_end.add_field(name="🐱 단또봇의 냉혹한 총평 한마디", value=ai_reaction_end, inline=False)

                    try:
                        await m.edit(embed=embed_end)
                        await m.clear_reactions()
                    except Exception as e_edit:
                        logger.error(f"Error finishing begging session message: {e_edit}")

                    ACTIVE_BEGGING_SESSIONS.pop(message_id, None)

            asyncio.create_task(end_begging_after_delay(msg.id, 600.0))

        except Exception as e:
            logger.error(f"Error executing beg command: {e}")
            try:
                await interaction.followup.send(f"❌ 구걸 명령 중 예상치 못한 에러가 발생했다냥! {e}", ephemeral=True)
            except Exception:
                pass

    @client.tree.command(name="가르치기", description="100만~1000만원의 비용을 지불하고 단또봇에게 지식을 가르칩니다. (나만 보기)")
    async def teach(interaction: discord.Interaction):
        # Prevent actions if db is not initialized
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았다냥!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Fetch user from database
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("❌ 아직 가입하지 않은 단또다냥! `/가입` 명령어부터 먼저 입력하라냥!", ephemeral=True)
                return

            user_money = user["money"]

            # 1.5 Check 24-hour persistent cooldown to prevent price gacha rolling
            now = datetime.datetime.now()
            if user.get("last_teaching"):
                try:
                    last_teach_dt = datetime.datetime.fromisoformat(user["last_teaching"])
                    time_passed = now - last_teach_dt
                    if time_passed.total_seconds() < 86400:
                        remaining = int(86400 - time_passed.total_seconds())
                        hours = remaining // 3600
                        minutes = (remaining % 3600) // 60
                        seconds = remaining % 60
                        await interaction.response.send_message(
                            f"❌ 단또봇 과외는 하루에 딱 한 번만 진행할 수 있다냥!\n"
                            f"가격 간보기(가챠) 방지를 위해, `{hours:02d}시간 {minutes:02d}분 {seconds:02d}초` 뒤에 다시 찾아와라냥!",
                            ephemeral=True
                        )
                        return
                except Exception as e:
                    logger.error(f"Error parsing last_teaching timestamp: {e}")

            # 2. Generate random price between 1M and 10M in 1K won increments
            price = random.randint(1000, 10000) * 1000

            # 3. Check if user has enough money
            if user_money < price:
                await interaction.response.send_message(
                    f"❌ 단또봇에게 지식을 주입하려면 무려 `{price:,}원`이 필요하다냥!\n"
                    f"하지만 지금 가진 돈은 `{user_money:,}원`밖에 없다냥... 거지새끼는 돈이나 더 벌어서 다시 찾아와라냥!",
                    ephemeral=True
                )
                return

            # 4. Show confirmation view (all ephemeral!)
            embed = discord.Embed(
                title="🧠 단또봇 지식 가르치기 🧠",
                description=f"단또봇에게 새로운 지식을 가르칠 귀한 기회가 왔다냥!\n"
                            f"제시된 지식 교육 라이선스 비용을 확인하고 진행할지 결정해 달라냥.\n\n"
                            f"• **가르칠 자**: {interaction.user.mention}\n"
                            f"• **제시된 무작위 교육비**: `{price:,}원`\n"
                            f"• **현재 보유 잔고**: `{user_money:,}원` (지불 후 잔고: `{user_money - price:,}원`)\n\n",
                color=0x9B59B6 # Purple
            )
            view = TeachConfirmationView(client, price, user_money)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            # 5. Lock cooldown immediately to prevent price gacha rolling
            await db.update_teaching_time(user_id, now.isoformat())

        except Exception as e:
            logger.error(f"Error executing teach command: {e}")
            try:
                await interaction.response.send_message(f"❌ 가르치기 명령 실행 중 에러 발생했다냥! {e}", ephemeral=True)
            except Exception:
                pass


RPS_LOG_BUFFER = []
RPS_LOG_FLUSH_TASK = None

async def flush_rps_debug_logs(client):
    # Wait for 0.6 seconds to gather any rapidly incoming logs
    await asyncio.sleep(0.6)
    
    global RPS_LOG_BUFFER, RPS_LOG_FLUSH_TASK
    if not RPS_LOG_BUFFER:
        RPS_LOG_FLUSH_TASK = None
        return
        
    # Safely swap out the buffer contents
    logs_to_send = list(RPS_LOG_BUFFER)
    RPS_LOG_BUFFER.clear()
    RPS_LOG_FLUSH_TASK = None
    
    combined_text = "\n".join(logs_to_send)
    
    # Also log to terminal
    logger.info(f"[RPS-DEBUG-FLUSHED] Consolidated logs:\n{combined_text}")
    
    if getattr(client, "log_channel_id", None):
        try:
            log_channel = client.get_channel(client.log_channel_id)
            if not log_channel:
                log_channel = await client.fetch_channel(client.log_channel_id)
            if log_channel:
                # If too long, truncate gracefully to fit inside Discord's 2000 char embed limit
                if len(combined_text) > 1900:
                    combined_text = combined_text[:1900] + "\n... (truncated)"
                    
                embed = discord.Embed(
                    title="✊✌️✋ 가위바위보 통합 디버그 로그",
                    description=f"```\n{combined_text}\n```",
                    color=0xE67E22,
                    timestamp=discord.utils.utcnow()
                )
                await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send combined RPS debug log: {e}")

async def send_rps_debug_log(client, text: str):
    # Log to terminal console immediately
    logger.info(text)
    
    # Append to buffer for Discord grouping
    RPS_LOG_BUFFER.append(text)
    
    global RPS_LOG_FLUSH_TASK
    if RPS_LOG_FLUSH_TASK is None or RPS_LOG_FLUSH_TASK.done():
        RPS_LOG_FLUSH_TASK = asyncio.create_task(flush_rps_debug_logs(client))


# Globals for Rock-Paper-Scissors
RPS_COOLDOWNS = {}  # user_id -> datetime of last match (start/accept)
ACTIVE_RPS_PLAYERS = set()  # set of user_ids currently in an active game
RANKING_COOLDOWNS = {}  # user_id -> datetime of last ranking check

# Globals for Begging
ACTIVE_BEGGING_SESSIONS = {} # message_id -> session dict

async def handle_begging_reaction(client, payload: discord.RawReactionActionEvent):
    message_id = payload.message_id
    if message_id not in ACTIVE_BEGGING_SESSIONS:
        return
        
    session = ACTIVE_BEGGING_SESSIONS[message_id]
    if not session["is_active"]:
        return
        
    beggar_id = session["beggar_id"]
    donor_id = payload.user_id
    
    # 1. Beggars cannot donate to themselves!
    if donor_id == beggar_id:
        try:
            guild = client.get_guild(payload.guild_id) if payload.guild_id else None
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(message_id)
                    member = guild.get_member(donor_id)
                    if member:
                        await msg.remove_reaction(payload.emoji, member)
        except Exception:
            pass
        return
        
    # Check if the emoji is 🪙
    if str(payload.emoji) != "🪙":
        return
        
    # Check if this donor has already donated on this message
    if donor_id in session["donors"]:
        try:
            guild = client.get_guild(payload.guild_id) if payload.guild_id else None
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(message_id)
                    member = guild.get_member(donor_id)
                    if member:
                        await msg.remove_reaction(payload.emoji, member)
        except Exception:
            pass
        return
        
    # Transfer money from donor to beggar in DB
    db = getattr(client, "db", None)
    if not db:
        return
        
    u_donor = await db.get_user(donor_id)
    if not u_donor:
        # Not registered user
        try:
            guild = client.get_guild(payload.guild_id) if payload.guild_id else None
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(message_id)
                    member = guild.get_member(donor_id)
                    if member:
                        await msg.remove_reaction(payload.emoji, member)
        except Exception:
            pass
        return
        
    if u_donor["money"] < 500:
        try:
            guild = client.get_guild(payload.guild_id) if payload.guild_id else None
            if guild:
                channel = guild.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(message_id)
                    member = guild.get_member(donor_id)
                    if member:
                        await msg.remove_reaction(payload.emoji, member)
                        await channel.send(f"❌ <@{donor_id}>님은 잔액이 부족하여 기부(500원)를 할 수 없다냥!", delete_after=5.0)
        except Exception:
            pass
        return
        
    # Valid donation!
    p_donor = await db.update_money(donor_id, -500)
    p_beggar = await db.update_money(beggar_id, 500)
    
    if p_donor is not None and p_beggar is not None:
        session["collected"] += 500
        session["donors"].add(donor_id)
        
        # Real-time update of public message embed
        try:
            msg = session["message"]
            u_beggar_info = await db.get_user(beggar_id)
            final_money = u_beggar_info["money"] if u_beggar_info else p_beggar
            
            embed = msg.embeds[0]
            embed.description = (
                f"### \"한 푼만 주십쇼냥... 제발 부탁드린다냥...\"\n\n"
                f"• **가련한 구걸자**: <@{beggar_id}>\n"
                f"• **현재 보유 재잔고**: `{final_money:,}원`\n"
                f"• **모금된 금액**: `{session['collected']:,}원` (+{len(session['donors'])}명 기부)\n\n"
                f"⚠️ **기부 방법**: 아래에 **🪙 (동전) 이모지 반응**을 달면 본인의 자금 중 **500원**이 이 구걸자에게 실시간 기부(이체)됩니다냥!\n"
                f"⏰ **모금 시간**: 앞으로 **10분** 동안만 모금이 열려있습니다냥!"
            )
            await msg.edit(embed=embed)
        except Exception as edit_err:
            logger.error(f"Error updating begging message on reaction: {edit_err}")

class RPSGameSession:
    def __init__(self, client, challenger: discord.Member, opponent: discord.Member, bet_amount: int, parent_msg: discord.Message):
        self.client = client
        self.challenger = challenger
        self.opponent = opponent
        self.bet_amount = bet_amount
        self.parent_msg = parent_msg
        self.challenger_choice = None  # "가위", "바위", "보"
        self.opponent_choice = None
        self.finished = False
        self.lock = asyncio.Lock()
        
    async def process_outcome(self):
        async with self.lock:
            if self.finished:
                await send_rps_debug_log(self.client, "[RPS-DEBUG] RPSGameSession already finalized. Skipping duplicate execution.")
                return
            self.finished = True
            
            await send_rps_debug_log(
                self.client,
                f"📊 [RPS-DEBUG] 세기의 가위바위보 대결 결과 집계 시작!\n"
                f"• 대전 판돈: {self.bet_amount:,}원\n"
                f"• 신청자 (Challenger): {self.challenger.display_name} (ID: {self.challenger.id})\n"
                f"• 수락자 (Opponent): {self.opponent.display_name} (ID: {self.opponent.id})\n"
                f"• 신청자 선택 (A Choice): {self.challenger_choice}\n"
                f"• 수락자 선택 (B Choice): {self.opponent_choice}"
            )
            
            # Remove from active players
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            await send_rps_debug_log(self.client, "[RPS-DEBUG] Players unlocked from ACTIVE_RPS_PLAYERS list.")
            
            choice_emojis = {"바위": "✊ 바위", "가위": "✌️ 가위", "보": "✋ 보", None: "🛑 기권 (시간 초과)"}
            
            # Check for non-selection (None means timeout/forfeit)
            c_choice = self.challenger_choice
            o_choice = self.opponent_choice
            
            winner = None
            loser = None
            reason_msg = ""
            
            if c_choice is None and o_choice is None:
                # Both timed out
                result_title = "🛑 대결 무효! (쌍방 기권) 🛑"
                color = 0x95A5A6 # Grey
                winner_id, loser_id = None, None
                reason_msg = "둘 다 모두 15초 이내에 선택하지 않아 쌍방 실격(무승부) 처리되었다냥!"
                await send_rps_debug_log(self.client, "[RPS-DEBUG] Result determined: Double Timeout (Tie/No action)")
            elif c_choice is None:
                # Challenger A timed out
                winner = self.opponent
                loser = self.challenger
                result_title = f"🏆 {winner.display_name}님 기권승! 🏆"
                color = 0x2ECC71
                reason_msg = f"{self.challenger.display_name}님이 15초 내 선택에 실패하여 {self.opponent.display_name}님이 기권승했다냥!"
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Opponent {winner.display_name} wins by Challenger timeout")
            elif o_choice is None:
                # Opponent B timed out
                winner = self.challenger
                loser = self.opponent
                result_title = f"🏆 {winner.display_name}님 기권승! 🏆"
                color = 0x2ECC71
                reason_msg = f"{self.opponent.display_name}님이 15초 내 선택에 실패하여 {self.challenger.display_name}님이 기권승했다냥!"
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Challenger {winner.display_name} wins by Opponent timeout")
            elif c_choice == o_choice:
                # Tie
                result_title = "🤝 가위바위보 비겼습니다냥! 🤝"
                color = 0x3498DB # Blue
                reason_msg = f"둘 다 모두 **{choice_emojis[c_choice]}**를 내어 승부가 나지 않았다냥. 판돈은 그대로 보존된다냥."
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Tie on {c_choice}")
            else:
                # Standard win/lose check
                # Rock beats Scissors, Scissors beats Paper, Paper beats Rock
                rules = {"바위": "가위", "가위": "보", "보": "바위"}
                if rules[c_choice] == o_choice:
                    winner = self.challenger
                    loser = self.opponent
                else:
                    winner = self.opponent
                    loser = self.challenger
                    
                result_title = f"🏆 대결 종료! {winner.display_name}님의 승리! 🏆"
                color = 0xF1C40F # Gold
                reason_msg = (
                    f"• {self.challenger.display_name}: **{choice_emojis[c_choice]}**\n"
                    f"• {self.opponent.display_name}: **{choice_emojis[o_choice]}**"
                )
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Winner {winner.display_name} ({c_choice if winner == self.challenger else o_choice}) vs Loser {loser.display_name} ({o_choice if winner == self.challenger else c_choice})")
                
            # DB processing
            payout_msg = ""
            db = self.client.db
            
            if winner and loser:
                # 20% commission on the winnings (net profit)
                profit = int(self.bet_amount * 0.8)
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Transferring funds: {self.bet_amount:,} won from {loser.display_name} to {winner.display_name} (payout profit: {profit:,} after 20% fee)")
                success = await db.transfer_rps_money(winner.id, loser.id, self.bet_amount, profit)
                if success:
                    payout_msg = (
                        f"💵 **베팅 판돈 정산 결과**\n"
                        f"• {winner.mention} 당첨금 지급: `+{profit:,}원` (20% 수수료 공제 완료)\n"
                        f"• {loser.mention} 자산 손실: `-{self.bet_amount:,}원`"
                    )
                    await send_rps_debug_log(self.client, "[RPS-DEBUG] Database ledger update succeeded.")
                else:
                    payout_msg = "⚠️ [오류] 판돈 이체 정산 중 예상치 못한 DB 오류가 발생했습니다. 수동 정산이 필요하다냥!"
                    await send_rps_debug_log(self.client, "[RPS-DEBUG] Database ledger update failed! Potential database lock or connection error.")
            else:
                payout_msg = "💵 **베팅 판돈 정산 결과**\n• 무승부 또는 쌍방 기권으로 자산 변동이 없다냥!"
                await send_rps_debug_log(self.client, "[RPS-DEBUG] No database balance change needed.")
                
            # Request LLM reaction
            if winner and loser:
                prompt = (
                    f"가위바위보 내기 매치 결과입니다.\n"
                    f"• 대결 판돈: {self.bet_amount:,}원\n"
                    f"• 도전자 {self.challenger.display_name}: {choice_emojis[c_choice]} 선택\n"
                    f"• 수락자 {self.opponent.display_name}: {choice_emojis[o_choice]} 선택\n"
                    f"• 최종 승리자: {winner.display_name} (+{int(self.bet_amount * 0.8):,}원 획득)\n"
                    f"• 최종 패배자: {loser.display_name} (-{self.bet_amount:,}원 손실)\n\n"
                    f"가위바위보 결과를 전해 듣고, 승리한 {winner.display_name}님에게는 무례하지만 그래도 치켜세워주고 "
                    f"패배하여 돈을 날린 {loser.display_name}님을 향해 한심하다는 듯 격렬히 놀리고 웃겨 자빠지는 얄미운 '단또봇' 말투(츤데레, 야옹체)로 아주 짧게(2~3문장) 작성해주세요."
                )
            else:
                prompt = (
                    f"가위바위보 내기 매치가 무승부(비김 또는 쌍방기권)로 끝났습니다.\n"
                    f"• 도전자 {self.challenger.display_name}: {choice_emojis[c_choice]} 선택\n"
                    f"• 수락자 {self.opponent.display_name}: {choice_emojis[o_choice]} 선택\n\n"
                    f"결국 아무도 돈을 얻지 못하고 싱겁게 끝난 것에 대해 김빠져하며 "
                    f"둘 다 어설프고 한심하다며 어깨를 으쓱하고 쫓아내는 얄미운 '단또봇' 말투(야옹체)로 짧게(2~3문장) 작성해주세요."
                )
            
            try:
                await send_rps_debug_log(self.client, "[RPS-DEBUG] Fetching real-time AI reaction response...")
                ai_reaction = await self.client.llm_client.generate_response(prompt, self.client.persona_prompt)
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] AI response fetched: {ai_reaction}")
            except Exception as e:
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Failed to fetch AI reaction: {e}")
                ai_reaction = "하아. 너무 시시한 승부라 말문이 턱 막힌다냥."
                
            # Build outcome embed
            embed = discord.Embed(
                title="✊✌️✋ 가위바위보 세기의 대결 결과 발표",
                description=f"### {result_title}\n\n"
                            f"{reason_msg}\n\n"
                            f"{payout_msg}",
                color=color
            )
            embed.add_field(name="🐱 단또봇의 실시간 품평회", value=ai_reaction, inline=False)
            
            # Edit parent message to display the final result (without any buttons)
            try:
                await self.parent_msg.edit(embed=embed, view=None)
                await send_rps_debug_log(self.client, "[RPS-DEBUG] Main game board message edited to final result. Game completed successfully!\n")
            except Exception as e:
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Failed to edit parent game board message to final result: {e}")


class RPSEphemeralAcceptView(discord.ui.View):
    def __init__(self, client, challenger: discord.Member, opponent: discord.Member, bet_amount: int, parent_msg: discord.Message, parent_view):
        super().__init__(timeout=30.0)
        self.client = client
        self.challenger = challenger
        self.opponent = opponent
        self.bet_amount = bet_amount
        self.parent_msg = parent_msg
        self.parent_view = parent_view
        
    async def on_timeout(self):
        # We don't need to do much here since the parent_view handles timeout cleanup
        pass
        
    @discord.ui.button(label="🟢 대결 수락", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Ephemeral Accept clicked by: {interaction.user.display_name}"))
            
            # Stop the public timeout view
            self.parent_view.stop()
            self.stop()
            
            # Double check money and registration on acceptance
            db = self.client.db
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Verifying balances in database before starting match (ephemeral)..."))
            u_challenger = await db.get_user(self.challenger.id)
            u_opponent = await db.get_user(self.opponent.id)
            
            if not u_challenger or u_challenger["money"] < self.bet_amount:
                asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Match Aborted (ephemeral): Challenger {self.challenger.display_name} balance too low."))
                ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
                ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
                
                embed = discord.Embed(title="❌ 경기 진행 무산", description=f"신청자 {self.challenger.display_name}님의 자산 부족 문제로 취소되었다냥.", color=0xE74C3C)
                await self.parent_msg.edit(embed=embed, view=None)
                await interaction.response.edit_message(content=f"❌ 신청자 {self.challenger.display_name}님의 보유 자산이 부족하여 경기 진행이 불가능하다냥!", embed=None, view=None)
                return
                
            if not u_opponent or u_opponent["money"] < self.bet_amount:
                asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Match Aborted (ephemeral): Opponent {self.opponent.display_name} balance too low."))
                ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
                ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
                
                embed = discord.Embed(title="❌ 경기 진행 무산", description=f"수락자 {self.opponent.display_name}님의 자산 부족 문제로 취소되었다냥.", color=0xE74C3C)
                await self.parent_msg.edit(embed=embed, view=None)
                await interaction.response.edit_message(content="❌ 본인의 보유 자산이 부족하여 수락이 불가능하다냥!", embed=None, view=None)
                return
                
            # Update cooldown timestamp strictly for the challenger who initiated the challenge
            now = datetime.datetime.now()
            RPS_COOLDOWNS[self.challenger.id] = now
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Cooldown timestamp locked strictly for Challenger {self.challenger.display_name}."))
            
            # We start the game session
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Creating RPSGameSession object..."))
            session = RPSGameSession(self.client, self.challenger, self.opponent, self.bet_amount, self.parent_msg)
            
            # Update public message to choice state (primary response)
            embed = discord.Embed(
                title="✊✌️✋ 선택 페이즈 시작!",
                description=f"### 두 플레이어는 15초 이내에 아래 버튼을 눌러 승부를 내야 한다냥!\n\n"
                            f"• **신청자**: {self.challenger.mention}\n"
                            f"• **수락자**: {self.opponent.mention}\n"
                            f"• **배팅 판돈**: `{self.bet_amount:,}원`\n\n"
                            f"⚠️ **주의**: 아래 가위, 바위, 보 버튼 중 하나를 클릭하면 나만 보기 메시지로 선택이 확정되며 상대방에게는 노출되지 않는다냥!",
                color=0xF39C12
            )
            view = RPSMainChoiceView(self.client, session)
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Editing public board message to Choice Phase and launching RPSMainChoiceView from ephemeral interaction."))
            await self.parent_msg.edit(embed=embed, view=view)
            
            # Edit the B's ephemeral view to confirm acceptance and guide selection
            await interaction.response.edit_message(
                content="✅ 대결을 수락하셨습니다냥!\n메인 화면에 표시된 ✊ 바위, ✌️ 가위, ✋ 보 버튼 중 원하는 선택지를 **15초 이내**에 선택해 주세요!",
                embed=None,
                view=None
            )
            
            # Start the 15-second game countdown in the background
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Starting 15-second background countdown task."))
            asyncio.create_task(view.start_countdown())
        except Exception as e:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-CRITICAL-ERROR] Exception inside ephemeral accept_btn: {e}"))
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            try:
                await interaction.response.edit_message(content="❌ 가위바위보 수락 처리 과정 중 에러가 발생하여 대결이 취소되었다냥!", embed=None, view=None)
            except Exception:
                pass
                
    @discord.ui.button(label="🔴 대결 거절", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Ephemeral Decline button clicked by: {interaction.user.display_name}"))
            
            self.parent_view.stop()
            self.stop()
            
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            
            embed = discord.Embed(
                title="❌ 가위바위보 대결 거절됨",
                description=f"수락자 {self.opponent.mention}님이 세기의 가위바위보 대결 매치를 취소/거절했다냥!",
                color=0xE74C3C
            )
            await self.parent_msg.edit(embed=embed, view=None)
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Decline board message updated via ephemeral decline."))
            
            await interaction.response.edit_message(content="✅ 대결 거절/취소 처리가 완료되었습니다.", embed=None, view=None)
        except Exception as e:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-CRITICAL-ERROR] Exception inside ephemeral decline_btn: {e}"))
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)


class RPSAcceptView(discord.ui.View):
    def __init__(self, client, challenger: discord.Member, opponent: discord.Member, bet_amount: int):
        super().__init__(timeout=30.0) # 30 seconds challenge acceptance timeout
        self.client = client
        self.challenger = challenger
        self.opponent = opponent
        self.bet_amount = bet_amount
        self.message = None
        
    async def on_timeout(self):
        await send_rps_debug_log(self.client, f"[RPS-DEBUG] RPSAcceptView timed out (30 seconds expired). Preparing message cleanup...")
        # Clean up global state
        ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
        ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
        await send_rps_debug_log(self.client, f"[RPS-DEBUG] Discarded player active locks due to timeout. Challenger: {self.challenger.id}, Opponent: {self.opponent.id}")
        
        if self.message:
            try:
                # Completely delete the challenge message on 30-second timeout
                await self.message.delete()
                await send_rps_debug_log(self.client, "[RPS-DEBUG] Timeout SUCCESS: Challenge board message deleted successfully from channel.")
            except Exception as e:
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Timeout WARNING: Failed to delete timed out RPS challenge message: {e}")
            
    @discord.ui.button(label="✉️ 대결 초대장 확인", style=discord.ButtonStyle.success)
    async def view_invitation_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] View invitation button clicked by: {interaction.user.display_name} ({interaction.user.id})"))
            if interaction.user.id != self.opponent.id:
                asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Rejecting invitation click: User {interaction.user.display_name} is not the designated opponent {self.opponent.display_name}"))
                await interaction.response.send_message(f"❌ 이 초대장은 수락 상대방인 {self.opponent.display_name}님 전용이다냥!", ephemeral=True)
                return
                
            # Send ephemeral choice panel
            embed = discord.Embed(
                title="✊✌️✋ 가위바위보 대결 신청 도착!",
                description=f"**{self.challenger.display_name}**님이 가위바위보 대결을 신청했다냥!\n"
                            f"• **배팅 판돈**: `{self.bet_amount:,}원`\n\n"
                            f"수락하여 진정한 맞다이를 까겠냥?",
                color=0x3498DB
            )
            view = RPSEphemeralAcceptView(self.client, self.challenger, self.opponent, self.bet_amount, self.message, self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Sent ephemeral accept/decline view to opponent."))
        except Exception as e:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-CRITICAL-ERROR] Exception inside view_invitation_btn: {e}"))

    @discord.ui.button(label="❌ 대결 취소", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Cancel button clicked by: {interaction.user.display_name} ({interaction.user.id})"))
            if interaction.user.id != self.challenger.id:
                await interaction.response.send_message("❌ 이 대결 신청은 도전자(신청자)만 취소할 수 있다냥!", ephemeral=True)
                return
                
            self.stop()
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            
            embed = discord.Embed(
                title="❌ 가위바위보 대결 취소됨",
                description=f"신청자 {self.challenger.mention}님이 대결 신청을 취소했다냥!",
                color=0xE74C3C
            )
            await interaction.response.edit_message(embed=embed, view=None)
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Match cancelled by challenger. Board message updated."))
        except Exception as e:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-CRITICAL-ERROR] Exception inside cancel_btn: {e}"))


class RPSMainChoiceView(discord.ui.View):
    def __init__(self, client, session: RPSGameSession):
        super().__init__(timeout=20.0)  # slightly longer than 15s to be safe
        self.client = client
        self.session = session
        
    async def start_countdown(self):
        # 15 seconds of action time
        await asyncio.sleep(15.0)
        # Force end the session
        await self.session.process_outcome()
        self.stop()
        
    async def record_choice(self, interaction: discord.Interaction, choice: str):
        user_id = interaction.user.id
        
        # Check if user is in the session
        if user_id != self.session.challenger.id and user_id != self.session.opponent.id:
            await interaction.response.send_message("❌ 이 대결에 관여된 플레이어만 선택할 수 있다냥!", ephemeral=True)
            return

        if self.session.finished:
            await interaction.response.send_message("❌ 이미 대결 시간이 지나가버렸다냥! (시간초과 실격)", ephemeral=True)
            return

        if user_id == self.session.challenger.id:
            if self.session.challenger_choice is not None:
                await interaction.response.send_message("❌ 이미 선택을 완료했다냥!", ephemeral=True)
                return
            self.session.challenger_choice = choice
        else:
            if self.session.opponent_choice is not None:
                await interaction.response.send_message("❌ 이미 선택을 완료했다냥!", ephemeral=True)
                return
            self.session.opponent_choice = choice

        # Inform only the user: "바위를 선택하셨습니냥!"
        await interaction.response.send_message(f"✅ **{choice}**를 선택했다냥!", ephemeral=True)

        asyncio.create_task(send_rps_debug_log(
            self.client, 
            f"[RPS-DEBUG] User {interaction.user.display_name} recorded choice: {choice}"
        ))

        # If both finished picking, immediately trigger result evaluation
        if self.session.challenger_choice is not None and self.session.opponent_choice is not None:
            await self.session.process_outcome()
            self.stop()

    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.primary)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "바위")

    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.success)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "가위")

    @discord.ui.button(label="✋ 보", style=discord.ButtonStyle.danger)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "보")


# Views and Modals for /가르치기 (RAG Knowledge Injection)
class TeachConfirmationView(discord.ui.View):
    def __init__(self, client, price: int, user_money: int):
        super().__init__(timeout=60.0)
        self.client = client
        self.price = price
        self.user_money = user_money
        
    @discord.ui.button(label="🟢 예 (지불 후 가르치기)", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Double check money in case they spent it in the last 60 seconds
        db = self.client.db
        user = await db.get_user(interaction.user.id)
        if not user or user["money"] < self.price:
            await interaction.response.send_message(
                f"❌ 그새 돈을 탕진해버렸냥?! 교육비 `{self.price:,}원`이 부족하다냥!",
                ephemeral=True
            )
            return
            
        # We open a Discord Modal!
        modal = TeachKnowledgeModal(self.client, self.price)
        await interaction.response.send_modal(modal)
        self.stop()
        
    @discord.ui.button(label="🔴 아니오 (취소)", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ 지식 가르치기를 취소했다냥. 뭐, 귀찮은 거 안 외워서 좋다냥.", ephemeral=True)
        self.stop()


class TeachKnowledgeModal(discord.ui.Modal, title="🧠 단또봇 지식 가르치기"):
    knowledge_input = discord.ui.TextInput(
        label="가르칠 정보/지식 내용",
        style=discord.TextStyle.paragraph,
        placeholder="예: 단또봇이 제일 좋아하는 음식은 우주 명작 참치 츄르다냥.",
        required=True,
        min_length=10,
        max_length=1000
    )
    
    def __init__(self, client, price: int):
        super().__init__()
        self.client = client
        self.price = price
        
    async def on_submit(self, interaction: discord.Interaction):
        import os
        db = self.client.db
        user_id = interaction.user.id
        username = interaction.user.display_name
        knowledge_text = self.knowledge_input.value.strip()
        
        # Double check money
        user = await db.get_user(user_id)
        if not user or user["money"] < self.price:
            await interaction.response.send_message(
                f"❌ 트랜잭션 도중 교육비 `{self.price:,}원`이 부족한 것이 감지되었다냥!",
                ephemeral=True
            )
            return
            
        # Deduct money
        new_money = await db.update_money(user_id, -self.price)
        if new_money is None or new_money == -1:
            await interaction.response.send_message("❌ 돈 이체 중 시스템 오류가 발생했다냥!", ephemeral=True)
            return
            
        # Append knowledge to Knowledge_Injection.txt
        rag_manager = getattr(self.client, "rag_manager", None)
        if not rag_manager:
            await interaction.response.send_message("❌ RAG 시스템이 준비되지 않았다냥!", ephemeral=True)
            return
            
        try:
            file_path = os.path.join(rag_manager.knowledge_dir, "Knowledge_Injection.txt")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Check if file exists, if not, write header
            file_exists = os.path.exists(file_path)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n{knowledge_text}")
                
            # Reload knowledge in-memory!
            rag_manager.reload_knowledge()
            
        except Exception as e:
            logger.error(f"Failed to write to Knowledge_Injection.txt: {e}")
            await interaction.response.send_message(f"❌ 지식 파일 저장 도중 시스템 오류 발생: `{e}`", ephemeral=True)
            return
            
        # Generate sassy reaction from AI
        prompt = (
            f"사용자 {username}님이 단또봇에게 같잖은 새로운 지식을 가르치기 위해 무려 {self.price:,}원을 지불하고 과외를 진행했습니다.\n"
            f"• 주입된 지식 내용: \"{knowledge_text}\"\n\n"
            f"돈(무려 {self.price:,}원)을 받았으니 귀찮지만 마지못해 기억해두겠다는 투로, 엄청 퉁명스럽고 싸가지없게 비꼬면서도 "
            f"알겠다며 기억해주겠다고 대답하는 단또봇 특유의 말투(츤데레, 야옹체)로 아주 짧게(2~3문장) 말해주세요."
        )
        ai_reaction = await self.client.llm_client.generate_response(prompt, self.client.persona_prompt)
        
        # Show successful ephemeral response
        embed = discord.Embed(
            title="🧠 지식 가르치기 완료! 🧠",
            description=f"지식 교육이 완벽하게 기억되었다냥!\n\n"
                        f"• **지식 제공자**: {interaction.user.mention}\n"
                        f"• **지불된 교육비**: `{self.price:,}원`\n"
                        f"• **현재 보유 잔고**: `{new_money:,}원`\n\n",
            color=0x2ECC71 # Green
        )
        embed.add_field(name="🐱 단또봇의 교육 후기", value=ai_reaction, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Dispatch Debug Log to Admin Log Channel!
        if self.client.log_channel_id:
            try:
                log_channel = self.client.get_channel(self.client.log_channel_id)
                if not log_channel:
                    log_channel = await self.client.fetch_channel(self.client.log_channel_id)
                if log_channel:
                    debug_embed = discord.Embed(
                        title="🔧 RAG 지식 주입 디버그 로그",
                        color=0x9B59B6, # Purple
                        timestamp=discord.utils.utcnow()
                    )
                    debug_embed.add_field(name="👤 제공자", value=f"{interaction.user.mention} ({user_id})", inline=True)
                    debug_embed.add_field(name="💰 지불된 교육비", value=f"`{self.price:,}원`", inline=True)
                    debug_embed.add_field(name="📁 파일명", value="`Knowledge_Injection.txt`", inline=True)
                    debug_embed.add_field(name="📝 주입된 지식 내용", value=f"```\n{knowledge_text}\n```", inline=False)
                    await log_channel.send(embed=debug_embed)
            except Exception as log_err:
                logger.error(f"Failed to send RAG debug log: {log_err}")

