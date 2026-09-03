#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标普500 场外基金申购额度监控器
--------------------------------
- 只盯【标普500指数·市值加权】的场外基金（清单见 funds.json，等权重/标普100 已排除）
- 数据源：天天基金公开页面（fund.eastmoney.com/{code}.html）的「交易状态 + 单日累计购买上限」
- 与上一次快照对比，额度一有变动立即推送（Server酱 / Bark）
- 零第三方依赖，Python 3.7+ 直接跑，适合 GitHub Actions 免费托管

用法:
    python3 sp500_quota_watch.py              # 正常运行（对比并推送）
    python3 sp500_quota_watch.py --init       # 只建立基线快照，不推送
    python3 sp500_quota_watch.py --print      # 只打印当前额度表，不写快照不推送
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# 设置标准输出编码为UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUNDS_FILE = os.path.join(BASE_DIR, "funds.json")
README_FILE = os.path.join(BASE_DIR, "README.md")
STATE_FILE = os.path.join(BASE_DIR, "data", "state.json")
LOG_FILE = os.path.join(BASE_DIR, "data", "history.log")
CST = timezone(timedelta(hours=8))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------- 工具函数
def now_cst():
    return datetime.now(CST)


def log(msg):
    line = "[%s] %s" % (now_cst().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def http_get(url, timeout=25, retries=3):
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception as e:
            last_err = e
            time.sleep(2 + i * 2)
    raise last_err


# ---------------------------------------------------------------- 抓取与解析
def parse_amount(text):
    """把 '10.00元' / '1.00万元' / '5美元' 统一换算成数字（元 或 美元）。"""
    if not text:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(万元|元|美元)", text)
    if not m:
        return None
    val = float(m.group(1).replace(",", ""))
    unit = m.group(2)
    if unit == "万元":
        val *= 10000
    return val


def fetch_one(fund):
    """返回 dict: status / limit_raw / limit_num / redeem / raw_name"""
    code = fund["code"]
    html = http_get("https://fund.eastmoney.com/%s.html" % code)

    title = re.search(r"<title>(.*?)</title>", html, re.S)
    raw_name = title.group(1).split("基金净值")[0].strip() if title else ""

    # 交易状态块：交易状态：</span><span class="staticCell">限大额 (<span>单日累计购买上限10.00元</span>)</span>
    blk = re.search(
        r'buyWayStatic.*?交易状态：</span><span class="staticCell">(.*?)</span>',
        html,
        re.S,
    )
    stat_raw = blk.group(1).strip() if blk else ""
    stat_raw = re.sub(r"<[^>]+>", "", stat_raw).strip()

    lim = re.search(r"单日累计购买上限\s*([\d,\.]+\s*(?:万元|元|美元))", stat_raw)
    lim_raw = lim.group(1).replace(" ", "") if lim else None

    if "暂停申购" in stat_raw:
        status, limit_num = "暂停申购", 0.0
    elif "限大额" in stat_raw:
        status = "限大额"
        limit_num = parse_amount(lim_raw) if lim_raw else None
    elif "开放申购" in stat_raw:
        status, limit_num = "开放申购", None
    elif "封闭期" in stat_raw or "认购期" in stat_raw:
        status, limit_num = stat_raw, 0.0
    else:
        status, limit_num = stat_raw or "未知", None

    redeem = "开放赎回" if "开放赎回" in html else ("暂停赎回" if "暂停赎回" in html else "-")

    return {
        "code": code,
        "name": fund.get("name") or raw_name,
        "firm": fund.get("firm", ""),
        "currency": fund.get("currency", "CNY"),
        "note": fund.get("note", ""),
        "status": status,
        "limit_raw": lim_raw,
        "limit_num": limit_num,
        "redeem": redeem,
        "status_raw": stat_raw,
    }


def fetch_all(funds, workers=4):
    """并发抓取；失败的条目不打进快照，避免误报。"""
    from concurrent.futures import ThreadPoolExecutor

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_one, f): f for f in funds}
        for fu, f in futures.items():
            try:
                results.append(fu.result())
            except Exception as e:
                failures.append((f["code"], f.get("name", ""), str(e)[:60]))
                log("抓取失败 %s %s : %s" % (f["code"], f.get("name", ""), str(e)[:60]))

    order = {f["code"]: i for i, f in enumerate(funds)}
    results.sort(key=lambda r: order.get(r["code"], 999))
    return results, failures


# ---------------------------------------------------------------- 快照对比
def sig(r):
    """用于判断『是否发生变化』的指纹"""
    return "%s|%s" % (r["status"], r["limit_num"])


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_state(results):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    data = {
        "updated_at": now_cst().strftime("%Y-%m-%d %H:%M:%S"),
        "funds": {r["code"]: {"status": r["status"], "limit_num": r["limit_num"],
                              "limit_raw": r["limit_raw"], "name": r["name"]}
                  for r in results},
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def diff(old, new_results):
    """返回变化列表 [(基金, 旧状态, 旧额度, 新状态, 新额度)]"""
    changes = []
    if not old:
        return changes
    old_map = old.get("funds", {})
    for r in new_results:
        o = old_map.get(r["code"])
        if o is None:
            continue  # 新增监控标的，不打扰
        if "%s|%s" % (o.get("status"), o.get("limit_num")) != sig(r):
            changes.append((r, o.get("status"), o.get("limit_num"), r["status"], r["limit_num"]))
    return changes


# ---------------------------------------------------------------- 展示
def fmt_limit(r):
    if r["status"] == "暂停申购":
        return "❌ 暂停申购"
    if r["status"] == "开放申购":
        return "🟢 开放申购（不限额）"
    if r["limit_num"] is None:
        return "🟡 %s（额度未公示）" % r["status"]
    unit = "美元" if r["currency"] == "USD" else "元"
    return "🟡 %s / 日" % ("%g%s" % (r["limit_num"], unit))


def render_table(results):
    lines = ["| 代码 | 份额 | 状态 | 赎回 |", "|---|---|---|---|"]
    for r in results:
        lines.append("| %s | %s | %s | %s |" % (r["code"], r["name"], fmt_limit(r), r["redeem"]))
    return "\n".join(lines)


def update_readme(results):
    """更新README.md中的实时额度表格"""
    try:
        with open(README_FILE, encoding="utf-8") as f:
            content = f.read()
        
        # 找到实时额度部分的开始和结束标记
        start_marker = "<!-- QUOTA_START -->"
        end_marker = "<!-- QUOTA_END -->"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            # 如果找不到标记，跳过更新
            return False
        
        # 生成新的表格内容
        table = render_table(results)
        summary = summarize(results)
        updated_at = now_cst().strftime("%Y-%m-%d %H:%M:%S")
        
        new_content = f"""{start_marker}
> 最后更新：{updated_at}

{table}

> {summary}
{end_marker}"""
        
        # 替换内容
        updated_content = content[:start_idx] + new_content + content[end_idx + len(end_marker):]
        
        with open(README_FILE, "w", encoding="utf-8") as f:
            f.write(updated_content)
        
        return True
    except Exception as e:
        log("更新README.md失败: %s" % str(e))
        return False


def summarize(results):
    buyable = [r for r in results if r["status"] in ("限大额", "开放申购")]
    cn = [r for r in buyable if r["currency"] == "CNY"]
    total = sum(r["limit_num"] or 0 for r in cn)
    if any(r["status"] == "开放申购" for r in cn):
        txt = "有份额完全开放申购"
    else:
        txt = "人民币份额合计约 %.0f 元/日" % total
    return "可买 %d 只 / 共 %d 只，%s" % (len(buyable), len(results), txt)


# ---------------------------------------------------------------- 推送
def notify(title, md_body):
    """按环境变量里配置的渠道推送；都返回 True/False。"""
    ok_any = False

    sct = os.environ.get("SCT_KEY", "").strip()  # Server酱 Turbo: sctp开头
    if sct:
        try:
            api = "https://sctapi.ftqq.com/%s.send" % sct
            data = urllib.parse.urlencode({"title": title, "desp": md_body}).encode()
            req = urllib.request.Request(api, data=data, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                log("Server酱 推送成功: %s" % resp.read().decode("utf-8", "ignore")[:80])
            ok_any = True
        except Exception as e:
            log("Server酱 推送失败: %s" % e)

    bark = os.environ.get("BARK_KEY", "").strip()
    if bark:
        try:
            plain = re.sub(r"[|`#*]", "", md_body)
            url = "https://api.day.app/%s/%s/%s" % (
                bark,
                urllib.parse.quote(title),
                urllib.parse.quote(plain[:1500]),
            )
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                log("Bark 推送成功: %s" % resp.read().decode("utf-8", "ignore")[:80])
            ok_any = True
        except Exception as e:
            log("Bark 推送失败: %s" % e)

    if not sct and not bark:
        log("未配置 SCT_KEY / BARK_KEY，跳过推送（仅写本地日志）")
    return ok_any


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="只建立基线快照，不推送")
    ap.add_argument("--print", dest="do_print", action="store_true", help="只打印当前额度表")
    ap.add_argument("--dry-notify", action="store_true", help="只打印将要推送的正文，不真发")
    args = ap.parse_args()

    with open(FUNDS_FILE, encoding="utf-8") as f:
        funds = json.load(f)["funds"]

    log("开始抓取 %d 只标普500场外基金额度..." % len(funds))
    results, failures = fetch_all(funds)

    if not results:
        log("全部抓取失败，保留原快照不动，退出")
        sys.exit(1)

    if args.do_print:
        print("\n" + render_table(results))
        print("\n" + summarize(results))
        if failures:
            print("\n抓取失败: %s" % failures)
        return

    old = load_state()
    changes = diff(old, results)

    # 抓取失败的标的：沿用旧值，避免"先失败后成功"造成假变动
    if old:
        old_map = old.get("funds", {})
        have = {r["code"] for r in results}
        for code, meta in old_map.items():
            if code not in have:
                results.append({"code": code, "name": meta.get("name", code), "firm": "",
                                "currency": "CNY", "note": "", "status": meta.get("status"),
                                "limit_raw": meta.get("limit_raw"),
                                "limit_num": meta.get("limit_num"), "redeem": "-",
                                "status_raw": ""})
        order = {f["code"]: i for i, f in enumerate(funds)}
        results.sort(key=lambda r: order.get(r["code"], 999))

    if args.init or old is None:
        save_state(results)
        update_readme(results)
        log("已建立基线快照（%d 只），本次不推送。下次起有变动会提醒。" % len(results))
        print("\n" + render_table(results))
        print("\n" + summarize(results))
        return

    if changes:
        now = now_cst().strftime("%Y-%m-%d %H:%M")
        title = "🔔 标普500额度变动！%s" % now_cst().strftime("%m-%d %H:%M")
        parts = ["## 🔔 标普500场外额度发生变动", "",
                 "监测时间：%s（共 %d 只，人民币份额口径）" % (now, len(funds)), ""]
        for r, os_, ol, ns, nl in changes:
            old_txt = "暂停申购" if os_ == "暂停申购" else (
                "开放申购" if os_ == "开放申购" else "%s %s" % (os_, ("%g%s" % (ol, "元") if ol is not None else "")))
            new_txt = fmt_limit(r)
            # 变动方向：恢复/上调 = 绿，暂停/下调 = 红橙
            old_v = ol if ol is not None else (0 if os_ == "暂停申购" else None)
            new_v = nl if nl is not None else (0 if ns == "暂停申购" else None)
            if ns == "暂停申购":
                emoji = "🔴"
            elif os_ == "暂停申购" or (old_v == 0 and new_v):
                emoji = "🟢"
            elif old_v is not None and new_v is not None and new_v > old_v:
                emoji = "🟢"
            elif old_v is not None and new_v is not None and new_v < old_v:
                emoji = "🟠"
            else:
                emoji = "🟡"
            parts.append("### %s %s `%s`" % (emoji, r["name"], r["code"]))
            parts.append("- 变化：**%s** → **%s**" % (old_txt, new_txt))
            if r["note"]:
                parts.append("- 备注：%s" % r["note"])
            parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("**当前全量状态**")
        parts.append("")
        parts.append(render_table(results))
        parts.append("")
        parts.append("> %s" % summarize(results))
        if args.dry_notify:
            print("\n===== 推送标题 =====\n" + title)
            print("\n===== 推送正文 =====\n" + "\n".join(parts))
            log("（预览模式，未真正推送）")
            return
        notify(title, "\n".join(parts))
        log("检测到 %d 项变动，已推送" % len(changes))
    else:
        log("额度无变动（%s）" % summarize(results))

    save_state(results)
    update_readme(results)


if __name__ == "__main__":
    main()
