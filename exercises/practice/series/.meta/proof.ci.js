export class Series {
  constructor(numberString) {
    if (!numberString) {
      throw new Error('series cannot be empty');
    }

    this.numberString = numberString;
    this.digits = this.getDigits();
  }

  getDigits() {
    return [...this.numberString].map((digit) => parseInt(digit, 10));
  }

  slices(sliceSize) {
    if (sliceSize < 0) {
      throw new Error('slice length cannot be negative');
    }

    if (sliceSize === 0) {
      throw new Error('slice length cannot be zero');
    }

    if (sliceSize > this.digits.length) {
      throw new Error('slice length cannot be greater than series length');
    }

    const sliceCount = this.digits.length - sliceSize + 1;
    return Array.from({ length: sliceCount }, (_, start) =>
      this.digits.slice(start, start + sliceSize),
    );
  }
}
