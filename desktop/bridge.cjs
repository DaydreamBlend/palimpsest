'use strict';
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { EventEmitter } = require('node:events');
const path = require('node:path');

function dockerArguments(c) {
  const args = ['compose', '-f', path.join(c.workspace, 'compose.yaml'), '-p', c.project, 'run', '--rm', '--no-deps', '-T',
    '--pull', 'never', '--volume', `${c.artifactVolume}:/var/lib/palimpsest/artifacts:ro`];
  if (c.queryDirectory !== null) args.push('--volume', `${c.queryDirectory}:/query:ro`);
  args.push('--entrypoint', 'python', 'app', 'tools/desktop_bridge.py', '--database-name', c.database);
  if (c.wikiId !== null) args.push('--wiki-id', c.wikiId);
  if (c.queryDirectory !== null) args.push('--query-directory', '/query');
  for (const dataId of c.include_data_ids || []) args.push('--include-data-id', dataId);
  return args;
}

class ReadBridge extends EventEmitter {
  constructor(config, { buildArguments = dockerArguments, encodeRequest = (request_id, payload) => ({ request_id, ...payload }) } = {}) {
    super(); this.config = config; this.buildArguments = buildArguments; this.encodeRequest = encodeRequest;
    this.pending = new Map(); this.child = null; this.buffer = ''; this.connected = false; this.error = null;
  }
  start() {
    if (this.child) return;
    const c = this.config;
    const args = this.buildArguments(c);
    const env = { ...process.env, PALIMPSEST_APP_IMAGE: c.image };
    this.error = null; this.buffer = '';
    const child = spawn('docker', args, { cwd: c.workspace, env, windowsHide: true, shell: false, stdio: ['pipe', 'pipe', 'pipe'] });
    this.child = child;
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      if (this.child !== child) return;
      this.buffer += chunk;
      if (this.buffer.length > 96 * 1024 * 1024) { this.fail('desktop_response_too_large'); this.close(); return; }
      let newline;
      while ((newline = this.buffer.indexOf('\n')) >= 0) {
        const line = this.buffer.slice(0, newline); this.buffer = this.buffer.slice(newline + 1);
        if (!line.trim()) continue;
        let reply;
        try { reply = JSON.parse(line); } catch { this.fail('invalid_desktop_response'); this.close(); return; }
        const pending = this.pending.get(reply.request_id); if (!pending) continue;
        clearTimeout(pending.timer); this.pending.delete(reply.request_id);
        if (reply.error) pending.reject(new Error(reply.error.code || 'desktop_request_failed'));
        else { this.connected = true; this.error = null; pending.resolve(reply.result); }
      }
    });
    // Docker diagnostics may contain deployment details; the renderer receives fixed error codes only.
    child.stderr.on('data', () => {});
    child.on('error', () => { if (this.child === child) this.fail('docker_unavailable'); });
    child.on('exit', () => { if (this.child === child) { this.child = null; this.fail('desktop_backend_disconnected'); } });
    child.stdin.on('error', () => { if (this.child === child) this.fail('desktop_backend_disconnected'); });
  }
  request(payload) {
    this.start();
    return new Promise((resolve, reject) => {
      const request_id = randomUUID();
      const timer = setTimeout(() => { this.pending.delete(request_id); this.error = 'desktop_backend_timeout'; this.connected = false; reject(new Error(this.error)); }, 45000);
      this.pending.set(request_id, { resolve, reject, timer });
      try { this.child.stdin.write(JSON.stringify(this.encodeRequest(request_id, payload)) + '\n'); }
      catch { clearTimeout(timer); this.pending.delete(request_id); reject(new Error('desktop_backend_disconnected')); }
    });
  }
  fail(code) {
    this.error = code; this.connected = false;
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(new Error(code)); }
    this.pending.clear();
  }
  close() {
    const child = this.child; this.child = null; this.fail('desktop_backend_disconnected');
    if (child) { child.stdin.end(); const timer = setTimeout(() => child.kill(), 5000); timer.unref(); child.once('exit', () => clearTimeout(timer)); }
  }
  state() { return { connected: this.connected, error: this.error, project: this.config.project, database: this.config.database,
    wikiId: this.config.wikiId, version: require('./package.json').version, readOnly: true }; }
}
module.exports = { ReadBridge, dockerArguments };
