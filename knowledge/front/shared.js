'use strict';
window.SK={};
SK.nodeNames={entry_node:'校验文件',pdf_to_md_node:'MinerU 解析',docx_to_md_node:'解析 DOCX',md_to_img_node:'图片摘要与对象存储',document_split_node:'文档切分',item_name_recognition_node:'识别主题',embedding_chunks_node:'生成向量',import_milvus_node:'写入并核实索引',item_name_confirmed_node:'确定资料范围',hybrid_vector_search_node:'混合检索',hyde_vector_search_node:'HyDE 检索',web_mcp_search_node:'联网搜索状态',rrf_merge_node:'融合检索结果',reranker_node:'重排序',answer_output_node:'生成回答并校验引用',idempotency_check:'检查已有版本'};
SK.progressText=e=>{const name=SK.nodeNames[e.node]||e.node;if(name){const phase={started:'开始',finished:'完成',failed:'失败',repairing_citations:'修正引用后再次校验',reused_committed_version:'复用已验证版本'}[e.phase]||e.phase||'';const seconds=e.durations?.[e.node];return `${name} · ${phase}${seconds!==undefined?' · '+seconds.toFixed(3)+' 秒':''}`;}return e.connection||e.error||({queued:'任务已排队',processing:'处理中',completed:'完成',failed:'失败',cancelled:'已取消',interrupted:'运行中断'}[e.status])||'任务状态更新';};
SK.node=(tag,text='',className='')=>{const e=document.createElement(tag);e.textContent=text;e.className=className;return e;};
SK.api=async(path,options={})=>{
  const r=await fetch(path,{credentials:'same-origin',...options});
  let data;try{data=await r.json();}catch{throw Error(`服务响应异常 (${r.status})`);}
  if(!r.ok){if(r.status===401)throw Error('请先使用本机访问凭证登录');throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));}
  return data;
};
SK.login=()=>new Promise(resolve=>{
  const dialog=SK.node('dialog');const form=SK.node('form');form.method='dialog';
  form.append(SK.node('h2','本机访问凭证'),SK.node('p','输入 APP_API_TOKEN。不要输入模型 API Key。'));
  const input=SK.node('input');input.type='password';input.required=true;input.autocomplete='current-password';input.setAttribute('aria-label','本机访问凭证');
  const message=SK.node('p','','error-text'),button=SK.node('button','登录');button.type='submit';
  form.append(input,button,message);dialog.append(form);document.body.append(dialog);dialog.showModal();
  form.onsubmit=async e=>{e.preventDefault();try{await SK.api('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:input.value})});input.value='';dialog.close();dialog.remove();resolve(true);}catch(error){message.textContent=error.message;}};
  dialog.addEventListener('cancel',()=>{dialog.remove();resolve(false);});
});
SK.health=async()=>{
  const label=document.getElementById('subTitle');
  try{const r=await fetch('/health/ready');const h=await r.json();if(r.status===401){label.textContent='请先本机登录';return;}
    label.textContent=h.status==='ready'?'服务就绪 · '+(h.components.web_search.status==='disabled'?'联网搜索未启用':'联网搜索待验证'):'未就绪：'+Object.entries(h.components).filter(([,v])=>v.status==='unavailable').map(([k,v])=>k+' ('+(v.error_type||'配置缺失')+')').join('、');
  }catch{label.textContent='本地服务连接失败';}
};
SK.watch=(id,onEvent,onFinal)=>{
  const key='sk-event-'+id;let cursor=Number(sessionStorage.getItem(key)||0);const stream=new EventSource('/stream/'+encodeURIComponent(id)+'?after='+cursor);
  function receive(event){const number=Number(event.lastEventId);if(number&&number<=cursor)return;cursor=number||cursor;sessionStorage.setItem(key,String(cursor));return JSON.parse(event.data);}
  stream.addEventListener('progress',e=>{const data=receive(e);if(data)onEvent(data);});
  stream.addEventListener('delta',e=>{receive(e);});
  stream.addEventListener('final',e=>{const data=receive(e);stream.close();if(data)onFinal(data);});
  stream.onerror=async()=>{onEvent({connection:'连接中断，正在按事件编号恢复'});try{const task=await SK.api('/status/'+id);if(['completed','failed','cancelled','interrupted'].includes(task.status)){stream.close();onFinal({status:task.status,...(task.results.query||task.results.import||task.results.error||{})});}}catch(error){onEvent({error:error.message});}};
  return stream;
};
SK.source=async citation=>{
  const data=await SK.api('/sources/'+[citation.document_id,citation.version,citation.chunk_id].map(encodeURIComponent).join('/'));
  const dialog=SK.node('dialog'),close=SK.node('button','关闭');close.onclick=()=>{dialog.close();dialog.remove();};
  dialog.append(close,SK.node('h2',data.document.file_title),SK.node('p',`处理后文档字符跨度 ${data.chunk.char_start}–${data.chunk.char_end}`),SK.node('pre',data.chunk.content,'evidence-text'));
  const original=SK.node('a','打开原文');original.href=data.document.original_url;original.target='_blank';original.rel='noopener';dialog.append(original);
  for(const im of data.document.images){const caption=SK.node('p',im.summary),image=SK.node('img');image.src=im.resource_url;image.alt=im.name;image.style.maxWidth='100%';dialog.append(caption,image);}
  document.body.append(dialog);dialog.showModal();
};
SK.citations=(parent,items)=>{for(const c of items||[]){const card=SK.node('details','','source-card');card.append(SK.node('summary',`[${c.citation_number}] ${c.title||c.file_title}`));for(const q of c.quotes||[])card.append(SK.node('blockquote',q));const button=SK.node('button','核对片段、原文与图片');button.onclick=()=>SK.source(c).catch(e=>alert(e.message));card.append(button);parent.append(card);}};
SK.renderDocuments=async()=>{
  const data=await SK.api('/documents'),selector=document.getElementById('documentSelect'),list=document.getElementById('documents');
  if(selector){const previous=selector.value;selector.replaceChildren(new Option('自动识别 / 有歧义时澄清',''));for(const d of data.items)selector.add(new Option(d.file_title,d.document_id));selector.value=previous;}
  if(list){list.replaceChildren();if(!data.items.length)list.append(SK.node('p','尚无成功导入的文档。'));for(const d of data.items){const card=SK.node('div','','source-card');card.append(SK.node('h3',d.file_title),SK.node('p',`${d.chunk_count} 个片段 · ${d.images.length} 张图片 · 版本 ${d.version.slice(0,10)}`));const link=SK.node('a','打开原文');link.href=d.original_url;link.target='_blank';link.rel='noopener';card.append(link);list.append(card);}}
  return data.items;
};
document.getElementById('btnLogin').onclick=async()=>{if(await SK.login())location.reload();};
