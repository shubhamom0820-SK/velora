import { z } from "zod";

/**
 * zod, set never to compile its parsers (T-3.11). Without `jitless`, zod probes
 * `new Function("")` to see whether it may, and production's CSP has no
 * `'unsafe-eval'` (D-059): the probe is blocked and caught, but the browser
 * still reports a `script-src eval` violation, seen in T-3.11's Chrome check,
 * and T-3.13's E2E fails on any. zod's own comment on the probe says the same.
 *
 * The one place zod is imported: ESLint refuses `"zod"` anywhere else.
 */
z.config({ jitless: true });

export { z };
