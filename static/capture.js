class Capture extends AudioWorkletProcessor {
  constructor(){super();this.samples=[];this.port.onmessage=()=>{if(this.samples.length){const batch=new Float32Array(Math.ceil(this.samples.length/480)*480);batch.set(this.samples);this.samples=[];this.port.postMessage(batch.buffer,[batch.buffer]);}this.port.postMessage("flushed");};}
  process(inputs,outputs){
    const channel=inputs[0]?.[0];
    if(channel){for(const s of channel)this.samples.push(s);}
    while(this.samples.length>=3840){const batch=new Float32Array(this.samples.splice(0,3840));this.port.postMessage(batch.buffer,[batch.buffer]);}
    return true;
  }
}
registerProcessor('capture',Capture);
