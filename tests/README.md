# Tests for the current solver

The suite lives in `tests/unit` and `tests/functional`, with shared fixtures in
`tests/conftest.py` and configuration in `pytest.ini`. The `/tests/` exclusion
was removed from `.gitignore` so the suite can be tracked. The solver source
is unchanged.

## Running the suite

With the project dependencies and pytest installed:

```bash
python3 -m pytest
python3 -m pytest -m unit
python3 -m pytest -m functional
```

Pytest was missing from the review environment. It was installed temporarily in
`/tmp/tsp-pytest-deps`, without changing the project dependencies:

```bash
PYTHONPATH=/tmp/tsp-pytest-deps python3 -m pytest -q
```

Result: **188 cases; 179 passed and 9 failed**, with no skips or expected-failure
markers. Failures are deliberately retained to expose potential bugs.

## Unit tests: 139 cases (133 passed, 6 failed)

| File | Functions covered |
| --- | --- |
| `unit/test_calculations.py` | `_objective`, `_objectiveTSP`, `_objectiveTSPWR`, `_calculate_distance`, `_calculate_refuel`, `_score`, `_min_values`, `_max_values`, `_calculate_path_cost`, `_path_prices` |
| `unit/test_state.py` | `__init__`, `__str__`, `__repr__`, `_clear`, `_best`, `_global_best`, `_dataToSave`, `_Opt_Type`, `run` (Excel argument validation) |
| `unit/test_operators.py` | `_two_opt_FLip`, `_two_opt`, `_two_and_a_half_opt`, `_k_opt_Flip`, `_k_opt_Random` |
| `unit/test_compute_position.py` | `_compute_position` |

All 25 functions have direct coverage. Normal `run` behavior is tested through
integration: fully isolating it would replace the operators, state evolution,
and subprocess execution that need verification. Its initial Excel argument
validation is tested in isolation.

Tests use explicit routes, manual calculations, fixed seeds, checks for input
mutation, exact candidate order/count/content, and manually prepared states.
`_compute_position` is called directly, without multiprocessing, for all five
operators, open/closed routes, improvements, no improvements, resets, cost
recalculation after a reset, zero/negative budgets, and refuel mode.

## Functional tests: 49 cases (46 passed, 3 failed)

- All combinations of TSP/refuel, ring mode enabled/disabled, and the nine modes:
  `1`, `2`, `3`, `4`, `5`, `10`, `12`, `15`, `21` (36 cases).
- Refuel with a full/empty initial tank, both ring settings, and forced resets.
- Swarms of 1, 2, and 6 particles on a four-node problem.
- Default `run` arguments and reinitialization of the same solver instance.
- Console output and real Excel files in temporary directories, including
  populated workbooks and empty workbooks before the progress threshold.
- Execution with zero iterations, returning the initial solution.

Assertions check termination, complete permutations without duplicates,
dimensions, objectives for `pos`, `best`, and `global_best`, consistency with
stored costs, cost ordering, best records, and unchanged input data.
Only the `Pool` factory is replaced, using a real `multiprocessing.Pool` with
one worker and a seed initializer. Results and operators are not mocked.
This does not test concurrency between multiple workers. There are no
benchmarks or duration assertions.

## Retained failures

1. **N=1, four nodes:** `run` raises `IndexError` in `_Opt_Type` because `nIter`
   retains four entries while the velocity array has only one row.
2. **N=2, four nodes:** execution finishes, but `f_global_best` has four entries
   while `global_best` has two rows, failing the dimension consistency check.
3. **N=6, four nodes:** `_clear` calls `_global_best`, which fails when indexing
   `nIter`, initialized with the node count rather than the particle count.
4. **5 L capacity:** `_calculate_refuel` effectively buys 8 L at the first node;
   it returns 8 when a feasible purchase plan requires a cost of 11.
5. **300 L capacity:** a feasible 200 L leg costs 150 instead of 200. The fixed
   `150.0` limit allows the calculation to continue with insufficient fuel.
6. **`_k_opt_Flip`, k=10, four nodes:** generates a six-element candidate with
   duplicates; `k=10` is the default argument of `run`.
7. **`_k_opt_Random`:** exhibits the same problem.
8. **Velocity ordering:** `_global_best` updates only the second row of `vel`,
   leaving velocities misaligned with the sorted particles.
9. **Global best with one particle:** `_global_best` does not update the record
   because `np.any([0])` is false; it retains a cost of 34 instead of 2.

## Other characterized behaviors

- `_compute_position` evaluates budget + 1 candidates when there is no
  improvement; even a zero budget processes one candidate.
- `_calculate_path_cost` returns `None` when prices are exhausted before fuel
  demand is met, or when the price array is empty.
- `_two_opt_FLip` includes unchanged and repeated candidates. In ring mode,
  k-opt and 2.5-opt operators can change the first node.
- `_k_opt_Random` reverses the segment when it does not cross the route boundary;
  only a segment crossing that boundary is randomly permuted.
- `_Opt_Type(99)` leaves the velocity unchanged without validating the mode.
- The TSP objective is the absolute difference from the sum of row minima.
  For an open route, it can prefer distance 12 (objective 1) over distance 9
  (objective 2). Tests preserve this existing definition.
- `verbose=False` still prints the final message and solution.
- Excel progress is recorded before updating the best result of the last
  iteration.

Tests do not run `_compute_position` with an invalid operator or a generator
that yields no candidates: inspection indicates its loop would not increment
the counter and might never terminate. Empty and single-node routes are tested
directly in the generators. No function is omitted; these are limits on tested
scenarios, not on function coverage. None of these behaviors has been fixed.
