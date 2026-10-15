# Experiment Runner architecture

The runner edits user-defined batches; the 22 historical experiments are editable presets, not limits. Solver algorithms, numerical dataset interpretation, and refueling behavior remain unchanged.

## Data flow

Desktop editor → immutable ExperimentConfiguration → validated ExpansionPlan → exact count / lazy ConcreteRunConfiguration iterator → persistent sequential coordinator → legacy Experiment/execute adapter → existing CPU solver.

Scientific settings use ordered tuples of ordinary Python numbers. Integers have no arbitrary maximum; requested k is never clamped or replaced by dataset-dependent effective k. Repetition IDs are labels, not RNG seeds. Output settings and repetition count/first ID are scalar. Dataset selection uses registry metadata, not matrices.

## Conditional expansion

The same branch-axis definition drives counting and iteration. Iterate datasets, problem modes, operators, reset states, particles, c1, ring, conditional dimensions, then repetitions. k applies to operators 4/5/15; operator share to 12/15/21; fuel settings to TSPWR; reset bounds/divisor when reset is enabled; warmup when verbose or Excel is enabled. Inactive axes contribute one choice, represented scientifically by null. Safe scalar legacy arguments are still forwarded, preserving singleton inactive preset values where available.

Compatibility is strict: every selected dataset must support every selected mode. Invalid configurations cannot launch. No matrix is loaded to count runs. Repetitions are iterated arithmetically, never pooled into a Cartesian-product input. Count uses products of axis lengths summed over applicability branches. Preview is bounded.

## Presets and identity

Import shallowly merged legacy defaults, preserve all numerical/Boolean settings, repetition starting IDs, verbosity, Excel and naming metadata. Regression counts are [1,1,1,1,1,1,1,1,1,1,270,180,80,120,50,4,5,120,120,120,120,10], totaling 1209. Preserve forwarded configurations rather than stochastic iteration order.

Each batch receives a UUID and immutable JSON snapshot of configuration, expansion version, registry metadata and planned count. A SQLite manifest records batch status and only dispatched runs. Unmaterialized runs are pending implicitly. Run identity combines batch ID and deterministic ordinal. Store counts/ordinals as decimal text where SQLite's fixed integer width would constrain Python integers.

## Execution and interruption

Run one concrete configuration at a time through a singleton legacy Experiment and execute(). Each run gets an isolated directory, preserving existing result filenames and run_config.json. This initially reloads the dataset for each run. A separate coordinator process keeps the GUI responsive and owns manifest writes; the solver retains its Pool behavior.

Commit running status before execution and terminal status before dispatching the next run. On Ctrl+C stop dispatch, unwind the current solver Pool, mark an unconfirmed active run interrupted, and leave completed runs and future implicit pending runs intact. Abrupt process termination may leave running status until inspection; recovery must distinguish this from confirmed success. No automatic resume/retry is implemented.

## Scaling and limitations

Lazy expansion does not remove solver memory costs: dense matrices require approximately 8*n*n bytes, swarm arrays scale with particles*n, multiprocessing adds overhead, and Excel history is buffered. Do not cache every matrix or result. Current singleton execution bounds legacy filename enumeration. Batch numerical summaries and historical cross-repetition analysis require a later manifest-aware adapter; raw Excel artifacts remain usable, and legacy analysis stays accessible.

No fake GPU selection, fixed numeric dropdowns, live convergence graphs, pause/resume, retry UI, or parallel batches. Backend policy is separate from scientific configuration. Future work includes bounded matrix reuse, dataset discovery/import, structured final results, reproducible solver RNG policy, batch aggregation and real GPU adapters.

## Implementation stages

1. Configuration model and validation (already implemented).
2. Shared branch expansion/counting and legacy preset regression.
3. SQLite batch lifecycle and thin legacy adapter with offline failure/interruption tests.
4. CustomTkinter editor with free numeric chips, Boolean sets, editable presets and exact count.
5. GUI startup, legacy terminal access, offline end-to-end tests and documentation.
