"""Run the report agent for one task and record real events (tool calls, results, timings) in the store."""
import json
import os
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from ..agent.offline import OfflineScriptModel
from ..agent.runtime import build_agent, configured_model
from ..agent.models import create_model, public_config, safe_error
from ..agent.tools import TOOL_TITLES
from .store import now

FILE_TYPES = {
    'report.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'report.pdf': 'application/pdf',
    'report.html': 'text/html; charset=utf-8',
    'advice.md': 'text/markdown; charset=utf-8',
    'diagnosis.json': 'application/json; charset=utf-8',
    'result.json': 'application/json; charset=utf-8',
    'qa.json': 'application/json; charset=utf-8',
    'input.json': 'application/json; charset=utf-8',
    'receipt.json': 'application/json; charset=utf-8',
}
ITEM_FIELDS = ('id', 'stage', 'gate', 'final', 'component', 'component_kind', 'component_label', 'section_label', 'direction',
               'direction_label', 'level', 'kind', 'kind_label', 'title', 'group', 'demand', 'capacity', 'unit', 'ratio', 'phi',
               'status', 'status_label', 'verdict', 'reason', 'provisional', 'locator', 'before')
RESULT_FIELDS = ('status', 'status_label', 'reason', 'evaluated', 'engineering_release', 'issues', 'gates', 'plastic',
                 'plastic_after', 'stops', 'provisional', 'has_retrofit', 'counts')


def input_summary(data):
    project = data.get('project') or {}
    variant = data.get('variant') or {}
    return {'bridge_name': f"{project.get('route', '')} {project.get('stake', '')}".strip() or data.get('bridge_id', '未命名桥梁'),
            'bridge_type': project.get('bridge_type'), 'span_text': project.get('span_text'), 'bridge_id': data.get('bridge_id'),
            'model_revision': data.get('model_revision'), 'data_kind': data.get('data_kind'), 'variant_title': variant.get('title'),
            'components': len(data.get('components') or []), 'checks': len(data.get('checks') or []),
            'retrofit_checks': len((data.get('retrofit') or {}).get('checks') or [])}


def tool_detail(content):
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return ('已读取' + f'（{len(content)} 字）') if isinstance(content, str) else '已返回', None
    if isinstance(payload, dict):
        return payload.get('summary') or '已返回', payload.get('status')
    return '已返回', None


class Runner:
    def __init__(self, store, data_dir, pool):
        self.store = store
        self.data_dir = Path(data_dir)
        self.pool = pool

    def submit(self, package, source, task, mode, model_config=None, template_path=None):
        ident = uuid.uuid4().hex
        run = {'id': ident, 'status': 'queued', 'mode': mode, 'source': source, 'task': task, 'created_at': now(),
               'started_at': None, 'finished_at': None, 'input_summary': input_summary(package.data), 'report_status': None,
               'result': None, 'items': [], 'diagnosis': None, 'advice': None, 'qa': None, 'rendering': None, 'files': [], 'pages': [], 'agent_message': None,
               'error': None}
        run['model_config'] = public_config(model_config) if model_config else None
        run['template'] = template_path.name if template_path else '系统母版'
        self.store.save(run)
        self.store.event(ident, 'queued', '任务已创建', '离线脚本模型：按固定顺序调用真实工具，不调用大模型' if mode == 'offline'
                         else '真实模型：由已配置的大模型选择工具，费用以服务商账单为准')
        self.pool.submit(self.execute, run, package, task, model_config, template_path)
        return run

    def execute(self, run, package, task, model_config=None, template_path=None):
        ident = run['id']
        out = self.data_dir / 'runs' / ident
        out.mkdir(parents=True, exist_ok=False)
        os.environ['LANGSMITH_TRACING'] = 'false'
        os.environ['LANGCHAIN_TRACING_V2'] = 'false'
        started = time.perf_counter()
        try:
            run.update(status='running', started_at=now())
            self.store.save(run)
            self.store.event(ident, 'started', 'Agent 开始执行', 'LangChain create_agent + LangGraph 工具循环')
            model = OfflineScriptModel() if run['mode'] == 'offline' else create_model(model_config) if model_config else configured_model()
            pending = {}
            with closing(sqlite3.connect(out / 'checkpoints.sqlite', check_same_thread=False)) as connection:
                graph, state = build_agent(model, package, out, SqliteSaver(connection), template_path=template_path)
                config = {'configurable': {'thread_id': ident}, 'recursion_limit': 60}
                final_message = None
                for chunk in graph.stream({'messages': [{'role': 'user', 'content': task}]}, config, stream_mode='updates'):
                    for update in chunk.values():
                        if not isinstance(update, dict):
                            continue
                        for message in update.get('messages', []):
                            for call in getattr(message, 'tool_calls', None) or []:
                                pending[call['id']] = time.perf_counter()
                                self.store.event(ident, 'tool_call', TOOL_TITLES.get(call['name'], call['name']), '执行中', tool=call['name'])
                            if message.type == 'tool':
                                elapsed = int((time.perf_counter() - pending.pop(message.tool_call_id, time.perf_counter())) * 1000)
                                detail, status = tool_detail(message.content)
                                if message.name == 'evaluate_gates' and state['result'] is not None:
                                    self.publish_result(run, state['result'])
                                if message.name == 'diagnose_weaknesses' and state['diagnosis'] is not None:
                                    run['diagnosis'] = state['diagnosis']
                                    self.store.save(run)
                                self.store.event(ident, 'tool_result', TOOL_TITLES.get(message.name, message.name), detail,
                                                 tool=message.name, elapsed_ms=elapsed, status=status)
                            elif message.type == 'ai' and message.content:
                                final_message = message.content if isinstance(message.content, str) else '\n'.join(b.get('text', '') for b in message.content if isinstance(b, dict) and b.get('type') == 'text')
                                if final_message:
                                    self.store.event(ident, 'agent_message', 'Agent 执行说明', final_message[:6000])
                            usage = getattr(message, 'usage_metadata', None)
                            if usage:
                                self.store.event(ident, 'usage', '模型用量', '服务商返回的 token 统计', usage=usage)
            if state['receipt'] is None:
                raise RuntimeError('Agent 结束时未完成交付')
            self.complete(run, state, out, final_message, started)
        except Exception as exc:  # noqa: BLE001 — report any failure to the page without leaking internals
            run.update(status='failed', finished_at=now(),
                       error=f'任务未完成（{type(exc).__name__}），未自动重试。请检查交接包或运行环境后重新发起。')
            self.store.save(run, event={'type': 'error', 'title': '任务执行失败', 'detail': run['error']})

    def publish_result(self, run, result):
        """Expose the judgement as soon as the engine returns, before the slower rendering steps finish."""
        run.update(result={k: result.get(k) for k in RESULT_FIELDS},
                   items=[{k: item.get(k) for k in ITEM_FIELDS} for item in result['items']])
        self.store.save(run)

    def complete(self, run, state, out, final_message, started):
        ident = run['id']
        result = state['result']
        files = [{'name': name, 'url': f'/api/runs/{ident}/files/{name}', 'bytes': (out / name).stat().st_size}
                 for name in FILE_TYPES if (out / name).is_file()]
        pages = sorted(p.name for p in (out / 'pages').glob('page-*.jpg')) if (out / 'pages').is_dir() else []
        self.publish_result(run, result)
        run.update(
            status='completed', finished_at=now(), report_status=result['status'],
            qa=state['qa'], rendering=state['rendering'], files=files, diagnosis=state['diagnosis'], advice=state['advice'],
            pages=[f'/api/runs/{ident}/pages/{n}' for n in range(1, len(pages) + 1)],
            agent_message=final_message, duration_ms=int((time.perf_counter() - started) * 1000))
        self.store.save(run, event={'type': 'completed', 'title': '任务完成',
                                   'detail': f"报告结论：{result['status_label']}（任务完成不等于验算通过）",
                                   'status': result['status']})
