import numpy as np
import pytest
from sklearn.linear_model import LogisticRegressionCV

def test_logistic_regression_cv_no_index_error():
    # Setup: Generate synthetic data
    np.random.seed(29)
    X = np.random.normal(size=(1000, 3))
    beta = np.random.normal(size=3)
    intercept = np.random.normal(size=None)
    y = np.sign(intercept + X @ beta)

    # Instantiate the model with refit=False
    model = LogisticRegressionCV(cv=5, solver='saga', refit=False)

    # Try fitting the model and expect it to NOT raise an IndexError
    try:
        model.fit(X, y)
    except IndexError:
        pytest.fail("IndexError was raised, but it should not have been.")
