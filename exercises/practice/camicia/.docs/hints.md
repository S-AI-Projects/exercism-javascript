# Hints

## General

- Camicia a tre (Beggar-My-Neighbour) simulation requires careful state tracking: the active player's hand, the opponent's hand, the central pile, the current payment debt, and seen game configurations for cycle/loop detection.

## Boundary Conditions: End of Game and Uncollected Piles

- Pay special attention to what constitutes a "trick" when a player runs out of cards during normal alternating play (when no penalty debt is active).
- A common mistake is to assume tricks only accumulate when a debt penalty is paid off (when `currentDebt` drops to zero).
- In Camicia, when an active player runs out of cards to play while there are already cards in the central pile, those remaining cards form a final trick completed by the end of the round.
- Diagnostic test case: consider `playerA = ['2']` and `playerB = ['3']`.
  1. Player A plays `'2'` (central pile: 1 card).
  2. Player B plays `'3'` (central pile: 2 cards).
  3. Player A has no remaining cards. The game terminates with `cards: 2`. Because a non-empty pile was accumulated, the total tricks must equal `1`, not `0`.
- Verify that your termination condition properly accounts for any non-empty central pile when a hand is exhausted.
