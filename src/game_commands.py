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
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다옹!", ephemeral=True)
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
                    f"사용자의 어리석음을 놀리며 잔액({existing_user['money']:,}원)을 공개적으로 소문내는 유쾌하고 얄미운 '단또봇' 말투(츤데레, 야옹체)로 아주 짧게(2~3문장) 말해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)
                
                embed = discord.Embed(
                    title="🐱 바보냐옹?! 이미 가입되어 있다옹!",
                    description=f"이미 가입하셔서 웰컴 지원금을 챙겨가셨습니다옹!\n\n"
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
                    f"신규 가입을 격하게 환영하면서, 지원금 50,000원으로 탕진하지 말고 잘 불려보라고 츤데레 섞인 '단또봇' 말투(야옹체)로 짧고 귀엽게(2~3문장) 말해주세요. "
                    f"사용할 수 있는 명령어는 /가입, /출석체크, /룰렛, /확인이 있다는 점도 넌지시 언급해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title="🎉 단또봇 미니게임 회원가입 완료!",
                    description=f"반갑다옹, **{username}**님! 가입 기념 지원금이 입금되었습니다.\n\n"
                                f"💵 **지급 금액:** 50,000원\n"
                                f"🎮 **사용 가능 명령어:**\n"
                                f"• `/가입` : 회원 가입 상태 및 보유 잔고 확인 (중복 가입 시 공개망신)\n"
                                f"• `/출석체크` : 일일 출석 10,000원 획득 (7일 연속 출석 시 100,000원 대박 보너스)\n"
                                f"• `/룰렛 [배팅금액]` : 0~9 무작위 숫자 3개를 맞추는 룰렛 게임 진행 (최소 배팅 500원)\n"
                                f"• `/확인` : 내 소지 잔고 및 출석일, 아이템 확인 (나만 보기)\n\n"
                                f"지금 바로 `/출석체크`나 `/룰렛`에 도전해 보라옹!",
                    color=0x2ECC71  # Green-ish
                )
                embed.add_field(name="🐱 단또봇의 환영 멘트", value=ai_reaction, inline=False)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message("❌ 가입 처리 중 알 수 없는 데이터베이스 오류가 발생했다옹!", ephemeral=True)

        except Exception as e:
            logger.error(f"Error handling register command for {username} ({user_id}): {e}")
            try:
                await interaction.followup.send("❌ 가입 처리 중 예상치 못한 치명적인 오류가 발생했다옹!")
            except Exception:
                await interaction.response.send_message("❌ 가입 처리 중 예상치 못한 치명적인 오류가 발생했다옹!", ephemeral=True)

    @client.tree.command(name="룰렛", description="숫자 3개를 무작위로 추첨하는 룰렛에 금액을 배팅합니다.")
    @app_commands.describe(betting_amount="배팅할 금액을 입력하세요 (보유 잔액 내에서 정수 입력, 최소 500원)")
    async def roulette(interaction: discord.Interaction, betting_amount: int):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다옹!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # 1. Fetch user information
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("⚠️ 아직 미니게임에 가입하지 않으셨습니다옹!\n먼저 `/가입` 명령어를 입력해 가입해 주세요!", ephemeral=True)
                return

            # 2. Check betting amount constraints
            if betting_amount < 500:
                await interaction.response.send_message("❌ 최소 배팅 금액은 **500원**입니다옹!", ephemeral=True)
                return

            if user["money"] < betting_amount:
                await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다옹!\n"
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
                    f"이 기쁜 소식에 대해 '단또봇'으로서 어안이 벙벙해하며 축하하고, "
                    f"자기 일처럼 신나서 츄르를 살 준비를 하라는 츤데레 섞인 장난스러운 축하 멘트를 단또봇 말투(야옹체)로 아주 짧게(2~3문장) 작성해주세요."
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
                    f"당첨을 축하하면서도 다음엔 더 모험해보라며 허세를 피우거나 조언하는 츤데레 '단또봇' 말투(야옹체)의 멘트를 아주 짧게(2~3문장) 작성해주세요."
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
                    f"돈을 날린 사용자를 격하게 비웃고 한심해하며, 고소해 죽겠다는 듯한 얄미우면서도 장난스러운 '단또봇' 특유의 놀림 멘트를 야옹체로 아주 짧고 얄밉게(2~3문장) 작성해주세요."
                )

            # Update database
            new_money = await db.update_money(user_id, winnings_change)
            if new_money is None:
                await interaction.followup.send("❌ 정산 도중 데이터베이스 처리 오류가 발생했다옹!")
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
                await interaction.followup.send("❌ 룰렛 게임 도중 예기치 못한 치명적인 오류가 발생했다옹!")
            except Exception:
                await interaction.response.send_message("❌ 룰렛 게임 도중 예기치 못한 치명적인 오류가 발생했다옹!", ephemeral=True)

    @client.tree.command(name="출석체크", description="하루에 한 번 출석체크하여 재화를 얻습니다. (7일 연속 출석 시 보너스)")
    async def checkin(interaction: discord.Interaction):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다옹!", ephemeral=True)
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
                await interaction.response.send_message("⚠️ 아직 가입하지 않으셨습니다옹!\n먼저 `/가입` 명령어를 통해 등록을 해주세요!", ephemeral=True)
                return

            if status == "already":
                await interaction.response.defer(ephemeral=False)
                
                # Already checked in today. Ask LLM to mock them
                prompt = (
                    f"사용자 {username}님이 오늘 이미 출석체크를 완료했는데, 욕심내서 욕심 부리며 한 번 더 /출석체크를 입력했습니다.\n"
                    f"• 현재 소지 잔고: {result['money']:,}원\n"
                    f"• 연속 출석일수: {result['streak']}일\n\n"
                    f"이 상황에 대해 오늘 이미 출석 보상을 받았으니 내일 다시 오라고 타박하고, "
                    f"욕심쟁이라며 사용자에게 핀잔을 주고 쫓아내려는 새침떼기 '단또봇' 말투(츤데레, 야옹체)로 짧고 귀엽게(2~3문장) 말해주세요."
                )
                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title="🛑 욕심쟁이 집사녀석, 중복 출석 불가다옹!",
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
                    result_title = "🎉 기적의 7일 연속 출석 달성! 대박 보너스! 🎉"
                    color = 0xF1C40F  # Golden
                    prompt = (
                        f"사용자 {username}님이 기어코 '7일 연속 출석체크'를 달성하여 보너스 지원금 {reward:,}원(일반 금액의 10배!)을 획득했습니다!\n"
                        f"• 오늘 지급 보너스: {reward:,}원\n"
                        f"• 현재 사용자의 소지 잔고: {new_money:,}원\n\n"
                        f"기특하게도 매일같이 찾아온 사용자를 기특해하며 격하게 축하해주고, "
                        f"기분이 좋아졌으니 이참에 돈을 크게 불려보라거나 나에게 츄르를 쏘라는 장난기 어필과 축하를 버무린 '단또봇' 말투(야옹체)로 아주 신나게(2~3문장) 말해주세요."
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
                        f"반갑게 아침/하루 인사를 건네며 오늘의 출석 정산금 10,000원을 지급했다는 사실을 알리고, "
                        f"이 돈을 룰렛으로 한순간에 날려먹지 말고 소중히 여기라는 츤데레 섞인 단또봇 말투(야옹체)로 짧게(2~3문장) 말해주세요."
                    )

                ai_reaction = await client.llm_client.generate_response(prompt, client.persona_prompt)

                embed = discord.Embed(
                    title=f"🐱 {username}님 출석 도장 완료다옹!",
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
                await interaction.followup.send("❌ 출석체크 처리 도중 예기치 못한 치명적인 오류가 발생했다옹!")
            except Exception:
                await interaction.response.send_message("❌ 출석체크 처리 도중 예기치 못한 치명적인 오류가 발생했다옹!", ephemeral=True)

    @client.tree.command(name="확인", description="나의 보유 자산, 연속 출석일, 소유 아이템 등을 비밀스럽게 확인합니다. (나만 보기)")
    async def confirm_status(interaction: discord.Interaction):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다옹!", ephemeral=True)
            return

        user_id = interaction.user.id
        username = interaction.user.display_name

        try:
            # Strictly ephemeral = True, only visible to the user who ran the command
            user = await db.get_user(user_id)
            if not user:
                await interaction.response.send_message("⚠️ 아직 가입하지 않으셨습니다옹!\n먼저 `/가입` 명령어를 입력해 등록해 주세요!", ephemeral=True)
                return

            # Display parsing items (JSON parsed as list/list display)
            items_str = user["items"] or "[]"
            # Since items is currently '[]' by default, parse it if needed
            import json
            try:
                items_list = json.loads(items_str)
            except Exception:
                items_list = []
                
            items_display = ", ".join(items_list) if items_list else "소지 중인 아이템이 없습니다옹 🎒"

            embed = discord.Embed(
                title=f"🎒 {username}님의 비밀 가방 정보 카드 🎒",
                description="해당 정보 카드는 오직 귀하에게만 보입니다옹! (Secret/Ephemeral)",
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
            await interaction.response.send_message("❌ 내 정보 확인 도중 치명적인 시스템 요류가 발생했다옹!", ephemeral=True)

    @client.tree.command(name="가위바위보", description="다른 사용자와 가위바위보 내기를 진행합니다. (수수료 20%, 5분 쿨다운)")
    @app_commands.describe(
        opponent="내기를 신청할 대상 디스코드 사용자",
        bet_amount="배팅할 판돈 금액 (500원 ~ 10,000,000원)"
    )
    async def play_rps(interaction: discord.Interaction, opponent: discord.Member, bet_amount: int):
        db = getattr(client, "db", None)
        if not db:
            await interaction.response.send_message("❌ 데이터베이스 시스템이 로딩되지 않았습니다옹!", ephemeral=True)
            return

        challenger = interaction.user
        
        # 1. Basic validations
        if bet_amount < 500 or bet_amount > 10000000:
            await interaction.response.send_message("❌ 배팅 금액은 **500원** 이상, **10,000,000원** 이하 범위에서만 정할 수 있습니다옹!", ephemeral=True)
            return
            
        if challenger.id == opponent.id:
            await interaction.response.send_message("❌ 스스로와 가위바위보를 할 순 없습니다옹!", ephemeral=True)
            return
            
        if opponent.bot:
            await interaction.response.send_message("❌ 봇과는 대적할 수 없습니다옹!", ephemeral=True)
            return

        try:
            # 2. Registration validations
            u_challenger = await db.get_user(challenger.id)
            if not u_challenger:
                await interaction.response.send_message("⚠️ 아직 가입하지 않으셨습니다옹!\n먼저 `/가입` 명령어를 입력해 등록해 주세요!", ephemeral=True)
                return
                
            u_opponent = await db.get_user(opponent.id)
            if not u_opponent:
                await interaction.response.send_message(f"⚠️ 상대방 `{opponent.display_name}`님은 아직 가입하지 않은 상태라 내기가 불가합니다옹!", ephemeral=True)
                return

            # 3. Money balance checks
            if u_challenger["money"] < bet_amount:
                await interaction.response.send_message(
                    f"❌ 배팅할 소지금이 부족합니다옹!\n"
                    f"• 내 잔액: {u_challenger['money']:,}원\n"
                    f"• 신청 배팅액: {bet_amount:,}원",
                    ephemeral=True
                )
                return
                
            if u_opponent["money"] < bet_amount:
                await interaction.response.send_message(
                    f"❌ 상대방 `{opponent.display_name}`님의 보유 골드가 부족하여 내기를 걸 수 없습니다옹!\n"
                    f"• 상대방 보유액: {u_opponent['money']:,}원",
                    ephemeral=True
                )
                return

            # 4. Active players checks
            if challenger.id in ACTIVE_RPS_PLAYERS:
                await interaction.response.send_message("❌ 현재 가위바위보 게임에 대기 중이거나 플레이 중입니다옹!", ephemeral=True)
                return
                
            if opponent.id in ACTIVE_RPS_PLAYERS:
                await interaction.response.send_message(f"❌ 상대방 `{opponent.display_name}`님이 현재 이미 다른 유저와 대결 중입니다옹!", ephemeral=True)
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
                        f"❌ 아직 손가락 쿨다운이 풀리지 않았습니다옹!\n"
                        f"• 남은 재도전 대기시간: **{remaining}초**",
                        ephemeral=True
                    )
                    return
                    
            if opponent.id in RPS_COOLDOWNS:
                diff = now - RPS_COOLDOWNS[opponent.id]
                if diff.total_seconds() < 300:
                    remaining = int(300 - diff.total_seconds())
                    await interaction.response.send_message(
                        f"❌ 상대방 `{opponent.display_name}`님이 최근 승부를 겨뤄 현재 대결 불가 상태입니다옹!\n"
                        f"• 상대방 쿨다운 잔여시간: **{remaining}초**",
                        ephemeral=True
                    )
                    return

            # Lock players in active set
            ACTIVE_RPS_PLAYERS.add(challenger.id)
            ACTIVE_RPS_PLAYERS.add(opponent.id)

            # Build challenge accept view and send public notice
            embed = discord.Embed(
                title="✊✌️✋ 가위바위보 세기의 대결 신청 ⚔️",
                description=f"### {challenger.mention}님이 {opponent.mention}님에게 목숨 건 단판 가위바위보 내기를 걸었습니다옹!\n\n"
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
            await interaction.response.send_message("❌ 가위바위보 신청 진행 중 시스템 에러가 발생했다옹!", ephemeral=True)


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
                reason_msg = "두 분 모두 10초 이내에 선택하지 않아 쌍방 실격(무승부) 처리되었습니다옹!"
                await send_rps_debug_log(self.client, "[RPS-DEBUG] Result determined: Double Timeout (Tie/No action)")
            elif c_choice is None:
                # Challenger A timed out
                winner = self.opponent
                loser = self.challenger
                result_title = f"🏆 {winner.display_name}님 기권승! 🏆"
                color = 0x2ECC71
                reason_msg = f"{self.challenger.display_name}님이 10초 내 선택에 실패하여 {self.opponent.display_name}님이 기권승하셨습니다옹!"
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Opponent {winner.display_name} wins by Challenger timeout")
            elif o_choice is None:
                # Opponent B timed out
                winner = self.challenger
                loser = self.opponent
                result_title = f"🏆 {winner.display_name}님 기권승! 🏆"
                color = 0x2ECC71
                reason_msg = f"{self.opponent.display_name}님이 10초 내 선택에 실패하여 {self.challenger.display_name}님이 기권승하셨습니다옹!"
                await send_rps_debug_log(self.client, f"[RPS-DEBUG] Result determined: Challenger {winner.display_name} wins by Opponent timeout")
            elif c_choice == o_choice:
                # Tie
                result_title = "🤝 가위바위보 비겼습니다옹! 🤝"
                color = 0x3498DB # Blue
                reason_msg = f"두 분 모두 **{choice_emojis[c_choice]}**를 내어 승부가 나지 않았습니다옹. 판돈은 그대로 보존됩니다."
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
                    
                result_title = f"🏆 대결 종료! {winner.display_name}님의 대승리! 🏆"
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
                    payout_msg = "⚠️ [오류] 판돈 이체 정산 중 예상치 못한 DB 오류가 발생했습니다. 수동 정산이 필요합니다옹!"
                    await send_rps_debug_log(self.client, "[RPS-DEBUG] Database ledger update failed! Potential database lock or connection error.")
            else:
                payout_msg = "💵 **베팅 판돈 정산 결과**\n• 무승부 또는 쌍방 기권으로 자산 변동이 없습니다옹!"
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
                    f"가위바위보 결과를 전해 듣고, 승리한 {winner.display_name}님에게는 아주 크게 치켜세워주고 "
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
                ai_reaction = "야옹... 너무 시시한 승부라 말문이 턱 막힌다옹!"
                
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
            
    @discord.ui.button(label="🟢 대결 수락", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Accept button clicked by: {interaction.user.display_name} ({interaction.user.id})"))
        if interaction.user.id != self.opponent.id:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Rejecting accept click: User {interaction.user.display_name} is not the designated opponent {self.opponent.display_name}"))
            await interaction.response.send_message(f"❌ 도전 대상자 파트너인 {self.opponent.display_name}님만 수락할 수 있습니다옹!", ephemeral=True)
            return
            
        # Cancel the accept view timeout
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Correct opponent clicked Accept. Stopping view timeout timer."))
        self.stop()
        
        # Double check money and registration on acceptance
        db = self.client.db
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Verifying balances in database before starting match..."))
        u_challenger = await db.get_user(self.challenger.id)
        u_opponent = await db.get_user(self.opponent.id)
        
        if not u_challenger or u_challenger["money"] < self.bet_amount:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Match Aborted: Challenger {self.challenger.display_name} balance too low or not registered."))
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            
            # Primary response: edit the message to failed status
            embed = discord.Embed(title="❌ 경기 진행 무산", description=f"신청자 {self.challenger.display_name}님의 자산 부족 문제로 취소되었습니다옹.", color=0xE74C3C)
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Secondary response: send ephemeral error explanation
            try:
                await interaction.followup.send(f"❌ 신청자 {self.challenger.display_name}님의 보유 자산이 신청 시점과 달리 모자라 경기 진행이 불가능합니다옹!", ephemeral=True)
            except Exception:
                pass
            return
            
        if not u_opponent or u_opponent["money"] < self.bet_amount:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Match Aborted: Opponent {self.opponent.display_name} balance too low or not registered."))
            ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
            ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
            
            # Primary response: edit the message to failed status
            embed = discord.Embed(title="❌ 경기 진행 무산", description=f"수락자 {self.opponent.display_name}님의 자산 부족 문제로 취소되었습니다옹.", color=0xE74C3C)
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Secondary response: send ephemeral error explanation
            try:
                await interaction.followup.send("❌ 본인의 미니게임 가입 보유 자산이 배팅액 대비 부족하여 수락이 불가능하다옹!", ephemeral=True)
            except Exception:
                pass
            return
            
        # Update cooldown timestamp to current time for both players to lock them
        now = datetime.datetime.now()
        RPS_COOLDOWNS[self.challenger.id] = now
        RPS_COOLDOWNS[self.opponent.id] = now
        asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Cooldown timestamp locked for players."))
        
        # We start the game session
        asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Creating RPSGameSession object..."))
        session = RPSGameSession(self.client, self.challenger, self.opponent, self.bet_amount, interaction.message)
        
        # Update public message to choice state (primary response)
        embed = discord.Embed(
            title="✊✌️✋ 선택 페이즈 시작!",
            description=f"### 두 플레이어는 10초 이내에 자신의 숨겨진 선택지를 클릭해야 합니다옹!\n\n"
                        f"• **신청자**: {self.challenger.mention}\n"
                        f"• **수락자**: {self.opponent.mention}\n"
                        f"• **배팅 판돈**: `{self.bet_amount:,}원`\n\n"
                        f"⚠️ **주의**: 아래 본인의 이름이 들어간 버튼을 눌러 나오는 나만 보기 화면에서 가위, 바위, 보 중 하나를 10초 이내에 눌러야 합니다!",
            color=0xF39C12
        )
        view = RPSMainChoiceView(self.client, session)
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Editing board message to Choice Phase and launching RPSMainChoiceView."))
        await interaction.response.edit_message(embed=embed, view=view)
        
        # Send ephemeral choice response to opponent B immediately using followup
        try:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Sending private choice panel to opponent B {self.opponent.display_name} via followup..."))
            await interaction.followup.send(
                "✅ 대결을 수락하셨습니다옹!\n아래 바위, 가위, 보 중 하나를 **10초 이내**에 선택해 주세요!",
                view=RPSIndividualChoiceView(self.opponent.id, session),
                ephemeral=True
            )
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Private choice panel sent successfully to B."))
        except Exception as followup_err:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Failed to send opponent B followup choice message: {followup_err}"))
        
        # Start the 10-second game countdown in the background
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Starting 10-second background countdown task."))
        asyncio.create_task(view.start_countdown())
        
    @discord.ui.button(label="🔴 대결 거절", style=discord.ButtonStyle.secondary)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Decline button clicked by: {interaction.user.display_name} ({interaction.user.id})"))
        if interaction.user.id != self.opponent.id and interaction.user.id != self.challenger.id:
            asyncio.create_task(send_rps_debug_log(self.client, f"[RPS-DEBUG] Rejecting decline click: User {interaction.user.display_name} is not challenger or opponent."))
            await interaction.response.send_message("❌ 이 매치에 관여된 플레이어만 판돈 거절을 누를 수 있습니다옹!", ephemeral=True)
            return
            
        self.stop()
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Declining match. Unlocking players and updating board message."))
        
        ACTIVE_RPS_PLAYERS.discard(self.challenger.id)
        ACTIVE_RPS_PLAYERS.discard(self.opponent.id)
        
        who = "상대방" if interaction.user.id == self.opponent.id else "신청자"
        embed = discord.Embed(
            title="❌ 가위바위보 대결 거절됨",
            description=f"{who} {interaction.user.mention}님이 세기의 가위바위보 대결 매치를 취소/거절하셨습니다옹!",
            color=0xE74C3C
        )
        
        # Primary response: edit message to show declined status and remove buttons
        await interaction.response.edit_message(embed=embed, view=None)
        asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Decline board message updated."))
        
        # Secondary response: send ephemeral confirmation
        try:
            await interaction.followup.send("✅ 대결 거절/취소 처리가 완료되었습니다.", ephemeral=True)
            asyncio.create_task(send_rps_debug_log(self.client, "[RPS-DEBUG] Private decline confirmation sent."))
        except Exception:
            pass


class RPSMainChoiceView(discord.ui.View):
    def __init__(self, client, session: RPSGameSession):
        super().__init__(timeout=15.0)  # slightly longer than 10s to be safe
        self.client = client
        self.session = session
        
    async def start_countdown(self):
        # 10 seconds of action time
        await asyncio.sleep(10.0)
        # Force end the session
        await self.session.process_outcome()
        self.stop()
        
    @discord.ui.button(label="🅰️ A의 선택지 열기 (A 전용)", style=discord.ButtonStyle.primary)
    async def choice_a_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.challenger.id:
            await interaction.response.send_message("❌ 이 버튼은 신청자(A) 전용입니다옹!", ephemeral=True)
            return
            
        if self.session.challenger_choice is not None:
            await interaction.response.send_message("❌ 이미 선택을 완료하셨습니다옹!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "🔒 **신청자 A 전용 개인 가위바위보 비밀 선택지**\n아래 가위, 바위, 보 중 하나를 즉시 선택하세요! (10초 제한)",
            view=RPSIndividualChoiceView(self.session.challenger.id, self.session),
            ephemeral=True
        )
        
    @discord.ui.button(label="🅱️ B의 선택지 열기 (B 전용)", style=discord.ButtonStyle.success)
    async def choice_b_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.opponent.id:
            await interaction.response.send_message("❌ 이 버튼은 수락자(B) 전용입니다옹!", ephemeral=True)
            return
            
        if self.session.opponent_choice is not None:
            await interaction.response.send_message("❌ 이미 선택을 완료하셨습니다옹!", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "🔒 **수락자 B 전용 개인 가위바위보 비밀 선택지**\n아래 가위, 바위, 보 중 하나를 즉시 선택하세요! (10초 제한)",
            view=RPSIndividualChoiceView(self.session.opponent.id, self.session),
            ephemeral=True
        )


class RPSIndividualChoiceView(discord.ui.View):
    def __init__(self, player_id: int, session: RPSGameSession):
        super().__init__(timeout=10.0)
        self.player_id = player_id
        self.session = session
        
    async def record_choice(self, interaction: discord.Interaction, choice: str):
        if self.session.finished:
            await interaction.response.send_message("❌ 이미 대결 시간이 지나가버렸습니다옹! (시간초과 실격)", ephemeral=True)
            return
            
        if self.player_id == self.session.challenger.id:
            if self.session.challenger_choice is not None:
                await interaction.response.send_message("❌ 이미 선택지를 지정하셨습니다옹!", ephemeral=True)
                return
            self.session.challenger_choice = choice
        else:
            if self.session.opponent_choice is not None:
                await interaction.response.send_message("❌ 이미 선택지를 지정하셨습니다옹!", ephemeral=True)
                return
            self.session.opponent_choice = choice
            
        await interaction.response.send_message(f"✅ 숨김 선택으로 **'{choice}'**를 확실하게 지명하셨습니다옹!", ephemeral=True)
        self.stop()
        
        # If both finished picking, immediately trigger result evaluation before 10s expires
        if self.session.challenger_choice is not None and self.session.opponent_choice is not None:
            await self.session.process_outcome()
            
    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.secondary)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "바위")
        
    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.secondary)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "가위")
        
    @discord.ui.button(label="✋ 보", style=discord.ButtonStyle.secondary)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "보")

