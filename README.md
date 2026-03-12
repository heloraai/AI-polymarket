# ZhihuMarket — AI 预测市场 × 知乎群体智慧

> 知乎 Agent2Agent 黑客松项目：用知乎热点自动生成预测市场，让 AI Agent 基于舆情数据交易

## 概念

将知乎的**群体智慧**转化为 AI 驱动的**预测市场**：

1. 从知乎热榜自动发现值得预测的事件
2. 分析知乎回答中的多方观点和舆论走向
3. AI Agent 基于分析结果进行概率推理和模拟交易
4. 事件到期后自动判定结果并结算

## 架构

```
┌────────────────────────────────────────────────────────┐
│                   ZhihuMarket A2A                      │
├─────────────┬─────────────┬────────────┬───────────────┤
│  Agent 1    │  Agent 2    │  Agent 3   │  Agent 4      │
│  热点猎手    │  舆情分析    │  预测交易   │  结果裁判      │
│             │             │            │               │
│  监控知乎    │  NLP分析     │  概率推理   │  事件到期后    │
│  热榜&话题   │  多方观点    │  模拟下单   │  判定结果      │
└─────────────┴─────────────┴────────────┴───────────────┘
        ↕ A2A Protocol ↕          ↕ A2A Protocol ↕
```

## 四个 Agent

### 1. 热点猎手 (Topic Hunter)
- 监控知乎热榜变化
- 从热门问题中提取可量化的预测命题
- 自动生成预测市场（如"XX电影票房是否过50亿"）

### 2. 舆情分析师 (Sentiment Analyst)
- 抓取某个问题下的高赞回答
- NLP 分析正反方论据质量、专业度
- 追踪答主的历史预测准确率（知乎大V预测力排行榜）
- 输出情绪指数和置信度

### 3. 预测交易员 (Prediction Trader)
- 综合舆情数据 + 外部信息源
- LLM 推理计算概率
- 执行模拟交易（虚拟积分系统）
- Kelly criterion 仓位管理

### 4. 结果裁判 (Outcome Judge)
- 追踪事件进展
- 到期后自动判定胜负
- 计算收益排行榜
- 回溯验证各 Agent 的预测准确率

## 知乎数据利用

| 数据源 | 用途 |
|--------|------|
| 热榜 | 自动发现值得预测的话题 |
| 问题详情 | 提取可量化的预测命题 |
| 回答内容 | 多角度舆情分析 |
| 投票数 | 衡量群体共识度 |
| 话题结构 | 分类预测市场（科技/政治/娱乐） |
| 用户画像 | 分析答主专业度和历史准确率 |
| 评论 | 捕捉反驳和补充论据 |
| 时间线 | 舆论转向检测（情绪拐点） |

## 亮点功能

- **知乎大V预测力排行榜**：回溯分析高赞答案的预测是否准确
- **舆论拐点预警**：知乎主流观点突然反转时触发信号
- **群体智慧 vs AI**：对比知乎群体观点和 AI 模型预测准确率
- **A2A 对战模式**：不同策略的 Agent 互相交易，优胜劣汰

## 技术栈

- **Language**: Python 3.11+
- **LLM**: Claude API (via Anthropic SDK)
- **知乎数据**: zhihu-api / 自建爬虫
- **向量数据库**: ChromaDB (存储/检索知乎内容)
- **A2A 协议**: Agent2Agent Protocol
- **Web UI**: Streamlit / Gradio

## 项目结构

```
zhihu-market/
├── agents/
│   ├── topic_hunter.py      # 热点猎手 Agent
│   ├── sentiment_analyst.py # 舆情分析 Agent
│   ├── prediction_trader.py # 预测交易 Agent
│   └── outcome_judge.py     # 结果裁判 Agent
├── zhihu/
│   ├── client.py            # 知乎 API 客户端
│   ├── hotlist.py           # 热榜监控
│   └── parser.py            # 内容解析
├── market/
│   ├── engine.py            # 预测市场引擎
│   ├── models.py            # 数据模型
│   └── settlement.py        # 结算系统
├── analysis/
│   ├── sentiment.py         # 情感分析
│   ├── credibility.py       # 可信度评估
│   └── trend.py             # 趋势检测
├── app.py                   # Web UI
├── config.py                # 配置
└── requirements.txt
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 API keys
python app.py
```

## 参考项目

- [Polymarket/agents](https://github.com/Polymarket/agents) — 官方 AI Agent 框架
- [Fully-Autonomous-Polymarket-AI-Trading-Bot](https://github.com/dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot) — 多模型集成交易机器人
- [polymarket-ai-market-suggestor](https://github.com/lorine93s/polymarket-ai-market-suggestor) — AI 市场建议器
- [lzjun567/zhihu-api](https://github.com/lzjun567/zhihu-api) — 知乎 Python API
- [wangzhe3224/zhihu-hotlist](https://github.com/wangzhe3224/zhihu-hotlist) — 知乎热榜

## License

MIT
