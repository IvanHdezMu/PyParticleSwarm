# TSP particle swarm experiments

`tsp_pso` combines **TSP** (*Traveling Salesperson Problem*) and **PSO** (*Particle Swarm Optimization*).

Run `python3 main.py` to open the **Experiment Runner** desktop GUI. A graphical
Tk display is required; install the existing `.devcontainer/requirements.txt`
dependencies (including CustomTkinter). Use `python3 main.py --terminal` for the
unchanged legacy run/analysis menus, including historical result analysis.

## Experiment Runner

Start with **Custom configuration** or any of the 22 editable presets. Select one registered dataset and one compatible problem type, then enter your
own numeric values. Fuel capacity and efficiency are single values in the GUI;
other scientific numeric controls retain their editable sweeps.
Numeric fields have an **Add** button (or press Enter) and removable value chips.
Values retain insertion order; duplicates and invalid values are rejected. Add a
replacement before removing the last value. Boolean sweep controls allow Off,
On, or both. Presets populate the form without executing anything.

The collapsed **Advanced settings** section contains the reset threshold divisor,
first repetition ID, progress warmup multiplier, and output directory. Legacy
presets retain non-1 repetition IDs even when that section is collapsed.

The exact **Planned runs** count comes from the same lazy expansion used for
execution. Conditional fields do not multiply irrelevant runs: k applies only to
operators 4/5/15, operator share to 12/15/21, fuel settings to TSPWR, and reset
settings when reset is enabled. For example, operators 10 and 15 with three
k-values produce four operator branches, not six. Repetitions multiply the count;
the first repetition ID can be 17 or another positive integer and is **not a seed**.

`c1` is a node-scaled search-budget multiplier, not an outer iteration count.
Consumption is **km/liter**. Numeric inputs are not restricted to preset values,
and requested k is never clamped by the editor. The existing solver may internally
handle k larger than node count; its semantics are unchanged.

The problem-type selector shows only modes supported by the selected dataset. Browsing reads
metadata only. Inactive settings remain in the configuration for later edits.
Click **Run batch**, review the exact count and destination, and confirm. Execution
runs sequentially in a separate CPU process while the GUI remains responsive.
The form may be edited for a later batch; the launched configuration is frozen.

Batch output is stored under:

```text
Results/batches/<batch-id>/
  batch.json                 # original configuration and dataset metadata
  manifest.sqlite3           # durable status of dispatched runs
  execution.log              # solver output and process diagnostics
  runs/<ordinal>/<dataset>/<legacy-run-directory>/
    run_config.json
    <legacy-result-name>.xlsx
```

An alternative output directory replaces `Results`; relative paths are resolved
from the project root. Pending runs are implicit, so creating a huge batch does
not insert a database row for every possible execution. Completed runs are
committed individually. A failed run stops the batch; later runs remain pending.

**Ctrl+C in the launching terminal**, or closing the window and confirming the
interruption, stops the current batch. Completed files/statuses remain saved;
the unconfirmed active run is marked interrupted and later runs stay pending.
Partial active-run artifacts may remain. If the OS kills the entire application
or power is lost, a manifest can retain a stale running state; there is no automatic
recovery/resume UI yet. Batches can also be started headlessly, once created, with
`python3 -m tsp_pso.experiments.batch_executor PATH_TO_BATCH` (new pending batches only).

Current limitations:

- Registered datasets only; generated MITECO file discovery/import is deferred.
- CPU-only, one run at a time; each run reloads its dataset. Dense matrices and
  existing solver history buffers can still consume substantial memory.
- No pause/resume, retries, parallel batches, GPU selector, or convergence graphs.
- Excel-off runs preserve configuration/status but the unchanged runner does not
  persist a numerical result or best route.
- Results use singleton legacy execution directories. Cross-repetition batch
  aggregation is deferred; the terminal analysis path remains available for old
  result directories. New raw Excel files and their snapshots are retained.
- Solver randomness and refueling feasibility behavior are unchanged. The GUI
  does not guarantee reproducible random trajectories or physically feasible tours.

See [the architecture](docs/experiment-runner-design.md) for the separation between
configuration, lazy expansion, persistence, the GUI, and the legacy solver adapter.

## Project layout

- `main.py`: desktop entry point, with `--terminal` compatibility mode.
- `tsp_pso/experiments/experiment_config.py`, `experiment_batch.py`: validated configuration, preset import, lazy expansion and counting.
- `tsp_pso/experiments/batch_store.py`, `batch_executor.py`: persistent sequential execution and legacy solver adapter.
- `tsp_pso/presentation/experiment_gui.py`: CustomTkinter batch editor.
- `.devcontainer/requirements.txt`: Python dependencies installed automatically by the devcontainer.
- `tsp_pso/application/runner.py`: experiment setup, dataset loading, and execution.
- `tsp_pso/analysis/analysis.py`: result validation and summaries.
- `tsp_pso/algorithms/particle_swarm.py`: shared particle swarm algorithm.
- `tsp_pso/infrastructure/tsplib/`: TSPLIB distance-matrix readers.
- `config/datasets.json`: dataset definitions.
- `config/experiments.json`: output directory, experiment defaults, ordered runs, and analysis output names.
- `config/historical_analyses.json`: analysis definitions for historical results.
- `datasets/TSPLIB/` and `datasets/Ottoni/`: input datasets grouped by source; original file names are preserved.
- `Results/<dataset>/<timestamp>_<parameters>/`: one directory per experiment execution, containing raw Excel files, `run_config.json`, and the analysis workbook.

The devcontainer installs the Python dependencies automatically.

## Execution output

Each experiment execution reserves a new directory using a UTC timestamp with
second precision and a compact summary of its parameter values. Executions with
the same directory name in the same second receive `__2`, `__3`, and so on through
an atomic directory-creation check. Existing run directories are never reused.
All sweep combinations and repetitions from one execution share that directory.
`execute()` returns its path.

`run_config.json` records the complete effective experiment configuration,
including sweep lists, repetition bounds/step, and `created_at`. It is written
even when Excel output is disabled. Existing raw filename formats are preserved
for the current catalog; a suffix is added only when a varying parameter would
otherwise be omitted and cause a collision within a run.

The analysis menu keeps its existing experiment ordering. Selecting an experiment
scans all timestamped run directories for that dataset, including runs with other
labels or configurations. Each run is analyzed independently from its saved
configuration, and its summary is written into the same directory. Malformed
snapshots, runs without Excel output, and incomplete or invalid workbooks are
skipped; incomplete workbook runs produce a diagnostic. No results are combined
across run directories. Analysis can be invoked directly with
`analyze_runs(dataset_directory)` from `tsp_pso.analysis.analysis`.

Historical analysis definitions retain their existing paths and behavior. Old
flat-layout results are not automatically migrated into timestamped runs.
