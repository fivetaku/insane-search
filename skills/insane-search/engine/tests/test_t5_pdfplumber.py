#!/usr/bin/env python3
"""M3 regression — optional pdfplumber PDF extraction with pypdf fallback.

Deterministic, network-free. Locks in:
  * pdfplumber present -> text-layer PDF extracted (even with pypdf blocked)
  * pdfplumber absent -> pypdf fallback still extracts
  * blank / no-text PDF -> pdf_no_text_layer
  * body over _PDF_MAX_BYTES -> pdf_too_large before any parser
  * neither extractor available -> pdf_no_extractor (graceful, no crash)
  * no AGPL import (pymupdf) anywhere in the engine

Run:  python3 engine/tests/test_t5_pdfplumber.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import engine.fetch_chain as fc  # noqa: E402
from engine.fetch_chain import _extract_pdf  # noqa: E402


def _build_text_pdf(lines) -> bytes:
    ops = ["BT /F1 12 Tf 72 740 Td 14 TL"]
    for ln in lines:
        ops.append(f"({ln}) Tj T*")
    ops.append("ET")
    stream = " ".join(ops).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode()
            + b" /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF")
    return bytes(out)


class _patched:
    def __init__(self, **kw):
        self.kw = kw; self.saved = {}
    def __enter__(self):
        for k, v in self.kw.items():
            self.saved[k] = getattr(fc, k); setattr(fc, k, v)
        return self
    def __exit__(self, *a):
        for k, v in self.saved.items():
            setattr(fc, k, v)


_TEXT_PDF = _build_text_pdf([f"Line number {i} of the document body." for i in range(12)])


def t_pdfplumber_extracts_even_without_pypdf() -> None:
    if fc._pdfplumber is None:
        print("  ⚠ skipped: pdfplumber not installed"); return
    with _patched(_PdfReader=None):  # force pdfplumber path
        title, text, q, err = _extract_pdf(_TEXT_PDF, "https://x.test/d.pdf")
    assert err == "", f"pdfplumber should extract; err={err}"
    assert "Line number 5" in text, f"expected body text, got: {text[:120]!r}"
    print(f"  ✓ pdfplumber extracts text-layer PDF (len={len(text)}, pypdf blocked)")


def t_pypdf_fallback_when_pdfplumber_absent() -> None:
    if fc._PdfReader is None:
        print("  ⚠ skipped: pypdf not installed"); return
    with _patched(_pdfplumber=None):  # force pypdf fallback
        title, text, q, err = _extract_pdf(_TEXT_PDF, "https://x.test/d.pdf")
    assert err == "" and "Line number 5" in text, f"pypdf fallback failed; err={err}"
    print("  ✓ pypdf fallback extracts when pdfplumber absent")


def t_blank_pdf_no_text_layer() -> None:
    try:
        from pypdf import PdfWriter
    except ImportError:
        print("  ⚠ skipped: pypdf not installed"); return
    import io
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    buf = io.BytesIO(); w.write(buf)
    _t, text, _q, err = _extract_pdf(buf.getvalue(), "https://x.test/blank.pdf")
    assert err == "pdf_no_text_layer" and text == "", f"got err={err}"
    print("  ✓ blank PDF -> pdf_no_text_layer")


def t_too_large_rejected_before_parser() -> None:
    with _patched(_PDF_MAX_BYTES=64):
        _t, text, _q, err = _extract_pdf(_TEXT_PDF, "https://x.test/big.pdf")
    assert err == "pdf_too_large" and text == "", f"got err={err}"
    print("  ✓ oversized PDF rejected before any parser")


def t_no_extractor_graceful() -> None:
    with _patched(_pdfplumber=None, _PdfReader=None):
        _t, text, _q, err = _extract_pdf(_TEXT_PDF, "https://x.test/d.pdf")
    assert err in ("pdf_no_extractor", "pypdf_missing") and text == "", f"got err={err}"
    print(f"  ✓ neither extractor -> graceful ({err}), no crash")


def t_no_agpl_import() -> None:
    # AGPL guard: no actual import of pymupdf / fitz (the pymupdf import name).
    # A prohibition mention in a comment is fine — only real imports are banned.
    import subprocess
    r = subprocess.run(
        ["grep", "-rnE", r"^\s*(import|from)\s+(pymupdf|fitz)\b", "engine/"],
        capture_output=True, text=True, cwd=ROOT)
    assert r.stdout.strip() == "", f"AGPL pymupdf/fitz import found:\n{r.stdout}"
    print("  ✓ no AGPL pymupdf/fitz import in engine/ (comment mention allowed)")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}"); failed += 1
    print(f"\n{'OK' if failed == 0 else 'FAIL'}: {len(tests)-failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
