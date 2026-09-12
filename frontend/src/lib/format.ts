export function dueCountdown(dueDateIso: string): { label: string; overdue: boolean } {
  const due = new Date(dueDateIso).getTime();
  const now = Date.now();
  const diffMs = due - now;
  const overdue = diffMs < 0;
  const abs = Math.abs(diffMs);

  const days = Math.floor(abs / (24 * 60 * 60 * 1000));
  const hours = Math.floor((abs % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));

  let amount: string;
  if (days > 0) amount = `${days}d ${hours}h`;
  else amount = `${hours}h`;

  return { label: overdue ? `${amount} overdue` : `${amount} left`, overdue };
}
