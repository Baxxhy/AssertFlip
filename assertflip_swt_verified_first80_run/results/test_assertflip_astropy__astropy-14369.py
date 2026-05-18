import pytest
from astropy.table import Table
from astropy import units as u

def test_cds_unit_parsing_exposes_bug(tmpdir):
    # Setup: Create MRT formatted data
    mrt_data = """Title:
Authors:
Table:
================================================================================
Byte-by-byte Description of file: tab.txt
--------------------------------------------------------------------------------
   Bytes Format Units          Label      Explanations
--------------------------------------------------------------------------------
   1- 10 A10    ---            ID         ID
  12- 21 F10.5  10+3J/m/s/kpc2    SBCONT     Cont surface brightness
  23- 32 F10.5  10-7J/s/kpc2     SBLINE     Line surface brightness
--------------------------------------------------------------------------------
ID0001     70.99200   38.51040      
ID0001     13.05120   28.19240      
ID0001     3.83610    10.98370      
ID0001     1.99101    6.78822       
ID0001     1.31142    5.01932      
"""

    # Write the MRT data to a temporary file
    mrt_file = tmpdir.join("tab.txt")
    mrt_file.write(mrt_data)

    # Read the table using the ascii.cds format
    dat = Table.read(str(mrt_file), format='ascii.cds')

    # Get the parsed units
    sbcont_unit = dat['SBCONT'].unit
    sbline_unit = dat['SBLINE'].unit

    # Assertions to expose the bug
    # Check that the parsed unit for SBCONT is equivalent to the expected unit
    assert sbcont_unit.is_equivalent(u.J / (u.m * u.s * u.kpc**2))  # This should fail if the bug is present
    assert sbline_unit.is_equivalent(u.J / (u.s * u.kpc**2))        # This should fail if the bug is present
