// Persian/RTL helpers, adapted from the VibeFarsi "utils" registry item.
// Kept dependency-free on purpose (no clsx/tailwind-merge needed here).

export type ClassValue = string | number | bigint | null | undefined | false | ClassValue[];

/** Minimal class joiner. */
export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const i of inputs) {
    if (!i) continue;
    if (Array.isArray(i)) {
      const nested = cn(...i);
      if (nested) out.push(nested);
    } else {
      out.push(String(i));
    }
  }
  return out.join(' ');
}

const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

/** Latin digits -> Persian digits: 1405 -> ۱۴۰۵ */
export function fa(value: string | number): string {
  return String(value).replace(/\d/g, (d) => FA_DIGITS[Number(d)]);
}

/** Persian/Arabic-Indic digits -> Latin (for parsing user input). */
export function en(value: string): string {
  return value
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/** Thousands-separated Persian number: 12450000 -> ۱۲٬۴۵۰٬۰۰۰ */
export function faNumber(value: number): string {
  return fa(Math.round(value).toLocaleString('en-US')).replace(/,/g, '٬');
}

/** Amount with the unit after the number (for money-like figures). */
export function formatToman(value: number): string {
  return `${faNumber(value)} تومان`;
}

/** Percent with Persian digits and the Persian percent sign: 18 -> ۱۸٪ */
export function faPercent(value: number, digits = 0): string {
  return `${fa(value.toFixed(digits))}٪`;
}

/** One decimal place in Persian digits, e.g. fps 12.4 -> ۱۲٫۴ */
export function faDecimal(value: number, digits = 1): string {
  return fa(value.toFixed(digits)).replace('.', '٫');
}

/** Persian relative time, e.g. «۲ ساعت پیش». */
export function faRelativeTime(input: string | Date): string {
  const then = typeof input === 'string' ? new Date(input) : input;
  const diff = Date.now() - then.getTime();
  if (Number.isNaN(diff)) return '—';
  const sec = Math.round(diff / 1000);
  if (sec < 60) return 'همین حالا';
  const min = Math.round(sec / 60);
  if (min < 60) return `${fa(min)} دقیقه پیش`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${fa(hr)} ساعت پیش`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${fa(day)} روز پیش`;
  const mo = Math.round(day / 30);
  if (mo < 12) return `${fa(mo)} ماه پیش`;
  return `${fa(Math.round(mo / 12))} سال پیش`;
}
