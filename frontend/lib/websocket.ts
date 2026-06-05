import { WSPayload } from "./types";

type Handler = (data: WSPayload) => void;

class TradingSocket {
  private ws: WebSocket | null = null;
  private handlers = new Set<Handler>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private url = "";

  connect(url: string) {
    this.url = url;
    this._open();
  }

  private _open() {
    this.ws = new WebSocket(this.url);

    this.ws.onmessage = (ev) => {
      try {
        const data: WSPayload = JSON.parse(ev.data);
        this.handlers.forEach((h) => h(data));
      } catch {
        // ignore malformed frames
      }
    };

    this.ws.onclose = () => {
      this.timer = setTimeout(() => this._open(), 3000);
    };

    this.ws.onerror = () => this.ws?.close();
  }

  on(handler: Handler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect() {
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close();
  }
}

export const socket = new TradingSocket();
