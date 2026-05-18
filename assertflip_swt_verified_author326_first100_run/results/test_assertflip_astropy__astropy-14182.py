import pytest
from astropy.table import QTable
import astropy.units as u
import sys
import io

def test_rst_write_with_header_rows():
    # Setup: Create a QTable instance with sample data
    tbl = QTable({'wave': [350, 950] * u.nm, 'response': [0.7, 1.2] * u.count})

    # Capture the output
    output = io.StringIO()
    sys.stdout = output

    # Attempt to write the table with header_rows argument
    tbl.write(sys.stdout, format="ascii.rst", header_rows=["name", "unit"])

    # Restore stdout
    sys.stdout = sys.__stdout__

    # Assert that no exception is raised, indicating the bug is fixed
    assert output.getvalue() != ""
