# pancalc-fconv.py

Convierte imágenes (JPEG, PNG, BMP, GIF, etc.) al formato `.g3p` nativo de las calculadoras **Casio fx-CG10/20/50** y **Graph 90+E**.

## Requisitos

```bash
pip install Pillow
```

## Uso

```bash
python3 pancalc-fconv.py imagen.jpg -o salida.g3p
```

Por defecto genera 16-bit (RGB565, 65536 colores). Para 3-bit (8 colores indexados, archivos ~5× más pequeños):

```bash
python3 pancalc-fconv.py imagen.png -o salida.g3p -b 3
```

Si no se especifica `-o`, el nombre de salida es el mismo que el de entrada con extensión `.g3p`:

```bash
python3 pancalc-fconv.py foto.jpg
# → foto.g3p
```

## Cómo pasar las imágenes a la calculadora

1. Conecta la CG50 por USB y presiona **F1** (USB Flash)
2. Copia el `.g3p` a la raíz o a cualquier carpeta de la calculadora
3. Desconecta de forma segura
4. Abre **Picture Plot** → **File** → **Open** → selecciona el archivo

También puedes usar las imágenes desde programas BASIC con `Pict 1` o como fondo en las apps de gráficos.

## Formato

- Resolución: **384 × 192 px** (se redimensiona automáticamente)
- Color 16-bit: RGB565 (65 536 colores)
- Color 3-bit: 8 colores (paleta Casio BASIC: negro, azul, rojo, magenta, verde, cian, amarillo, blanco)
- Compresión: DEFLATE + ofuscación de bits
- Checksum: Adler32

## Especificaciones técnicas

El script genera el formato **CP** (Casio Provided), variante del `.g3p` sin footer adicional. Compatible con todos los modelos fx-CG y Graph 90+E desde OS 2.02 en adelante.

Referencia: [Cemetech — Reverse-engineering the .g3p format](https://www.cemetech.net/forum/viewtopic.php?t=10560)
