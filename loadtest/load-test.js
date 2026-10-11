// k6 load test for the expenses API.
//   k6 run -e API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com/dev loadtest/load-test.js
//
// Ramps from 0 to 50 virtual users. Each iteration creates an expense and reads it back,
// so Lambda has to scale out to many concurrent execution environments.
import http from "k6/http";
import { check, sleep } from "k6";

const API_URL = (__ENV.API_URL || "").replace(/\/$/, "");

export const options = {
  scenarios: {
    ramp_up: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 }, // warm-up
        { duration: "1m", target: 50 }, // scale out
        { duration: "2m", target: 50 }, // sustained load
        { duration: "30s", target: 0 }, // ramp down
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"], // less than 1% errors
    "http_req_duration{name:POST /expenses}": ["p(95)<800"],
    "http_req_duration{name:GET /expenses/{id}}": ["p(95)<500"],
  },
};

const CATEGORIES = ["alimentacao", "transporte", "moradia", "lazer", "saude", "educacao", "outros"];

export function setup() {
  if (!API_URL) {
    throw new Error("Set the API_URL environment variable: k6 run -e API_URL=... load-test.js");
  }
}

export default function () {
  const payload = JSON.stringify({
    description: `k6 vu-${__VU} iter-${__ITER}`,
    amount: Math.round(Math.random() * 20000) / 100 + 1,
    category: CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)],
  });

  const created = http.post(`${API_URL}/expenses`, payload, {
    headers: { "Content-Type": "application/json" },
    tags: { name: "POST /expenses" },
  });
  const ok = check(created, { "created (201)": (r) => r.status === 201 });

  if (ok) {
    const id = created.json("id");
    const fetched = http.get(`${API_URL}/expenses/${id}`, { tags: { name: "GET /expenses/{id}" } });
    check(fetched, { "read back (200)": (r) => r.status === 200 });
  }

  sleep(1);
}
