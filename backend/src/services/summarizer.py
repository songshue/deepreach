"""Task summarization utilities."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Tuple

from hello_agents import ToolAwareSimpleAgent

from model import SummaryState, TodoItem
from config import Configuration
from utils import strip_thinking_tokens,strip_tool_calls
from services.notes import build_note_guidance

class SummarizationService:
    """处理同步和流式任务总结。"""
    def __init__(
        self,
        summarizer_factory: Callable[[], ToolAwareSimpleAgent],
        config: Configuration,
    ) -> None:
        self._agent_factory = summarizer_factory
        self._config = config

    def summarize_task(
        self,
        state: SummaryState,
        task: TodoItem,
        context: str,
    ) -> str:
        """
        对任务进行总结。
        """
        prompt = self._build_prompt(state,task,context)
        agent = self._agent_factory()
        try:
            response = agent.run(prompt)
        finally:
            agent.clear_history()
        
        summary_text = response.strip()
        if self._config.strip_thinking_tokens:
            summary_text = strip_thinking_tokens(summary_text)
        summary_text = strip_tool_calls(summary_text).strip()
        return summary_text or "暂无可用信息"

    def stream_task_summary(
        self,
        state: SummaryState,
        task: TodoItem,
        context: str,
    ) -> Tuple[Iterator[str], Callable[[], str]]:
        """
        流式处理任务总结。
        """
        prompt = self._build_prompt(state,task,context)
        agent = self._agent_factory()
        remove_thinking= self._config.strip_thinking_tokens
        raw_buffer = ""
        visible_output = ""
        emit_index = 0

        def flush_buffer() -> Iterator[str]:
            nonlocal raw_buffer,emit_index
            while True:
                start = raw_buffer.find("<think>",emit_index)
                if start == -1:
                    if emit_index < len(raw_buffer):
                        segment =  raw_buffer[emit_index:]
                        emit_index = len(raw_buffer)
                        if segment:
                            yield segment
                    break
                if start > emit_index:
                    segment = raw_buffer[emit_index:start]
                    emit_index = start
                    if segment:
                        yield segment
                end = raw_buffer.find("</think>",start)
                if end == -1:
                    break
                emit_index = end+len("</think>")
        def generator() -> Iterator[str]:
            nonlocal raw_buffer,visible_output,emit_index
            try:
                for chunk in agent.stream_run(prompt):
                    raw_buffer += chunk
                    if remove_thinking:
                        for segment in flush_buffer():
                            visible_output += segment
                            if segment:
                                yield segment
                    else:
                        visible_output += chunk
            finally:
                if remove_thinking:
                    for segment in flush_buffer():
                        visible_output += segment
                        if segment:
                            yield segment_history()
                agent.clear_history()

        def get_summary() -> str:
            if remove_thinking:
                cleaned = strip_thinking_tokens(visible_output)
            else:
                cleaned = visible_output

            return strip_tool_calls(cleaned).strip()

        return generator(), get_summary

    def _build_prompt(
        self,
        state: SummaryState,
        task: TodoItem,
        context: str,
    ) -> str:
        """
        构建任务总结提示。
        """
        return (
            f"任务主题：{state.research_topic}\n"
            f"任务名称：{task.title}\n"
            f"任务目标：{task.intent}\n"
            f"检索查询：{task.query}\n"
            f"任务上下文：\n{context}\n"
            f"{build_note_guidance(task)}\n"
            "请按照以上协作要求先同步笔记，然后返回一份面向用户的 Markdown 总结（仍遵循任务总结模板）。"
        )
            
