from __future__ import annotations

import json
import sys
from typing import Any, Dict, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from config import Configuration, SearchAPI
from agent import DeepResearchAgent
from dotenv import load_dotenv

load_dotenv()

# 添加控制台日志处理程序
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


# 添加错误日志文件处理程序
logger.add(
    sink=sys.stderr,
    level="ERROR",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)

class ResearchRequest(BaseModel):
    """
    研究请求模型，用于接收研究主题和配置。
    """
    topic: str = Field(
        ...,
        description="要研究的主题或问题",
    )
    search_api: SearchAPI = Field(
        default=None,
        description="要使用的网络搜索API",
    )

class ResearchResponse(BaseModel):
    """
    研究响应模型，用于返回研究结果。
    """
    report_markdown: str = Field(
        ...,
        description="研究报告的Markdown格式内容",
    )
    todo_items:list[dict[str,Any]] = Field(
        default_factory=list,
        description="待办事项列表，每个项包含任务描述和完成状态",
    )


def _mask_secret(value:Optional[str],visible:int = 4) -> str:
    """
    对敏感信息进行掩码处理，显示前visible个字符和后visible个字符。
    """
    if not value:
        return ""
    if len(value) <= visible *2:
        return "*" * len(value)
    return value[:visible] + "..." + value[-visible:]


def _build_config(payload:ResearchRequest) -> Configuration:
    """
    从研究请求构建配置对象。
    """
    overrides: Dict[str, Any] = {}

    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)

def create_app() -> FastAPI:
    """
    创建FastAPI应用实例。
    """
    app = FastAPI(
        title="Deep Reach API",
        version="1.0",
        description="提供深度研究功能的API",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 使用on_event直到FastAPI版本支持lifespan装饰器
    @app.on_event("startup")
    def log_startup_configuration() -> None:
        config = Configuration.from_env()

        if config.llm_provider == "ollama":
            base_url = config.sanitized_ollama_url()
        elif config.llm_provider == "lmstudio":
            base_url = config.lmstudio_base_url
        else:
            base_url = config.llm_base_url or "unset"

        logger.info(
            "DeepResearch configuration loaded: provider=%s model=%s base_url=%s search_api=%s "
            "max_loops=%s fetch_full_page=%s tool_calling=%s strip_thinking=%s api_key=%s",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            _mask_secret(config.llm_api_key),
        )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """
        健康检查端点，返回服务状态。
        """
        return {"status": "healthy"}
    
    @app.post("/research", response_model=ResearchResponse)
    def research_endpoint(payload: ResearchRequest) -> ResearchResponse:
        """
        研究端点，接收研究主题和配置，返回研究结果。
        """
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
            result = agent.run(payload.topic)
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HTTPException(status_code=500, detail="Research failed") from exc
        
        todo_payload = [
            {
                "id": item.id,
                "title": item.title,
                "intent": item.intent,
                "query": item.query,
                "status": item.status,
                "summary": item.summary,
                "sources_summary": item.sources_summary,
                "note_id": item.note_id,
                "note_path": item.note_path,
            }
            for item in result.todo_items
        ]
        return ResearchResponse(
            report_markdown=(result.report_markdown or result.running_summary or ""),
            todo_items=todo_payload,
        )
    
    @app.post("/research/stream")
    def research_stream_endpoint(payload: ResearchRequest) -> ResearchResponse:
        """
        研究流端点，接收研究主题和配置，返回流式研究结果。
        """
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        
        def event_iterator() -> Iterator[dict[str]]:
            """
            事件迭代器，用于流式返回研究事件。
            """
            try:
                for event in agent.run_stream(payload.topic):
                    yield f"data:{json.dumps(event,ensure_ascii=False)}\n\n"
            except Exception as exc:  # pragma: no cover - defensive guardrail
                logger.exception("Streaming research failed")
                error_payload = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        
        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers = {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )