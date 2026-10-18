import { $, h, fmtDuration } from './dom.js';
import { api, postJson } from './api.js';
import { createModelView } from './model-view.js';

export function initWorkspace({getSelection, onReady, onConfig}) {
  const model = createModelView();
  let preflight = null, templateId = null, visualEpoch = 0, rawIds = [], savedKey = false;
  function keyState(cfg){savedKey=Boolean(cfg.model_config?.configured);$('modelKey').required=!savedKey;$('modelKey').placeholder=savedKey?'已在服务内存保存；同一接口留空可复用':'仅保留在本地服务内存';}
  function sourceBody() { const s=getSelection(); if(!s)return null;return s.kind==='scenario'?{scenario_id:s.id}:s.kind==='zip'?{package_id:s.packageId}:{package:s.package}; }
  function reset() {
    preflight=null;rawIds=[];$('confirmInput').checked=false;$('confirmInput').disabled=true;$('readinessBadge').textContent='尚未检查';delete $('readinessBadge').dataset.state;
    $('intakeIssues').replaceChildren();$('intakeInventory').replaceChildren(h('p',{class:'muted',text:'选择案例或导入交接包后，检查上游资料。'}));$('rawInventory').replaceChildren();onReady(false);
  }
  $('confirmInput').addEventListener('change',()=>onReady(Boolean(preflight && $('confirmInput').checked), preflight?.ready));
  $('inspectBtn').addEventListener('click',async()=>{
    const body=sourceBody(), selection=getSelection();if(!body)return;
    $('inspectBtn').disabled=true;$('readinessBadge').textContent='检查中…';
    try {const result=await postJson('/api/inspect',body);if(getSelection()!==selection)return;preflight=result;
      $('intakeInventory').replaceChildren(...result.inventory.map(r=>h('div',{class:'inventory-item'},h('strong',{text:r.count}),h('span',{text:r.name}))));
      $('intakeIssues').replaceChildren(h('p',{text:result.message}),...result.issues.slice(0,30).map(x=>h('p',{text:x})),...(result.notes||[]).map(x=>h('p',{text:`原件复核提示：${x}`})));
      $('readinessBadge').textContent=result.ready?'检查完成，可以确认':'交接包待补正，只能生成补正通知';$('readinessBadge').dataset.state=result.ready?'ok':'warn';$('confirmInput').disabled=false;onReady($('confirmInput').checked,result.ready);
    } catch(e){$('readinessBadge').textContent='检查失败';$('readinessBadge').dataset.state='error';$('intakeIssues').textContent=e.message;}finally{$('inspectBtn').disabled=false;}
  });
  function showDrawing(record) {
    if(record.preview){$('drawingPreview').src=record.preview;$('drawingPreview').hidden=false;$('drawingLink').href=record.preview;}
    $('drawingCaption').textContent=record.drawing_name?`${record.drawing_name} · 第 ${record.drawing_page||1} / ${record.drawing_pages} 页`:(record.name||'');
    $('drawingFacts').replaceChildren(...Object.entries(record.candidates||{}).filter(([,v])=>v.length).map(([k,v])=>h('p',{text:`${k}（待核对）：${v.join('、')}`})));
  }
  async function loadVisual(id){const epoch=++visualEpoch;model.set(null);$('drawingPreview').hidden=true;$('drawingLink').removeAttribute('href');$('drawingCaption').textContent='未载入图纸';$('drawingFacts').replaceChildren();$('visualSource').textContent='暂无模型';
    if(!['golden-76K','golden-53K'].includes(id))return;
    try{const result=await api(`/api/case-assets/${id}`);if(epoch!==visualEpoch)return;model.set(result.geometry||null);showDrawing(result);$('visualSource').textContent=result.model_name||'未提供模型';$('visualNote').textContent=result.note||'';}catch(e){$('visualSource').textContent=e.message;}
  }
  $('rawUploadBtn').addEventListener('click',()=>$('rawFiles').click());
  $('rawFiles').addEventListener('change',async e=>{
    const files=Array.from(e.target.files), selection=getSelection();e.target.value='';$('rawUploadBtn').disabled=true;
    for(const file of files){const row=h('div',{class:'source-file'},h('strong',{text:file.name}),h('small',{text:'正在识别…'}));$('rawInventory').append(row);
      try{if(file.size>50*1024*1024)throw new Error('文件不超过 50 MB');const r=await api('/api/intake',{method:'POST',headers:{'X-Filename':encodeURIComponent(file.name),'Content-Type':'application/octet-stream'},body:file});
        if(getSelection()!==selection)continue;rawIds.push(r.id);row.replaceChildren(h('strong',{text:`${r.name} · ${r.status}`}),h('small',{text:r.detail}));
        if(r.geometry){const b=h('button',{text:'查看模型'});b.onclick=async()=>{model.set(await api(r.geometry));$('visualSource').textContent=r.name;};row.append(b);model.set(await api(r.geometry));$('visualSource').textContent=r.name;}
        if(r.preview){const b=h('button',{text:'查看图纸识别'});b.onclick=()=>showDrawing(r);row.append(b);showDrawing(r);}
        if(r.pages){const page=h('input',{type:'number',min:1,max:r.pages,value:1,'aria-label':'图纸页码'}),view=h('button',{text:'查看本页'}),recognize=h('button',{text:'识别本页'}),output=h('div');
          view.onclick=()=>{const url=r.preview+'?page='+page.value;$('drawingPreview').src=url;$('drawingPreview').hidden=false;$('drawingLink').href=url;$('drawingCaption').textContent=`${r.name} · 第 ${page.value}/${r.pages} 页`;};
          recognize.onclick=async()=>{recognize.disabled=true;output.textContent='正在识别本页…';try{const result=await postJson('/api/intake/recognize',{id:r.id,page:Number(page.value)});output.replaceChildren(h('p',{text:`${result.method} · ${result.message}`}),...Object.entries(result.candidates).filter(([,v])=>v.length).map(([k,v])=>h('p',{text:`${k}：${v.join('、')}`})),h('details',{},h('summary',{text:'识别全文'}),h('pre',{text:result.extracted_text})));view.click();}catch(e){output.textContent=e.message;}finally{recognize.disabled=false;}};
          row.append(h('div',{class:'drawing-controls'},'页码',page,`/ ${r.pages}`,view,recognize),output);}
        if(r.extracted_text){const d=h('details',{},h('summary',{text:'查看识别文字（需核对）'}),h('pre',{text:r.extracted_text}));row.append(d);}
      }catch(error){row.replaceChildren(h('strong',{text:file.name}),h('small',{text:error.message}));}
    }$('rawUploadBtn').disabled=false;
  });
  const modelBody=()=>({protocol:$('modelProtocol').value,base_url:$('modelUrl').value,model:$('modelName').value,...($('modelKey').value?{api_key:$('modelKey').value}:{use_saved_key:savedKey}),max_tokens:Number($('modelTokens').value)});
  $('modelProtocol').addEventListener('change',()=>{$('protocolHint').textContent=$('modelProtocol').value==='anthropic-messages'?'Claude 填写服务基础地址，如 https://api.anthropic.com；也可粘贴 /v1/messages 完整端点。':'OpenAI 可填写站点地址（自动补 /v1），或含自定义路径的基础地址、完整端点。';});
  $('modelForm').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;try{const config=await postJson('/api/model',modelBody());onConfig(config);keyState(config);$('modelUrl').value=config.model_config.base_url;$('modelKey').value='';$('modelFeedback').textContent=`已应用 ${config.model_config.protocol} / ${config.model}。密钥仅在服务内存中；未调用模型。`;}catch(e){$('modelFeedback').textContent=e.message;}finally{button.disabled=false;}});
  $('testModel').addEventListener('click',async()=>{if(!$('modelForm').reportValidity())return;$('testModel').disabled=true;$('modelFeedback').textContent='正在发送一次工具调用测试，请等待…';try{const r=await postJson('/api/model/test',modelBody());$('modelFeedback').textContent=r.message;}catch(e){$('modelFeedback').textContent=e.message;}finally{$('testModel').disabled=false;}});
  $('clearModel').addEventListener('click',async()=>{try{const cleared=await postJson('/api/model',{clear:true});onConfig(cleared);keyState(cleared);$('modelKey').value='';$('modelFeedback').textContent='已清除页面配置；若服务设置了环境变量，则回到环境变量配置。';}catch(e){$('modelFeedback').textContent=e.message;}});
  $('templateUploadBtn').addEventListener('click',()=>$('templateInput').click());
  document.querySelector('.download-template').addEventListener('click',async e=>{
    e.preventDefault();$('templateFeedback').textContent='正在下载 Word 母版…';
    try {
      const response=await fetch('/api/template');
      if(!response.ok)throw new Error(`母版下载失败（HTTP ${response.status}），请重新运行“启动演示.cmd”更新本地服务。`);
      if(!response.headers.get('Content-Type')?.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document'))throw new Error('服务返回的不是 DOCX 母版，请重新启动工作台。');
      const blob=await response.blob(), header=new Uint8Array(await blob.slice(0,4).arrayBuffer());
      if(header[0]!==80||header[1]!==75||header[2]!==3||header[3]!==4)throw new Error('母版内容无效，请重新启动工作台。');
      const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='系统报告母版.docx';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      $('templateFeedback').textContent='系统 DOCX 母版已下载。';
    }catch(error){$('templateFeedback').textContent=error.message;}
  });
  $('templateInput').addEventListener('change',async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;$('templateUploadBtn').disabled=true;try{const r=await api('/api/template',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});templateId=r.template_id;$('templateFeedback').textContent=`当前：${file.name}。${r.message}`;}catch(e){$('templateFeedback').textContent=`上传未应用：${e.message}`;}finally{$('templateUploadBtn').disabled=false;}});
  $('templateReset').addEventListener('click',()=>{templateId=null;$('templateFeedback').textContent='当前：系统母版';});
  return {reset,loadVisual,extra:()=>({template_id:templateId,intake_ids:rawIds}),hydrate(cfg){keyState(cfg);const c=cfg.model_config||{};$('modelProtocol').value=c.protocol||'openai-chat';$('modelUrl').value=c.base_url||'';$('modelName').value=c.model||'';$('modelTokens').value=c.max_tokens||4096;}};
}

export function renderExecution(run,events){
  const completed=events.filter(e=>e.type==='tool_result' && e.status!=='BLOCKED').length;
  const label={queued:'排队中',running:'执行中',completed:'已完成',failed:'执行失败',interrupted:'已中断'}[run?.status]||'等待任务';
  $('processSummary').className=`process-summary ${run?.status||''}`;$('processSummary').replaceChildren(h('b',{text:label}),h('span',{text:run?`${run.input_summary?.bridge_name||''} · 已返回 ${completed} 次工具结果`:'请先完成资料检查并发起报告任务。'}),h('span',{text:run?.duration_ms?`耗时 ${fmtDuration(run.duration_ms)}`:''}));
  const log=$('eventLog'),atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<40;
  log.replaceChildren(...events.filter(e=>e.type!=='usage').map(e=>h('li',{class:e.type},h('time',{text:new Date(e.at).toLocaleTimeString()}),h('strong',{text:e.title}),h('p',{text:e.detail||''}))));
  if(atBottom)log.scrollTop=log.scrollHeight;
}
