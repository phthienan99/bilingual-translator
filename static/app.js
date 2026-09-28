const $=id=>document.getElementById(id);
let diagnosticChunks=[],diagnosticSamples=0;
function clearDiagnostic(){diagnosticChunks=[];diagnosticSamples=0;$('audioDownload').disabled=true;$('diagnosticDuration').textContent='No diagnostic audio saved.';}
$('keepAudio').onchange=()=>{if(!$('keepAudio').checked)clearDiagnostic();};
function rememberAudio(buffer){if(!$('keepAudio').checked)return;const samples=new Float32Array(buffer).slice();diagnosticChunks.push(samples);diagnosticSamples+=samples.length;while(diagnosticSamples>16000*60){diagnosticSamples-=diagnosticChunks.shift().length;}$('audioDownload').disabled=true;$('diagnosticDuration').textContent='Diagnostic audio saved: '+(diagnosticSamples/16000).toFixed(2)+' seconds (up to 60 seconds). Stop before downloading.';}
$('audioDownload').onclick=()=>{const wav=new ArrayBuffer(44+diagnosticSamples*2),view=new DataView(wav);const word=(offset,text)=>{for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i));};word(0,'RIFF');view.setUint32(4,36+diagnosticSamples*2,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,diagnosticSamples*2,true);let offset=44;for(const chunk of diagnosticChunks)for(const value of chunk){const v=Math.max(-1,Math.min(1,value));view.setInt16(offset,Math.round(v*(v<0?32768:32767)),true);offset+=2;}const url=URL.createObjectURL(new Blob([wav],{type:'audio/wav'})),link=document.createElement('a');link.href=url;link.download='translator-diagnostic-'+new Date().toISOString().replace(/[:.]/g,'-')+'.wav';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};

let token=sessionStorage.getItem('session'),streams=[],ctx,node,pending=Promise.resolve(),queued=0,capturing=false,receivingAudio=false,starting=false,stopping=false,flushed=null,switchingLanguage=false,lastLanguage=$('language').value;
async function api(path,body,method='POST'){
 const r=await fetch('/api/'+path,{method,headers:{'X-App-Request':'1','X-Session':token||'',...(body instanceof ArrayBuffer?{'Content-Type':'application/octet-stream'}:{'Content-Type':'application/json'})},body:method==='GET'?undefined:body instanceof ArrayBuffer?body:JSON.stringify(body||{})});
 if(!r.ok){let message=await r.text();try{message=JSON.parse(message).error||message;}catch{}throw Error(message||r.statusText);}return r;
}
function release(){capturing=false;receivingAudio=false;$('captureStatus').textContent='Audio capture off.';$('audioDownload').disabled=!diagnosticSamples;if(node)node.disconnect();node=null;for(const source of streams){for(const track of source.getTracks())track.stop();}streams=[];if(ctx)ctx.close();ctx=null;}
async function stop(){stopping=true;if(node&&capturing){await new Promise(resolve=>{flushed=resolve;node.port.postMessage('flush');setTimeout(resolve,500);});}release();$('stop').disabled=true;try{await Promise.race([pending,new Promise(resolve=>setTimeout(resolve,3000))]);await api('stop');}catch(e){$('error').textContent=e.message;}finally{stopping=false;$('language').disabled=false;$('audioSource').disabled=false;$('keepAudio').disabled=false;$('start').disabled=false;$('statusPill').textContent='Ready';}}

async function getAudioStreams(){
 if(!navigator.mediaDevices){throw Error('This browser does not expose microphone capture on localhost. Please use the latest Chrome or Edge and allow microphone access.');}
 const mode=$('audioSource').value;
 const result=[];
 if(mode==='microphone'||mode==='both'){
   let mic;try{mic=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});}catch(e){const browser=/Safari/i.test(navigator.userAgent)&&!/Chrome|Chromium|Edg/i.test(navigator.userAgent)?' Safari may require microphone access to be enabled in System Settings → Privacy & Security → Microphone. Chrome or Edge is recommended.':'';throw Error('Microphone access failed.'+browser+' '+(e?.message||''));}
   result.push(mic);
 }
 if(mode==='tab'){
   const display=await navigator.mediaDevices.getDisplayMedia({video:true,audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false},selfBrowserSurface:'exclude',surfaceSwitching:'include',systemAudio:'include'});
   const videoTracks=display.getVideoTracks();
   for(const track of videoTracks)track.stop();
   if(!display.getAudioTracks().length){for(const track of display.getTracks())track.stop();throw Error('No tab/system audio was shared. Choose the video tab and enable Share tab audio, then try again.');}
   result.push(display);
 }
 if(mode==='both'){
   const display=await navigator.mediaDevices.getDisplayMedia({video:true,audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false},selfBrowserSurface:'exclude',surfaceSwitching:'include',systemAudio:'include'});
   for(const track of display.getVideoTracks())track.stop();
   if(!display.getAudioTracks().length){for(const track of display.getTracks())track.stop();for(const stream of result)for(const track of stream.getTracks())track.stop();throw Error('No tab/system audio was shared. Choose the video tab and enable Share tab audio, then try again.');}
   result.push(display);
 }
 return result;
}

async function capture(){
 starting=true;
 $('captureStatus').textContent=$('audioSource').value==='microphone'?'Preparing microphone — please wait before speaking.':'Choose the video/browser tab and enable its audio when the sharing dialog appears.';
 try{
   streams=await getAudioStreams();
   if(stopping){release();return;}
   ctx=new AudioContext({sampleRate:16000});
   if(ctx.sampleRate!==16000)throw Error('This browser cannot capture at 16 kHz. Try Chrome or Edge.');
   await ctx.audioWorklet.addModule('/static/capture.js');await ctx.resume();
   node=new AudioWorkletNode(ctx,'capture');
   node.port.onmessage=event=>{if(event.data==="flushed"){if(flushed)flushed();flushed=null;return;}if(!capturing)return;if(!receivingAudio){receivingAudio=true;$('captureStatus').textContent=$('audioSource').value==='microphone'?'Microphone ready — speak now.':'Browser/tab audio ready — play the video now.';}rememberAudio(event.data);if(queued>12){$('error').textContent='Audio upload cannot keep up. Session stopped.';void stop();return;}queued++;pending=pending.then(()=>api('audio',event.data)).catch(e=>{$('error').textContent=e.message;release();void api('stop').catch(()=>{});}).finally(()=>queued--);};
   for(const media of streams){const source=ctx.createMediaStreamSource(media);source.connect(node);}
   node.connect(ctx.destination);capturing=true;
 }catch(e){$('error').textContent=e.message;release();await api('stop').catch(()=>{});$('stop').disabled=true;$('language').disabled=false;$('audioSource').disabled=false;$('keepAudio').disabled=false;}
 finally{starting=false;}
}

$('start').onclick=async()=>{try{clearDiagnostic();$('keepAudio').disabled=true;$('audioSource').disabled=true;$('captureStatus').textContent='Loading models — please wait before speaking.';$('error').textContent='';$('start').disabled=true;$('language').disabled=true;stopping=false;const r=await(await api('start',{language:$('language').value})).json();token=r.session;sessionStorage.setItem('session',token);lastLanguage=$('language').value;$('stop').disabled=false;}catch(e){$('error').textContent=e.message;$('start').disabled=false;$('language').disabled=false;$('audioSource').disabled=false;$('keepAudio').disabled=false;}};
$('stop').onclick=stop;

$('language').onchange=async()=>{
 const next=$('language').value;
 if(!token||stopping){lastLanguage=next;return;}
 if(switchingLanguage)return;
 switchingLanguage=true;$('language').disabled=true;
 try{await api('language',{language:next});lastLanguage=next;$('status').textContent='Live translation switched to '+next+'. New captions will use this language.';}
 catch(e){$('language').value=lastLanguage;$('error').textContent=e.message;}
 finally{switchingLanguage=false;$('language').disabled=false;}
};

function render(id,records){$(id).replaceChildren(...records.map(r=>{const p=document.createElement('p');const label=document.createElement('small');label.className='caption-stage';label.textContent=(r.correction_applied||'').startsWith('retained last visible caption')?'Unconfirmed — final recognition unavailable':r.update_kind==='provisional'?'Interim — may change':'Final — check important details';p.append(label,document.createTextNode(r.corrected_english+'\n'+r.translation));return p;}));}
async function poll(){
 if(token)try{const s=await(await api('state',null,'GET')).json();
   if(s.language&&!switchingLanguage){$('language').value=s.language;lastLanguage=s.language;}
   const displayStatus=(s.ready&&s.alive&&!s.stopping&&!receivingAudio)?'Models ready; preparing audio.':s.status;$('status').textContent=displayStatus;$('statusPill').textContent=s.stopping?'Stopping':s.alive?(s.ready?'Listening':'Loading'):'Ready';$('level').value=s.level;if(s.error)$('error').textContent=s.error;
   render('captions',s.records.slice(-3));render('history',s.records);$('download').disabled=!s.records.length;
   $('start').disabled=s.alive;$('language').disabled=Boolean(s.alive&&!s.ready)||switchingLanguage;$('audioSource').disabled=s.alive;$('keepAudio').disabled=s.alive;$('stop').disabled=!s.alive||s.stopping;
   if(s.ready&&s.alive&&!s.stopping&&!capturing&&!starting&&!stopping)void capture();
   if(!s.alive)release();
 }catch(e){$('error').textContent='Connection lost: '+e.message;release();}
 setTimeout(poll,500);
}
$('download').onclick=async()=>{try{const r=await api('history',null,'GET'),url=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=url;a.download='caption-history.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){$('error').textContent=e.message;}};
poll();
