# Constants, defaults and shared metadata

This reference describes production data identified by the audit of all 78 Python
files (42 production files and 36 test files). It distinguishes module metadata,
dataclass defaults, imported aliases and shared runtime state. Ordinary imports of
functions, classes and modules are not themselves constants.

The production inventory contains 24 module-level data definitions and nine
imported bindings to those definitions. The sections below also cover solver
class attributes and every dataclass field with a default. Values describe the
current contracts; changing them can affect compatibility even when the change
looks like a metadata edit.

- [Validation and applicability](#validation-and-applicability)
- [Expansion, fallbacks and compatibility](#expansion-fallbacks-and-compatibility)
- [Dataclass defaults](#dataclass-defaults)
- [Presentation metadata](#presentation-metadata)
- [Paths, files and imported aliases](#paths-files-and-imported-aliases)
- [Solver selection and class collaborators](#solver-selection-and-class-collaborators)
- [Analysis and result formats](#analysis-and-result-formats)
- [MITECO generator](#miteco-generator)
- [Shared state and import behavior](#shared-state-and-import-behavior)
- [Maintenance relationships](#maintenance-relationships)

## Validation and applicability

Definitions: [experiment_config.py](../tsp_pso/experiments/experiment_config.py).
These tables are not loaded from JSON. `ExperimentConfiguration.__post_init__()`
validates requests; `is_parameter_active()` describes which validated parameters
apply to a scalar combination. An inactive requested value is still validated
and retained, so editing can activate it later.

| Name | Type and current content | Consumer and effect of changing it |
| --- | --- | --- |
| `SUPPORTED_PROBLEM_MODES` | `frozenset({'tsp', 'tspwr'})` | Configuration validation. Adding a mode does not implement a solver or add dataset support. |
| `SUPPORTED_OPERATORS` | `frozenset({1, 2, 3, 4, 5, 10, 12, 15, 21})` | Configuration validation. IDs must agree with the solver's operator dispatch; GUI choices are maintained separately. |
| `OPERATORS_USING_K` | `frozenset({4, 5, 15})` | `is_parameter_active('k', ...)`. Changes affect GUI controls, branch counts and generated combinations. |
| `OPERATORS_USING_PRIMARY_SHARE` | `frozenset({12, 15, 21})` | Activates the primary particle share for mixed operators; affects GUI and expansion. |
| `FUEL_FIELDS` | `frozenset({'fuel_capacity', 'consumption', 'full_initial_tank'})` | Active only in `tspwr`. Changes affect which axes multiply the run count. |
| `RESET_FIELDS` | `frozenset({'minimum_reset_probability', 'maximum_reset_probability', 'reset_threshold_divisor'})` | Active only when permutation reset is enabled. |
| `_INTEGER_FIELDS` | `dict(particles=2, c1=1, k=1)` | Maps fields to minimum accepted integers, **not default values**. Booleans and floating-point values are rejected for these fields. |
| `_BOOLEAN_FIELDS` | `('ring', 'permutation_reset', 'full_initial_tank')` | Requires actual booleans; also contributes names to `_SWEEP_FIELDS`. |
| `_PROBABILITY_FIELDS` | `('minimum_reset_probability', 'maximum_reset_probability', 'primary_operator_share')` | Requires finite numeric values in `[0, 1]`; contributes names to `_SWEEP_FIELDS`. |
| `_POSITIVE_FIELDS` | `('fuel_capacity', 'consumption', 'reset_threshold_divisor')` | Requires finite numeric values strictly greater than zero; contributes names to `_SWEEP_FIELDS`. |
| `_SWEEP_FIELDS` | Ordered tuple shown below | Normalizes lists to tuples, rejects empty axes and duplicates, and converts axes to lists in `to_dict()`. Also identifies otherwise always-active parameters. |

The full `_SWEEP_FIELDS` order is:

```text
datasets, problem_modes, particles, c1, operators, k,
ring, permutation_reset, full_initial_tank,
minimum_reset_probability, maximum_reset_probability, primary_operator_share,
fuel_capacity, consumption, reset_threshold_divisor,
progress_warmup_multiplier
```

It is assembled at import from several tuples; it is not a live view of those
names. Reassigning `_BOOLEAN_FIELDS` later would not rebuild `_SWEEP_FIELDS`.
Its order is not the execution order: expansion defines its own axes.

The sets and tuples are immutable. `_INTEGER_FIELDS` is a mutable dictionary,
but production code treats it as read-only. These objects remain local to this
module in production; other components use the applicability function rather
than importing its internal tables.

There are two additional applicability rules in `is_parameter_active()`:
`progress_warmup_multiplier` is active when `verbose or excel`, and other known
sweep fields are active unconditionally. Probability validation deliberately does
not reorder bounds or require the minimum to be below the maximum.

## Expansion, fallbacks and compatibility

Definitions: [experiment_batch.py](../tsp_pso/experiments/experiment_batch.py).

| Name | Type | Contract and consumers |
| --- | --- | --- |
| `CONDITIONAL` | Immutable tuple | Ordered conditional axes consumed by `_branches()` and paired with generated values by `iterate_runs()`. Changing its order can change run ordinals. |
| `DEFAULTS` | Mutable dictionary, treated as read-only | Safe scalar fallbacks for inactive parameters with multiple requested values. Used by `iterate_runs()` to populate `legacy_values`; not the editor's defaults and not a JSON merge source. |
| `EXPANSION_VERSION` | Integer, currently `1` | Imported by `batch_store.create_batch()` to write `batch.json`, and by `batch_executor.execute_batch()` to check the saved version. A different version is rejected. |

`CONDITIONAL` and `DEFAULTS` currently contain the same field names:

| Position in `CONDITIONAL` | Field | `DEFAULTS` value |
| --- | --- | --- |
| 1 | `k` | `10` |
| 2 | `primary_operator_share` | `0.2` |
| 3 | `minimum_reset_probability` | `0.2` |
| 4 | `maximum_reset_probability` | `0.8` |
| 5 | `reset_threshold_divisor` | `1000` |
| 6 | `fuel_capacity` | `150.0` |
| 7 | `consumption` | `7.0` |
| 8 | `full_initial_tank` | `False` |
| 9 | `progress_warmup_multiplier` | `5` |

### From applicability to execution

`_branches()` visits datasets, problem modes, operators and reset states, in
requested order. Each branch starts with particles, `c1` and ring axes. It then
asks `is_parameter_active()` about each name in `CONDITIONAL`. An active axis
retains its requested values; an inactive axis becomes `(None,)`.

`count_runs()` and `iterate_runs()` share this branch definition. Repetitions are
added last and vary fastest. The configuration itself retains all requested
values, even those collapsed during expansion. The GUI also uses
`is_parameter_active()` to show or enable controls; it does not duplicate these
operator applicability sets.

For each inactive field, `iterate_runs()` supplies an effective legacy scalar:

- If exactly one value was requested, preserve it.
- If several values were requested, use `DEFAULTS[field]`.

For active fields, use the value selected by the Cartesian product. Scientific
fields can therefore contain `None` while `legacy_values` contains a concrete
number or boolean. [to_legacy_experiment()](../tsp_pso/experiments/batch_executor.py)
uses those effective values to construct the singleton traditional `Experiment`
passed to the runner. Changing a fallback can change saved effective arguments
even when it does not change the run count.

### Small worked example

```python
from tsp_pso.experiments.experiment_config import ExperimentConfiguration, RepetitionSpec
from tsp_pso.experiments.experiment_batch import compile_plan, count_runs, iterate_runs

configuration = ExperimentConfiguration(
    datasets=('berlin52',),
    particles=(8, 4), c1=(3,), operators=(10, 15), k=(10, 1000),
    permutation_reset=(False,),
    minimum_reset_probability=(0.2, 0.4), fuel_capacity=(150, 200),
    verbose=False, excel=False, progress_warmup_multiplier=(0, 5),
    repetitions=RepetitionSpec(2, 17),
)
plan = compile_plan(configuration)
assert count_runs(plan) == 12
```

Direct construction uses dataclass defaults for omitted fields: mode `tsp`,
ring enabled, primary share `0.2`, maximum reset probability `0.8`, consumption
`7.0`, empty tank and reset divisor `1000`. It does not read experiment JSON to
fill these values. `compile_plan()` reads catalog metadata when no catalog is
supplied, but does not load a distance matrix.

Fuel fields are inactive in TSP. Reset fields are inactive because reset is off.
Warmup is inactive because both output flags are false. Operator 10 ignores `k`;
operator 15 activates it and primary share. Consequently:

```text
operator 10: 2 particle values × 1 inactive k choice × 2 repetitions = 4
operator 15: 2 particle values × 2 k values          × 2 repetitions = 8
```

| Ordinals | Operator | Particles | Scientific `k` | Repetition IDs |
| --- | --- | --- | --- | --- |
| 1–2 | 10 | 8 | `None` | 17, 18 |
| 3–4 | 10 | 4 | `None` | 17, 18 |
| 5–6 | 15 | 8 | 10 | 17, 18 |
| 7–8 | 15 | 8 | 1000 | 17, 18 |
| 9–10 | 15 | 4 | 10 | 17, 18 |
| 11–12 | 15 | 4 | 1000 | 17, 18 |

The first run forwards legacy `k=10`, minimum reset probability `0.2`, capacity
`150.0` and warmup `5`, using fallbacks for those multi-valued inactive fields.
If the requested inactive `k` were instead `(1000,)`, it would forward `1000`.

### Persisted batches

[batch_store.py](../tsp_pso/experiments/batch_store.py) saves configuration,
descriptors, total count and `EXPANSION_VERSION` in `batch.json`.
[batch_executor.py](../tsp_pso/experiments/batch_executor.py) checks the version and
recomputed count before execution. A future change to expansion semantics or
order requires reviewing this compatibility contract; a version bump is not a
migration mechanism. No resume behavior is implied.

The current traditional presets total 1,209 configurations in 22 presets, with
counts `[1 × 10, 270, 180, 80, 120, 50, 4, 5, 120, 120, 120, 120, 10]`. Their
ordered configurations match the traditional model. This does not mean arbitrary
traditional sweeps and conditional batch sweeps have identical semantics.

## Dataclass defaults

Defaults belong to distinct contracts. They are not all aliases of `DEFAULTS`.
The dataclasses below are frozen, and their current default objects are immutable.
A field annotation without a value is not a shared constant.

### Requested batch configuration

Definition: `ExperimentConfiguration` in
[experiment_config.py](../tsp_pso/experiments/experiment_config.py). `datasets` is
required. These defaults apply to omitted constructor fields; explicit preset
values take precedence. Changing scientific defaults can change calculations or
expansion; changing output defaults affects presentation and persistence.

| Fields | Defaults | Consumers and effects |
| --- | --- | --- |
| `name` | `'Untitled batch'` | GUI, manifest and fallback legacy label. |
| `problem_modes` | `('tsp',)` | Compatibility validation, applicability and solver selection. |
| `particles`, `c1`, `operators`, `k` | `(8,)`, `(1200,)`, `(10,)`, `(10,)` | Search settings and ordered expansion. |
| `ring`, `permutation_reset` | `(True,)`, `(True,)` | Route closure and reset behavior; reset also controls active axes. |
| `minimum_reset_probability`, `maximum_reset_probability` | `(0.2,)`, `(0.8,)` | Reset probabilities when active. |
| `fuel_capacity`, `consumption`, `full_initial_tank` | `(150.0,)`, `(7.0,)`, `(False,)` | TSPWR capacity, km/liter and initial tank state. |
| `reset_threshold_divisor`, `primary_operator_share`, `progress_warmup_multiplier` | `(1000,)`, `(0.2,)`, `(5,)` | Reset threshold, mixed-operator particle allocation and recording threshold. |
| `repetitions` | `RepetitionSpec()` | Count and starting ID; immutable shared default object. |
| `verbose`, `excel` | `False`, `True` | Console output and Excel history; together determine warmup applicability. |
| `output_dir` | `Path('Results')` | Requested output base; batch storage resolves relative paths from its project root. |
| `legacy_style`, `legacy_label`, `analysis_output` | `'standard'`, `None`, `None` | Compatibility naming and analysis metadata forwarded to the traditional model. |

`RepetitionSpec`, in the same file, defaults to `count=1`, `first_id=1`. These
values control execution count and labels, not RNG seeds. Changing `first_id`
changes persisted IDs and filenames. Lists supplied to `ExperimentConfiguration`
are copied to tuples; `to_dict()` returns detached JSON-compatible data.

### Traditional experiment

Definition: [Experiment](../tsp_pso/experiments/experiment.py).
`dataset`, `label` and `steps` are required. Runner, analysis and batch adaptation
consume instances. This model preserves a full Cartesian product, including axes
that conditional batch expansion would collapse.

| Fields | Defaults | Consumers and effects |
| --- | --- | --- |
| `particles`, `opts` | `(8,)`, `(10,)` | Particle count and operator sweep. |
| `minimums`, `maximums` | `(0.2,)`, `(0.8,)` | Reset probability sweep. |
| `rings`, `full_tanks` | `(True,)`, `(False,)` | Route closure and initial tank sweep. |
| `repetitions` | `range(1, 2)` | Full-product repetition labels, varying fastest. |
| `excel`, `verbose` | `False`, `True` | Output controls; intentionally different from batch configuration defaults. |
| `refuel` | `False` | Runner's default TSP/TSPWR selection. |
| `style`, `analysis_output` | `'standard'`, `None` | Result filename conventions and analysis output metadata. |
| `max_capacity`, `consumption` | `150.0`, `7.0` | TSPWR arguments. |
| `permut_reset`, `k` | `True`, `10` | Reset enablement and k-based search argument. |
| `reset_threshold_divisor`, `primary_operator_share`, `progress_warmup_multiplier` | `1000`, `0.2`, `5` | Forwarded to `PSOConfig`. |

`build_experiments(options)` and `build_presets(options)` merge each JSON entry
with `options['defaults']` shallowly. For example, an override of `repetitions`
replaces the entire start/stop dictionary; it does not inherit missing nested
keys. The JSON defaults in [experiments.json](../config/experiments.json) are
configuration data loaded on demand, not module globals.

### Solver configuration

| Definition | Defaults and required fields | Consumer and consequences |
| --- | --- | --- |
| [PSOConfig](../tsp_pso/algorithms/core/pso_config.py) | Required `N`, `c1`; `ring_mode=False`, `reset_threshold_divisor=1000`, `primary_operator_share=0.2`, `progress_warmup_multiplier=5` | `ParticleSwarm.__init__()` copies effective settings into the instance. Changes affect direct solver construction; runner normally supplies these values explicitly. |
| [RefuelConfig](../tsp_pso/algorithms/tspwr/refuel_config.py) | `max_capacity=None`, `consumption=None`, `full_init=False` | TSPWR initialization and fuel calculations. Missing capacity/consumption are rejected by the solver; `None` is not a usable fuel value. |

`DatasetDescriptor`, `ExpansionPlan` and `ConcreteRunConfiguration` have required
fields without defaults. They do not add shared default containers.

## Presentation metadata

Definitions: [experiment_editor.py](../tsp_pso/presentation/experiment_editor.py)
and [experiment_gui.py](../tsp_pso/presentation/experiment_gui.py).
The three dictionaries here are mutable objects treated as read-only metadata.

### `NUMERIC_FIELDS`

Maps a field to `(label, numeric type)`. `parse_numeric()` uses the type to decide
whether a decimal is permitted; GUI widgets and validation messages use labels.

| Field | Label | Numeric type |
| --- | --- | --- |
| `particles` | Number of particles | `int` |
| `c1` | Search effort (c1) | `int` |
| `k` | Segment length (k) | `int` |
| `minimum_reset_probability` | Minimum reset probability | `float` |
| `maximum_reset_probability` | Maximum reset probability | `float` |
| `reset_threshold_divisor` | Reset threshold divisor | `float` |
| `primary_operator_share` | Primary operator share | `float` |
| `fuel_capacity` | Fuel capacity (L) | `float` |
| `consumption` | Fuel efficiency (km/L) | `float` |
| `progress_warmup_multiplier` | Progress warmup multiplier | `float` |

Parsing tries integers first even for a `float` field: consumption text `"7"`
becomes integer `7`, while `"7.5"` becomes float `7.5`. The same decimal text is
rejected for `k`. This preserves large integers rather than forcing them through
floating point. `ExperimentConfiguration` then performs range, type, duplicate
and finiteness validation. Changing labels affects UI; changing types affects
accepted input and must remain compatible with model validation.

### Operator IDs and labels

`OPERATOR_LABELS` determines selectable IDs and their display order. Values are
only labels; [ParticleSwarm._Opt_Type()](../tsp_pso/algorithms/core/particle_swarm.py)
implements dispatch and allocation, and `_compute_position()` calls the operators.

| ID | `OPERATOR_LABELS` text | Uses `k` | Uses primary share |
| --- | --- | --- | --- |
| 1 | Segment flip (2-opt) | No | No |
| 2 | Node relocation (2.5-opt) | No | No |
| 3 | Node swap (2-opt) | No | No |
| 4 | k-segment flip | Yes | No |
| 5 | k-segment random (legacy) | Yes | No |
| 10 | Adaptive flip / relocation | No | No |
| 12 | Mixed flip + relocation | No | Yes |
| 15 | Mixed flip + k-random | Yes | Yes |
| 21 | Mixed relocation + flip | No | Yes |

These IDs currently match `SUPPORTED_OPERATORS`. The membership sets describe
applicability, while the labels explain it to users. Editing a label does not
change an algorithm; adding a key offers a new GUI choice but does not implement
that choice in validation or the solver.

### `FIELD_HELP`

Defined only in `experiment_gui.py`, this dictionary supplies optional text for
`NumericValues.__init__()`. Its seven keys are `c1`, `k`,
`primary_operator_share`, `minimum_reset_probability`,
`maximum_reset_probability`, `reset_threshold_divisor`, and
`progress_warmup_multiplier`. Their text explains node-scaled effort, segment
size, primary share, probabilities, reset threshold and recording warmup,
respectively. Changes affect help text only, not validation or calculations.

## Paths, files and imported aliases

Three modules independently define `ROOT = Path(__file__).resolve().parents[2]`.
They currently resolve to the same project directory, but are not aliases of
each other. A `Path` is immutable; its module binding can still be replaced.

| Definition | Local consumers | Effect of changing it |
| --- | --- | --- |
| [infrastructure/experiment_options.py](../tsp_pso/infrastructure/experiment_options.py) | `load_run_options()`, `load_catalog_options()`, `load_preset_options()` | Changes default configuration locations. Also supplies the aliases below. |
| [application/runner.py](../tsp_pso/application/runner.py) | `load_dataset()`, `execute()`, `create_run_directory()` | Changes default dataset and configured output bases. Explicit output paths retain working-directory semantics. |
| [analysis/analysis.py](../tsp_pso/analysis/analysis.py) | `first_missing_result()`, `analyze()` | Changes the default base for relative analysis paths; explicit `root` takes precedence. |

The infrastructure root is imported into:

| Alias location | Consumer |
| --- | --- |
| [experiment_batch.py](../tsp_pso/experiments/experiment_batch.py) | `load_catalog()` and `load_presets()` form the original configuration paths. The `ROOT` name is retained for compatibility. |
| [batch_store.py](../tsp_pso/experiments/batch_store.py) | `create_batch()` resolves a relative output directory. |
| [experiment_process.py](../tsp_pso/experiments/experiment_process.py) | `BatchProcess` launches its child with `cwd=ROOT`. |
| [experiment_gui.py](../tsp_pso/presentation/experiment_gui.py) | `validated_review()` checks output paths against the batch storage base. |

There are five other imported data bindings: `SOLVER_REGISTRY` in runner,
`EXPANSION_VERSION` in both batch store and executor, and `NUMERIC_FIELDS` and
`OPERATOR_LABELS` in the experiment GUI. They reference the defining objects,
not independent copies.

For a mutable dictionary, `from module import TABLE` shares the object: modifying
`TABLE[key]` is visible through all aliases. Reassigning `module.TABLE` instead
leaves earlier imports pointing at the previous object. Similarly, replacing
`experiment_options.ROOT` after imports does not update the four aliases.
`dict(TABLE)` creates a shallow copy, not a recursively independent structure.

### Reader contracts

- `load_catalog_options()` reads only `config/datasets.json` by default.
- `load_preset_options()` reads only `config/experiments.json` by default.
- `load_run_options()` reads experiments and, unless the JSON already contains
  `datasets`, adds sibling `datasets.json` and `historical_analyses.json` sections.

All three infrastructure readers accept an optional path. Falsey paths select
the default; explicit relative paths use the working directory. The public
`experiment_batch.load_catalog()` and `load_presets()` remain no-argument
wrappers. Descriptor construction and `build_presets()` stay in `experiments/`.
Changing one reader to use another can change which files are required and which
errors occur; these readers are not interchangeable.

No configuration is loaded just by defining `ROOT`. Paths embedded in JSON are
not automatically made absolute by the readers. The
[dataset reader](../tsp_pso/infrastructure/dataset_reader.py) supports descriptor
formats `euc`, `matrix`, `json` and `excel`; these format strings are local
contracts, not another global registry.

## Solver selection and class collaborators

### `SOLVER_REGISTRY`

Definition: [solver_registry.py](../tsp_pso/algorithms/solver_registry.py).

```python
SOLVER_REGISTRY = {
    'tsp': (TSPParticleSwarm, tsp_arguments),
    'tspwr': (TSPWRParticleSwarm, tspwr_arguments),
}
```

`runner.execute()` indexes this dictionary with the requested problem type. The
entry provides a solver class and an argument builder. `tsp_arguments()` returns
an empty dictionary; `tspwr_arguments()` adds dataset prices and `RefuelConfig`
constructed from experiment capacity, consumption and initial tank state.

The dictionary is mutable, but normal production execution does not modify it.
Tests replace entries through the shared `runner.SOLVER_REGISTRY` reference and
exercise an additional solver. Removing an entry or changing its builder changes
execution or raises a lookup/constructor error. Registering a solver does not
implicitly add a supported mode to batch validation or dataset metadata.

### `ParticleSwarm` class attributes

Definition: [particle_swarm.py](../tsp_pso/algorithms/core/particle_swarm.py).

| Attributes | Declared value | Scope and consumer |
| --- | --- | --- |
| `swarm_size`, `member_size`, `N`, `c1` | `None` | Immutable class sentinels; constructor assigns effective values on each instance. |
| `pos`, `best`, `global_best`, `fx`, `f_best`, `f_global_best`, `vel`, `nIter`, `k`, `cur_steps` | `None` | Sentinels before `_clear()`; arrays and progress are subsequently instance state. They are not shared swarm arrays. |
| `result_writer` | `None` | Optional class-level object exposing `write(history, file_path)`. `run()` otherwise creates `ExcelResultWriter`. |
| `console_presenter` | `None` | Optional class-level presenter used by `_get_console_presenter()`; otherwise creates `ConsolePresenter`. |
| `particle_executor_factory` | `None` | Optional zero-argument factory used by `run()`; otherwise uses `ParticleExecutor`. The active executor is local to the run. |

The last three are intentionally configurable shared bindings, read through
`type(self)`. Replacing one affects instances of that class, including subclasses
that inherit the attribute. They are not placed in serialized solver instance
state because bound worker methods serialize that state. Moving them onto an
instance could change multiprocessing behavior. Tests use temporary replacements;
production does not rebind them during normal execution.

`self.pos = ...` shadows the class sentinel on one instance; it does not modify
`ParticleSwarm.pos`. Replacing these sentinels with mutable class containers would
change that isolation contract.

The specialization labels are immutable strings:

- [TSPParticleSwarm._result_label](../tsp_pso/algorithms/tsp/tsp_particle_swarm.py):
  `'DISTANCE'`.
- [TSPWRParticleSwarm._result_label](../tsp_pso/algorithms/tspwr/tspwr_particle_swarm.py):
  `'REFUEL COST'`.

`ParticleSwarm.__str__()` passes the label with the physical measure from
`_dataToSave()` to the presenter. A label change affects displayed text, not the
objective minimized by the solver.

## Analysis and result formats

`METRICS`, defined in [analysis.py](../tsp_pso/analysis/analysis.py), is a mutable
list treated as read-only:

```python
['mean_minimum_result', 'mean_step_of_minimum', 'best_result']
```

`analyze()` zips it with three computed values, in that order: mean of the
per-repetition minima, mean step at those minima, and best minimum across
repetitions. It also appends this list after configuration columns when creating
the output DataFrame. Reordering names without their calculations mislabels
results; renaming them changes the analysis output schema. For minima `10, 14`
at steps `3, 5`, the three values are `12, 4, 10`.

[ExcelResultWriter.write()](../tsp_pso/infrastructure/writers/excel_result_writer.py)
defines its `['Step', 'Result']` columns locally. Analysis requires those exact
input names. They are a cross-module file contract, not module globals.
Likewise, styles `standard`, `berlin_grid`, `bays` and `fuel` are validated in the
configuration model and interpreted by
[result_naming.py](../tsp_pso/experiments/result_naming.py). Changing a style or its
meaning affects filenames and result discovery. No global filename table exists.

## MITECO generator

Definitions: [generate_miteco.py](../tools/dataset_generators/generate_miteco.py).

| Name | Value | Consumers and consequences |
| --- | --- | --- |
| `SOURCE_URL` | `https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/` | CLI `main()` and generator GUI download from it; `generate()` saves it as provenance metadata. Changing it affects downloads and recorded source. |
| `DEFAULT_OUTPUT` | Project root / `datasets/MITECO_Spain` | `generate()` uses it when no output is supplied; the GUI uses it to initialize its output field. Changing it affects default output location, not explicit paths. |

Both objects are immutable and are not changed by production code. The
[generator GUI](../tools/dataset_generators/gui.py) imports the module as
`generator` and reads `generator.SOURCE_URL` and `generator.DEFAULT_OUTPUT` when
needed. This differs from importing the individual values as local aliases.

The saved metadata contains local literal `generator_version=2`. It describes
the dataset generator, not experiment expansion, and is unrelated to
`EXPANSION_VERSION`. Station selection uses a local `random.Random(seed)` object.
That seed is distinct from experiment repetition labels.

## Shared state and import behavior

Module tables are constructed during import, as are `ROOT` paths, the immutable
`RepetitionSpec()` default, `Path('Results')` and the traditional repetition range.
The project does not load catalogs, matrices or batches, open SQLite connections,
start a process pool or create GUI windows merely by importing these modules.
Imported libraries can have their own initialization behavior.

Mutable metadata is not automatically problematic runtime state. Production does
not mutate `DEFAULTS`, `_INTEGER_FIELDS`, `NUMERIC_FIELDS`, `OPERATOR_LABELS`,
`FIELD_HELP`, `METRICS` or `SOLVER_REGISTRY`. The solver's per-instance arrays and
the GUI's current configuration are different from module metadata.

Some genuinely shared state belongs to dependencies or the process:

- Solver calls to `np.random` consume NumPy's process-global RNG state. It is not
  a constant defined by this repository; repetition IDs do not seed it.
- Both GUI constructors set CustomTkinter appearance and theme. Widgets read
  shared theme metadata, but these changes happen at application construction,
  not module import.
- The experiment GUI installs a `SIGINT` handler while running its event loop
  and restores the previous handler in `finally`.

Tests contain `pytestmark`, sample catalogs, expected operator candidates,
validation inputs and available multiprocessing start methods. They are test
metadata, not production configuration. Tests also temporarily patch roots,
registry entries and solver class collaborators; the shared NumPy RNG state is
saved and restored by the fixture. See [tests](../tests/) for these contracts.

## Maintenance relationships

Keep metadata near the responsibility that interprets it. A single project-wide
`constants.py` would obscure the different contracts described here.

| Relationship | Guaranteed by construction or consumer | Requires coordinated maintenance |
| --- | --- | --- |
| Validation groups and `_SWEEP_FIELDS` | Several groups are expanded directly into the tuple. | Correct classification and coverage of newly added model fields. |
| `CONDITIONAL` and expansion values | `_branches()` and `iterate_runs()` share the same order. | Applicability rules, concrete-run fields and fallback keys must remain compatible. |
| `CONDITIONAL` and `DEFAULTS` | Lookup is by field name. | Their key sets currently match; no automatic generation enforces that match. |
| GUI activity and expansion activity | Both use `is_parameter_active()`. | Applicability must still reflect the scientific implementation. |
| Operator validation, labels and solver dispatch | Each consumer explicitly interprets IDs. | Current ID sets agree, but none is generated from all the others. |
| Numeric parsing and model validation | Parsed input passes through the model. | GUI metadata must use valid field names and compatible types. |
| Version and persisted expansion | Executor checks the saved version and count. | Semantic/order changes require a compatibility decision. |
| Result columns and analysis | Analysis validates required input columns. | Names, metric order and calculations must agree. |
| Repeated defaults across models and JSON | Explicit configuration values take precedence. | Similar numbers do not prove interchangeable contracts; do not automatically unify them. |

Existing globals outside these tables are ordinary imported modules/functions or
classes, including compatibility reexports such as `runner.Experiment`.
`main.py`, terminal, storage helpers, TSPLIB readers and package initializers do
not introduce additional module data constants. Local literals such as the
SQLite timeout or interruption grace period are operational policy, not shared
module state.
