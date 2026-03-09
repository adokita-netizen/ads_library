import { describe, expect, it } from "vitest";

import {
  formatScreenLoadMs,
  getSlowestScreen,
  recordScreenLoadMetric,
} from "./screenLoadMetrics";

describe("screenLoadMetrics", () => {
  it("records latest, avg, count, and max per screen", () => {
    const first = recordScreenLoadMetric({}, "hit-ads", 812.4);
    const second = recordScreenLoadMetric(first, "hit-ads", 1200);

    expect(second["hit-ads"]).toEqual({
      count: 2,
      latestMs: 1200,
      avgMs: 1006,
      maxMs: 1200,
    });
  });

  it("formats milliseconds for UI badges", () => {
    expect(formatScreenLoadMs(0)).toBe("-");
    expect(formatScreenLoadMs(482)).toBe("482ms");
    expect(formatScreenLoadMs(1480)).toBe("1.5s");
  });

  it("returns the slowest latest screen", () => {
    const metrics = {
      trend: { count: 1, latestMs: 640, avgMs: 640, maxMs: 640 },
      "hit-ads": { count: 2, latestMs: 980, avgMs: 900, maxMs: 980 },
    };

    expect(getSlowestScreen(metrics)).toEqual([
      "hit-ads",
      { count: 2, latestMs: 980, avgMs: 900, maxMs: 980 },
    ]);
  });
});
