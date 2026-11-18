# Camicia Maintenance: Mutation-Driven Regression Analysis

## Overview

This maintenance document records a deliberate mutation study on `exercises/practice/camicia/.meta/proof.ci.js` (`simulateGame`).
The mutation targets the terminal boundary condition when a player's hand is exhausted while non-penalty cards remain in the central pile.

## Documented Mutant

### Mistaken Assumption

A developer might incorrectly assume that tricks are only recorded when a face-card penalty debt is fulfilled (`currentDebt === 0`). Under this false assumption, the developer omits counting the residual cards in the central pile as a final trick when an active player runs out of cards during standard turn rotation:

```javascript
// Original reference implementation:
const extraTrick = pile.length === 0 ? 0 : 1;
return {
  status: 'finished',
  tricks: totalTricks + extraTrick,
  cards: cardsPlayed,
};

// Deliberate Mutant:
const extraTrick = 0; // Mistakenly ignores non-empty final pile
return {
  status: 'finished',
  tricks: totalTricks,
  cards: cardsPlayed,
};
```

### Rejecting Test Case

- **Test Name**: `two cards, one trick`
- **Canonical UUID**: `0b7f737c-3ecd-4a55-b34d-e65c62a85c28`
- **Input**:
  - `playerA = ['2']`
  - `playerB = ['3']`
- **Expected Outcome**:
  ```json
  {
    "status": "finished",
    "cards": 2,
    "tricks": 1
  }
  ```
- **Mutant Observed Outcome**:
  ```json
  {
    "status": "finished",
    "cards": 2,
    "tricks": 0
  }
  ```
- **Result**: The test suite rejects this mutant immediately on assertion failure:
  `Expected tricks: 1, Received tricks: 0`.

## Named Baseline Cases Verification

The baseline reference passes all 28 canonical test cases, including the required named cases:
1. `two cards, one trick` (`0b7f737c-3ecd-4a55-b34d-e65c62a85c28`)
2. `three cards, one trick` (`27c19d75-53a5-48e5-b33b-232c3884d4f3`)
3. `four cards, one trick` (`9b02dd49-efaf-4b71-adca-a05c18a7c5b0`)

## Automated Verification

```bash
python3 work/R53-T003/check.py
```
