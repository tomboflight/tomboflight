export function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => asString(item))
    .filter((item) => item.length > 0);
}

export function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
}

export function toHumanLabel(value: string): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return 'Unknown';
  }

  return normalized
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(' ')
    .filter((segment) => segment.length > 0)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

export function formatTimestamp(value: unknown, fallback = 'Unavailable'): string {
  const normalized = asString(value);
  if (!normalized) {
    return fallback;
  }

  const parsed = Date.parse(normalized);
  if (Number.isNaN(parsed)) {
    return normalized;
  }

  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(new Date(parsed));
  } catch {
    return normalized;
  }
}

export function formatBytes(value: unknown, fallback = 'Unavailable'): string {
  const parsed = asNumber(value);
  if (parsed === null || parsed < 0) {
    return fallback;
  }

  if (parsed < 1024) {
    return `${Math.round(parsed)} B`;
  }

  const units = ['KB', 'MB', 'GB', 'TB'];
  let current = parsed / 1024;
  let unitIndex = 0;

  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }

  const precision = current >= 100 ? 0 : current >= 10 ? 1 : 2;
  return `${current.toFixed(precision)} ${units[unitIndex]}`;
}

export function truthyFlags(record: Record<string, unknown>, prefix: string): string[] {
  return Object.entries(record)
    .filter(([key, value]) => key.startsWith(prefix) && Boolean(value))
    .map(([key]) => key)
    .sort((left, right) => left.localeCompare(right));
}

export function toProjectId(value: unknown): string {
  const record = asRecord(value);
  return asString(record.id) || asString(record._id);
}
