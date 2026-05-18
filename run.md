# AssertFlip 全量数据运行说明

## 1. 进入仓库根目录

```bash
cd /root/Baxxhy/BugReproduce/AssertFlip
```

## 2. 运行 SWT-Lite Unique 数据

```bash
bash scripts/run_swtlite_full.sh
```

这个命令默认跑较小的 SWT-Lite Unique 数据集，严格保持论文内部流程配置，但是数据量比 SWT-Bench-Verified 小。

默认数据集是：

```text
datasets/SWT_Lite_Agentless_Unique_Only.json
```

默认对应的评测结果文件是：

```text
evaluation_results_on_SWT_Bench/assertFlip_Lite_unique_188_instances.json
```

日志会自动写到：

```text
logs/run_swt_lite_unique_YYYYmmdd_HHMMSS.log
```

查看最新日志：

```bash
ls -t logs/run_swt_lite_unique_*.log | head -1
```

实时查看最新日志：

```bash
tail -f $(ls -t logs/run_swt_lite_unique_*.log | head -1)
```

如果想严格保持论文的每条数据内部配置不变，同时提速，可以开多个 worker 并行跑多个 instance：

```bash
WORKERS=4 bash scripts/run_swtlite_full.sh
```

推荐先用：

```bash
WORKERS=3 bash scripts/run_swtlite_full.sh
```

这不会修改论文默认的 `10 regeneration attempts`、`10 refinement attempts`、pass-invert、LLM validation、planner 等配置；只是同时跑多个独立 instance。注意 worker 越多，同时启动的 Docker 容器和 LLM 请求越多，如果 API 限流或机器压力过大，就把 `WORKERS` 降到 2 或 3。

如果磁盘空间紧张，可以设置每跑完一条就删除该条 Docker 镜像：

```bash
REMOVE_IMAGE_AFTER_RUN=1 WORKERS=1 bash scripts/run_swtlite_full.sh
```

这会节省磁盘空间，但以后重跑同一条数据时需要重新拉镜像。磁盘紧张时建议配合 `WORKERS=1` 或 `WORKERS=2` 使用，不要同时拉太多镜像。

清理已经停止的旧容器：

```bash
docker container prune -f
```

如果遇到 Docker API 读取超时，比如：

```text
UnixHTTPConnectionPool(host='localhost', port=None): Read timed out. (read timeout=60)
```

说明不是 AssertFlip 生成的测试失败，而是 Python Docker SDK 等 Docker daemon 响应时超时。当前脚本已经默认把 Docker client timeout 调成 600 秒。如果机器很慢，可以这样调得更大：

```bash
DOCKER_CLIENT_TIMEOUT=1800 bash scripts/run_swtlite_full.sh
```

如果想运行 SWT-Bench-Verified 全量 433 条，使用：

```bash
WORKERS=3 bash scripts/run_swtverified_full.sh
```

两个固定入口脚本分别是：

```text
scripts/run_swtlite_full.sh
scripts/run_swtverified_full.sh
scripts/run_swtverified_first80.sh
```

底层通用入口是：

```text
scripts/run_assertflip_full.sh
```

如果只想跑 SWT-Bench-Verified 前 80 条：

```bash
WORKERS=1 REMOVE_IMAGE_AFTER_RUN=1 bash scripts/run_swtverified_first80.sh
```

前 80 条结果目录：

```text
assertflip_swt_verified_first80_run/results/
```

前 80 条汇总报告：

```text
assertflip_swt_verified_first80_run/assertflip_swt_verified_first80_summary.txt
```

如果只想跑作者默认输出的 326 条里的前 100 条，并且跑完后直接进入 SWT-Bench 最终验证：

```bash
WORKERS=2 EVAL_WORKERS=1 bash scripts/run_swtverified_author326_first100.sh
```

这个脚本会先运行 AssertFlip 生成阶段，然后把被 AssertFlip 接受的测试转换成 SWT-Bench predictions，最后调用官方 SWT-Bench harness 验证 F2P 和覆盖率。

作者 326 前 100 条的本地生成结果目录：

```text
assertflip_swt_verified_author326_first100_run/results/
```

作者 326 前 100 条的本地生成汇总：

```text
assertflip_swt_verified_author326_first100_run/assertflip_swt_verified_author326_first100_summary.txt
```

跑完验证后会多出这些文件：

```text
assertflip_swt_verified_author326_first100_run/results/preds_swt_verified_author326_first100.jsonl
assertflip_swt_verified_author326_first100_run/swtbench_eval_<run_id>.json
assertflip_swt_verified_author326_first100_run/swtbench_eval_<run_id>_summary.txt
```

其中 `swtbench_eval_<run_id>_summary.txt` 里会写最终 F2P 成功条数、F2P 成功率、平均覆盖率和平均覆盖率增量。

脚本默认使用国内镜像源：

```text
Docker Hub 代理：docker.1ms.run
PyPI：https://pypi.tuna.tsinghua.edu.cn/simple
apt：https://mirrors.tuna.tsinghua.edu.cn
```

如果你要临时换成别的国内源，可以这样覆盖：

```bash
DOCKER_IMAGE_REGISTRY=docker.m.daocloud.io PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn bash scripts/run_swtlite_full.sh
```

运行产生的中间结果会输出到：

```text
assertflip_swt_lite_unique_run/results/
```

最终汇总报告会输出到：

```text
assertflip_swt_lite_unique_run/assertflip_swt_lite_unique_summary.txt
```

## 3. 运行完成后查看总结果

查看汇总报告前 80 行：

```bash
sed -n '1,80p' assertflip_swt_lite_unique_run/assertflip_swt_lite_unique_summary.txt
```

完整查看每一条数据的结果：

```bash
less assertflip_swt_lite_unique_run/assertflip_swt_lite_unique_summary.txt
```

这个文件里会包含：

- 每一条数据的 `instance_id`
- 每一条是否 F2P 成功
- 是否生成了 attempt log
- 是否被 AssertFlip 在 buggy 版本上接受
- 普通 coverage.py 行覆盖率
- 失败原因或报错
- 总共成功复现多少条
- 总数据量是多少
- 总复现率是多少
- 论文里的覆盖率指标说明

## 4. 查看原始运行日志

查看每条数据的 runner 状态：

```bash
less assertflip_swt_lite_unique_run/results/run_summary.jsonl
```

查看某一条具体数据的 attempt log：

```bash
python -m json.tool assertflip_swt_lite_unique_run/results/attempts_<INSTANCE_ID>.json | less
```

例如：

```bash
python -m json.tool assertflip_swt_lite_unique_run/results/attempts_astropy__astropy-6938.json | less
```

## 5. 如果已经跑完，只想重新生成 txt 汇总报告

```bash
RUN_GENERATION=0 bash scripts/run_swtlite_full.sh
```

这个命令不会重新跑 Docker 和 LLM，只会根据已有结果重新生成：

```text
assertflip_swt_lite_unique_run/assertflip_swt_lite_unique_summary.txt
```

## 6. 重要说明：F2P 和覆盖率的含义

`scripts/run_assertflip_full.sh` 会运行 AssertFlip 的生成流程，也就是在 buggy 版本上生成测试、执行测试、做 LLM validation。

但是严格按照论文和 SWT-Bench 的定义，F2P 不是只看 buggy 版本是否失败。F2P 的定义是：

```text
生成的测试在 buggy 版本上失败，并且在应用 golden patch 后通过。
```

所以最终 txt 里的 F2P 标签来自这个文件：

```text
evaluation_results_on_SWT_Bench/assertFlip_default_run.json
```

这是仓库里已经提供的 SWT-Bench 评测结果。

另外，`attempts_*.json` 里面保存的 coverage 是 coverage.py 的普通行覆盖率，它是在 buggy 版本运行生成测试时得到的。

论文里提到的覆盖率是：

```text
Delta Mean Change Coverage
```

也就是生成测试覆盖 golden patch 修改代码行的比例。这个指标需要 SWT-Bench 官方评测流程才能严格计算，不能直接用 `attempts_*.json` 里的普通 coverage.py 覆盖率替代。
