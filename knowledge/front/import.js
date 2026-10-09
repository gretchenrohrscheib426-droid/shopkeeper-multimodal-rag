'use strict';
const zone=document.getElementById('dropZone'),input=document.getElementById('fileInput'),list=document.getElementById('fileList');
zone.onclick=()=>input.click();zone.onkeydown=e=>{if(e.key==='Enter'||e.key===' ')input.click();};
input.onchange=()=>{for(const file of input.files)upload(file);input.value='';};
zone.ondragover=e=>{e.preventDefault();};zone.ondrop=e=>{e.preventDefault();for(const file of e.dataTransfer.files)upload(file);};
function monitor(id,card,status,log,cancel){
  const active=JSON.parse(localStorage.getItem('sk-import-tasks')||'{}');active[id]=card.dataset.name;localStorage.setItem('sk-import-tasks',JSON.stringify(active));
  cancel.onclick=async()=>{try{await SK.api('/tasks/'+id+'/cancel',{method:'POST'});status.textContent='已请求取消，等待当前操作结束';}catch(e){status.textContent=e.message;}};
  SK.watch(id,event=>{const text=SK.progressText(event);log.append(SK.node('p',text));status.textContent=text;},result=>{
    status.textContent=result.status==='completed'?`已完成 · ${result.chunk_count} 个片段${result.already_imported?' · 复用现有版本':''}`:result.status+' · '+(result.error||'');
    cancel.disabled=true;const active=JSON.parse(localStorage.getItem('sk-import-tasks')||'{}');delete active[id];localStorage.setItem('sk-import-tasks',JSON.stringify(active));SK.renderDocuments().catch(e=>status.textContent+=' / '+e.message);
  });
}
function taskCard(name){const card=SK.node('div','','task-card');card.dataset.name=name;const status=SK.node('p','等待上传'),log=SK.node('div','','task-events'),cancel=SK.node('button','取消');card.append(SK.node('strong',name),status,log,cancel);list.prepend(card);return [card,status,log,cancel];}
async function upload(file){const elements=taskCard(file.name),status=elements[1];try{const form=new FormData();form.append('file',file);const result=await SK.api('/upload',{method:'POST',body:form});monitor(result.task_id,...elements);}catch(error){status.textContent=error.message;elements[3].disabled=true;}}
(async()=>{await SK.health();try{await SK.renderDocuments();const old=JSON.parse(localStorage.getItem('sk-import-active')||'null');if(old){monitor(old.id,...taskCard(old.name));localStorage.removeItem('sk-import-active');}for(const [id,name] of Object.entries(JSON.parse(localStorage.getItem('sk-import-tasks')||'{}'))){if(id!==old?.id)monitor(id,...taskCard(name));}}catch(e){list.append(SK.node('p',e.message,'error-text'));}})();
