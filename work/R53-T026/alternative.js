// Independent alternative approach: Integer Binary Search over candidate root interval [1, radicand]
export const squareRoot = (radicand) => {
  if (radicand < 2) {
    return radicand;
  }

  let low = 1;
  let high = Math.floor(radicand / 2);

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const square = mid * mid;

    if (square === radicand) {
      return mid;
    }
    if (square < radicand) {
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return high;
};
