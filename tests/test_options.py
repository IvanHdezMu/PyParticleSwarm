import contextlib
import io
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import analysis as analysis_module
import main


class RunOptionsTests(unittest.TestCase):
    def test_existing_experiments_and_filenames(self):
        experiments = main.build_experiments()
        self.assertEqual(len(experiments), 21)
        self.assertEqual([e.count for e in experiments],
                         [1] * 10 + [270, 180, 80, 120, 50, 4, 5] + [120] * 4)
        expected = {
            'standard': 'berlin52_True_8_2000_21_10_0.2_0.8_1.xlsx',
            'berlin_grid': 'berlin52_True_8_1000_10_10_1_0.0_0.4.xlsx',
            'bays': 'bays29_True_2_2000_10_1.xlsx',
            'fuel': 'Bahia30D_True_8_1200_10_False_False_1.xlsx',
        }
        for index in (10, 11, 12, 17):
            experiment = experiments[index]
            self.assertEqual(main.result_filename(experiment, next(experiment.configurations())),
                             expected[experiment.style])

    def test_execute_uses_configured_algorithm_options(self):
        experiment = main.Experiment('berlin52', 'sample', (10,), max_capacity=90,
                                     consumption=5, permut_reset=False, k=7)
        with patch.object(main, 'load_dataset', return_value=('matrix', None)), \
             patch.object(main, 'ParticleSwarm_VarOptMultiprocess') as algorithm, \
             contextlib.redirect_stdout(io.StringIO()):
            main.execute(experiment)
        self.assertEqual(algorithm.call_args.kwargs['maxCapacity'], 90)
        self.assertEqual(algorithm.call_args.kwargs['consumption'], 5)
        self.assertFalse(algorithm.return_value.run.call_args.kwargs['permutReset'])
        self.assertEqual(algorithm.return_value.run.call_args.kwargs['k'], 7)

    def test_main_dispatches_both_modes(self):
        with patch('builtins.input', side_effect=['invalid', '4', '1', '1']), \
             patch.object(main, 'execute') as execute, contextlib.redirect_stdout(io.StringIO()):
            main.main()
        execute.assert_called_once_with(main.EXPERIMENTS[0])
        with patch('builtins.input', side_effect=['2', '11']), \
             patch.object(analysis_module, 'first_missing_result', return_value=None), \
             patch.object(analysis_module, 'analyze') as analyze, contextlib.redirect_stdout(io.StringIO()):
            main.main()
        self.assertEqual(analyze.call_args.args[0]['id'], 'berlin52_c1 and probability sweep')
        with patch('builtins.input', side_effect=['0']), \
             patch.object(main, 'execute') as execute, contextlib.redirect_stdout(io.StringIO()):
            main.main()
        execute.assert_not_called()


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.option = {'id': 'test', 'label': 'Test', 'parameters': {'N': [8, 16]},
                       'repetitions': {'start': 1, 'stop': 3},
                       'input_template': 'input_{N}_{number}.xlsx',
                       'columns': ['N'], 'output': 'summary.xlsx'}
        for n in (8, 16):
            pd.DataFrame({'Result': [20, 5, 5], 'Step': [1, 3, 4]}).to_excel(
                self.root / f'input_{n}_1.xlsx', index=False)
            pd.DataFrame({'Result': [8, 12], 'Step': [7, 9]}).to_excel(
                self.root / f'input_{n}_2.xlsx', index=False)

    def test_aggregation_and_excel_output(self):
        with contextlib.redirect_stdout(io.StringIO()):
            table = analysis_module.analyze(self.option, root=self.root)
        self.assertEqual(table['N'].tolist(), [8, 16])
        self.assertEqual(table['mean_minimum_result'].tolist(), [6.5, 6.5])
        self.assertEqual(table['mean_step_of_minimum'].tolist(), [5, 5])
        self.assertEqual(table['best_result'].tolist(), [5, 5])
        saved = pd.read_excel(self.root / 'summary.xlsx')
        pd.testing.assert_frame_equal(table, saved, check_dtype=False)

    def test_missing_file_does_not_replace_existing_summary(self):
        output = self.root / 'summary.xlsx'
        output.write_bytes(b'existing summary')
        (self.root / 'input_16_2.xlsx').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'input_16_2.xlsx'):
            analysis_module.analyze(self.option, root=self.root)
        self.assertEqual(output.read_bytes(), b'existing summary')

    def test_invalid_workbook_does_not_create_summary(self):
        pd.DataFrame({'Other': [1]}).to_excel(self.root / 'input_8_1.xlsx', index=False)
        with self.assertRaisesRegex(ValueError, 'Result or Step'):
            analysis_module.analyze(self.option, root=self.root)
        self.assertFalse((self.root / 'summary.xlsx').exists())

    def test_configured_analyses_are_available_from_main(self):
        options = analysis_module.load_analysis_options()
        self.assertEqual({option['id'] for option in options},
                         {'00', '02_08'} |
                         {f'{e.dataset}_{e.label}' for e in main.EXPERIMENTS})
        for number, option in main.analysis_menu_options(options).items():
            with self.subTest(analysis=option['id']), \
                 patch('builtins.input', side_effect=['2', str(number)]), \
                 patch.object(analysis_module, 'first_missing_result', return_value=None), \
                 patch.object(analysis_module, 'analyze') as analyze, \
                 contextlib.redirect_stdout(io.StringIO()):
                main.main()
                analyze.assert_called_once_with(option)

    def test_analysis_selection_matches_run_numbers(self):
        options = analysis_module.load_analysis_options()
        for number, experiment in enumerate(main.EXPERIMENTS, 1):
            if not experiment.excel:
                continue
            with self.subTest(run=number), \
                 patch('builtins.input', side_effect=['2', str(number)]), \
                 patch.object(analysis_module, 'first_missing_result', return_value=None), \
                 patch.object(analysis_module, 'analyze') as analyze, \
                 contextlib.redirect_stdout(io.StringIO()):
                main.main()
            selected = analyze.call_args.args[0]
            self.assertEqual(selected['experiment'], {'dataset': experiment.dataset,
                                                     'label': experiment.label})
        menu = main.analysis_menu_options(list(reversed(options)))
        self.assertTrue(all(number in menu for number in range(1, 22)))
        self.assertEqual(menu[8]['id'], 'Minas24D_individual')
        self.assertEqual(menu[11]['id'], 'berlin52_c1 and probability sweep')
        self.assertEqual(menu[21]['id'], 'Minas57D_circuit and initial tank')
        with patch('builtins.input', side_effect=['2', '24', '11']), \
             patch.object(analysis_module, 'first_missing_result', return_value=None), \
             patch.object(analysis_module, 'analyze') as analyze, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            main.main()
        self.assertIn('That number is not on the menu.', output.getvalue())
        self.assertEqual(analyze.call_args.args[0]['id'], 'berlin52_c1 and probability sweep')

    def test_missing_run_8_results_offer_execution(self):
        missing = self.root / 'missing.xlsx'
        with patch('builtins.input', side_effect=['2', '8', 'n']), \
             patch.object(analysis_module, 'first_missing_result', return_value=missing), \
             patch.object(main, 'execute') as execute, \
             patch.object(analysis_module, 'analyze') as analyze, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            main.main()
        self.assertIn('Missing results for option 8', output.getvalue())
        execute.assert_not_called()
        analyze.assert_not_called()

        with patch('builtins.input', side_effect=['2', '8', 'y']), \
             patch.object(analysis_module, 'first_missing_result', return_value=missing), \
             patch.object(main, 'execute') as execute, \
             patch.object(analysis_module, 'analyze') as analyze, \
             contextlib.redirect_stdout(io.StringIO()):
            main.main()
        execute.assert_called_once_with(main.EXPERIMENTS[7])
        self.assertEqual(analyze.call_args.args[0]['id'], 'Minas24D_individual')

    def test_run_8_saves_results_for_analysis_8(self):
        experiment = main.EXPERIMENTS[7]
        analysis = main.analysis_menu_options(analysis_module.load_analysis_options())[8]

        def save_results(**kwargs):
            self.assertTrue(kwargs['excel'])
            self.assertTrue(kwargs['verbose'])
            pd.DataFrame({'Result': [20, 5], 'Step': [1, 3]}).to_excel(
                kwargs['file_path'], index=False)

        with patch.object(main, 'load_dataset', return_value=('matrix', None)), \
             patch.object(main, 'ParticleSwarm_VarOptMultiprocess') as algorithm, \
             contextlib.redirect_stdout(io.StringIO()):
            algorithm.return_value.run.side_effect = save_results
            main.execute(experiment, output_dir=self.root / main.RUN_OPTIONS['output_dir'])
            table = analysis_module.analyze(analysis, root=self.root)
        self.assertEqual(table['best_result'].tolist(), [5])
        result = self.root / main.RUN_OPTIONS['output_dir'] / 'Minas24D' / \
            main.result_filename(experiment, next(experiment.configurations()))
        self.assertTrue(result.is_file())
        self.assertTrue((self.root / analysis['output']).is_file())

    def test_current_analyses_read_exactly_the_files_written_by_run(self):
        experiments = {(e.dataset, e.label): e for e in main.build_experiments() if e.excel}
        options = [a for a in analysis_module.load_analysis_options() if 'experiment' in a]
        self.assertEqual(len(options), len(experiments))
        for option in options:
            with self.subTest(analysis=option['id']):
                reference = option['experiment']
                experiment = experiments[(reference['dataset'], reference['label'])]
                expected = [str(Path(main.RUN_OPTIONS['output_dir']) / experiment.dataset /
                                main.result_filename(experiment, configuration))
                            for configuration in experiment.configurations()]
                actual = []
                for values in product(*option['parameters'].values()):
                    configuration = dict(zip(option['parameters'], values))
                    actual.extend(option['input_template'].format(**configuration, number=number)
                                  for number in analysis_module.repetition_numbers(option))
                self.assertEqual(actual, expected)

    def test_analysis_tracks_changes_to_run_options(self):
        options = main.load_run_options()
        options['output_dir'] = 'other_results'
        options['defaults']['k'] = 7
        entry = options['experiments'][10]
        entry.update(steps=[100], minimums=[0.1], maximums=[0.9],
                     repetitions={'start': 3, 'stop': 5})
        path = self.root / 'run_options.json'
        path.write_text(json.dumps(options), encoding='utf-8')
        analysis = next(a for a in analysis_module.load_analysis_options(run_options_path=path)
                        if a['id'] == 'berlin52_c1 and probability sweep')
        self.assertEqual(analysis['input_template'],
                         'other_results/berlin52/berlin52_True_{N}_{c1}_{optType}_7_{number}_{minR}_{maxR}.xlsx')
        self.assertEqual(analysis['output'], 'other_results/berlin52/Analysis_berlin52_grid.xlsx')
        self.assertEqual(analysis['parameters']['c1'], [100])
        self.assertEqual(analysis['parameters']['minR'], [0.1])
        self.assertEqual(list(analysis_module.repetition_numbers(analysis)), [3, 4])

    def test_execute_outputs_can_be_analyzed_for_every_filename_style(self):
        for index in (0, 7, 10, 11, 12, 17):
            options = main.load_run_options()
            entry = options['experiments'][index]
            entry.update(steps=[10], particles=[2], minimums=[0.2], maximums=[0.8],
                         rings=[True], full_tanks=[False],
                         repetitions={'start': 1, 'stop': 3})
            experiment = main.build_experiments(options)[index]
            reference = {'id': 'integration', 'experiment': {'dataset': experiment.dataset,
                         'label': experiment.label}, 'output': 'summary.xlsx'}
            analysis = analysis_module.analysis_for_experiment(reference, options)

            def save_results(**kwargs):
                pd.DataFrame({'Result': [20, 5, 5], 'Step': [1, 3, 4]}).to_excel(
                    kwargs['file_path'], index=False)

            with self.subTest(style=experiment.style), \
                 patch.object(main, 'load_dataset', return_value=('matrix', None)), \
                 patch.object(main, 'ParticleSwarm_VarOptMultiprocess') as algorithm, \
                 contextlib.redirect_stdout(io.StringIO()):
                algorithm.return_value.run.side_effect = save_results
                main.execute(experiment, output_dir=self.root / options['output_dir'])
                table = analysis_module.analyze(analysis, root=self.root)
                self.assertEqual(table['mean_minimum_result'].tolist(), [5])
                self.assertEqual(table['mean_step_of_minimum'].tolist(), [3])

    def test_references_to_missing_or_unsaved_experiments_are_rejected(self):
        reference = {'id': 'invalid', 'experiment': {'dataset': 'berlin52',
                     'label': 'individual'}, 'output': None}
        with self.assertRaisesRegex(ValueError, 'does not save results'):
            options = main.load_run_options()
            options['experiments'][0]['excel'] = False
            analysis_module.analysis_for_experiment(reference, options)
        reference['experiment']['label'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'exactly one run'):
            analysis_module.analysis_for_experiment(reference, main.load_run_options())


if __name__ == '__main__':
    unittest.main()
