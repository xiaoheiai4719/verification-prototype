# 方案与代码核验助手

## 1. 快速体验

[下载 v0.3.0](https://github.com/xiaoheiai4719/verification-prototype/releases/tag/v0.3.0)，解压后用浏览器打开 `outputs/demo/learn.html`。先写下你的设计，再逐条看提示，最后对照源码和测试结果。

重新运行示例需要 Python 3.10+，无需安装依赖或配置 API key。在项目目录执行：

```sh
python3 verify.py demo
```

完成后打开 `outputs/demo/report.html` 查看完整核验报告。示例只运行随包提供的虚构测试，不验证真实存储供应商。

## 2. 核验自己的仓库

1. 准备一份 Markdown 方案，每条要求独占一行，例如 `- R1: 超时重试不能重复保存。`
2. 在本项目目录运行，替换下面的仓库和方案路径：

```sh
python3 verify.py inspect --repo /path/to/repo --plan /path/to/plan.md --out outputs/inspection
```

3. 打开 `outputs/inspection/report.html`。如需设计推演，参考 [决策卡模板](examples/retry-cards.json)，手写或让外部 AI 生成 `cards.json`，再用相同的命令加上 `--cards cards.json`。报告可能包含源码，分享前先检查。

## 3. 在终端进行设计推演

下面用内置样例；请先运行第 1 节的 `demo` 命令。用自己的仓库时，把报告、仓库、方案和卡片 ID 换成对应值。

```sh
session_dir=$(mktemp -d)
learn() {
  python3 verify.py learn "$@" --report outputs/demo/report.json \
    --card retry-response-lost --session "$session_dir/lesson.json" \
    --repo examples/upload --plan examples/upload/plan.md
}
learn start
learn answer --text '这里写你的首次判断'
learn hint
learn reveal
```

`hint` 可以重复运行来查看下一条提示。代码或方案变更后，重新生成报告并开启新会话。`inspect` 不会运行你的仓库代码，未运行的检查不会标成通过。

## 4. 运行测试

```sh
python3 -m unittest discover -s tests -v
```
