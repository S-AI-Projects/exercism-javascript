export const isArmstrongNumber = (input) => {
  const bigInput = BigInt(input);

  const digits = [...String(bigInput)];
  // Every digit is raised to the number of digits in the input.
  const digitCount = BigInt(digits.length);

  const sumOfPoweredDigits = digits.reduce(
    (sum, digit) => sum + BigInt(digit) ** digitCount,
    BigInt(0),
  );

  return sumOfPoweredDigits === bigInput;
};
