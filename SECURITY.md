# Security Policy

## Supported versions

MathFmt 1.x is the supported stable line. Users should run the latest available 1.x
release; pre-1.0 versions are unsupported.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the MathFmt repository. Do not include confidential
DOCX files; provide a synthetic reproducer instead. The maintainer will respond **within 7 days**
and aim to resolve within 30 days. Please allow time for investigation before public disclosure.
Alternatively, contact the maintainer at <gml853503962@gmail.com>.

MathFmt processes files locally. Treat untrusted DOCX files as untrusted ZIP/XML input and run the
tool with ordinary user privileges.

MathFmt rejects encrypted or duplicate ZIP members, excessive entry counts, oversized expanded
packages or members, suspicious compression ratios, and OOXML parts containing DTD declarations.
XML parsing disables external entities, DTD loading, network access, recovery mode, and unlimited
tree expansion. These limits reduce resource-exhaustion and entity-expansion risk; they do not make
untrusted documents equivalent to trusted content.
