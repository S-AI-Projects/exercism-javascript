# Hints

## Choosing an approach

The reference approach keeps the orbital period for each planet in an object.
It looks up the selected planet's period, converts seconds into Earth-years,
divides by that period, and rounds the result to two decimal places.

Another approach is a `switch` statement. It checks the planet name one case at
a time and selects that planet's orbital period before doing the same
calculation. An unknown name should still produce an error.

For example, with an input of `age('earth', 1000000000)`, the Earth-year
calculation is `1000000000 / 31557600`, which rounds to **31.69**. Earth's
orbital period is 1 Earth-year, so the final age is also **31.69**.

The object lookup is useful when the planet names and periods are best kept
together as a small table. It is compact and easy to update. The `switch`
approach is useful when you want each choice and its behavior to be explicit.
It avoids a separate lookup object, but needs a case for every planet and more
repetitive code. The object takes a small amount of memory; the switch still
stores its cases and values in the program, so any real memory difference is
small and depends on the JavaScript runtime.
