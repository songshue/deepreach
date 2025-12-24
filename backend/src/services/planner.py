
from __future__ import annotations

from cgitb import text
import json
import logging
import re
from typing import Any, List, Optional

from hello_agents import ToolAwareSimpleAgent

from model import SummaryState, TodoItem
from config import Configuration
from prompt import get_current_date, todo_planner_instructions
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)

TOOL_CALL_PATTERN = re.compile(
    r"\[TOOL_CALL:(?P<tool>[^:]+):(?P<body>[^\]]+)\]",
    re.IGNORECASE,
)

class PlanningService:
    def __init__(self, planner_agent: ToolAwareSimpleAgent,config:Configuration):
        self._agent = planner_agent
        self._config = config

    def plan_todo_list(self,state:SummaryState)->List[TodoItem]:
        """
        计划待办事项列表
        """
        prompt = todo_planner_instructions.format(
            current_date=get_current_date(),
            research_topic=state.research_topic,
        )
        response = self._agent.run(prompt)
        self._agent.clear_history()
        logger.info("Planner raw output (truncated): %s", response[:500])

        tasks_payload = self._extract_tasks(response)
        todo_items:List[TodoItem] = []

        for idx,item in enumerate(tasks_payload,start=1):
            title = str(item.get("title") or f"任务{idx}").strip()
            intent = str(item.get("intent") or "聚焦主题的关键问题").strip()
            query = str(item.get("query") or state.research_topic).strip()

            task = TodoItem(
                id = idx,
                title=title,
                intent=intent,
                query=query,
            )
            todo_items.append(task)
        state.todo_items = todo_items
        titles = [task.title for task in todo_items]
        logger.info("Planner produced %d tasks: %s", len(todo_items), titles)
        return todo_items

    @staticmethod
    def create_fallback_task(state:SummaryState) -> TodoItem:
        """
        创建回退任务
        """
        return TodoItem(
            id=1,
            title="基础背景梳理",
            intent="收集主题的核心背景与最新动态",
            query=f"{state.research_topic} 最新进展" if state.research_topic else "基础背景梳理",
        )
    
    def _extract_tasks(self,response:str) -> List[dict[str,Any]]:
        """
        从LLM响应中提取待办事项任务
        """
        text = response.strip()
        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)      
        
        json_payload = self._extract_json_payload(text)
        tasks:List[dict[str,Any]] = []
        if isinstance(json_payload,dict):
            candidate = json_payload.get("tasks")
            if isinstance(candidate,list):
                for item in candidate:
                    if isinstance(item,dict):
                        tasks.append(item)
        elif isinstance(json_payload,list):
            for item in json_payload:
                if isinstance(item,dict):
                    tasks.append(item)
        if not tasks:
            tool_payload = self._extract_tool_calls(text)
            if tool_payload and isinstance(tool_payload.get("tasks"),list):
                for item in tool_payload.get("tasks"):
                    if isinstance(item,dict):
                        tasks.append(item)
        
        return tasks


    
    def _extract_tool_calls(self,text:str) -> Optional[dict[str,Any]]:
        """
        从文本中提取工具调用
        """
        match = TOOL_CALL_PATTERN.search(text)
        if not match:
            return None
        tool_body = match.group("body").strip()
        try:
            tool_payload = json.loads(tool_body)
            if isinstance(tool_payload,dict):
                return tool_payload
        except json.JSONDecodeError:
            pass

        parts = [segment.strip() for segment in body.split(",") if segment.strip()]
        tool_payload:dict[str,Any] = {}
        for part in parts:
            if "=" not in part:
                continue
            key,value = part.split("=",1)
            tool_payload[key.strip()] = value.strip().strip('"').strip("'")
        
        return tool_payload or None


    

    
    def _extract_json_payload(self,text:str) -> Optional[dict[str,Any] | list]:
        """
        从文本中提取JSON负载
        """
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end+1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None
        return None
