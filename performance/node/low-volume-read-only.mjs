import process from 'node:process';

const baseUrl = (process.env.BASE_URL ?? '').replace(/\/$/, '');
const token = process.env.TEST_PASSENGER_TOKEN;
const approved = process.env.ALLOW_PRODUCTION === 'true';
const stages = [1, 5, 10];
const stageDurationMs = Number(process.env.STAGE_DURATION_MS ?? 30_000);

if (!baseUrl || !token) {
  throw new Error('BASE_URL and TEST_PASSENGER_TOKEN are required.');
}
if (!approved) {
  throw new Error('Refusing production traffic without ALLOW_PRODUCTION=true.');
}
if (!/^https:\/\//.test(baseUrl)) {
  throw new Error('Production BASE_URL must use HTTPS.');
}

const samples = [];
let stopped = false;

function percentile(values, p) {
  if (values.length === 0) return 0;
  const index = Math.min(values.length - 1, Math.ceil(values.length * p) - 1);
  return [...values].sort((a, b) => a - b)[index];
}

async function get(path, headers = {}) {
  const started = performance.now();
  try {
    const response = await fetch(`${baseUrl}${path}`, { headers });
    samples.push({ duration: performance.now() - started, ok: response.ok, path, status: response.status });
  } catch {
    samples.push({ duration: performance.now() - started, ok: false, path, status: 0 });
  }
}

async function virtualUser(deadline) {
  const auth = { Authorization: `Bearer ${token}` };
  while (!stopped && Date.now() < deadline) {
    await get('/api/health');
    await get('/api/v1/search/nearby?lat=30.0444&lng=31.2357&limit=2', auth);
    await get('/api/v1/loyalty/catalog', auth);
    await new Promise((resolve) => setTimeout(resolve, 1_000 + Math.floor(Math.random() * 1_000)));
  }
}

for (const vus of stages) {
  if (stopped) break;
  const deadline = Date.now() + stageDurationMs;
  console.log(`Starting ${vus}-VU read-only stage for ${stageDurationMs / 1000}s`);
  await Promise.all(Array.from({ length: vus }, () => virtualUser(deadline)));

  const failed = samples.filter((sample) => !sample.ok).length;
  const p95 = percentile(samples.map((sample) => sample.duration), 0.95);
  const errorRate = samples.length === 0 ? 1 : failed / samples.length;
  console.log(`Cumulative: ${samples.length} requests, p95 ${p95.toFixed(0)}ms, errors ${(errorRate * 100).toFixed(2)}%`);
  if (p95 >= 500 || errorRate >= 0.01) {
    stopped = true;
    console.error('Stopping: production safety threshold breached.');
  }
}

const failed = samples.filter((sample) => !sample.ok).length;
const p95 = percentile(samples.map((sample) => sample.duration), 0.95);
const byPath = Object.groupBy(samples, (sample) => sample.path);

console.log(JSON.stringify({
  requests: samples.length,
  p95_ms: Number(p95.toFixed(1)),
  failed_requests: failed,
  error_rate: samples.length === 0 ? 1 : Number((failed / samples.length).toFixed(4)),
  by_path: Object.fromEntries(Object.entries(byPath).map(([path, entries]) => [path, {
    requests: entries.length,
    failed: entries.filter((entry) => !entry.ok).length,
    p95_ms: Number(percentile(entries.map((entry) => entry.duration), 0.95).toFixed(1)),
  }])),
}, null, 2));

process.exitCode = stopped ? 1 : 0;
