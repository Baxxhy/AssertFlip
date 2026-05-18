import pytest
from astropy.io.registry import identify_format
from astropy.table import Table

def test_identify_format_no_index_error():
    # Call identify_format with a filepath that does not have a valid FITS extension
    # This should NOT raise an IndexError if the bug is fixed
    try:
        identify_format("write", Table, "bububu.ecsv", None, [], {})
    except IndexError:
        pytest.fail("IndexError was raised, indicating the bug is still present.")
