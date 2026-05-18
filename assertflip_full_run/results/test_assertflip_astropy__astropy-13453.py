import pytest
from astropy.table import Table
from io import StringIO

def test_html_table_formats_ignored():
    # Create a sample table with floating-point numbers
    t = Table([(1.23875234858e-24, 3.2348748432e-15), (2, 4)], names=('a', 'b'))
    
    # Prepare to capture the output
    with StringIO() as sp:
        # Write the table to HTML format with specified formats
        t.write(sp, format="html", formats={"a": lambda x: f"{x:.2e}"})
        output = sp.getvalue()
    
    # Check that the output contains the expected HTML structure
    assert '<table>' in output  # Ensure the table tag is present
    assert '<tr>' in output     # Ensure there are row tags
    assert '<td>' in output     # Ensure there are data cell tags

    # Check that the values in the 'a' column are formatted as expected
    # This assertion should fail if the bug is present
    assert '1.24e-24' in output  # Expecting formatted value to be in scientific notation
    assert '3.23e-15' in output  # Expecting formatted value to be in scientific notation
