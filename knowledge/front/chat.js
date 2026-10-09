'use strict';
const chat=document.getElementById('chat'),input=document.getElementById('input'),send=document.getElementById('send'),cancel=document.getElementById('btnCancel');
let session=localStorage.getItem('sk-session')||crypto.randomUUID(),active=null;
localStorage.setItem('sk-session',session);
function message(role,text){const row=SK.node('div','','msg '+(role==='user'?'user':'bot')),avatar=SK.node('div',role==='user'?'我':'掌柜','avatar'),body=SK.node('div'),bubble=SK.node('div',text,'bubble answer');body.append(bubble);row.append(avatar,body);chat.append(row);chat.scrollTop=chat.scrollHeight;return {row,body,bubble};}
function finish(view,result,question){
  if(view.progress)view.progress.open=false;
  cancel.textContent='取消任务';
  view.bubble.textContent=result.status==='completed'?(result.answer||''):`${result.status}：${result.error||'任务未完成，请重新提交。'}`;
  SK.citations(view.body,result.citations);
  if(result.degraded)view.body.append(SK.node('p','部分检索分支失败，本次使用可用证据回答。','error-text'));
  for(const option of result.clarification_options||[]){const b=SK.node('button',option.label);b.onclick=()=>{document.getElementById('documentSelect').value=option.document_id;submit(question);};view.body.append(b);}
  const details=SK.node('details','','source-card');details.append(SK.node('summary','检索详情与真实模型用量'),SK.node('pre',JSON.stringify({hybrid:result.hybrid_status,hyde:result.hyde_status,web:result.web_status,join_count:result.join_count,candidates:(result.rrf_chunks||[]).map(x=>({id:x.chunk_id,title:x.title,rrf:x.rrf_score})),reranked:(result.reranked_docs||[]).map(x=>({id:x.chunk_id,score:x.rerank_score})),usage:result.usage},null,2),'evidence-text'));view.body.append(details);
  active=null;send.disabled=false;cancel.disabled=true;localStorage.removeItem('sk-query-active');chat.scrollTop=chat.scrollHeight;
}
function watch(task,view,question){
  active=task;send.disabled=true;cancel.disabled=false;
  localStorage.setItem('sk-query-active',JSON.stringify({task,question,session}));
  const progress=SK.node('details','','source-card'),log=SK.node('div','','task-events');view.progress=progress;progress.open=true;progress.append(SK.node('summary','真实节点进度'),log);view.body.append(progress);
  SK.watch(task,event=>{const text=SK.progressText(event);log.append(SK.node('p',text));view.bubble.textContent=text;},result=>finish(view,result,question));
}
async function submit(question){
  if(active||!question.trim())return;
  message('user',question);const view=message('assistant','正在提交查询…');send.disabled=true;input.value='';
  const selected=document.getElementById('documentSelect').value,isStream=document.getElementById('streamToggle').checked;
  try{const result=await SK.api('/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:question,session_id:session,is_stream:isStream,selected_document_ids:selected?[selected]:[]})});if(isStream)watch(result.task_id,view,question);else finish(view,{status:'completed',...result},question);}
  catch(error){view.bubble.textContent=error.message;send.disabled=false;}
}
send.onclick=()=>submit(input.value);input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit(input.value);}};
cancel.onclick=async()=>{if(active){try{await SK.api('/tasks/'+active+'/cancel',{method:'POST'});cancel.textContent='等待取消';}catch(e){alert(e.message);}}};
document.getElementById('btnNew').onclick=()=>{if(active)return;localStorage.setItem('sk-session',crypto.randomUUID());location.reload();};
document.getElementById('btnClear').onclick=async()=>{if(active)return;if(confirm('清除当前会话的历史记录？')){try{await SK.api('/history/'+session,{method:'DELETE'});location.reload();}catch(e){alert(e.message);}}};
(async()=>{await SK.health();try{await SK.renderDocuments();const history=await SK.api('/history/'+session);if(history.items.length)chat.replaceChildren();for(const item of history.items){const view=message(item.role,item.text);if(item.role==='assistant')SK.citations(view.body,item.citations);}
  const saved=JSON.parse(localStorage.getItem('sk-query-active')||'null');if(saved&&saved.session===session){const status=await SK.api('/status/'+saved.task);if(['completed','failed','cancelled','interrupted'].includes(status.status)){localStorage.removeItem('sk-query-active');if(!history.items.some(x=>x.task_id===saved.task))finish(message('assistant',''),{status:status.status,...(status.results.query||status.results.error||{})},saved.question);}else watch(saved.task,message('assistant','恢复任务事件…'),saved.question);}
}catch(e){message('assistant',e.message);}})();
