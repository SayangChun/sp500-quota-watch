# sp500-quota-watch

标普500场外基金申购额度自动监控与推送工具。

## 功能特性

- 自动监控多只标普500场外基金的申购额度
- 额度变动时自动推送通知（Server酱/Bark）
- 工作日固定时间检测，有变动时立即推送
- 零第三方依赖，Python 3.7+ 直接运行
- 适合 GitHub Actions 免费托管

## 其他用户使用教程（Fork 方式）

如果你想使用这个项目监控自己的标普500基金额度，可以通过 Fork 的方式：

### 1. Fork 仓库

1. 访问项目仓库：https://github.com/你的用户名/sp500-quota-watch
2. 点击右上角的 **Fork** 按钮
3. 选择你的 GitHub 账号，等待 Fork 完成

### 2. 配置 Secrets

1. 进入你 Fork 后的仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加推送渠道密钥：
   - `SCT_KEY`：Server酱密钥（sctp 开头）
   - `BARK_KEY`：Bark 密钥

### 3. 启用 GitHub Actions

1. 在你的仓库中，点击 **Actions** 选项卡
2. 如果看到 " workflows aren't being run on this forked repository" 的提示，点击 **I understand my workflows, go ahead and enable them**
3. GitHub Actions 会自动启用

### 4. 自定义监控的基金（可选）

如果你只想监控特定的基金，可以编辑 `funds.json` 文件，只保留你关心的基金：

```json
{
  "funds": [
    { "code": "017641", "name": "摩根标普500指数(QDII) 人民币A", "firm": "摩根", "currency": "CNY", "note": "费率最低 0.65%/年" },
    { "code": "050025", "name": "博时标普500ETF联接 A", "firm": "博时", "currency": "CNY", "note": "规模最大" }
  ]
}
```

### 5. 等待自动运行

GitHub Actions 会在工作日自动运行：
- 周一到周四 15:30（交易日前一天下午）提前查询
- 周一到周五交易时段（9:20-15:00）每20分钟密集检测
- 有变动时立即推送

### 6. 手动测试

你也可以手动触发工作流测试：
1. 进入 **Actions** 选项卡
2. 选择 **标普500场外额度监控** 工作流
3. 点击 **Run workflow** 按钮

## 快速开始（原作者/直接使用）

### 1. 配置推送渠道

项目支持两种推送方式：

#### Server酱（推荐）
通过微信推送，获取密钥：https://sct.ftqq.com/

#### Bark
iOS 推送，获取密钥：https://github.com/Finb/Bark

### 2. 在 GitHub 仓库中添加 Secrets

1. 进入你的 GitHub 仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下密钥（二选一或都添加）：
   - `SCT_KEY`：Server酱密钥（sctp 开头）
   - `BARK_KEY`：Bark 密钥

### 3. 启用 GitHub Actions

确保 GitHub Actions 已启用。工作流会在：
- 周一到周四 15:30（交易日前一天下午）提前查询
- 周一到周五交易时段（9:20-15:00）每20分钟密集检测
- 有变动时立即推送

## 本地使用

### 查看当前额度表（不推送）
```bash
python3 sp500_quota_watch.py --print
```

### 建立基线快照（首次运行）
```bash
python3 sp500_quota_watch.py --init
```

### 正常运行（检测变动并推送）
```bash
python3 sp500_quota_watch.py
```

## 推送效果示例

当检测到额度变动时，你会收到类似这样的推送：

```
🔔 标普500额度变动！08-31 15:10

### 🟢 摩根标普500指数(QDII) 人民币A `017641`
- 变化：限大额 10元/日 → 开放申购（不限额）
```

## 监控的基金

详见 `funds.json`，包含摩根、博时、易方达、天弘、华夏、国泰等基金公司的标普500场外基金。

## 实时额度

<!-- QUOTA_START -->
> 最后更新：2026-09-04 16:29:53

| 代码 | 份额 | 状态 | 赎回 |
|---|---|---|---|
| 017641 | 摩根标普500指数(QDII) 人民币A | ❌ 暂停申购 | 暂停赎回 |
| 019305 | 摩根标普500指数(QDII) 人民币C | ❌ 暂停申购 | 暂停赎回 |
| 050025 | 博时标普500ETF联接 A | ❌ 暂停申购 | 暂停赎回 |
| 006075 | 博时标普500ETF联接 C | ❌ 暂停申购 | 暂停赎回 |
| 018738 | 博时标普500ETF联接 E(人民币) | ❌ 暂停申购 | 开放赎回 |
| 161125 | 易方达标普500指数(QDII-LOF) 人民币A | ❌ 暂停申购 | 暂停赎回 |
| 012860 | 易方达标普500指数(QDII-LOF) 人民币C | ❌ 暂停申购 | 暂停赎回 |
| 007721 | 天弘标普500发起(QDII-FOF) A | ❌ 暂停申购 | 暂停赎回 |
| 007722 | 天弘标普500发起(QDII-FOF) C | ❌ 暂停申购 | 暂停赎回 |
| 022523 | 天弘标普500发起(QDII-FOF) D | 🟡 限大额（额度未公示） | 开放赎回 |
| 018064 | 华夏标普500ETF发起式联接(QDII) A人民币 | ❌ 暂停申购 | 暂停赎回 |
| 018065 | 华夏标普500ETF发起式联接(QDII) C | ❌ 暂停申购 | 暂停赎回 |
| 017028 | 国泰标普500ETF发起联接(QDII) A人民币 | ❌ 暂停申购 | 暂停赎回 |
| 017030 | 国泰标普500ETF发起联接(QDII) C人民币 | ❌ 暂停申购 | 暂停赎回 |

> 可买 1 只 / 共 14 只，人民币份额合计约 0 元/日
<!-- QUOTA_END -->

## 注意事项

1. 首次运行会建立基线快照，不会推送
2. 快照保存在 `data/state.json`，会自动提交到仓库
3. 如果抓取失败，会沿用旧值避免误报
4. 只有当额度变动时才会推送通知
5. README.md中的"实时额度"表格会随每次检测自动更新，用户可直接在GitHub仓库首页查看最新额度
