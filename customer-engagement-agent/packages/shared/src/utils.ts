export const DAY_MS = 86_400_000;

export function daysBetween(olderIso: string, newerIso: string): number {
  return Math.max(0, Math.floor((new Date(newerIso).getTime() - new Date(olderIso).getTime()) / DAY_MS));
}

export function clamp(value: number, min = 0, max = 100): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function isoDaysAgo(days: number, now = new Date()): string {
  return new Date(now.getTime() - days * DAY_MS).toISOString();
}

export function id(prefix: string): string {
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}-${Date.now().toString(36)}-${random}`;
}
