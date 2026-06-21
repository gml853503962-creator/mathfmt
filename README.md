# MathFmt

[![CI](https://github.com/gml853503962-creator/mathfmt/actions/workflows/ci.yml/badge.svg)](https://github.com/gml853503962-creator/mathfmt/actions/workflows/ci.yml)

[中文](#中文) | [English](#english)

MathFmt turns plain-text formulas in Word documents into native Word OMML equations —
stacked fractions, radicals, superscripts, subscripts, derivatives, and standard
mathematical operators — suitable for textbooks, exams, and technical reports.

---

## Status

**Alpha (v0.1.0).** Formula detection uses heuristic character-class scanning, not
semantic understanding. False positives and false negatives are expected. Always
review `candidates.json` before applying, or use `convert` only on formula-dense
documents. See [Limitations](docs/formula-syntax.md#6-limitations).

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
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json  # 审核后转换
mathfmt convert input.docx                           # 保守一键转换
mathfmt validate input.docx                           # 离线结构验证
mathfmt doctor                                        # 环境诊断
```

### 版本路线

| 版本 | 内容 |
|---|---|
| **0.1.0** (2026-06-21) | 基础扫描、审核、转换；原生 Word 公式输出；Windows + Office |
| **0.2.0** (2026-Q3) | 跨平台内置 OMML；置信度评分；独立验证；积分/求和/矩阵/向量/分段 |
| **0.3.0** (2026-Q4) | 正式语法引擎；LaTeX 输入；性能优化 |
| **1.0.0** (2027) | 稳定 API；长期支持 |

### 更多文档

- [公式语法参考](docs/formula-syntax.md) — 完整预处理规则、语法、MathML 映射和限制
- [工作流指南](docs/workflow.md) — 安装、审核流程、错误处理、CI 使用

### 维护

单人维护（Leo），尽力响应。欢迎提交 Issue 和 PR。安全漏洞请参阅 [SECURITY.md](SECURITY.md)。

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
mathfmt apply   input.docx --review candidates.json --output out.docx --report result.json  # Apply reviewed candidates
mathfmt convert input.docx                           # Conservative one-step conversion
mathfmt validate input.docx                           # Offline structure validation
mathfmt doctor                                        # Environment check
```

### Version Roadmap

| Version | Scope |
|---|---|
| **0.1.0** (2026-06-21) | Scan, review, convert; native Word OMML; Windows + Office |
| **0.2.0** (2026-Q3) | Cross-platform built-in OMML; confidence scoring; validate; integrals, sums, matrices |
| **0.3.0** (2026-Q4) | Formal grammar engine; LaTeX input; performance |
| **1.0.0** (2027) | Stable API; long-term support |

### Further Reading

- [Formula Syntax Reference](docs/formula-syntax.md) — every preprocessing rule, the full grammar, MathML output mapping, and known limitations
- [Workflow Guide](docs/workflow.md) — step-by-step install, review flow, troubleshooting, CI usage

### Maintenance

Single-maintainer project (Leo), best-effort response. Issues and pull requests are
welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
and [SECURITY.md](SECURITY.md).

---

## Contributing

Issues and pull requests are welcome.

## License

MIT License. Copyright (c) 2026 Leo.
