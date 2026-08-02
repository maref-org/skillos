import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');

export const options = {
  thresholds: {
    errors: ['rate<0.01'],
    response_time: ['p(99)<500'],
    http_req_duration: ['p(95)<300'],
  },
  scenarios: {
    baseline: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
      tags: { scenario: 'baseline' },
      startTime: '0s',
    },
    peak: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '10s', target: 30 },
        { duration: '20s', target: 30 },
        { duration: '10s', target: 10 },
      ],
      tags: { scenario: 'peak' },
      startTime: '30s',
    },
    soak: {
      executor: 'constant-vus',
      vus: 15,
      duration: '2m',
      tags: { scenario: 'soak' },
      startTime: '70s',
    },
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const responses = http.batch([
    ['GET', `${BASE_URL}/health`, null, { tags: { endpoint: 'health' } }],
    ['GET', `${BASE_URL}/api/v1/skills`, null, { tags: { endpoint: 'skills_list' } }],
    ['POST', `${BASE_URL}/api/v1/skills`, JSON.stringify({
      name: 'test-skill',
      version: '1.0.0',
      category: 'utility',
    }), { tags: { endpoint: 'skills_create' }, headers: { 'Content-Type': 'application/json' } }],
  ]);

  responses.forEach((res) => {
    const ok = check(res, { 'status is 2xx': (r) => r.status >= 200 && r.status < 300 });
    errorRate.add(!ok);
    responseTime.add(res.timings.duration);
  });

  sleep(1);
}
