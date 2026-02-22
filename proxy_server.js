#!/usr/bin/env node
const http = require('http');
const { WebSocketServer, WebSocket } = require('/home/ubuntu/node_modules/ws');
const { execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const PORT = parseInt(process.env.PROXY_PORT || '4000');
const GW_URL = process.env.GW_URL || 'ws://localhost:18789';
const DISPLAY = process.env.DISPLAY || ':99';
const STATIC_DIR = process.env.STATIC_DIR || path.join(__dirname, 'ai-pc-frontend', 'dist');

const MIME = {
  '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
};

const server = http.createServer((req, res) => {
  const cors = () => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', '*');
  };

  if (req.method === 'OPTIONS') {
    cors();
    res.writeHead(200);
    res.end();
    return;
  }

  if (req.url === '/api/health') {
    cors();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end('{"ok":true}');
    return;
  }

  if (req.url === '/api/screenshot' || req.url?.startsWith('/api/screenshot?')) {
    cors();
    try {
      const tmp = path.join(os.tmpdir(), 'soalin_ss_' + Date.now() + '.jpg');
      execSync(`scrot -o -q 60 ${tmp}`, { env: { ...process.env, DISPLAY }, timeout: 5000 });
      const buf = fs.readFileSync(tmp);
      fs.unlinkSync(tmp);
      const b64 = buf.toString('base64');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ image: b64 }));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(e) }));
    }
    return;
  }

  let filePath = path.join(STATIC_DIR, req.url === '/' ? 'index.html' : req.url.split('?')[0]);
  if (!fs.existsSync(filePath)) filePath = path.join(STATIC_DIR, 'index.html');
  try {
    const data = fs.readFileSync(filePath);
    const ext = path.extname(filePath);
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end('Not Found');
  }
});

const wss = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', (clientWs, req) => {
  const clientAddr = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
  console.log(`[proxy] client connected from ${clientAddr}`);

  const gwWs = new WebSocket(GW_URL, {
    headers: { origin: 'http://localhost:4000' },
  });
  let clientClosed = false;
  let gwClosed = false;
  const buffered = [];

  clientWs.on('message', (data, isBinary) => {
    const text = isBinary ? data : data.toString();
    console.log(`[proxy] client→gw: ${String(text).slice(0, 120)}`);
    if (!gwClosed && gwWs.readyState === WebSocket.OPEN) {
      gwWs.send(text);
    } else {
      buffered.push(text);
    }
  });

  gwWs.on('open', () => {
    console.log(`[proxy] connected to gateway`);
    for (const msg of buffered) {
      gwWs.send(msg);
    }
    buffered.length = 0;
  });

  gwWs.on('message', (data, isBinary) => {
    const text = isBinary ? data : data.toString();
    console.log(`[proxy] gw→client: ${String(text).slice(0, 120)}`);
    if (!clientClosed && clientWs.readyState === WebSocket.OPEN) {
      clientWs.send(text);
    }
  });

  gwWs.on('close', (code, reason) => {
    console.log(`[proxy] gw closed code=${code} reason=${String(reason)}`);
    gwClosed = true;
    if (!clientClosed) clientWs.close();
  });

  gwWs.on('error', (err) => {
    console.log(`[proxy] gw error: ${err.message}`);
    gwClosed = true;
    if (!clientClosed) clientWs.close();
  });

  clientWs.on('close', (code, reason) => {
    console.log(`[proxy] client closed code=${code} reason=${String(reason)}`);
    clientClosed = true;
    if (!gwClosed) gwWs.close();
  });

  clientWs.on('error', (err) => {
    console.log(`[proxy] client error: ${err.message}`);
    clientClosed = true;
    if (!gwClosed) gwWs.close();
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Soalin proxy on :${PORT} (gateway=${GW_URL}, static=${STATIC_DIR}, display=${DISPLAY})`);
});
