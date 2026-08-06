# -*- coding: utf-8 -*-
"""B 站网页投稿：封面 -> 预上传 -> upos 元数据 -> 分块上传 -> 完成通知 -> add/v3 提交。

用法:
  python publish_bilibili.py --video final_loud.mp4 --cover cover.png \
      --cookies cookies.json --config publish.json

publish.json:
  {"title": "...", "desc": "...", "tag": "a,b,c", "dynamic": "...",
   "tid": 231, "human_type2": 1012}
"""
import argparse
import base64
import json
import math
import os
import sys
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def make_session(cookies):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://member.bilibili.com/",
                      "Origin": "https://member.bilibili.com"})
    s.cookies.update(cookies)
    return s


def jdump(obj):
    return json.dumps(obj, ensure_ascii=False)


def step_cover(session, cover_path, csrf):
    b64 = base64.b64encode(open(cover_path, "rb").read()).decode()
    r = session.post("https://member.bilibili.com/x/vu/web/cover/up",
                     params={"ts": int(time.time() * 1000)},
                     data={"csrf": csrf, "cover": f"data:image/png;base64,{b64}"}, timeout=60)
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"cover up failed: {jdump(j)}")
    log(f"封面已上传: {j['data']['url']}")
    return j["data"]["url"]


def step_preupload(session, filename, size):
    params = {"name": filename, "size": size, "r": "upos", "profile": "ugcfx/bup",
              "ssl": 0, "version": "2.10.4.0", "build": "2140000", "webVersion": "2.13.0"}
    r = session.get("https://member.bilibili.com/preupload", params=params, timeout=30)
    j = r.json()
    if j.get("OK") != 1:
        raise RuntimeError(f"preupload failed: {jdump(j)}")
    log(f"预上传 OK: biz_id={j['biz_id']} chunk_size={j['chunk_size']} uri={j['upos_uri']}")
    return j


def step_meta(pre, size):
    url = f"https:{pre['endpoint']}/{pre['upos_uri'].replace('upos://', '')}"
    params = {"uploads": "", "output": "json", "profile": "ugcfx/bup",
              "filesize": size, "partsize": pre["chunk_size"], "biz_id": pre["biz_id"]}
    r = requests.post(url, params=params,
                      headers={"X-Upos-Auth": pre["auth"], "User-Agent": UA}, timeout=30)
    j = r.json()
    if j.get("OK") != 1:
        raise RuntimeError(f"upos meta failed: {jdump(j)}")
    log(f"upos 元数据 OK: upload_id={j['upload_id']}")
    return j["upload_id"], url


def step_chunks(url, auth, upload_id, video_path, size, chunk_size):
    chunks = math.ceil(size / chunk_size)
    log(f"开始分块上传: {chunks} 块 x {chunk_size}")
    etags = []
    with open(video_path, "rb") as f:
        for i in range(chunks):
            start = i * chunk_size
            data = f.read(chunk_size)
            params = {"uploadId": upload_id, "chunks": chunks, "total": size,
                      "chunk": i, "size": len(data), "partNumber": i + 1,
                      "start": start, "end": start + len(data)}
            ok = False
            for attempt in range(1, 5):
                try:
                    r = requests.put(url, params=params, data=data,
                                     headers={"X-Upos-Auth": auth,
                                              "Content-Type": "application/octet-stream",
                                              "User-Agent": UA}, timeout=240)
                    if r.status_code == 200:
                        etag = r.headers.get("ETag") or r.headers.get("Etag") or "etag"
                        etags.append(etag.strip('"'))
                        log(f"  分块 {i + 1}/{chunks} OK (etag={etag})")
                        ok = True
                        break
                    log(f"  分块 {i + 1} 尝试{attempt} 失败 status={r.status_code} {r.text[:100]}")
                except Exception as e:
                    log(f"  分块 {i + 1} 尝试{attempt} 异常: {e}")
                time.sleep(3)
            if not ok:
                raise RuntimeError(f"分块 {i + 1} 上传失败")
    return etags, chunks


def step_finalize(url, auth, upload_id, biz_id, filename, etags, chunks):
    params = {"name": filename, "uploadId": upload_id, "biz_id": biz_id,
              "output": "json", "profile": "ugcfx/bup"}
    parts = [{"partNumber": i + 1,
              "eTag": etags[i] if i < len(etags) else "etag"} for i in range(chunks)]
    r = requests.post(url, params=params, json={"parts": parts},
                      headers={"X-Upos-Auth": auth,
                               "Content-Type": "application/json; charset=UTF-8",
                               "User-Agent": UA}, timeout=60)
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text[:300]}
    if j.get("OK") != 1:
        raise RuntimeError(f"upos finalize failed: {jdump(j)}")
    log("upos 上传完成通知 OK")


def step_submit(session, cfg, cover_url, stem, cid, csrf):
    payload = {
        "videos": [{"filename": stem, "title": cfg["title"], "desc": "", "cid": cid}],
        "cover": cover_url, "cover43": "", "title": cfg["title"],
        "copyright": 1, "tid": cfg["tid"],
        "tag": cfg["tag"], "desc_format_id": 9999, "desc": cfg["desc"],
        "recreate": -1, "dynamic": cfg.get("dynamic", ""),
        "interactive": 0, "act_reserve_create": 0, "no_disturbance": 0,
        "no_reprint": 0, "subtitle": {"open": 0, "lan": ""},
        "dolby": 0, "lossless_music": 0,
        "up_selection_reply": False, "up_close_reply": False, "up_close_danmu": False,
        "web_os": 3, "csrf": csrf,
    }
    if cfg.get("human_type2"):
        payload["human_type2"] = cfg["human_type2"]
    session.get("https://member.bilibili.com/x/geetest/pre/add", timeout=10)
    ts = int(time.time() * 1000)
    r = session.post("https://member.bilibili.com/x/vu/web/add/v3",
                     params={"ts": ts, "csrf": csrf}, json=payload, timeout=60)
    j = r.json()
    log(f"add/v3 响应: {jdump(j)[:400]}")
    if j.get("code") != 0:
        raise RuntimeError(f"add/v3 failed: {jdump(j)}")
    return j["data"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--cover", required=True)
    ap.add_argument("--cookies", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cookies = json.load(open(args.cookies, encoding="utf-8"))
    cfg = json.load(open(args.config, encoding="utf-8"))
    csrf = cookies["bili_jct"]
    filename = os.path.basename(args.video)
    size = os.path.getsize(args.video)
    log(f"== 开始上传发布 == {filename} ({size} bytes)")

    session = make_session(cookies)
    cover_url = step_cover(session, args.cover, csrf)
    pre = step_preupload(session, filename, size)
    upload_id, url = step_meta(pre, size)
    etags, chunks = step_chunks(url, pre["auth"], upload_id, args.video, size, pre["chunk_size"])
    step_finalize(url, pre["auth"], upload_id, pre["biz_id"], filename, etags, chunks)

    stem = os.path.splitext(pre["upos_uri"].split("/")[-1])[0]
    cid = pre["biz_id"]
    log(f"稿件 filename={stem} cid={cid}")

    data = step_submit(session, cfg, cover_url, stem, cid, csrf)
    bvid = data.get("bvid")
    log(f"== 发布成功 == aid={data.get('aid')} bvid={bvid}")
    log(f"链接: https://www.bilibili.com/video/{bvid}")
    if args.config:
        out = os.path.join(os.path.dirname(os.path.abspath(args.config)), "publish_result.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"code": 0, "data": data, "cover": cover_url, **cfg},
                      f, ensure_ascii=False, indent=2)
        log(f"结果已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
