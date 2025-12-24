import os
from enum import Enum
from typing import Optional,Any
from pydantic import BaseModel,Field

class SearchAPI(Enum):
    """
    搜索API枚举类
    """
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    SEARXNG = "searxng"
    ADVANCED = "advanced"


class Configuration(BaseModel):
    """
    配置类，用于存储应用程序的配置参数。
    """
    max_web_research_loops: int = Field(
        default=3,
        title="Research Depth",
        description="执行的研究迭代次数",
    )
    local_llm: str = Field(
        default="llama3.2",
        title="Local Model Name",
        description="本地托管的LLM名称（Ollama/LMStudio）",
    )
    llm_provider: str = Field(
        default="ollama",
        title="LLM Provider",
        description="提供商标识（ollama、lmstudio 或 custom）",
    )
    search_api: SearchAPI = Field(
        default=SearchAPI.TAVILY,
        title="Search API",
        description="要使用的网络搜索API",
    )
    enable_notes: bool = Field(
        default=True,
        title="Enable Notes",
        description="是否在NoteTool中存储任务进度",
    )
    notes_workspace: str = Field(
        default="./notes",
        title="Notes Workspace",
        description="NoteTool持久化任务笔记的目录",
    )
    fetch_full_page: bool = Field(
        default=True,
        title="Fetch Full Page",
        description="是否在搜索结果中包含完整页面内容",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        title="Ollama Base URL",
        description="Ollama API的基础URL（不含/v1后缀）",
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        title="LMStudio Base URL",
        description="LMStudio OpenAI兼容API的基础URL",
    )
    strip_thinking_tokens: bool = Field(
        default=True,
        title="Strip Thinking Tokens",
        description="是否从模型响应中去除<think>标记",
    )
    use_tool_calling: bool = Field(
        default=False,
        title="Use Tool Calling",
        description="使用工具调用而非JSON模式生成结构化输出",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        title="LLM API Key",
        description="使用自定义OpenAI兼容服务时的可选API密钥",
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        title="LLM Base URL",
        description="使用自定义OpenAI兼容服务时的可选基础URL",
    )
    llm_model_id: Optional[str] = Field(
        default=None,
        title="LLM Model ID",
        description="使用自定义OpenAI兼容服务时的可选模型标识符",
    )

    @classmethod
    def from_env(cls,overrides:Optional[dict[str,Any]]=None) -> "Configuration":
        """
        从环境变量创建配置实例。
        """
        raw_values:dict[str,Any] = {}

        for field_name in cls.model_fields.keys():
            env_key = field_name.upper()
            if env_key in os.environ:
                raw_values[field_name] = os.getenv(env_key)

        env_aliases = {
            "local_llm": os.getenv("LOCAL_LLM"),
            "llm_provider": os.getenv("LLM_PROVIDER"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "llm_model_id": os.getenv("LLM_MODEL_ID"),
            "llm_base_url": os.getenv("LLM_BASE_URL"),
            "lmstudio_base_url": os.getenv("LMSTUDIO_BASE_URL"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL"),
            "max_web_research_loops": os.getenv("MAX_WEB_RESEARCH_LOOPS"),
            "fetch_full_page": os.getenv("FETCH_FULL_PAGE"),
            "strip_thinking_tokens": os.getenv("STRIP_THINKING_TOKENS"),
            "use_tool_calling": os.getenv("USE_TOOL_CALLING"),
            "search_api": os.getenv("SEARCH_API"),
            "enable_notes": os.getenv("ENABLE_NOTES"),
            "notes_workspace": os.getenv("NOTES_WORKSPACE"),
        }
        for key,value in env_aliases.items():
            if value is not None:
                raw_values.setdefault(key,value)
        
        if overrides:
            for key,value in overrides.items():
                if key is not None:
                    raw_values[key] = value
        return cls(**raw_values)

    def sanitized_ollama_url(self) -> str:
        """
        返回清理后的Ollama基础URL，确保以/v1结尾。
        """
        url = self.ollama_base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        return url
    
    def resolved_model(self) -> Optional[str]:
        """
        返回解析后的模型ID，考虑自定义服务配置。
        """
        return self.llm_model_id or self.local_llm
