"""Scripted offline model: drives the real LangChain/LangGraph tool loop in a fixed order without any LLM call."""
import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .tools import ORDER


class OfflineScriptModel(BaseChatModel):
    @property
    def _llm_type(self):
        return 'scripted-offline'

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        completed = {m.name for m in messages if isinstance(m, ToolMessage)}
        for name in ORDER:
            if name not in completed:
                call = {'name': name, 'args': {}, 'id': f'offline-{name}', 'type': 'tool_call'}
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[call]))])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.closing(messages)))])

    @staticmethod
    def closing(messages):
        """Quote the delivery receipt verbatim; the scripted model adds no judgement of its own."""
        def summary_of(name):
            message = next((m for m in reversed(messages) if isinstance(m, ToolMessage) and m.name == name), None)
            try:
                return json.loads(message.content).get('summary') if message else None
            except (TypeError, ValueError):
                return None
        diagnosis = summary_of('diagnose_weaknesses')
        return (f'离线脚本流程结束：{summary_of("finalize_delivery") or "未取得交付回执"}。'
                + (f'薄弱环节诊断：{diagnosis}；建议书为规则库生成。' if diagnosis else '')
                + '结论以 result.json 与报告正文为准；本次由脚本模型按固定顺序调用工具，未调用大模型。')
