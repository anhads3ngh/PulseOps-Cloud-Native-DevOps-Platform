/* PulseOps dashboard — vanilla JS, no build step, no remote JS dependencies. */
const $ = (id) => document.getElementById(id);
const statuses = ['published', 'queued', 'processing', 'failed'];
let toastTimer;
let refreshing = false;

function toast(message, error = false) {
  const el = $('toast');
  el.textContent = message;
  el.className = `toast show ${error ? 'error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 4000);
}

async function request(url, options = {}) {
  const response = await fetch(url, { cache: 'no-store', ...options });
  const json = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(json.detail || `HTTP ${response.status}`);
  return json;
}

function setText(id, value) { $(id).textContent = String(value); }
function safeText(value) { return String(value || ''); }

function renderStats(data) {
  const n = Number(data.total || 0);
  setText('m-total', n);
  setText('m-published', data.published || 0);
  setText('m-retries', data.retry_attempts || 0);
  setText('m-success', data.published + data.failed ? data.success_rate : '—');
  setText('donut-count', n);
  const palette = { published: '#35dfa9', queued: '#9398ff', processing: '#f4b56b', failed: '#f0779e' };
  let at = 0; const segments = [];
  for (const status of statuses) {
    const count = Number(data[status] || 0);
    setText(`legend-${status}`, count);
    if (count && n) {
      const next = at + 100 * count / n;
      segments.push(`${palette[status]} ${at}% ${next}%`);
      at = next;
    }
  }
  $('donut').style.background = segments.length ? `conic-gradient(${segments.join(',')})` : '#2a3246';
}

function renderJobs(items) {
  const container = $('jobs');
  container.replaceChildren();
  setText('job-count', `Showing ${items.length} most recent deliveries`);
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.innerHTML = '<span>◌</span><strong>Nothing in the queue yet</strong><p>Submit a job to see the pipeline in action.</p>';
    container.append(empty);
    return;
  }
  for (const job of items) {
    const row = document.createElement('div'); row.className = 'job';
    const detail = document.createElement('div'); detail.className = 'job-detail';
    const icon = document.createElement('span'); icon.className = 'channel-icon';
    icon.textContent = ({ linkedin: 'in', instagram: '◎', x: '𝕏' })[job.channel] || '?';
    const titleWrap = document.createElement('div'); titleWrap.style.minWidth = '0';
    const title = document.createElement('strong'); title.className = 'job-title'; title.textContent = safeText(job.content);
    const meta = document.createElement('span'); meta.className = 'job-meta';
    const date = new Date(job.created_at);
    meta.textContent = `${job.id.slice(0, 8)} · ${Number.isFinite(date.getTime()) ? date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '—'} · ${job.failure_mode}`;
    titleWrap.append(title, meta); detail.append(icon, titleWrap);
    const attempts = document.createElement('span'); attempts.className = 'attempts'; attempts.textContent = `${job.attempts}×`;
    const state = document.createElement('span'); state.className = 'state';
    const badge = document.createElement('span'); badge.className = `status ${job.status}`; badge.textContent = job.status;
    state.append(badge); row.append(detail, attempts, state); container.append(row);
  }
}

async function refresh(showError = false) {
  if (refreshing) return;
  refreshing = true;
  try {
    const [stats, jobs] = await Promise.all([request('/api/stats'), request('/api/jobs')]);
    renderStats(stats); renderJobs(jobs.items || []);
    $('sync-time').textContent = `Synced ${new Date().toLocaleTimeString([], { hour:'2-digit', minute:'2-digit', second:'2-digit' })}`;
  } catch (error) {
    $('sync-time').textContent = 'Service unreachable';
    if (showError) toast(`Unable to refresh: ${error.message}`, true);
  } finally { refreshing = false; }
}

async function submitJob(channel, content, failureMode, batchKey) {
  const key = $('api-key').value.trim();
  const headers = { 'Content-Type': 'application/json', 'Idempotency-Key': batchKey || crypto.randomUUID() };
  if (key) headers['X-Demo-Key'] = key;
  return request('/api/jobs', { method: 'POST', headers, body: JSON.stringify({ channel, content, failure_mode: failureMode }) });
}

$('api-key').value = sessionStorage.getItem('pulseops_demo_key') || '';
$('api-key').addEventListener('input', (event) => sessionStorage.setItem('pulseops_demo_key', event.target.value));
$('reveal-key').addEventListener('click', () => { $('api-key').type = $('api-key').type === 'password' ? 'text' : 'password'; });
$('content').addEventListener('input', () => setText('char-count', `${$('content').value.length} / 280`));
$('refresh').addEventListener('click', () => refresh(true));
$('job-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const button = $('send-job'); button.disabled = true;
  try {
    const content = $('content').value.trim();
    if (!content) throw new Error('Write a simulated post before submitting.');
    const job = await submitJob($('channel').value, content, $('failure').value);
    toast(`Job ${job.id.slice(0,8)} queued · watch the delivery log.`);
    $('content').value = ''; setText('char-count', '0 / 280'); await refresh();
  } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
});
$('demo-batch').addEventListener('click', async () => {
  const button = $('demo-batch'); button.disabled = true; button.textContent = 'Injecting traffic…';
  const run = crypto.randomUUID();
  const examples = [
    ['linkedin', 'New release: Reliable publishing with idempotent workers ✨', 'none'],
    ['instagram', 'Behind the scenes: our event-driven infrastructure ☁️', 'none'],
    ['x', 'Simulated 503 outage — watch automatic retries restore delivery.', 'transient'],
    ['linkedin', 'Testing a downstream outage in the chaos engineering lab.', 'permanent'],
    ['x', 'Observability turns failures into actionable signals 📈', 'none'],
  ];
  try {
    const results = await Promise.allSettled(examples.map(([c, body, mode], i) => submitJob(c, body, mode, `${run}-${i}`)));
    const succeeded = results.filter(r => r.status === 'fulfilled').length;
    if (!succeeded) throw new Error(results[0].reason?.message || 'Unable to queue demo jobs');
    toast(`${succeeded}/5 synthetic events queued. Observe retries and the DLQ case.`);
    await refresh();
  } catch (error) { toast(error.message, true); }
  finally { button.disabled = false; button.textContent = 'Run chaos demo ↗'; }
});
refresh();
setInterval(() => refresh(), 5000);
