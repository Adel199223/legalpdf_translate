// Integer decimal arithmetic mirrors pricing.translation_fee_eur's half-up cents.
export function translationFeeEur(words, rate) {
  const count = String(words ?? "").trim();
  const match = String(rate ?? "").trim().replace(",", ".").match(/^\+?(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i);
  if (!/^\d+$/.test(count) || !Number.isSafeInteger(Number(count)) || !match
      || !(match[1] || match[2]) || !Number.isFinite(Number(rate.toString().replace(",", ".")))) return null;
  const exponent = Number(match[3] || 0);
  if (Math.abs(exponent) > 100 || (match[1] + (match[2] || "")).length > 100) return null;
  const scale = (match[2] || "").length - exponent;
  let numerator = BigInt(count) * BigInt((match[1] || "0") + (match[2] || "")) * 100n;
  let denominator = 1n;
  if (scale > 0) denominator = 10n ** BigInt(scale);
  else numerator *= 10n ** BigInt(-scale);
  const cents = (numerator * 2n + denominator) / (denominator * 2n);
  return `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
}

export function updateTranslationFinance(nodes) {
  const automatic = nodes.mode?.value === "auto";
  if (nodes.total) nodes.total.readOnly = automatic;
  if (automatic && nodes.total) {
    nodes.total.value = translationFeeEur(nodes.words?.value, nodes.rate?.value) ?? "";
  }
  if (nodes.profit) nodes.profit.readOnly = true;
  if (nodes.note) nodes.note.textContent = nodes.profit?.value?.trim()
    ? "Historical profit value retained; currency basis is unverified and it is not recalculated."
    : "Profit is not calculated: fees are EUR and API costs are USD. No exchange rate is assumed.";
}
