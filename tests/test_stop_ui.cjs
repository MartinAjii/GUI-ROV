// No browser or physical ROV required: exercise the stop UI state machine.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let now=100, timer, sendOK=true;
const sent=[];
const elements=Object.fromEntries(['btnStopDisarm','stopStatus','stopArmState'].map(id=>[id,{
 textContent:'', disabled:true, dataset:{}, addEventListener(name,fn){this[name]=fn;}
}]));
const context=vm.createContext({document:{getElementById:id=>elements[id]},
 performance:{now:()=>now},setInterval:fn=>{timer=fn;},
 Telemetry:{send:data=>{sent.push(data);return sendOK;}},Date,Math});
vm.runInContext(fs.readFileSync('js/emergency-stop.js','utf8')+'\nglobalThis.ui=EmergencyStop;',context);
const ui=context.ui, b=elements.btnStopDisarm, status=elements.stopStatus, state=elements.stopArmState;
const data=(extra={})=>({connected:true,stop_available:true,armed:true,
 stop:{phase:'idle',id:null,message:''},...extra});
ui.init(); assert(b.disabled);
ui.setConnection(true); assert(b.disabled);
ui.onTelemetry({connected:true}); assert(b.disabled); // Old backend is not stop-capable.
ui.onTelemetry(data()); assert(!b.disabled);
b.click(); assert(b.disabled); assert.equal(sent.length,1); assert.equal(sent[0].command,'disarm');
b.click(); assert.equal(sent.length,1);
ui.onResult({id:sent[0].id,stop:{id:sent[0].id,phase:'pending',message:'Menunggu heartbeat DISARM'}});
assert(b.disabled); assert.equal(state.textContent,'ARMED');
ui.onTelemetry(data({armed:false,stop:{id:sent[0].id,phase:'confirmed'}}));
assert.equal(state.textContent,'DISARMED');
ui.onTelemetry(data({stop:{id:sent[0].id,phase:'confirmed'}}));
assert.match(status.textContent,/kembali ARMED/);
b.click();ui.onResult({id:sent.at(-1).id,stop:{phase:'rejected',message:'Pixhawk menolak DISARM'}});
assert.match(status.textContent,/menolak/); assert(!b.disabled);
now+=2100;timer();assert(b.disabled);assert.equal(state.textContent,'STATUS TIDAK DIKETAHUI');
ui.onTelemetry(data());assert(!b.disabled);
sendOK=false;b.click();assert.match(status.textContent,/Gagal mengirim/);
sendOK=true;b.click();now+=7100;ui.onTelemetry(data());timer();assert.match(status.textContent,/belum terkonfirmasi/);
ui.setConnection(false);assert(b.disabled);assert.equal(state.textContent,'STATUS TIDAK DIKETAHUI');
ui.setConnection(true);assert(b.disabled); // Never reuse telemetry across reconnects.
ui.onTelemetry(data());assert(!b.disabled);
console.log('PASS: UI offline, old backend, pending, duplicate click, ACK, heartbeat, re-arm, denial, stale data, send failure, timeout, reconnect.');
