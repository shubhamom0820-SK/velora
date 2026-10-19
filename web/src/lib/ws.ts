import { api, apiBaseUrl } from "@/lib/api";
import { type Infer, z } from "@/lib/zod-mini";

/**
 * The app's one socket to the API (T-7.12, 02-ARCHITECTURE §6, D-881): the
 * only code that opens a `WebSocket` (ESLint enforces it, as it does `fetch`
 * for `api.ts`). It only listens, and says `ping` and `typing`: messages are
 * sent by REST, where they are checked, masked and kept.
 *
 * - **Connect:** a ticket (`POST /v1/ws/ticket`, single use, 30 s), then
 *   `ws(s)://<the API's host>/ws?ticket=…`.
 * - **Reconnect** after anything but a revoked session (4000) or a refused
 *   origin (4403), neither of which another try would change: attempt `n`
 *   waits a random time between half of `min(30 s, 1 s × 2ⁿ)` and all of it.
 *   The count starts again only once a socket has stayed open 10 s, so one the
 *   server closes at once still backs off.
 * - **Ping** every 25 s, well inside the server's 60 s (4408); no `pong`
 *   within 10 s and the socket is given up for a new one.
 * - **Paused** once the tab has been hidden 5 minutes: closed, and opened
 *   again the moment it is shown.
 * - **Every reconnect** (never the first connect) calls `onReconnect`, so what
 *   happened while it was down is asked of the API again.
 */

export const BACKOFF_FIRST_MS = 1_000;
export const BACKOFF_MAX_MS = 30_000;
export const STEADY_MS = 10_000;
export const PING_EVERY_MS = 25_000;
export const PONG_WITHIN_MS = 10_000;
export const HIDDEN_PAUSE_MS = 5 * 60_000;
/** The server relays one `typing` a Thread every 3 s (D-670); more is dropped. */
export const TYPING_EVERY_MS = 3_000;

/** The server's close codes (02-ARCHITECTURE §6). */
export const CLOSE = {
  revoked: 4000,
  noTicket: 4401,
  forbidden: 4403,
  idle: 4408,
  tooSlow: 1013,
} as const;

/** Closes after which trying again changes nothing. */
const FINAL: ReadonlySet<number> = new Set([CLOSE.revoked, CLOSE.forbidden]);

const Envelope = z.object({
  type: z.string(),
  id: z.string(),
  data: z.record(z.string(), z.unknown()),
});
export type RealtimeEvent = Infer<typeof Envelope>;

/** Attempt `attempt`'s wait (0 for the first retry), with `random` in [0, 1). */
export function backoffDelay(attempt: number, random: number): number {
  const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_FIRST_MS * 2 ** attempt);
  return ceiling / 2 + (random * ceiling) / 2;
}

/** `ws(s)://` on the API's own host: `https` becomes `wss`, `http` `ws`. */
export function socketUrl(ticket: string, base: string = apiBaseUrl()): string {
  const url = new URL("/ws", base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("ticket", ticket);
  return url.toString();
}

/** One envelope from the server, or null for anything else. */
export function parseEvent(raw: unknown): RealtimeEvent | null {
  if (typeof raw !== "string") return null;
  try {
    const found = Envelope.safeParse(JSON.parse(raw));
    return found.success ? found.data : null;
  } catch {
    return null;
  }
}

async function askTicket(): Promise<string> {
  return (await api.post("/v1/ws/ticket")).ticket;
}

type Visibility = {
  readonly visibilityState: DocumentVisibilityState;
  addEventListener(type: "visibilitychange", listener: () => void): void;
  removeEventListener(type: "visibilitychange", listener: () => void): void;
};

export type RealtimeOptions = {
  onEvent: (event: RealtimeEvent) => void;
  onReconnect: () => void;
  ticket?: () => Promise<string>;
  open?: (url: string) => WebSocket;
  random?: () => number;
  page?: Visibility;
};

export type RealtimeState =
  "idle" | "connecting" | "open" | "waiting" | "paused" | "stopped";

export class Realtime {
  private readonly options: Required<RealtimeOptions>;
  private socket: WebSocket | null = null;
  private attempt = 0;
  private everOpened = false;
  private running = false;
  private paused = false;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private steadyTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;
  private pongTimer: ReturnType<typeof setTimeout> | undefined;
  private hiddenTimer: ReturnType<typeof setTimeout> | undefined;
  private lastTyping = new Map<string, number>();
  state: RealtimeState = "idle";

  constructor(options: RealtimeOptions) {
    this.options = {
      ticket: askTicket,
      open: (url) => new WebSocket(url),
      random: Math.random,
      page: document,
      ...options,
    };
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.options.page.addEventListener("visibilitychange", this.onVisibility);
    if (this.options.page.visibilityState === "hidden") this.onVisibility();
    void this.connect();
  }

  stop(): void {
    this.running = false;
    this.options.page.removeEventListener(
      "visibilitychange",
      this.onVisibility,
    );
    clearTimeout(this.hiddenTimer);
    this.drop();
    this.state = "stopped";
  }

  /** `typing` in `threadId`, at most once every 3 s, and only while open. */
  typing(threadId: string, now: number = Date.now()): void {
    if (this.state !== "open" || !this.socket) return;
    const last = this.lastTyping.get(threadId);
    if (last !== undefined && now - last < TYPING_EVERY_MS) return;
    this.lastTyping.set(threadId, now);
    this.send("typing", { thread_id: threadId });
  }

  private send(type: string, data: Record<string, unknown>): void {
    this.socket?.send(JSON.stringify({ type, id: crypto.randomUUID(), data }));
  }

  private async connect(): Promise<void> {
    if (!this.running || this.paused) return;
    this.state = "connecting";
    let ticket: string;
    try {
      ticket = await this.options.ticket();
    } catch {
      // No ticket (a blip, a 5xx, too many asked): try again, backing off.
      this.retry();
      return;
    }
    if (!this.running || this.paused) return;
    const socket = this.options.open(socketUrl(ticket));
    this.socket = socket;
    socket.onopen = () => this.opened(socket);
    socket.onmessage = (message) => this.received(socket, message.data);
    socket.onclose = (closed) => this.closed(socket, closed.code);
  }

  private opened(socket: WebSocket): void {
    if (socket !== this.socket) return;
    this.state = "open";
    this.steadyTimer = setTimeout(() => {
      this.attempt = 0;
    }, STEADY_MS);
    this.pingTimer = setInterval(() => this.ping(), PING_EVERY_MS);
    const again = this.everOpened;
    this.everOpened = true;
    if (again) this.options.onReconnect();
  }

  private ping(): void {
    this.send("ping", {});
    clearTimeout(this.pongTimer);
    this.pongTimer = setTimeout(() => {
      // Silent: give it up for a new one.
      this.drop();
      this.retry();
    }, PONG_WITHIN_MS);
  }

  private received(socket: WebSocket, raw: unknown): void {
    if (socket !== this.socket) return;
    const event = parseEvent(raw);
    if (event === null) return;
    if (event.type === "pong") {
      clearTimeout(this.pongTimer);
      return;
    }
    this.options.onEvent(event);
  }

  private closed(socket: WebSocket, code: number): void {
    if (socket !== this.socket) return;
    this.drop();
    if (FINAL.has(code)) {
      this.running = false;
      this.state = "stopped";
      return;
    }
    this.retry();
  }

  /** Lets go of the socket and every timer of its own, handlers first. */
  private drop(): void {
    clearTimeout(this.retryTimer);
    clearTimeout(this.steadyTimer);
    clearInterval(this.pingTimer);
    clearTimeout(this.pongTimer);
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      // CONNECTING (0) or OPEN (1): closed by us, normally.
      if (socket.readyState <= 1) socket.close(1000);
    }
  }

  private retry(): void {
    if (!this.running || this.paused) return;
    this.state = "waiting";
    const wait = backoffDelay(this.attempt, this.options.random());
    this.attempt += 1;
    this.retryTimer = setTimeout(() => void this.connect(), wait);
  }

  private readonly onVisibility = (): void => {
    if (this.options.page.visibilityState === "hidden") {
      clearTimeout(this.hiddenTimer);
      this.hiddenTimer = setTimeout(() => {
        this.paused = true;
        this.drop();
        this.state = "paused";
      }, HIDDEN_PAUSE_MS);
      return;
    }
    clearTimeout(this.hiddenTimer);
    if (!this.paused) return;
    this.paused = false;
    this.attempt = 0;
    void this.connect();
  };
}

/** The app's socket while it runs, for `typing` from the composer. */
let current: Realtime | null = null;

export function setCurrentRealtime(realtime: Realtime | null): void {
  current = realtime;
}

/** Tells the other person in `threadId` that I'm typing, if a socket is open. */
export function sendTyping(threadId: string): void {
  current?.typing(threadId);
}
