# 错误总结与修正（2026-08-07 Qwen3.8-Max 视频实战）

> 本文档是 bilibili-ai-video 的「错误档案」：每条含现象 / 根因 / 修正 / 预防。SKILL.md 关键坑速查与 workflow.md 已含要点，本文档为完整版。

## 1. 发布后标题/简介/标签全乱码（最严重）

- 现象：视频已发布成功，但 B 站页面上标题、简介、标签里的中文全部变成 `?`，完全没法推流。
- 根因：`publish.json` 由 PowerShell `@'...'@ | python -` 管道生成，Windows PowerShell 5.1 默认 `$OutputEncoding` 为 ASCII，中文经 stdin 传给 Python 时被替换成 `?`。
- 修正：用编辑接口修复已发布稿件：
  `POST https://member.bilibili.com/x/vu/web/edit?ts=&csrf=`，body 与 add/v3 一致并加 `aid`；`videos[0]` = `{"filename": <upos_uri 文件名去扩展名>, "title", "desc": "", "cid": <biz_id>}`；`cover` 用已上传封面 URL；`tag` 完整重传。实测 `code=0` 后 view/tag 接口立即生效。
- 预防：
  - 含中文的 JSON/脚本禁止走 PowerShell 管道进 Python stdin。
  - 正确写法：`@'...'@ | Set-Content -Encoding UTF8 file.json`（PowerShell 内存 UTF-16 → UTF-8 文件）或 `apply_patch`。
  - Python 读 PowerShell 写出的文件用 `encoding="utf-8-sig"`（带 BOM）。
  - 发布前自查：`python -c "print(open('publish.json',encoding='utf-8').read()[:60])"` 不应出现 `?`。

## 2. 标签只挂上 3 个 / 出现乱码标签 AI??

- 现象：add/v3 提交 10 个标签，实际只有 3 个挂上，其中一个还是乱码 `AI??`。
- 根因：同 #1，标签名中的中文在生成 config 时已变 `?`，非法标签被 B 站静默丢弃。
- 修正：`x/tag/archive/add|del` 用 web Cookie 返回 `-403 访问权限不足`，不要用；正确方式是重发 `edit/v3` 并完整重传 `tag` 字段。
- 预防：config 里标签写正确 UTF-8，发布后复查 `GET https://api.bilibili.com/x/tag/archive/tags?bvid=`，应等于提交数量（≤10）。

## 3. 克隆参考音频报 speaker encoder Expand 错误

- 现象：`character_voice.py save` 提取音色时，ONNX 报 `Non-zero status code ... /speaker_encoder/asp/Expand ... invalid expand shape`。
- 根因：`qwen3_tts_speaker_encoder.fp16.onnx` 输入 mel 序列超过约 30 秒音频就失败（41s 失败、30s 成功），与 onnxruntime 版本无关。
- 修正：先用 faster-whisper 转写拿到逐句时间轴，再用 ffmpeg 裁剪 ≤30s 的干净片段，最后用与片段匹配的文本 `character_voice.py save`。
- 预防：参考音频一律先裁剪到 ≤30s；能拿到逐句时间轴就选语音干净、无 BGM 的片段。

## 4. TTS 引擎用 python -（stdin）运行直接崩

- 现象：`@'...'@ | python -` 跑引擎，spawn 子进程报 `OSError: ... '<stdin>'`，随后「解码器超时」，`engine.create_stream()` 返回 None。
- 根因：引擎用 multiprocessing spawn 起解码器子进程，子进程需要重载 `__main__`，stdin 方式没有可重载的脚本文件。
- 修正：TTS 一律写成脚本文件 `python gen_tts_clone.py`，`__main__` 里调用 `multiprocessing.freeze_support()`。
- 预防：所有 TTS 相关脚本保存为 `.py` 文件运行；不要在命令行内联跑引擎。

## 5. loudnorm 后音轨采样率变成 96kHz

- 现象：`final_loud.mp4` 的 AAC 采样率为 96000 Hz，不符合 B 站 44.1kHz 规范。
- 根因：assemble_video.py 的 loudnorm 命令未指定 `-ar`，ffmpeg 默认按输出容器选了高采样率。
- 修正：`ffmpeg -y -i final.mp4 -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:v copy -c:a aac -b:a 192k -ar 44100 -movflags +faststart final_loud.mp4`。
- 预防：loudnorm 步骤显式加 `-ar 44100`，发布前用 ffprobe 复核 `sample_rate=44100`。
- 2026-08-07 复核：`assemble_video.py` 已内置 `-ar 44100`；顺带修复段尾白（去掉 `-shortest`，让 0.35s 尾白真正生效）与首尾淡出时序（按成片实际时长 `total` 计算，不再落在视频结束点之后）。

## 6. 发布后 view 接口返回 -404

- 现象：`verify_published.py` 刚发布就跑，返回 `-404 啥都木有`。
- 根因：稿件处于审核队列（`is_pubing`），`view` 接口还没公开。
- 修正：等约 2 分钟后重试；用 `state=0`（公开）、`playurl` 有 durl、创作中心 `arc_audits` 无 reject_reason 作为通过标准。
- 预防：发布脚本成功后 sleep 120s 再验证。

## 7. 技能脚本与 segments 格式不匹配

- 现象：`gen_slides.py`/`assemble_video.py` 报错或遍历到字符串。
- 根因：文案写成 `{"segments":[...]}`，而脚本直接迭代 JSON 顶层（要求数组）。
- 修正：另存 `segments_array.json`（裸数组）传给技能脚本。
- 预防：segments 一律存为顶层数组；或脚本侧兼容 `data.get("segments", data)`。

## 8. PowerShell Set-Content 带 BOM 导致 Python json.load 报错

- 现象：`json.load(open(p, encoding="utf-8"))` 报 `Unexpected UTF-8 BOM`。
- 根因：PowerShell `Set-Content -Encoding UTF8` 输出带 BOM。
- 修正：Python 读取用 `encoding="utf-8-sig"`，或先用 Python 重写为无 BOM UTF-8。
- 预防：读 PowerShell 生成的文件统一 `utf-8-sig`；写回用 Python `json.dump(..., ensure_ascii=False)`。

## 9. quick_validate.py 在中文 Windows 上 GBK 读 SKILL.md 直接崩 / SKILL.md 带 BOM 校验失败

- 现象：`python quick_validate.py <skill>` 报 `UnicodeDecodeError: 'gbk' codec can't decode`；SKILL.md 开头有 BOM 时返回 `No YAML frontmatter found`。
- 根因：`skill-creator` 的 `quick_validate.py`/`generate_openai_yaml.py`/`init_skill.py` 用 `Path.read_text()/write_text()` 默认编码（中文 Windows = GBK）读写 UTF-8 文件；PowerShell 写出的 SKILL.md 带 BOM 导致 `startswith("---")` 失败。
- 修正：这三个脚本统一加 `encoding="utf-8"`；SKILL.md 及所有 UTF-8 文本文件去 BOM（.ps1 例外：PowerShell 5.1 必须保留 BOM 才能正确解析中文）。
- 预防：技能文件一律 UTF-8 无 BOM；校验工具读文件显式指定 `encoding="utf-8"`，不要依赖系统默认编码。
