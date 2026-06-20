# MathFmt

[中文](#中文) | [English](#english)

MathFmt turns awkward plain-text formulas in Word documents into native Word equations suitable for
textbooks, exams, and technical reports. Processing stays on your computer.

## 中文

MathFmt 将 DOCX 文档中的普通文本公式转换为 Word 原生 OMML 公式，例如把 `ds(t)/dt`、
`sqrt(x^2+1)` 和 `p1` 排版为纸质教材中常见的分式、根号与上下标。

### 特点

- 保留原始 DOCX，始终写入新文件。
- 支持正文、表格、页眉、页脚和混合文本公式。
- 自动跳过代码、图片公式和已有 Word 原生公式。
- 提供可审核流程和保守的一键转换。
- 完全本地运行，不上传文档。

### 环境要求

- Windows 10/11
- Python 3.10 或更高版本
- Microsoft Word/Office，并包含 `MML2OMML.XSL`

MathFmt 不分发微软的 XSL 文件。它会自动检查常见 Office 安装目录，也可使用 `--xsl` 指定路径。

### 安装

```powershell
pip install mathfmt
mathfmt doctor
```

从源码开发安装：

```powershell
git clone https://github.com/gml853503962-creator/mathfmt.git
cd mathfmt
python -m pip install -e ".[dev]"
```

### 使用

```powershell
# 保守的一键转换
mathfmt convert input.docx

# 审核后转换
mathfmt scan input.docx --report candidates.json
mathfmt apply input.docx --review candidates.json --output output.docx --report result.json
```

一键转换默认生成 `input.mathfmt.docx` 和 `input.mathfmt.report.json`，不会覆盖原文件。编辑
`candidates.json` 中的 `selected`、`source` 或 `linear` 后再执行 `apply`。如果 Office 安装在
非标准目录，为 `apply`、`convert` 或 `doctor` 添加 `--xsl C:\path\to\MML2OMML.XSL`。

### Codex Skill

仓库中的 `skills/mathfmt` 可复制到 Codex 技能目录。技能依赖已安装的 `mathfmt` 命令。

## English

MathFmt converts plain-text formulas in DOCX files into native Word OMML equations with stacked
fractions, radicals, superscripts, subscripts, derivatives, and standard mathematical operators.

### Highlights

- Never overwrites the source DOCX.
- Handles body text, tables, headers, footers, and formulas mixed with prose.
- Skips likely code, image formulas, and existing Word equations.
- Offers both a review-first workflow and conservative one-step conversion.
- Processes documents locally without uploading them.

### Requirements and installation

MathFmt 0.1 supports Windows, Python 3.10+, and a Microsoft Office installation containing
`MML2OMML.XSL`. The Microsoft stylesheet is detected locally and is not distributed with MathFmt.

```powershell
pip install mathfmt
mathfmt doctor
mathfmt convert input.docx
```

For review-first conversion, run `scan`, edit the generated JSON, then run `apply` as shown above.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md).

## License

MIT License. Copyright (c) 2026 Leo.
