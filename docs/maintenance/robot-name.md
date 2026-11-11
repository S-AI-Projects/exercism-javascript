# Robot Name Maintenance Rationale

## Canonical Test Case Mapping

| UUID | Canonical Description | Spec Test Name | Included | JavaScript Implementation Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `0396495b-0056-4b77-8fa6-ba4be5877aa2` | has a name | `has a name` | `true` | Matches regex `^[A-Z]{2}\d{3}$` checking 2 capital letters and 3 digits. |
| `3fc83307-e854-4632-a9b0-917ec7b6b33a` | name is the same each time | `name is the same each time` | `true` | Validates that multiple evaluations of ES6 `get name()` return the identical cached string. |
| `068ba0fc-2b62-4217-91fb-5ec9cfb92c4b` | different robots have different names | `different robots have different names` | `true` | Verifies instance-level uniqueness across separately allocated `new Robot()` objects. |
| `a57f6d3f-5ce7-497d-aa21-4d37c95e1eb9` | reset name | `is able to reset the name` | `true` | Tests that invoking `robot.reset()` changes `robot.name` to a newly assigned unique value. |

## Track-Specific Extensions (Non-Canonical)

The JavaScript test suite adds track-specific cases to test language guarantees and ensure robust algorithms:
- **`internal name cannot be modified`**: Asserts that assigning to `robot.name` throws an error because only a getter is defined (`get name()`).
- **Sequentiality tests (`areSequential`)**: Ensures random generation rather than predictable sequential increments.
- **Large volume and total exhaustion tests**: Checks handling of 10,000 resets and all 676,000 name combinations (`26 * 26 * 10 * 10 * 10`) along with `Robot.releaseNames()`.