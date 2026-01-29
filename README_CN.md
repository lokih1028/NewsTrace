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

- 🔍 **AI 语义审计**：识别新闻中的情绪化修饰、逻辑漏洞和翻译失真。
- ⏱️ **时间胶囊追踪**：T+7 自动化回测机制，验证新闻对市场的实际影响。
- 📊 **信源公信力评级**：量化媒体可信度，生成红黑榜。
- 🤖 **全流程自动化**：从新闻接入到定时结算的闭环系统。
- 📈 **可视化仪表盘**：基于 Streamlit 的实时监控和数据分析。

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
├── src/                # 核心逻辑（审计引擎、追踪器、采集器）
├── api/                # FastAPI 接口服务
├── dashboard/          # Streamlit 仪表盘界面
├── config/             # 配置文件
├── migrations/         # 数据库初始化脚本
├── docker-compose.yml  # Docker 编排配置
└── .env.example        # 环境变量模板
```

---

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request！让我们一起构建更透明的金融情报环境。

**让“金融直觉”让位于“科学证据”** 🚀
