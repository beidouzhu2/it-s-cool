#!/usr/bin/env python3
"""Send categorized weekly links; never install or modify packages."""
import argparse
import datetime as dt
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

FAMILIES = (("IPK", ""), ("APK", "openwrt25-"), ("CORE", "core-"))
TITLES = {
    "IPK": "📦 OpenWrt 24.10 / IPK 插件",
    "APK": "📦 OpenWrt 25.12 / APK 插件（不要用于 IPK 系统）",
    "CORE": "⚙️ 独立内核更新（注意系统及架构）",
}
LIMIT = 3700

def units(s):
    return len(s.encode("utf-16-le")) // 2

def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Bleki-weekly"}
    token = os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request("https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise

def release_assets(tag):
    data = api("/releases/tags/" + urllib.parse.quote(tag, safe=""))
    if not data or data.get("draft"):
        return []
    out = []
    page = 1
    while True:
        assets = api(f"/releases/{data['id']}/assets?per_page=100&page={page}")
        if not isinstance(assets, list):
            raise RuntimeError("Cannot list release assets")
        out.extend(a for a in assets if a.get("state") == "uploaded" and a.get("size", 0) > 0 and a["name"].lower().endswith(".run"))
        if len(assets) < 100:
            return out
        page += 1

def collect(today, fetch=release_assets):
    found = {}
    for family, prefix in FAMILIES:
        found[family] = (None, [])
        for age in range(8):
            date = (today - dt.timedelta(days=age)).isoformat()
            assets = fetch(prefix + date)
            if assets:
                found[family] = (date, assets)
                break
    return found

def arch(name):
    n = name.lower()
    if "aarch64" in n or "arm64" in n:
        if "a53" in n or "cortex-a53" in n:
            return "ARM64 / Cortex-A53"
        if "generic" in n:
            return "ARM64 / Generic"
        return "ARM64"
    if "aarch32" in n or "armv7" in n or "arm32" in n:
        return "ARM32"
    if "x86_64" in n or "x86-64" in n or "amd64" in n:
        return "x86_64"
    if "x86" in n:
        return "x86（请核对）"
    return "架构请核对文件名"

def classify(found):
    groups = {k: [] for k, _ in FAMILIES}
    for family, (date, assets) in found.items():
        for a in sorted(assets, key=lambda x: x["name"].lower()):
            n = a["name"].lower()
            core = family == "CORE" or n.startswith(("sing-box_", "25-sing-box_", "xray-core_"))
            group = "CORE" if core else family
            source = {"IPK": "24.10/IPK", "APK": "25.12/APK", "CORE": "24/25（请核对兼容性）"}[family]
            groups[group].append((date, source, a))
    return groups

def render(today, found):
    groups = classify(found)
    messages = []
    for group, entries in groups.items():
        header = f"⭐️ <b>Bleki 插件每周更新</b>\n<b>{TITLES[group]}</b>\n推送日期：{today.isoformat()} · {len(entries)} 个文件\n\n"
        chunk = header
        if not entries:
            messages.append(header + "最近 8 个日历日没有可用安装包；请检查构建结果。")
            continue
        for date, source, a in entries:
            name = html.escape(a["name"])
            url = html.escape(a["browser_download_url"], quote=True)
            stamp = date if date == today.isoformat() else date + "（历史构建）"
            line = f"♦️ <code>{name}</code>\n{html.escape(arch(a['name']))} · {html.escape(source)} · {stamp}\n<a href=\"{url}\">点击下载 .run</a>\n\n"
            if units(header + line) > LIMIT:
                raise RuntimeError("Asset entry too long")
            if units(chunk + line) > LIMIT:
                messages.append(chunk)
                chunk = header
            chunk += line
        messages.append(chunk)
    return messages

def send(messages):
    for msg in messages:
        data = urllib.parse.urlencode({"chat_id": os.environ["TG_CHAT_ID"], "text": msg, "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen("https://api.telegram.org/bot" + os.environ["TG_BOT_TOKEN"] + "/sendMessage", data=data, timeout=30) as resp:
                result = json.load(resp)
        except (urllib.error.URLError, TimeoutError):
            raise SystemExit("Telegram request failed")
        if not result.get("ok"):
            raise SystemExit("Telegram rejected message")
    print(f"Sent {len(messages)} categorized message(s)")

def self_test():
    today = dt.date(2026, 11, 30)
    def a(name):
        return {"name": name, "browser_download_url": "https://github.com/example/repo/releases/download/test/" + name}
    data = {
        "2026-11-30": [a("openclash-x86-64.run"), a("sing-box_v1_aarch64_generic.run")] + [a(f"test_{i}_aarch64_cortex-a53.run") for i in range(50)],
        "openwrt25-2026-11-29": [a("25-openclash_x86_64.run"), a("25-sing-box_v1_aarch64_cortex-a53.run")],
        "core-2026-11-30": [a("xray-core_v1_aarch64_a53.run")],
    }
    found = collect(today, lambda tag: data.get(tag, []))
    groups = classify(found)
    assert [len(groups[k]) for k in ("IPK", "APK", "CORE")] == [51, 1, 3]
    assert found["APK"][0] == "2026-11-29"
    msgs = render(today, found)
    assert len(msgs) > 3 and all(units(m) <= LIMIT for m in msgs)
    assert any("历史构建" in m and "25-openclash" in m for m in msgs)
    assert any("Cortex-A53" in m for m in msgs)
    assert any("<code>openclash-x86-64.run</code>" in m for m in msgs)
    assert any('">点击下载 .run</a>' in m for m in msgs)
    assert not any("<b>openclash-x86-64.run</b>" in m for m in msgs)
    assert len(render(today, collect(today, lambda _: []))) == 3
    print("Classification, date fallback, missing-family notices and message chunking passed")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    today = dt.datetime.now(ZoneInfo("Asia/Shanghai")).date()
    found = collect(today)
    messages = render(today, found)
    for key, entries in classify(found).items():
        print(f"{key}: {len(entries)} files")
    if args.dry_run:
        print(f"Dry run: {len(messages)} messages; no Telegram delivery")
    else:
        send(messages)

if __name__ == "__main__":
    main()
