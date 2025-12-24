import operator
from typing import List, Optional
from pydantic import BaseModel, Field


class TodoItem(BaseModel):
    """
    单个待办事项数据类
    """
    id: int
    title: str
    intent: str
    query: str
    status: str = Field(default="pending", description="待办事项状态")
    summary: Optional[str] = Field(default=None, description="待办事项摘要")
    sources_summary: Optional[str] = Field(default=None, description="待办事项来源摘要")
    notices: List[str] = Field(default_factory=list, description="待办事项注意事项列表")
    note_id: Optional[str] = Field(default=None, description="待办事项笔记ID")
    note_path: Optional[str] = Field(default=None, description="待办事项笔记路径")
    stream_token: Optional[str] = Field(default=None, description="待办事项流令牌")
    
    model_config = {
        "frozen": False,  # 允许修改字段值
        "populate_by_name": True,  # 支持通过名称填充字段
        "kw_only": True  # 强制所有字段必须使用关键字参数
    }


class SummaryState(BaseModel):
    """
    汇总状态数据类，用于保存深度研究工作流中的中间结果。
    """
    research_topic: Optional[str] = Field(default=None, description="研究主题")  # Report topic
    search_query: Optional[str] = Field(default=None, description="搜索查询")  # Deprecated placeholder
    web_research_results: List = Field(default_factory=list)  # pydantic自动处理列表合并
    sources_gathered: List = Field(default_factory=list)  # pydantic自动处理列表合并
    research_loop_count: int = Field(default=0, description="研究循环次数")  # Research loop count
    running_summary: Optional[str] = Field(default=None, description="运行中摘要")  # Legacy summary field
    todo_items: List[TodoItem] = Field(default_factory=list)  # pydantic自动处理列表合并
    structured_report: Optional[str] = Field(default=None, description="结构化报告")
    report_note_id: Optional[str] = Field(default=None, description="报告笔记ID")
    report_note_path: Optional[str] = Field(default=None, description="报告笔记路径")
    
    model_config = {
        "frozen": False,  # 允许修改字段值
        "populate_by_name": True,  # 支持通过名称填充字段
        "arbitrary_types_allowed": True,  # 允许任意类型
        "kw_only": True  # 强制所有字段必须使用关键字参数
    }


class SummaryStateInput(BaseModel):
    """汇总状态输入，仅包含研究主题。"""
    research_topic: Optional[str] = Field(default=None, description="研究主题")  # Report topic
    
    model_config = {
        "frozen": False,
        "populate_by_name": True,
        "kw_only": True  # 强制所有字段必须使用关键字参数
    }


class SummaryStateOutput(BaseModel):
    """
    汇总状态输出，用于返回最终报告及待办列表。
    """
    running_summary: Optional[str] = Field(default=None, description="运行中摘要")  # Backward-compatible文本
    report_markdown: Optional[str] = Field(default=None, description="报告Markdown")
    todo_items: List[TodoItem] = Field(default_factory=list, description="待办事项列表")
    
    model_config = {
        "frozen": False,
        "populate_by_name": True,
        "kw_only": True  # 强制所有字段必须使用关键字参数
    }
