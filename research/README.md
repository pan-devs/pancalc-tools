# pancalc-fconv.py

Convierte imágenes (JPEG, PNG, BMP, GIF, etc.) al formato `.g3p` nativo de las calculadoras **Casio fx-CG10/20/50** y **Graph 90+E**.

## Requisitos

```bash
pip install Pillow
```

## Uso básico

```bash
python3 pancalc-fconv.py foto.jpg
# → foto_001.g3p (o foto.g3p si es horizontal)
```

### Opciones principales

| Opción | Descripción |
|--------|-------------|
| `-o`, `--output` | Nombre del archivo de salida |
| `-b`, `--bits` | `3` (8 colores, archivos ~5× más pequeños) o `16` (RGB565, 65536 colores, default) |
| `--decode` | Decodifica un `.g3p` a PNG |
| `--split` | `auto` (default), `on` (forzar división), `off` (forzar letterbox) |
| `--overlap` | Píxeles de solapamiento entre tiras (default: 16) |

### Ejemplos

```bash
# Default 16-bit
python3 pancalc-fconv.py paisaje.jpg -o paisaje.g3p

# 3-bit (más pequeño)
python3 pancalc-fconv.py logo.png -o logo.g3p -b 3

# Forzar división en tiras para foto horizontal
python3 pancalc-fconv.py panorama.jpg --split on

# Sin solapamiento entre tiras
python3 pancalc-fconv.py retrato.jpg --overlap 0

# Decodificar
python3 pancalc-fconv.py imagen.g3p --decode
```

## Fotos verticales (retrato)

El script detecta automáticamente las fotos verticales y las divide en varias tiras de 384×192 px, numeradas secuencialmente:

```
foto_001.g3p   ← tira 1 (arriba)
foto_002.g3p   ← tira 2 (sigue con solapamiento)
foto_003.g3p   ← tira 3
```

Cada tira incluye un **solapamiento** de 16 px con la anterior para mantener continuidad visual al pasar de una a otra. Ajustable con `--overlap`.

### Comportamiento por orientación

| Orientación | Modo auto | `--split on` | `--split off` |
|-------------|-----------|--------------|---------------|
| **Vertical** (retrato) | Divide en tiras | Divide en tiras | Letterbox centrado |
| **Horizontal** (paisaje) | Letterbox centrado | Divide en tiras | Letterbox centrado |
| **Cuadrada** | Letterbox centrado | Divide en tiras | Letterbox centrado |

### Corrección EXIF

Fotos tomadas con celular en modo retrato se orientan automáticamente usando los metadatos EXIF.

## Cómo pasar las imágenes a la calculadora

1. Conecta la CG50 por USB y presiona **F1** (USB Flash)
2. Copia los `.g3p` a la raíz o a cualquier carpeta
3. Desconecta de forma segura
4. Abre **Picture Plot** → **File** → **Open** → selecciona el archivo
5. Para las tiras numeradas, ábrelas una por una o navegá entre archivos desde el menú

También puedes usar las imágenes desde programas BASIC con `Pict 1` o como fondo en las apps de gráficos.

## Formato

- Resolución: **384 × 192 px** (se redimensiona automáticamente preservando aspect ratio)
- Color 16-bit: RGB565 (65 536 colores)
- Color 3-bit: 8 colores (paleta Casio BASIC: negro, azul, rojo, magenta, verde, cian, amarillo, blanco)
- Compresión: DEFLATE + ofuscación de bits
- Checksum: Adler32
- Variante: **CP** (Casio Provided), sin footer adicional

## Documentación técnica

Ver [`docs.md`](docs.md) para especificaciones detalladas del formato `.g3p` y estructura interna del archivo.

## Referencias

- [Cemetech — Reverse-engineering the .g3p format](https://www.cemetech.net/forum/viewtopic.php?t=10560)
- [Cahute — Documentación de formatos Casio](https://cahuteproject.org/)
