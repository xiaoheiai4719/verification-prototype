# v0.2 验证结果

- 原 v0.1 17 项回归测试通过；新增23项机制测试通过；合计40/40。
- compileall 通过。
- 实际 demo：baseline normal passed；baseline lost_response failed（2对象）；fixed normal/lost_response 均 passed（1对象）。
- baseline/fixed 分开显示结论；R3 缺真实供应商证据，保持 needs_evidence。
- 通用 inspect 命令成功，runs 为空，不会伪称运行测试。
- 审阅导入实际 smoke 成功；快照不匹配、重大问题 decline、无依据 contest 的拒绝由测试验证。
- 输入快照 check 返回 MATCH；改变代码/方案导致过期由自动测试验证。
- 静态 HTML 结构/转义测试通过；未完成浏览器视觉验收（前次 Chromium 因环境 socket 权限无法启动，本轮未重复尝试）。
- 未调用模型、真实外部服务；未自主研究真实仓库；未做安全渗透或产品效果评测。

## 独立复审修正（v0.2.1）

- 先新增回归测试再修复：原版 44 项中 4 项失败，复现日志见 review-reproduction.txt。
- 超时结果保留 requirement_ids、runner_sha256、运行时长、范围和空断言，要求状态正确归为 blocked，不会丢失关联。
- 合法 JSON {} 缺少观察字段时总体保持 error，不再误标 failed/contradicted；非对象 JSON 也归 error。
- check 同时核对输入和每条运行的 runner_sha256。指纹绑定 demo_probe.py、verify.py、workflow.py，缺少指纹也过期。未执行测试的 inspect 报告没有运行结果，无需运行器匹配。
- 测试实际修改临时副本的上述三个文件，逐个验证旧运行结果过期。
- 最终 46/46 自动测试通过，compileall 通过；demo 重新实际运行，四项结果仍为 passed/failed/passed/passed；新报告 check 返回 MATCH。
- 仍不是防篡改签名，也未绑定 Python 解释器、操作系统及外部依赖环境；不构成完整可复现环境保证。
