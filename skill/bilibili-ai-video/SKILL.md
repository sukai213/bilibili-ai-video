---
name: bilibili-ai-video
description: End-to-end creation and publishing of original AI/tech review videos to Bilibili. Use when the user wants to (1) produce an AI/tech review video from scratch - original copywriting, AI voiceover, holo-tech slides, ffmpeg assembly with loudness normalization, cover image - and/or (2) publish/upload a finished video to Bilibili automatically via the web upload API (cover upload, preupload, chunked UPOS upload, archive add/v3) using cookies extracted from the logged-in Bilibili client, including post-publish verification. Covers DeepSeek/LLM/Agent review topics, Qwen3-TTS voiceover, CDP cookie extraction, and Bilibili upload API details.
---

# Bilibili AI 科技视频制作与发布

## 概述

把「AI 科技测评视频」从零做成成品并自动发布到 B 站：原创文案 → 分段脚本 → TTS 配音 → 全息科技风幻灯片 → ffmpeg 剪辑成片（含响度标准化）→ 提取客户端登录态 → 网页投稿 API 自动上传发布 → 公开验证。全流程已在真实环境跑通（DeepSeek V4 Flash「贾维斯时刻」实测视频，BV1gSup66E4i）。

## 工作流总览

1. 选题与原创文案（严禁抄袭）
2. 分段脚本 `segments.json`（场景 / 标题 / 要点 / 旁白）
3. Qwen3-TTS 逐段配音（记录每段时长）
4. 全息蓝科技风幻灯片（1920x1080）
5. ffmpeg 分段编码 + 拼接 + BGM 混音 + loudnorm 响度标准化
6. 从已登录 B 站客户端提取 Cookie（CDP，不要试图解密 Cookie 库）
7. 上传发布：封面 → 预上传 → upos 元数据 → 分块上传 → 完成通知 → add/v3 提交
8. 公开验证：view 接口 / 播放地址 / 标签

## 第 1 步：原创文案

- 文案必须完全原创，禁止抄袭他人文案；数据需来自官方文档/官方公告并标注来源。
- 参考结构（详见 `references/copy-template.md`）：视频概述（选题/观众/时长/卖点）、标题候选、封面文案、简介模板、分镜脚本（时间轴/画面/旁白/音效）、避坑点、来源标注。
- 成片后按实际分段时间轴改写简介里的时间点，别用预估时间。

## 第 2 步：分段脚本

用 `scripts/segments.example.json` 的格式定义 24 段左右：`id, scene, title, points[], narration`。旁白即口播逐字稿。scene 影响幻灯片配色。

## 第 3 步：TTS 配音

运行 `scripts/gen_tts.py`：

```bash
python gen_tts.py --segments segments.json --out audio --model-dir <Qwen3-TTS-Q5 目录> --voice "35岁男性科技主播，声音沉稳、磁性、冷静，普通话标准，语速适中"
```

- 输出 `audio/seg_XX.wav` 与 `audio/meta.json`（含每段时长），支持断点续跑。
- **必须**在脚本内设置 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`，否则引擎打印 emoji 会抛异常。
- 同一视频内保持同一 voice、同一 seed，音色才一致。

## 第 4 步：幻灯片

运行 `scripts/gen_slides.py`：

```bash
python gen_slides.py --segments segments.json --out slides --brand "DEEPSEEK V4 FLASH" --watermark "「 贾维斯时刻 」"
```

- 输出 1920x1080 全息蓝科技风 PNG，含标题、要点、底部字幕条、进度角标。
- 之后用 `03_cover.py` 同款风格生成封面（主标题+副标题+小字卖点），参见 `scripts/gen_cover.py`。

## 第 5 步：剪辑成片

运行 `scripts/assemble_video.py`：

```bash
python assemble_video.py --segments segments.json --meta audio/meta.json --slides slides --audio audio --out . --ffmpeg <ffmpeg.exe 路径>
```

- 逐段 `-loop 1` 编码（每段加 0.35s 尾白），concat 拼接，合成环境 BGM，最后 loudnorm 响度标准化（目标 I=-16 LUFS，符合 B 站要求）。
- 成片约 5 分钟 / 14MB，H.264 1080p30 + AAC 44.1kHz。

## 第 6 步：提取登录态（Cookie）

1. 关闭 B 站客户端，用调试端口重启：`bilibili.exe --remote-debugging-port=9222`，手动登录一次。
2. 运行 `scripts/extract_bili_cookies.py --cdp http://127.0.0.1:9222 --out cookies.json`。
3. 用 `GET https://api.bilibili.com/x/web-interface/nav` 验证 `isLogin=true`。
- **坑**：B 站新版 Cookie 存 SQLite v18 且带 App-Bound 加密，无法 DPAPI 解密，必须走 CDP `Network.getAllCookies`。
- 至少提取 `SESSDATA / bili_jct / DedeUserID / buvid3 / bili_ticket`。

## 第 7 步：上传发布

运行 `scripts/publish_bilibili.py`：

```bash
python publish_bilibili.py --video final_loud.mp4 --cover cover.png --cookies cookies.json --config publish.json
```

`publish.json` 字段：`title / desc / tag / dynamic / tid / human_type2`。发布流程：

1. 封面：`POST https://member.bilibili.com/x/vu/web/cover/up`（form：`csrf`、`cover=data:image/png;base64,...`）→ `data.url`
2. 预上传：`GET https://member.bilibili.com/preupload?name=..&size=..&r=upos&profile=ugcfx/bup&version=2.10.4.0&build=2140000` → `auth / chunk_size / endpoint / upos_uri / biz_id`
3. upos 元数据：`POST https:{endpoint}/{path}?uploads=&output=json&profile=ugcfx/bup&filesize=..&partsize=..&biz_id=..`（头 `X-Upos-Auth`）→ `upload_id`
4. 分块：`PUT https:{endpoint}/{path}?uploadId=..&chunks=..&total=..&chunk=i&size=..&partNumber=i+1&start=..&end=..`（`X-Upos-Auth`，application/octet-stream），失败重试（最多 4 次，间隔 3s）
5. 完成通知：`POST` 同 upos URL，`name`（带扩展名）、`uploadId`、`biz_id`、`output=json`、`profile=ugcfx/bup`，JSON body `{"parts":[{"partNumber":n,"eTag":"etag"}]}` → `OK=1`
6. 提交：`POST https://member.bilibili.com/x/vu/web/add/v3`（URL 参数 `ts/csrf`，JSON body）→ `data.bvid`
   - `videos[0]`：`filename` = upos_uri 的文件名**去掉扩展名**，`cid` = 预上传返回的 `biz_id`
   - 其他必填：`copyright=1`（自制）、`tid`、`tag`（≤10 个逗号分隔）、`desc_format_id=9999`、`recreate=-1`、`interactive=0`、`act_reserve_create=0`、`no_disturbance=0`、`no_reprint=0`、`subtitle={"open":0,"lan":""}`、`dolby=0`、`lossless_music=0`、`up_selection_reply=false`、`up_close_reply=false`、`up_close_danmu=false`、`web_os=3`、`csrf=bili_jct`
- 分区 `tid` 不能完全依赖 `types/predict`（预测可能不准），直接查 `references/bilibili-upload-api.md` 的分区表或 `x/vupre/web/archive/pre` 的 `typelist`。常用：科技-计算机技术=231、科技-数码=95、知识-科学科普=201。
- 请求头统一：`User-Agent`（浏览器 UA）+ `Referer: https://member.bilibili.com/` + `Origin: https://member.bilibili.com/`。
- 账号需完成手机绑定/实名才能发布；发布后视频先进审核（`is_pubing`），几分钟内公开。

## 第 8 步：验证

运行 `scripts/verify_published.py --bvid BVxxxx --cookies cookies.json`，检查：

- `GET https://api.bilibili.com/x/web-interface/view?bvid=..` 返回 `code=0, state=0`
- 播放地址 `GET https://api.bilibili.com/x/player/playurl` 有 durl/dash
- 标签接口返回 10 个标签、`tid` 正确

## 关键坑速查

- TTS 必须 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`。
- Cookie 必须走 CDP，别碰 SQLite 解密。
- add/v3 的 `filename` 无扩展名；完成通知的 `name` 带扩展名；`cid=biz_id`。
- `bili_jct` 即 CSRF；提交需带 `csrf`（URL 参数 + body）。
- 标题 ≤80 字、简介 ≤2000 字、标签 ≤10 个、封面 16:10。
- 发布后先在创作中心确认 `arc_audits` 无 `reject_reason`。

## 资源

- `scripts/`：`gen_tts.py` / `gen_slides.py` / `gen_cover.py` / `assemble_video.py` / `extract_bili_cookies.py` / `publish_bilibili.py` / `verify_published.py` / `segments.example.json`
- `references/`：`workflow.md`（详细流程与坑）、`bilibili-upload-api.md`（投稿接口文档）、`copy-template.md`（原创文案模板）
- `assets/`：示例封面、示例幻灯片
