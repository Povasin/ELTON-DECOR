export function parseRublesToMinor(value: string): string | null {
  const normalized = value.trim().replace(/\s+/g, "").replace(",", ".");
  if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) return null;

  const [whole, fraction = ""] = normalized.split(".");
  const fractionMinor = (fraction + "00").slice(0, 2);
  return (BigInt(whole) * 100n + BigInt(fractionMinor)).toString();
}

export function formatPriceInput(amountMinor: string): string {
  if (!/^\d+$/.test(amountMinor)) return "";

  const minor = BigInt(amountMinor);
  const whole = minor / 100n;
  const fraction = (minor % 100n).toString().padStart(2, "0");
  return fraction === "00" ? whole.toString() : `${whole}.${fraction}`;
}
