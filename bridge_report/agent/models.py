"""Explicit protocol adapters. Credentials live only in the local server's memory."""
import os
from urllib.parse import urlsplit

PROTOCOLS = ('openai-chat', 'openai-responses', 'anthropic-messages')


def environment_config():
    return dict(protocol=os.getenv('BRIDGE_AGENT_PROTOCOL', 'openai-chat'),
                model=os.getenv('BRIDGE_AGENT_MODEL', ''), base_url=os.getenv('BRIDGE_AGENT_BASE_URL', ''),
                api_key=os.getenv('BRIDGE_AGENT_API_KEY', ''), max_tokens=4096)


def validate_config(value):
    if not isinstance(value, dict):
        raise ValueError('模型配置必须是 JSON 对象')
    cfg = {key: value.get(key, '') for key in ('protocol', 'model', 'base_url', 'api_key')}
    if cfg['protocol'] not in PROTOCOLS:
        raise ValueError('请选择支持的模型协议')
    for key in ('model', 'base_url', 'api_key'):
        if not isinstance(cfg[key], str) or not cfg[key].strip() or len(cfg[key]) > 4096:
            raise ValueError('模型名称、接口地址和 API Key 均须填写')
        cfg[key] = cfg[key].strip()
    url = urlsplit(cfg['base_url'])
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('接口地址须为 http(s) URL，不含密钥、查询参数或片段')
    cfg['base_url'] = cfg['base_url'].rstrip('/')
    suffix = {'openai-chat': '/chat/completions', 'openai-responses': '/responses', 'anthropic-messages': '/messages'}[cfg['protocol']]
    if cfg['base_url'].endswith(suffix):
        cfg['base_url'] = cfg['base_url'][:-len(suffix)]
    if cfg['protocol'] in ('openai-chat', 'openai-responses') and not urlsplit(cfg['base_url']).path:
        cfg['base_url'] += '/v1'
    if cfg['protocol'] == 'anthropic-messages' and cfg['base_url'].endswith('/v1'):
        cfg['base_url'] = cfg['base_url'][:-3]
    tokens = value.get('max_tokens', 4096)
    if isinstance(tokens, bool) or not isinstance(tokens, int) or not 128 <= tokens <= 32768:
        raise ValueError('最大输出 token 数须为 128—32768 的整数')
    cfg['max_tokens'] = tokens
    return cfg


def public_config(cfg):
    return {key: cfg.get(key) for key in ('protocol', 'model', 'base_url', 'max_tokens')} | {'configured': bool(cfg.get('api_key'))}


def create_model(config):
    cfg = validate_config(config)
    common = dict(model=cfg['model'], base_url=cfg['base_url'], api_key=cfg['api_key'], max_retries=0,
                  timeout=120, max_tokens=cfg['max_tokens'])
    if cfg['protocol'] == 'anthropic-messages':
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(**common)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(**common, use_responses_api=cfg['protocol'] == 'openai-responses', store=False)


def safe_error(exc):
    status = getattr(exc, 'status_code', None)
    if status == 401:
        return '鉴权失败，请核对 API Key 和模型访问权限。'
    if status == 403:
        return '服务商拒绝访问（HTTP 403），请检查密钥权限、IP 限制或站点防护规则。'
    if status == 429:
        return '服务商限流或额度不足，请检查账户后手动重试。'
    if status == 404:
        return '服务商接口不存在（HTTP 404），请核对 /v1 地址、协议和模型 ID。'
    if status in (400, 422):
        return '接口不接受请求，请核对协议、地址、模型名称及工具调用支持。'
    if 'Timeout' in type(exc).__name__:
        return '接口等待超时，未自动重试。'
    return '接口请求失败，请检查服务商状态或本地网络；未自动重试。'


def test_connection(config):
    """One explicit, bounded tool-call request; no project data is sent."""
    tool = {'name': 'connection_ok', 'description': 'Confirm tool calling works.',
            'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
    model = create_model(config).bind_tools([tool])
    response = model.invoke('Call connection_ok once to confirm the connection. Do not output any other content.')
    ok = any(c.get('name') == 'connection_ok' for c in response.tool_calls)
    return {'ok': ok, 'message': '连接成功，工具调用可用。' if ok else '接口可响应，但未返回工具调用；请检查模型是否支持工具。',
            'usage': response.usage_metadata}
