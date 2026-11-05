export function displayValue(tag, meta, connected = true) {
  if (!connected || !tag || tag.quality !== 'GOOD' || !Number.isFinite(tag.value)) return '—';
  const divisor = meta?.divisor || 1;
  return (tag.value / divisor).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

export function confirmsCommand(tag, pending) {
  return Boolean(tag && pending && tag.quality === 'GOOD' &&
    tag.timestamp > pending.previousTimestamp && tag.value === pending.raw);
}

export async function readJson(response) {
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Проверьте введённые значения';
    throw new Error(detail);
  }
  return data;
}
