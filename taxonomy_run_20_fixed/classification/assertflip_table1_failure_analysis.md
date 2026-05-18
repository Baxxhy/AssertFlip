# AssertFlip Failure Analysis Using SWT-Bench Taxonomy Table 1

This analysis uses the taxonomy definitions from Table 1 of `2018 - A taxonomy of failing bug reproduction tests on SWT-bench.pdf`.
It is based on the local 20-instance AssertFlip run with `openai/gpt-4o-mini` in `pass_then_invert` mode.

## Table 1 Categories Used

- Mechanical Failure / Not Implemented: the tool does not provide a real test.
- Mechanical Failure / Output Format Inconsistency: the test is logically close but expects a different output format.
- Mechanical Failure / Environment Error: the test environment fails before meaningful test execution.
- Mechanical Failure / Incorrect File Reference: the generated test references a nonexistent or wrong file path.
- Mechanical Failure / Wrong API Call: the test uses an external/project API incorrectly.
- Misimplementation / Incorrect Input/Mock: the test setup, input, fixture, or mock does not recreate the buggy state.
- Misimplementation / Incorrect Assertion: the oracle checks the wrong variable, state, exception, or opposite behavior.
- Misimplementation / Logical Failure: the test is syntactically valid but semantically disconnected from the bug trigger.
- Requirement Misunderstanding / Misunderstanding Edge Case Logic: the test misses an edge case required by the issue.
- Requirement Misunderstanding / Misunderstanding Function Logic From Natural Language: the test mistranslates the issue's natural-language requirement.

## Summary

- Total instances: 20
- Accepted by AssertFlip: 2
- Failed before acceptance: 18

### Counts By Class

- Misimplementation: 13
- Mechanical Failure: 4
- Requirement Misunderstanding: 1
- Accepted: 2

### Counts By Subclass

- Misimplementation / Incorrect Assertion: 9
- Misimplementation / Incorrect Input/Mock: 4
- Mechanical Failure / Environment Error: 2
- Mechanical Failure / Incorrect File Reference: 1
- Mechanical Failure / Output Format Inconsistency: 1
- Requirement Misunderstanding / Misunderstanding Edge Case Logic: 1
- Accepted: 2

## Per-Instance Analysis

| Project | Instance | Phase | Taxonomy Label | Concrete Failure | Why AssertFlip Did Not Reach Reproduction | Improvement Direction |
|---|---|---|---|---|---|---|
| astropy | astropy__astropy-12907 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The inverted test asserted that nested-model output should not equal the expected output, but the expected output was actually the correct behavior. | AssertFlip successfully reached inversion, but inversion produced the wrong oracle. The LLM changed the assertion into an invalid negative check rather than a bug-specific fail-to-pass oracle. | Add an oracle repair step after validation rejection: when validation says "asserts opposite/correct behavior", regenerate only the assertion while preserving the passing setup. |
| astropy | astropy__astropy-13033 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test expected an exception message containing `missing`, but the actual message says the `time` column is expected. | The generated oracle was too specific about the exception text and not grounded in the real behavior. | Prefer checking exception type and semantically relevant fields over brittle exact message fragments unless the issue is explicitly about message text. |
| astropy | astropy__astropy-13236 | generate_passing_test | Misimplementation / Incorrect Assertion | Phase A never got a passing baseline; last failure was `AssertionError: assert None == ('field1', 'field2')`. | AssertFlip depends on first generating a passing test. Here the generated baseline already asserted the wrong metadata/state, so inversion could not start. | Add a Phase A oracle sanity check: if the candidate fails with AssertionError, ask the model to remove or weaken assertions until it produces a true passing setup before inversion. |
| astropy | astropy__astropy-13398 | generate_passing_test | Misimplementation / Incorrect Input/Mock | Phase A repeatedly hit an AstropyWarning about IERS polar motion data for invalid/out-of-range times. | The test input uses time/coordinate data that triggers unrelated Astropy IERS behavior instead of the reported bug. | Add Astropy-specific prompt constraints and fixtures: avoid remote/IERS-sensitive dates unless issue requires them; use deterministic local test data. |
| astropy | astropy__astropy-13579 | generate_passing_test | Misimplementation / Incorrect Input/Mock | Phase A used frame name `helioprojective`, which is not a known coordinate frame in this environment/version. | The model hallucinated or assumed an unavailable Astropy coordinate frame. This is incorrect test setup, not a real reproduction. | Use source/API retrieval before test generation for project symbols and valid frame names; reject candidates containing unavailable symbols before pytest. |
| astropy | astropy__astropy-13977 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test expected adding DuckArray instances with incompatible units to return `NotImplemented`, but actual Quantity handling performs valid unit conversion. | The generated failing oracle contradicted actual library semantics. Inversion made the test fail, but not for the target bug. | During inversion, require the model to justify why the failing assertion should pass after the gold fix; run fixed-version validation when available. |
| astropy | astropy__astropy-14096 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test checked for an error message involving `random_attr`, but the actual error concerns property `prop`. | The oracle targeted the wrong attribute/error message, so the failure is not the reported bug. | Use issue-specific entity extraction: preserve exact property/attribute names from the issue and prohibit invented names in the assertion. |
| astropy | astropy__astropy-14182 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test expected `header_rows` to be an unexpected keyword, but actual failure was missing required positional argument `filename`. | The generated call shape was wrong, causing an unrelated TypeError before testing the intended behavior. This is partly wrong assertion and partly wrong API interaction. | Add API signature retrieval for methods under test, then repair call arguments before oracle inversion. |
| astropy | astropy__astropy-14309 | terminating | Accepted | AssertFlip accepted a final bug-revealing test. | The pass-then-invert flow worked for this instance. | No failure-specific change needed. |
| astropy | astropy__astropy-14365 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test failed due to a warning about missing `table_id`, not the intended case-sensitivity ValueError. | The test reached a related API but did not control required input details, so the observed failure was a different precondition. | Add precondition validation: if the error is a warning or setup precondition, repair setup before treating the failure as bug-revealing. |
| astropy | astropy__astropy-14369 | validate_bug_with_llm | Requirement Misunderstanding / Misunderstanding Edge Case Logic | The test did not account for equivalent unit representations and a scaling factor. | The model misunderstood an edge case in unit parsing: different textual units can be semantically equivalent. | Add domain-aware normalization checks for Astropy units; compare unit equivalence rather than raw strings when issue concerns unit parsing. |
| astropy | astropy__astropy-14508 | generate_passing_test | Mechanical Failure / Output Format Inconsistency | Phase A failed around FITS card float/comment formatting; warning showed card comment truncation. | The test is near the right area, but it relies on brittle exact string/format output while the actual formatting differs. | Use normalized FITS card fields or targeted substrings instead of full `str(card)` equality unless formatting is the exact bug. |
| astropy | astropy__astropy-14539 | generate_passing_test | Misimplementation / Incorrect Assertion | Phase A failed with `ValueError: The truth value of an array with more than one element is ambiguous`; the candidate also asserted opposite FITSDiff identity semantics. | The passing baseline was already invalid. AssertFlip could not reach a stable passing test because the oracle/setup triggered the bug or asserted the wrong result too early. | Separate setup construction from oracle assertion: first create the FITS files and verify no unrelated crash, then synthesize the minimal fail-to-pass assertion. |
| astropy | astropy__astropy-14995 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | The test expected a TypeError for masked/unmasked NDDataRef multiplication, but it did not match the reported conditions. | The generated oracle targeted a plausible but wrong condition; inversion produced a failure disconnected from the exact bug trigger. | Extract the issue's operand/mask conditions into structured requirements and validate candidate setup against them before inversion. |
| astropy | astropy__astropy-8872 | terminating | Accepted | AssertFlip accepted a final bug-revealing test. | The pass-then-invert flow worked for this instance. | No failure-specific change needed. |
| django | django__django-10554 | generate_passing_test | Misimplementation / Incorrect Input/Mock | Phase A failed with database setup errors such as missing table for generated model. | The generated Django test defined models/app labels but did not create a valid app/table lifecycle in Django's test harness. | Add Django-specific scaffolding: use `isolate_apps`, `schema_editor.create_model`, or existing Django test utilities rather than ad hoc app labels. |
| django | django__django-10880 | generate_passing_test | Misimplementation / Incorrect Input/Mock | Phase A failed with `No installed app with label 'test_app'`. | The generated test calls migrations for an app that is not installed. This is an invalid mock app setup. | Same Django scaffold fix: dynamically create models inside isolated apps and avoid `makemigrations` for nonexistent apps. |
| django | django__django-10914 | generate_passing_test | Mechanical Failure / Incorrect File Reference | Phase A failed because the test tried to stat `test_file.txt`, but that path did not exist. | The generated file upload test referenced a file path/name without ensuring the file existed at that path. | Enforce tempfile/path discipline: every file path used by a generated test must be created in `TemporaryDirectory` or `tmp_path` before assertions. |
| astropy | astropy__astropy-13453 | runner | Mechanical Failure / Environment Error | Docker command returned non-zero before a usable attempts file was produced. | This is outside AssertFlip's semantic generation loop; the container command failed before meaningful classification of a generated test. | Capture full container stdout/stderr to a per-instance log, retry dependency installation separately, and rerun only this instance. |
| astropy | astropy__astropy-14598 | runner | Mechanical Failure / Environment Error | Docker command timed out after about 3600 seconds. | The run exceeded the harness timeout, so no final generated-test decision was reached. | Add per-phase timeout logs, kill stuck pytest/LLM phases separately, and rerun with a larger timeout only after identifying the stuck command. |

## Why AssertFlip Fails On These Cases

AssertFlip's central assumption is that generating a passing test is easier than directly generating a failing bug reproduction. The local failures show three pressure points:

1. Phase A is fragile for complex project setup.
   Django model/app/database setup and Astropy domain fixtures require project-specific testing knowledge. If Phase A cannot produce a passing baseline, the inversion strategy never starts.

2. Assertion inversion is too syntactic.
   Several candidates failed because the LLM inverted the assertion into the opposite of correct behavior, or asserted an invented exception message. The result is a failing test, but not a bug-reproducing test.

3. LLM validation rejects many failures but does not repair them specifically enough.
   The validator often correctly says why the candidate is unrelated, but AssertFlip mostly uses that as broad feedback for another generation attempt. It does not route the failure to a specialized repair action based on the taxonomy category.

4. The harness needs better mechanical observability.
   For runner failures and timeouts, the current result only records the outer `docker exec` failure. It should preserve container logs and phase-level timeout information so mechanical failures can be fixed rather than rerun blindly.

## Recommended AssertFlip Improvements

1. Add a taxonomy-guided repair loop.
   After each pytest failure or validation rejection, classify the failure into the Table 1 subclass and choose a repair strategy:
   - Incorrect Input/Mock: rewrite setup/fixtures only.
   - Incorrect Assertion: preserve setup and rewrite oracle only.
   - Wrong API Call: retrieve signature/source before rewriting call.
   - Incorrect File Reference: create or correct paths using temp files.
   - Output Format Inconsistency: normalize or compare semantic fields.
   - Environment Error: stop semantic retries and fix harness/logs.

2. Make Phase A pass-first stricter.
   Phase A should not merely ask the LLM for a passing test. It should progressively remove or weaken assertions until setup execution is clean, then add assertions back only after the setup is valid.

3. Add project-specific scaffolds.
   - Django: provide templates using `SimpleTestCase`, `TestCase`, `isolate_apps`, and `schema_editor` for dynamic models.
   - Astropy: provide safe warnings handling, deterministic local data, valid coordinate frames, and unit-equivalence checks.

4. Use source/API retrieval before generation and repair.
   If the model references a class, function, frame name, or method signature, AssertFlip should verify it exists in the target version before running pytest.

5. Validate on the fixed version before accepting when possible.
   The true SWT-Bench success criterion is fail on buggy and pass after the fix. LLM validation is useful, but fixed-version execution is a stronger oracle.

6. Improve runner logging.
   Store the full `docker pull`, `pip install`, `assertflip`, and pytest output per instance. For timeouts, record the active command and last output.

