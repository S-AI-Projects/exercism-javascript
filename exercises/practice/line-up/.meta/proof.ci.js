const ORDINAL_SUFFIXES = {
  1: 'st',
  2: 'nd',
  3: 'rd',
};

const getSuffix = (number) => {
  // Invariant: numbers ending in 11, 12, or 13 always take 'th' before checking the units digit.
  const lastTwoDigits = number % 100;
  const isTeenException = lastTwoDigits >= 11 && lastTwoDigits <= 13;
  if (isTeenException) {
    return 'th';
  }

  const unitsDigit = number % 10;
  return ORDINAL_SUFFIXES[unitsDigit] ?? 'th';
};

export const format = (name, number) =>
  `${name}, you are the ${number}${getSuffix(number)} customer we serve today. Thank you!`;
