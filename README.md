# Mapa base — Tierra Santa (estilo grabado antiguo)

Mapa base cartográfico de Tierra Santa renderizado con estética de **grabado
antiguo sobre pergamino** (relieve por hachurado, agua con oleaje grabado).
Pensado como capa base para superponer rutas/lugares bíblicos.

## Calibración (INMUTABLE)
`input/calibracion.json` define el marco geográfico y **no debe cambiarse**:

| campo | valor |
|-------|-------|
| bbox (W,S,E,N) | `34.5, 30.8, 36.6, 33.7` |
| dimensiones | `2000 × 2600` px |
| proyección | lineal (equirectangular directa) |

Conversión lng/lat → px:
```
x = (lng - 34.5) / (36.6 - 34.5) * 2000
y = (1 - (lat - 30.8) / (33.7 - 30.8)) * 2600
```

## Estado — Iteración 2 (en curso)
Rehacer el tratamiento **visual** conservando geometría y calibración perfectas
de la iteración 1.

- [x] Relieve: hillshade multidireccional (tonal 17%) + hachurado por rango de
      pendiente (<3° nada · 3-10° escaso · 10-20° medio · >20° denso), trazos
      cuesta abajo estilo grabado. → `preview/relief_preview.png`
- [x] Mar/lagos: navy sólido `#0D1B2A` + oleaje horizontal ondulado
      `#B8923A`; Mar Muerto unificado en un solo cuerpo. → `preview/sea_preview.png`
- [x] Río Jordán: spline suave de la centerline (iter1), trazo navy ~4px con
      leve taper + borde dorado ~1px; sólo sobre tierra (afluente norte +
      tramo Galilea→Mar Muerto). → `preview/jordan_preview.png`
- [ ] Composición final + export PNG master / WebP <600KB / calibracion.json.

## Geometría
La geografía de la iteración 1 (costa, lagos, Jordán) se **preserva exactamente**
recuperándola del master anterior (`input/iter1_master.png`) en vez de
re-descargar datasets modernos que romperían la calibración. Ver
`src/recover_geometry.py`. El Mar Muerto (partido en 2-3 piezas en los datos
modernos) se fusiona en una sola silueta continua.

## Datos de entrada
- `input/dem_SRTMGL1.tif` — DEM SRTM 1 arc-sec (EPSG:4326), bounds = bbox.
- `input/iter1_master.png` — master de la iteración 1 (fuente de geometría).
- `input/calibracion.json` — calibración (no tocar).

## Uso
```bash
pip install -r requirements.txt
cd src
python recover_geometry.py   # -> input/derived/water_masks.npz (+ debug)
python relief.py             # -> preview/relief_preview.png (+ thumb)
python sea.py                # -> preview/sea_preview.png + derived/sea_layer.npz
python jordan.py             # -> preview/jordan_preview.png + derived/jordan_layer.npz
# (pendiente) python compose.py
```

## Paleta
- Navy agua/tinta: `#0D1B2A`
- Dorado (oleaje, contornos, bordes): `#B8923A`
- Pergamino: crema cálido
- Hachurado relieve: sepia oscuro `#4A3A22`
