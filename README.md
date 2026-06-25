# MathFmt

[![CI](https://github.com/gml853503962-creator/mathfmt/actions/workflows/ci.yml/badge.svg)](https://github.com/gml853503962-creator/mathfmt/actions/workflows/ci.yml)

[中文](#中文) | [English](#english)

MathFmt turns plain-text formulas in Word documents into native Word OMML equations —
stacked fractions, radicals, superscripts, subscripts, derivatives, and standard
mathematical operators — suitable for textbooks, exams, and technical reports.

---

## Quick Start · 快速开始

**Who is this for?** Anyone who writes math-heavy Word documents — teachers preparing
exams, students writing lab reports, engineers drafting technical specs. If you type
formulas like `x^2` or `sqrt(a/b)` in Word and want them rendered as proper equations,
MathFmt is for you.

**适合谁用？** 需要在 Word 里写数学公式的人——老师出试卷、学生写实验报告、工程师写技术文档。如果你在 Word 里输入 `x^2` 或 `sqrt(a/b)` 这样的文本公式，想让它们变成原生公式，MathFmt 就是你的工具。

### Install · 安装

```bash
pip install mathfmt
```

Requirements: Python ≥ 3.10. The only runtime dependency is `lxml`.

### Check your environment · 检查环境

```bash
mathfmt doctor
```

Prints Python version, backend availability, and platform info — useful before filing a bug report.

### Convert a document · 转换文档

```bash
# One-step conservative conversion (high-confidence formulas only)
mathfmt convert input.docx --output output.docx

# Scan first, review candidates, then apply (recommended for production)
mathfmt scan input.docx --report candidates.json
mathfmt apply input.docx --review candidates.json --report preview.json --dry-run
mathfmt apply input.docx --review candidates.json --output output.docx --report result.json
mathfmt apply input.docx --review candidates.json --output output.docx --report result.json --strict
```

For detailed workflow, see [docs/workflow.md](docs/workflow.md).

---

## Status

**Beta (v0.3.0).** Cross-platform OMML, confidence scoring, expanded formula support, self-update, parser fixes, and structured report/safety workflows.

---

## 中文

MathFmt 将 DOCX 中的普通文本公式排版为 Word 原生 OMML 公式。

### 快速示例

| 输入（纯文本） | 输出（Word 原生公式） |
|---|---|
| `ds(t)/dt` | 堆叠分式 d s(t) / d t |
| `s'(t) = -s''(t)` | 导数分数形式 |
| `sqrt(x^2 + 1)` | 根号 √(x²+1) |
| `x^3 + p1` | 上标 x³ + 下标 p₁ |
| `x != 0` | x ≠ 0 |
| `sin(x) + cos(x)` | sin(x) + cos(x) |
| `lim(p->0)` | lim 带下置 p→0 |
| `a/(b+c)` | 堆叠分式 |
| `e^(p1*t)` | e 的 p₁t 次幂 |
| `1(t)` | u(t)（单位阶跃） |
| `Delta + pi` | Δ + π |
| `x, y, z` | 逗号分隔序列 |

### 兼容性

| | Windows 10/11 | macOS | Linux |
|---|---|---|---|
| Python 3.10–3.13 | ✔ | ✔ | ✔ |
| 公式扫描 | ✔ | ✔ | ✔ |
| OMML 公式输出（内置 Python 后端） | ✔ | ✔ | ✔ |
| OMML 公式输出（Office XSL 后端） | ✔ | ✔¹ | ✔¹ |
| Word 渲染 | ✔ | ✔² | — |

¹ 需手动指定 `MML2OMML.XSL` 路径（`--xsl`）。  
² macOS 版 Microsoft Word。

### 命令

```powershell
mathfmt scan    input.docx --report candidates.json   # 扫描公式候选
mathfmt apply   input.docx --review candidates.json --report preview.json --dry-run  # 仅预览，不写 DOCX
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json  # 审核后转换
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json --strict  # 失败则不写输出
mathfmt convert input.docx                           # 保守一键转换
mathfmt validate input.docx                           # 离线结构验证
mathfmt doctor                                        # 环境诊断
mathfmt update                                        # 检查 GitHub 更新
```

### 更新

```powershell
mathfmt update              # 检查更新并显示安装命令
mathfmt update --check      # CI 模式：有更新时退出码 1，最新时退出码 0
mathfmt update --pre        # 包含预发布版本
mathfmt update --force      # 跳过缓存，立即检查 GitHub
```

检测结果缓存 1 小时。也可直接运行：

```powershell
pip install --upgrade mathfmt
```

### 版本路线

| 版本 | 内容 |
|---|---|
| **0.1.0** (2026-06-21) | 基础扫描、审核、转换；原生 Word 公式输出；Windows + Office |
| **0.2.0** (2026-06-21) | 跨平台内置 OMML；置信度评分；独立验证；积分/求和/矩阵/向量/分段 |
| **0.2.1** (2026-06-21) | GitHub 自更新；缓存隔离；SemVer 预发布支持 |
| **0.2.2** (2026-06-21) | CI/Ruff 修复；缓存崩溃修复；退出码修正；验证报告版本 |
| **0.2.3** (2026-06-22) | Parser 修复（省略号/阶乘/大型算子/边界/深度）；文档与示例完善 |
| **0.3.0** (2026-06-25) | 结构化转换报告；dry-run 预览；严格模式；失败公式提示；更好的错误信息 |
| **1.0.0** (2027) | 稳定 API；长期支持 |

### 更多文档

- [公式语法参考](docs/formula-syntax.md) — 完整预处理规则、语法、MathML 映射和限制
- [工作流指南](docs/workflow.md) — 安装、审核流程、错误处理、CI 使用
- [示例](examples/README.md) — 从零开始的测试文档准备和转换教程
- [路线图](ROADMAP.md) — 版本规划与功能展望

### 维护

单人维护（Leo），尽力响应。欢迎提交 Issue 和 PR，也可通过
[gml853503962@gmail.com](mailto:gml853503962@gmail.com) 联系。安全漏洞请参阅
[SECURITY.md](SECURITY.md)。

---

## English

MathFmt converts plain-text formulas in DOCX files into native Word OMML equations.

### Quick Examples

| Input (plain text in DOCX) | Output (native Word equation) |
|---|---|
| `ds(t)/dt` | Stacked fraction d s(t) / d t |
| `s'(t) = -s''(t)` | Leibniz fraction derivatives |
| `sqrt(x^2 + 1)` | Radical √(x²+1) |
| `x^3 + p1` | Superscript x³ + subscript p₁ |
| `x != 0` | x ≠ 0 |
| `sin(x) + cos(x)` | sin(x) + cos(x) |
| `lim(p->0)` | lim with under-script p→0 |
| `a/(b+c)` | Stacked fraction |
| `e^(p1*t)` | e raised to p₁t |
| `1(t)` | u(t) (unit step) |
| `Delta + pi` | Δ + π |
| `x, y, z` | Comma-separated sequence |

### Compatibility

| | Windows 10/11 | macOS | Linux |
|---|---|---|---|
| Python 3.10–3.13 | ✔ | ✔ | ✔ |
| Formula scanning | ✔ | ✔ | ✔ |
| OMML output (built-in Python backend) | ✔ | ✔ | ✔ |
| OMML output (Office XSL backend) | ✔ | ✔¹ | ✔¹ |
| Word rendering | ✔ | ✔² | — |

¹ Manual `--xsl` path required for Office XSL backend.  
² Microsoft Word for Mac.

### Commands

```powershell
mathfmt scan    input.docx --report candidates.json   # Scan formula candidates
mathfmt apply   input.docx --review candidates.json --report preview.json --dry-run  # Preview only
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json  # Apply reviewed candidates
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json --strict  # Do not write output on failures
mathfmt convert input.docx                           # Conservative one-step conversion
mathfmt validate input.docx                           # Offline structure validation
mathfmt doctor                                        # Environment check
mathfmt update                                        # Check GitHub for updates
```

### Updating

```powershell
mathfmt update              # Check for updates and show install commands
mathfmt update --check      # CI mode: exit 1 when update available, 0 when current
mathfmt update --pre        # Include pre-release versions
mathfmt update --force      # Skip cache, re-check GitHub immediately
```

Check results are cached for 1 hour. You can also upgrade directly:

```powershell
pip install --upgrade mathfmt
```

### Version Roadmap

| Version | Scope |
|---|---|
| **0.1.0** (2026-06-21) | Scan, review, convert; native Word OMML; Windows + Office |
| **0.2.0** (2026-06-21) | Cross-platform built-in OMML; confidence scoring; validate; integrals, sums, matrices |
| **0.2.1** (2026-06-21) | GitHub self-update; cache isolation; SemVer pre-release support |
| **0.2.2** (2026-06-21) | CI/Ruff fixes; cache crash fix; exit code correction; validate version |
| **0.2.3** (2026-06-22) | Parser fixes (ellipsis, factorial, n-ary, 1(t), x_bar, boundary); depth validation; docs & examples |
| **0.3.0** (2026-06-25) | Structured conversion reports; dry-run preview; strict mode; failed-formula warnings; better errors |
| **1.0.0** (2027) | Stable API; long-term support |

### Further Reading

- [Formula Syntax Reference](docs/formula-syntax.md) — every preprocessing rule, the full grammar, MathML output mapping, and known limitations
- [Workflow Guide](docs/workflow.md) — step-by-step install, review flow, troubleshooting, CI usage
- [Examples](examples/README.md) — walkthrough from a blank test document to formatted output
- [Roadmap](ROADMAP.md) — planned features and version timeline

### Maintenance

Single-maintainer project (Leo), best-effort response. Issues and pull requests are
welcome. You can also contact the maintainer at
[gml853503962@gmail.com](mailto:gml853503962@gmail.com). See
[CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and
[SECURITY.md](SECURITY.md).

---

## Contributing

Issues and pull requests are welcome.

## License

MIT License. Copyright (c) 2026 Leo.
