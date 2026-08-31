# sp500-quota-watch

标普500场外基金申购额度自动监控与推送工具。

## 功能特性

- 自动监控多只标普500场外基金的申购额度
- 额度变动时自动推送通知（Server酱/Bark）
- 工作日固定时间检测，收盘后推送当日汇总
- 零第三方依赖，Python 3.7+ 直接运行
- 适合 GitHub Actions 免费托管

## 快速开始

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
- 工作日 9:20、11:20、13:20 自动检测变动
- 工作日 15:10 收盘后推送当日汇总

## 本地使用

### 查看当前额度表（不推送）
```bash
python3 sp500_quota_watch.py --print
```

### 建立基线快照（首次运行）
```bash
python3 sp500_quota_watch.py --init
```

### 测试推送
```bash
python3 sp500_quota_watch.py --force-notify
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

## 注意事项

1. 首次运行会建立基线快照，不会推送
2. 快照保存在 `data/state.json`，会自动提交到仓库
3. 如果抓取失败，会沿用旧值避免误报
4. 工作日 15:10 会固定推送当日汇总，确保长期不提醒也不会漏
