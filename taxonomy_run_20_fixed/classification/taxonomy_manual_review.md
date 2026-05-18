# AssertFlip Taxonomy Manual Review

This file is a manual review of the 20-sample run using the taxonomy categories from the SWT-Bench taxonomy paper. It corrects obvious automatic-mapping mistakes by checking the actual pytest/LLM-validation evidence.

## Counts By Class
- Misimplementation: 13
- Mechanical Failure: 4
- Accepted: 2
- Requirement Misunderstanding: 1

## Counts By Subclass
- Misimplementation / Incorrect Assertion: 9
- Misimplementation / Incorrect Input/Mock: 4
- Accepted / Accepted: 2
- Mechanical Failure / Environment Error: 2
- Mechanical Failure / Incorrect File Reference: 1
- Mechanical Failure / Output Format Inconsistency: 1
- Requirement Misunderstanding / Misunderstanding Edge Case Logic: 1

## Per Instance
| project | instance | status | class | subclass | evidence |
|---|---|---|---|---|---|
| astropy | astropy__astropy-12907 | failure | Misimplementation | Incorrect Assertion | Phase A generated 10 passing candidate(s), but inversion/LLM validation rejected 10 failing candidate(s). Last validation reason: The test is incorrectly structured to validate the bug. The assertion checks if the output of the nested model is not equal to the expected output,... |
| astropy | astropy__astropy-13033 | failure | Misimplementation | Incorrect Assertion | Phase A generated 10 passing candidate(s), but inversion/LLM validation rejected 10 failing candidate(s). Last validation reason: The test does not correctly reproduce the reported bug because it incorrectly asserts that the exception message should contain the word 'missing'.... |
| astropy | astropy__astropy-13236 | failure | Misimplementation | Incorrect Assertion | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: AssertionError: assert None == ('field1', 'field2') |
| astropy | astropy__astropy-13398 | failure | Misimplementation | Incorrect Input/Mock | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: >           warnings.warn(wmsg.format('after'), AstropyWarning) E           astropy.utils.exceptions.AstropyWarning: Tried to get polar motio... |
| astropy | astropy__astropy-13579 | failure | Misimplementation | Incorrect Input/Mock | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: ValueError: Coordinate frame name "helioprojective" is not a known coordinate frame (['altaz', 'barycentricmeanecliptic', 'barycentrictrueecl... |
| astropy | astropy__astropy-13977 | failure | Misimplementation | Incorrect Assertion | Phase A generated 7 passing candidate(s), but inversion/LLM validation rejected 7 failing candidate(s). Last validation reason: The test is incorrect because it does not accurately reproduce the reported bug. The expectation that the addition of two DuckArray instances with in... |
| astropy | astropy__astropy-14096 | failure | Misimplementation | Incorrect Assertion | Phase A generated 10 passing candidate(s), but inversion/LLM validation rejected 10 failing candidate(s). Last validation reason: The test is incorrectly designed to check for an error message related to a non-existent attribute 'random_attr', but the actual error raised is ab... |
| astropy | astropy__astropy-14182 | failure | Misimplementation | Incorrect Assertion | Phase A generated 10 passing candidate(s), but inversion/LLM validation rejected 10 failing candidate(s). Last validation reason: The test fails to reproduce the reported bug because the error message it checks for does not match the actual error raised. The test expects a Typ... |
| astropy | astropy__astropy-14309 | success | Accepted | Accepted | AssertFlip accepted a final bug-revealing test for this instance. |
| astropy | astropy__astropy-14365 | failure | Misimplementation | Incorrect Assertion | Phase A generated 1 passing candidate(s), but inversion/LLM validation rejected 1 failing candidate(s). Last validation reason: The test does not correctly reproduce the reported bug because it fails due to a warning about the `table_id` not being specified, rather than a Valu... |
| astropy | astropy__astropy-14369 | failure | Requirement Misunderstanding | Misunderstanding Edge Case Logic | Phase A generated 10 passing candidate(s), but inversion/LLM validation rejected 10 failing candidate(s). Last validation reason: The test is incorrectly asserting the expected unit for the 'SBCONT' column. The expected unit is 'J / (m s kpc2)', but the actual parsed unit is '... |
| astropy | astropy__astropy-14508 | failure | Mechanical Failure | Output Format Inconsistency | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: FAILED astropy/tests/test_rh12ef68.py::test_fits_card_float_formatting_bug - astropy.io.fits.verify.VerifyWarning: Card is too long, comment ... |
| astropy | astropy__astropy-14539 | failure | Misimplementation | Incorrect Assertion | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: ValueError: The truth value of an array with more than one element is ambiguous. Use a.any() or a.all() |
| astropy | astropy__astropy-14995 | failure | Misimplementation | Incorrect Assertion | Phase A generated 9 passing candidate(s), but inversion/LLM validation rejected 9 failing candidate(s). Last validation reason: The test attempts to reproduce the bug described in the issue ticket, but it does not correctly reflect the conditions under which the bug occurs. Th... |
| astropy | astropy__astropy-8872 | success | Accepted | Accepted | AssertFlip accepted a final bug-revealing test for this instance. |
| django | django__django-10554 | failure | Misimplementation | Incorrect Input/Mock | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: FAILED (errors=1) |
| django | django__django-10880 | failure | Misimplementation | Incorrect Input/Mock | Phase A failed before inversion: 0 passing candidate(s); 22 failing execution(s) across 10 generation attempt(s). Last pytest failure: No installed app with label 'test_app'. |
| django | django__django-10914 | failure | Mechanical Failure | Incorrect File Reference | Phase A failed before inversion: 0 passing candidate(s); 100 failing execution(s) across 10 generation attempt(s). Last pytest failure: FAILED (errors=1) |
| astropy | astropy__astropy-13453 | failure | Mechanical Failure | Environment Error | Command 'docker exec 0b34383a58666d8c800da2e141af18290f579694a3a12f2a8dc8d5e774d03ab4 bash -c "pip install /assertflip && pip install hypothesis && assertflip --test-cmd 'pytest -rA' --source-dir astropy --tests-dir astropy/tests --max-attempts 10 --dataset /results/astropy__a... |
| astropy | astropy__astropy-14598 | failure | Mechanical Failure | Environment Error | Command 'docker exec 0a3090990a949a9d1ec3e154792c1b3beae2050de67c2450c0751d82f987fffd bash -c "pip install /assertflip && pip install hypothesis && assertflip --test-cmd 'pytest -rA' --source-dir astropy --tests-dir astropy/tests --max-attempts 10 --dataset /results/astropy__a... |
