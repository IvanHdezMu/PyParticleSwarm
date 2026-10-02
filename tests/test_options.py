import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import analisis
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
        experiment = main.Experiment('berlin52', 'prueba', (10,), max_capacity=90,
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
        with patch('builtins.input', side_effect=['2', '1']), \
             patch.object(analisis, 'analyze') as analyze, contextlib.redirect_stdout(io.StringIO()):
            main.main()
        self.assertEqual(analyze.call_args.args[0]['id'], '00')
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
            pd.DataFrame({'Resultado': [20, 5, 5], 'Step': [1, 3, 4]}).to_excel(
                self.root / f'input_{n}_1.xlsx', index=False)
            pd.DataFrame({'Resultado': [8, 12], 'Step': [7, 9]}).to_excel(
                self.root / f'input_{n}_2.xlsx', index=False)

    def test_aggregation_and_excel_output(self):
        with contextlib.redirect_stdout(io.StringIO()):
            table = analisis.analyze(self.option, root=self.root)
        self.assertEqual(table['N'].tolist(), [8, 16])
        self.assertEqual(table['media_valor_min'].tolist(), [6.5, 6.5])
        self.assertEqual(table['media_step_valor_minimo'].tolist(), [5, 5])
        self.assertEqual(table['mejor_resultado'].tolist(), [5, 5])
        saved = pd.read_excel(self.root / 'summary.xlsx')
        pd.testing.assert_frame_equal(table, saved, check_dtype=False)

    def test_missing_file_does_not_replace_existing_summary(self):
        output = self.root / 'summary.xlsx'
        output.write_bytes(b'existing summary')
        (self.root / 'input_16_2.xlsx').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'input_16_2.xlsx'):
            analisis.analyze(self.option, root=self.root)
        self.assertEqual(output.read_bytes(), b'existing summary')

    def test_invalid_workbook_does_not_create_summary(self):
        pd.DataFrame({'Other': [1]}).to_excel(self.root / 'input_8_1.xlsx', index=False)
        with self.assertRaisesRegex(ValueError, 'Resultado o Step'):
            analisis.analyze(self.option, root=self.root)
        self.assertFalse((self.root / 'summary.xlsx').exists())

    def test_configured_analyses_are_available_from_main(self):
        options = analisis.load_analysis_options()
        self.assertEqual({option['id'] for option in options}, {
            '00', '02_08', 'Bahia30D', 'Minas24D', 'Minas30D', 'Minas57D',
            'bays29_optType', 'berlin52_optType', 'berlin52_optType_2',
            'ch150', 'kroA100', 'rat195', 'st70',
        })
        for number, option in enumerate(options, 1):
            with self.subTest(analysis=option['id']), \
                 patch('builtins.input', side_effect=['2', str(number)]), \
                 patch.object(analisis, 'analyze') as analyze, \
                 contextlib.redirect_stdout(io.StringIO()):
                main.main()
                analyze.assert_called_once_with(option)


if __name__ == '__main__':
    unittest.main()
