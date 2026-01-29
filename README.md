# NewsTrace - AI 新闻审计系统

> 🤖 基于 AI 的金融新闻智能审计系统,零成本部署,每日自动分析

[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ 核心功能

- 🔍 **AI 语义审计** - 识别新闻逻辑漏洞和情绪化偏见
- 📊 **信源评级** - 基于历史表现的媒体公信力排行
- 🎯 **知识图谱** - 自动提取实体并建立关联
- 📈 **情感分析** - 正/负面/不确定性词汇识别
- 📱 **多渠道推送** - 企业微信/飞书/Telegram/邮件

---

## 🚀 快速开始 (10分钟)

### 零成本部署 (推荐)

**无需服务器,完全免费!**

详细步骤请查看: [📖 零成本部署指南](ZERO_COST_DEPLOYMENT.md)

**简要步骤:**

1. Fork 本仓库
2. 获取 [Gemini API Key](https://aistudio.google.com/) (免费)
3. 配置 GitHub Secrets
4. 启用 Actions

---

## 💰 成本对比

| 方案 | 月成本 | 适用场景 |
|------|--------|---------|
| **零成本方案** | $0 | 个人使用,每日定时分析 |
| 传统部署 | $200+ | 专业投研,7×24h 实时监控 |

---

## 📁 项目结构

```
NewsTrace/
├── .github/workflows/    # GitHub Actions 工作流
├── src/                  # 核心代码
│   ├── llm_provider.py      # LLM 提供商 (OpenAI/Gemini/Ollama)
│   ├── audit_engine.py      # AI 审计引擎
│   ├── knowledge_graph.py   # 知识图谱
│   ├── enhanced_analyzer.py # 增强分析器
│   └── multi_channel_notifier.py  # 多渠道通知
├── run_actions.py        # GitHub Actions 入口
├── requirements.txt      # 核心依赖
└── ZERO_COST_DEPLOYMENT.md  # 部署指南
```

---

## 🛠️ 技术栈

- **AI/LLM**: OpenAI GPT-4o / Google Gemini / Ollama
- **数据源**: AkShare (免费) / Tushare
- **数据库**: SQLite / PostgreSQL
- **推送**: 企业微信/飞书/Telegram/PushPlus

---

## 📖 文档

- [零成本部署指南](ZERO_COST_DEPLOYMENT.md) - 10分钟完成部署
- [技术研究报告](TECHNICAL_RESEARCH_REPORT.md) - 系统设计与架构
- [更新日志](CHANGELOG.md) - 版本历史

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

---

## 📄 License

[MIT License](LICENSE) © 2026

---

## ⚠️ 免责声明

本项目仅供学习和研究使用,不构成任何投资建议。股市有风险,投资需谨慎。
