# AssertFlip Table 1 Failure Analysis / AssertFlip 按 Table 1 的失败分析

This report re-analyzes the local 20-instance AssertFlip run with `openai/gpt-4o-mini`, using the failure taxonomy from Table 1 of `2018 - A taxonomy of failing bug reproduction tests on SWT-bench.pdf`.

本报告重新分析本地使用 `openai/gpt-4o-mini` 跑的 20 条 AssertFlip 结果，并严格使用 `/root/Baxxhy/BugReproduce/AssertFlip/2018 - A taxonomy of failing bug reproduction tests on SWT-bench.pdf` 中 Table 1 的失败分类。

## Important Clarification / 重要说明

The classification follows the categories and definitions in Table 1, but the evidence comes from our local AssertFlip generation artifacts: `attempts_*.json`, pytest traces, LLM validation reasons, and runner errors. Therefore, this is a taxonomy-based diagnosis of why AssertFlip failed on these 20 samples, not a claim that we reproduced the paper author's full annotation protocol.

这里的分类使用 Table 1 的类别和定义，但证据来自我们本地 AssertFlip 运行产物：`attempts_*.json`、pytest trace、LLM validation reason 和 runner 错误。因此，这是一份“按论文 taxonomy 做的本地失败诊断”，不是说我们完整复现了论文作者的人工标注流程。

## Table 1 Taxonomy Used / 使用的 Table 1 分类

| Class | Subclass | Meaning | 中文解释 |
|---|---|---|---|
| Mechanical Failure | Not Implemented | The tool does not provide a real executable test. | 工具没有生成真正可执行的测试，或者是 TODO/占位逻辑。 |
| Mechanical Failure | Output Format Inconsistency | The test is logically close but expects a different output format. | 测试逻辑接近，但对输出格式、字符串表示、顺序等期望不一致。 |
| Mechanical Failure | Environment Error | Environment or harness fails before meaningful test execution. | 测试环境或执行 harness 在真正测试前失败。 |
| Mechanical Failure | Incorrect File Reference | The generated test references a wrong or nonexistent path. | 生成的测试引用了错误或不存在的文件路径。 |
| Mechanical Failure | Wrong API Call | The test interacts with a library/API incorrectly. | 测试错误调用了项目或外部库 API。 |
| Misimplementation | Incorrect Input/Mock | The setup/input/mock does not recreate the buggy state. | 测试输入、mock、fixture、数据库/app setup 没有复现 bug 所需状态。 |
| Misimplementation | Incorrect Assertion | The oracle checks the wrong variable/state/exception/opposite behavior. | 断言检查了错误变量、错误状态、错误异常消息，或者断言了相反行为。 |
| Misimplementation | Logical Failure | The operation sequence is syntactically valid but semantically disconnected from the bug. | 测试语法上能跑，但操作序列和 bug 触发条件语义上无关。 |
| Requirement Misunderstanding | Misunderstanding Edge Case Logic | The test misses an edge case required by the issue. | 测试没有理解 issue 中的边界条件或特殊情况。 |
| Requirement Misunderstanding | Misunderstanding Function Logic From Natural Language | The test mistranslates the natural-language requirement. | 测试错误理解了 issue 自然语言描述中的功能逻辑。 |

## Overall Result / 总体结果

| Metric | Count | 中文 |
|---|---:|---|
| Total instances | 20 | 总样本数 20 |
| Accepted by AssertFlip | 2 | AssertFlip 接受 2 条 |
| Failed before acceptance | 18 | 未成功复现 18 条 |

### Counts By Class / 大类统计

| Class | Count | 中文说明 |
|---|---:|---|
| Misimplementation | 13 | 主要是测试写错：输入/setup 不对或 oracle 不对。 |
| Mechanical Failure | 4 | 主要是环境、文件路径、输出格式等机械问题。 |
| Requirement Misunderstanding | 1 | 主要是没有理解边界逻辑。 |
| Accepted | 2 | AssertFlip 成功接受。 |

### Counts By Subclass / 小类统计

| Subclass | Count | 中文说明 |
|---|---:|---|
| Incorrect Assertion | 9 | 最主要失败：断言方向、异常消息、预期状态写错。 |
| Incorrect Input/Mock | 4 | Django/Astropy setup、mock、输入不正确。 |
| Environment Error | 2 | Docker/container runner 层失败或超时。 |
| Incorrect File Reference | 1 | 引用了不存在的文件路径。 |
| Output Format Inconsistency | 1 | 对 FITS card 字符串/格式期望不一致。 |
| Misunderstanding Edge Case Logic | 1 | 没处理单位等价和缩放因子这种边界逻辑。 |
| Accepted | 2 | 成功生成 bug-revealing test。 |

## Why AssertFlip Failed / AssertFlip 为什么失败

### 1. Phase A failed before inversion / Phase A 在 inversion 前失败

English:
AssertFlip's main idea is pass-then-invert: first generate a passing test on the buggy version, then invert its assertion so that it fails and reveals the bug. For many failed instances, Phase A never produced a passing baseline. Once the passing baseline is missing, assertion inversion cannot start. These failures are mostly `Incorrect Input/Mock` and `Incorrect Assertion`.

中文：
AssertFlip 的核心是 pass-then-invert：先在 buggy version 上生成一个 passing test，再把断言反转成 failing test 来暴露 bug。这里很多失败样本在 Phase A 就没有生成 passing baseline。没有 passing baseline，后续 assertion inversion 根本无法开始。这类失败主要属于 `Incorrect Input/Mock` 和 `Incorrect Assertion`。

Typical examples / 典型例子：

- `django__django-10554`: generated model/table setup was invalid, causing missing table errors.
  - 中文：生成的 Django model/table setup 不合法，导致数据库表不存在。
- `django__django-10880`: generated test used `test_app`, but that app was not installed.
  - 中文：测试使用了 `test_app`，但 Django 环境中没有安装这个 app。
- `astropy__astropy-13579`: generated coordinate frame `helioprojective` was not available in this Astropy version.
  - 中文：生成的坐标系 `helioprojective` 在该 Astropy 版本里不存在。
- `astropy__astropy-13236`: baseline assertion was already wrong: `assert None == ('field1', 'field2')`.
  - 中文：baseline 测试自己的断言已经错了：`assert None == ('field1', 'field2')`。

### 2. Inversion produced failing tests, but not bug-revealing tests / Inversion 后失败了，但不是目标 bug

English:
Several instances reached inversion and produced a failing test, but LLM validation rejected it because the failure did not match the reported bug. This is the main `Incorrect Assertion` pattern: the test fails, but it fails for the wrong reason.

中文：
有些样本已经进入 inversion，并且生成了 failing test，但 LLM validation 判断这个失败不是 issue 描述的 bug。这是最典型的 `Incorrect Assertion`：测试确实失败了，但失败原因错了。

Typical examples / 典型例子：

- `astropy__astropy-12907`: assertion checked that nested model output was not equal to the expected output, but the expected output was actually correct.
  - 中文：断言 nested model 输出不等于 expected output，但那个 expected output 实际上是正确行为。
- `astropy__astropy-13033`: test expected exception text containing `missing`, but the actual relevant message concerned the expected `time` column.
  - 中文：测试期待异常消息包含 `missing`，但实际相关消息是期望存在 `time` column。
- `astropy__astropy-14096`: test checked invented attribute `random_attr`, while the actual issue concerned property `prop`.
  - 中文：测试检查了模型自己编造的 `random_attr`，但 issue 实际相关的是 `prop`。
- `astropy__astropy-14182`: test expected a `header_rows` keyword error, but the actual failure was missing `filename`.
  - 中文：测试期待 `header_rows` keyword error，但实际失败是缺少 `filename` 参数。

### 3. Some failures are domain edge cases / 一些失败是领域边界逻辑没理解

English:
`astropy__astropy-14369` is a `Requirement Misunderstanding / Misunderstanding Edge Case Logic` case. The generated test compared unit representations too literally and did not account for equivalent unit scaling. This is not just a wrong assertion string; it reflects missing domain reasoning about Astropy units.

中文：
`astropy__astropy-14369` 属于 `Requirement Misunderstanding / Misunderstanding Edge Case Logic`。生成测试把单位表示当成字符串或表面形式比较，没有理解单位等价和缩放因子。这不只是断言字符串写错，而是缺少 Astropy unit 领域知识。

### 4. Mechanical failures still exist / 仍然存在机械失败

English:
Two instances failed at the runner/container level, before we got meaningful generated-test evidence. These are `Environment Error`. One instance timed out, and one returned a non-zero Docker exec status. Another case referenced a file path that was never created, which is `Incorrect File Reference`.

中文：
有两条在 runner/container 层失败，在拿到有意义的 generated-test 证据前就失败了，属于 `Environment Error`。一条超时，一条 `docker exec` 非零退出。还有一条引用了没有创建的文件路径，属于 `Incorrect File Reference`。

Examples / 例子：

- `astropy__astropy-13453`: Docker command returned non-zero.
- `astropy__astropy-14598`: Docker command timed out after about 3600 seconds.
- `django__django-10914`: generated test tried to `os.stat('test_file.txt')`, but that path did not exist.

## Per-Instance Diagnosis / 每条样本诊断

| Project | Instance | Phase | Table 1 Label | 中文分类 | Concrete reason | 中文原因 |
|---|---|---|---|---|---|---|
| astropy | astropy__astropy-12907 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Inverted assertion checked the opposite of correct nested-model output. | 反转后的断言检查了正确输出的相反状态。 |
| astropy | astropy__astropy-13033 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Expected exception message containing `missing`, but actual relevant message concerned `time`. | 期待错误异常消息，实际相关错误是 `time` column。 |
| astropy | astropy__astropy-13236 | generate_passing_test | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Phase A baseline failed with `assert None == ('field1', 'field2')`. | Phase A baseline 自己断言错误。 |
| astropy | astropy__astropy-13398 | generate_passing_test | Misimplementation / Incorrect Input/Mock | 实现错误 / 输入或 mock 错误 | Input triggered unrelated IERS polar-motion warning. | 输入触发了无关的 IERS polar motion warning。 |
| astropy | astropy__astropy-13579 | generate_passing_test | Misimplementation / Incorrect Input/Mock | 实现错误 / 输入或 mock 错误 | Used unavailable coordinate frame `helioprojective`. | 使用了当前版本不存在的坐标系。 |
| astropy | astropy__astropy-13977 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Expected DuckArray addition to return `NotImplemented`, but Quantity conversion was valid. | 错把合法 Quantity 单位转换当成 bug。 |
| astropy | astropy__astropy-14096 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Checked error text for invented `random_attr` instead of issue-relevant `prop`. | 检查了编造的属性名，而不是 issue 相关属性。 |
| astropy | astropy__astropy-14182 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Expected `header_rows` error, but call failed due to missing `filename`. | API 调用形态不对，导致错误参数缺失。 |
| astropy | astropy__astropy-14309 | terminating | Accepted | 成功 | AssertFlip accepted a final bug-revealing test. | AssertFlip 成功生成并接受 bug-revealing test。 |
| astropy | astropy__astropy-14365 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Failure came from missing `table_id` warning, not intended case-sensitivity behavior. | 失败来自缺少 `table_id` 的 warning，而不是目标大小写问题。 |
| astropy | astropy__astropy-14369 | validate_bug_with_llm | Requirement Misunderstanding / Misunderstanding Edge Case Logic | 需求误解 / 边界逻辑误解 | Did not account for equivalent unit representation and scaling factor. | 没有理解单位等价和缩放因子。 |
| astropy | astropy__astropy-14508 | generate_passing_test | Mechanical Failure / Output Format Inconsistency | 机械失败 / 输出格式不一致 | FITS card float/comment formatting expectation was brittle. | 对 FITS card 字符串/格式期望过于脆弱。 |
| astropy | astropy__astropy-14539 | generate_passing_test | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Baseline triggered ambiguous array truth-value error and asserted wrong FITSDiff semantics. | baseline 已经触发数组 truth-value 错误，并且 FITSDiff 断言方向不对。 |
| astropy | astropy__astropy-14995 | validate_bug_with_llm | Misimplementation / Incorrect Assertion | 实现错误 / 断言错误 | Expected TypeError under conditions that did not match the reported masked/unmasked operand bug. | 构造的 masked/unmasked 条件和 issue 不匹配。 |
| astropy | astropy__astropy-8872 | terminating | Accepted | 成功 | AssertFlip accepted a final bug-revealing test. | AssertFlip 成功生成并接受 bug-revealing test。 |
| django | django__django-10554 | generate_passing_test | Misimplementation / Incorrect Input/Mock | 实现错误 / 输入或 mock 错误 | Generated model/table setup caused missing database table. | 动态 model/table setup 不正确，数据库表不存在。 |
| django | django__django-10880 | generate_passing_test | Misimplementation / Incorrect Input/Mock | 实现错误 / 输入或 mock 错误 | Generated app label `test_app` was not installed. | 生成的 `test_app` 没有安装。 |
| django | django__django-10914 | generate_passing_test | Mechanical Failure / Incorrect File Reference | 机械失败 / 文件引用错误 | Test referenced `test_file.txt` without creating it. | 测试引用了未创建的文件路径。 |
| astropy | astropy__astropy-13453 | runner | Mechanical Failure / Environment Error | 机械失败 / 环境错误 | Docker exec returned non-zero before meaningful generated-test evidence. | Docker 执行层非零退出，没拿到有意义测试证据。 |
| astropy | astropy__astropy-14598 | runner | Mechanical Failure / Environment Error | 机械失败 / 环境错误 | Docker exec timed out after about 3600 seconds. | Docker/container 执行超时。 |

## How To Improve AssertFlip / 如何改进 AssertFlip

### 1. Add taxonomy-guided repair / 增加 taxonomy 引导的修复循环

English:
After each failed pytest run or LLM validation rejection, AssertFlip should classify the failure into a Table 1 subclass and choose a specific repair strategy. Right now, many failures are simply fed back into another broad generation attempt.

中文：
每次 pytest 失败或 LLM validation 拒绝后，AssertFlip 应该先把失败归入 Table 1 的小类，然后选择对应修复策略。现在很多失败只是把错误反馈给模型重新生成，修复动作太泛。

Recommended routing / 建议路由：

- Incorrect Assertion: keep setup, rewrite only the oracle.
  - 断言错误：保留 setup，只重写 oracle。
- Incorrect Input/Mock: rewrite setup/fixture/mock, keep issue target.
  - 输入/mock 错误：重写 setup、fixture、mock。
- Wrong API Call: retrieve source/signature before rewriting.
  - API 调用错误：先查源码和函数签名，再重写调用。
- Incorrect File Reference: force temp file creation before file assertions.
  - 文件引用错误：强制先创建临时文件，再做文件断言。
- Output Format Inconsistency: normalize output or compare semantic fields.
  - 输出格式不一致：用规范化输出或语义字段比较。
- Environment Error: stop LLM semantic retries and fix harness/logging.
  - 环境错误：停止 LLM 语义重试，转向 harness/log 修复。

### 2. Strengthen Phase A / 强化 Phase A

English:
Phase A should first construct a clean executable setup before adding strong assertions. A passing baseline should be treated as a separate artifact: setup must run, imports must be valid, project-specific fixtures must be correct, and only then should AssertFlip ask for assertions.

中文：
Phase A 应该先构造一个能干净执行的 setup，再加入强断言。Passing baseline 应该被拆成独立产物：先保证 import 正确、setup 能跑、项目 fixture 正确，再让模型加 assertion。

Concrete change / 具体改法：

- Add a setup-only mode before assertion generation.
  - 加一个 setup-only 生成阶段。
- If failure is AssertionError, weaken/remove assertion until baseline passes.
  - 如果失败是 AssertionError，先弱化或移除断言直到 baseline 通过。
- If failure is setup/import/API-related, repair setup before inversion.
  - 如果失败是 setup/import/API 问题，先修 setup，再进入 inversion。

### 3. Add project-specific scaffolds / 增加项目特定 scaffold

English:
The failures show that GPT-4o-mini often lacks enough project-specific test knowledge for Django and Astropy. AssertFlip should provide scaffolds rather than relying on generic generation.

中文：
这些失败说明 GPT-4o-mini 对 Django 和 Astropy 的项目测试知识不足。AssertFlip 应该提供 scaffold，而不是完全依赖通用生成。

Django scaffold / Django 模板：

- Use `isolate_apps` for dynamic models.
- Use `schema_editor.create_model()` when a test needs a temporary model table.
- Avoid `makemigrations` for nonexistent generated apps.
- Prefer existing Django test utilities and settings patterns.

Astropy scaffold / Astropy 模板：

- Use valid coordinate frames from the target version.
- Avoid IERS/remote-data-sensitive dates unless the issue requires them.
- Compare units by equivalence, not raw string form.
- For FITS cards, compare structured fields unless the bug is exactly formatting.
- Handle expected warnings explicitly.

### 4. Add source/API retrieval before generation / 生成前加入源码和 API 检索

English:
Before accepting a generated test, AssertFlip should verify that referenced classes, functions, frames, keyword arguments, and file paths exist in the target version.

中文：
在接受生成测试之前，AssertFlip 应该检查测试里引用的 class、function、frame、keyword argument、file path 是否真的存在于目标版本。

This would directly reduce:

- hallucinated APIs like invalid coordinate frames;
- wrong method signatures like missing `filename`;
- invented attributes like `random_attr`;
- nonexistent generated apps or file paths.

这能直接减少：

- 幻觉 API，例如不存在的坐标系；
- 错误函数签名，例如缺少 `filename`；
- 编造属性，例如 `random_attr`；
- 不存在的 app 或文件路径。

### 5. Use fixed-version validation when possible / 尽量加入 fixed-version 验证

English:
The real SWT-Bench criterion is fail on the buggy version and pass on the fixed version. LLM validation is useful but weaker. For accepted or promising candidates, AssertFlip should run the generated test against the fixed version when the harness is available.

中文：
SWT-Bench 真正标准是：buggy version 上失败，fixed version 上通过。LLM validation 有用，但不如 fixed-version 执行可靠。对已经接近成功的候选测试，AssertFlip 应该尽量在 fixed version 上再跑一次。

### 6. Improve runner observability / 改进 runner 日志

English:
For environment errors and timeouts, the current outer error is not enough. AssertFlip should save full container logs, pip install logs, pytest logs, and the active phase when timeout occurs.

中文：
对于环境错误和超时，当前外层错误不够。AssertFlip 应该保存完整 container log、pip install log、pytest log，以及超时时正在执行的阶段。

