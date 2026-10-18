// Same-origin JSON API client with readable error messages.

export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error('无法连接本地服务，请确认工作台服务已启动');
  }
  const text = await response.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!response.ok) {
    if(response.status===404 && data?.error==='地址不存在')throw new Error('本地后端版本过旧，缺少此接口。请重新运行“启动演示.cmd”后刷新页面。');
    const error = new Error((data && data.error) || `请求失败（HTTP ${response.status}）`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export function postJson(path, body) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

export function postZip(path, file) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/zip' }, body: file });
}
