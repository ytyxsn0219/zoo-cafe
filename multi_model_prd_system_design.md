# 多模型协同讨论生成 PRD 系统 — 技术方案

## 一、核心设计理念

| 理念 | 说明 |
|------|------|
| **通用化 (General-Purpose Agents)** | 每个 Agent 都是通用智能体，可根据需要扮演任何角色（PM、架构师、评审员等） |
| **协作式 (Collaborative Discussion)** | 所有 Agent 参与每个阶段，各自提出方案 → 相互评审 → 修改完善 → 达成共识 |
| **可配置 (Configurable)** | Agent 数量、使用的模型均可配置，灵活调整参与规模和成本 |
| **主持人引导 (Moderator-Guided)** | 设立主持人 Agent，引导讨论节奏、总结进展、推动共识达成 |
| **模型解耦 (Model Agnostic)** | 通过 Model Registry + 配置文件管理模型，新增模型只需改配置，无需改代码 |
| **可观测 (Observable)** | 全流程可追溯、可回放，每轮讨论有日志与指标 |

---

## 二、系统架构

系统分为四层：**交互层、编排层、智能体层、基础设施层**。

```
┌──────────────────────────────────────────────────┐
│                  交互层 (UI)                       │
│         Streamlit / Next.js / FastAPI SSE         │
├──────────────────────────────────────────────────┤
│                 编排层 (Orchestration)             │
│       LangGraph / AutoGen  ─  Discussion Engine   │
├──────────────────────────────────────────────────┤
│                智能体层 (Agent Layer)              │
│  通用 Agent A │ 通用 Agent B │ ...  主持人 Agent    │
│  (可配置数量 N 个，每个可扮演任何角色)              │
├──────────────────────────────────────────────────┤
│              基础设施层 (Infrastructure)           │
│  Model Gateway (LiteLLM) │ Redis │ VectorDB      │
│  Prompt Store │ Logging │ Metrics                 │
└──────────────────────────────────────────────────┘
```

### 2.1 基础设施层

#### Model Gateway（模型网关）

- 使用 **LiteLLM** 或 **OneAPI** 提供统一的 OpenAI 格式接口
- 后端挂载 GPT、Claude、Gemini、DeepSeek 及本地 Llama 模型
- 弹性扩展：配置文件中新增一行即可接入新模型

#### Memory Store（记忆存储）

| 类型 | 技术选型 | 用途 |
|------|---------|------|
| 短期记忆 | Redis | 当前讨论上下文、会话状态 |
| 长期记忆 | ChromaDB / Milvus | 存储历史 PRD，支持 RAG 检索参考 |

#### Prompt Store（提示词管理）

- Prompt 模板统一存放于 `prompts/` 目录下的 YAML 文件
- 支持版本管理（配合 Git）和 A/B 测试
- 运行时通过 Jinja2 渲染变量

### 2.2 智能体层

#### 通用 Agent (Universal Agent)

每个 Agent 都是通用智能体，可扮演以下任何角色：

| 角色 | 说明 | 使用场景 |
|------|------|---------|
| 需求分析师 | 挖掘用户需求、提出澄清问题 | 需求澄清阶段 |
| 产品经理 | 功能拆解、用户流程设计、PRD撰写 | 所有阶段 |
| 架构师 | 技术可行性评估、数据结构设计 | 所有阶段 |
| 评审员 | 寻找逻辑漏洞、边缘情况、挑战假设 | 所有阶段 |
| 撰写者 | 整合讨论结果、输出标准格式文档 | 文档生成阶段 |

#### 主持人 Agent (Moderator)

| 属性 | 说明 |
|------|------|
| 角色 | 讨论主持人，不参与方案提出，只负责流程引导 |
| 推荐模型 | GPT-4o-mini（低成本、稳定） |
| 职责 | 1. 启动讨论，明确阶段目标 2. 邀请 Agent 提出方案 3. 总结各方观点 4. 引导评审环节 5. 判断是否达成共识 6. 宣布讨论结束或进入下一轮 |

#### Agent 配置示例

```yaml
agents:
  - name: "agent_01"
    model_ref: "gpt4o_model"          # 可配置不同模型
    display_name: "Agent 01"
    description: "通用智能体"

  - name: "agent_02"
    model_ref: "claude35_model"        # 可配置不同模型
    display_name: "Agent 02"
    description: "通用智能体"

  - name: "agent_03"
    model_ref: "deepseek_model"        # 可配置不同模型
    display_name: "Agent 03"
    description: "通用智能体"

  - name: "moderator"
    model_ref: "cheap_model"           # 使用便宜模型
    display_name: "主持人"
    description: "讨论主持人"
    is_moderator: true
```

### 2.3 编排层

基于 **LangGraph** 构建有向图式工作流，采用统一的协作讨论模式。

#### 协作讨论模式 (Collaborative Discussion Mode)

每个阶段都遵循以下标准流程：

```
┌─────────────────────────────────────────────────────────┐
│                    讨论阶段开始                       │
│         主持人明确当前阶段目标和任务范围                 │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  第1轮：提出方案                        │
│     所有 Agent 依次提出各自的解决方案/观点              │
│     主持人确保每个 Agent 都有机会发言                   │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  第2-N轮：评审修改                     │
│     Agent 之间相互评审、提出改进意见                   │
│     原提案者根据反馈修改完善自己的方案                 │
│     可能有多轮评审-修改循环                            │
└────────────────────┬────────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  共识判定                             │
│     主持人判断各方是否达成一致意见                     │
│     达成共识 → 进入下一阶段                            │
│     未达成共识 → 继续评审修改或主持人总结后强制推进     │
└─────────────────────────────────────────────────────────┘
```

#### 讨论终止条件

| 条件 | 说明 |
|------|------|
| 达成共识 | 主持人判定各方观点已趋同，无明显分歧 |
| 达到最大轮数 | 超过配置的 max_rounds 限制 |
| Token 超限 | 触发上下文压缩后继续，无法继续则提前终止 |

### 2.4 交互层

- **后端**：FastAPI，通过 SSE (Server-Sent Events) 实时推送讨论进度
- **前端**：Streamlit（MVP）或 Next.js（正式版），群聊式界面展示多 Agent 对话

---

## 三、业务流程

```
用户输入需求
    │
    ▼
┌─────────────────────────┐
│ 阶段1: 需求澄清          │  所有 Agent + 主持人
│ - 主持人发起讨论           │  max_turns=5
│ - 各 Agent 提出澄清问题    │  协作模式
│ - 相互评审问题质量         │
│ - 达成共识: 需求清洗单     │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 阶段2: 功能设计          │  所有 Agent + 主持人
│ - 各 Agent 提出功能列表   │  max_turns=10
│ - 相互评审和优化功能       │  协作模式
│ - 评估技术可行性          │
│ - 达成共识: 核心功能列表   │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 阶段3: PRD撰写评审       │  所有 Agent + 主持人
│ - 各 Agent 撰写PRD草稿    │  max_turns=10
│ - 相互评审和完善PRD        │  协作模式
│ - 聚焦逻辑漏洞和细节      │
│ - 达成共识: 最终PRD草稿    │
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 阶段4: 文档生成          │  主持人引导 + 某Agent
│ - 主持人指定某Agent整合   │  单次生成
│ - 输出标准格式PRD        │
│ - 支持 Markdown/PDF     │
└─────────────────────────┘
```

### 阶段 1：需求澄清

1. 用户输入一句话需求（如："我想做一个给宠物用的外卖 App"）
2. 主持人发起讨论："请各位根据用户需求，提出需要澄清的关键问题"
3. 各 Agent 依次提出 3-5 个关键问题（目标用户？盈利模式？核心差异点？MVP 范围？）
4. Agent 之间相互评审：问题是否切中要害？是否重复？是否有遗漏？
5. 各 Agent 根据反馈优化自己的问题列表
6. 主持人总结：整合所有优质问题，生成《需求澄清问卷》
7. 用户回答后，所有 Agent 基于用户回答生成《需求清洗单》，并相互评审、合并
8. **输出**：结构化的需求清洗单（JSON）

### 阶段 2：功能设计

- **输入**：需求清洗单
- **参与者**：所有 Agent + 主持人
- **过程**：
  1. 主持人发起讨论："请各位基于需求清洗单，提出核心功能列表"
  2. 各 Agent 依次提出自己的功能方案，包含功能名称、优先级、描述
  3. Agent 之间相互评审：
     - 功能是否覆盖了需求？
     - 优先级是否合理？
     - 是否存在遗漏或冗余？
     - 技术可行性如何？
  4. 原提案者根据反馈修改完善
  5. 多轮迭代后，主持人总结共识功能列表
- **输出**：包含功能编号、名称、优先级、描述的共识功能列表
- **终止条件**：达成共识 或 达到 `max_turns=10`

### 阶段 3：PRD 撰写评审

- **输入**：共识功能列表
- **参与者**：所有 Agent + 主持人
- **过程**：
  1. 主持人分配任务："请各位分别撰写 PRD 草稿的不同模块"
  2. 各 Agent 撰写各自负责的模块：
     - 背景与目标
     - 功能详述（User Story、流程、验收标准）
     - 非功能需求
     - 技术要点
  3. Agent 之间相互评审：
     - 逻辑是否自洽？
     - 流程是否完整？
     - 异常处理是否到位？
     - 字段定义是否清晰？
  4. 原撰写者根据评审意见修改
  5. 主持人整合各模块，生成完整 PRD 草稿
- **输出**：完整的 PRD 草稿
- **终止条件**：达成共识 或 达到 `max_turns=10`

### 阶段 4：文档生成

- **输入**：PRD 草稿 + 所有讨论记录
- **过程**：
  1. 主持人指定一个 Agent 作为"文档撰写者"
  2. 该 Agent 将 PRD 草稿标准化为最终输出格式：
     - 添加文档元信息（版本、日期等）
     - 确保格式统一
     - 生成目录
  3. 其他 Agent 可对文档格式提出最终建议
- **输出**：标准格式 PRD 文档（Markdown / PDF）

---

## 四、工程约束

### 4.1 项目结构

```
multi-model-prd/
├── config/
│   ├── models.yaml              # 模型配置（弹性扩展入口）
│   ├── agents.yaml              # Agent 角色与 Prompt 映射
│   └── settings.yaml            # 全局配置（max_turns、超时等）
├── prompts/
│   ├── universal_agent.yaml      # 通用 Agent 的 Prompt 模板
│   ├── moderator.yaml           # 主持人 Agent 的 Prompt 模板
│   ├── stage_elicitation.yaml   # 阶段1：需求澄清的阶段指令
│   ├── stage_design.yaml        # 阶段2：功能设计的阶段指令
│   ├── stage_writing.yaml       # 阶段3：PRD撰写的阶段指令
│   ├── stage_finalizing.yaml    # 阶段4：文档生成的阶段指令
│   └── summarizer.yaml         # 上下文压缩的 Prompt 模板
├── src/
│   ├── __init__.py
│   ├── main.py                  # 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py            # FastAPI 路由
│   │   └── schemas.py           # Pydantic 请求/响应模型
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py              # Agent 基类
│   │   ├── registry.py          # Agent 注册与工厂
│   │   └── roles/               # 各角色实现（如需自定义逻辑）
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── engine.py            # 讨论引擎（DiscussionRoom）
│   │   ├── workflow.py          # LangGraph 工作流定义
│   │   ├── consensus.py         # 共识判定逻辑
│   │   └── summarizer.py       # 上下文压缩
│   ├── models/
│   │   ├── __init__.py
│   │   ├── gateway.py           # LiteLLM 封装
│   │   └── registry.py          # 模型注册表，从 config 加载
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py        # Redis 短期记忆
│   │   └── long_term.py         # VectorDB 长期记忆 (RAG)
│   ├── output/
│   │   ├── __init__.py
│   │   ├── markdown.py          # Markdown 渲染
│   │   └── pdf.py               # PDF 导出
│   └── utils/
│       ├── __init__.py
│       ├── prompt_loader.py     # Prompt 模板加载与渲染
│       ├── logger.py            # 结构化日志
│       └── token_counter.py     # Token 计数工具
├── tests/
│   ├── test_agents.py
│   ├── test_engine.py
│   ├── test_gateway.py
│   └── test_workflow.py
├── docs/                        # 仅在需要时添加
├── pyproject.toml               # 项目元数据 + 依赖
├── Dockerfile
├── docker-compose.yaml          # Redis + VectorDB + App
└── .env.example                 # 环境变量模板
```

### 4.2 编码规范

| 约束项 | 要求 |
|--------|------|
| Python 版本 | >= 3.11 |
| 类型标注 | 所有公开函数和返回值必须有类型标注 |
| 数据校验 | 使用 Pydantic v2 做输入输出校验 |
| 异步模型 | API 层和模型调用全部使用 async/await |
| 代码风格 | Ruff 格式化 + Ruff lint，CI 中强制检查 |
| Import 规范 | 所有 import 放在文件头部，isort 排序 |
| 日志规范 | 使用 structlog，禁止裸 print |
| 错误处理 | 禁止裸 except，必须指定异常类型 |

### 4.3 配置管理约束

#### models.yaml 规范

```yaml
models:
  - name: "gpt4o_model"          # 唯一标识
    provider: "openai"
    model: "gpt-4o"
    description: "OpenAI GPT-4o"
    config:
      temperature: 0.7
      max_tokens: 4096
      timeout: 60
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "claude35_model"        # 唯一标识
    provider: "anthropic"
    model: "claude-3-5-sonnet-20241022"
    description: "Anthropic Claude 3.5 Sonnet"
    config:
      temperature: 0.5
      max_tokens: 8192
      timeout: 90
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "deepseek_model"
    provider: "deepseek"
    model: "deepseek-reasoner"
    description: "DeepSeek Reasoner"
    config:
      temperature: 0.5
      max_tokens: 4096
      timeout: 120
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "cheap_model"           # 用于主持人和简单任务
    provider: "openai"
    model: "gpt-4o-mini"
    description: "OpenAI GPT-4o-mini (低成本)"
    config:
      temperature: 0.3
      max_tokens: 2000
      timeout: 30
      retry:
        max_attempts: 2
        backoff_factor: 1
```

#### agents.yaml 规范

```yaml
agents:
  - name: "agent_01"
    model_ref: "gpt4o_model"       # 引用 models.yaml 中的 name
    display_name: "Agent 01"
    description: "通用智能体 01"
    enabled: true

  - name: "agent_02"
    model_ref: "claude35_model"
    display_name: "Agent 02"
    description: "通用智能体 02"
    enabled: true

  - name: "agent_03"
    model_ref: "deepseek_model"
    display_name: "Agent 03"
    description: "通用智能体 03"
    enabled: true

  # 可继续添加更多 Agent...

  - name: "moderator"
    model_ref: "cheap_model"      # 使用低成本模型
    display_name: "主持人"
    description: "讨论主持人"
    is_moderator: true
    enabled: true
```

#### settings.yaml 规范

```yaml
discussion:
  max_turns_per_stage:
    elicitation: 5                # 需求澄清最多 5 轮
    design: 10                    # 功能设计最多 10 轮
    writing: 10                   # PRD撰写最多 10 轮
    finalizing: 1                 # 文档生成 1 轮
  consensus_threshold: 0.8        # 共识判定阈值（0-1）
  context_compression:
    enabled: true
    trigger_after_turns: 5        # 每 5 轮触发一次上下文压缩
    max_context_tokens: 100000    # 上下文 token 上限

memory:
  redis:
    url: "${REDIS_URL}"
    ttl: 86400                    # 短期记忆 24 小时过期
  vector_db:
    provider: "chroma"            # chroma / milvus
    collection: "prd_history"
    embedding_model: "text-embedding-3-small"

output:
  default_format: "markdown"
  supported_formats:
    - "markdown"
    - "pdf"
  template_dir: "prompts/"
```

### 4.4 接口规范

#### API 路由设计

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sessions` | 创建新的 PRD 生成会话 |
| GET | `/api/v1/sessions/{id}` | 获取会话状态与进度 |
| POST | `/api/v1/sessions/{id}/messages` | 用户在会话中发送消息 |
| GET | `/api/v1/sessions/{id}/stream` | SSE 流式获取讨论过程 |
| GET | `/api/v1/sessions/{id}/output` | 获取最终 PRD 文档 |
| GET | `/api/v1/sessions/{id}/output?format=pdf` | 导出 PDF |
| GET | `/api/v1/health` | 健康检查 |

#### 核心数据模型 (Pydantic)

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class SessionStatus(str, Enum):
    CREATED = "created"
    ELICITATION = "elicitation"
    BRAINSTORMING = "brainstorming"
    CRITIQUING = "critiquing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentMessage(BaseModel):
    agent_name: str
    agent_role: str
    content: str
    model_used: str
    stage: str
    round_num: int
    token_usage: int
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionCreate(BaseModel):
    initial_requirement: str = Field(..., min_length=5, max_length=5000)
    preferred_output_format: str = Field(default="markdown")


class SessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    current_stage: str
    messages: list[AgentMessage]
    created_at: datetime
    updated_at: datetime


class PRDOutput(BaseModel):
    session_id: str
    title: str
    content: str                    # Markdown 格式正文
    format: str
    total_tokens_used: int
    total_rounds: int
    generated_at: datetime
```

### 4.5 错误处理约束

| 场景 | 策略 |
|------|------|
| 单个模型调用超时 | 按配置重试（指数退避），3 次失败后降级到备选模型 |
| 模型返回空响应 | 记录日志，重新调用一次，仍失败则跳过该 Agent 本轮发言 |
| 上下文超过 Token 限制 | 立即触发 Summarizer Agent 压缩上下文后继续 |
| 讨论无法达成共识 | 超过 max_turns 后由 PM Agent 强制出结论，标记为"未完全共识" |
| Redis 连接失败 | 降级为内存存储，记录告警日志 |
| VectorDB 不可用 | 跳过 RAG 检索，仅基于当前上下文工作 |
| API 请求校验失败 | 返回 422 + 详细字段错误信息 |

### 4.6 可观测性约束

| 维度 | 实现 |
|------|------|
| **日志** | structlog 输出 JSON 格式，包含 session_id、agent_name、stage、round 等字段 |
| **指标** | Prometheus metrics：每个 Agent 的调用延迟、Token 消耗、成功率 |
| **追踪** | OpenTelemetry trace，每次讨论一个 trace，每个 Agent 发言一个 span |
| **回放** | 全量讨论记录持久化到 Redis/DB，支持按 session_id 回放 |

### 4.7 安全约束

| 约束项 | 要求 |
|--------|------|
| API Key | 全部通过环境变量注入，禁止硬编码，`.env` 加入 `.gitignore` |
| 用户输入 | Pydantic 校验 + 长度限制，防止 Prompt 注入 |
| 输出过滤 | 对 Agent 输出做敏感词检测，防止模型幻觉泄露内部信息 |
| 速率限制 | FastAPI 中间件限制每个 IP 的请求频率 |
| CORS | 仅允许白名单域名 |

### 4.8 部署约束

```yaml
# docker-compose.yaml 结构
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - redis
      - chroma
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  redis_data:
  chroma_data:
```

| 约束项 | 要求 |
|--------|------|
| 容器化 | 必须提供 Dockerfile + docker-compose.yaml |
| 环境隔离 | 开发 / 测试 / 生产三套环境配置 |
| 无状态 | App 容器无状态，所有状态存储在 Redis / VectorDB |
| 健康检查 | 必须暴露 `/api/v1/health` 端点 |

---

## 五、关键实现

### 5.1 Agent 基类

```python
from typing import ClassVar
from abc import ABC, abstractmethod
import litellm
from pydantic import BaseModel


class AgentConfig(BaseModel):
    name: str
    role: str
    model_name: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60


class BaseAgent(ABC):
    ROLE: ClassVar[str]

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.history: list[dict[str, str]] = []

    async def speak(self, context: list[dict[str, str]]) -> AgentMessage:
        messages = [
            {"role": "system", "content": self.config.system_prompt}
        ] + context

        response = await litellm.acompletion(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )

        content: str = response.choices[0].message.content
        token_usage: int = response.usage.total_tokens

        return AgentMessage(
            agent_name=self.config.name,
            agent_role=self.config.role,
            content=content,
            model_used=self.config.model_name,
            stage="",       # 由编排层填充
            round_num=0,    # 由编排层填充
            token_usage=token_usage,
        )
```

### 5.2 讨论引擎

```python
import asyncio
from typing import Optional


class DiscussionRoom:
    def __init__(
        self,
        agents: list[BaseAgent],
        max_rounds: int = 5,
        consensus_threshold: float = 0.8,
    ) -> None:
        self.agents = agents
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold
        self.context: list[dict[str, str]] = []
        self.all_messages: list[AgentMessage] = []

    async def start_debate(self, topic: str, stage: str) -> list[AgentMessage]:
        self.context.append({"role": "user", "content": f"讨论主题: {topic}"})

        for round_num in range(1, self.max_rounds + 1):
            for agent in self.agents:
                msg = await agent.speak(self.context)
                msg.stage = stage
                msg.round_num = round_num

                self.context.append({
                    "role": "assistant",
                    "name": agent.config.name,
                    "content": msg.content,
                })
                self.all_messages.append(msg)

                if await self._check_consensus():
                    return self.all_messages

            if self._should_compress_context(round_num):
                await self._compress_context()

        return self.all_messages

    async def _check_consensus(self) -> bool:
        """用轻量模型判断当前讨论是否已达成共识"""
        if len(self.context) < 4:
            return False

        recent = self.context[-6:]
        prompt = (
            "根据以下对话，判断参与者是否已就核心问题达成共识。"
            "返回 0-1 的分数，仅返回数字。\n\n"
            + "\n".join(f"{m.get('name', 'user')}: {m['content']}" for m in recent)
        )
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
        )
        try:
            score = float(response.choices[0].message.content.strip())
            return score >= self.consensus_threshold
        except ValueError:
            return False

    def _should_compress_context(self, round_num: int) -> bool:
        return round_num % 5 == 0

    async def _compress_context(self) -> None:
        """使用 Summarizer 压缩上下文"""
        full_text = "\n".join(
            f"{m.get('name', 'user')}: {m['content']}" for m in self.context
        )
        response = await litellm.acompletion(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"请将以下多轮讨论压缩为关键共识和分歧摘要，保留所有重要决策：\n\n{full_text}",
            }],
            max_tokens=2000,
        )
        summary: str = response.choices[0].message.content
        self.context = [{"role": "system", "content": f"前序讨论摘要：{summary}"}]
```

### 5.3 LangGraph 工作流

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict


class PRDState(TypedDict):
    requirement: str
    clarified_requirement: dict | None
    feature_list: list[str]
    prd_draft: str
    critique_notes: list[str]
    final_prd: str
    status: str


def build_prd_workflow() -> StateGraph:
    graph = StateGraph(PRDState)

    graph.add_node("elicit", elicit_requirements)
    graph.add_node("brainstorm", brainstorm_features)
    graph.add_node("draft", draft_prd)
    graph.add_node("critique", critique_prd)
    graph.add_node("revise", revise_prd)
    graph.add_node("finalize", finalize_document)

    graph.set_entry_point("elicit")
    graph.add_edge("elicit", "brainstorm")
    graph.add_edge("brainstorm", "draft")
    graph.add_edge("draft", "critique")
    graph.add_conditional_edges(
        "critique",
        should_revise,
        {True: "revise", False: "finalize"},
    )
    graph.add_edge("revise", "critique")
    graph.add_edge("finalize", END)

    return graph.compile()


def should_revise(state: PRDState) -> bool:
    return len(state["critique_notes"]) > 0
```

---

## 六、难点与应对策略

| 难点 | 问题描述 | 解决方案 |
|------|---------|---------|
| **上下文过长** | 讨论几轮后超出 Token 限制 | Summarizer Agent 每 5 轮压缩一次；上下文 Token 实时计数，超阈值强制压缩 |
| **无限扯皮** | 模型之间客套或无法达成一致 | 强制 max_turns 限制 + 共识判定函数；超时后 PM 强制拍板，标记"未完全共识" |
| **幻觉控制** | 架构师设计了不存在的技术方案 | 接入 Web Search Tool (Tavily API)，Agent 在设计方案时联网验证；输出后做 fact-check 环节 |
| **模型不稳定** | 某个模型 API 临时不可用 | 每个角色配置 fallback 模型；指数退避重试；降级策略 |
| **费用控制** | 多模型多轮对话消耗大 | 实时 Token 计数 + 预算上限；低优先级环节用便宜模型；上下文压缩减少 Token 消耗 |
| **输出质量波动** | 不同模型风格不统一 | Writer Agent 做最终统一润色；Prompt 中明确输出格式要求；引入评分机制 |

---

## 七、技术栈总结

| 层级 | 技术选型 |
|------|---------|
| 开发语言 | Python 3.11+ |
| Web 框架 | FastAPI (后端) + Streamlit/Next.js (前端) |
| Agent 框架 | LangGraph（自定义流程）或 MetaGPT（开箱即用 SOP） |
| 模型接口 | LiteLLM |
| 短期记忆 | Redis 7 |
| 长期记忆 | ChromaDB / Milvus |
| Prompt 管理 | YAML + Jinja2 |
| 日志 | structlog |
| 可观测性 | OpenTelemetry + Prometheus |
| 容器化 | Docker + docker-compose |
| 代码质量 | Ruff (lint + format) + mypy (类型检查) |
| 测试 | pytest + pytest-asyncio |
| 包管理 | uv 或 poetry (pyproject.toml) |

---

## 八、MVP 里程碑建议

| 阶段 | 内容 | 建议周期 |
|------|------|---------|
| M0 - 基础骨架 | 项目结构搭建、模型网关接入、单 Agent 调通 | 1 周 |
| M1 - 核心流程 | 4 阶段工作流跑通（单模型），CLI 交互 | 1-2 周 |
| M2 - 多模型协同 | 接入多模型、讨论引擎、共识判定 | 1-2 周 |
| M3 - 可用产品 | FastAPI 接口、Streamlit UI、文档导出 | 1-2 周 |
| M4 - 生产就绪 | 可观测性、错误处理、性能优化、Docker 部署 | 1-2 周 |

---

## 九、依赖清单 (pyproject.toml)

以下为项目完整依赖，Claude Code 应直接生成此文件：

```toml
[project]
name = "multi-model-prd"
version = "0.1.0"
description = "Multi-model collaborative PRD generation system"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "litellm>=1.50.0",
    "langgraph>=0.2.0",
    "redis>=5.2.0",
    "chromadb>=0.5.0",
    "pyyaml>=6.0.0",
    "jinja2>=3.1.0",
    "structlog>=24.4.0",
    "sse-starlette>=2.1.0",
    "tiktoken>=0.8.0",
    "markdown>=3.7",
    "weasyprint>=62.0",
    "httpx>=0.27.0",
    "tenacity>=9.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.7.0",
    "mypy>=1.12.0",
    "pre-commit>=4.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 十、环境变量清单 (.env.example)

Claude Code 应生成此文件作为模板，实际密钥通过 `.env` 注入：

```bash
# ===== 模型 API Keys =====
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx

# ===== 可选模型 =====
GEMINI_API_KEY=
OPENAI_API_BASE=              # 自定义 OpenAI 兼容端点（可选）

# ===== Redis =====
REDIS_URL=redis://localhost:6379/0

# ===== ChromaDB =====
CHROMA_HOST=localhost
CHROMA_PORT=8001

# ===== 应用配置 =====
APP_ENV=development           # development / testing / production
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO                # DEBUG / INFO / WARNING / ERROR

# ===== 安全 =====
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8501
RATE_LIMIT_PER_MINUTE=30

# ===== 费用控制 =====
MAX_TOKENS_PER_SESSION=500000 # 单个会话最大 Token 消耗
```

---

## 十一、配置文件完整定义

### 11.1 config/agents.yaml

此文件定义所有参与的 Agent，包括通用智能体和主持人。每个 Agent 可独立配置使用的模型：

```yaml
agents:
  - name: "agent_01"
    model_ref: "gpt4o_model"         # 引用 models.yaml 中的 name
    display_name: "Agent 01"
    description: "通用智能体"
    enabled: true

  - name: "agent_02"
    model_ref: "claude35_model"
    display_name: "Agent 02"
    description: "通用智能体"
    enabled: true

  - name: "agent_03"
    model_ref: "deepseek_model"
    display_name: "Agent 03"
    description: "通用智能体"
    enabled: true

  # 可继续添加更多 Agent...

  - name: "moderator"
    model_ref: "cheap_model"          # 主持人使用低成本模型
    display_name: "主持人"
    description: "讨论主持人，负责引导流程、总结进展、推动共识"
    is_moderator: true
    enabled: true
```

### 11.2 config/models.yaml（完整版，含 fallback）

```yaml
models:
  - name: "gpt4o_model"
    provider: "openai"
    model: "gpt-4o"
    fallback: "claude35_model"        # 不可用时降级到此模型
    config:
      temperature: 0.7
      max_tokens: 4096
      timeout: 60
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "claude35_model"
    provider: "anthropic"
    model: "claude-3-5-sonnet-20241022"
    fallback: "gpt4o_model"
    config:
      temperature: 0.5
      max_tokens: 8192
      timeout: 90
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "deepseek_model"
    provider: "deepseek"
    model: "deepseek-reasoner"
    fallback: "gpt4o_model"
    config:
      temperature: 0.5
      max_tokens: 4096
      timeout: 120
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "cheap_model"
    provider: "openai"
    model: "gpt-4o-mini"
    fallback: null
    config:
      temperature: 0.3
      max_tokens: 2000
      timeout: 30
      retry:
        max_attempts: 2
        backoff_factor: 1
      max_tokens: 4096
      timeout: 60
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "logic_brain"
    provider: "anthropic"
    model: "claude-3-5-sonnet-20241022"
    role_assignment: ["architect", "writer"]
    fallback: "creative_brain"
    config:
      temperature: 0.3
      max_tokens: 8192
      timeout: 90
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "critical_brain"
    provider: "deepseek"
    model: "deepseek-reasoner"
    role_assignment: ["reviewer"]
    fallback: "logic_brain"
    config:
      temperature: 0.5
      max_tokens: 4096
      timeout: 120
      retry:
        max_attempts: 3
        backoff_factor: 2

  - name: "cheap_brain"
    provider: "openai"
    model: "gpt-4o-mini"
    role_assignment: ["summarizer", "_consensus_judge"]
    fallback: null
    config:
      temperature: 0.2
      max_tokens: 2000
      timeout: 30
      retry:
        max_attempts: 2
        backoff_factor: 1
```

### 11.3 config/settings.yaml（完整版）

```yaml
app:
  name: "multi-model-prd"
  version: "0.1.0"
  debug: false

server:
  host: "${APP_HOST:-0.0.0.0}"
  port: "${APP_PORT:-8000}"
  workers: 1                          # 因为 LangGraph 有状态，单 worker

discussion:
  max_turns_per_stage:
    elicitation: 5                    # 需求澄清最多 5 轮
    design: 10                        # 功能设计最多 10 轮
    writing: 10                       # PRD撰写最多 10 轮
    finalizing: 1                     # 文档生成 1 轮
  consensus:
    enabled: true
    threshold: 0.8
    judge_model: "cheap_model"         # 使用便宜模型判断共识
    min_messages_before_check: 4      # 至少 4 条消息后才检查共识
  context_compression:
    enabled: true
    trigger_after_turns: 5
    max_context_tokens: 100000
    summarizer_agent: "cheap_model"   # 压缩时使用便宜模型

memory:
  redis:
    url: "${REDIS_URL:-redis://localhost:6379/0}"
    ttl: 86400
    key_prefix: "prd:"
  vector_db:
    provider: "chroma"
    host: "${CHROMA_HOST:-localhost}"
    port: "${CHROMA_PORT:-8001}"
    collection: "prd_history"
    embedding_model: "text-embedding-3-small"
    top_k: 5                          # RAG 检索返回条数

output:
  default_format: "markdown"
  supported_formats: ["markdown", "pdf"]
  prd_template: "prd_output_template.yaml"

logging:
  level: "${LOG_LEVEL:-INFO}"
  format: "json"
  include_fields: ["session_id", "agent_name", "stage", "round_num"]

security:
  cors_origins: "${CORS_ALLOWED_ORIGINS:-http://localhost:3000}"
  rate_limit_per_minute: "${RATE_LIMIT_PER_MINUTE:-30}"
  max_tokens_per_session: "${MAX_TOKENS_PER_SESSION:-500000}"
```

---

## 十二、Prompt 模板完整定义

每个 Prompt 模板为独立 YAML 文件，包含 `system_prompt` 和可选的 `user_prompt_template` 字段。模板中使用 `{{ variable }}` 作为 Jinja2 占位符。

### 12.1 prompts/universal_agent.yaml

通用 Agent 的 Prompt 模板，用于所有参与讨论的 Agent。

```yaml
name: "universal_agent"
version: "1.0"
description: "通用智能体 - 可扮演任何角色"

system_prompt: |
  你是一位专业的产品与技术专家，拥有丰富的产品需求文档（PRD）撰写经验。

  ## 你的核心能力
  你能够扮演以下任何角色，根据讨论需要灵活切换：
  - **需求分析师**：挖掘需求、提出澄清问题
  - **产品经理**：功能拆解、用户流程设计、优先级评估
  - **系统架构师**：技术可行性评估、数据结构设计
  - **评审员**：寻找逻辑漏洞、边缘情况、挑战假设
  - **文档撰写者**：整合讨论结果、输出标准格式文档

  ## 你的工作方式
  1. 根据主持人给出的阶段指令，明确当前任务
  2. 提出你的独立观点和方案
  3. 认真阅读其他 Agent 的发言
  4. 对其他 Agent 的方案进行建设性评审：
     - 指出方案的优点
     - 提出改进建议
     - 指出潜在的问题或遗漏
  5. 根据评审意见修改完善自己的方案
  6. 积极寻求共识，在合理范围内调整立场

  ## 输出原则
  - 每次发言聚焦一个主题，清晰表达你的观点
  - 对其他 Agent 的评审意见要具体、有依据
  - 如果发现严重问题，明确指出并提出解决方案
  - 如果赞同其他 Agent 的观点，明确表示支持
  - 避免空洞的客套话，直接讨论实质内容

  ## 角色扮演说明
  当需要扮演特定角色时，请展现该角色的专业视角：
  - 需求分析师：关注用户需求、场景、痛点
  - 产品经理：关注用户价值、功能优先级、用户体验
  - 架构师：关注技术可行性、实现成本、系统设计
  - 评审员：关注逻辑完整性、边缘情况、潜在风险

  ## 规则
  - 使用中文交流
  - 保持专业、客观的态度
  - 不要无异议地附和他人，要有独立思考
  - 但也不要固执己见，接受合理建议

user_prompt_template: |
  ## 当前阶段：{{ stage }}

  ## 阶段指令：
  {{ stage_instruction }}

  ## 讨论背景：
  {{ discussion_context }}

  ## 前序讨论记录（最近 {{ recent_messages_count }} 条）：
  {{ recent_messages }}

  请根据以上信息，提出你的观点或方案。
```

### 12.2 prompts/moderator.yaml

主持人 Agent 的 Prompt 模板。

```yaml
name: "moderator"
version: "1.0"
description: "讨论主持人 - 引导流程、推动共识"

system_prompt: |
  你是一位专业的讨论主持人，负责引导多 Agent 协作讨论。

  ## 你的核心职责
  1. **启动讨论**：明确当前阶段的目标和任务范围
  2. **邀请发言**：确保每个 Agent 都有机会提出自己的观点
  3. **总结进展**：定期总结各方观点，指出共识和分歧
  4. **引导评审**：引导 Agent 之间相互评审
  5. **判断共识**：评估各方是否达成一致意见
  6. **宣布结果**：宣布讨论进入下一阶段或结束

  ## 讨论阶段与流程

  ### 阶段1：需求澄清（elicitation）
  1. 发起讨论："请各位根据用户需求，提出需要澄清的关键问题"
  2. 邀请每个 Agent 依次提出问题（3-5个）
  3. 邀请 Agent 之间相互评审问题质量
  4. 总结优质问题，生成《需求澄清问卷》
  5. 收集用户回答后，邀请 Agent 生成需求清洗单
  6. 合并、整合，输出最终需求清洗单

  ### 阶段2：功能设计（design）
  1. 发起讨论："请各位基于需求清洗单，提出核心功能列表"
  2. 邀请每个 Agent 提出功能方案（功能名称、优先级、描述）
  3. 邀请 Agent 相互评审：功能覆盖、优先级、可行性
  4. 多轮迭代后，总结共识功能列表

  ### 阶段3：PRD撰写评审（writing）
  1. 分配任务："请各位分别撰写 PRD 的不同模块"
  2. 各 Agent 撰写：背景与目标、功能详述、非功能需求、技术要点
  3. 邀请 Agent 相互评审：逻辑、流程、异常处理
  4. 整合各模块，生成完整 PRD 草稿

  ### 阶段4：文档生成（finalizing）
  1. 指定一个 Agent："请将 PRD 草稿标准化为最终输出格式"
  2. 邀请其他 Agent 对格式提出建议
  3. 确认最终文档

  ## 共识判定标准
  判断各方达成共识的标志：
  - 主要方案得到多数 Agent 支持或认可
  - 分歧点已通过讨论解决或达成折中
  - 没有重大未解决的争议

  ## 规则
  - 使用中文
  - 保持中立，不偏向任何 Agent
  - 确保讨论效率，避免无意义的重复
  - 必要时可提醒 Agent 聚焦主题
  - 超过最大轮数后，总结当前状态并进入下一阶段

user_prompt_template: |
  ## 当前阶段：{{ stage }}

  ## 当前轮数：{{ current_round }} / {{ max_rounds }}

  ## 参与讨论的 Agent：
  {{ agent_list }}

  ## 讨论记录：
  {{ discussion_history }}

  请根据以上情况，执行主持人的职责。
```

### 12.3 prompts/summarizer.yaml

上下文压缩的 Prompt 模板。

```yaml
name: "summarizer"
version: "1.0"
description: "上下文总结者 - 压缩讨论记录"

system_prompt: |
  你的任务是压缩多轮讨论记录，保留所有关键信息。

  ## 压缩规则
  1. **必须保留**：
     - 所有已达成的共识和决策
     - 所有未解决的分歧（标注各方立场）
     - 关键的数据/指标/约束条件
     - 功能列表及其优先级变更
  2. **可以去除**：
     - 重复表达的相同观点
     - 客套话和过渡语
     - 已被推翻的早期方案（仅保留推翻原因）
  3. **输出格式**：
     ```
     ## 讨论摘要（截至第 N 轮）

     ### 已达成共识
     - 共识1
     - 共识2

     ### 未解决分歧
     - 分歧1：A 认为...，B 认为...

     ### 当前功能列表
     - 功能1 [P0] - 简述
     - 功能2 [P1] - 简述

     ### 关键约束
     - 约束1
     ```

user_prompt_template: |
  以下是需要压缩的讨论记录（共 {{ total_messages }} 条消息，{{ total_rounds }} 轮）：

  {{ discussion_text }}

  请压缩为结构化摘要。
```

### 12.4 prompts/stage_elicitation.yaml

阶段指令模板 - 需求澄清。

```yaml
name: "stage_elicitation"
version: "1.0"
description: "需求澄清阶段指令"

instruction: |
  当前处于**需求澄清阶段**。

  请各位 Agent 根据用户的初始需求，提出需要澄清的关键问题。

  建议的问题维度（请选择最关键的 3-5 个）：
  1. 目标用户是谁？使用场景是什么？
  2. 核心要解决的痛点是什么？
  3. 期望的盈利/商业模式？
  4. 与市面上类似产品的核心差异点？
  5. MVP（最小可行产品）的范围期望？
  6. 是否有时间节点或技术栈约束？

  请依次提出你的问题，然后相互评审问题质量，最后整合为需求清洗单。

  需求清洗单格式：
  ```json
  {
    "project_name": "项目名称",
    "one_line_summary": "一句话描述",
    "target_users": ["用户群体"],
    "core_pain_points": ["痛点"],
    "business_model": "商业模式",
    "differentiators": ["差异点"],
    "mvp_scope": "MVP范围",
    "constraints": {"timeline": "", "tech_stack": "", "budget": ""},
    "open_questions": []
  }
  ```
```

### 12.5 prompts/stage_design.yaml

阶段指令模板 - 功能设计。

```yaml
name: "stage_design"
version: "1.0"
description: "功能设计阶段指令"

instruction: |
  当前处于**功能设计阶段**。

  请各位 Agent 基于需求清洗单，提出核心功能列表。

  要求：
  1. 每个功能包含：功能名称、所属模块、用户故事、优先级（P0/P1/P2）、简述
  2. 覆盖需求清洗单中的核心需求和痛点
  3. 考虑技术可行性
  4. 区分 MVP 必需功能和增强功能

  输出格式：
  ```
  ## 功能列表（Agent XXX）

  ### [模块名]
  - F001: [功能名称] [P0]
    - 用户故事：作为 [角色]，我希望 [功能]，以便 [价值]
    - 简述：...
  ```

  提出方案后，请相互评审：
  - 功能是否覆盖了需求？
  - 优先级是否合理？
  - 是否存在遗漏或冗余？
  - 技术可行性如何？
```

### 12.6 prompts/stage_writing.yaml

阶段指令模板 - PRD 撰写评审。

```yaml
name: "stage_writing"
version: "1.0"
description: "PRD撰写评审阶段指令"

instruction: |
  当前处于**PRD 撰写评审阶段**。

  请各位 Agent 基于共识功能列表，撰写 PRD 草稿的不同模块。

  模块分配建议：
  - Agent 01: 背景与目标、用户角色
  - Agent 02: 功能详述（核心功能）
  - Agent 03: 非功能需求、技术要点
  - 其他 Agent 可补充遗漏部分

  撰写完成后，请相互评审：
  - 逻辑是否自洽？
  - 流程是否完整（正常+异常）？
  - 异常处理是否到位？
  - 字段定义是否清晰？
  - 是否有逻辑冲突或遗漏？

  输出格式：
  ```
  ## [章节标题]

  [详细内容...]
  ```

  根据评审意见修改完善后，整合为完整 PRD 草稿。
```

### 12.7 prompts/stage_finalizing.yaml

阶段指令模板 - 文档生成。

```yaml
name: "stage_finalizing"
version: "1.0"
description: "文档生成阶段指令"

instruction: |
  当前处于**文档生成阶段**。

  请指定的 Agent 将 PRD 草稿标准化为最终输出格式。

  标准格式要求：
  1. 添加文档头部信息：
     - 版本号
     - 生成日期
     - 生成方式：多 Agent 协作讨论
  2. 确保以下章节完整：
     - 1. 背景与目标
     - 2. 功能需求（功能总览表 + 功能详述）
     - 3. 非功能需求
     - 4. 技术要点
     - 5. 待确认项（如有）
  3. 生成目录
  4. 使用 Markdown 标准格式

  其他 Agent 可对文档格式提出最终建议。
```

---

## 十三、逐文件实现规格

以下为 `src/` 目录下每个文件的详细实现规格，包含类/函数签名、输入输出类型、内部逻辑描述。Claude Code 应按文件逐个实现。

### 13.1 src/main.py — 应用入口

```python
"""应用入口，负责 FastAPI app 创建和生命周期管理。"""
import contextlib
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.models.registry import ModelRegistry
from src.agents.registry import AgentRegistry
from src.memory.short_term import RedisMemory
from src.memory.long_term import VectorMemory
from src.utils.logger import setup_logging
from src.utils.config import load_settings


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用生命周期管理：
    1. 加载 settings.yaml, models.yaml, agents.yaml
    2. 初始化 ModelRegistry（验证所有模型连通性）
    3. 初始化 AgentRegistry（根据 agents.yaml 创建所有 Agent 实例）
    4. 初始化 RedisMemory 连接池
    5. 初始化 VectorMemory 连接
    6. 将以上实例存入 app.state
    yield 后执行清理：关闭 Redis 连接池、释放资源
    """
    ...


def create_app() -> FastAPI:
    """
    创建 FastAPI 实例：
    1. 设置 lifespan
    2. 添加 CORS 中间件（origins 来自配置）
    3. 添加速率限制中间件
    4. 注册 router（prefix="/api/v1"）
    5. 返回 app
    """
    ...


if __name__ == "__main__":
    uvicorn.run("src.main:create_app", factory=True, host="0.0.0.0", port=8000, reload=True)
```

### 13.2 src/utils/config.py — 配置加载

```python
"""统一配置加载模块，读取 YAML 并解析环境变量占位符。"""
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ModelConfig(BaseModel):
    """单个模型的配置，对应 models.yaml 中的一项"""
    name: str
    provider: str
    model: str
    role_assignment: list[str]
    fallback: str | None = None
    config: dict[str, Any]


class AgentDef(BaseModel):
    """单个 Agent 的定义，对应 agents.yaml 中的一项"""
    name: str
    role: str
    display_name: str
    model_ref: str
    prompt_template: str
    description: str
    stages: list[str]
    config_override: dict[str, Any] | None = None


class DiscussionSettings(BaseModel):
    max_turns_per_stage: dict[str, int]
    consensus: dict[str, Any]
    context_compression: dict[str, Any]


class Settings(BaseModel):
    """全局配置聚合，由 settings.yaml + models.yaml + agents.yaml 合并而成"""
    models: list[ModelConfig]
    agents: list[AgentDef]
    discussion: DiscussionSettings
    memory: dict[str, Any]
    output: dict[str, Any]
    logging: dict[str, Any]
    security: dict[str, Any]


def resolve_env_vars(value: str) -> str:
    """
    解析 ${VAR:-default} 格式的环境变量引用。
    逻辑：用正则匹配 ${...} 模式，从 os.environ 取值，有默认值则 fallback。
    """
    ...


def load_yaml(path: Path) -> dict[str, Any]:
    """
    加载 YAML 文件并递归解析其中的环境变量占位符。
    """
    ...


def load_settings(config_dir: Path = Path("config")) -> Settings:
    """
    加载并合并三个配置文件，返回 Settings 实例。
    1. 读取 config/settings.yaml → 解析环境变量
    2. 读取 config/models.yaml → 解析为 list[ModelConfig]
    3. 读取 config/agents.yaml → 解析为 list[AgentDef]
    4. 合并为 Settings 返回
    """
    ...
```

### 13.3 src/utils/prompt_loader.py — Prompt 加载与渲染

```python
"""Prompt 模板加载和 Jinja2 渲染。"""
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
import yaml


class PromptTemplate(BaseModel):
    name: str
    version: str
    description: str
    system_prompt: str
    user_prompt_template: str | None = None


class PromptLoader:
    def __init__(self, prompts_dir: Path = Path("prompts")) -> None:
        """
        初始化：
        1. 扫描 prompts_dir 下所有 .yaml 文件
        2. 解析为 PromptTemplate 缓存到 dict（key=name）
        3. 初始化 Jinja2 Environment
        """
        ...

    def get_system_prompt(self, template_name: str) -> str:
        """返回指定模板的 system_prompt 原文。"""
        ...

    def render_user_prompt(self, template_name: str, **variables: Any) -> str:
        """
        用 Jinja2 渲染 user_prompt_template，传入变量。
        如果模板没有 user_prompt_template 则返回空字符串。
        """
        ...
```

### 13.4 src/utils/logger.py — 结构化日志

```python
"""基于 structlog 的结构化日志配置。"""
import structlog


def setup_logging(level: str = "INFO", json_format: bool = True) -> None:
    """
    配置 structlog：
    1. 设置 processors（添加时间戳、日志级别、调用信息）
    2. 如果 json_format=True，使用 JSONRenderer
    3. 否则使用 ConsoleRenderer（开发模式）
    4. 绑定 stdlib logging 到 structlog
    """
    ...


def get_logger(**initial_bindings: str) -> structlog.stdlib.BoundLogger:
    """
    获取带预绑定字段的 logger。
    使用示例：logger = get_logger(session_id="abc", agent_name="pm")
    """
    ...
```

### 13.5 src/utils/token_counter.py — Token 计数

```python
"""Token 计数工具，用于上下文管理和费用控制。"""
import tiktoken


class TokenCounter:
    def __init__(self, default_model: str = "gpt-4o") -> None:
        """初始化 tiktoken 编码器。"""
        ...

    def count(self, text: str, model: str | None = None) -> int:
        """计算文本的 token 数量。如果指定 model 则用该模型的编码器。"""
        ...

    def count_messages(self, messages: list[dict[str, str]], model: str | None = None) -> int:
        """
        计算 OpenAI 格式 messages 列表的总 token 数。
        包含 role/name/content 的所有 token + 消息格式开销。
        """
        ...

    def is_over_limit(self, messages: list[dict[str, str]], limit: int) -> bool:
        """判断 messages 是否超过 token 上限。"""
        ...
```

### 13.6 src/models/registry.py — 模型注册表

```python
"""模型注册表，管理所有可用模型并提供查询和降级能力。"""
from src.utils.config import ModelConfig


class ModelRegistry:
    def __init__(self, model_configs: list[ModelConfig]) -> None:
        """
        初始化：
        1. 将 model_configs 存为 dict（key=name）
        2. 构建 role → model_name 的映射
        3. 构建 fallback 链
        """
        ...

    def get_model(self, name: str) -> ModelConfig:
        """根据名称获取模型配置。不存在则抛 KeyError。"""
        ...

    def get_model_for_role(self, role: str) -> ModelConfig:
        """根据角色获取推荐模型配置。优先返回第一个匹配的。"""
        ...

    def get_fallback(self, name: str) -> ModelConfig | None:
        """获取指定模型的降级模型。无降级则返回 None。"""
        ...

    async def health_check(self) -> dict[str, bool]:
        """
        对所有模型发送简单 ping 请求，返回各模型的可用状态。
        实现：对每个模型调用 litellm.acompletion 发一条简短消息，超时 10 秒。
        """
        ...
```

### 13.7 src/models/gateway.py — 模型网关

```python
"""LiteLLM 封装，提供统一的模型调用接口，含重试和降级。"""
from typing import Any

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.registry import ModelRegistry
from src.utils.config import ModelConfig
from src.utils.logger import get_logger


class ModelGateway:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.logger = get_logger(component="model_gateway")

    async def call(
        self,
        model_name: str,
        messages: list[dict[str, str]],
        **override_params: Any,
    ) -> litellm.ModelResponse:
        """
        统一模型调用入口：
        1. 从 registry 获取 ModelConfig
        2. 合并 config 中的默认参数和 override_params
        3. 使用 tenacity 重试：max_attempts 和 backoff_factor 来自配置
        4. 如果重试耗尽，尝试 fallback 模型
        5. fallback 也失败，抛出 ModelCallError
        6. 记录日志：model_name, latency, token_usage, success/failure
        """
        ...

    async def _call_with_retry(
        self,
        config: ModelConfig,
        messages: list[dict[str, str]],
        **params: Any,
    ) -> litellm.ModelResponse:
        """
        实际调用 litellm.acompletion 的内部方法，附带 tenacity 重试装饰。
        重试参数从 config.config.retry 中获取。
        """
        ...
```

### 13.8 src/agents/base.py — Agent 基类

```python
"""Agent 基类，所有角色 Agent 继承此类。"""
from typing import ClassVar

from src.api.schemas import AgentMessage
from src.models.gateway import ModelGateway
from src.utils.config import AgentDef
from src.utils.prompt_loader import PromptLoader


class BaseAgent:
    ROLE: ClassVar[str] = ""

    def __init__(
        self,
        agent_def: AgentDef,
        gateway: ModelGateway,
        prompt_loader: PromptLoader,
    ) -> None:
        """
        初始化：
        1. 保存 agent_def, gateway, prompt_loader
        2. 从 prompt_loader 加载 system_prompt
        3. 如果 agent_def 有 config_override，合并参数
        """
        ...

    async def speak(
        self,
        context: list[dict[str, str]],
        stage: str = "",
        round_num: int = 0,
        **template_vars: str,
    ) -> AgentMessage:
        """
        Agent 发言：
        1. 构建 messages：[system_prompt] + context
        2. 如果有 user_prompt_template 且传入了 template_vars，渲染后追加到 messages
        3. 调用 gateway.call(model_name, messages)
        4. 构建 AgentMessage 返回（stage 和 round_num 由调用方传入）
        """
        ...

    async def speak_with_instruction(
        self,
        context: list[dict[str, str]],
        instruction: str,
        stage: str = "",
        round_num: int = 0,
    ) -> AgentMessage:
        """
        带额外指令的发言（用于编排层给 Agent 附加阶段性任务说明）：
        1. 将 instruction 作为最后一条 user message 附加到 context
        2. 调用 speak()
        """
        ...
```

### 13.9 src/agents/registry.py — Agent 注册与工厂

```python
"""Agent 注册表，根据配置创建和管理 Agent 实例。"""
from src.agents.base import BaseAgent
from src.models.gateway import ModelGateway
from src.utils.config import AgentDef, Settings
from src.utils.prompt_loader import PromptLoader


class AgentRegistry:
    def __init__(
        self,
        agent_defs: list[AgentDef],
        gateway: ModelGateway,
        prompt_loader: PromptLoader,
    ) -> None:
        """
        初始化：遍历 agent_defs，为每个创建 BaseAgent 实例，存入 dict（key=name）。
        """
        ...

    def get_agent(self, name: str) -> BaseAgent:
        """根据名称获取 Agent。不存在则抛 KeyError。"""
        ...

    def get_agents_for_stage(self, stage: str) -> list[BaseAgent]:
        """返回参与指定阶段的所有 Agent 列表（按 agents.yaml 中的顺序）。"""
        ...
```

### 13.10 src/orchestration/engine.py — 讨论引擎

```python
"""讨论引擎，管理 Agent 间的多轮对话。"""
from collections.abc import AsyncIterator

from src.agents.base import BaseAgent
from src.api.schemas import AgentMessage
from src.orchestration.consensus import ConsensusJudge
from src.orchestration.summarizer import ContextSummarizer
from src.utils.token_counter import TokenCounter
from src.utils.prompt_loader import PromptLoader


class DiscussionRoom:
    def __init__(
        self,
        agents: list[BaseAgent],
        moderator: BaseAgent,
        max_rounds: int,
        consensus_judge: ConsensusJudge,
        summarizer: ContextSummarizer,
        token_counter: TokenCounter,
        prompt_loader: PromptLoader,
        max_context_tokens: int = 100000,
    ) -> None:
        """
        初始化讨论室：
        - agents: 参与讨论的通用 Agent 列表
        - moderator: 主持人 Agent
        - max_rounds: 最大轮数
        - consensus_judge: 共识判定器
        - summarizer: 上下文压缩器
        - token_counter: Token 计数器
        - prompt_loader: Prompt 加载器
        - max_context_tokens: 上下文 Token 上限
        """
        self.agents = agents
        self.moderator = moderator
        self.context: list[dict[str, str]] = []
        self.all_messages: list[AgentMessage] = []

    async def run(
        self, stage: str, stage_instruction: str, initial_context: str
    ) -> AsyncIterator[AgentMessage]:
        """
        执行讨论循环（yield 每条消息，支持 SSE 流式推送）：
        1. 主持人发起讨论，明确阶段目标和任务
        2. for round in range(max_rounds):
           a. 第1轮：所有 agent 依次提出方案
           b. 第2-N轮：agent 相互评审，根据反馈修改
           c. 主持人总结进展，判断是否达成共识
           d. 检查 token 数是否超限，超限则触发压缩
        3. 达成共识或达到 max_rounds 后结束
        """
        # 主持人发起讨论
        stage_prompt = self.prompt_loader.render_user_prompt(
            f"stage_{stage}",
            stage_instruction=stage_instruction,
            discussion_context=initial_context,
            recent_messages_count=0,
            recent_messages="",
        )
        msg = await self.moderator.speak_with_instruction(
            self.context, stage_prompt, stage, 0
        )
        yield msg
        self.context.append({"role": "assistant", "name": "moderator", "content": msg.content})
        self.all_messages.append(msg)

        for round_num in range(1, max_rounds + 1):
            # 所有 agent 发言
            for agent in self.agents:
                user_prompt = self.prompt_loader.render_user_prompt(
                    "universal_agent",
                    stage=stage,
                    stage_instruction=stage_instruction,
                    discussion_context=initial_context,
                    recent_messages_count=5,
                    recent_messages=self._get_recent_messages(),
                )
                msg = await agent.speak(self.context, stage, round_num, stage_instruction=stage_instruction)
                yield msg
                self.context.append({
                    "role": "assistant",
                    "name": agent.config.name,
                    "content": msg.content,
                })
                self.all_messages.append(msg)

                # 检查 token 数
                if self.token_counter.is_over_limit(self.context, max_context_tokens):
                    await self._maybe_compress()

            # 主持人总结进展，判断共识
            consensus = await self.consensus_judge.check(self.context)
            if consensus:
                # 主持人宣布达成共识
                summary_prompt = f"当前讨论已达成共识，请总结本轮讨论成果。"
                msg = await self.moderator.speak_with_instruction(
                    self.context, summary_prompt, stage, round_num
                )
                yield msg
                break
            elif round_num < max_rounds:
                # 主持人引导下一轮
                next_round_prompt = f"当前尚未达成共识，请各位继续评审和修改方案。"
                msg = await self.moderator.speak_with_instruction(
                    self.context, next_round_prompt, stage, round_num
                )
                yield msg

    def _get_recent_messages(self) -> str:
        """获取最近5条消息的文本摘要。"""
        recent = self.context[-10:] if len(self.context) >= 10 else self.context
        return "\n".join(f"{m.get('name', 'user')}: {m['content']}" for m in recent)

    async def _maybe_compress(self) -> None:
        """如果 context 超过 max_context_tokens，调用 summarizer 压缩。"""
        summary = await self.summarizer.summarize(self.context)
        self.context = [{"role": "system", "content": f"前序讨论摘要：\n{summary}"}]
```

### 13.11 src/orchestration/consensus.py — 共识判定

```python
"""共识判定逻辑。"""
from src.models.gateway import ModelGateway


class ConsensusJudge:
    def __init__(
        self,
        gateway: ModelGateway,
        judge_model: str = "cheap_model",
        threshold: float = 0.8,
        min_messages: int = 4,
    ) -> None:
        ...

    async def check(self, context: list[dict[str, str]]) -> bool:
        """
        判断是否达成共识：
        1. 如果消息数 < min_messages，返回 False
        2. 取最近 6 条消息
        3. 构造 prompt 让 judge_model 返回 0-1 分数
        4. 分数 >= threshold 则返回 True
        5. 解析失败返回 False
        """
        ...
```

### 13.12 src/orchestration/summarizer.py — 上下文压缩

```python
"""上下文压缩器。"""
from src.models.gateway import ModelGateway


class ContextSummarizer:
    def __init__(self, gateway: ModelGateway, model_name: str = "cheap_brain") -> None:
        ...

    async def summarize(self, context: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        压缩上下文：
        1. 将 context 拼接为文本
        2. 调用模型生成结构化摘要
        3. 返回新的 context：[{"role": "system", "content": "前序讨论摘要：..."}]
        """
        ...
```

### 13.13 src/orchestration/workflow.py — LangGraph 工作流

```python
"""LangGraph 工作流定义，串联 4 个阶段。"""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.registry import AgentRegistry
from src.orchestration.engine import DiscussionRoom
from src.utils.config import Settings
from src.utils.prompt_loader import PromptLoader


class PRDState(TypedDict):
    session_id: str
    requirement: str                     # 用户原始输入
    clarified_requirement: dict | None   # 阶段1 输出：需求清洗单（JSON）
    feature_list: str                    # 阶段2 输出：共识功能列表（Markdown 文本）
    prd_draft: str                       # 阶段3 输出：PRD 草稿
    final_prd: str                       # 阶段4 输出：最终 PRD 文档
    status: str                          # 当前状态
    all_messages: list[dict[str, Any]]   # 全部 Agent 消息记录
    error: str | None                    # 错误信息


def build_prd_workflow(
    agent_registry: AgentRegistry,
    settings: Settings,
    prompt_loader: PromptLoader,
) -> Any:  # 返回 CompiledGraph
    """
    构建并编译 LangGraph 工作流：

    节点定义：
    - elicit: 需求澄清节点
    - design: 功能设计节点
    - writing: PRD 撰写评审节点
    - finalize: 文档生成节点

    边定义：
    - elicit → design
    - design → writing
    - writing → finalize
    - finalize → END
    """
    ...


async def elicit_requirements(state: PRDState) -> PRDState:
    """
    需求澄清节点：
    1. 获取所有通用 Agent + 主持人
    2. 创建 DiscussionRoom
    3. 加载阶段指令 stage_elicitation.yaml
    4. 启动讨论：用户需求作为初始上下文
    5. 收集讨论结果，提取需求清洗单
    6. 更新 state.clarified_requirement 和 state.status
    """
    ...


async def design_features(state: PRDState) -> PRDState:
    """
    功能设计节点：
    1. 获取所有通用 Agent + 主持人
    2. 创建 DiscussionRoom
    3. 加载阶段指令 stage_design.yaml
    4. 启动讨论：需求清洗单作为初始上下文
    5. 收集讨论结果，提取共识功能列表
    6. 更新 state.feature_list 和 state.status
    """
    ...


async def write_prd(state: PRDState) -> PRDState:
    """
    PRD 撰写评审节点：
    1. 获取所有通用 Agent + 主持人
    2. 创建 DiscussionRoom
    3. 加载阶段指令 stage_writing.yaml
    4. 启动讨论：功能列表作为初始上下文
    5. 收集讨论结果，整合为 PRD 草稿
    6. 更新 state.prd_draft 和 state.status
    """
    ...


async def finalize_document(state: PRDState) -> PRDState:
    """
    文档生成节点：
    1. 获取所有通用 Agent + 主持人
    2. 创建 DiscussionRoom（或者直接调用某 Agent）
    3. 加载阶段指令 stage_finalizing.yaml
    4. 启动讨论：PRD 草稿作为初始上下文
    5. 生成最终 PRD 文档
    6. 更新 state.final_prd 和 state.status = "completed"
    """
    ...
```

## 十四、测试规格

### 14.1 测试策略

| 层级 | 范围 | 工具 |
|------|------|------|
| 单元测试 | config 加载、token 计数、prompt 渲染、Markdown 处理 | pytest |
| 集成测试 | Agent 发言、讨论引擎（Mock 模型调用）| pytest + pytest-asyncio |
| 端到端测试 | 完整工作流（使用 cheap model）| pytest + httpx AsyncClient |

### 14.2 tests/conftest.py — 共享 Fixtures

```python
"""pytest 共享 fixtures。"""
import pytest
from unittest.mock import AsyncMock
from src.utils.config import load_settings, Settings, ModelConfig, AgentDef


@pytest.fixture
def settings() -> Settings:
    """加载测试用配置（config/ 目录下的文件）。"""
    ...


@pytest.fixture
def mock_gateway() -> AsyncMock:
    """
    Mock 的 ModelGateway，call() 返回预设响应：
    - content: "Mock response for {model_name}"
    - usage.total_tokens: 100
    """
    ...


@pytest.fixture
def sample_context() -> list[dict[str, str]]:
    """包含 3 轮对话的示例上下文。"""
    return [
        {"role": "user", "content": "讨论主题: 宠物外卖App"},
        {"role": "assistant", "name": "agent_01", "content": "我建议核心功能包括..."},
        {"role": "assistant", "name": "agent_02", "content": "技术上需要考虑..."},
        {"role": "assistant", "name": "agent_03", "content": "有一个逻辑问题..."},
    ]
```

### 14.3 tests/test_config.py

```python
"""配置加载测试。"""

class TestResolveEnvVars:
    def test_with_default(self): ...
        # "${VAR:-default}" → "default" (当 VAR 未设置)

    def test_with_env(self): ...
        # "${VAR:-default}" → "actual" (当 VAR="actual")

    def test_no_placeholder(self): ...
        # "plain text" → "plain text"


class TestLoadSettings:
    def test_loads_all_configs(self, tmp_path): ...
        # 创建临时 yaml 文件，验证 load_settings 返回完整 Settings

    def test_model_config_validation(self): ...
        # 缺少必填字段时 Pydantic 抛 ValidationError

    def test_agent_references_valid_model(self, settings): ...
        # 所有 agent 的 model_ref 都在 models 中存在
```

### 14.4 tests/test_agents.py

```python
"""Agent 测试。"""

class TestBaseAgent:
    async def test_speak_returns_agent_message(self, mock_gateway): ...
        # 验证 speak() 返回正确的 AgentMessage 结构

    async def test_speak_includes_system_prompt(self, mock_gateway): ...
        # 验证调用 gateway 时 messages[0] 是 system prompt

    async def test_speak_with_instruction_appends_user_msg(self, mock_gateway): ...
        # 验证 instruction 被追加为 user message


class TestAgentRegistry:
    def test_get_agent(self, settings): ...
        # 按 name 获取已注册 Agent

    def test_get_agents(self, settings): ...
        # 获取所有 Agent 列表，验证主持人单独获取

    def test_get_nonexistent_agent_raises(self, settings): ...
        # 获取不存在的 Agent 抛 KeyError

    def test_get_moderator(self, settings): ...
        # 获取主持人 Agent
```

### 14.5 tests/test_engine.py

```python
"""讨论引擎测试。"""

class TestDiscussionRoom:
    async def test_runs_correct_number_of_rounds(self, mock_gateway): ...
        # 共识未达成时，运行 max_rounds 轮

    async def test_stops_on_consensus(self, mock_gateway): ...
        # 模拟 consensus_judge 返回 True，验证提前终止

    async def test_context_compression_triggered(self, mock_gateway): ...
        # 当 token 数超过阈值时触发压缩

    async def test_all_agents_speak_each_round(self, mock_gateway): ...
        # 每轮所有 Agent 都发言一次

    async def test_moderator_guides_discussion(self, mock_gateway): ...
        # 验证主持人在每轮发言


class TestConsensusJudge:
    async def test_returns_false_when_too_few_messages(self): ...
    async def test_returns_true_when_score_above_threshold(self, mock_gateway): ...
    async def test_returns_false_on_parse_error(self, mock_gateway): ...
```

### 14.6 tests/test_workflow.py

```python
"""LangGraph 工作流测试。"""

class TestPRDWorkflow:
    async def test_full_workflow_happy_path(self, mock_gateway): ...
        # Mock 所有 Agent 调用，验证工作流从 elicit 到 finalize 正常走完
        # 验证 final_prd 不为空

    async def test_stage_elicitation_output(self, mock_gateway): ...
        # 验证需求澄清阶段输出需求清洗单

    async def test_stage_design_output(self, mock_gateway): ...
        # 验证功能设计阶段输出功能列表

    async def test_stage_writing_output(self, mock_gateway): ...
        # 验证 PRD 撰写阶段输出 PRD 草稿

    async def test_state_persisted_between_nodes(self, mock_gateway): ...
        # 验证 state 在节点间正确传递
```

### 14.7 tests/test_api.py

```python
"""API 路由测试。"""
import httpx
from fastapi.testclient import TestClient

class TestSessionAPI:
    async def test_create_session(self, client: httpx.AsyncClient): ...
        # POST /sessions → 201, 返回 session_id

    async def test_get_session_not_found(self, client: httpx.AsyncClient): ...
        # GET /sessions/nonexistent → 404

    async def test_send_message_wrong_status(self, client: httpx.AsyncClient): ...
        # 在非 waiting_input 状态发消息 → 400/409

    async def test_get_output_before_complete(self, client: httpx.AsyncClient): ...
        # status != completed 时获取 output → 400


class TestHealthAPI:
    async def test_health_check(self, client: httpx.AsyncClient): ...
        # GET /health → 200, 含 models/redis/vector_db 状态
```

---

## 十五、实现顺序指令（给 Claude Code 的执行计划）

请严格按以下顺序逐步实现，每步完成后运行 `pytest` 确保通过：

### Step 0: 项目初始化

```
1. 创建 multi-model-prd/ 目录结构（按 4.1 节）
2. 生成 pyproject.toml（按第九章）
3. 生成 .env.example（按第十章）
4. 生成 .gitignore（包含 .env, __pycache__, .mypy_cache, .ruff_cache, dist/, *.egg-info）
5. 运行 `pip install -e ".[dev]"` 安装依赖
```

### Step 1: 配置层

```
1. 实现 src/utils/config.py（含 resolve_env_vars, load_yaml, load_settings）
2. 创建 config/models.yaml（按 11.2 节）
3. 创建 config/agents.yaml（按 11.1 节）
4. 创建 config/settings.yaml（按 11.3 节）
5. 编写 tests/test_config.py 并通过
```

### Step 2: 工具层

```
1. 实现 src/utils/logger.py
2. 实现 src/utils/token_counter.py
3. 实现 src/utils/prompt_loader.py
4. 创建所有 prompts/*.yaml 文件（按第十二章）
5. 编写 tests/test_utils.py（覆盖 token 计数和 prompt 渲染）并通过
```

### Step 3: 模型层

```
1. 实现 src/models/registry.py
2. 实现 src/models/gateway.py（含 tenacity 重试和 fallback）
3. 编写 tests/test_gateway.py（Mock litellm.acompletion）并通过
```

### Step 4: 智能体层

```
1. 实现 src/agents/base.py
2. 实现 src/agents/registry.py
3. 编写 tests/test_agents.py 并通过
```

### Step 5: 编排层

```
1. 实现 src/orchestration/consensus.py
2. 实现 src/orchestration/summarizer.py
3. 实现 src/orchestration/engine.py
4. 编写 tests/test_engine.py 并通过
```

### Step 6: 工作流

```
1. 实现 src/orchestration/workflow.py（含所有阶段节点函数）
2. 编写 tests/test_workflow.py 并通过
```

### Step 7: 存储层

```
1. 实现 src/memory/short_term.py
2. 实现 src/memory/long_term.py
3. 编写 tests/test_memory.py（使用 fakeredis 和 Mock ChromaDB）并通过
```

### Step 8: 输出层

```
1. 实现 src/output/markdown.py
2. 实现 src/output/pdf.py
3. 编写 tests/test_output.py 并通过
```

### Step 9: API 层

```
1. 实现 src/api/schemas.py（按 13.18 节）
2. 实现 src/api/routes.py（按 13.19 节）
3. 实现 src/main.py（按 13.1 节）
4. 编写 tests/test_api.py（使用 httpx.AsyncClient）并通过
```

### Step 10: 容器化

```
1. 创建 Dockerfile（多阶段构建，基于 python:3.11-slim）
2. 创建 docker-compose.yaml（按 4.8 节）
3. 验证 `docker compose up` 能正常启动
```

### Step 11: 全流程验证

```
1. 运行 `ruff check src/ tests/`（零 error）
2. 运行 `mypy src/`（零 error）
3. 运行 `pytest --cov=src --cov-report=term-missing`（所有测试通过，覆盖率 > 80%）
```

---

## 十六、关键设计决策备忘

以下决策已在方案中做出，Claude Code 实现时应遵循，不需再询问：

| 决策 | 选择 | 原因 |
|------|------|------|
| Agent 框架 | LangGraph（不用 MetaGPT） | 需要完全自定义讨论流程和条件分支 |
| 模型调用 | LiteLLM（不直接用各 SDK） | 统一接口，一行代码切换模型 |
| 异步模式 | 全 async/await | FastAPI + litellm 均支持，性能更好 |
| 状态管理 | LangGraph State + Redis | State 用于工作流内部，Redis 用于持久化和跨请求 |
| SSE 推送 | sse-starlette | 轻量，与 FastAPI 原生集成 |
| 共识判定 | 主持人 + LLM-as-Judge | 结合人工式引导和自动判断，更灵活 |
| Prompt 存储 | YAML 文件（非数据库） | MVP 阶段够用，Git 版本管理 |
| 上下文压缩 | Summarizer Agent | 比截断更智能，保留关键决策 |
| PDF 导出 | weasyprint | 纯 Python 实现，无需外部服务 |
| 包管理 | pyproject.toml + pip | 通用性最好，兼容 uv/poetry |
| Agent 模式 | 通用 Agent + 主持人 | 灵活可配置，所有 Agent 参与讨论 |
    1. 获取 brainstorming 阶段的 Agents（PM + 架构师 + 评审员）
    2. 创建 DiscussionRoom，设置 max_rounds 来自 settings
    3. 以 clarified_requirement 为 topic 启动 Debate
    4. 从讨论结果中提取最终的功能列表
    5. 更新 state.feature_list
    """
    ...


async def draft_prd(state: PRDState) -> PRDState:
    """
    PRD 草稿撰写节点：
    1. 获取 "senior_pm" Agent
    2. 调用 agent.speak_with_instruction()，传入 feature_list
    3. 将输出存为 state.prd_draft
    """
    ...


async def critique_prd(state: PRDState) -> PRDState:
    """
    评审节点：
    1. 获取 "critic" Agent
    2. 将 prd_draft 作为 context 让 Critic 评审
    3. 解析 Critic 输出：
       - 如果包含 "[LGTM]"，设置 critique_notes = []
       - 否则提取所有问题到 critique_notes
    """
    ...


async def revise_prd(state: PRDState) -> PRDState:
    """
    修订节点：
    1. 获取 "senior_pm" Agent
    2. 将 critique_notes + 当前 prd_draft 传入
    3. PM 输出修订后的 PRD 草稿
    4. 更新 state.prd_draft, revision_count += 1, 清空 critique_notes
    """
    ...


async def finalize_document(state: PRDState) -> PRDState:
    """
    文档生成节点：
    1. 获取 "writer" Agent
    2. 传入所有材料（clarified_requirement, feature_list, prd_draft, 评审记录）
    3. Writer 输出完整 PRD Markdown
    4. 更新 state.final_prd, state.status = "completed"
    """
    ...
```

### 13.14 src/memory/short_term.py — Redis 短期记忆

```python
"""Redis 短期记忆，存储会话状态和讨论上下文。"""
import json
from typing import Any

import redis.asyncio as redis


class RedisMemory:
    def __init__(self, url: str, ttl: int = 86400, key_prefix: str = "prd:") -> None:
        """初始化 Redis 异步连接池。"""
        ...

    async def save_session(self, session_id: str, data: dict[str, Any]) -> None:
        """序列化为 JSON 并存储，设置 TTL。key = {prefix}session:{session_id}"""
        ...

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """读取并反序列化会话数据。"""
        ...

    async def append_message(self, session_id: str, message: dict[str, Any]) -> None:
        """向会话消息列表追加一条消息。使用 Redis LIST 的 RPUSH。"""
        ...

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话全部消息列表。"""
        ...

    async def close(self) -> None:
        """关闭连接池。"""
        ...
```

### 13.15 src/memory/long_term.py — VectorDB 长期记忆

```python
"""VectorDB 长期记忆，存储历史 PRD 供 RAG 检索。"""
import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorMemory:
    def __init__(
        self,
        host: str,
        port: int,
        collection_name: str,
        embedding_model: str = "text-embedding-3-small",
        top_k: int = 5,
    ) -> None:
        """
        初始化 ChromaDB 客户端：
        1. 连接远程 ChromaDB（host:port）
        2. 获取或创建 collection
        """
        ...

    async def store_prd(self, session_id: str, prd_content: str, metadata: dict) -> None:
        """
        将完成的 PRD 存入向量库：
        1. 按章节拆分 PRD 内容（按 ## 分割）
        2. 每个分片加上 metadata（session_id, 章节标题, 生成日期）
        3. 调用 collection.add()
        """
        ...

    async def search_similar(self, query: str, n_results: int | None = None) -> list[dict]:
        """
        RAG 检索：
        1. 使用 query 在 collection 中做相似性搜索
        2. 返回 top_k 条结果，每条含 content + metadata + distance
        """
        ...
```

### 13.16 src/output/markdown.py — Markdown 渲染

```python
"""PRD 文档 Markdown 渲染。"""
from datetime import datetime


class MarkdownRenderer:
    def render(self, prd_content: str, metadata: dict) -> str:
        """
        对 Writer Agent 输出的 Markdown 做后处理：
        1. 确保文档头部有标准元信息（版本、日期、生成方式）
        2. 确保所有表格格式正确
        3. 添加目录（TOC）
        4. 返回最终 Markdown 字符串
        """
        ...

    def save(self, content: str, path: str) -> None:
        """将 Markdown 内容写入文件。"""
        ...
```

### 13.17 src/output/pdf.py — PDF 导出

```python
"""PRD 文档 PDF 导出。"""
import markdown
from weasyprint import HTML


class PDFExporter:
    def export(self, markdown_content: str, output_path: str) -> str:
        """
        将 Markdown 转换为 PDF：
        1. 使用 markdown 库将 Markdown 转为 HTML
        2. 注入 CSS 样式（专业文档风格：宋体、合理间距、表格边框）
        3. 使用 weasyprint 将 HTML 转为 PDF
        4. 保存到 output_path 并返回路径
        """
        ...
```

### 13.18 src/api/schemas.py — 全部 Pydantic 模型

```python
"""API 请求/响应的 Pydantic 模型定义。"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    CREATED = "created"
    ELICITATION = "elicitation"          # 需求澄清中
    WAITING_USER_INPUT = "waiting_input" # 等待用户回答
    BRAINSTORMING = "brainstorming"      # 头脑风暴中
    DRAFTING = "drafting"                # 撰写草稿中
    CRITIQUING = "critiquing"            # 评审中
    REVISING = "revising"               # 修订中
    FINALIZING = "finalizing"            # 生成最终文档中
    COMPLETED = "completed"
    FAILED = "failed"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: ...)  # UUID
    agent_name: str
    agent_role: str
    display_name: str
    content: str
    model_used: str
    stage: str
    round_num: int
    token_usage: int
    timestamp: datetime = Field(default_factory=datetime.now)
    is_consensus: bool = False           # 是否为共识结论消息


class SessionCreate(BaseModel):
    initial_requirement: str = Field(..., min_length=5, max_length=5000)
    preferred_output_format: str = Field(default="markdown")


class UserMessage(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class SessionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    current_stage: str
    total_tokens_used: int
    total_rounds: int
    messages: list[AgentMessage]
    created_at: datetime
    updated_at: datetime


class SessionListItem(BaseModel):
    session_id: str
    status: SessionStatus
    initial_requirement: str
    created_at: datetime


class PRDOutput(BaseModel):
    session_id: str
    title: str
    content: str
    format: str
    total_tokens_used: int
    total_rounds: int
    generated_at: datetime


class SSEEvent(BaseModel):
    """SSE 推送事件格式"""
    event: str                           # agent_message / stage_change / error / completed
    data: dict


class HealthResponse(BaseModel):
    status: str                          # healthy / degraded / unhealthy
    models: dict[str, bool]              # 各模型可用状态
    redis: bool
    vector_db: bool
    version: str
```

### 13.19 src/api/routes.py — API 路由

```python
"""FastAPI 路由定义。"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.api.schemas import (
    HealthResponse,
    PRDOutput,
    SessionCreate,
    SessionResponse,
    UserMessage,
)

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, request: Request) -> SessionResponse:
    """
    创建新的 PRD 生成会话：
    1. 生成 session_id (UUID)
    2. 初始化 PRDState，存入 Redis
    3. 启动 LangGraph 工作流的 elicit 阶段（后台任务）
    4. 返回 SessionResponse（status=elicitation）
    """
    ...


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """
    获取会话状态：
    1. 从 Redis 读取会话数据
    2. 不存在则返回 404
    3. 返回 SessionResponse（含全部消息历史）
    """
    ...


@router.post("/sessions/{session_id}/messages", response_model=SessionResponse)
async def send_message(session_id: str, body: UserMessage, request: Request) -> SessionResponse:
    """
    用户在会话中发送消息（用于需求澄清阶段的问答）：
    1. 校验会话存在且 status 为 waiting_input
    2. 将用户消息注入工作流上下文
    3. 继续 elicit 阶段的下一轮
    4. 返回更新后的 SessionResponse
    """
    ...


@router.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str, request: Request) -> EventSourceResponse:
    """
    SSE 流式推送讨论过程：
    1. 校验会话存在
    2. 创建 AsyncGenerator，从 DiscussionRoom 的 run() 方法 yield 事件
    3. 事件类型：agent_message / stage_change / consensus_reached / error / completed
    4. 返回 EventSourceResponse
    """
    ...


@router.get("/sessions/{session_id}/output", response_model=PRDOutput)
async def get_output(session_id: str, request: Request, format: str = "markdown") -> Any:
    """
    获取最终 PRD 文档：
    1. 校验会话存在且 status=completed
    2. 如果 format=markdown，直接返回 PRDOutput
    3. 如果 format=pdf，调用 PDFExporter 生成 PDF 并返回 FileResponse
    4. 不支持的 format 返回 400
    """
    ...


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    健康检查：
    1. 检查 Redis 连通性
    2. 检查 VectorDB 连通性
    3. 检查各模型可用性（通过 ModelRegistry.health_check）
    4. 全部健康返回 "healthy"，部分故障返回 "degraded"，全部故障返回 "unhealthy"
    """
    ...
```

---

## 十四、测试规格

### 14.1 测试策略

| 层级 | 范围 | 工具 |
|------|------|------|
| 单元测试 | config 加载、token 计数、prompt 渲染、Markdown 处理 | pytest |
| 集成测试 | Agent 发言、讨论引擎（Mock 模型调用）| pytest + pytest-asyncio |
| 端到端测试 | 完整工作流（使用 cheap model）| pytest + httpx AsyncClient |

### 14.2 tests/conftest.py — 共享 Fixtures

```python
"""pytest 共享 fixtures。"""
import pytest
from unittest.mock import AsyncMock
from src.utils.config import load_settings, Settings, ModelConfig, AgentDef


@pytest.fixture
def settings() -> Settings:
    """加载测试用配置（config/ 目录下的文件）。"""
    ...


@pytest.fixture
def mock_gateway() -> AsyncMock:
    """
    Mock 的 ModelGateway，call() 返回预设响应：
    - content: "Mock response for {model_name}"
    - usage.total_tokens: 100
    """
    ...


@pytest.fixture
def sample_context() -> list[dict[str, str]]:
    """包含 3 轮对话的示例上下文。"""
    return [
        {"role": "user", "content": "讨论主题: 宠物外卖App"},
        {"role": "assistant", "name": "pm", "content": "我建议核心功能包括..."},
        {"role": "assistant", "name": "architect", "content": "技术上需要考虑..."},
        {"role": "assistant", "name": "reviewer", "content": "有一个逻辑问题..."},
    ]
```

### 14.3 tests/test_config.py

```python
"""配置加载测试。"""

class TestResolveEnvVars:
    def test_with_default(self): ...
        # "${VAR:-default}" → "default" (当 VAR 未设置)

    def test_with_env(self): ...
        # "${VAR:-default}" → "actual" (当 VAR="actual")

    def test_no_placeholder(self): ...
        # "plain text" → "plain text"


class TestLoadSettings:
    def test_loads_all_configs(self, tmp_path): ...
        # 创建临时 yaml 文件，验证 load_settings 返回完整 Settings

    def test_model_config_validation(self): ...
        # 缺少必填字段时 Pydantic 抛 ValidationError

    def test_agent_references_valid_model(self, settings): ...
        # 所有 agent 的 model_ref 都在 models 中存在
```

### 14.4 tests/test_agents.py

```python
"""Agent 测试。"""

class TestBaseAgent:
    async def test_speak_returns_agent_message(self, mock_gateway): ...
        # 验证 speak() 返回正确的 AgentMessage 结构

    async def test_speak_includes_system_prompt(self, mock_gateway): ...
        # 验证调用 gateway 时 messages[0] 是 system prompt

    async def test_speak_with_instruction_appends_user_msg(self, mock_gateway): ...
        # 验证 instruction 被追加为 user message


class TestAgentRegistry:
    def test_get_agent(self, settings): ...
        # 按 name 获取已注册 Agent

    def test_get_agents_for_stage(self, settings): ...
        # 按阶段获取 Agent 列表，验证顺序和数量

    def test_get_nonexistent_agent_raises(self, settings): ...
        # 获取不存在的 Agent 抛 KeyError
```

### 14.5 tests/test_engine.py

```python
"""讨论引擎测试。"""

class TestDiscussionRoom:
    async def test_runs_correct_number_of_rounds(self, mock_gateway): ...
        # 共识未达成时，运行 max_rounds 轮

    async def test_stops_on_consensus(self, mock_gateway): ...
        # 模拟 consensus_judge 返回 True，验证提前终止

    async def test_context_compression_triggered(self, mock_gateway): ...
        # 当 token 数超过阈值时触发压缩

    async def test_all_agents_speak_each_round(self, mock_gateway): ...
        # 每轮所有 Agent 都发言一次


class TestConsensusJudge:
    async def test_returns_false_when_too_few_messages(self): ...
    async def test_returns_true_when_score_above_threshold(self, mock_gateway): ...
    async def test_returns_false_on_parse_error(self, mock_gateway): ...
```

### 14.6 tests/test_workflow.py

```python
"""LangGraph 工作流测试。"""

class TestPRDWorkflow:
    async def test_full_workflow_happy_path(self, mock_gateway): ...
        # Mock 所有 Agent 调用，验证工作流从 elicit 到 finalize 正常走完
        # 验证 final_prd 不为空

    async def test_critique_triggers_revision(self, mock_gateway): ...
        # Critic 返回问题 → 进入 revise → 再次 critique

    async def test_max_revisions_limit(self, mock_gateway): ...
        # Critic 持续返回问题，但 revision_count 达上限后跳转 finalize

    async def test_state_persisted_between_nodes(self, mock_gateway): ...
        # 验证 state 在节点间正确传递
```

### 14.7 tests/test_api.py

```python
"""API 路由测试。"""
import httpx
from fastapi.testclient import TestClient

class TestSessionAPI:
    async def test_create_session(self, client: httpx.AsyncClient): ...
        # POST /sessions → 201, 返回 session_id

    async def test_get_session_not_found(self, client: httpx.AsyncClient): ...
        # GET /sessions/nonexistent → 404

    async def test_send_message_wrong_status(self, client: httpx.AsyncClient): ...
        # 在非 waiting_input 状态发消息 → 400/409

    async def test_get_output_before_complete(self, client: httpx.AsyncClient): ...
        # status != completed 时获取 output → 400


class TestHealthAPI:
    async def test_health_check(self, client: httpx.AsyncClient): ...
        # GET /health → 200, 含 models/redis/vector_db 状态
```

---

## 十五、实现顺序指令（给 Claude Code 的执行计划）

请严格按以下顺序逐步实现，每步完成后运行 `pytest` 确保通过：

### Step 0: 项目初始化

```
1. 创建 multi-model-prd/ 目录结构（按 4.1 节）
2. 生成 pyproject.toml（按第九章）
3. 生成 .env.example（按第十章）
4. 生成 .gitignore（包含 .env, __pycache__, .mypy_cache, .ruff_cache, dist/, *.egg-info）
5. 运行 `pip install -e ".[dev]"` 安装依赖
```

### Step 1: 配置层

```
1. 实现 src/utils/config.py（含 resolve_env_vars, load_yaml, load_settings）
2. 创建 config/models.yaml（按 11.2 节）
3. 创建 config/agents.yaml（按 11.1 节）
4. 创建 config/settings.yaml（按 11.3 节）
5. 编写 tests/test_config.py 并通过
```

### Step 2: 工具层

```
1. 实现 src/utils/logger.py
2. 实现 src/utils/token_counter.py
3. 实现 src/utils/prompt_loader.py
4. 创建所有 prompts/*.yaml 文件（按第十二章）
5. 编写 tests/test_utils.py（覆盖 token 计数和 prompt 渲染）并通过
```

### Step 3: 模型层

```
1. 实现 src/models/registry.py
2. 实现 src/models/gateway.py（含 tenacity 重试和 fallback）
3. 编写 tests/test_gateway.py（Mock litellm.acompletion）并通过
```

### Step 4: 智能体层

```
1. 实现 src/agents/base.py
2. 实现 src/agents/registry.py
3. 编写 tests/test_agents.py 并通过
```

### Step 5: 编排层

```
1. 实现 src/orchestration/consensus.py
2. 实现 src/orchestration/summarizer.py
3. 实现 src/orchestration/engine.py
4. 编写 tests/test_engine.py 并通过
```

### Step 6: 工作流

```
1. 实现 src/orchestration/workflow.py（含所有阶段节点函数）
2. 编写 tests/test_workflow.py 并通过
```

### Step 7: 存储层

```
1. 实现 src/memory/short_term.py
2. 实现 src/memory/long_term.py
3. 编写 tests/test_memory.py（使用 fakeredis 和 Mock ChromaDB）并通过
```

### Step 8: 输出层

```
1. 实现 src/output/markdown.py
2. 实现 src/output/pdf.py
3. 编写 tests/test_output.py 并通过
```

### Step 9: API 层

```
1. 实现 src/api/schemas.py（按 13.18 节）
2. 实现 src/api/routes.py（按 13.19 节）
3. 实现 src/main.py（按 13.1 节）
4. 编写 tests/test_api.py（使用 httpx.AsyncClient）并通过
```

### Step 10: 容器化

```
1. 创建 Dockerfile（多阶段构建，基于 python:3.11-slim）
2. 创建 docker-compose.yaml（按 4.8 节）
3. 验证 `docker compose up` 能正常启动
```

### Step 11: 全流程验证

```
1. 运行 `ruff check src/ tests/`（零 error）
2. 运行 `mypy src/`（零 error）
3. 运行 `pytest --cov=src --cov-report=term-missing`（所有测试通过，覆盖率 > 80%）
```

---

## 十六、关键设计决策备忘

以下决策已在方案中做出，Claude Code 实现时应遵循，不需再询问：

| 决策 | 选择 | 原因 |
|------|------|------|
| Agent 框架 | LangGraph（不用 MetaGPT） | 需要完全自定义讨论流程和条件分支 |
| 模型调用 | LiteLLM（不直接用各 SDK） | 统一接口，一行代码切换模型 |
| 异步模式 | 全 async/await | FastAPI + litellm 均支持，性能更好 |
| 状态管理 | LangGraph State + Redis | State 用于工作流内部，Redis 用于持久化和跨请求 |
| SSE 推送 | sse-starlette | 轻量，与 FastAPI 原生集成 |
| 共识判定 | LLM-as-Judge（cheap model） | 灵活度高于规则引擎，成本可控 |
| Prompt 存储 | YAML 文件（非数据库） | MVP 阶段够用，Git 版本管理 |
| 上下文压缩 | Summarizer Agent | 比截断更智能，保留关键决策 |
| PDF 导出 | weasyprint | 纯 Python 实现，无需外部服务 |
| 包管理 | pyproject.toml + pip | 通用性最好，兼容 uv/poetry |
