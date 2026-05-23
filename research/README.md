# research/ — Converter research & documentation

## Estado

El código del conversor se movió a [`pcalc/converter.py`](../pcalc/converter.py) e integrado al CLI `pcalc convert`.

**`pancalc-fconv.py`** se mantiene aquí como referencia standalone, pero todo el desarrollo activo está en `pcalc/converter.py`.

## Documentación técnica

Ver [`docs.md`](docs.md) para especificaciones del formato `.g3p`.

## Uso (CLI integrado)

```bash
# Desde la raíz del proyecto
pip install -e .
pcalc convert foto.jpg
pcalc convert --decode imagen.g3p
```

## Referencias

- [Cemetech — Reverse-engineering the .g3p format](https://www.cemetech.net/forum/viewtopic.php?t=10560)
- [Cahute — Documentación de formatos Casio](https://cahuteproject.org/)
