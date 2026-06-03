# AI 预问诊与预分诊后端系统

## 需求分析与技术方案

---

# 一、项目定位

## 1. 项目是什么

本项目是一个 **面向人形机器人的 AI 预问诊与预分诊后端系统**。

机器人负责：

- ASR 语音识别
- TTS 语音播报
- 屏幕展示
- 硬件交互
- 把患者文本传给后端
- 播报后端返回的问题和结果

你们后端负责：

- 多轮问诊管理
- 患者症状采集
- 字段抽取
- 结构化 State 管理
- 红旗风险识别
- 红 / 黄 / 绿风险分层
- 推荐科室
- 患者预分诊结果
- 医生结构化摘要
- 多轮对话存储
- 审计和日志

---

## 2. 项目不做什么

系统明确不做：

- AI 诊断
- AI 开药
- 自动处方
- 具体药物剂量
- 治疗方案
- 疾病概率预测
- 替代医生判断
- 自动决定检查项目

---

# 二、核心业务目标

## 1. 患者端目标

患者通过机器人完成预问诊后，能够知道：

- 当前是否存在急症风险
- 是否需要急诊
- 应该优先挂哪个科
- 就医前需要准备什么
- 如何更清楚地向医生描述病情

---

## 2. 医生端目标

医生或导诊人员可以看到：

- 患者主诉
- 现病史
- 阳性症状
- 重要阴性症状
- 既往史
- 过敏史
- 用药史
- 风险等级
- 风险原因
- 推荐科室
- 缺失信息
- 原始问答记录

---

## 3. 系统端目标

后端需要做到：

- 可配置
- 可扩展
- 可追溯
- 低延迟
- 可测试
- 可部署到服务器
- 可被机器人通过 API 调用

---

# 三、一期业务范围

## 1. 一期先做什么

一期建议只做高频呼吸道场景：

- 发热
- 咳嗽
- 咽痛

对应路径：

```
fever_cough_v1
```

---

## 2. 一期推荐科室

一期支持推荐：

- 急诊
- 呼吸内科
- 全科
- 发热门诊
- 儿科，可选

---

## 3. 一期风险等级

| 风险等级 | 含义               | 建议            |
| ---- | ---------------- | ------------- |
| 红色   | 存在急症风险           | 立即联系现场医护或前往急诊 |
| 黄色   | 暂无必须急诊信号，但建议尽快就医 | 尽快线下就医        |
| 绿色   | 当前未发现明显急症风险      | 普通门诊或继续观察     |

---

## 4. 一期暂不做

- 复杂 RAG
- 模型微调
- HIS 深度对接
- 多租户
- 复杂管理后台
- 处方
- 诊断
- 治疗方案

---

# 四、整体业务流程

## 1. 会话开始

流程：

```
机器人开始接待患者  ↓调用后端创建会话接口  ↓后端初始化 session 和 state  ↓返回第一句问题
```

返回示例：

```
{  "session_id": "s_10001",  "status": "created",  "reply": "请问您哪里不舒服？",  "display_text": "请问您哪里不舒服？"}
```

---

## 2. 患者回答

患者说：

```
我发烧三天，还咳嗽嗓子疼
```

机器人 ASR 后传给后端：

```
{  "text": "我发烧三天，还咳嗽嗓子疼",  "asr_confidence": 0.91}
```

后端处理：

```
读取当前 State  ↓红旗关键词预检  ↓LLM 字段抽取  ↓更新 State  ↓风险规则判断  ↓判断继续追问还是结束  ↓返回下一句问题或最终结果
```

返回示例：

```
{  "status": "in_progress",  "reply": "请问最高体温是多少℃？目前有没有呼吸困难、胸痛或咳血？",  "display_text": "请问最高体温是多少℃？目前有没有呼吸困难、胸痛或咳血？",  "quick_replies": ["有", "没有", "不确定"],  "risk_level": "unknown"}
```

---

## 3. 红色风险熔断

如果患者说：

```
胸口疼，喘不上气
```

后端直接命中红色风险。

返回：

```
{  "status": "emergency",  "risk_level": "red",  "reply": "您提到胸痛和呼吸困难，这属于需要尽快处理的风险信号。请立即联系现场医护人员，或前往急诊。",  "display_text": "请立即联系现场医护人员，或前往急诊。",  "recommended_action": "立即联系现场医护或前往急诊",  "recommended_departments": ["急诊"],  "should_stop_dialogue": true}
```

---

## 4. 最终预分诊

当信息采集完成，或达到最大追问轮数后，后端输出最终结果。

示例：

```
{  "status": "completed",  "risk_level": "yellow",  "risk_reasons": [    "发热持续3天",    "伴咳嗽、咽痛等呼吸道症状"  ],  "recommended_action": "建议尽快线下就医",  "recommended_departments": ["呼吸内科", "全科"],  "reply": "目前没有发现必须立即急诊的风险信号。您发热已经三天，并伴有咳嗽和咽痛，建议尽快就医。可以优先选择呼吸内科或全科。",  "patient_report": {    "preparation": [      "请记录体温变化",      "准备已用药名称",      "说明过敏史",      "带上既往检查结果"    ]  },  "doctor_summary_status": "generating"}
```

---

# 五、功能需求

## 1. 会话管理

需要支持：

- 创建会话
- 查询会话
- 恢复会话
- 结束会话
- 标记 emergency
- 标记 completed
- 记录机器人来源
- 记录机器人位置

会话状态：

```
createdin_progresscompletedemergencyabandonederror
```

---

## 2. 文本输入处理

后端接收机器人传来的 ASR 文本。

需要支持：

- 普通症状描述
- 否定表达
- 不确定表达
- ASR 低置信度
- 用户说“不知道”
- 用户回答无关内容
- 用户要求开药
- 用户询问诊断
- 高危症状描述

示例：

```
“没有胸痛，也没有喘”→ chest_pain=false, shortness_of_breath=false“胸口疼，喘不上气”→ chest_pain=true, shortness_of_breath=true“不太确定有没有发烧”→ fever=unknown
```

---

## 3. 主诉识别

需要识别：

- 原始主诉
- 标准化症状
- 持续时间
- 问诊路径 path_id
- 初始红旗候选

示例：

```
{  "chief_complaint": {    "raw_text": "我发烧三天，还咳嗽嗓子疼",    "main_symptoms": ["fever", "cough", "sore_throat"],    "duration_days": 3,    "path_id": "fever_cough_v1"  }}
```

---

## 4. 字段抽取

一期需要抽取：

- 年龄
- 性别
- 是否怀孕
- 发热持续时间
- 最高体温
- 当前体温
- 是否咳嗽
- 咳嗽类型
- 是否有痰
- 痰颜色
- 是否咽痛
- 是否乏力
- 是否头痛
- 是否腹泻
- 是否皮疹
- 是否呼吸困难
- 是否胸痛
- 是否咳血
- 是否意识异常
- 是否抽搐
- 是否嘴唇发紫
- 是否有基础病
- 是否有药物过敏
- 是否已用药
- 用药效果

字段抽取输出示例：

```
{  "extracted_slots": {    "slots.fever.duration_days": 3,    "slots.cough.has_cough": true,    "slots.associated_symptoms.sore_throat": true  },  "uncertain_fields": [],  "raw_evidence": [    {      "field": "slots.fever.duration_days",      "text": "发烧三天"    }  ]}
```

---

## 5. 动态追问

系统根据当前 State 判断缺失字段，并返回下一句追问。

追问原则：

- 红旗字段优先
- 一次最多问 1～2 个问题
- 支持“有 / 没有 / 不确定”
- 最多追问 4～6 轮
- 优先使用模板生成追问
- 不要每轮调用 LLM 生成追问

示例：

```
{  "reply": "请问最高体温是多少℃？目前有没有呼吸困难、胸痛或咳血？",  "quick_replies": ["有", "没有", "不确定"]}
```

---

## 6. 红旗风险识别

一期红旗包括：

- 呼吸困难
- 胸痛或明显胸闷
- 咳血
- 意识异常
- 抽搐
- 嘴唇或面色发紫
- 严重脱水
- 婴幼儿高热伴精神差
- 孕妇腹痛或阴道出血
- 自伤 / 自杀风险

命中后必须：

- 停止普通问诊
- 返回急诊提示
- 推荐急诊
- 记录规则命中
- 生成急诊摘要

---

## 7. 风险分层

### 红色风险

条件：

- 命中任一红旗症状

处理：

- 建议立即联系现场医护或前往急诊
- 停止普通追问

---

### 黄色风险

条件包括：

- 发热 ≥ 3 天
- 最高体温 ≥ 39℃
- 症状持续加重
- 老人
- 儿童
- 孕妇
- 慢性肺病
- 心脏病
- 糖尿病
- 肿瘤
- 免疫低下
- 自行用药后仍反复

处理：

- 建议尽快线下就医
- 推荐对应科室

---

### 绿色风险

条件：

- 无红色风险
- 无黄色风险
- 症状较轻
- 病程较短

处理：

- 普通门诊或继续观察
- 提示症状加重时及时就医

---

## 8. 科室推荐

一期规则：

| 条件           | 推荐科室          |
| ------------ | ------------- |
| 红色风险         | 急诊            |
| 发热 + 咳嗽 / 咽痛 | 呼吸内科 / 全科     |
| 儿童发热         | 儿科 / 全科       |
| 孕妇发热         | 产科 / 全科，严重时急诊 |
| 症状不明确        | 全科            |

输出示例：

```
{  "recommended_departments": ["呼吸内科", "全科"],  "department_reason": "主诉为发热、咳嗽、咽痛等呼吸道相关症状"}
```

---

## 9. 患者预分诊结果

返回适合机器人播报的短文本。

示例：

```
目前没有发现必须立即急诊的风险信号。您发热已经三天，并伴有咳嗽和咽痛，建议尽快就医。可以优先选择呼吸内科或全科。
```

结构化返回：

```
{  "risk_level": "yellow",  "recommended_action": "建议尽快线下就医",  "recommended_departments": ["呼吸内科", "全科"],  "preparation": [    "记录体温变化",    "准备已用药名称",    "说明过敏史"  ]}
```

---

## 10. 医生结构化摘要

医生摘要异步生成。

摘要字段：

```
{  "chief_complaint": "",  "history_of_present_illness": "",  "positive_findings": [],  "negative_findings": [],  "past_history": [],  "allergy_history": [],  "medication_history": [],  "risk_level": "",  "risk_reasons": [],  "recommended_departments": [],  "missing_key_information": [],  "questions_for_doctor_to_confirm": [],  "disclaimer": "本摘要仅供医生接诊前参考，不作为诊断或处方依据。"}
```

---

## 11. 安全拦截

必须拦截：

- 明确诊断
- 具体用药
- 药物剂量
- 治疗方案
- 淡化急症
- 替代医生判断

禁止输出：

```
你可能是肺炎，可以吃阿莫西林。
```

安全改写：

```
我不能为您做诊断或提供处方建议。可以帮您整理症状，并建议由医生进一步判断。
```

---

# 六、非功能需求

## 1. 性能要求

| 场景           | 目标        |
| ------------ | --------- |
| 创建会话         | < 300ms   |
| 红色风险快速返回     | 100～300ms |
| 普通问诊一轮       | 1.5～3.5s  |
| 最终预分诊结果      | 1.5～3s    |
| 医生摘要生成       | 后台 2～6s   |
| 风险规则判断       | < 50ms    |
| Slot Planner | < 30ms    |

---

## 2. 可用性要求

需要支持：

- LLM 超时降级
- 模板兜底
- 会话恢复
- 异常重试
- 失败日志
- 规则本地执行
- 摘要异步生成

LLM 失败兜底示例：

```
我刚才没有完全理解您的回答。请问最高体温是多少℃？有没有呼吸困难、胸痛或咳血？
```

---

## 3. 安全要求

需要支持：

- 机器人调用 token
- HTTPS
- 接口限流
- 请求日志
- 敏感信息脱敏
- Prompt Injection 防护
- 输出安全审核
- 审计日志

---

## 4. 可追溯要求

必须记录：

- 患者原始输入
- ASR 置信度
- 后端返回内容
- 字段抽取结果
- State 变化
- 风险规则命中
- 科室推荐原因
- 医生摘要
- 安全拦截记录
- 模型版本
- Prompt 版本
- 规则版本

---

# 七、技术方案

## 1. 技术栈

推荐：

- Python
- FastAPI
- LangGraph
- Pydantic
- SQLite，本地开发阶段
- Redis，联调阶段缓存 State
- PostgreSQL，试点上线阶段
- Celery / RQ，异步摘要任务
- Docker
- pytest

---

## 2. 当前阶段技术选择

开发阶段：

```
FastAPI + LangGraph + SQLite + 本地 JSON 配置
```

机器人联调阶段：

```
FastAPI + LangGraph + Redis + SQLite
```

试点上线阶段：

```
FastAPI + LangGraph + Redis + PostgreSQL
```

---

## 3. 总体架构

```
机器人 / 其他客户端        ↓FastAPI API 层        ↓LangGraph 工作流层        ↓Preconsult State 状态层        ↓Agent 层        ↓Tool Layer 工具层        ↓Rule Engine / Path Config / Templates        ↓SQLite / Redis / PostgreSQL
```

---

## 4. 后端分层

### API 接入层

负责：

- 创建会话
- 接收患者文本
- 返回下一句追问
- 返回最终结果
- 查询医生摘要
- 接收反馈

---

### LangGraph 工作流层

负责流程编排。

低延迟节点：

```
precheck_red_flagsextract_and_update_staterisk_gatekeeperplan_or_triageresponse_builder
```

---

### Preconsult State 状态层

State 是唯一事实来源。

保存：

- 主诉
- 患者基本信息
- 症状字段
- 红旗字段
- 风险等级
- 规则命中
- 缺失字段
- 对话轮数
- 最终结果
- 医生摘要状态

---

### Agent 层

只保留必要的 LLM Agent：

- Extraction Agent
- Summary Agent
- Safety Agent

每轮对话主要调用 Extraction Agent 一次。

---

### Tool Layer 工具层

包括：

- StateTool
- SlotTool
- PathTool
- RiskTool
- TriageTool
- TemplateTool
- LLMTool
- DictionaryTool
- SafetyTool
- AuditTool

---

### 规则与配置层

包括：

- 问诊路径配置
- 红旗规则
- 黄色风险规则
- 科室推荐规则
- 症状词典
- 追问模板
- 患者结果模板
- 医生摘要 Prompt
- 安全规则

---

### 数据存储层

开发阶段：

```
SQLite本地 JSON 配置
```

联调阶段：

```
Redis 缓存当前 StateSQLite 保存完整 messages
```

上线阶段：

```
Redis 缓存当前 StatePostgreSQL 保存完整数据和审计
```

---

# 八、核心工作流设计

## 1. LangGraph 流程

```
START  ↓precheck_red_flags  ├── emergency_response  └── extract_and_update_state          ↓     risk_gatekeeper          ├── emergency_response          └── plan_or_triage                  ├── inquiry_response                  └── triage_response                          ↓                     summary_async
```

---

## 2. 普通问诊流程

```
机器人传入文本  ↓加载 State  ↓红旗关键词预检  ↓LLM 抽取字段  ↓State 更新  ↓本地风险规则  ↓本地 Slot Planner  ↓模板生成追问  ↓返回机器人
```

原则：

```
每轮最多一次 LLM 调用
```

---

## 3. 红色风险流程

```
机器人传入文本  ↓关键词命中胸痛 / 呼吸困难等  ↓RiskTool 生成红色风险  ↓TemplateTool 生成急诊提示  ↓返回机器人
```

原则：

```
0 次 LLM 调用
```

---

## 4. 最终收口流程

```
字段采集完成或达到最大轮数  ↓RiskTool 最终分层  ↓TriageTool 推荐科室  ↓TemplateTool 生成患者报告  ↓返回机器人  ↓Celery 异步生成医生摘要
```

---

# 九、API 设计

## 1. 创建会话

```
POST /api/preconsult/sessions
```

请求：

```
{  "source": "robot",  "robot_id": "robot_001",  "location": "门诊大厅"}
```

响应：

```
{  "session_id": "s_10001",  "status": "created",  "reply": "请问您哪里不舒服？",  "display_text": "请问您哪里不舒服？"}
```

---

## 2. 发送患者文本

```
POST /api/preconsult/sessions/{session_id}/messages
```

请求：

```
{  "text": "我发烧三天，还咳嗽嗓子疼",  "asr_confidence": 0.91}
```

响应：

```
{  "session_id": "s_10001",  "status": "in_progress",  "reply": "请问最高体温是多少℃？目前有没有呼吸困难、胸痛或咳血？",  "display_text": "请问最高体温是多少℃？目前有没有呼吸困难、胸痛或咳血？",  "quick_replies": ["有", "没有", "不确定"],  "risk_level": "unknown",  "recommended_departments": [],  "should_stop_dialogue": false}
```

---

## 3. 急诊风险响应

```
{  "session_id": "s_10001",  "status": "emergency",  "risk_level": "red",  "reply": "您提到胸痛和呼吸困难，这属于需要尽快处理的风险信号。请立即联系现场医护人员，或前往急诊。",  "display_text": "请立即联系现场医护人员，或前往急诊。",  "recommended_action": "立即联系现场医护或前往急诊",  "recommended_departments": ["急诊"],  "should_stop_dialogue": true}
```

---

## 4. 获取最终结果

```
GET /api/preconsult/sessions/{session_id}/result
```

响应：

```
{  "session_id": "s_10001",  "status": "completed",  "risk_level": "yellow",  "risk_reasons": [    "发热持续3天",    "伴咳嗽、咽痛等呼吸道症状"  ],  "recommended_action": "建议尽快线下就医",  "recommended_departments": ["呼吸内科", "全科"],  "patient_report": {    "message": "目前没有发现必须立即急诊的风险信号。您发热已经三天，并伴有咳嗽和咽痛，建议尽快就医。",    "preparation": [      "请记录体温变化",      "准备已用药名称",      "说明过敏史"    ]  },  "doctor_summary_status": "ready"}
```

---

## 5. 获取医生摘要

```
GET /api/preconsult/sessions/{session_id}/doctor-summary
```

响应：

```
{  "chief_complaint": "发热伴咳嗽、咽痛3天",  "history_of_present_illness": "患者自述发热3天，最高体温38.8℃，伴咳嗽、咽痛。否认胸痛、呼吸困难、咳血、意识异常等急症风险表现。",  "positive_findings": ["发热3天", "咳嗽", "咽痛"],  "negative_findings": ["无胸痛", "无呼吸困难", "无咳血"],  "risk_level": "yellow",  "risk_reasons": ["发热持续3天", "伴呼吸道症状"],  "recommended_departments": ["呼吸内科", "全科"],  "missing_key_information": ["当前体温未提供"],  "disclaimer": "本摘要仅供医生接诊前参考，不作为诊断或处方依据。"}
```

---

# 十、多轮对话存储方案

## 1. 当前阶段

建议使用：

```
SQLite 保存完整多轮对话SQLite 保存完整 StateRedis 暂时可不用
```

---

## 2. 机器人联调阶段

建议使用：

```
Redis 保存当前 StateSQLite 保存完整 messages
```

---

## 3. 上线阶段

建议使用：

```
Redis 保存当前 StatePostgreSQL 保存完整 messages、state、rule hits、summary、audit logs
```

---

## 4. 多轮消息表

```
CREATE TABLE preconsult_messages (  id INTEGER PRIMARY KEY AUTOINCREMENT,  session_code TEXT NOT NULL,  turn_index INTEGER NOT NULL,  role TEXT NOT NULL,  message_text TEXT NOT NULL,  asr_confidence REAL,  question_key TEXT,  extracted_slots TEXT,  risk_level_at_time TEXT,  created_at TEXT);
```

一轮通常存两条：

```
patient messageassistant / robot reply message
```

---

## 5. State 表

```
CREATE TABLE preconsult_states (  id INTEGER PRIMARY KEY AUTOINCREMENT,  session_code TEXT NOT NULL,  state_json TEXT NOT NULL,  version INTEGER DEFAULT 1,  created_at TEXT,  updated_at TEXT);
```

---

## 6. 风险命中表

```
CREATE TABLE risk_rule_hits (  id INTEGER PRIMARY KEY AUTOINCREMENT,  session_code TEXT NOT NULL,  rule_id TEXT,  rule_name TEXT,  trigger_field TEXT,  trigger_value TEXT,  risk_level TEXT,  reason TEXT,  created_at TEXT);
```

---

## 7. 医生摘要表

```
CREATE TABLE doctor_summaries (  id INTEGER PRIMARY KEY AUTOINCREMENT,  session_code TEXT NOT NULL,  summary_json TEXT NOT NULL,  created_at TEXT);
```

---

# 十一、Preconsult State 设计

```
{  "session_id": "s_10001",  "status": "in_progress",  "source": "robot",  "robot_context": {    "robot_id": "robot_001",    "location": "门诊大厅"  },  "path_id": "fever_cough_v1",  "chief_complaint": {    "raw_text": "我发烧三天，还咳嗽嗓子疼",    "main_symptoms": ["fever", "cough", "sore_throat"],    "duration_days": 3  },  "patient_basic_info": {    "age": null,    "gender": null,    "pregnancy_status": null  },  "slots": {    "fever": {      "duration_days": 3,      "max_temperature_c": null    },    "cough": {      "has_cough": true,      "cough_type": null    },    "red_flags": {      "shortness_of_breath": null,      "chest_pain": null,      "hemoptysis": null,      "confusion": null    },    "past_history": {},    "allergy_history": {},    "medication_history": {}  },  "risk": {    "current_level": "unknown",    "rule_hits": []  },  "dialogue": {    "turn_count": 1,    "max_turns": 5,    "missing_required_slots": []  }}
```

---

# 十二、规则配置设计

## 1. 红旗规则

```
{  "rule_id": "RED_DYSPNEA",  "name": "呼吸困难",  "condition": {    "field": "slots.red_flags.shortness_of_breath",    "operator": "equals",    "value": true  },  "risk_level": "red",  "reason": "存在呼吸困难",  "should_stop_dialogue": true}
```

---

## 2. 黄色规则

```
{  "rule_id": "YELLOW_FEVER_3_DAYS",  "name": "发热持续3天及以上",  "condition": {    "field": "slots.fever.duration_days",    "operator": ">=",    "value": 3  },  "risk_level": "yellow",  "reason": "发热持续3天及以上"}
```

---

## 3. 科室规则

```
{  "rule_id": "DEPT_FEVER_COUGH",  "condition": {    "field": "chief_complaint.main_symptoms",    "operator": "contains_any",    "value": ["fever", "cough", "sore_throat"]  },  "departments": ["呼吸内科", "全科"],  "reason": "主诉为发热、咳嗽、咽痛等呼吸道相关症状"}
```

---

# 十三、项目目录结构

```
ai_preconsult_backend/├── app/│   ├── main.py│   ├── api/│   │   ├── sessions.py│   │   ├── messages.py│   │   ├── results.py│   │   └── doctor.py│   ├── graph/│   │   ├── state.py│   │   ├── nodes.py│   │   ├── routes.py│   │   └── build_graph.py│   ├── agents/│   │   ├── extraction_agent.py│   │   ├── summary_agent.py│   │   └── safety_agent.py│   ├── tools/│   │   ├── state_tool.py│   │   ├── slot_tool.py│   │   ├── path_tool.py│   │   ├── risk_tool.py│   │   ├── triage_tool.py│   │   ├── template_tool.py│   │   ├── llm_tool.py│   │   ├── dictionary_tool.py│   │   ├── safety_tool.py│   │   └── audit_tool.py│   ├── engines/│   │   ├── rule_engine.py│   │   ├── risk_engine.py│   │   └── triage_engine.py│   ├── configs/│   │   ├── paths/│   │   │   └── fever_cough_v1.json│   │   ├── rules/│   │   │   ├── red_flags.json│   │   │   ├── yellow_flags.json│   │   │   └── department_rules.json│   │   ├── dictionaries/│   │   │   └── symptom_dictionary.json│   │   └── templates/│   │       ├── question_templates.json│   │       └── patient_report_templates.json│   ├── prompts/│   │   ├── extraction.txt│   │   ├── summary.txt│   │   └── safety.txt│   ├── db/│   │   ├── models.py│   │   ├── session.py│   │   └── migrations/│   └── tests/│       ├── test_risk_engine.py│       ├── test_triage_engine.py│       ├── test_graph_flow.py│       └── test_api_messages.py├── Dockerfile├── docker-compose.yml├── pyproject.toml└── README.md
```

---

# 十四、测试需求

必须建立测试病例库，覆盖：

- 普通咳嗽
- 发热 1 天
- 发热 3 天
- 最高体温 39℃
- 胸痛
- 呼吸困难
- 咳血
- 意识异常
- 儿童高热
- 孕妇发热
- 老人发热
- 糖尿病患者发热
- 用户问吃什么药
- 用户问是不是肺炎
- 用户说不知道
- ASR 置信度低

---

## 验收指标

| 指标             | 目标        |
| -------------- | --------- |
| 红色风险漏识别率       | ≤ 2%      |
| 诊断越界率          | 0         |
| 处方越界率          | 0         |
| 普通单轮响应         | 1.5～3.5s  |
| 红色风险响应         | 100～300ms |
| LLM JSON 解析失败率 | ≤ 3%      |
| 科室推荐合理率        | ≥ 85%     |
| 医生摘要可用率        | ≥ 80%     |

---

# 十五、部署方案

## 1. 开发阶段

```
FastAPI + LangGraph + SQLite + 本地 JSON 配置
```

---

## 2. 机器人联调阶段

```
FastAPI + LangGraph + Redis + SQLite
```

---

## 3. 试点上线阶段

```
FastAPI + LangGraph + Redis + PostgreSQL + Celery + Nginx
```

---

## 4. Docker Compose 服务

包括：

- FastAPI app
- SQLite / PostgreSQL
- Redis
- Celery worker，可选
- Nginx，可选

---

# 十六、第一阶段交付清单

第一阶段需要交付：

- FastAPI 后端服务
- 创建会话接口
- 发送患者文本接口
- 查询结果接口
- 查询医生摘要接口
- LangGraph 低延迟工作流
- Preconsult State
- 发热 / 咳嗽 / 咽痛路径
- 红旗关键词预检
- LLM 字段抽取
- Risk Engine
- Triage Engine
- 追问模板
- 患者预分诊结果
- 医生摘要异步生成
- SQLite 本地存储
- 基础多轮对话存储
- 基础审计日志
- 测试病例库
- Docker 部署

---

# 十七、后期扩展方式

后期不要重写系统，而是新增症状路径配置。

新增一个病症路径时，新增：

- path_schema
- slot_schema
- red_flag_rules
- yellow_rules
- department_rules
- question_templates
- summary_template
- 测试病例

例如后续可扩展：

```
dizziness_v1abdominal_pain_v1rash_v1chest_pain_v1headache_v1diarrhea_vomiting_v1
```

核心流程不变：

```
患者主诉  ↓识别症状路径  ↓加载对应配置  ↓动态追问  ↓风险判断  ↓科室推荐  ↓医生摘要
```

---

# 十八、最终总结

本系统是一个 **面向人形机器人的 AI 预问诊后端服务**。

核心架构：

```
FastAPI+ LangGraph+ Preconsult State+ Extraction Agent+ Tool Layer+ Rule Engine+ SQLite / Redis / PostgreSQL+ Docker
```

核心原则：

- 每轮最多 1 次 LLM
- 红旗风险 0 次 LLM 快速返回
- 风险分层和科室推荐全部规则化
- 追问优先模板生成
- 医生摘要异步生成
- 多轮对话长期存在 messages 表
- 当前结构化状态存在 state 表
- Redis 只做缓存，不做唯一存储
- 所有过程可追溯
- 不诊断、不开药、不替代医生判断
