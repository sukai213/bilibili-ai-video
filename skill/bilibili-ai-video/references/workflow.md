# 制作与发布详细流程（含踩坑记录）

本流程已在真实环境完整跑通：
成片 `final_loud.mp4`（5 分 15 秒 / 14MB，H.264 1080p30 + AAC 44.1kHz，响度 mean -18.7 LUFS）
已发布 https://www.bilibili.com/video/BV1gSup66E4i

## 环境依赖

- Windows + Python 3.10+
- `ffmpeg`（9.0 essentials 可用，路径示例 `C:\Users\Administrator\ffmpeg\ffmpeg-9.0-essentials_build\bin\ffmpeg.exe`）
- 微软雅黑字体 `C:\Windows\Fonts\msyh.ttc` / `msyhbd.ttc`
- Python 包：`Pillow numpy requests websockets`（`pip install pillow numpy requests websockets`）
- Qwen3-TTS-Q5 语音模型（本地 GGUF 量化版，含 `model-design` 子目录；本机位于 `C:\Users\Administrator\Desktop\Qwen3-TTS-Q5`）
- 已登录的 B 站客户端（用于提取 Cookie）

## 阶段 1：文案与分段

1. 原创文案：概述 / 标题候选 / 封面文案 / 简介 / 分镜脚本 / 避坑 / 来源。模板见 `copy-template.md`。
2. 写成 `segments.json`（数组），每段含 `id / scene / title / points[] / narration`。旁白即逐字稿。
3. 制作封面图（16:10 或 1920x1080），用与幻灯片一致的全息蓝风格。

## 阶段 2：配音（Qwen3-TTS）

```bash
python gen_tts.py --segments segments.json --out audio --model-dir "C:\Users\Administrator\Desktop\Qwen3-TTS-Q5" --voice "35岁男性科技主播，声音沉稳、磁性、冷静，普通话标准，语速适中，略带金属质感的未来感"
```

- 输出 `audio/seg_01.wav ... seg_24.wav` + `audio/meta.json`（每段 `duration`）。
- 单段生成约 5-12 秒（GPU/ONNX DML），可续跑。
- 坑：引擎打印 emoji 依赖 UTF-8 控制台，脚本内必须 `os.environ["PYTHONIOENCODING"]="utf-8"`、`os.environ["PYTHONUTF8"]="1"`，否则初始化抛异常；引擎就绪后反复 create engine 可能再次失败，尽量一次跑完。

## 阶段 3：幻灯片与封面

```bash
python gen_slides.py --segments segments.json --out slides
python gen_cover.py --title "贾维斯时刻！" --subtitle "DeepSeek V4 Flash 正式版实测" --hints "1M 上下文 / 1元每百万token / Agent 大幅升级" --out cover.png
```

- 幻灯片 1920x1080，深蓝渐变 + 网格 + 光晕 + 辉光文字，每段一页：标题 / 要点 / 底部字幕条 / 右上进度。
- 封面同风格：主标题 + 副标题 + 小字卖点。

## 阶段 4：剪辑成片

```bash
python assemble_video.py --segments segments.json --meta audio/meta.json --slides slides --audio audio --out . --ffmpeg <ffmpeg路径>
```

步骤：
1. 每段：`ffmpeg -loop 1 -framerate 30 -t dur -i slide.png -i seg.wav -c:v libx264 -crf 20 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 44100 -shortest`（时长 = 旁白 + 0.35s 尾白）。
2. concat demuxer 拼接。
3. 混入合成环境 BGM（脚本内置 Am-F-C-G 和弦垫底，音量 0.10），首尾淡入淡出。
4. 响度标准化：`loudnorm=I=-16:TP=-1.5:LRA=11`（B 站建议 -16 LUFS 左右），输出 `final_loud.mp4`。
5. 抽样 3 帧与对应幻灯片做相关性检查，确认画面与分镜对应。

## 阶段 5：登录态

1. 关闭 B 站客户端 → `"<bilibili安装路径>\bilibili.exe" --remote-debugging-port=9222` 启动并登录。
2. `python extract_bili_cookies.py --cdp http://127.0.0.1:9222 --out cookies.json`
3. 验证 `GET https://api.bilibili.com/x/web-interface/nav` → `code=0, isLogin=true`。

坑：
- B 站新版 Cookie 在 `Network\Cookies`（SQLite v18），值被 App-Bound 加密，DPAPI 解不开，别浪费时间，直接 CDP。
- CDP 页面里 `Network.getAllCookies` 一次拿全量 Cookie。

## 阶段 6：上传发布

```bash
python publish_bilibili.py --video final_loud.mp4 --cover cover.png --cookies cookies.json --config publish.json
```

`publish.json`：

```json
{
  "title": "【贾维斯时刻】DeepSeek V4 Flash 正式版实测：喊一声“贾维斯”，它把活全干完了",
  "desc": "……（≤2000 字，含实际分段时间轴与来源标注）",
  "tag": "DeepSeek,DeepSeekV4,V4Flash,AI编程,大模型,Agent,贾维斯,开源,人工智能,API教程",
  "dynamic": "……（粉丝动态文案）",
  "tid": 231,
  "human_type2": 1012
}
```

接口顺序与要点（详见 `bilibili-upload-api.md`）：

1. 封面 `POST /x/vu/web/cover/up?ts=`（form：`csrf`、`cover=data:image/png;base64,...`）→ `data.url`
2. 预上传 `GET /preupload`（`name` 带扩展名、`size`、`r=upos`、`profile=ugcfx/bup`、`ssl=0`、`version=2.10.4.0`、`build=2140000`）→ `auth/biz_id/chunk_size/endpoint/upos_uri`
3. upos 元数据 `POST https:{endpoint}/{path}?uploads=&output=json&profile=ugcfx/bup&filesize=&partsize=&biz_id=`（头 `X-Upos-Auth: auth`）→ `upload_id`
4. 分块 `PUT https:{endpoint}/{path}?uploadId=&chunks=&total=&chunk=&size=&partNumber=&start=&end=`（`X-Upos-Auth`；`size/end` 用该分块实际字节数；失败重试 4 次间隔 3s）→ 200
5. 完成通知 `POST` 同 URL（`name` 带扩展名、`uploadId`、`biz_id`、`output=json`、`profile=ugcfx/bup`），body `{"parts":[{"partNumber":n,"eTag":"etag"}]}` → `OK=1`
6. 提交 `POST /x/vu/web/add/v3?ts=&csrf=`，JSON body 见 SKILL.md 第 7 步；`videos[0].filename` = upos_uri 文件名去扩展名，`videos[0].cid` = `biz_id`

请求头：`User-Agent` 浏览器 UA、`Referer: https://member.bilibili.com/`、`Origin: https://member.bilibili.com/`。所有 POST 带 `csrf=bili_jct`。

## 阶段 7：验证

```bash
python verify_published.py --bvid BV1gSup66E4i --cookies cookies.json
```

检查项：
- `view` 接口 `code=0`、`state=0`（公开）、`tid`、`title`、`desc`、`pic` 正确
- `playurl` 有 durl/dash（可播放）
- 创作中心 `x/web/archives` 的 `arc_audits` 无 `reject_reason`；初审几分钟内公开

## 常见错误码

- `-101` 未登录（Cookie 失效，重新走 CDP）
- `-111` CSRF 失败（`csrf` 必须等于 `bili_jct`）
- `-400` 请求参数错误（检查必填字段与 filename 格式）
- `53019` 标题过长（≤80 字）
- 预上传 404：路径是 `member.bilibili.com/preupload`，不是 `/x/vupre/web/upload/preupload`
- upos PUT 403：缺 `X-Upos-Auth` 请求头

## 本次实战新增踩坑（2026-08-07 Qwen3.8-Max 视频，BV1Gfub6fELA）

实战流程与之前一致：选题(Qwen3.8-Max) → 原创文案 17 段 → 音色克隆配音 → 幻灯片/封面 → ffmpeg 成片 → 网页投稿 API 发布。以下为本次新增问题与解决方案：

### 1. PowerShell 管道传中文 → 发布乱码（最严重）
- 现象：`@'...'@ | python -` 方式生成的 publish.json 中所有中文变成 `?`，发布后 B 站标题/简介/标签全乱码，完全没法推流。
- 原因：Windows PowerShell 5.1 默认 `$OutputEncoding` 为 ASCII，管道传给原生进程时中文被替换成 `?`。
- 规则：**含中文的 JSON/脚本一律禁止走 PowerShell 管道进 Python stdin**。
  - 正确：`@'...'@ | Set-Content -Encoding UTF8 file.json`（PowerShell 内存 UTF-16 → UTF-8 文件，安全）
  - 或直接用 `apply_patch`
  - Python 读 PowerShell 写出的文件用 `encoding="utf-8-sig"`（带 BOM）或先转无 BOM。
- 自查：发布前 `python -c "print(open('publish.json',encoding='utf-8').read()[:50])"` 确认无 `?`。

### 2. 已发布稿件乱码的修复
- 接口：`POST https://member.bilibili.com/x/vu/web/edit?ts=&csrf=`，body 与 add/v3 一致并加 `aid`。
- 关键字段：`videos[0]` = `{"filename": <upos_uri 文件名去扩展名>, "title": cfg["title"], "desc": "", "cid": <biz_id>}`；`cover` 用已上传封面 URL（发布结果里保存的 `data.cover` 或封面接口返回 url）；`tag` 用逗号分隔完整重传。
- 实测返回 `code=0` 后，view/tag 接口立即看到正确标题简介与全部 10 个标签。
- 不要用 `x/tag/archive/add|del` 补标签：web Cookie 直接 `-403 访问权限不足`。

### 3. 克隆参考音频时长限制（speaker encoder）
- `qwen3_tts_speaker_encoder.fp16.onnx` 对超过约 30s 的音频报 `Expand node invalid expand shape`（41s 失败、30s 成功，与 onnxruntime 版本无关）。
- 流程：先 whisper/faster-whisper 转写拿到逐句时间轴 → ffmpeg 裁剪 ≤30s 干净片段 → 用对应文本 `character_voice.py save`。
- 本机 ffmpeg 路径：`C:\Users\Administrator\ffmpeg\ffmpeg-9.0-essentials_build\bin\ffmpeg.exe`。

### 4. TTS 引擎禁止 stdin 方式运行
- 现象：`python -` 跑引擎，spawn 子进程重载 `__main__` 报 `OSError: ... '<stdin>'`，随后"解码器超时"，引擎返回 None。
- 规则：TTS 只能 `python gen_tts_clone.py`（脚本文件），并在 `__main__` 里 `multiprocessing.freeze_support()`。

### 5. loudnorm 输出采样率
- assemble_video.py 的 loudnorm 步骤未指定采样率时，ffmpeg 输出 96kHz AAC；按规范应补 `-ar 44100`：
  `ffmpeg -y -i final.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:v copy -c:a aac -b:a 192k -ar 44100 -movflags +faststart final_loud.mp4`

### 6. 其他
- 发布后 `view` 返回 -404 是审核中（is_pubing），等约 2 分钟后再验证；确认 `state=0` 公开、`playurl` 有 durl、`arc_audits` 通过。
- `gen_slides.py` / `assemble_video.py` 直接迭代 JSON 顶层，segments 必须是数组；如果文案写成 `{"segments":[...]}`，另存 `segments_array.json` 传入。
- 标签数量以 tag 接口复查为准：本次修复后 10 个标签全部挂上，乱码标签（如 `AI??`）不会再出现。
