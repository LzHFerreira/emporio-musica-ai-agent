"""Build tiny text PDFs for source-maintenance tests without an OCR dependency."""


def text_pdf(lines, pages=1):
    """Return a PDF containing the supplied ASCII text lines on each page."""
    return _document(_objects(_stream(lines), pages))


def _stream(lines):
    commands = ["BT /F1 10 Tf 36 800 Td"]
    for line in lines:
        commands.extend([f"({line}) Tj", "0 -18 Td"])
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def _objects(stream, pages):
    font_id = 3 + 2 * pages
    kids = " ".join(f"{3 + 2 * index} 0 R" for index in range(pages))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    for index in range(pages):
        page_id = 3 + 2 * index
        content_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode()
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return objects


def _document(objects):
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n".encode())
    pdf.extend(f"startxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)
