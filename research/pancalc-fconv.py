#!/usr/bin/env python3
"""
pancalc-fconv.py — Convierte imágenes a formato .g3p (Casio fx-CG50 / Graph 90+E).
Formato: CP (Casio Provided), 384×192 px, RGB565 (16-bit) o 3-bit indexado.
"""

import argparse, struct, zlib, os, sys
from PIL import Image

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


def convert_image(input_path, output_path, bit_depth=16):
    img = Image.open(input_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Preservar aspect ratio: redimensionar para que quepa en 384x192 y centrar con letterbox
    src_w, src_h = img.size
    scale = min(WIDTH / src_w, HEIGHT / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
    x_offset = (WIDTH - new_w) // 2
    y_offset = (HEIGHT - new_h) // 2
    canvas.paste(img, (x_offset, y_offset))
    img = canvas

    pixels = [img.getpixel((x, y)) for y in range(HEIGHT) for x in range(WIDTH)]

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
        raise ValueError("bit_depth debe ser 3 o 16")

    raw_bytes = bytes(raw_data)
    compressed = zlib.compress(raw_bytes)[2:-4]
    adler = zlib.adler32(raw_bytes) & 0xFFFFFFFF
    data_with_checksum = compressed + struct.pack('>I', adler)
    obfuscated = obfuscate(data_with_checksum)

    img_hdr = build_image_header(bit_depth, len(obfuscated))
    total_size = 210 + len(obfuscated)
    metadata = build_metadata(total_size)
    header_32 = build_header_32bit(total_size)

    g3p = header_32 + metadata + img_hdr + obfuscated

    with open(output_path, 'wb') as f:
        f.write(g3p)

    print(f"OK: {input_path} -> {output_path}")
    print(f"    {len(g3p)} bytes, {bit_depth}-bit, {WIDTH}x{HEIGHT}")


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


def decode_image(input_path, output_path):
    with open(input_path, 'rb') as f:
        raw = f.read()

    hdr = raw[:32]
    if hdr[0:8] != bytes([0xAA, 0xAC, 0xBD, 0xAF, 0x90, 0x88, 0x9A, 0x8D]):
        print("Error: header magico invalido", file=sys.stderr)
        sys.exit(1)

    bit_depth = struct.unpack('>H', raw[0xC6:0xC8])[0]
    img_hdr_sz = struct.unpack('>I', raw[0xCC:0xD0])[0]
    obfuscated = raw[0xD2:]
    if len(obfuscated) != img_hdr_sz - 2:
        print("Advertencia: tamano de datos no coincide", file=sys.stderr)

    encoded = deobfuscate(obfuscated)

    stored_adler = struct.unpack('>I', encoded[-4:])[0]
    compressed = encoded[:-4]

    raw_bytes = zlib.decompress(compressed, -zlib.MAX_WBITS)

    if zlib.adler32(raw_bytes) & 0xFFFFFFFF != stored_adler:
        print("Error: Adler32 no coincide", file=sys.stderr)
        sys.exit(1)

    expected_len = WIDTH * HEIGHT * (2 if bit_depth == 16 else 0)
    if bit_depth == 16:
        expected_len = WIDTH * HEIGHT * 2
    elif bit_depth == 3:
        expected_len = (WIDTH * HEIGHT * 3 + 7) // 8
    if len(raw_bytes) < expected_len:
        print("Error: datos insuficientes", file=sys.stderr)
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


def main():
    parser = argparse.ArgumentParser(
        description="Convierte imagenes a formato Casio .g3p (CG50/Graph 90+E)")
    parser.add_argument("input", help="Archivo de imagen de entrada (.jpg/.png/...) o .g3p")
    parser.add_argument("-o", "--output", help="Archivo de salida")
    parser.add_argument("-b", "--bits", type=int, choices=[3, 16], default=16,
                        help="bits: 3 (8 colores) o 16 (65536)")
    parser.add_argument("--decode", action="store_true",
                        help="Decodificar .g3p a PNG")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: no se encuentra '{args.input}'")
        sys.exit(1)

    if args.decode:
        output = args.output
        if not output:
            base = os.path.splitext(args.input)[0]
            output = f"{base}_decoded.png"
        decode_image(args.input, output)
    else:
        output = args.output
        if not output:
            base = os.path.splitext(args.input)[0]
            output = f"{base}.g3p"
        convert_image(args.input, output, args.bits)


if __name__ == "__main__":
    main()
