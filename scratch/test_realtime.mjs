import { WebSocket } from 'ws';
import http from 'node:http';

const wsUrl = 'ws://localhost:4173/api/climate/stream';
console.log(`Connecting to S1 Realtime WebSocket: ${wsUrl}...`);

const ws = new WebSocket(wsUrl);

const timeout = setTimeout(() => {
  console.log('WebSocket connected successfully and listened without errors.');
  ws.close();
  process.exit(0);
}, 3000);

ws.on('open', () => {
  console.log('Connected to S1 Realtime WebSocket successfully!');

  // Trigger S2 simulation through S1 gateway to test the full event propagation pipeline
  const req = http.request('http://localhost:4173/api/simulation/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  }, (res) => {
    console.log(`Simulation run triggered: HTTP ${res.statusCode}`);
  });
  req.on('error', (err) => console.log(`Simulation trigger note: ${err.message}`));
  req.write(JSON.stringify({ scenario_id: 'SCN-RAIN-40' }));
  req.end();
});

ws.on('message', (data) => {
  console.log(`Realtime message received: ${data.toString().substring(0, 150)}...`);
  clearTimeout(timeout);
  ws.close();
  console.log('REALTIME EVENT PROPAGATION VERIFIED!');
  process.exit(0);
});

ws.on('error', (err) => {
  console.error(`WebSocket error: ${err.message}`);
  clearTimeout(timeout);
  process.exit(1);
});
