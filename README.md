# TSP particle swarm experiments

`tsp_pso` combines **TSP** (*Traveling Salesperson Problem*) and **PSO** (*Particle Swarm Optimization*).

Run `python3 main.py` and choose **run** to execute an experiment or **analysis** to summarize its results. Both menus use the same experiment numbers. If results are missing, analysis offers to run the selected experiment first.

## Project layout

- `main.py`: command-line entry point.
- `.devcontainer/requirements.txt`: Python dependencies installed automatically by the devcontainer.
- `tsp_pso/runner.py`: experiment setup, dataset loading, and execution.
- `tsp_pso/analysis.py`: result validation and summaries.
- `tsp_pso/solver.py`: particle swarm algorithm.
- `tsp_pso/tsplib/`: TSPLIB distance-matrix readers.
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
`analyze_runs(dataset_directory)` from `tsp_pso.analysis`.

Historical analysis definitions retain their existing paths and behavior. Old
flat-layout results are not automatically migrated into timestamped runs.
