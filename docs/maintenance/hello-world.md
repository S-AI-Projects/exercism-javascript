# Maintenance Documentation: `hello-world`

## Mutation-Driven Regression Analysis

### Contract Summary
- **Function signature:** `export function hello()` (0 arguments; smallest valid input is `hello()`).
- **Expected output:** Exact string `"Hello, World!"` (case-sensitive, including comma + space and trailing exclamation mark).

### Documented Mutant
- **Original reference (`.meta/proof.ci.js`):** `export const hello = () => 'Hello, World!';`
- **Mutant (omitted trailing exclamation punctuation):** `export const hello = () => 'Hello, World';`
- **Mistaken assumption exposed:** Assuming approximate greeting text without exact trailing punctuation (`!`) satisfies the specification.

### Rejecting Test Case
- **Canonical Test ID:** `af9ffe10-dc13-42d8-a742-e7bdafac449d`
- **Test Name:** `Say Hi!` (`exercises/practice/hello-world/hello-world.spec.js`)
- **Minimal Input:** `hello()` (no arguments)
- **Original Reference Behavior:** Passes (`Expected: "Hello, World!"`, `Received: "Hello, World!"`).
- **Mutant Behavior:** Rejected (`Expected: "Hello, World!"`, `Received: "Hello, World"`).

## Verification

Run the automated mutation regression check:

```bash
python3 work/R53-T023/check.py
```
