import pytest
from astropy.io.registry import identify_format
from astropy.table import Table

def test_identify_format_no_index_error():
    # This test is designed to confirm that an IndexError is NOT raised
    # when identify_format is called with a non-FITS file extension
    # and an empty args list, indicating the bug is fixed.
    try:
        identify_format("write", Table, "bububu.ecsv", None, [], {})  # This should not trigger the bug
    except IndexError:
        pytest.fail("IndexError was raised when it should not have been.")
