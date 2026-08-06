# bilibili-ai-video

「AI 科技测评视频」从零制作到自动发布 B 站的完整可复用技能（Codex Skill）。

- 原创文案与分镜模板（数据须来自官方文档/公告并标注来源）
- Qwen3-TTS 本地配音（逐段生成 + 断点续跑）
- 全息蓝科技风幻灯片与封面生成（1920×1080）
- ffmpeg 自动剪辑成片 + 响度标准化（-16 LUFS，符合 B 站要求）
- 从已登录 B 站客户端提取登录态（CDP，免密码）
- 网页投稿 API 自动上传发布（封面 → 预上传 → 分块上传 → add/v3 提交）
- 发布后自动验证（公开状态 / 播放地址 / 标签 / 审核结果）

## 实战案例

DeepSeek V4 Flash「贾维斯时刻」实测视频（5 分 15 秒，全流程由本技能完成）：

https://www.bilibili.com/video/BV1gSup66E4i

## 目录结构

```
├── skill/bilibili-ai-video/   完整技能源码（可直接复制到 Codex 技能库）
│   ├── SKILL.md               技能主文档
│   ├── agents/openai.yaml     UI 元数据
│   ├── scripts/               全部可执行脚本
│   ├── references/            流程文档 / 投稿接口文档 / 文案模板
│   └── assets/                示例封面与幻灯片
├── docs/                      使用说明书（md + txt）
└── examples/                  实战成品示例（成片、封面、文案包、旁白逐字稿）
```

## 快速开始

```bash
# 1. 配音（Qwen3-TTS 本地模型）
python skill/bilibili-ai-video/scripts/gen_tts.py \
    --segments segments.json --out audio \
    --model-dir "C:\Users\Administrator\Desktop\Qwen3-TTS-Q5"

# 2. 幻灯片与封面
python skill/bilibili-ai-video/scripts/gen_slides.py --segments segments.json --out slides
python skill/bilibili-ai-video/scripts/gen_cover.py --title "贾维斯时刻！" --subtitle "..." --out cover.png

# 3. 剪辑成片（含响度标准化）
python skill/bilibili-ai-video/scripts/assemble_video.py \
    --segments segments.json --meta audio/meta.json \
    --slides slides --audio audio --out . --ffmpeg <ffmpeg.exe>

# 4. 提取 B 站登录态（客户端需以 --remote-debugging-port=9222 启动并登录）
python skill/bilibili-ai-video/scripts/extract_bili_cookies.py --cdp http://127.0.0.1:9222 --out cookies.json

# 5. 上传发布
python skill/bilibili-ai-video/scripts/publish_bilibili.py \
    --video final_loud.mp4 --cover cover.png --cookies cookies.json --config publish.json

# 6. 发布验证
python skill/bilibili-ai-video/scripts/verify_published.py --bvid BVxxxx --cookies cookies.json
```

详细流程与踩坑记录见 `docs/说明书.md` 和 `skill/bilibili-ai-video/references/workflow.md`。

## 环境依赖

- Windows + Python 3.10+
- ffmpeg、微软雅黑字体、Pillow / numpy / requests / websockets
- Qwen3-TTS-Q5 本地语音模型
- 已登录的 B 站客户端（用于提取 Cookie）

## 说明

本仓库内文案、视频、图片均为原创制作；引用数据来自 DeepSeek 官方文档与官方公告。代码与文档可自由使用，引用请注明出处。
