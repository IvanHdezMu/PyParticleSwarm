# PyParticleSwarm

## Overview

PyParticleSwarm explores route optimization using Particle Swarm Optimization
(PSO) with permutation-based local search. It supports the **Traveling Salesperson
Problem (TSP)** and a **TSP with refueling (TSPWR)** formulation, configurable
experiments, persistent batch execution, and analysis of Excel result histories.

The project includes a desktop Experiment Runner, terminal run/analysis menus,
TSPLIB and geographic dataset readers, and a separate MITECO fuel-station dataset
generator. The algorithms, experiment orchestration, presentation, and output
components live in separate packages.

## Algorithms

| Problem | Solver | Evaluation |
| --- | --- | --- |
| TSP | `TSPParticleSwarm` | Route distance, with an optional closing edge in ring mode. |
| TSPWR | `TSPWRParticleSwarm` | Refueling cost using route distances, station prices, tank capacity, fuel efficiency, and the initial tank state. |

Both classes inherit directly from `ParticleSwarm`. TSPWR adds fuel-capacity
constraints and refueling calculations; it does not inherit from TSP. The current
refueling model does **not** guarantee physically feasible tours (see Limitations).

`ParticleSwarm` is the common implementation for these route problems, based on
permutations and distance matrices. Its representation and search operators are
not a universal PSO engine for arbitrary optimization problems. Shared search
includes the existing 2-opt/flip, 2.5-opt, k-opt variants and operator combinations.
Objectives are minimized; the internal objective can differ from the physical
distance or fuel cost displayed and saved in results.

The main components are:

- [`ParticleSwarm`](tsp_pso/algorithms/core/particle_swarm.py): shared swarm state,
  search operators, best-result management, and execution coordination.
- [`TSPParticleSwarm`](tsp_pso/algorithms/tsp/tsp_particle_swarm.py) and
  [`TSPWRParticleSwarm`](tsp_pso/algorithms/tspwr/tspwr_particle_swarm.py):
  problem-specific objectives, bounds, and reported measures.
- [`PSOConfig`](tsp_pso/algorithms/core/pso_config.py): frozen common settings,
  including particle count `N`, search budget `c1`, ring mode, reset threshold,
  operator share, and progress warmup. `c1` is a node-scaled search-budget
  multiplier, not an outer iteration count.
- [`RefuelConfig`](tsp_pso/algorithms/tspwr/refuel_config.py): frozen capacity,
  consumption, and initial-tank settings for TSPWR. Capacity is in liters and
  consumption is **km/liter**. Dataset prices remain a separate input.
- [`SOLVER_REGISTRY`](tsp_pso/algorithms/solver_registry.py): maps `tsp` and `tspwr`
  to their solver classes and problem-specific argument builders. The application
  runner retains compatibility with experiment configurations using `refuel`.
- [`ParticleExecutor`](tsp_pso/infrastructure/executors/particle_executor.py),
  [`ExcelResultWriter`](tsp_pso/infrastructure/writers/excel_result_writer.py), and
  [`ConsolePresenter`](tsp_pso/presentation/console_presenter.py): process-pool
  execution, Excel writing, and console formatting/output respectively.

For direct solver use, `matrix` and TSPWR `prices` are retained by reference and
must remain unchanged for the solver's lifetime. `run()` returns an independent,
writable route copy and its objective value. Configuration objects are immutable;
solver validation and numeric conversions still occur during construction.

## Getting Started

Run commands from the repository root. Python 3.12 is the version used by CI and
the development environment. Install the existing dependencies:

```bash
python3 -m pip install -r .devcontainer/requirements.txt
```

The devcontainer installs these automatically. The desktop interfaces also need
Tk and access to a graphical display; the devcontainer includes `python3-tk`, but
still needs display access.

```bash
python3 main.py             # Desktop Experiment Runner
python3 main.py --terminal  # Terminal run/analysis menus; no display required
```

In the terminal interface, select **run** and then a configured experiment, or
**analysis** to inspect saved results as described below. Experiment definitions
and defaults are in [`config/experiments.json`](config/experiments.json); dataset
paths, formats, and supported problems are in
[`config/datasets.json`](config/datasets.json). The desktop entry point uses
`presentation/experiment_gui.py`; terminal menus live in
[`presentation/terminal.py`](tsp_pso/presentation/terminal.py).

The traditional terminal experiments use the full Cartesian product from
[`Experiment`](tsp_pso/experiments/experiment.py), including inactive sweep values.
The current configuration contains 22 experiments and 1,209 configurations; the
GUI/batch expansion applies the conditional rules described below instead.

[`load_run_options()`](tsp_pso/infrastructure/experiment_options.py) reads the
project's `config/experiments.json` by default, combining it with sibling
`datasets.json` and `historical_analyses.json`. Its Python API also accepts combined
JSON configuration files. An explicitly supplied relative configuration path is
relative to the working directory; complementary files are read from its directory.

[`dataset_reader.py`](tsp_pso/infrastructure/dataset_reader.py) supports `euc`
(rounded TSPLIB Euclidean distances), `matrix` (TSPLIB edge weights), `excel`
(Ottoni-style coordinate/price columns), and `json` (geographic nodes and prices,
including MITECO output). Geographic distances are in kilometers. Dataset paths
normally resolve under the project's `datasets/` directory; absolute paths remain
absolute. The reader returns a distance matrix and prices, or `None` for prices
in TSPLIB datasets.

For development tests:

```bash
python3 -m pip install pytest
python3 -m pytest
```

The separate [MITECO dataset generator](tools/dataset_generators/README.md)
provides a CLI and desktop GUI, including saved-source snapshot replay. Generated
JSON files are not automatically registered in the Experiment Runner. See its
README for commands, source requirements, and reproducibility limits.

## Experiment Runner

Start with **Custom configuration** or any of the **22 editable presets**. Select
one registered dataset and a compatible problem type, then enter your own numeric
values. Fuel capacity and efficiency are single values in the GUI; other
scientific numeric controls retain their editable sweeps.

Numeric fields have an **Add** button (or press Enter) and removable value chips.
Values retain insertion order; duplicates and invalid values are rejected. Add a
replacement before removing the last value. Boolean sweep controls allow Off,
On, or both. Presets populate the form without executing anything.

The collapsed **Advanced settings** section contains the reset threshold divisor,
first repetition ID, progress warmup multiplier, and output directory. Presets
retain non-1 repetition IDs even when that section is collapsed.

The exact **Planned runs** count comes from the same lazy expansion used for
execution. Conditional fields do not multiply irrelevant runs: k applies only to
operators 4/5/15, operator share to 12/15/21, fuel settings to TSPWR, and reset
settings when reset is enabled. Operators 10 and 15 with three k-values produce
four operator branches, not six. Repetitions multiply the count; the first
repetition ID can be 17 or another positive integer and is **not a random seed**.
Numeric inputs are not restricted to preset values, and requested k is never
clamped by the editor; the solver handles k larger than the node count internally.

The problem-type selector shows only modes supported by the dataset. Browsing
reads metadata only. Inactive settings remain available for later edits. Click
**Run batch**, review the exact count and destination, and confirm. Runs execute
sequentially in a separate coordinator process while the GUI remains responsive;
each solver manages its own multiprocessing pool. Editing the form afterward
does not change the frozen configuration of the launched batch.

Batch output is stored under:

```text
Results/batches/<batch-id>/
  batch.json                 # original configuration and dataset metadata
  manifest.sqlite3           # durable status of dispatched runs
  execution.log              # solver output and process diagnostics
  runs/<ordinal>/<dataset>/<timestamp>_<parameters>/
    run_config.json
    <result-name>.xlsx        # when Excel output is enabled
```

An alternative output directory replaces `Results`; relative paths are resolved
from the project root. Pending runs are implicit, so a huge batch does not create
a database row for every possible execution. Completed runs are committed
individually. A failed run stops the batch; later runs remain pending.

**Ctrl+C in the launching terminal**, or closing the window and confirming the
interruption, stops the active batch. Completed files/statuses remain saved; the
unconfirmed active run is marked interrupted and later runs stay pending. Partial
active-run artifacts may remain. Abrupt OS termination or power loss can leave
stale running status; there is no automatic recovery/resume UI.

An already-created, new pending batch can also be started headlessly:

```bash
python3 -m tsp_pso.experiments.batch_executor PATH_TO_BATCH
```

This is not a resume command. The batch coordinator adapts each concrete run to
the existing `Experiment`/`execute()` application API, which selects the current
specialized solver through the registry. The dataset descriptor saved in the
batch snapshot is passed explicitly to `execute()`; no shared dataset catalog is
modified. See the
[Experiment Runner architecture](docs/experiment-runner-design.md) for expansion,
persistence, and interruption details; its legacy-adapter terminology refers to
this experiment API boundary.

## Results and Analysis

Each application-level experiment execution reserves a new directory under
`Results/<dataset>/<timestamp>_<parameters>/`. Names use UTC timestamps with
second precision and a compact parameter summary; collisions receive `__2`,
`__3`, and so on via atomic directory creation. Existing directories are never
reused. All combinations and repetitions in that execution share the directory,
and `execute()` returns its path. Batch runs use the nested layout shown above,
with one concrete configuration and repetition per application-level execution.

[`run_storage.py`](tsp_pso/infrastructure/run_storage.py) owns directory reservation
and snapshot writing. The application default output path is resolved from the
project root and experiment options. In direct Python calls to `execute()`, an
explicit relative `output_dir` is relative to the working directory; absolute
paths are preserved. This differs from the project-relative batch output setting.

`run_config.json` records the effective experiment configuration, sweep lists,
repetition bounds/step, and `created_at`, even with Excel disabled. Existing raw
filename conventions are preserved; suffixes distinguish varying parameters that
would otherwise collide within an execution.

Raw Excel histories have columns **`Step`** and **`Result`**. `Result` is route
distance for TSP or refueling cost for TSPWR, rather than necessarily the returned
internal objective. Samples are collected after the configured progress warmup.
Short executions can produce an empty workbook with column headers; there is no
guaranteed final sample or saved route in that workbook.

The implementation is [`tsp_pso/analysis/analysis.py`](tsp_pso/analysis/analysis.py).
For each parameter combination, it finds the minimum sampled `Result` in each
repetition and the corresponding `Step`, then reports:

| Column | Meaning |
| --- | --- |
| `mean_minimum_result` | Mean of the per-repetition minima. |
| `mean_step_of_minimum` | Mean of the recorded steps at those minima. |
| `best_result` | Best minimum across the repetitions. |

These are summaries of recorded samples, not necessarily the final solver state.
Each repetition contributes one minimum with equal weight. Ties select the first
minimum in workbook row order, not the smallest `Step`. Missing `Result` values
are ignored when other results are available; an empty history, all-missing
results, or a missing `Step` at the selected minimum rejects that history.
Tables contain the configured parameter columns followed by the three metrics
in the order above. They are printed to the console and written to Excel without
a row index when an output is defined.

**Terminal analysis.** Run `python3 main.py --terminal` and choose **analysis**.
The menu mirrors the current experiment ordering. Selecting an experiment scans
the timestamped run directories for its dataset, including other labels and
configurations. Each run is reconstructed from its saved configuration and
analyzed independently; its summary is saved in the same run directory. All 22
configured presets retain their menu positions even when a preset has
`excel=false`: previously saved Excel runs for that dataset remain available,
as do historical definitions through the Python API. If no eligible run snapshot
is found, the menu offers to execute the selected experiment only when that
preset saves Excel. Otherwise it explains that execution would not save results
and returns without offering to run it. Snapshot discovery does not check that
all workbooks are complete; those checks happen during analysis.

**Direct directory analysis.** For example, from the repository root:

```bash
python3 -c "from tsp_pso.analysis.analysis import analyze_runs; analyze_runs('Results/Minas24D')"
```

Use the actual dataset directory for your results. The scanner examines immediate
timestamped child directories, not an entire recursive batch tree. For a batch,
pass `Results/batches/<batch-id>/runs/<ordinal>/<dataset>` instead. There is no
automatic cross-run-directory or cross-repetition batch aggregation.

Discovery reads each candidate directory's `run_config.json`, requiring the saved
experiment fields, a parseable `created_at`, and a dataset matching the parent
directory. It uses the saved configuration independently of today's presets.
Saved repetition ranges use `start`, exclusive `stop`, and `step` (default 1 when
omitted), including valid negative steps. Empty ranges and a zero step are invalid.
Both `discover_run_analyses()` and `analyze_runs()` resolve a relative dataset
directory from the current working directory; discovered input and output paths
are absolute, so they remain valid when passed to `analyze()` from elsewhere.

Each run's summary uses its saved `analysis_output` filename, or
`Analysis_<dataset>_<label>.xlsx` when none is set, inside that run's directory.
Reanalysis replaces that summary; it does not combine runs or read existing
summaries as raw input. `analyze_runs()` returns a mapping from absolute run
directory strings to the successfully generated DataFrames.

Malformed snapshots and Excel-disabled runs are silently skipped. Missing, empty,
corrupt, or invalid workbooks cause the affected run to be skipped with a diagnostic;
other runs can still be analyzed. Individual/historical analysis requires all
configured inputs and rejects missing files, missing columns, or unusable data.
Read and calculation errors include the input path; aggregation errors list the
participating paths and their selected minimum/step values. Contextual errors
retain the original exception as their cause. An input failure produces no new
summary for that run, but does not remove a summary from an earlier analysis.

**Historical results.**
[`config/historical_analyses.json`](config/historical_analyses.json) defines the
older Berlin52 layouts (`00` and `02_08`), their repetition ranges and filename
templates. They retain their existing paths; flat-layout results are not
migrated automatically. These definitions are loaded by `load_analysis_options()`
but are **not listed in the current experiment-only terminal menu**. To analyze
an existing historical dataset from a shell, select its definition explicitly
through the Python API:

```bash
python3 - <<'PY'
from tsp_pso.analysis.analysis import analyze, load_analysis_options

historical = next(item for item in load_analysis_options() if item['id'] == '00')
analyze(historical)
PY
```

This requires the workbooks specified by that definition to exist. Both current
historical definitions have `output: null`, so they print the table without
writing a summary file. Relative input/output paths in analysis definitions are
resolved from the project root, or from an explicit `root` passed to `analyze()`;
absolute paths are preserved. Individual and historical analyses return a
DataFrame, while a catalog selection passed to `analyze()` returns the same
per-run mapping as `analyze_runs()`.

## Project Structure

See the [constants and shared metadata reference](docs/constants.md) for defaults,
validation rules, expansion order and imported aliases.

| Path | Purpose |
| --- | --- |
| [`main.py`](main.py) | Desktop entry point and terminal mode. |
| [`tsp_pso/algorithms/core/`](tsp_pso/algorithms/core/) | Shared `ParticleSwarm` and `PSOConfig`. |
| [`tsp_pso/algorithms/tsp/`](tsp_pso/algorithms/tsp/) | TSP specialization. |
| [`tsp_pso/algorithms/tspwr/`](tsp_pso/algorithms/tspwr/) | TSPWR specialization and `RefuelConfig`. |
| [`tsp_pso/algorithms/solver_registry.py`](tsp_pso/algorithms/solver_registry.py) | Solver classes and argument builders. |
| [`tsp_pso/application/runner.py`](tsp_pso/application/runner.py) | Coordinates solver selection, dataset reading, run storage and configuration execution. |
| [`tsp_pso/experiments/experiment.py`](tsp_pso/experiments/experiment.py) | Traditional `Experiment` model and `build_experiments(options)`. |
| [`tsp_pso/experiments/result_naming.py`](tsp_pso/experiments/result_naming.py) | Shared filename conventions for execution and analysis. |
| [`tsp_pso/experiments/`](tsp_pso/experiments/) | `experiment_config.py`, `experiment_batch.py`, `batch_store.py`, `batch_executor.py` and `experiment_process.py`: validated configuration, presets, lazy expansion, persistence and batch coordination. |
| [`tsp_pso/presentation/terminal.py`](tsp_pso/presentation/terminal.py) | Interactive execution/analysis menus, confirmations and cancellation handling. |
| [`tsp_pso/presentation/`](tsp_pso/presentation/) | Desktop Experiment GUI/editor and solver console presenter. |
| [`tsp_pso/infrastructure/experiment_options.py`](tsp_pso/infrastructure/experiment_options.py) | JSON option loading and complementary configuration files. |
| [`tsp_pso/infrastructure/dataset_reader.py`](tsp_pso/infrastructure/dataset_reader.py) | Dataset reading from an explicit descriptor and dataset root, reusing `tsplib/`. |
| [`tsp_pso/infrastructure/run_storage.py`](tsp_pso/infrastructure/run_storage.py) | Atomic run-directory reservation and `run_config.json` snapshots. |
| [`tsp_pso/infrastructure/`](tsp_pso/infrastructure/) | Also contains `tsplib/`, `executors/particle_executor.py` and `writers/excel_result_writer.py`. |
| [`tsp_pso/analysis/`](tsp_pso/analysis/) | Result discovery, validation and summaries. |
| [`config/`](config/) | Dataset catalog, experiment defaults/presets and historical analyses. |
| [`datasets/TSPLIB/`](datasets/TSPLIB/) and [`datasets/Ottoni/`](datasets/Ottoni/) | Input datasets with their original filenames. |
| [`tools/dataset_generators/`](tools/dataset_generators/) | MITECO JSON dataset generation and its separate GUI. |
| [`tests/`](tests/) | Unit and functional tests, including real multiprocessing. |
| [`.devcontainer/requirements.txt`](.devcontainer/requirements.txt) | Application dependencies installed by the devcontainer. |

`application/runner.py` coordinates operations; experiment definitions and naming
belong to `experiments/`, file access belongs to `infrastructure/`, and interactive
menus belong to `presentation/terminal.py`. Analysis uses the extracted experiment,
naming and configuration modules directly.

Importing runner does not read configuration JSON or build experiments. Its
`execute()` function accepts optional `dataset`, `run_options` and `datasets_root`
arguments, loading defaults on demand when needed. There are no `RUN_OPTIONS`,
`DATASETS` or `EXPERIMENTS` globals in runner. Compatibility helpers, including
`runner.main()`, remain available; the normal terminal entry point is
`presentation.terminal.main()`.

## Limitations

- The Experiment Runner uses registered datasets only; automatic discovery/import
  of generated MITECO files is deferred.
- Execution is CPU-only, one batch run at a time. Each run reloads its dataset;
  dense matrices, swarm state, multiprocessing and buffered Excel histories can
  consume substantial memory.
- There is no pause/resume, retry UI, parallel-batch support, GPU selector, or live
  convergence graph. Abrupt termination may leave incomplete artifacts/statuses.
- With Excel disabled, configuration/status are preserved, but the experiment
  runner does not persist a numerical result or best route. The solver's direct
  Python return value is separate from persisted experiment artifacts.
- Analysis needs valid sampled Excel histories. Empty histories are not usable,
  and no automatic aggregation spans run directories or singleton batch runs.
- Repetition IDs are labels, not seeds. Solver randomness and process scheduling
  do not guarantee reproducible trajectories across executions or platforms.
- The refueling model does not guarantee physically feasible tours. Fuel-related
  controls do not add a separate feasibility validator.
- Inputs supplied directly to solvers remain shared references and must not be
  modified during the solver's lifetime.
