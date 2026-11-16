# Hints

## General

- The goal is to count how many times each of the four DNA nucleotides (`A`, `C`, `G`, and `T`) appears in a given DNA sequence string.
- In JavaScript, the expected result is not an object or dictionary; it is a single formatted string containing four space-delimited numbers.
- If the input contains any character other than uppercase `A`, `C`, `G`, or `T`, the function must throw an error with the exact message `'Invalid nucleotide in strand'`.

## Walkthrough of Key Cases

### 1. Empty Strand

- **Input**: `''`
- **Analysis**: An empty string contains zero characters. Consequently, there are zero occurrences of `A`, `C`, `G`, and `T`.
- **Expected Result**: `'0 0 0 0'`
- **Why**: Even when no nucleotides are present, the contract requires returning the baseline counts of all four nucleotides.

### 2. Single-Character Strand

- **Input**: `'G'`
- **Analysis**: The strand has a length of 1, consisting solely of the nucleotide guanine (`G`).
  - Adenine (`A`): `0`
  - Cytosine (`C`): `0`
  - Guanine (`G`): `1`
  - Thymine (`T`): `0`
- **Expected Result**: `'0 0 1 0'`
- **Why**: The counts must follow the required ordering (`A C G T`). Since `G` is the third nucleotide in this order, the `1` appears at the third position.

### 3. Strand with Repeated Nucleotides

- **Input**: `'GGGGGGG'`
- **Analysis**: The strand contains 7 consecutive `G` nucleotides and no other characters.
  - Adenine (`A`): `0`
  - Cytosine (`C`): `0`
  - Guanine (`G`): `7`
  - Thymine (`T`): `0`
- **Expected Result**: `'0 0 7 0'`
- **Why**: All 7 matching characters contribute to the count of `G`, while the remaining three counts stay at `0`.

---

## Decision Table

The following table summarizes the input conditions, nucleotide distributions, and expected outputs defined by the exercise test suite:

| Input Condition                | Sample Input                                                               | Count A | Count C | Count G | Count T | Expected Output                                |
| :----------------------------- | :------------------------------------------------------------------------- | :------ | :------ | :------ | :------ | :--------------------------------------------- |
| **Empty sequence**             | `""`                                                                       | 0       | 0       | 0       | 0       | `"0 0 0 0"`                                    |
| **Single nucleotide**          | `"G"`                                                                      | 0       | 0       | 1       | 0       | `"0 0 1 0"`                                    |
| **Repeated nucleotide**        | `"GGGGGGG"`                                                                | 0       | 0       | 7       | 0       | `"0 0 7 0"`                                    |
| **Multiple mixed nucleotides** | `"AGCTTTTCATTCTGACTGCAACGGGCAATATGTCTCTGTGTGGATTAAAAAAAGAGTGTCTGATAGCAGC"` | 20      | 12      | 17      | 21      | `"20 12 17 21"`                                |
| **Invalid characters present** | `"AGXXACT"`                                                                | —       | —       | —       | —       | Throws `Error('Invalid nucleotide in strand')` |

---

## JavaScript Representation of Results

- **Output Type**: The return value must be a primitive string (`typeof result === 'string'`).
- **Formatting**: The string must consist of four non-negative integers separated by a single space character (`' '`).
- **Template**: `'${countA} ${countC} ${countG} ${countT}'`
- **No Surrounding Whitespace**: There should be no leading space before the first number and no trailing space after the last number.

---

## Ordering Requirements

The output string requires a strict, fixed order:

1. **First position**: Adenine (`A`)
2. **Second position**: Cytosine (`C`)
3. **Third position**: Guanine (`G`)
4. **Fourth position**: Thymine (`T`)

This order is alphabetical (`A`, `C`, `G`, `T`) and is completely independent of the order in which nucleotides appear in the input sequence. For example, in `'GATTACA'`, although `G` appears first in the input, its count is still placed at the third position in the output (`'3 1 1 2'`).

---

## Behavior Outside the Exercise Contract

To keep your solution compliant with the test suite, be aware of what is—and what is not—part of the exercise contract:

- **Case-Sensitivity**: The valid DNA alphabet consists strictly of uppercase `'A'`, `'C'`, `'G'`, and `'T'`. Lowercase characters (such as `'a'` or `'g'`) are not normalized and must be treated as invalid nucleotides.
- **Whitespace**: Input strings are not trimmed. Spaces, tabs, or newlines within or around the strand are considered invalid characters and must trigger an error.
- **Non-DNA Characters**: Characters such as RNA Uracil (`'U'`) or IUPAC ambiguity codes (e.g., `'N'`, `'X'`) are invalid.
- **Error Object**: When signaling an invalid strand, throw a standard JavaScript `Error` with the message `'Invalid nucleotide in strand'`.
- **Non-String Types**: The exercise specification assumes string input. Handling non-string primitives (`null`, `undefined`, numbers) is not part of the required contract.
