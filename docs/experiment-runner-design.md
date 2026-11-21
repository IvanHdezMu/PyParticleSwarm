# Experiment Runner architecture

The runner edits user-defined batches; the 22 historical experiments are editable presets, not limits. Solver algorithms, numerical dataset interpretation, and refueling behavior remain unchanged.

## Data flow

Batch selection screen → existing editor or saved configuration → persisted concrete queue → existing sequential coordinator → runner.execute(ConcreteRunConfiguration) → existing CPU solver. Expansion occurs only when preparing a new queue, never when resuming it.

Scientific settings use ordered tuples of ordinary Python numbers. Integers have no arbitrary maximum; requested k is never clamped or replaced by dataset-dependent effective k. Repetition IDs are labels, not RNG seeds. Output settings and repetition count/first ID are scalar. Dataset selection uses registry metadata, not matrices.

## Conditional expansion

The same branch-axis definition drives counting and iteration. Iterate datasets, problem modes, operators, reset states, particles, c1, ring, conditional dimensions, then repetitions. k applies to operators 4/5/15; operator share to 12/15/21; fuel settings to TSPWR; reset bounds/divisor when reset is enabled; warmup when verbose or Excel is enabled. Inactive axes contribute one choice, represented scientifically by null. Safe scalar legacy arguments are still forwarded, preserving singleton inactive preset values where available.

Compatibility is strict: every selected dataset must support every selected mode. Invalid configurations cannot launch. No matrix is loaded to count runs. Repetitions are iterated arithmetically, never pooled into a Cartesian-product input. Count uses products of axis lengths summed over applicability branches. Queue materialization is bounded to 10,000 runs; counting remains lazy.

## Presets and identity

Import shallowly merged legacy defaults, preserve all numerical/Boolean settings, repetition starting IDs, verbosity, Excel and naming metadata. Regression counts are [1,1,1,1,1,1,1,1,1,1,270,180,80,120,50,4,5,120,120,120,120,10], totaling 1209. Preserve forwarded configurations rather than stochastic iteration order.

Each batch receives a UUID and immutable JSON snapshot. The single SQLite schema
stores the complete queue and pause/resume control data. `EXPANSION_VERSION=1`
describes the scientific expansion rules. Queues contain every concrete run with status pending
and null start/end timestamps, including all nine effective scalars. Preparation
uses a temporary sibling directory and a transaction; the directory is renamed
only after the complete queue is committed. Failed preparation is not published.
Run identity remains batch ID plus decimal ordinal.

The batch/runs columns retain their previous names. `runs.started_at` now permits
NULL. The new one-row `control` table has `id=1`, `pause_requested` (0/1), and
JSON `owner` metadata (PID, process group, boot identity). This metadata does not
replace OS locking. The batch gains the `paused` status; runs gain explicit
`pending` status. No run_config.json or Excel schema changes.

## Execution and interruption

Run one ConcreteRunConfiguration directly through execute(); repetition belongs to the coordinator, not a second sweep engine. Each run gets an isolated directory, preserving existing result filenames and run_config.json. This initially reloads the dataset for each run. A separate coordinator process keeps the GUI responsive and owns manifest writes; the solver retains its Pool behavior.

The existing coordinator holds an OS file lock for its lifetime. On Linux,
recovery also checks the previous boot/process group, including surviving spawned
workers, and refuses recovery while any live member remains. Zombie processes
cannot write results. Recovery is conservative on platforms without this check.
Direct in-process calls release their ownership record on exit; isolated GUI
coordinators retain group evidence so a subsequent process can inspect survivors.

Start/resume reads the persisted concrete rows in numeric ordinal order and skips
succeeded rows. The previous interrupted attempt is preserved; a retry reserves a
new run directory and updates the same manifest row. Failed runs require separate
user intervention and are not automatically retried. Logs append across sessions.

The GUI writes a pause request into SQLite. `start_run()` checks that request and
claims the next run under `BEGIN IMMEDIATE`, eliminating the check/dispatch race.
No SQL transaction spans solver work. After the last successful run, completion
wins over a pending pause request. Only completion triggers automatic analysis.
The existing signal interruption path remains available for unexpected shutdown
handling and tests; it is not used by the Pause button or normal window close.

The runner reads `legacy_values` once and uses those exact scalars for PSOConfig,
run arguments, scalar registry arguments and storage. Result naming has one
formatter accepting scalar metadata and the established parameter tuple.
Storage writes the historical JSON schema directly, with no intermediate model.
Only analysis reconstructs historical Experiment snapshots and sweep suffixes;
the runner reexports Experiment solely to preserve old pickle names. No modern
module branches between historical and concrete input types.

## Automatic analysis

After recording successful completion, the coordinator calls `analyze_batch()`
in the existing `analysis/analysis.py`. `prepare_batch_groups()` validates the
saved batch, manifest and run snapshots, then supplies parameters and ordered
Excel paths to the original `analyze()`; no statistical formula is duplicated.
Groups use all saved effective scalars and ascending repetition IDs, rather than
reconstructing a Cartesian product of inactive axes. Numeric ordinal order
preserves the first appearance of each configuration. Paths are rebased below
the selected batch directory, supporting moved batches.

The entry point requires one dataset and one problem mode, matching the GUI.
API batches with multiple selections still execute but cannot use this summary.
A valid complete batch produces `Analysis.xlsx`, with one `Analysis` sheet, a
row per configuration, the 18 parameter columns documented in README and the
three original metrics, an autofilter and frozen headers. Temporary writing and
final replacement preserve any earlier summary if validation or writing fails.
Analysis errors (including disabled Excel or empty histories) are recorded in
`execution.log` without changing `succeeded` or rerunning solvers. This work runs
in the existing coordinator, with no new GUI control or multiprocessing policy.

## Scaling and limitations

Lazy expansion does not remove solver memory costs: dense matrices require approximately 8*n*n bytes, swarm arrays scale with particles*n, multiprocessing adds overhead, and Excel history is buffered. Do not cache every matrix or result. Each concrete execution formats one result filename. Batch analysis reads one history at a time but retains manifest records, grouped paths and the summary table in memory. Legacy analysis remains accessible.

No fake GPU selection, fixed numeric dropdowns, live convergence graphs, immediate cancellation, failed-run retry UI, or parallel batches. Backend policy is separate from scientific configuration. Future work includes bounded matrix reuse, dataset discovery/import, structured final results, reproducible solver RNG policy, aggregation across multiple batches and real GPU adapters.

## Implementation stages

1. Configuration model and validation (already implemented).
2. Shared branch expansion/counting and legacy preset regression.
3. SQLite batch lifecycle and concrete execution with offline failure/interruption tests.
4. CustomTkinter editor with free numeric chips, Boolean sets, editable presets and exact count.
5. GUI startup, offline end-to-end tests and documentation.
