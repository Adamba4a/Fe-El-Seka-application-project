import http from 'k6/http';
import { check, fail, group, sleep } from 'k6';

const baseUrl = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const passengerToken = __ENV.TEST_PASSENGER_TOKEN;
const productionTarget = !/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/.test(baseUrl);

if (productionTarget && __ENV.ALLOW_PRODUCTION !== 'true') {
  fail('Refusing non-local traffic. Use a staging URL, or explicitly set ALLOW_PRODUCTION=true after approval.');
}
if (!passengerToken) {
  fail('TEST_PASSENGER_TOKEN is required. Use a dedicated, verified passenger test account.');
}

export const options = {
  scenarios: {
    passenger_reads: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: Number(__ENV.BASELINE_VUS || 10) },
        { duration: '2m', target: Number(__ENV.RAMP_VUS || 25) },
        { duration: '2m', target: Number(__ENV.PEAK_VUS || 50) },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
    checks: ['rate>0.99'],
  },
};

const authHeaders = { Authorization: `Bearer ${passengerToken}` };

export default function () {
  group('health', () => {
    const response = http.get(`${baseUrl}/api/health`);
    check(response, { 'health responds': (res) => res.status === 200 });
  });

  group('passenger read endpoints', () => {
    const nearby = http.get(`${baseUrl}/api/v1/search/nearby?lat=30.0444&lng=31.2357&limit=2`, {
      headers: authHeaders,
      tags: { name: 'nearby_rides' },
    });
    check(nearby, { 'nearby read responds': (res) => res.status === 200 });

    const catalog = http.get(`${baseUrl}/api/v1/loyalty/catalog`, {
      headers: authHeaders,
      tags: { name: 'loyalty_catalog' },
    });
    check(catalog, { 'catalog read responds': (res) => res.status === 200 });
  });
  sleep(Math.random() * 2 + 1);
}
