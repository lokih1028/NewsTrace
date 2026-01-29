# 📊 NewsTrace 零成本部署指南 (小白版)

> 🎯 10分钟完成部署,无需服务器,完全免费!

---

## 📋 准备工作 (5分钟)

### 1️⃣ 注册 GitHub 账号

**如果已有账号,跳过此步骤**

1. 访问 <https://github.com/signup>
2. 输入邮箱 → 创建密码 → 选择用户名
3. 验证邮箱 (查收验证邮件)

---

### 2️⃣ 获取免费 Gemini API Key

**这是 AI 分析的核心,完全免费!**

1. 访问 <https://aistudio.google.com/>
2. 点击右上角 **"Sign in"** (用 Google 账号登录)
3. 点击左侧 **"Get API key"**
4. 点击 **"Create API key"** → 选择项目 (或新建)
5. **复制** 生成的 API Key (格式: `AIza...`)

📌 **保存好这个 Key,稍后要用!**

---

### 3️⃣ 获取推送通知 Token (可选)

**选择一个你常用的推送方式:**

#### 方式A: PushPlus (推荐,最简单)

1. 访问 <https://www.pushplus.plus>
2. 微信扫码登录
3. 复制 **"一对一推送 Token"**

#### 方式B: 企业微信机器人

1. 打开企业微信群 → 右键 → 添加群机器人
2. 复制 Webhook URL

#### 方式C: 飞书机器人

1. 打开飞书群 → 设置 → 群机器人 → 添加机器人
2. 复制 Webhook URL

---

## 🚀 开始部署 (5分钟)

### Step 1: 创建 GitHub 仓库

1. 访问 <https://github.com/new>
2. 填写信息:
   - **Repository name**: `NewsTrace` (必填)
   - **Description**: `AI新闻审计系统` (可选)
   - **Private**: ✅ 勾选 (推荐私有)
   - **其他选项**: 全部不勾选
3. 点击 **"Create repository"**

---

### Step 2: 上传代码

#### 方法1: 使用命令行 (推荐)

1. 在 GitHub 仓库页面,点击右上角绿色按钮 **"Code"**
2. 复制 HTTPS 地址 (格式: `https://github.com/你的用户名/NewsTrace.git`)
3. 打开本地 `NewsTrace` 文件夹
4. 右键空白处 → 选择 **"在终端中打开"** (或 **"Open in Windows Terminal"**)
5. 依次执行以下命令:

```powershell
# 添加远程仓库 (替换成你复制的地址)
git remote add origin https://github.com/你的用户名/NewsTrace.git

# 推送代码
git branch -M main
git push -u origin main
```

**如果提示输入用户名和密码:**

- 用户名: 你的 GitHub 用户名
- 密码: 需要使用 **Personal Access Token** (不是登录密码!)

**获取 Token:**

1. GitHub 右上角头像 → Settings
2. 左侧最底部 → Developer settings
3. Personal access tokens → Tokens (classic)
4. Generate new token → 勾选 `repo` → Generate token
5. **复制生成的 Token** (只显示一次!)

---

#### 方法2: 使用 GitHub Desktop (更简单)

1. 下载安装 [GitHub Desktop](https://desktop.github.com/)
2. 打开软件 → File → Add local repository
3. 选择 `NewsTrace` 文件夹
4. 点击 **"Publish repository"**
5. 取消勾选 "Keep this code private" (如果想公开)
6. 点击 **"Publish repository"**

---

### Step 3: 配置 Secrets (关键步骤!)

**在 GitHub 仓库页面:**

1. 点击 **"Settings"** (设置)
2. 左侧菜单 → **"Secrets and variables"** → **"Actions"**
3. 点击 **"New repository secret"**

**添加以下 Secrets (至少添加前2个):**

| Name              | Value         | 说明                          |
| ----------------- | ------------- | ----------------------------- |
| `GEMINI_API_KEY`  | `AIza...`     | 第2步获取的 Gemini Key ✅必填 |
| `PUSHPLUS_TOKEN`  | `xxx`         | 第3步获取的推送 Token ✅推荐  |
| `WATCH_KEYWORDS`  | `黄金,茅台,英伟达` | 关注的关键词 (可选)           |

**添加方法:**

- Name: 输入上表中的名称 (如 `GEMINI_API_KEY`)
- Secret: 粘贴对应的值
- 点击 **"Add secret"**
- 重复操作添加其他 Secrets

---

### Step 4: 启用 GitHub Actions

1. 点击仓库顶部 **"Actions"** 标签
2. 看到提示 "Workflows aren't being run..."
3. 点击绿色按钮 **"I understand my workflows, go ahead and enable them"**

---

### Step 5: 测试运行

1. 在 Actions 页面,点击左侧 **"📊 NewsTrace 每日分析"**
2. 右侧点击 **"Run workflow"** 下拉框
3. 选择 **"full"** 模式
4. 点击绿色按钮 **"Run workflow"**
5. 等待 30 秒,刷新页面
6. 点击出现的运行记录,查看执行日志

**成功标志:**

- ✅ 所有步骤显示绿色对勾
- ✅ 收到推送通知 (如果配置了)

---

## 📅 自动运行设置

**默认配置:** 每个工作日 18:00 (北京时间) 自动运行

**修改运行时间:**

1. 进入仓库 → 点击 `.github/workflows/daily_analysis.yml`
2. 点击右上角 ✏️ 编辑
3. 找到第 8 行 `cron: '0 10 * * 1-5'`
4. 修改时间 (参考下表)
5. 点击 **"Commit changes"**

**时间对照表:**

| 北京时间    | Cron 表达式     |
| ----------- | --------------- |
| 每天 9:00   | `0 1 * * *`     |
| 每天 12:00  | `0 4 * * *`     |
| 每天 18:00  | `0 10 * * *`    |
| 每天 21:00  | `0 13 * * *`    |

---

## ❓ 常见问题

### Q1: Actions 运行失败怎么办?

**A:** 点击失败的运行记录 → 查看红色 ❌ 的步骤 → 检查错误信息

- 常见原因: `GEMINI_API_KEY` 配置错误
- 解决方法: 重新检查 Secrets 配置

### Q2: 没有收到推送通知?

**A:** 检查:

1. `PUSHPLUS_TOKEN` 是否正确配置
2. PushPlus 是否已关注公众号
3. 查看 Actions 日志中的推送部分

### Q3: 如何查看分析结果?

**A:**

- 方式1: 查看推送通知
- 方式2: Actions → 运行记录 → Artifacts → 下载 `newstrace-data-xxx`

### Q4: 每月免费额度够用吗?

**A:** 完全够用!

- GitHub Actions: 2000分钟/月 (每次运行约5分钟)
- Gemini API: 60次/分钟 (每日分析约50条新闻)

---

## 💡 进阶配置

### 添加更多推送渠道

**企业微信:**

```text
Name: WECHAT_WEBHOOK_URL
Secret: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

**飞书:**

```text
Name: FEISHU_WEBHOOK_URL  
Secret: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

**Telegram:**

```text
Name: TELEGRAM_BOT_TOKEN
Secret: 123456:ABC-DEF...

Name: TELEGRAM_CHAT_ID
Secret: 123456789
```

---

## 🎉 完成

现在你的 NewsTrace 已经部署成功,每天会自动分析新闻并推送给你!

**有问题?** 提交 Issue: <https://github.com/你的用户名/NewsTrace/issues>
