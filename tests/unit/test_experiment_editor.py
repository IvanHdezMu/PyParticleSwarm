from dataclasses import replace
import pytest
from tsp_pso.experiment_config import ExperimentConfiguration
from tsp_pso.experiment_editor import add_numeric, remove_value, toggle_value, review
from tsp_pso.experiment_batch import load_catalog, load_presets

pytestmark = pytest.mark.unit


def test_free_entry_and_ordered_removal():
    c = ExperimentConfiguration(datasets=('berlin52',))
    c = add_numeric(c,'particles','123456789012345678901234567890')
    c = add_numeric(c,'k','1000000')
    c = add_numeric(c,'consumption','8.125')
    assert c.particles == (8,123456789012345678901234567890)
    assert c.k == (10,1000000) and c.consumption == (7.0,8.125)
    c = remove_value(c,'k',10)
    assert c.k == (1000000,)
    with pytest.raises(ValueError):
        remove_value(c,'k',1000000)


@pytest.mark.parametrize('field,text', [('k','10'),('k','0'),('k','1.5'),('particles','abc'),
    ('consumption','nan'),('primary_operator_share','1.1')])
def test_rejected_drafts(field,text):
    with pytest.raises(ValueError):
        add_numeric(ExperimentConfiguration(datasets=('berlin52',)),field,text)


def test_boolean_selection_and_live_counts():
    catalog = load_catalog()
    c = ExperimentConfiguration(datasets=('berlin52',),operators=(15,))
    assert review(c,catalog)[1] == 1
    c = toggle_value(c,'ring',False)
    assert c.ring == (True,False) and review(c,catalog)[1] == 2
    c = add_numeric(c,'k','1000000')
    assert review(c,catalog)[1] == 4
    c = toggle_value(c,'ring',True)
    assert c.ring == (False,) and review(c,catalog)[1] == 2


def test_presets_remain_editable():
    for preset in load_presets():
        changed = add_numeric(preset,'particles','123456')
        assert changed.particles[-1] == 123456
        assert 123456 not in preset.particles


def test_invalid_compatibility_blocks_review():
    with pytest.raises(ValueError,match='does not support'):
        review(ExperimentConfiguration(datasets=('berlin52',),problem_modes=('tspwr',)),load_catalog())
