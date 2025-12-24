# DeepReach - 深度研究智能体系统

DeepReach是一个基于人工智能的深度研究智能体系统，能够自动完成从主题分析、任务分解到信息收集、总结和报告生成的完整研究流程。系统采用前后端分离架构，提供直观的用户界面和强大的研究能力。

## 技术栈

### 后端
- **Python** - 主要开发语言
- **FastAPI** - 高性能API框架，支持异步和自动文档生成
- **Pydantic** - 数据验证和序列化库
- **HelloAgents** - 智能体框架，用于构建和管理研究智能体
- **Loguru** - 现代化日志管理库
- **Dotenv** - 环境变量管理

### 前端
- **Vue 3** - 渐进式JavaScript框架，支持组合式API
- **TypeScript** - 类型安全的JavaScript超集
- **Vite** - 下一代前端构建工具
- **Axios** - HTTP客户端，用于API通信

## 目录结构

```
deepreach/
├── backend/                    # 后端服务目录
│   ├── src/                    # 后端源代码
│   │   ├── __pycache__/        # Python编译文件
│   │   ├── notes/              # 笔记存储目录
│   │   │   └── notes_index.json # 笔记索引文件
│   │   ├── services/           # 服务模块
│   │   │   ├── __pycache__/    # 服务编译文件
│   │   │   ├── notes.py        # 笔记管理服务
│   │   │   ├── planner.py      # 任务规划服务
│   │   │   ├── reporter.py     # 报告生成服务
│   │   │   ├── search.py       # 搜索服务
│   │   │   ├── summarizer.py   # 总结服务
│   │   │   └── tool_events.py  # 工具事件服务
│   │   ├── agent.py            # 深度研究智能体实现
│   │   ├── config.py           # 配置管理
│   │   ├── main.py             # FastAPI应用入口
│   │   ├── model.py            # 数据模型定义
│   │   ├── prompt.py           # 提示词模板
│   │   └── utils.py            # 工具函数
│   └── .env                    # 环境变量配置
├── frontend/                   # 前端应用目录
│   ├── src/                    # 前端源代码
│   │   ├── services/           # 服务模块
│   │   │   └── api.ts          # API通信服务
│   │   ├── App.vue             # 主应用组件
│   │   ├── env.d.ts            # 环境类型定义
│   │   ├── main.ts             # 应用入口
│   │   └── style.css           # 全局样式
│   ├── .env                    # 环境变量配置
│   ├── .gitignore              # Git忽略文件
│   ├── index.html              # HTML模板
│   ├── package-lock.json       # npm依赖锁定文件
│   ├── package.json            # npm配置文件
│   ├── tsconfig.json           # TypeScript配置
│   ├── tsconfig.node.json      # Node.js TypeScript配置
│   └── vite.config.ts          # Vite配置
├── notes/                      # 全局笔记存储目录
│   ├── note_*.md               # 生成的研究笔记
│   └── notes_index.json        # 全局笔记索引
└── README.md                   # 项目文档
```

## 安装步骤

### 后端安装

1. 确保已安装Python 3.11+版本

2. 创建并激活虚拟环境（推荐）：
   ```bash
   cd backend
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/macOS
   source venv/bin/activate
   ```

3. 安装依赖：
   ```bash
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn pydantic loguru python-dotenv aiohttp hello-agents
   ```

4. 配置环境变量：
   - 复制并修改`.env`文件，根据需要配置搜索API和LLM参数

5. 启动后端服务：
   ```bash
   cd src
   python main.py
   ```

   服务将在`http://0.0.0.0:8000`启动，API文档可访问`http://localhost:8000/docs`

### 前端安装

1. 确保已安装Node.js 16+版本

2. 安装依赖：
   ```bash
   cd frontend
   npm install
   ```

3. 启动开发服务器：
   ```bash
   npm run dev
   ```

   前端应用将在`http://localhost:5173`启动

## 配置说明

### 环境变量配置（backend/.env）

```env
# 搜索服务配置
SEARCH_API='duckduckgo'  # 可选值: duckduckgo, tavily, perplexity, searxng

# LLM模型配置
LLM_PROVIDER=custom      # 可选值: ollama, lmstudio, custom
LLM_MODEL_ID='gpt-4.1-mini'  # 模型名称
LLM_API_KEY='your-api-key'   # API密钥
LLM_BASE_URL='https://api.example.com/v1'  # API地址

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 研究配置
MAX_WEB_RESEARCH_LOOPS=3  # 研究迭代次数
FETCH_FULL_PAGE=True      # 是否获取完整页面内容
```

## 使用方法

1. 启动后端服务和前端应用

2. 在浏览器中访问`http://localhost:5173`

3. 输入研究主题，选择搜索引擎（可选）

4. 点击"开始研究"按钮

5. 系统将自动：
   - 分析研究主题
   - 生成研究任务清单
   - 执行信息搜索
   - 总结搜索结果
   - 生成最终报告

6. 研究过程中，您可以：
   - 查看实时进度
   - 浏览任务执行情况
   - 查看搜索来源和摘要
   - 跟踪研究日志

7. 研究完成后，您将获得：
   - 结构化研究报告
   - 完整的研究过程记录
   - 可访问的研究笔记

## 功能特性

### 1. 自动研究流程
- 主题分析与任务分解
- 多轮信息搜索与收集
- 智能结果总结与整合
- 结构化报告生成

### 2. 实时反馈
- 任务执行状态实时更新
- 搜索来源可视化展示
- 研究过程日志记录
- 支持取消正在进行的研究

### 3. 灵活配置
- 支持多种搜索引擎（DuckDuckGo、Tavily、Perplexity等）
- 支持多种LLM模型（本地或云端）
- 可配置研究深度和范围
- 支持自定义API端点

### 4. 数据持久化
- 研究笔记自动保存
- 任务执行记录完整存储
- 支持笔记查询和管理
- 报告可导出和共享

## API接口说明

### 1. 健康检查
- **URL**: `/health`
- **方法**: GET
- **描述**: 检查服务健康状态
- **响应**: `{"status": "healthy"}`

### 2. 研究请求
- **URL**: `/research`
- **方法**: POST
- **描述**: 提交研究主题并获取研究结果
- **请求体**:
  ```json
  {
    "topic": "研究主题",
    "search_api": "duckduckgo"
  }
  ```
- **响应**:
  ```json
  {
    "report_markdown": "研究报告内容",
    "todo_items": [
      {
        "id": 1,
        "title": "任务标题",
        "intent": "任务意图",
        "query": "搜索查询",
        "status": "completed",
        "summary": "任务总结",
        "sources_summary": "来源摘要",
        "note_id": "笔记ID",
        "note_path": "笔记路径"
      }
    ]
  }
  ```

### 3. 研究流请求
- **URL**: `/research/stream`
- **方法**: POST
- **描述**: 提交研究主题并获取流式研究结果
- **请求体**: 同研究请求
- **响应**: Server-Sent Events (SSE) 流，包含实时研究进度和结果

## 关键模块说明

### 深度研究智能体（agent.py）
实现核心研究逻辑，协调各个服务模块完成研究任务：
- 研究主题分析与任务规划
- 多轮搜索与信息收集
- 结果总结与整合
- 报告生成与持久化

### 配置管理（config.py）
管理系统配置参数：
- 搜索API配置
- LLM模型配置
- 研究深度与范围
- 服务器设置

### 搜索服务（search.py）
实现多种搜索引擎的集成：
- DuckDuckGo搜索
- Tavily搜索
- Perplexity搜索
- Searxng搜索
- 搜索结果处理与格式化

### 总结服务（summarizer.py）
实现搜索结果的智能总结：
- 基于LLM的文本摘要
- 信息提取与整合
- 上下文感知总结

### 报告生成服务（reporter.py）
实现研究报告的生成：
- 报告结构规划
- 内容组织与格式化
- Markdown格式输出

## 故障排除

### 1. 搜索显示"已跳过"无结果
- 检查搜索引擎API配置是否正确
- 确保API密钥有效
- 尝试更换其他搜索引擎

### 2. LLM连接失败
- 检查LLM_PROVIDER和LLM_BASE_URL配置
- 确保API密钥有效
- 验证网络连接

### 3. 前端无法连接后端
- 检查后端服务是否正常运行
- 确保CORS配置正确
- 验证前端API地址配置

## 更新日志

### v1.0.0
- 初始版本发布
- 实现完整的深度研究流程
- 支持多种搜索引擎
- 前后端分离架构
- 实时研究进度展示
- 研究结果持久化

## 贡献指南

欢迎贡献代码！请按照以下步骤：

1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 许可证

本项目采用MIT许可证 - 查看[LICENSE](LICENSE)文件了解详情。

## 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub: [deepreach-repo](https://github.com/your-username/deepreach)
- Email: contact@deepreach.example.com

---

感谢使用DeepReach深度研究智能体系统！
