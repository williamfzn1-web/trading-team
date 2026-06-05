function utc(iso: string): Date {
  return new Date(iso.endsWith("Z") ? iso : iso + "Z");
}

export function toLocalDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return utc(iso).toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function toLocalTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return utc(iso).toLocaleTimeString("zh-TW", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function toLocalDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return utc(iso).toLocaleDateString("zh-TW");
}

export function timeAgo(iso: string): string {
  const diff = (Date.now() - utc(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}
