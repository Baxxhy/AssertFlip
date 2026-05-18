import pytest
import numpy as np
from astropy.time import Time
from astropy.timeseries import TimeSeries

def test_remove_required_column_exposes_bug():
    # Setup: Create a TimeSeries object with required columns
    time = Time(np.arange(100000, 100003), format='jd')
    ts = TimeSeries(time=time, data={"flux": [99.9, 99.8, 99.7]})
    ts._required_columns = ["time", "flux"]  # Set required columns

    # Attempt to remove a required column and check for the correct exception
    with pytest.raises(ValueError) as excinfo:
        ts.remove_column("flux")  # This should trigger the bug

    # Assert that the exception message does not contain the misleading information
    assert "expected 'time' as the first columns but found 'time'" not in str(excinfo.value)
