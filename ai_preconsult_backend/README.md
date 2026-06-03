# AI 预问诊系统

DeepSeek 驱动的智能预问诊后端，患者在候诊时通过对话完成症状采集、风险评估和科室推荐，医生接诊前即可查看结构化摘要。

## 功能

- **三条预问诊路径** — 发热/咳嗽/咽痛、腹痛、头痛，LLM 自动识别主诉并切换路径
- **Function Calling 字段抽取** — DeepSeek 从自然语言中提取结构化医学字段，Schema 约束类型和合法值
- **LLM 动态追问** — 根据已采集信息生成上下文感知的自然追问，不再机械填表
- **医生摘要生成** — 会话完成后自动生成结构化摘要供接诊医生快速查阅
- **规则引擎风险分诊** — 18 条红旗规则 + 11 条黄旗规则 + 科室推荐
- **不确定字段确认** — LLM 标记的模糊数值自动触发确认追问
- **追问重试上限** — 同一字段最多问 3 次，超时自动跳过防止死循环

## 技术栈

| 层级 | 技术 |
|---|---|
| 框架 | FastAPI + Uvicorn |
| 数据库 | SQLite（版本化状态快照） |
| AI | DeepSeek API（OpenAI 兼容 `/v1/chat/completions`） |
| 前端 | Vue 3 + Vite |
| 语言 | Python 3.11+ |

## 项目结构

```
ai_preconsult_backend/
├── app/
│   ├── agents/           # 3 个 LLM Agent（抽取/追问/摘要）
│   ├── api/              # FastAPI 路由（5 个端点）
│   ├── configs/          # JSON 配置文件
│   │   ├── dictionaries/ # 关键词字典（LLM 兜底）
│   │   ├── paths/        # 路径定义（必填字段 + 优先级）
│   │   ├── prompts/      # Prompt 管理
│   │   ├── rules/        # 红旗/黄旗/科室规则
│   │   └── templates/    # 追问和报告模板
│   ├── core/             # 配置加载 + 环境变量
│   ├── db/               # SQLite 持久化
│   ├── engines/          # 规则引擎（条件/风险/分诊）
│   ├── models/           # Pydantic 数据模型
│   ├── services/         # 核心业务编排
│   ├── tests/            # 测试用例
│   └── tools/            # 工具函数（字典/槽位/状态/模板）
├── .env.example          # 环境变量模板
├── pyproject.toml
└── README.md
```

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key
```

### 2. 安装依赖

```bash
pip install fastapi uvicorn pydantic httpx
```

### 3. 启动后端

```bash
cd ai_preconsult_backend
uvicorn ai_preconsult_backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```bash
cd preconsult-web
npm install
npm run dev
```

打开 `http://localhost:3000`

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/preconsult/paths` | 可选路径列表 |
| `POST` | `/api/preconsult/sessions` | 创建会话（可选 path_id/age/gender） |
| `POST` | `/api/preconsult/sessions/{id}/messages` | 发送患者消息 |
| `GET` | `/api/preconsult/sessions/{id}/messages` | 对话记录 |
| `GET` | `/api/preconsult/sessions/{id}/result` | 当前采集结果 |
| `GET` | `/api/preconsult/sessions/{id}/doctor-summary` | 医生摘要 |

## 配置

所有配置通过 `.env` 文件管理：

```env
PRECONSULT_LLM_BASE_URL=https://api.deepseek.com
PRECONSULT_LLM_MODEL=deepseek-chat
PRECONSULT_LLM_API_KEY=sk-your-key-here
PRECONSULT_LLM_TIMEOUT=30
```

## 添加新路径

1. `configs/paths/` — 新建路径 JSON（必填字段 + 优先级）
2. `models/schemas.py` — 添加新 Slot 类
3. `agents/extraction_agent.py` — Function Calling schema 加字段
4. `agents/question_agent.py` — 加字段描述
5. `services/preconsult_service.py` — 注册路径 + 检测逻辑
6. `configs/rules/` — 加红旗/黄旗/科室规则
7. `configs/templates/question_templates.json` — 加追问模板兜底
