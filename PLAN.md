# WhisperVideo 开发计划

## 一、项目目标

实现一个独立的 Python Web 项目，支持用户上传 MP3，并生成以下产物：

- Whisper 转写 JSON
- SRT 字幕文件
- 黑底字幕视频 MP4

同时提供一个前端页面，方便用户上传、查看处理状态、预览视频并下载结果。

## 二、第一版范围

### 包含内容

- FastAPI 后端
- 本地任务处理
- MP3 上传
- `mp3 -> json -> srt -> 字幕视频` 流水线
- 静态前端页面
- 本地磁盘保存上传文件和输出文件
- 任务状态轮询接口

### 暂不包含

- 登录认证
- 数据库持久化
- 多用户隔离
- 分布式队列
- 云存储
- WebSocket 实时推送
- 高级字幕样式配置

## 三、技术方案

- 语言：Python
- Web 框架：FastAPI
- 启动方式：Uvicorn
- 语音转写：调用外部 `python -m whisper`
- 视频处理：调用外部 `ffmpeg`
- 文件存储：本地 `workspace/` 目录

## 四、目录规划

```text
whispervideo/
  app/
    main.py
    config.py
    models.py
    jobs.py
    pipeline.py
    utils/
      files.py
      srt.py
    static/
      index.html
      app.css
      app.js
  workspace/
    uploads/
    jobs/
    outputs/
  requirements.txt
  .env.example
  README.md
  PLAN.md
```

## 五、阶段拆分

1. 创建项目脚手架和基础配置
2. 实现后端任务与处理流水线
3. 实现前端上传与状态页面
4. 编写运行说明并检查项目结构

## 六、进度记录

### 2026-03-29

- [x] 创建 `PLAN.md`
- [x] 创建项目脚手架和基础配置
- [x] 实现后端任务与处理流水线
- [x] 实现前端上传与状态页面
- [x] 编写运行说明并检查项目结构

说明：

- 已创建 `app/`、`workspace/`、静态资源、依赖文件、环境变量示例和基础配置模型。
- 已实现上传接口、任务状态接口、后台线程任务、Whisper 转写、SRT 生成、黑底字幕视频生成和产物下载接口。
- 已实现前端上传页、任务轮询、结果下载和视频预览。
- 已补充 `README.md`、`.gitignore`，并完成语法检查；当前机器尚未安装 `fastapi` 和 `uvicorn` 依赖。
- 已增加字幕位置和字幕大小可选参数；用户不填写时自动使用默认值。
- 已增加“纯字幕文本”下载产物，不包含时间戳和编号。

## 七、记录规则

每完成一个阶段：

1. 在本文档中把对应阶段标记为已完成
2. 追加一句简短说明，写清本阶段完成了什么
3. 立即开始下一阶段开发
