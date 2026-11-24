// mqtt-flatten.js <topic> [broker] - one topic per value, for viewers that cannot look inside a message.
// The PLCnext firmware client publishes every flagged port in one JSON message:
//   <topic>  {"Messages":[{"Payload":{"TE1":57.5,"P2_RUN":1},"Timestamp":"..."}], ...}
// This republishes each value, retained, as  <topic>/TE1  57.5   (numbers rounded to 3 decimals).
// Runs with the mqtt package that FUXA brings along: node mqtt-flatten.js plcnext/dh
const mqtt = require('mqtt');
const topic = process.argv[2] || 'plcnext/dh', broker = process.argv[3] || 'mqtt://127.0.0.1:1883';
const client = mqtt.connect(broker, { clientId: 'flatten-' + topic.replace(/\W/g, '-') });
const last = {};
client.on('connect', () => { client.subscribe(topic); console.log(new Date().toISOString(), 'connected, flattening', topic); });
client.on('error', e => console.log(new Date().toISOString(), 'error', e.message));
client.on('message', (t, msg) => {
  let payload;
  try { payload = JSON.parse(msg.toString()).Messages[0].Payload; } catch (e) { return; }
  for (const k of Object.keys(payload)) {
    const v = typeof payload[k] === 'number' ? String(Math.round(payload[k] * 1000) / 1000) : String(payload[k]);
    if (last[k] !== v) { last[k] = v; client.publish(topic + '/' + k, v, { retain: true }); }
  }
});
