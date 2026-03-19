"""观点交易所 — 4 阶段辩论引擎

1. 圆桌讨论 (Roundtable) — 2 轮自由讨论
2. 亮牌下注 (Reveal & Bet) — CPMM 市场定价
3. 站队辩护 (Team Defense) — 按阵营辩护，允许叛变
4. 刘看山裁决 (Judge Ruling) — 裁决 + 结算
"""

import json
import uuid
from collections import Counter
from datetime import datetime
from openai import OpenAI
from agents.personalities import AGENT_PERSONALITIES, JUDGE_PERSONALITY
from services.llm import call_llm, parse_json_from_text, build_transcript_context
from services.pricing import calculate_option_prices
from services.zhihu_api import search_credible_formatted
from config import SHARE_PAYOUT


def get_agents_for_debate(custom_agents: list[dict]) -> list[dict]:
    """Return the 5 built-in agents plus any custom agents."""
    agents = list(AGENT_PERSONALITIES)
    for ca in custom_agents:
        agents.append({
            "id": ca.get("id", uuid.uuid4().hex[:6]),
            "name": ca.get("name", "自定义Agent"),
            "emoji": ca.get("emoji", "🤖"),
            "description": ca.get("description", "用户自定义Agent"),
            "risk_appetite": ca.get("risk_appetite", 0.5),
            "system_prompt": ca.get(
                "system_prompt",
                f"你是一个辩论参与者，名叫{ca.get('name', '自定义Agent')}。请用中文发表你的观点。",
            ),
        })
    return agents


def generate_options_for_topic(client: OpenAI, title: str) -> list[dict]:
    """Use LLM to generate appropriate debate options for a topic.

    Returns 2-6 options depending on topic complexity (Task 4: improved).
    """
    prompt = (
        f"辩题：「{title}」\n\n"
        "请为这个辩题生成合适的选项。规则：\n"
        "- 二元对立问题（如'该不该'、'会不会'、'是不是'）：生成 2 个选项\n"
        "- 有明显第三方视角的二元问题：生成 3 个选项（含中间立场）\n"
        "- 原因分析类问题（如'为什么'、'问题出在哪'）：生成 4-5 个选项\n"
        "- 方案选择类问题（如'怎么办'、'哪种方式'）：生成 4-6 个选项\n"
        "- 预测类问题（如'未来会怎样'）：生成 3-5 个选项\n"
        "- 多因素评价问题（如'最重要的是什么'）：生成 4-6 个选项\n\n"
        "【重要】不要总是生成3个选项！根据话题复杂度选择合适的数量。\n"
        "简单二选一的话题就生成2个，复杂多因素话题要生成4-6个。\n\n"
        "- 每个选项应该代表一个明确的、有人会支持的立场\n"
        "- 选项之间应该有真正的分歧，不能都是同一个意思\n"
        "- 对于复杂话题，可以包含一个辩证/中间立场的选项\n"
        "- 选项文字简洁有力，每个不超过10个字\n\n"
        '只输出 JSON 数组，格式：\n'
        '[{"label": "选项1"}, {"label": "选项2"}, ...]\n'
        "不要有其他文字。"
    )

    try:
        text = call_llm(
            client,
            "你是一个辩论主持人，负责设计公平有趣的辩论选项。只输出JSON。",
            [{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        # Parse JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            options = json.loads(text[start:end])
            if isinstance(options, list) and len(options) >= 2:
                default_colors = [
                    "#4ecdc4", "#ff6b6b", "#ffd93d",
                    "#6c5ce7", "#a8e6cf", "#ff8a5c",
                ]
                return [
                    {
                        "key": f"option_{i}",
                        "label": opt.get("label", f"选项{i+1}"),
                        "color": default_colors[i % len(default_colors)],
                    }
                    for i, opt in enumerate(options[:6])  # Max 6 options
                ]
    except Exception as e:
        print(f"Option generation failed: {e}")

    # Fallback: 用话题本身再试一次，简化 prompt
    try:
        text2 = call_llm(
            client,
            "为这个话题生成3-5个不同的观点立场，每个不超过8个字。只输出JSON数组：[{\"label\":\"观点1\"},{\"label\":\"观点2\"}]",
            [{"role": "user", "content": title}],
            max_tokens=200,
        )
        start = text2.find("[")
        end = text2.rfind("]") + 1
        if start >= 0 and end > start:
            opts2 = json.loads(text2[start:end])
            if isinstance(opts2, list) and len(opts2) >= 2:
                default_colors = ["#4ecdc4", "#ff6b6b", "#ffd93d", "#6c5ce7", "#a8e6cf"]
                return [
                    {"key": f"option_{i}", "label": opt.get("label", f"观点{i+1}"), "color": default_colors[i % len(default_colors)]}
                    for i, opt in enumerate(opts2[:5])
                ]
    except Exception:
        pass

    # 最终 fallback
    return [
        {"key": "option_0", "label": "完全赞同", "color": "#4ecdc4"},
        {"key": "option_1", "label": "不太认同", "color": "#ff6b6b"},
        {"key": "option_2", "label": "需要更多信息", "color": "#ffd93d"},
        {"key": "option_3", "label": "有更好的角度", "color": "#6c5ce7"},
    ]


def run_phase1_roundtable(
    client: OpenAI,
    debate: dict,
    agents: list[dict],
) -> list[dict]:
    """Phase 1: 圆桌讨论 — 2 rounds of open discussion.

    Round 1: Each agent gives initial opinion, can ask questions.
    Round 2: Agents respond to round 1, refine positions.
    """
    transcript = list(debate.get("transcript", []))
    options_text = "\n".join(
        f"  - [{opt['key']}] {opt['label']}: {opt.get('description', '')}"
        for opt in debate["options"]
    )

    for round_num in range(1, 3):
        round_label = "第一轮" if round_num == 1 else "第二轮"
        phase_name = f"圆桌讨论-{round_label}"

        for agent in agents:
            context = build_transcript_context(transcript)

            if round_num == 1:
                # Include Zhihu answer data if available in context
                zhihu_context = debate.get('context', '')
                if zhihu_context:
                    zhihu_context = f"以下是知乎社区对这个话题的真实讨论：\n{zhihu_context}"

                user_content = (
                    f"辩题：「{debate['title']}」\n\n"
                    f"{zhihu_context}\n\n"
                    f"可选立场：\n{options_text}\n\n"
                    f"{'之前的发言：' + chr(10) + context + chr(10) if context else ''}"
                    f"这是圆桌讨论{round_label}。请发表你对这个辩题的初步看法，"
                    f"分析各个选项的优劣。你可以向其他参与者提出问题。\n"
                    f"发言控制在200字以内，要有你的性格特色（{agent['description']}）。\n"
                    f"直接发表你的观点，不要输出JSON。"
                )
            else:
                user_content = (
                    f"辩题：「{debate['title']}」\n\n"
                    f"背景信息：{debate.get('context', '')}\n\n"
                    f"可选立场：\n{options_text}\n\n"
                    f"之前的发言：\n{context}\n\n"
                    f"这是圆桌讨论{round_label}。请回应其他参与者在第一轮的发言，"
                    f"回答别人的问题，或对别人的观点发起挑战。可以进一步阐明你的立场。\n"
                    f"发言控制在200字以内，要有你的性格特色（{agent['description']}）。\n"
                    f"直接发表你的观点，不要输出JSON。"
                )

            try:
                text = call_llm(
                    client,
                    agent["system_prompt"],
                    [{"role": "user", "content": user_content}],
                    max_tokens=512,
                )
            except Exception as e:
                text = f"（{agent['name']}思考中遇到了困难：{e}）"

            msg = {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "agent_emoji": agent["emoji"],
                "content": text.strip(),
                "phase": phase_name,
                "round_num": round_num,
                "target_agent": None,
                "timestamp": datetime.now().isoformat(),
            }
            transcript.append(msg)

    return transcript


def run_phase2_reveal_bet(
    client: OpenAI,
    debate: dict,
    agents: list[dict],
    transcript: list[dict],
) -> tuple[list[dict], dict[str, float]]:
    """Phase 2: 亮牌下注 — Agents buy ONE SHARE at the current market price.

    Uses Polymarket-style CPMM pricing:
    - Each option's price is determined by market demand
    - Agent pays the current option price for 1 share
    - If they win, they get 100; if they lose, they lose their purchase price

    Returns (bets, final_market_prices).
    """
    options_text = "\n".join(
        f"  - [{opt['key']}] {opt['label']}: {opt.get('description', '')}"
        for opt in debate["options"]
    )
    option_keys = [opt["key"] for opt in debate["options"]]
    context = build_transcript_context(transcript)

    # Personality-based guidance
    personality_guidance = {
        "bull": "你天生乐观，倾向于选择最积极、最有希望的那个选项。如果有代表变革或进步的选项，那就是你的菜。",
        "bear": "你天生悲观谨慎，倾向于选择最保守、最指出问题的那个选项。你看到的永远是风险。",
        "fox": "你是逆向思维者。大多数人会选什么？你偏不选。找到最被忽视或最反直觉的那个选项。",
        "owl": "你是学者，倾向于选择最辩证、最有条件的选项（如果有'取决于''看情况'这类中间立场，那就是你的选择）。如果没有中间选项，选证据最充分的。",
        "degen": "你凭直觉走，哪个选项让你觉得最刺激、最有赌性，就选哪个。不需要理由，跟着感觉冲。",
    }

    # Track bets placed so far (for dynamic price calculation)
    bets_so_far: list[dict] = []
    chosen_so_far: list[str] = []

    # Fixed bet: 200积分 / 选项数, 每人只能押1份
    INITIAL_BALANCE = 200
    n_opts = len(option_keys)
    fixed_bet = INITIAL_BALANCE // n_opts

    bets = []
    for agent in agents:
        guidance = personality_guidance.get(agent["id"], "根据你的性格自由选择一个立场。")

        # Calculate current market prices for display only
        current_prices = calculate_option_prices(option_keys, bets_so_far)
        prices_display = " | ".join(
            f"[{k}] {current_prices[k]:.1f}¢" for k in option_keys
        )

        # Diversity pressure
        diversity_hint = ""
        if chosen_so_far:
            counts = Counter(chosen_so_far)
            most_common_key = counts.most_common(1)[0][0]
            most_common_label = next(
                (o["label"] for o in debate["options"] if o["key"] == most_common_key),
                most_common_key,
            )
            if counts[most_common_key] >= 2:
                diversity_hint = (
                    f"\n注意：已经有 {counts[most_common_key]} 个参与者选择了「{most_common_label}」。"
                    f"作为{agent['description']}，你真的也要跟风吗？考虑一下其他选项。"
                )

        constraint = f"{guidance}{diversity_hint}"

        user_content = (
            f"辩题：「{debate['title']}」\n\n"
            f"背景信息：{debate.get('context', '')}\n\n"
            f"可选立场：\n{options_text}\n\n"
            f"规则：每人固定下注 {fixed_bet} 积分，选一个你支持的选项。赢了瓜分输家的积分。\n\n"
            f"之前的圆桌讨论：\n{context}\n\n"
            f"现在是「亮牌下注」环节。你需要选一个立场，固定下注 {fixed_bet} 积分。\n\n"
            f"{constraint}\n"
            f"你的性格：{agent['description']}\n\n"
            f"请只输出 JSON，格式如下（不要有任何其他文字）：\n"
            f"{{\n"
            f'  "chosen_option": "选项key，只能是 {option_keys} 中的一个",\n'
            f'  "confidence": 0.1到1.0之间的小数,\n'
            f'  "reasoning": "你选择这个立场的原因（50字以内）"\n'
            f"}}"
        )

        try:
            text = call_llm(
                client,
                agent["system_prompt"] + "\n注意：你必须只输出JSON，不要有其他文字。",
                [{"role": "user", "content": user_content}],
                max_tokens=256,
            )
            data = parse_json_from_text(text)
        except Exception:
            data = {}

        chosen = str(data.get("chosen_option", "")).strip()
        print(f"  [BET] {agent['name']}: raw chosen_option={chosen!r}, data={data}")

        if chosen not in option_keys:
            # Try fuzzy: maybe LLM returned label instead of key
            matched = False
            for opt in debate["options"]:
                if opt["label"] in chosen or chosen in opt["label"] or chosen == opt["key"]:
                    chosen = opt["key"]
                    matched = True
                    break
            if not matched:
                # Fallback: pick least-chosen option to maximize divergence
                counts = Counter(chosen_so_far)
                least_chosen = min(option_keys, key=lambda k: counts.get(k, 0))
                chosen = least_chosen
                print(f"  [BET] {agent['name']}: FALLBACK to least-chosen={chosen}")

        # Fixed bet amount for all agents
        purchase_price = fixed_bet

        try:
            confidence = max(0.1, min(1.0, float(data.get("confidence", 0.5))))
        except (ValueError, TypeError):
            confidence = 0.5

        chosen_label = next(
            (opt["label"] for opt in debate["options"] if opt["key"] == chosen),
            chosen,
        )

        # Track for dynamic pricing and diversity
        chosen_so_far.append(chosen)

        bet = {
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "agent_emoji": agent["emoji"],
            "chosen_option": chosen,
            "chosen_label": chosen_label,
            "bet_amount": round(purchase_price, 1),
            "purchase_price": round(purchase_price, 1),
            "confidence": round(confidence, 2),
            "reasoning": data.get("reasoning", "直觉判断"),
        }
        bets.append(bet)
        bets_so_far.append(bet)

    # Final market prices after all bets
    final_prices = calculate_option_prices(option_keys, bets)
    return bets, final_prices


def run_phase3_team_defense(
    client: OpenAI,
    debate: dict,
    agents: list[dict],
    transcript: list[dict],
    bets: list[dict],
) -> list[dict]:
    """Phase 3: 站队辩护 — Agents grouped by option, defend their choice.

    Agents can try to convince others to defect. 1 round.
    """
    options_text = "\n".join(
        f"  - [{opt['key']}] {opt['label']}: {opt.get('description', '')}"
        for opt in debate["options"]
    )
    context = build_transcript_context(transcript)

    # Build team info
    teams: dict[str, list[dict]] = {}
    agent_bets: dict[str, dict] = {}
    for bet in bets:
        teams.setdefault(bet["chosen_option"], []).append(bet)
        agent_bets[bet["agent_id"]] = bet

    teams_summary = []
    for opt_key, team_bets in teams.items():
        opt_label = next(
            (o["label"] for o in debate["options"] if o["key"] == opt_key),
            opt_key,
        )
        members = ", ".join(
            f"{b['agent_emoji']}{b['agent_name']}(买入价{b['purchase_price']}¢)"
            for b in team_bets
        )
        total = sum(b["purchase_price"] for b in team_bets)
        teams_summary.append(f"  【{opt_label}】阵营：{members} | 总投入: {total:.1f}¢")
    teams_text = "\n".join(teams_summary)

    defense_messages = []
    for agent in agents:
        bet = agent_bets.get(agent["id"])
        if not bet:
            continue

        my_label = bet["chosen_label"]
        my_option = bet["chosen_option"]

        # Find opponents
        opponents = [
            f"{b['agent_emoji']}{b['agent_name']}({b['chosen_label']})"
            for b in bets
            if b["chosen_option"] != my_option
        ]
        opponents_text = ", ".join(opponents) if opponents else "无"

        user_content = (
            f"辩题：「{debate['title']}」\n\n"
            f"你的立场：{my_label}\n"
            f"你的买入价：{bet['purchase_price']}¢（赢了得{SHARE_PAYOUT}¢，净赚{SHARE_PAYOUT - bet['purchase_price']:.1f}¢）\n\n"
            f"各阵营情况：\n{teams_text}\n\n"
            f"对手：{opponents_text}\n\n"
            f"之前的讨论和下注：\n{context}\n\n"
            f"现在是「站队辩护」环节。你需要：\n"
            f"1. 做一段有力的最终陈词，捍卫你选择的立场「{my_label}」\n"
            f"2. 攻击对方阵营的弱点\n"
            f"3. 你可以尝试说服对方阵营的某个Agent叛变到你这边\n\n"
            f"你也可以选择「叛变」——如果你在讨论中被说服了，可以改变立场。\n\n"
            f"请只输出 JSON：\n"
            f"{{\n"
            f'  "defense_speech": "你的最终陈词（150字以内）",\n'
            f'  "target_agent": "你想说服的对方Agent名字，没有则为null",\n'
            f'  "defect": false,\n'
            f'  "defect_to": "如果叛变，新立场的key；不叛变则为null"\n'
            f"}}"
        )

        try:
            text = call_llm(
                client,
                agent["system_prompt"] + "\n注意：你必须只输出JSON，不要有其他文字。",
                [{"role": "user", "content": user_content}],
                max_tokens=512,
            )
            data = parse_json_from_text(text)
        except Exception:
            data = {"defense_speech": "我坚持我的立场。", "defect": False}

        option_keys = [opt["key"] for opt in debate["options"]]

        defected = data.get("defect", False)
        defect_to = data.get("defect_to")
        new_option = my_option
        new_label = my_label

        if defected and defect_to and defect_to in option_keys and defect_to != my_option:
            new_option = defect_to
            new_label = next(
                (o["label"] for o in debate["options"] if o["key"] == defect_to),
                defect_to,
            )
            # Update the bet record
            bet["chosen_option"] = new_option
            bet["chosen_label"] = new_label

        msg = {
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "agent_emoji": agent["emoji"],
            "content": data.get("defense_speech", "我坚持我的立场。"),
            "phase": "站队辩护",
            "round_num": 1,
            "target_agent": data.get("target_agent"),
            "defected": defected and defect_to in option_keys and defect_to != my_option,
            "old_option": my_option if defected else None,
            "new_option": new_option if defected else None,
            "old_label": my_label if defected else None,
            "new_label": new_label if defected else None,
            "timestamp": datetime.now().isoformat(),
        }
        defense_messages.append(msg)

    return defense_messages


def run_phase4_judgment(
    client: OpenAI,
    debate: dict,
    transcript: list[dict],
    bets: list[dict],
    defense_messages: list[dict],
) -> dict:
    """Phase 4: 刘看山裁决 — Judge reviews all content, picks winner, calculates payouts.

    Payout model (Polymarket-style):
    - Winners: receive SHARE_PAYOUT (100) per share, profit = 100 - purchase_price
    - Losers: lose their purchase_price (the amount they paid for the share)
    """

    # Build full debate record for judge
    options_text = "\n".join(
        f"  - [{opt['key']}] {opt['label']}: {opt.get('description', '')}"
        for opt in debate["options"]
    )
    option_keys = [opt["key"] for opt in debate["options"]]

    # Transcript context
    discussion_text = build_transcript_context(transcript)

    # Bets summary (with market prices)
    bets_lines = []
    for b in bets:
        bets_lines.append(
            f"  {b['agent_emoji']}{b['agent_name']}: "
            f"选择【{b['chosen_label']}】，买入价 {b.get('purchase_price', b.get('bet_amount', 0))}¢/股，"
            f"信心 {b['confidence']:.0%}，理由：{b['reasoning']}"
        )
    bets_text = "\n".join(bets_lines)

    # Defense messages
    defense_lines = []
    for msg in defense_messages:
        defect_note = ""
        if msg.get("defected"):
            defect_note = f" [叛变！从{msg['old_label']}转向{msg['new_label']}]"
        target_note = f" (对 @{msg['target_agent']})" if msg.get("target_agent") else ""
        defense_lines.append(
            f"  {msg['agent_emoji']}{msg['agent_name']}{target_note}{defect_note}: {msg['content']}"
        )
    defense_text = "\n".join(defense_lines)

    options_json_keys = ", ".join(f'"{k}"' for k in option_keys)

    # ── 知乎可信搜：为裁判提供真实数据 ──
    search_context = ""
    try:
        search_results = search_credible_formatted(debate["title"], count=5)
        if search_results:
            search_context = (
                f"\n===== 【知乎可信搜数据】（PRIMARY 证据来源，必须优先引用） =====\n"
                f"以下是知乎社区对「{debate['title']}」的真实讨论摘要。\n"
                f"【重要指令】你必须在裁决中：\n"
                f"  1. 引用至少2条可信搜数据作为裁决依据\n"
                f"  2. 标注来源（如「据知乎@xxx的分析（N赞）...」）\n"
                f"  3. 在「数据裁定依据」部分列出所有引用的数据源\n\n"
                f"{search_results}\n\n"
            )
            print(f"[可信搜] Found results for: {debate['title'][:30]}")
        else:
            search_context = (
                "\n【注意】本次裁决未获取到知乎可信搜数据，请完全基于辩论内容裁决，"
                "并在报告中说明「本次裁决缺乏外部数据验证，仅基于辩论内容」。\n\n"
            )
            print(f"[可信搜] No results for: {debate['title'][:30]} (judge will use debate content only)")
    except Exception as e:
        print(f"[可信搜] Search failed: {e}")

    user_content = (
        f"辩题：「{debate['title']}」\n\n"
        f"背景信息：{debate.get('context', '')}\n\n"
        f"可选立场：\n{options_text}\n\n"
        f"===== 圆桌讨论记录 =====\n{discussion_text}\n\n"
        f"===== 下注情况（Polymarket CPMM 定价） =====\n{bets_text}\n\n"
        f"===== 站队辩护 =====\n{defense_text}\n"
        f"{search_context}"
        f"请综合以上全部信息，做出你的裁决。\n\n"
        f"裁决标准（100分制，对每个选项分别打分）：\n"
        f"  - 事实依据（30分）：论点是否有真实数据支撑？是否与可信搜数据一致？引用了哪些可信来源？\n"
        f"  - 逻辑严密（25分）：推理链条是否完整？有无逻辑谬误？\n"
        f"  - 反驳质量（20分）：对对方论点的反驳是否击中要害？\n"
        f"  - 社会共识（15分）：是否契合知乎社区和社会多数人的真实体验？\n"
        f"  - 可操作性（10分）：方案是否可落地？代价收益是否合理？\n\n"
        f"【裁决报告要求——知乎高赞回答风格】\n"
        f"你的 reasoning 字段必须包含以下5个部分（用标记分隔）：\n"
        f"1.【结论先行】开篇直接亮明裁决结果（1-2句话）\n"
        f"2.【证据分析】逐一分析每个选项的数据支撑，引用Agent原话和可信搜数据\n"
        f"3.【反方声音】承认败方论点中合理的部分\n"
        f"4.【数据裁定依据】列出支持裁决的关键数据点和来源（可信搜数据优先）\n"
        f"5.【最终结论】重申结果，给出简短有力的总结\n"
        f"全文400-600字。\n\n"
        f"请只输出 JSON：\n"
        f"{{\n"
        f'  "winning_option": 必须是 [{options_json_keys}] 中的一个,\n'
        f'  "reasoning": "详细裁决报告（400-600字），必须包含上述5个部分",\n'
        f'  "option_analysis": {{"各选项key": {{"score": 总分, "strength": "核心优势（50字以内）", "weakness": "致命弱点（50字以内）", "key_evidence": "最有力的一条证据", "data_support": "可信搜数据支撑情况"}}}},\n'
        f'  "scores": {{"各选项key": {{"facts": 0-30, "logic": 0-25, "rebuttal": 0-20, "consensus": 0-15, "feasibility": 0-10, "total": 0-100}}}},\n'
        f'  "mvp": "表现最好的Agent名字（不含emoji）",\n'
        f'  "mvp_reason": "为什么这个Agent是MVP（50字以内）",\n'
        f'  "highlights": ["精彩瞬间1：谁说了什么（引用原话），为什么精彩", "精彩瞬间2", "精彩瞬间3"],\n'
        f'  "data_sources": ["裁决引用的数据来源1（标注来自可信搜还是辩论内容）", "数据来源2"]\n'
        f"}}"
    )

    try:
        text = call_llm(
            client,
            JUDGE_PERSONALITY["system_prompt"] + "\n注意：你必须只输出合法JSON，不要有其他文字。不要使用markdown代码块。",
            [{"role": "user", "content": user_content}],
            max_tokens=2048,
        )
        ruling = parse_json_from_text(text)
        if not ruling:
            print(f"[JUDGE] JSON parse failed. Raw text (first 300): {text[:300]}")
    except Exception as e:
        print(f"[JUDGE] LLM error: {e}")
        ruling = {}

    winning_option = ruling.get("winning_option", "")
    if winning_option not in option_keys:
        # Fallback: option with most total bets
        option_totals: dict[str, float] = {}
        for b in bets:
            option_totals[b["chosen_option"]] = (
                option_totals.get(b["chosen_option"], 0)
                + b.get("purchase_price", b.get("bet_amount", 0))
            )
        winning_option = (
            max(option_totals, key=option_totals.get)
            if option_totals
            else option_keys[0]
        )

    winning_label = next(
        (o["label"] for o in debate["options"] if o["key"] == winning_option),
        winning_option,
    )

    # ── 固定下注积分制结算 ──
    # 所有人下注相同金额，赢家平分输家的积分池
    total_pool = sum(
        b.get("bet_amount", 0) for b in bets
    )
    winners = [b for b in bets if b["chosen_option"] == winning_option]
    losers = [b for b in bets if b["chosen_option"] != winning_option]
    loser_pool = sum(b.get("bet_amount", 0) for b in losers)
    win_bonus = round(loser_pool / len(winners), 1) if winners else 0

    payouts = {}
    for b in bets:
        bet_amt = b.get("bet_amount", 0)
        if b["chosen_option"] == winning_option:
            payouts[b["agent_name"]] = {
                "bet": bet_amt,
                "payout": bet_amt + win_bonus,
                "profit": win_bonus,
                "net": win_bonus,
                "result": "win",
            }
        else:
            payouts[b["agent_name"]] = {
                "bet": bet_amt,
                "payout": 0,
                "profit": -bet_amt,
                "net": -bet_amt,
                "result": "lose",
            }

    judgment = {
        "winning_option": winning_option,
        "winning_label": winning_label,
        "reasoning": ruling.get("reasoning", "裁判综合考量后做出了裁决。"),
        "option_analysis": ruling.get("option_analysis", {}),
        "scores": ruling.get("scores", {}),
        "mvp": ruling.get("mvp", ""),
        "mvp_reason": ruling.get("mvp_reason", ""),
        "highlights": ruling.get("highlights", []),
        "data_sources": ruling.get("data_sources", []),
        "total_pool": total_pool,
        "loser_pool": loser_pool,
        "payouts": payouts,
    }

    return judgment
