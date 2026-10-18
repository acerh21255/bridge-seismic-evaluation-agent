import { $ } from './dom.js';

export function createModelView() {
  const canvas = $('modelCanvas'), ctx = canvas.getContext('2d');
  let geometry = null, yaw = -.45, pitch = .32, zoom = 1, drag = null;
  function draw() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr);
    ctx.fillStyle = '#e0e5ec'; ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#cdd3dc'; ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 28) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
    for (let y = 0; y < h; y += 28) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
    if (!geometry) { ctx.fillStyle = '#555f6b'; ctx.font = '13px Microsoft YaHei'; ctx.fillText('选择案例或上传 SAP 文本模型', 24, h / 2); return; }
    const all = Object.values(geometry.nodes);
    const min = [0,1,2].map(i => Math.min(...all.map(p => p[i]))), max = [0,1,2].map(i => Math.max(...all.map(p => p[i])));
    const center = min.map((v,i) => (v+max[i])/2), extent = Math.max(...max.map((v,i) => v-min[i]), 1);
    const scale = Math.min(w*.78, h*1.25)/extent*zoom;
    const project = p => { const [x,y,z] = p.map((v,i) => v-center[i]); const u = x*Math.cos(yaw)-y*Math.sin(yaw), depth = x*Math.sin(yaw)+y*Math.cos(yaw); return [w/2+u*scale, h*.53-(z*Math.cos(pitch)+depth*Math.sin(pitch))*scale]; };
    for (const edge of geometry.edges) { const a=project(geometry.nodes[edge.a]), b=project(geometry.nodes[edge.b]); ctx.strokeStyle=edge.kind==='link'?'#6b7280':'#6d5dfc';ctx.lineWidth=edge.kind==='link'?3:2;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke(); }
    for (const [id,p] of Object.entries(geometry.nodes)) { const q=project(p);ctx.fillStyle='#4032bb';ctx.beginPath();ctx.arc(...q,2.6,0,Math.PI*2);ctx.fill();if(all.length<40){ctx.fillStyle='#4c5662';ctx.font='9px Consolas';ctx.fillText(id,q[0]+4,q[1]-5);} }
    ctx.fillStyle='#555f6b';ctx.font='10px Consolas';ctx.fillText('FRAME ─   LINK ─   · JOINT',18,h-36);ctx.fillText('X / Y / Z · m',w-112,h-18);
  }
  canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(-1.57,Math.min(1.57,pitch+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];draw();});
  canvas.addEventListener('pointerup',()=>drag=null); canvas.addEventListener('pointercancel',()=>drag=null);
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.3,Math.min(6,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
  document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>{yaw=b.dataset.camera==='iso'?-.45:0;pitch=b.dataset.camera==='top'?Math.PI/2:b.dataset.camera==='front'?0:.32;zoom=1;draw();}));
  $('modelShot').addEventListener('click',()=>{if(!geometry)return;const a=document.createElement('a');a.href=canvas.toDataURL('image/png');a.download='SAP模型视图.png';a.click();});
  new ResizeObserver(draw).observe(canvas);
  return {set(value){geometry=value;yaw=-.45;pitch=.32;zoom=1;$('modelStats').textContent=value?`${Object.keys(value.nodes).length} 节点 / ${value.edges.length} 杆件与连接 / m · 拖动旋转`:'等待模型';draw();},draw};
}
