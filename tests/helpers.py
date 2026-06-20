from __future__ import annotations

import zipfile
from pathlib import Path

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <w:body>
  <w:p><w:r><w:t>Inline formula: x^2 + 1 = 2.</w:t></w:r></w:p>
  <w:p><w:r><w:t>ds(t)/dt = 3</w:t></w:r></w:p>
  <w:p><w:r><w:t>y = step(sys, t);</w:t></w:r></w:p>
  <w:p><m:oMath><m:r><m:t>x</m:t></m:r></m:oMath></w:p>
  <w:p><w:r><w:drawing/></w:r><w:r><w:t>image x = 1</w:t></w:r></w:p>
  <w:tbl><w:tr><w:tc>
   <w:tcPr><w:tcW w:w="4000" w:type="dxa"/></w:tcPr>
   <w:p><w:r><w:t>x^2+x^3+x^4+x^5+x^6+x^7+x^8+x^9+x^10+x^11+x^12+x^13+x^14+x^15+x^16+x^17 = 0</w:t></w:r></w:p>
  </w:tc></w:tr></w:tbl>
  <w:sectPr>
   <w:headerReference w:type="default" r:id="rIdHeader"/>
   <w:footerReference w:type="default" r:id="rIdFooter"/>
   <w:pgSz w:w="11906" w:h="16838"/>
   <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/>
  </w:sectPr>
 </w:body>
</w:document>"""

HEADER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:p><w:r><w:t>Header: p1 = p2</w:t></w:r></w:p>
</w:hdr>"""

FOOTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:p><w:r><w:t>Footer: sqrt(x^2) = x</w:t></w:r></w:p>
</w:ftr>"""

FAKE_XSL = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
 xmlns:mml="http://www.w3.org/1998/Math/MathML"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
 <xsl:output method="xml" encoding="UTF-8"/>
 <xsl:template match="/">
  <m:oMath><m:r><m:t><xsl:value-of select="//mml:math"/></m:t></m:r></m:oMath>
 </xsl:template>
</xsl:stylesheet>"""


def make_docx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("word/document.xml", DOCUMENT_XML)
        archive.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        archive.writestr("word/header1.xml", HEADER_XML)
        archive.writestr("word/footer1.xml", FOOTER_XML)
    return path


def make_fake_xsl(path: Path) -> Path:
    path.write_text(FAKE_XSL, encoding="utf-8")
    return path
