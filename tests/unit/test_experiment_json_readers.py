"""Single-file reader contracts and their experiment-layer adapters."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tsp_pso.experiments import experiment_batch
from tsp_pso.infrastructure import experiment_options

pytestmark = pytest.mark.unit
READERS = [
    (experiment_options.load_catalog_options, 'datasets.json'),
    (experiment_options.load_preset_options, 'experiments.json'),
]


@pytest.mark.parametrize('reader,filename', READERS)
def test_default_reader_path_is_project_relative(reader, filename, tmp_path, monkeypatch):
    with (experiment_options.ROOT / 'config' / filename).open(encoding='utf-8') as stream:
        expected = json.load(stream)
    monkeypatch.chdir(tmp_path)
    assert reader() == reader(None) == reader('') == expected


@pytest.mark.parametrize('reader,filename', READERS)
@pytest.mark.parametrize('relative', [False, True])
def test_explicit_paths_read_one_file_without_merging(reader, filename, relative, tmp_path, monkeypatch):
    directory = tmp_path / 'custom'
    directory.mkdir()
    path = directory / filename
    expected = ({'datasets': {'x': {'filename': 'relative/data'}}}
                if filename == 'datasets.json' else
                {'output_dir': 'relative/results', 'defaults': {}, 'experiments': []})
    path.write_text(json.dumps(expected), encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    selected = path.relative_to(tmp_path) if relative else path
    assert reader(selected) == reader(str(selected)) == expected
    assert list(directory.iterdir()) == [path]


@pytest.mark.parametrize('reader,filename', READERS)
@pytest.mark.parametrize('payload', [None, [], {'unexpected': 'unchanged'}])
def test_readers_do_not_validate_or_transform_decoded_values(reader, filename, payload, tmp_path):
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding='utf-8')
    assert reader(path) == payload


@pytest.mark.parametrize('reader,filename', READERS)
def test_reader_file_and_json_errors_propagate(reader, filename, tmp_path):
    path = tmp_path / filename
    with pytest.raises(FileNotFoundError) as raised:
        reader(path)
    assert raised.value.filename == str(path)
    path.write_text('{invalid', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        reader(path)


def test_catalog_adapter_preserves_order_types_and_root_alias(tmp_path, monkeypatch):
    directory = tmp_path / 'config'
    directory.mkdir()
    data = {'datasets': {
        name: dict(filename=name + '.json', format='json', source='custom',
                   problem_types=['tsp', 'tspwr']) for name in ('second', 'first')}}
    (directory / 'datasets.json').write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(experiment_batch, 'ROOT', tmp_path)
    descriptors = experiment_batch.load_catalog()
    assert type(descriptors) is tuple
    assert [d.id for d in descriptors] == ['second', 'first']
    assert all(type(d) is experiment_batch.DatasetDescriptor for d in descriptors)
    assert [asdict(d) for d in descriptors] == [
        dict(id=name, **{**entry, 'problem_types': ('tsp', 'tspwr')})
        for name, entry in data['datasets'].items()]


@pytest.mark.parametrize('loader,filename', [
    (experiment_batch.load_catalog, 'datasets.json'),
    (experiment_batch.load_presets, 'experiments.json'),
])
def test_public_adapters_preserve_errors(loader, filename, tmp_path, monkeypatch):
    directory = tmp_path / 'config'
    directory.mkdir()
    monkeypatch.setattr(experiment_batch, 'ROOT', tmp_path)
    path = directory / filename
    with pytest.raises(FileNotFoundError) as raised:
        loader()
    assert raised.value.filename == str(path)
    path.write_text('{invalid', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        loader()
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(KeyError) as raised:
        loader()
    assert raised.value.args == ('datasets' if filename == 'datasets.json' else 'experiments',)
    path.write_text('null', encoding='utf-8')
    with pytest.raises(TypeError):
        loader()


def test_imports_do_not_read_configuration_or_reverse_dependencies():
    code = '''
import sys
import json
from pathlib import Path
from unittest.mock import patch
with patch.object(Path, 'open', side_effect=AssertionError('file read')), \\
     patch('builtins.open', side_effect=AssertionError('file read')), \\
     patch.object(json, 'load', side_effect=AssertionError('JSON read')):
    from tsp_pso.infrastructure import experiment_options
    assert not any(name.startswith('tsp_pso.experiments') for name in sys.modules)
    from tsp_pso.experiments import experiment_batch
    assert experiment_batch.ROOT == experiment_options.ROOT
    assert 'tsp_pso.application.runner' not in sys.modules
'''
    result = subprocess.run([sys.executable, '-B', '-c', code],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
