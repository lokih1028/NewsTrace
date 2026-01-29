# 📊 NewsTrace 零成本部署指南

> 🎯 使用 GitHub Actions 实现完全免费的 7×24h 新闻审计系统

## ✨ 功能概述

- **每日自动分析** - 工作日 18:00 自动执行
- **Gemini 免费 LLM** - 无需付费 API
- **多渠道推送** - 企业微信/飞书/Telegram/邮件
- **零服务器成本** - GitHub Actions 托管

## 🚀 快速开始

### 1. Fork 仓库

点击右上角 `Fork` 按钮

### 2. 配置 Secrets

进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

#### LLM 配置 (二选一)

| Secret | 说明 | 必填 |
|--------|------|:----:|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) 免费获取 | ✅ 推荐 |
| `OPENAI_API_KEY` | OpenAI API Key | 可选 |
| `OPENAI_BASE_URL` | 兼容 API 地址 (如 DeepSeek) | 可选 |
| `OPENAI_MODEL` | 模型名称 | 可选 |

#### 通知渠道 (至少配一个)

| Secret | 说明 |
|--------|------|
| `WECHAT_WEBHOOK_URL` | 企业微信机器人 Webhook |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID |
| `PUSHPLUS_TOKEN` | [PushPlus](https://www.pushplus.plus) Token |
| `EMAIL_SENDER` | 发件人邮箱 |
| `EMAIL_PASSWORD` | 邮箱授权码 |

#### 其他配置

| Secret | 说明 | 默认值 |
|--------|------|--------|
| `WATCH_KEYWORDS` | 关注关键词 (逗号分隔) | 黄金,茅台,英伟达,央行,GDP |
| `TUSHARE_TOKEN` | Tushare Pro Token | 可选 |

### 3. 启用 Actions

进入 `Actions` 标签 → 点击 `I understand my workflows, go ahead and enable them`

### 4. 手动测试

`Actions` → `NewsTrace 每日分析` → `Run workflow` → 选择模式 → `Run workflow`

## 📅 定时执行

默认每个工作日 **18:00 (北京时间)** 自动执行

修改时间: 编辑 `.github/workflows/daily_analysis.yml` 中的 `cron` 表达式

```yaml
schedule:
  - cron: '0 10 * * 1-5'  # UTC 10:00 = 北京 18:00
```

## 💰 成本对比

| 项目 | 传统方案 | 零成本方案 |
|------|---------|-----------|
| 服务器 | $5-20/月 | $0 |
| LLM API | $50-200/月 | $0 (Gemini 免费) |
| 数据库 | $10-30/月 | $0 (SQLite) |
| **总计** | **$65-250/月** | **$0** |

## ⚠️ 限制说明

1. **非实时** - 每日定时执行,无法盘中监控
2. **GitHub Actions 限制** - 免费版每月 2000 分钟
3. **Gemini 限制** - 60 QPM,个人使用足够

## 📁 数据存储

- 数据库: `data/newstrace.db` (SQLite)
- 报告: `data/reports/daily_YYYYMMDD.md`
- 摘要: `data/summary.json`

运行后数据会作为 Artifact 保存 30 天

## 🔧 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export GEMINI_API_KEY=your_key
export PUSHPLUS_TOKEN=your_token

# 运行
python run_actions.py
```

---

**如有问题,请提交 Issue!**
