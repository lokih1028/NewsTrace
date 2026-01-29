# NewsTrace 2.0 更新日志

## [2.0.0] - 2026-01-26

### 🎯 重大变更

#### 战略重构: 从"纠错"到"交易"

- 从"纠正翻译错误"转向"利用市场预期差"
- 实现基于反身性(Reflexivity)的自适应权重系统

### ✨ 新增功能

#### 1. 自适应权重引擎 (`src/strategy_updater.py`)

- **MarketFeedback**: 连接语义审计与市场回溯的数据结构
- **DynamicConfig**: 系统的"长期记忆",存储进化权重
- **StrategyUpdater**:
  - `calculate_reward()`: 计算 AI 判断与市场走势的偏差
  - `evolve()`: 基于贝叶斯推断调整权重
  - `generate_new_prompt_instruction()`: 将数学参数转化为自然语言指令

#### 2. 多时间点市场追踪 (`src/market_tracker.py`)

- **T+1 追踪**: 隔日价格快照
- **T+3 追踪**: 短线结案,用于权重进化
- **T+7 追踪**: 价值结案,计算最终 PnL
- **PnL 计算**: 自动计算盈亏百分比
- **最大回撤**: 追踪期间的最大回撤指标

#### 3. 动态 Prompt 系统

- 审计引擎根据最新权重配置动态生成 Prompt 指令
- 在牛市/熊市中自动调整评分标准
- 支持特征检测输出 (`detected_features`)

#### 4. 自动化工作流

- **daily_price_update.py**: 每日 15:30 更新价格快照
- **daily_evolution.py**: 每日 16:00 执行权重进化

### 🗄️ 数据库变更

#### 新增表

- **market_tracking**: T+0 到 T+7 市场表现追踪表
  - 支持多时间点价格快照 (T0/T1/T3/T7)
  - 存储 PnL 和最大回撤指标
  - 记录市场状态 (Bull/Bear/Neutral)

- **strategy_evolution_log**: AI 权重进化历史日志
  - 记录特征权重变化
  - 存储触发原因和样本数量

#### 扩展表

- **news**:
  - 新增 `ai_audit_result` JSONB 字段
  - 新增 `related_tickers` 数组字段

#### 新增视图

- **v_latest_weights**: 每个特征的最新权重配置
- **v_tracking_performance**: 追踪任务绩效汇总

#### 新增函数

- **get_feature_weight()**: 获取指定特征的当前权重
- **calculate_pnl()**: 计算价格变化百分比

### 🔧 改进

#### 审计引擎 (`src/audit_engine.py`)

- 支持从数据库加载动态权重
- 动态构建 Prompt,注入市场反馈指令
- 输出包含 `detected_features` 字段

#### 测试覆盖

- 新增 `test_strategy_updater.py`: 策略更新器单元测试
- 新增 `test_market_tracker.py`: 市场追踪器单元测试

### 📚 文档

- **UPGRADE_GUIDE.md**: 详细的升级指南
- **cron_jobs/README.md**: Cron Jobs 使用说明
- **implementation_plan.md**: 实施计划文档
- **task.md**: 任务清单

### 🔄 迁移指南

参见 [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md)

### ⚠️ 破坏性变更

- 数据库 Schema 变更,需要运行迁移脚本
- `AuditEngine` 构造函数新增 `db` 参数(可选)
- 推荐使用新的 `MarketTracker` 替代旧的 `TrackingScheduler`

### 🐛 修复

- 修复了固定 T+7 回测的局限性
- 改进了权重配置的持久化机制

### 📊 性能

- 使用 JSONB 索引提升审计结果查询性能
- TimescaleDB 优化时序数据存储

---

## [1.0.0] - 2026-01-25

### 初始版本

- AI 语义审计
- T+7 固定追踪
- 信源公信力评级
- Dashboard 可视化
