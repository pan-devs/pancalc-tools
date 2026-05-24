"""
pcalc/converter.py — Image conversion to/from Casio .g3p format.
Supports fx-CG10/20/50 and Graph 90+E.
"""

import struct, zlib, os, sys, re, unicodedata
from PIL import Image, ImageOps

WIDTH  = 384
HEIGHT = 192

PALETTE_3BIT = [
    (0, 0, 0),       # Negro
    (0, 0, 255),     # Azul
    (255, 0, 0),     # Rojo
    (255, 0, 255),   # Magenta
    (0, 255, 0),     # Verde
    (0, 255, 255),   # Cian
    (255, 255, 0),   # Amarillo
    (255, 255, 255), # Blanco
]


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def obfuscate(data):
    return bytes(((~b & 0x1F) << 3) | ((~b & 0xE0) >> 5) for b in data)


def deobfuscate(data):
    return bytes(~(((b & 0x07) << 5) | ((b & 0xF8) >> 3)) & 0xFF for b in data)


def build_header_32bit(total_size):
    inv_sz = (~total_size) & 0xFFFFFFFF
    lsb = inv_sz & 0xFF
    pair_sum = (((inv_sz >> 8) & 0xFF) + (inv_sz & 0xFF)) & 0xFF

    hdr = bytearray(32)
    hdr[0:8] = bytes([0xAA, 0xAC, 0xBD, 0xAF, 0x90, 0x88, 0x9A, 0x8D])
    hdr[8] = 0x82
    hdr[9] = 0xFF
    hdr[0x0A] = 0xEF
    hdr[0x0B] = 0xFF
    hdr[0x0C] = 0xEF
    hdr[0x0D] = 0xFF
    hdr[0x0E] = (lsb + 0xBF) & 0xFF
    hdr[0x0F] = 0xFE
    hdr[0x10] = (inv_sz >> 24) & 0xFF
    hdr[0x11] = (inv_sz >> 16) & 0xFF
    hdr[0x12] = (inv_sz >> 8) & 0xFF
    hdr[0x13] = inv_sz & 0xFF
    hdr[0x14] = (lsb + 0x48) & 0xFF
    hdr[0x1C] = (pair_sum + 0x9B) & 0xFF
    hdr[0x1D] = (lsb + 0x85) & 0xFF
    return bytes(hdr)


def build_metadata(total_size):
    buf = bytearray(0xC0 - 0x20)
    buf[0:6] = bytes([0x43, 0x50, 0x00, 0x01, 0x00, 0x00])
    struct.pack_into('>I', buf, 0x10, total_size - 0x20)
    struct.pack_into('>I', buf, 0x14, 0x00000001)
    struct.pack_into('>I', buf, 0x18, total_size - 0xB8)
    struct.pack_into('>I', buf, 0x98, 0x00010000)
    struct.pack_into('>I', buf, 0x9C, total_size - 0xCC)
    return bytes(buf)


def build_image_header(bit_depth, data_size):
    buf = bytearray(18)
    buf[0:2] = struct.pack('>H', 0)
    buf[2:4] = struct.pack('>H', WIDTH)
    buf[4:6] = struct.pack('>H', HEIGHT)
    buf[6:8] = struct.pack('>H', bit_depth)
    buf[8:10] = struct.pack('>H', 0x0100)
    buf[10:12] = struct.pack('>H', 0)
    buf[12:16] = struct.pack('>I', data_size + 2)
    buf[16:18] = struct.pack('>H', 0x3C1B)
    return bytes(buf)


def _encode_g3p_bytes(pixels, bit_depth):
    """Encode RGB pixels (384x192) into complete .g3p bytes (headers + data)."""
    if bit_depth == 16:
        raw_data = bytearray()
        for r, g, b in pixels:
            c = rgb565(r, g, b)
            raw_data.append((c >> 8) & 0xFF)
            raw_data.append(c & 0xFF)
    elif bit_depth == 3:
        raw_data = bytearray()
        i = 0
        while i < len(pixels):
            c1 = _nearest_color(pixels[i])
            i += 1
            if i < len(pixels):
                c2 = _nearest_color(pixels[i])
                i += 1
                raw_data.append((c1 << 5) | (c2 << 2))
            else:
                raw_data.append(c1 << 5)
    else:
        raise ValueError("bit_depth must be 3 or 16")

    raw_bytes = bytes(raw_data)
    compressed = zlib.compress(raw_bytes)[2:-4]
    adler = zlib.adler32(raw_bytes) & 0xFFFFFFFF
    data_with_checksum = compressed + struct.pack('>I', adler)
    obfuscated = obfuscate(data_with_checksum)

    img_hdr = build_image_header(bit_depth, len(obfuscated))
    total_size = 210 + len(obfuscated)
    metadata = build_metadata(total_size)
    header_32 = build_header_32bit(total_size)

    return header_32 + metadata + img_hdr + obfuscated


def _nearest_color(pixel):
    r, g, b = pixel
    best_idx = 0
    best_dist = float('inf')
    for i, (pr, pg, pb) in enumerate(PALETTE_3BIT):
        d = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx


def _process_image_to_g3p(img: Image.Image, output_path: str, bit_depth: int = 16,
                           split: str = "auto", overlap: int = 16,
                           input_name: str = "") -> None:
    """Encode a PIL Image to .g3p file(s), handling split and letterbox."""
    src_w, src_h = img.size
    scale_w = WIDTH / src_w
    fit_h = int(src_h * scale_w)

    do_split = split == "on" or (split == "auto" and src_h > src_w and fit_h > HEIGHT)

    if do_split:
        img = img.resize((WIDTH, fit_h), Image.LANCZOS)
        step = max(1, HEIGHT - overlap)
        n_strips = (fit_h - overlap + step - 1) // step
        base, ext = os.path.splitext(output_path)

        for i in range(n_strips):
            y_start = i * step
            y_end = min(y_start + HEIGHT, fit_h)
            strip = img.crop((0, y_start, WIDTH, y_end))

            if strip.height < HEIGHT:
                canvas = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
                canvas.paste(strip, (0, (HEIGHT - strip.height) // 2))
                strip = canvas

            pixels = list(strip.getdata())
            g3p_bytes = _encode_g3p_bytes(pixels, bit_depth)

            strip_name = f"{base}_{i+1:03d}{ext}"
            with open(strip_name, 'wb') as f:
                f.write(g3p_bytes)

            label = input_name or os.path.basename(output_path)
            print(f"OK: {label} -> {os.path.basename(strip_name)}")
            print(f"    Strip {i+1}/{n_strips}, {len(g3p_bytes)} bytes, {bit_depth}-bit, {WIDTH}x{HEIGHT}")
    else:
        scale = min(WIDTH / src_w, HEIGHT / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
        x_offset = (WIDTH - new_w) // 2
        y_offset = (HEIGHT - new_h) // 2
        canvas.paste(img, (x_offset, y_offset))

        pixels = list(canvas.getdata())
        g3p_bytes = _encode_g3p_bytes(pixels, bit_depth)

        with open(output_path, 'wb') as f:
            f.write(g3p_bytes)

        label = input_name or output_path
        print(f"OK: {label} -> {output_path}")
        print(f"    {len(g3p_bytes)} bytes, {bit_depth}-bit, {WIDTH}x{HEIGHT}")


def convert_image(input_path, output_path, bit_depth=16, split="auto", overlap=16):
    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img) or img
    if img.mode != 'RGB':
        img = img.convert('RGB')
    _process_image_to_g3p(img, output_path, bit_depth, split, overlap,
                          os.path.basename(input_path))


RENDER_SCALE = 12.5


def convert_document_g3p(input_path, output_path, bit_depth=16, overlap=16):
    """Render each page of a PDF/DOCX to 384px-wide images and convert to .g3p strips."""
    import fitz

    doc = fitz.open(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    out_base  = os.path.splitext(output_path)[0]

    for i, page in enumerate(doc):
        zoom = WIDTH * RENDER_SCALE / page.rect.width
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        page_path = f"{out_base}_{i+1:03d}.g3p"
        label = f"{base_name} (p.{i+1})"
        _process_image_to_g3p(img, page_path, bit_depth, "on", overlap, label)

    doc.close()


def decode_image(input_path, output_path):
    with open(input_path, 'rb') as f:
        raw = f.read()

    hdr = raw[:32]
    if hdr[0:8] != bytes([0xAA, 0xAC, 0xBD, 0xAF, 0x90, 0x88, 0x9A, 0x8D]):
        print("Error: invalid magic header", file=sys.stderr)
        sys.exit(1)

    bit_depth = struct.unpack('>H', raw[0xC6:0xC8])[0]
    img_hdr_sz = struct.unpack('>I', raw[0xCC:0xD0])[0]
    obfuscated = raw[0xD2:]
    if len(obfuscated) != img_hdr_sz - 2:
        print("Warning: data size mismatch", file=sys.stderr)

    encoded = deobfuscate(obfuscated)
    stored_adler = struct.unpack('>I', encoded[-4:])[0]
    compressed = encoded[:-4]
    raw_bytes = zlib.decompress(compressed, -zlib.MAX_WBITS)

    if zlib.adler32(raw_bytes) & 0xFFFFFFFF != stored_adler:
        print("Error: Adler32 mismatch", file=sys.stderr)
        sys.exit(1)

    if bit_depth == 16:
        expected_len = WIDTH * HEIGHT * 2
    elif bit_depth == 3:
        expected_len = (WIDTH * HEIGHT + 1) // 2  # 2px per byte
    else:
        expected_len = 0

    if len(raw_bytes) < expected_len:
        print("Error: insufficient data", file=sys.stderr)
        sys.exit(1)

    if bit_depth == 16:
        img = Image.new('RGB', (WIDTH, HEIGHT))
        px = img.load()
        idx = 0
        for y in range(HEIGHT):
            for x in range(WIDTH):
                hi = raw_bytes[idx]; lo = raw_bytes[idx+1]
                c = (hi << 8) | lo
                r = (c >> 11) & 0x1F; r = (r << 3) | (r >> 2)
                g = (c >> 5) & 0x3F;  g = (g << 2) | (g >> 4)
                b = c & 0x1F;         b = (b << 3) | (b >> 2)
                px[x, y] = (r, g, b)
                idx += 2
    elif bit_depth == 3:
        img = Image.new('RGB', (WIDTH, HEIGHT))
        px = img.load()
        idx = 0
        for y in range(HEIGHT):
            for x in range(0, WIDTH, 2):
                b = raw_bytes[idx]
                c1 = (b >> 5) & 0x07
                c2 = (b >> 2) & 0x07
                px[x, y] = PALETTE_3BIT[c1]
                if x + 1 < WIDTH:
                    px[x+1, y] = PALETTE_3BIT[c2]
                idx += 1

    img.save(output_path)
    print(f"OK: {input_path} -> {output_path}")
    print(f"    {bit_depth}-bit, {WIDTH}x{HEIGHT}")


_ASCII_MAP = str.maketrans({
    'ß': 'ss', 'ẞ': 'SS',
    'œ': 'oe', 'Œ': 'OE',
    'æ': 'ae', 'Æ': 'AE',
    'ð': 'd',  'Ð': 'D',
    'þ': 'th', 'Þ': 'TH',
})


def _clean_text(text: str) -> str:
    """Strip accents and non-ASCII chars for calculator compatibility."""
    # Handle special multi-char mappings first
    text = text.translate(_ASCII_MAP)
    # NFD decomposition: é → e + combining acute
    text = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks (accents, cedillas, etc.)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    # Strip remaining non-ASCII (should only be unusual chars now)
    text = ''.join(c if ord(c) < 128 else ' ' for c in text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def convert_text(input_path: str, output_path: str):
    """Extract text from a PDF or DOCX file and save as plain text."""
    import fitz  # pymupdf

    doc = fitz.open(input_path)
    total_chars = 0
    lines: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            cleaned = _clean_text(text)
            if cleaned:
                lines.append(cleaned)
                total_chars += len(cleaned)
    doc.close()

    if total_chars < 10 * len(lines) if lines else 1:
        print(f"Note: very little text extracted — this may be a scanned PDF (no selectable text).",
              file=sys.stderr)

    result = "\n\n".join(lines)
    with open(output_path, "w", encoding="ascii") as f:
        f.write(result)
        f.write("\n")

    print(f"OK: {input_path} -> {output_path}")
    print(f"    {len(result)} chars, {len(lines)} non-empty pages")