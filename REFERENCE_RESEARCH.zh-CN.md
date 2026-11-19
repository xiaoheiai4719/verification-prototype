# 五个参考项目：方案与代码核验原型的迭代依据

检查日期：2026-11-16。五个仓库均在云端 shallow clone，读取了下面列出的实际实现。未安装运行这些项目、未调用任何模型 API，也未使用用户电脑或额度。以下是机制分析，不是效果评测。仅借鉴思想并独立实现，不把第三方代码直接混入原型。

## 1. OpenSpec：把模糊方案变成有依赖的产物与场景
- 仓库：https://github.com/Fission-AI/OpenSpec
- 固定提交：ea635dd255f8686dcf48626bbcbe0e3fd59b6067
- 许可：MIT，仓库 LICENSE。
- 路径：`src/core/artifact-graph/graph.ts` 的 `getNextArtifacts` 和 `getBlocked` 根据 `requires` 与完成集合推导可做/阻塞产物，采用拓扑排序和声明顺序保证确定性。
- `src/core/schemas/base.schema.ts` 给每条 Requirement 配 scenarios，并要求至少一个场景；`validator.ts` 对具体缺失给出位置和修复提示。
- 借鉴：每条验收要求至少有具体场景、证据或明确未知；缺场景的要求不能静默变成验收完成。展示下一步的前置依赖和阻塞原因。
- 不照搬：`state.ts` 用产物文件存在判断 completed。文件写出来不等于内容可靠，更不等于运行验证通过。我们的要求验收必须与运行结果分开。
- 源码：https://github.com/Fission-AI/OpenSpec/blob/ea635dd255f8686dcf48626bbcbe0e3fd59b6067/src/core/artifact-graph/graph.ts
- 规范：https://github.com/Fission-AI/OpenSpec/blob/ea635dd255f8686dcf48626bbcbe0e3fd59b6067/src/core/schemas/base.schema.ts

## 2. Repomix：让输入范围清楚，而不只是把整个仓库塞给模型
- 仓库：https://github.com/yamadashy/repomix
- 固定提交：813a886c6aa1d66aaec0b061a4442754529c7bcb
- 许可：MIT。
- 路径：`fileSearch.ts` 处理忽略规则和链接边界；`fileCollect.ts` 收集内容时保留 `skippedFiles` 与原因，并限制文件大小；`validateFileSafety.ts` 调用安全检查，再由 `filterOutUntrustedFiles.ts` 移除可疑普通文件。
- 借鉴：导入仓库时显式报告扫描/纳入/跳过数量和原因；默认排除环境凭证文件、二进制、生成目录、超大文件和越界链接。后续分析必须承认没读取的部分。
- 不照搬：该版本 Git diff/log 检出敏感内容后会警告但仍保留；因此不能声称用了安全扫描便不会泄密。原型不自动读取 diff/log，且应把秘密扫描描述为尽力检查，不是零泄露保证。
- 源码：https://github.com/yamadashy/repomix/blob/813a886c6aa1d66aaec0b061a4442754529c7bcb/src/core/file/fileCollect.ts
- 安全路径：https://github.com/yamadashy/repomix/blob/813a886c6aa1d66aaec0b061a4442754529c7bcb/src/core/security/validateFileSafety.ts

## 3. Promptfoo：把判断标准和运行结果分开
- 仓库：https://github.com/promptfoo/promptfoo
- 固定提交：b0723901f5ebc96847473ea27e342948ee51260d
- 根许可：MIT；若未来复制具体文件或使用打包依赖，仍需分别检查其许可。
- 路径：`src/assertions/json.ts` 对输出解析 JSON，再按 JSON Schema 校验，返回 `pass/score/reason/assertion`；`assertionsResult.ts` 汇总组件结果和计分，保留相关元数据及成本信息。
- 借鉴：把每项验收变成明确断言；确定性检查与模型评语区分；保留每条断言的失败原因，不能只有一个总分。测试运行失败、断言失败、未运行是不同状态。
- 不照搬：`AssertionsResult.noAssertsResult()` 返回 pass=true；在我们的核验场景，无验收断言只能算未验证，不能算通过。零权重指标、平均分也不应掩盖硬性要求失败。
- 源码：https://github.com/promptfoo/promptfoo/blob/b0723901f5ebc96847473ea27e342948ee51260d/src/assertions/json.ts
- 结果汇总：https://github.com/promptfoo/promptfoo/blob/b0723901f5ebc96847473ea27e342948ee51260d/src/assertions/assertionsResult.ts

## 4. Elephant Goldfish Model：让审阅意见有处理过程
- 仓库：https://github.com/google/elephant-goldfish-model
- 固定提交：72d06f52a2482885d9a64bd24b291c6e8628942c
- 许可：Apache-2.0。
- 路径：`egm-resolve/SKILL.md` 将意见区分为 CONTEST、ESCALATE、PROPOSE FIX、DECLINE；反驳需可读证据，只有作者知道的信息要升级确认。`egm-review-loop/SKILL.md` 区分 completed 和 not run，失败审阅不能被当成没问题，默认五轮上限、连续两轮 clean。
- 借鉴：审阅发现要有 ID、严重性、来源和处理结论；已接受风险/已反驳/待确认不混成“关闭”。可以导出给独立审阅者的包，避免把执行者结论当既定事实。
- 不照搬：流程多数在 Markdown 中，由宿主和模型执行，不是独立程序强制状态机；没有运行真实审阅时必须显示未运行。原型可提供审阅输入与导入格式，但不能把预写示例当自主审阅。
- 源码：https://github.com/google/elephant-goldfish-model/blob/72d06f52a2482885d9a64bd24b291c6e8628942c/skills/egm-resolve/SKILL.md
- 循环：https://github.com/google/elephant-goldfish-model/blob/72d06f52a2482885d9a64bd24b291c6e8628942c/skills/egm-review-loop/SKILL.md

## 5. SWE-agent：先复现，再修改，再重跑
- 仓库：https://github.com/SWE-agent/SWE-agent
- 固定提交：3ea751c087f32b16e039a2233dd6eefecef325d5
- 许可：MIT。
- 路径：`config/default.yaml` 提示先读代码、创建并运行复现脚本、修改、重跑并考虑边界。`tools/review_on_submit_m/bin/submit` 从真实 git diff 生成复审材料，按 review stage 输出复审提示，再产生提交补丁。
- 借鉴：同一规则在修改前后使用同一检查方法，保存真实差异与执行记录；如果测试后代码又变了，结果标过期或重新运行；失败不能被删除测试掩盖。
- 不照搬：其默认配置带基准测试背景，要求不改测试并移除复现脚本不应机械复制。提交脚本支持 --force；提示要求重跑并不是程序已经检查重跑发生。
- 源码：https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/config/default.yaml
- 提交审阅：https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/tools/review_on_submit_m/bin/submit

## 这次迭代建议
1. 优先做安全、透明的资料导入和跳过清单（Repomix）。
2. 将要求、场景、证据、检查关联起来并展示覆盖缺口（OpenSpec）。
3. 把确定性断言与 AI 评语分开，无断言不通过（Promptfoo）。
4. 增加可交给独立 Agent 的审阅包和状态记录（EGM）。
5. 保留修改前后同一故障场景的运行证据，绑定版本（SWE-agent）。

这些机制不要求直接安装五个项目。第一版采用独立、小规模实现即可。是否真的提高问题发现率、降低误报，仍须另设带已知问题的评测集；生成报告和通过结构校验均不代表已自主理解真实仓库。
