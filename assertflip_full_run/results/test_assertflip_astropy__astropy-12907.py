import numpy as np
import pytest
from astropy.modeling import models as m
from astropy.modeling.separable import separability_matrix

def test_nested_compound_model_separability_bug_exposure():
    cm = m.Linear1D(10) & m.Linear1D(5)
    nested_model = m.Pix2Sky_TAN() & cm
    
    result = separability_matrix(nested_model)
    
    expected_correct_output = np.array([[ True,  True, False, False],
                                        [ True,  True, False, False],
                                        [False, False,  True, False],
                                        [False, False, False,  True]])
    
    assert np.array_equal(result, expected_correct_output), "The separability matrix output is incorrect."
