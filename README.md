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
- `config/run_options.json`: datasets, run settings, and analysis output names.
- `Datasets/`: input datasets; original file names are preserved.
- `Results/<dataset>/`: generated run files and analysis workbooks. Run creates each directory as needed.

The devcontainer installs the Python dependencies automatically.
