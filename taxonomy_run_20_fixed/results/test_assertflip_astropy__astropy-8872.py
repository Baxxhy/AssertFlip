import numpy as np
import astropy.units as u
import pytest

def test_quantity_float16_upgrade():
    # Create a Quantity from np.float16
    q_float16 = np.float16(1) * u.km
    # Assert that the dtype of the Quantity created from np.float16 is NOT float64
    assert q_float16.dtype != np.float64  # This should fail if the bug is present

    # Create Quantities from other float types for comparison
    q_float32 = np.float32(1) * u.km
    q_float64 = np.float64(1) * u.km
    q_float128 = np.float128(1) * u.km

    # Assert that the dtypes of these Quantities are as expected
    assert q_float32.dtype == np.float32  # Correct behavior
    assert q_float64.dtype == np.float64  # Correct behavior
    assert q_float128.dtype == np.float128  # Correct behavior

    # Additional edge case tests
    q_float16_neg = np.float16(-1) * u.km
    assert q_float16_neg.dtype != np.float64  # This should fail if the bug is present

    q_float16_zero = np.float16(0) * u.km
    assert q_float16_zero.dtype != np.float64  # This should fail if the bug is present

    # Test with an array of np.float16 values
    q_float16_array = np.array([np.float16(1), np.float16(2)]) * u.km
    assert q_float16_array.dtype != np.float64  # This should fail if the bug is present
