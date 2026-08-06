# -*- coding: utf-8 -*-
"""通过 CDP 提取 B 站客户端会话 Cookie。

前置：B 站客户端已用调试端口启动并登录：
  "<bilibili.exe>" --remote-debugging-port=9222

用法:
  python extract_bili_cookies.py --cdp http://127.0.0.1:9222 --out cookies.json
"""
import argparse
import asyncio
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
import websockets

KEEP = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5",
        "buvid3", "b_nut", "bili_ticket")


def get_targets(cdp):
    with urllib.request.urlopen(cdp + "/json/list", timeout=5) as r:
        return json.loads(r.read())


async def get_cookies(ws_url):
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "Network.getAllCookies"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 2:
                return msg["result"]["cookies"]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="http://127.0.0.1:9222")
    ap.add_argument("--out", default="cookies.json")
    args = ap.parse_args()

    targets = get_targets(args.cdp)
    print("targets:", len(targets))
    for t in targets:
        print("-", t.get("type"), (t.get("url") or "")[:80], (t.get("title") or "")[:40])
    page = next((t for t in targets if t.get("type") == "page"), targets[0])
    cookies = await get_cookies(page["webSocketDebuggerUrl"])
    print("total cookies:", len(cookies))
    keep = {}
    for c in cookies:
        n = c.get("name", "")
        if n in KEEP:
            keep[n] = c.get("value", "")
            print(f"{n} = {c.get('value','')[:60]} (domain={c.get('domain')})")
    json.dump(keep, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", len(keep), "cookies ->", args.out)
    if "SESSDATA" not in keep or "bili_jct" not in keep:
        print("WARN: 缺少 SESSDATA/bili_jct，可能未登录")


asyncio.run(main())
