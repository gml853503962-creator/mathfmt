#!/usr/bin/env python3
"""Pure-Python MathML to OMML converter — no XSL required."""

from __future__ import annotations

from lxml import etree

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def qname(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


INVISIBLE_TIMES = "⁢"

MATHML_TAGS = {
    "mi",
    "mn",
    "mo",
    "mfrac",
    "msqrt",
    "msup",
    "msub",
    "msubsup",
    "mfenced",
    "munder",
    "mrow",
    "mtable",
    "mtr",
    "mtd",
}


def mathml_to_omml_py(math_elem: etree._Element) -> etree._Element:
    omath = etree.Element(qname(M_NS, "oMath"))
    for child in math_elem:
        _convert(child, omath)
    return omath


def _convert(elem: etree._Element, parent: etree._Element) -> None:
    tag = etree.QName(elem).localname

    if tag not in MATHML_TAGS:
        for child in elem:
            _convert(child, parent)
        return

    if tag == "mi":
        _text_run(parent, elem.text or "")
    elif tag == "mn":
        _text_run(parent, elem.text or "")
    elif tag == "mo":
        text = elem.text or ""
        if text != INVISIBLE_TIMES:
            _text_run(parent, text)
    elif tag == "mfrac":
        _fraction(elem, parent)
    elif tag == "msqrt":
        _radical(elem, parent)
    elif tag == "msup":
        _script(elem, parent, "sSup", "sup")
    elif tag == "msub":
        _script(elem, parent, "sSub", "sub")
    elif tag == "msubsup":
        _subsup(elem, parent)
    elif tag == "mfenced":
        _delimiter(elem, parent)
    elif tag == "munder":
        _limit(elem, parent)
    elif tag == "mtable":
        _matrix(elem, parent)
    elif tag == "mrow":
        for child in elem:
            _convert(child, parent)


def _text_run(parent: etree._Element, text: str) -> None:
    r = etree.SubElement(parent, qname(M_NS, "r"))
    t = etree.SubElement(r, qname(M_NS, "t"))
    t.text = text


def _fraction(elem: etree._Element, parent: etree._Element) -> None:
    f = etree.SubElement(parent, qname(M_NS, "f"))
    num = etree.SubElement(f, qname(M_NS, "num"))
    if len(elem) > 0:
        _convert(elem[0], num)
    den = etree.SubElement(f, qname(M_NS, "den"))
    if len(elem) > 1:
        _convert(elem[1], den)


def _radical(elem: etree._Element, parent: etree._Element) -> None:
    rad = etree.SubElement(parent, qname(M_NS, "rad"))
    rad_pr = etree.SubElement(rad, qname(M_NS, "radPr"))
    deg_hide = etree.SubElement(rad_pr, qname(M_NS, "degHide"))
    deg_hide.set(qname(M_NS, "val"), "1")
    etree.SubElement(rad, qname(M_NS, "deg"))
    e = etree.SubElement(rad, qname(M_NS, "e"))
    for child in elem:
        _convert(child, e)


def _script(
    elem: etree._Element,
    parent: etree._Element,
    container: str,
    script_role: str,
) -> None:
    container_elem = etree.SubElement(parent, qname(M_NS, container))
    e = etree.SubElement(container_elem, qname(M_NS, "e"))
    if len(elem) > 0:
        _convert(elem[0], e)
    script = etree.SubElement(container_elem, qname(M_NS, script_role))
    if len(elem) > 1:
        _convert(elem[1], script)


def _subsup(elem: etree._Element, parent: etree._Element) -> None:
    ss = etree.SubElement(parent, qname(M_NS, "sSubSup"))
    e = etree.SubElement(ss, qname(M_NS, "e"))
    if len(elem) > 0:
        _convert(elem[0], e)
    sub = etree.SubElement(ss, qname(M_NS, "sub"))
    if len(elem) > 1:
        _convert(elem[1], sub)
    sup = etree.SubElement(ss, qname(M_NS, "sup"))
    if len(elem) > 2:
        _convert(elem[2], sup)


def _delimiter(elem: etree._Element, parent: etree._Element) -> None:
    d = etree.SubElement(parent, qname(M_NS, "d"))
    d_pr = etree.SubElement(d, qname(M_NS, "dPr"))
    beg = etree.SubElement(d_pr, qname(M_NS, "begChr"))
    beg.set(qname(M_NS, "val"), elem.get("open", "("))
    end = etree.SubElement(d_pr, qname(M_NS, "endChr"))
    end.set(qname(M_NS, "val"), elem.get("close", ")"))
    e = etree.SubElement(d, qname(M_NS, "e"))
    for child in elem:
        _convert(child, e)


def _limit(elem: etree._Element, parent: etree._Element) -> None:
    lim_low = etree.SubElement(parent, qname(M_NS, "limLow"))
    e = etree.SubElement(lim_low, qname(M_NS, "e"))
    if len(elem) > 0:
        _convert(elem[0], e)
    lim = etree.SubElement(lim_low, qname(M_NS, "lim"))
    if len(elem) > 1:
        _convert(elem[1], lim)


def _matrix(elem: etree._Element, parent: etree._Element) -> None:
    m = etree.SubElement(parent, qname(M_NS, "m"))
    etree.SubElement(m, qname(M_NS, "mPr"))
    # Add base justification for all columns
    for child in elem:
        if etree.QName(child).localname == "mtr":
            mr = etree.SubElement(m, qname(M_NS, "mr"))
            for td in child:
                e = etree.SubElement(mr, qname(M_NS, "e"))
                for cell_child in td:
                    _convert(cell_child, e)
