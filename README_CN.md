# NewsTrace - 金融新闻智能审计与回溯系统 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

NewsTrace 是一个集“语义审计”与“表现追踪”于一体的闭环式金融情报系统。它能将不可量化的新闻文字转化为可审计、可回测的科学资产，帮助投资者剥离财经媒体的“滤镜”，量化每一份情报的真实含金量。

---

## 📖 快速导航

- [🐣 小白保姆级上手指南](./NOVICE_GUIDE_CN.md) - **如果你是新手，请先看这里！**
- [🚀 快速开始（Docker 部署）](#-快速开始docker-部署)
- [🛠️ 本地开发环境配置](#-本地开发环境配置)
- [✨ 核心功能](#-核心功能)
- [📁 项目结构](#-项目结构)

---

## ✨ 核心功能

### AI 审计引擎
- 🔍 **多角度语义审计**：识别新闻中的情绪化修饰、逻辑漏洞和翻译失真
- 🎲 **输出多样性优化**：Temperature 随机波动 + 时间盐缓存,避免雷同分析
- 📊 **实时市场上下文**：对接 Tushare API,基于大盘实时行情生成市场环境描述
- 🎯 **随机化审计侧重**：每次分析随机选择不同的关注点,增加分析深度

### 智能关键词生成
- 🤖 **一键生成关键词**：输入股票代码,自动生成相关新闻关键词
- 🧠 **AI 增强生成**：可选使用 GPT 生成产业链上下游关键词
- 📋 **批量配置**：支持多只股票一次性生成完整监控配置

### 追踪与评级
- ⏱️ **时间胶囊追踪**：T+7 自动化回测机制，验证新闻对市场的实际影响
- 📊 **信源公信力评级**：量化媒体可信度，生成红黑榜
- 📈 **可视化仪表盘**：基于 Streamlit 的实时监控和数据分析

---

## 🚀 快速开始（Docker 部署）

这是推荐的部署方式，可以避免复杂的依赖安装问题。

### 1. 环境准备

确保你的电脑已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并填入你的 API Key：

```bash
cp .env.example .env
# 编辑 .env 文件
# OPENAI_API_KEY=sk-xxx
# TUSHARE_TOKEN=xxx
```

### 3. 启动服务

```bash
docker-compose up -d
```

### 4. 访问系统

- **可视化仪表盘**: [http://localhost:8501](http://localhost:8501)
- **API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🎯 智能关键词生成器

**无需手动配置关键词！** 输入股票代码,自动生成相关新闻监控关键词。

### 使用方法

```bash
# 1. 配置 Tushare Token (免费注册: https://tushare.pro/register)
$env:TUSHARE_TOKEN="你的token"

# 2. 为茅台、五粮液生成关键词
python scripts/generate_keywords.py 600519.SH 000858.SZ

# 3. 查看生成结果
cat config/auto_keywords.json
```

### 生成示例

```json
{
  "watch_keywords": ["贵州茅台", "茅台", "白酒", "消费税", "五粮液", ...],
  "stock_mapping": {
    "600519.SH": ["贵州茅台", "茅台", "白酒", "消费税"],
    "000858.SZ": ["五粮液", "白酒", "消费税"]
  }
}
```

### 应用到主程序

```python
import json

with open('config/auto_keywords.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    WATCH_KEYWORDS = config['watch_keywords']
```

---

## 🛠️ 本地开发环境配置

如果你需要修改代码或进行二次开发：

### 1. 安装依赖

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

### 2. 初始化数据库

确保已安装 PostgreSQL，并运行：

```bash
psql -U postgres -f migrations/001_init.sql
```

### 3. 启动各组件

你需要打开四个终端分别运行：

- **API**: `uvicorn api.main:app --reload`
- **Worker**: `celery -A src.tasks worker --loglevel=info`
- **Beat**: `celery -A src.tasks beat --loglevel=info`
- **Dashboard**: `streamlit run dashboard/app.py`

---

## 📁 项目结构

```text
NewsTrace/
├── src/
│   ├── audit_engine.py         # AI审计引擎(支持实时行情上下文)
│   ├── keyword_generator.py    # 智能关键词生成器
│   ├── market_tracker.py       # 市场追踪器
│   └── ...
├── scripts/
│   └── generate_keywords.py    # 关键词生成命令行工具
├── api/                        # FastAPI 接口服务
├── dashboard/                  # Streamlit 仪表盘
├── config/                     # 配置文件
├── migrations/                 # 数据库脚本
└── .env.example                # 环境变量模板
```

---

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request！让我们一起构建更透明的金融情报环境。

**让“金融直觉”让位于“科学证据”** 🚀
