# Documentación técnica — pancalc-fconv.py

## Estructura del archivo .g3p (variante CP)

El formato `.g3p` es un contenedor Casio para imágenes en calculadoras fx-CG. Este script genera la variante **CP** (Casio Provided, `CP0100`), compatible con fx-CG10/20/50 y Graph 90+E.

### Layout general

```
+0x00   32 bytes   Standard header (32-bit)
+0x20   160 bytes  Metadata block (CP0100)
+0xC0   18 bytes   Image header
+0xD2   variable   Image data (obfuscated)
```

### Standard header (offset 0x00, 32 bytes)

Campo común a todos los formatos G3\* (G3P, G3M, G3A, etc.). Los bytes de "seguridad" se calculan a partir del tamaño total del archivo.

| Offset | Bytes | Descripción |
|--------|-------|-------------|
| 0x00 | 8 | Magic: `AA AC BD AF 90 88 9A 8D` |
| 0x08 | 1 | Tipo: `0x82` (G3P) |
| 0x09 | 1 | `0xFF` |
| 0x0A | 1 | `0xEF` |
| 0x0B | 1 | `0xFF` |
| 0x0C | 1 | `0xEF` |
| 0x0D | 1 | `0xFF` |
| 0x0E | 1 | Seguridad: `(LSB(~total_size) + 0xBF) & 0xFF` |
| 0x0F | 1 | `0xFE` |
| 0x10 | 4 | `~total_size & 0xFFFFFFFF` (big-endian) |
| 0x14 | 1 | Seguridad: `(LSB(~total_size) + 0x48) & 0xFF` |
| 0x15 | 7 | Cero |
| 0x1C | 1 | Seguridad: `(suma_low16(~total_size) + 0x9B) & 0xFF` |
| 0x1D | 1 | Seguridad: `(LSB(~total_size) + 0x85) & 0xFF` |
| 0x1E | 2 | Cero |

### Metadata CP0100 (offset 0x20, 160 bytes)

| Offset | Bytes | Descripción |
|--------|-------|-------------|
| 0x20 | 6 | `43 50 00 01 00 00` (ASCII "CP" = Casio Provided) |
| 0x26 | 10 | Cero |
| 0x30 | 4 | `total_size - 0x20` (big-endian) |
| 0x34 | 4 | `00 00 00 01` |
| 0x38 | 4 | `total_size - 0xB8` (big-endian) |
| 0x3C | 124 | Cero |
| 0xB8 | 4 | `00 01 00 00` |
| 0xBC | 4 | `total_size - 0xCC` (big-endian) |

### Image header (offset 0xC0, 18 bytes)

| Offset | Bytes | Tipo | Descripción |
|--------|-------|------|-------------|
| 0xC0 | 2 | u16 big-endian | `0x0000` (desconocido) |
| 0xC2 | 2 | u16 big-endian | Ancho en píxeles: `0x0180` = 384 |
| 0xC4 | 2 | u16 big-endian | Alto en píxeles: `0x00C0` = 192 |
| 0xC6 | 2 | u16 big-endian | Bits por píxel: `0x0010` (16) o `0x0003` (3) |
| 0xC8 | 2 | u16 big-endian | `0x0100` |
| 0xCA | 2 | u16 big-endian | `0x0000` |
| 0xCC | 4 | u32 big-endian | Tamaño de datos comprimidos + 2 |
| 0xD0 | 2 | u16 big-endian | `0x3C1B` (ID CP0100) |

### Image data (offset 0xD2)

Los datos de imagen pasan por tres transformaciones:

#### 1. Pixel encoding

**16-bit (RGB565):** Cada píxel se codifica en 2 bytes big-endian:

```
bits:  RRRRR GGGGGG BBBBB
        5b     6b     5b
valor: (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)
```

**3-bit (8 colores):** Cada byte almacena 2 píxeles:

```
bits:  [c1][c2][00]
        3b  3b  2b
valor: (c1 << 5) | (c2 << 2)
```

Paleta de 8 colores: negro, azul, rojo, magenta, verde, cian, amarillo, blanco. La conversión usa distancia euclidiana en RGB.

#### 2. Compresión DEFLATE

Los píxeles crudos se comprimen con `zlib.compress()` y se eliminan los 2 bytes de cabecera zlib y los 4 bytes de Adler32 del contenedor zlib:

```python
compressed = zlib.compress(raw_bytes)[2:-4]
```

El Adler32 se calcula por separado y se añade al final:

```python
adler = zlib.adler32(raw_bytes) & 0xFFFFFFFF
data = compressed + struct.pack('>I', adler)
```

#### 3. Ofuscación bitwise

Cada byte se transforma con inversión de bits y swapping de nibbles:

```python
# Obfuscate
(~b & 0x1F) << 3 | (~b & 0xE0) >> 5

# Deobfuscate (inversa)
~(((b & 0x07) << 5) | ((b & 0xF8) >> 3)) & 0xFF
```

Efecto: los bits 0-4 pasan a posición 3-7, los bits 5-7 pasan a posición 0-2, y luego se invierten todos los bits.

## Procesamiento de imagen

### Letterbox (fotos horizontales / cuadradas)

Para imágenes que entran en 384×192 preservando aspect ratio:

1. Escalar con `min(384/src_w, 192/src_h)` para que quepa
2. Centrar sobre un lienzo negro de 384×192

### Split (fotos verticales)

Para imágenes con `src_h > src_w` que exceden 192 px de alto:

1. Escalar ancho a 384 px manteniendo aspect ratio
2. Dividir en tiras de 192 px con **solapamiento** configurable (default 16 px)
3. Cada tira se codifica como un `.g3p` independiente
4. La última tira se centra con letterbox si mide menos de 192 px

```
Tira 1: [0, 192)
Tira 2: [176, 368)   ← 16 px de solapamiento
Tira 3: [352, 544)
...
```

### Corrección EXIF

Se aplica `PIL.ImageOps.exif_transpose()` para rotar automáticamente fotos de celular según los metadatos EXIF de orientación (valores 3, 6, 8).

## Decodificación (.g3p → PNG)

El proceso inverso:

1. Validar cabecera mágica
2. Leer `bit_depth` y tamaño de datos del image header
3. Extraer datos ofuscados desde offset 0xD2
4. Deobfuscar byte a byte
5. Separar Adler32 (últimos 4 bytes) y descomprimir DEFLATE con `zlib.decompress(wbits=-15)` (raw inflate)
6. Verificar Adler32
7. Decodificar píxeles según bit depth (RGB565 o 3-bit palette)
8. Guardar como PNG

## Referencias

- [Cemetech — Reverse-engineering the .g3p format](https://www.cemetech.net/forum/viewtopic.php?t=10560) — KermMartian
- [Cahute project](https://cahuteproject.org/) — Documentación de formatos Casio
- [Planète Casio — libcasio](https://git.planet-casio.com/Lailouezzz/libcasio) — Implementación de referencia
