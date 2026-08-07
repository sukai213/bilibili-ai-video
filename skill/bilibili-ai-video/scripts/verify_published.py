# -*- coding: utf-8 -*-
"""发布后验证：view 接口 / 播放地址 / 标签 / 创作中心审核状态。

用法:
  python verify_published.py --bvid BV1gSup66E4i --cookies cookies.json
"""
import argparse
import json
import os
import sys

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvid", required=True)
    ap.add_argument("--cookies", required=True)
    args = ap.parse_args()

    cookies = json.load(open(args.cookies, encoding="utf-8-sig"))
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    s.cookies.update(cookies)

    j = s.get("https://api.bilibili.com/x/web-interface/view",
              params={"bvid": args.bvid}, timeout=20).json()
    if j.get("code") != 0:
        print("未公开或不存在:", j.get("code"), j.get("message"))
        return 1
    d = j["data"]
    print("bvid    :", d["bvid"])
    print("aid     :", d["aid"])
    print("title   :", d["title"])
    print("desc    :", (d.get("desc") or "")[:80].replace("\n", " / "))
    print("tid     :", d["tid"], "| tname:", d.get("tname"))
    print("state   :", d["state"], "(0=公开)")
    print("duration:", d["duration"], "s")
    print("cover   :", d.get("pic"))
    st = d.get("stat") or {}
    print("stats   : view=%s like=%s coin=%s favorite=%s" % (st.get("view"), st.get("like"), st.get("coin"), st.get("favorite")))

    pr = s.get("https://api.bilibili.com/x/player/playurl",
               params={"bvid": args.bvid, "cid": d["cid"], "qn": 16}, timeout=20).json()
    dd = pr.get("data") or {}
    ok = bool(dd.get("durl")) or bool(dd.get("dash"))
    print("play    :", "OK" if ok else "不可播放", "| durl:", len(dd.get("durl") or []), "| dash:", bool(dd.get("dash")))

    try:
        t = s.get("https://api.bilibili.com/x/tag/archive/tags",
                  params={"bvid": args.bvid}, timeout=20).json()
        tags = [x.get("tag_name") for x in (t.get("data") or [])]
        print("tags    :", tags)
    except Exception as e:
        print("tags err:", e)

    try:
        a = s.get("https://member.bilibili.com/x/web/archives",
                  params={"status": "all", "pn": 1, "ps": 10}, timeout=20).json()
        for x in (a.get("data") or {}).get("arc_audits") or []:
            arc = x.get("Archive") or {}
            if str(arc.get("aid")) == str(d["aid"]):
                print("audit   :", "通过" if not arc.get("reject_reason") else ("驳回: " + arc.get("reject_reason")))
    except Exception as e:
        print("audit err:", e)

    print("url     : https://www.bilibili.com/video/%s" % args.bvid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
