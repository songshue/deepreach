from __future__ import annotations

from atexit import register
from gc import enable
import logging
import re
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any, Callable, Iterator

from aiohttp import payload
from hello_agents import HelloAgentsLLM, ToolAwareSimpleAgent
from hello_agents.tools import ToolRegistry
from hello_agents.tools.builtin.note_tool import NoteTool

from config import Configuration
from prompt import (
    report_writer_instructions,
    task_summarizer_instructions,
    todo_planner_system_prompt,
)
from model import SummaryState, SummaryStateOutput, TodoItem
from services.planner import PlanningService
from services.reporter import ReportingService
from services.search import dispatch_search, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)

class DeepResearchAgent:
    """
    深度研究智能体，负责协调研究、规划、总结和报告任务。
    """
    def __init__(self,config:Configuration | None = None) -> None:
        """
        初始化深度研究智能体。

        :param config: 配置对象，若未提供则从环境变量加载。
        """
        self.config = config or Configuration.from_env()
        self.llm = self._init_llm()
        self.note_tool = (
            NoteTool(
                workspace=self.config.notes_workspace
            )
            if self.config.enable_notes
            else None
        )

        self.tools_registry : ToolRegistry | None = None
        if self.note_tool:
            register = ToolRegistry()
            register.register_tool(self.note_tool)
            self.tools_registry = register

        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self._tool_event_sink_enabled = False
        self._state_lock = Lock()
        self.todo_agent = self._create_tool_aware_agent(
            name = "研究规划专家",
            system_prompt = todo_planner_system_prompt.strip(),
        )
        self.report_agent = self._create_tool_aware_agent(
            name = "报告撰写专家",
            system_prompt = report_writer_instructions.strip(),
        )

        self._summarizer_factory:Callable[[], ToolAwareSimpleAgent] = lambda: self._create_tool_aware_agent(
            name = "任务总结专家",
            system_prompt = task_summarizer_instructions.strip(),
        )

        self.planner = PlanningService(self.todo_agent,self.config)
        self.summarizer = SummarizationService(
            self._summarizer_factory,
            self.config,
        )
        self.reporting = ReportingService(
            self.report_agent,
            self.config,
        )
        self._last_search_notices:list[str] = []

    def _init_llm(self) -> HelloAgentsLLM:
        """
        初始化LLM模型。

        :return: 初始化后的LLM模型实例。
        """
        llm_kwargs:dict[str,Any] = {"temperature": 0.0}
        model_id = self.config.llm_model_id or self.config.local_llm
        if model_id:
            llm_kwargs["model"] = model_id
        
        provider = (self.config.llm_provider or "").lower()
        if provider:
            llm_kwargs["provider"] = provider
        if provider == "ollama":
            llm_kwargs["base_url"] = self.config.sanitized_ollama_url()
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif provider == "lmstudio":
            llm_kwargs["base_url"] = self.config.lmstudio_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
        else:
            if self.config.llm_base_url:
                llm_kwargs["base_url"] = self.config.llm_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
        
        return HelloAgentsLLM(**llm_kwargs)

    def _create_tool_aware_agent(self,*, name: str, system_prompt: str) -> ToolAwareSimpleAgent:
        """
        创建一个工具感知智能体。

        :param name: 智能体名称。
        :param system_prompt: 智能体系统提示。
        :return: 初始化后的工具感知智能体实例。
        """
        return ToolAwareSimpleAgent(
            name=name,
            system_prompt=system_prompt,
            llm=self.llm,
            enable_tool_calling = self.tools_registry is not None,
            tool_registry=self.tools_registry,
            tool_call_listener = self._tool_tracker.record,
            
        )

    def _set_tool_event_sink(self,sink:Callable[[dict[str,Any]],None] | None) -> None:
        """
        设置工具事件接收器。

        :param sink: 接收工具事件的回调函数。
        """
        self._tool_event_sink_enabled = sink is not None
        self._tool_tracker.set_event_sink(sink)

    def run(self,topic:str) -> SummaryStateOutput:
        """
        运行深度研究智能体，协调研究、规划、总结和报告任务。

        :param topic: 研究主题。
        """
        state = SummaryState(research_topic=topic)
        state.todo_items = self.planner.plan_todo_list(state)
        self._drain_tool_events(state)
        if not state.todo_items:
            logger.info("No TODO items generated; falling back to single task")
            state.todo_items = [self.planner.create_fallback_task(state)]
        for task in state.todo_items:
            self._execute_task(state,task,emit_stream=False)
        
        report = self.reporting.generate_report(state)
        self._drain_tool_events(state)
        state.structured_report = report
        state.running_summary = report
        self._persist_final_report(state,report)
        return SummaryStateOutput(
            running_summary=report,
            report_markdown=report,
            todo_items=state.todo_items,
        )
    
    def run_stream(self,topic:str)-> Iterator[dict[str,Any]]:
        """
        以流式方式运行深度研究智能体，协调研究、规划、总结和报告任务。

        :param topic: 研究主题。
        :return: 一个迭代器，每次迭代返回一个包含研究状态的字典。
        """
        state = SummaryState(research_topic=topic)
        logger.debug("Starting streaming research: topic=%s", topic)
        yield {"type": "status", "message": "初始化研究流程"}


        state.todo_items = self.planner.plan_todo_list(state)
        for event in self._drain_tool_events(state):
            yield event
        if not state.todo_items:
            state.todo_items = [self.planner.create_fallback_task(state)]
            
        channel_map:dict[int,dict[str,Any]] = {}
        for index,task in enumerate(state.todo_items,start=1):
            token = f"task_{task.id}"
            task.stream_token = token
            channel_map[task.id] = {"token":token,"step":index}
        
        yield{
            "type":"todo_list",
            "tasks":[self._serialize_task(t) for t in state.todo_items],
            "step":0,
        }
        event_queue:Queue[dict[str,Any]] = Queue()

        def enqueue(
            event:dict[str,Any],
            *,
            task:TodoItem | None = None,
            step_override: int | None = None,
        ) -> None:
            """
            将事件加入队列，可选指定任务ID和步骤覆盖。

            参数:
                event: 要加入队列的事件字典。
                task: 可选，关联的任务对象，用于获取任务ID。
                step_override: 可选，指定事件的步骤编号，用于覆盖默认值。
            """
            payload = dict(event)
            target_task_id = payload.get("task_id")
            if task is not None:
                target_task_id = task.id
                payload["task_id"] = task.id
            channel = channel_map.get(target_task_id ) if target_task_id is not None else None
            if channel:
                payload.setdefault("step", channel["step"])
                payload["stream_token"] = channel["token"]
            if step_override is not None:
                payload["step"] = step_override
            event_queue.put(payload)
        
        def tool_event_sink(event:dict[str,Any]) -> None:
            """
            工具事件接收器，将工具调用事件加入队列。

            参数:
                event: 要加入队列的工具调用事件字典。
            """
            enqueue(event,task=task)
        self._set_tool_event_sink(tool_event_sink)
        threads:list[Thread] = []

        def worker(task:TodoItem,step:int) -> None:
            """
            任务执行器，处理单个任务的研究流程。

            参数:
                task: 要执行的任务对象。
                step: 任务在研究流程中的步骤编号。
            """
            try:
                enqueue(
                    {
                       "type": "task_status",
                        "task_id": task.id,
                        "status": "in_progress",
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path, 
                    },
                    task=task,
                )
                for event in self._execute_task(state,task,emit_stream=True,step=step):
                    enqueue(event,task=task)
            except Exception as exc:  # pragma: no cover - defensive guardrail
                logger.exception("Task execution failed", exc_info=exc)
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "failed",
                        "detail": str(exc),
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )
            finally:
                enqueue({"type": "__task_done__", "task_id": task.id})
        
        for task in state.todo_items:
            step = channel_map.get(task.id,{}).get("step",0)
            thread = Thread(target=worker,args=(task,step))
            threads.append(thread)
            thread.start()
        active_workers = len(state.todo_items)
        finished_workers = 0
        try:
            while finished_workers < active_workers:
                event = event_queue.get()
                if event["type"] == "__task_done__":
                    finished_workers += 1
                    continue
                yield event
            
            while True:
                try:
                    event = event_queue.get_nowait()
                except Empty:
                    break

                if event["type"] == "__task_done__":
                    yield event
        finally:
            self._set_tool_event_sink(None)
            for thread in threads:
                thread.join()
        
        report = self.reporting.generate_report(state)
        final_step = len(state.todo_items)+1
        for event in self._drain_tool_events(state,step=final_step):
            yield event
        
        state.structured_report = report
        state.running_summary = report

        note_event = self._persist_final_report(state,report)
        if note_event:
            yield note_event
        
        yield {
            "type": "final_report",
            "report": report,
            "note_id": state.report_note_id,
            "note_path": state.report_note_path,
        }
        yield{"type":"done"}

    def _execute_task(
        self,
        state:SummaryState,
        task:TodoItem,
        *,
        emit_stream:bool,
        step:int | None = None,
        ) -> Iterator[dict[str,Any]]:
        """
        执行单个任务的研究流程。

        参数:
            state: 当前的研究状态对象，包含研究信息和任务列表。
            task: 要执行的任务对象。
            emit_stream: 是否在执行过程中实时发送事件流。
            step: 任务在研究流程中的步骤编号。

        返回:
            一个迭代器，生成任务执行过程中的事件字典。
        """
        task.status = "in_progress"
        search_result, notices, answer_text, backend = dispatch_search(
            task.query,
            self.config,
            state.research_loop_count,
        )
        self._last_search_result = notices
        task.notices = notices

        if emit_stream:
            for event in self._drain_tool_events(state,step=step):
                yield event
        else:
            self._drain_tool_events(state,step=step)
        
        if notices and emit_stream:
            for notice in notices:
                if notice:
                    yield{
                        "type":"status",
                        "message":notice,
                        "task_id":task.id,
                        "step":step,
                    }

        if not search_result or not search_result.get("results"):
            task.status = "skipped"
            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "skipped",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                }
            else:
                self._drain_tool_events(state)
            return
        else:
            if not emit_stream:
                self._drain_tool_events(state)

        sources_summary,context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )
        task.sources_summary = sources_summary
        with self._state_lock:
            state.web_research_results.append(context)
            state.sources_gathered.append(sources_summary)
            state.research_loop_count += 1

        summary_text:str | None = None

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "sources",
                "task_id": task.id,
                "latest_sources": sources_summary,
                "raw_context": context,
                "step": step,
                "backend": backend,
                "note_id": task.note_id,
                "note_path": task.note_path,
            }
            summary_stream, summary_getter = self.summarizer.stream_task_summary(state, task, context)
            try:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                for chunk in summary_stream:
                    if chunk:
                        yield {
                            "type": "task_summary_chunk",
                                "task_id": task.id,
                                "content": chunk,
                                "note_id": task.note_id,
                                "step": step,
                        }
                    for event in self._drain_tool_events(state, step=step):
                        yield event
            finally:
                summary_text = summary_getter()
        else:
            summary_text = self.summarizer.summarize_task(state, task, context)
            self._drain_tool_events(state)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status",
                "task_id": task.id,
                "status": "completed",
                "summary": task.summary,
                "sources_summary": task.sources_summary,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": step,
            }
        else:
            self._drain_tool_events(state)



    @property
    def _tool_call_events(self) -> list[dict[str,Any]]:
        """
        获取当前工具调用事件列表。

        返回:
            包含所有工具调用事件的列表。
        """
        return self._tool_tracker.as_dict()


    def _serialize_task(self,task:TodoItem) -> dict[str,Any]:
        """
        将任务数据类转换为前端可序列化的字典。

        参数:
            task: 要序列化的任务对象。

        返回:
            包含任务ID、描述和流令牌的字典。
        """
        return{
            "id":task.id,
            "title": task.title,
            "intent": task.intent,
            "query": task.query,
            "status": task.status,
            "summary": task.summary,
            "sources_summary": task.sources_summary,
            "note_id": task.note_id,
            "note_path": task.note_path,
            "stream_token": task.stream_token,
        }

    def _persist_final_report(self,state:SummaryState,report:str) -> dict[str,Any] | None:
        """
        将最终报告持久化到笔记中。

        参数:
            state: 当前的研究状态对象，包含笔记信息。
            report: 要持久化的最终报告内容。

        返回:
            若成功持久化，则返回包含笔记ID和路径的事件字典；否则返回None。
        """
        if not self.note_tool or not report or not report.strip():
            return None
        note_title = f"研究报告：{state.research_topic}".strip() or "研究报告"
        tags = ["deep_research", "report"]
        content = report.strip()

        note_id = self._find_existing_report_note_id(state)
        response = ""

        if note_id:
            response = self.note_tool.run(
                {
                    "action": "update",
                    "note_id": note_id,
                    "title": note_title,
                    "tags": tags,
                    "content": content,
                }
            )
            if response.startswith("❌"):
                note_id = None
        if not note_id:
            response = self.note_tool.run(
                {
                    "action": "create",
                    "note_type": "conclusion",
                    "title": note_title,
                    "tags": tags,
                    "content": content,
                }
            )
            note_id =self._extract_note_id_from_text(response)
        if not note_id:
            return None
        state.report_note_id = note_id
        if self.config.notes_workspace:
            note_path = Path(self.config.notes_workspace) / f"{note_id}.md"
            state.report_note_path = str(note_path)
        else:
            note_path = None
        
        payload = {
            "type": "report_note",
            "note_id": note_id,
            "title": note_title,
            "content": content,
        }
        if note_path:
            payload["path"] = str(note_path)
        return payload


    def _find_existing_report_note_id(self,state:SummaryState) -> str | None:
        """
        查找已存在的研究报告笔记ID。

        参数:
            state: 当前的研究状态对象，包含笔记信息。

        返回:
            若找到已存在的研究报告笔记ID，则返回该ID；否则返回None。
        """
        if state.report_note_id:
            return state.report_note_id
        for event in reversed(self._tool_tracker.as_dict()):
            if event.get("tool") != "note":
                continue

            parameters = event.get("parameters",{})
            if not isinstance(parameters,dict):
                continue
            action = parameters.get("action")
            if action not in {"create","update"}:
                continue

            note_type = parameters.get("note_type")
            if note_type != "conclusion":
                title = parameters.get("title")
                if not(isinstance(title,str) and title.startswith("研究报告")):
                    continue
            note_id = parameters.get("note_id")
            if not note_id:
                note_id = self._tool_tracker._extract_note_id(event.get("result", ""))  # type: ignore[attr-defined]

            if note_id:
                return note_id

        return None



    @staticmethod
    def _extract_note_id_from_text(response:str) -> str | None:
        """
        从文本中提取笔记ID。

        参数:
            response: 包含笔记ID的文本。

        返回:
            若提取到笔记ID，则返回该ID；否则返回None。
        """
        if not response:
            return None

        match = re.search(r"ID:\s*([^\n]+)", response)
        if not match:
            return None

        return match.group(1).strip()



    def _drain_tool_events(self,state:SummaryState,*,
        step: int | None = None,) -> list[dict[str,Any]]:
        """
        排空工具事件队列，将工具调用产生的事件收集并返回。

        参数:
            state: 当前的研究状态对象，用于记录事件。
            step: 可选，当前步骤的编号，用于标记事件来源步骤。

        返回:
            若工具事件接收器未启用，则返回收集到的事件列表；否则返回空列表。
        """
        events = self._tool_tracker.drain(state, step=step)
        if self._tool_event_sink_enabled:
            return []
        return events

    def run_deep_research(topic:str,config:Configuration |None =None) -> SummaryStateOutput:
        """
        执行深度研究，根据给定的主题进行研究。

        参数:
            topic: 研究主题，用于指导研究内容。
            config: 可选，配置对象，包含研究参数。若未提供，则使用默认配置。

        返回:
            包含研究状态输出的SummaryStateOutput对象。
        """
        agent = DeepResearchAgent(config=config)
        return agent.run(topic)

