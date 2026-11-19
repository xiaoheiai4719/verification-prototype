# 方案与代码核验助手：离线最小原型

这是一个可运行的证据工作流，不是已经接入模型的自主审查产品。
不调用模型、不使用 API key、不消耗模型额度、不上传仓库、不修改输入仓库。
Python 3.10+，只用标准库。

## v0.3 · 把 Rederive 的追问和证据核验接到一起

**不用装依赖，先打开 `outputs/demo/learn.html`。** 先写一个方案，再逐条看提示、补约束，最后才亮出真实源码、设计取舍、验收条件和已记录的测试结果。同一张卡贯穿推演与核验，不用在两套工具间拷贝结论。完整核验报告（含答案）在 `outputs/demo/report.html`。

本版借鉴 [Rederive](https://github.com/EricJujianZou/rederive) 的苏格拉底提问法，没有复制上游代码或安装、运行上游 Skill。内置问题和约束是人工设计的；**没有模型自动出题、读答案打分、根据回答即时追问**。网页是离线的教学界面，答案嵌在文件内，只在正常操作下逐步展示，不是防作弊机制；输入不发送、不持久化。

### 用自己的仓库走一遍

1. 用一个有 `- R1: …` 标记的方案先运行一次 `inspect`，得到输入快照和有界 `agent-packet.json`。
2. 让人或外部 AI 给关键设计主张写一张卡。不要把结论放在题目里；按从简单到难写提示和约束。把代码事实、业务取舍与仍未知的依赖分开。源码引用只填相对路径和起止行；不能在卡里填测试通过。
3. 用 `inspect --cards cards.json` 生成报告，再执行下面的 `learn` 命令。CLI 会校验仓库扫描范围内的代码和方案快照；变更后要重新检查，不会拿旧证据接着推演。

导入模板：`examples/retry-cards.json`（JSON 数组）。给自己的仓库改好卡片后，把示例中的仓库和方案路径换掉：

```sh
python verify.py inspect --repo examples/upload --plan examples/upload/plan.md --cards examples/retry-cards.json --out outputs/import-example
```

下面的内置 demo 则额外包含真实运行的虚构样例测试：

```sh
python verify.py demo
python verify.py learn start --report outputs/demo/report.json --card retry-response-lost --session /tmp/retry-lesson.json --repo examples/upload --plan examples/upload/plan.md
python verify.py learn answer --report outputs/demo/report.json --card retry-response-lost --session /tmp/retry-lesson.json --repo examples/upload --plan examples/upload/plan.md --text '先区分操作结果未知与操作确定失败'
python verify.py learn hint --report outputs/demo/report.json --card retry-response-lost --session /tmp/retry-lesson.json --repo examples/upload --plan examples/upload/plan.md
python verify.py learn reveal --report outputs/demo/report.json --card retry-response-lost --session /tmp/retry-lesson.json --repo examples/upload --plan examples/upload/plan.md
```

重复体验时，为 `--session` 指定一个新路径。旧会话文件不被覆盖。CLI 会话保存学习者输入，请像对待自己的本地笔记一样保管。`decision-cards.json` 是只含题面的输出；`report.json` 含答案和源码，别当成无剧透或可公开的文件发出去。真实仓库的导入流程不会执行仓库测试；无运行记录时显示未运行，不代表通过。


## 立即体验

```sh
python verify.py demo
python -m http.server 8765 --bind 127.0.0.1
```

浏览器打开 http://127.0.0.1:8765/outputs/demo/report.html ，或者直接打开该 HTML 文件。
也可以直接打开本包中的 `outputs/demo/report.html` 查看已执行的记录。

四个检查是真实执行结果：

| 实现 | 普通成功 | 远端成功但响应丢失 |
|---|---|---|
| 原始版 | 通过 | 失败：产生 2 个对象 |
| 对照修正版 | 通过 | 通过：只有 1 个对象 |

不是实际存储供应商验证。测试只覆盖自带的 FakeStorage，不能证明真实系统或所有输入正确。
R3 的真实供应商 24 小时契约保持未验证。并发、重启、权限仍未覆盖。

## 通用只读导入

方案中需要显式要求标记，例如 `- R1: 超时重试不能重复保存。`。
普通自由文本不会被伪称自动理解：需由人或外部 Agent 整理成该格式。

```sh
python verify.py inspect --repo /path/to/repo --plan /path/to/plan.md --out outputs/inspection
python verify.py check --report outputs/inspection/report.json --repo /path/to/repo --plan /path/to/plan.md
```

`check` 输入一致退出 0；扫描范围内内容变化退出 2，输出 STALE。
按源文件内容与方案计算 SHA256，并非仅依赖 Git HEAD，因此扫描范围内未提交的改动也能发现。
未扫描文件不会被监测。快照范围：允许扩展名的 UTF-8 源文件，单个不超过 200KB；跳过隐藏、依赖目录及 symlink。当前限制500文件与2MB源内容，跳过项写入报告；大仓库建议分范围调查。

## AI/人工调查如何接进来

当前程序不调用大模型。父会话/其他 Agent 可以读仓库生成候选判断，输出 `proposals.json`：

```json
[
  {
    "requirement_id": "R1",
    "claim": "待验证：重试未携带稳定请求身份，可能重复保存",
    "references": [{"file": "service.py", "start": 24, "end": 31}],
    "next_step": "模拟响应丢失，观察对象数量"
  }
]
```

导入：

```sh
python verify.py inspect --repo examples/upload --plan examples/upload/plan.md --proposals proposals.json --out outputs/inspection
```

程序验证引用位置实际存在，从文件提取原文；候选判断最多标成 `source_located`（来源已定位），不能自己填 `verified` 或运行结果。
引用存在≠引用支持结论。人/Agent 仍可能误解代码。
要求保持未验收，由用户根据覆盖范围决定是否接受；本版没有批准/自动实施功能。
没有通用测试执行能力，避免导入仓库后静默运行任意脚本。`demo` 只运行随包生成的虚构代码。

## 数据、信任与安全边界

- HTML 是无外部资源的静态报告。引用、日志和输入文本均转义。
- JSON 包含扫描到的源文件内容；报告可能含商业信息或源文件中的秘密。仅有基础秘密模式检测，勿公开分享未经人工检查的真实仓库报告。
- 子进程超时 5 秒，仅用于演示；这不是容器/OS 级安全沙箱，不能用来运行不可信仓库。
- 执行器产生测试状态并保存真实 stdout/stderr。手工改 JSON 仍能伪造记录：本版不提供签名、防篡改或多用户权限。
- 代码、方案 hash 用于过期检测，不等于真实性证明。应在评审前运行 `check`；静态 HTML 不会自行感知后续修改。
- requirements、claims、runs 分开：测试通过不会自动把整个业务要求标为已验证。
- 修正版仅为演示性对照。真实提供商幂等契约、长时间重试、并发、重启恢复需独立验证。

## 工程验证

```sh
python -m unittest discover -s tests -v
python -m compileall -q verify.py demo_probe.py demo_cards.py rederive.py rederive_web.py workflow.py examples tests
```

## 下一步（尚未实现）

接入可选模型接口/工具循环、完整需求提取、持久化调查状态、独立审阅者、可信测试适配器、覆盖与发布门禁。应先选一个实际仓库做盲测，不能凭这个虚构案例声称具有通用缺陷发现能力。

## v0.2：借鉴五个开源项目后的实际改进

各来源、固定 SHA、许可证与边界见 `REFERENCE_RESEARCH.zh-CN.md`。未复制第三方代码，未安装其依赖。

- **OpenSpec**：增加依赖图与 `ready/blocked`、阻塞来源。要求状态由证据/运行结果推导，不能用文件存在冒充业务验收。
- **Repomix**：扫描上限 500 个文件 / 2MB 内容 / 单文件 200KB；显式 `skipped` 清单；排除敏感文件名、二进制、链接与常见秘密模式。不保证检测全部秘密，导出仍需检查。
- **Promptfoo**：测试结果携带逐字段断言（预期/实际/原因），空断言为 `not_run`，异常与断言失败分开，不用平均分掩盖失败。
- **EGM**：支持绑定输入快照的审阅意见导入，保留 open/propose_fix/contest/escalate/decline，重大问题不能静默 decline。反驳需要证据文字，但软件不保证该文字证明了结论。
- **SWE-agent**：修改前后用同样故障场景对照，JSON 和 HTML 分组展示。运行记录带快照和 runner hash，`check` 检测输入变化。

新增 `outputs/demo/agent-packet.json`，可交给真实 Agent 阅读与调查。包中要求把仓库文本当数据而非指令，寻找支持/反对证据并保留未知。**导出包不代表已经执行了 AI 调查。**

审阅导入格式（`input_snapshot` 必须使用本次报告的真实 ID）：

```json
[{"id":"review-1","input_snapshot":"COPY_ACTUAL_SNAPSHOT_ID","requirement_id":"R3","severity":"major","disposition":"escalate","message":"真实供应商契约缺失","evidence":"请取得供应商版本化文档"}]
```

```sh
python verify.py inspect --repo examples/upload --plan examples/upload/plan.md --reviews reviews.json --out outputs/reviewed
```

真实依赖验证、模型 API、自由文本需求理解、自动工具调查、认证审批与防篡改日志仍未实现。系统显示的审阅是导入意见，不能证明来自独立模型。所有要求最终验收仍保持未接受。

### v0.2.1 复审修正
超时保留要求关联；缺失观察值为执行 error 而非业务 failed。check 现在同时检查输入和已保存运行器指纹（demo_probe.py、verify.py、workflow.py）。旧运行缺失指纹、指纹不同均需重跑。指纹不涵盖 Python/OS 环境，也不是防篡改签名。46 项测试通过，修前失败复现见 outputs/review-reproduction.txt。
