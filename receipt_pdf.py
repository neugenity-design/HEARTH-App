"""Small dependency-free PDF renderer for locked Hearth payment receipts."""

from textwrap import wrap


def _safe(value):
    text = str(value or '').replace('\r', ' ').replace('\n', ' ')
    return text.replace('—', '-').replace('–', '-').replace('•', '-').strip()


def _pdf_text(value):
    return _safe(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _money(value):
    return f'${float(value or 0):,.2f}'


def create_receipt_pdf(snapshot, reference):
    """Return a one-page, printable PDF using only the locked receipt snapshot."""
    owner = snapshot.get('owner') or {}
    business = owner.get('business') or owner.get('name') or 'Property manager'
    rows = [
        ('Received from', snapshot.get('tenant_name')),
        ('Property', snapshot.get('property_name')),
        ('Address', snapshot.get('property_address')),
        ('For', snapshot.get('category')),
        ('Description', snapshot.get('description')),
        ('Amount received', _money(snapshot.get('amount'))),
        ('Payment method', snapshot.get('method')),
        ('Reference', snapshot.get('reference')),
    ]

    commands = [
        '0.141 0.286 0.231 rg 0 690 612 102 re f',
        '1 1 1 rg BT /F2 27 Tf 54 744 Td (Payment receipt) Tj ET',
        f'0.87 0.92 0.82 rg BT /F1 10 Tf 54 718 Td ({_pdf_text(reference)}  |  {_pdf_text(snapshot.get("date"))}) Tj ET',
        f'0.149 0.235 0.204 rg BT /F2 14 Tf 54 658 Td ({_pdf_text(business)}) Tj ET',
    ]
    if snapshot.get('void'):
        commands.extend([
            '0.64 0.25 0.21 rg BT /F2 24 Tf 430 744 Td (VOID) Tj ET',
            '0.64 0.25 0.21 rg BT /F2 10 Tf 430 724 Td (Not a valid receipt) Tj ET',
        ])
    y = 640
    for line in [owner.get('address'), owner.get('email')]:
        if _safe(line):
            commands.append(f'0.40 0.46 0.42 rg BT /F1 9 Tf 54 {y} Td ({_pdf_text(line)}) Tj ET')
            y -= 14

    y -= 22
    for label, value in rows:
        value_lines = wrap(_safe(value) or '-', width=62, break_long_words=True, break_on_hyphens=False) or ['-']
        height = max(38, 24 + 12 * (len(value_lines) - 1))
        commands.append(f'0.89 0.91 0.87 RG 0.6 w 54 {y-height+7} m 558 {y-height+7} l S')
        commands.append(f'0.45 0.50 0.46 rg BT /F2 8 Tf 54 {y-9} Td ({_pdf_text(label.upper())}) Tj ET')
        for index, line in enumerate(value_lines):
            font = 'F2' if label == 'Amount received' else 'F1'
            size = 13 if label == 'Amount received' else 10
            commands.append(f'0.149 0.235 0.204 rg BT /{font} {size} Tf 206 {y-10-index*12} Td ({_pdf_text(line)}) Tj ET')
        y -= height

    commands.extend([
        '0.93 0.95 0.90 rg 54 49 504 48 re f',
        '0.34 0.43 0.37 rg BT /F1 8 Tf 68 78 Td (This receipt records a payment entered by the property owner.) Tj ET',
        f'0.34 0.43 0.37 rg BT /F1 8 Tf 68 63 Td (Receipt {_pdf_text(reference)} is locked to the payment shown above.) Tj ET',
    ])
    stream = ('\n'.join(commands) + '\n').encode('cp1252', 'replace')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
        f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'endstream',
    ]
    output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode())
        output.extend(body)
        output.extend(b'\nendobj\n')
    xref = len(output)
    output.extend(f'xref\n0 {len(objects)+1}\n'.encode())
    output.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(output)
