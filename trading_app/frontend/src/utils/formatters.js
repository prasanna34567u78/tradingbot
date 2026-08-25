export const getCurrencySymbol = (currency = 'INR') => {
  if (!currency) return '₹';
  const c = String(currency).toUpperCase().trim();
  if (c === 'INR' || c === 'RS' || c === 'RUPEES') return '₹';
  if (c === 'USD') return '$';
  if (c === 'EUR') return '€';
  if (c === 'GBP') return '£';
  if (c === 'JPY') return '¥';
  if (c === 'AUD') return 'A$';
  if (c === 'CAD') return 'C$';
  if (c === 'AED') return 'AED ';
  return `${currency} `;
};

export const formatCurrency = (amount, currency = 'INR', decimals = 2) => {
  const symbol = getCurrencySymbol(currency);
  const num = Number(amount || 0);
  const formatted = Math.abs(num).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `${num < 0 ? '-' : ''}${symbol}${formatted}`;
};
