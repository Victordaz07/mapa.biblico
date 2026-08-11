"""
Recupera la geometría EXACTA de la iteración 1 desde input/iter1_master.png (2000x2600):
  - máscaras de agua: Mediterráneo, Mar de Galilea, Mar Muerto (unificado)
  - polilínea del río Jordán
Guarda en input/derived/.  No re-descarga datasets: preserva la geografía perfecta.
"""
import os, json
import numpy as np
from PIL import Image
from scipy.ndimage import (binary_fill_holes, label, binary_closing,
                           binary_dilation, binary_erosion, binary_opening)
from common import INPUT, DERIVED, W, H, save_png

img = np.asarray(Image.open(os.path.join(INPUT, "iter1_master.png")).convert("RGB")).astype(np.int16)
R, G, B = img[..., 0], img[..., 1], img[..., 2]

# --- 1) máscara de "tinta oscura" (navy fill + trazos negros del río) ---
dark = (R < 70) & (G < 85) & (B < 110) & (B >= R)  # navy y negro; B>=R descarta pardos del hachurado
# el relleno de agua es navy sólido; rellenamos los anillos dorados internos
water_solid = binary_fill_holes(dark)

# --- 2) separar cuerpos de agua (blobs grandes) del trazo fino del río ---
# abrir para eliminar líneas delgadas (<~3px)
blobs = binary_opening(water_solid, iterations=3)
blobs = binary_fill_holes(blobs)
lab, n = label(blobs)
sizes = np.bincount(lab.ravel()); sizes[0] = 0
print("componentes agua:", n, "tamaños top:", sorted(sizes.tolist(), reverse=True)[:8])

# Mediterráneo = componente grande que toca el borde izquierdo/superior
med = np.zeros((H, W), bool)
lakes = []
for i in range(1, n+1):
    if sizes[i] < 400:
        continue
    comp = lab == i
    touches_edge = comp[:, 0].any() or comp[0, :].any() or comp[-1, :].any()
    cx = np.flatnonzero(comp.any(0)).mean()
    if touches_edge and cx < W*0.45:
        med |= comp
    else:
        ys = np.flatnonzero(comp.any(1)); xs = np.flatnonzero(comp.any(0))
        lakes.append((i, sizes[i], ys.mean(), xs.mean(), comp))

# ordenar lagos por latitud (y): Galilea arriba (y menor), Mar Muerto abajo
lakes.sort(key=lambda t: t[2])
print("lagos detectados (id,size,ymean,xmean):", [(l[0], int(l[1]), int(l[2]), int(l[3])) for l in lakes])

# Galilea = lago más al norte de tamaño medio; Mar Muerto = piezas al sur
galilee = lakes[0][4].copy()
dead_pieces = [l[4] for l in lakes[1:]]

# --- 3) Mar Muerto: unir 2-3 piezas en una sola silueta continua ---
dead = np.zeros((H, W), bool)
for p in dead_pieces:
    dead |= p
# puente explícito: unir el tramo inferior del cuerpo norte con el superior del basin sur
# por sus centroides de columna, para garantizar continuidad aunque el hueco sea grande.
ys_all = np.flatnonzero(dead.any(1))
bridge = np.zeros((H, W), bool)
for y in range(ys_all.min(), ys_all.max()+1):
    xs = np.flatnonzero(dead[y])
    if xs.size:
        bridge[y, xs.min():xs.max()+1] = True  # rellena el interior por fila
# donde una fila NO tiene agua (el hueco), interpola el rango x entre la fila válida
# anterior y siguiente para tender el istmo
rows_with = {int(y): (int(np.flatnonzero(dead[y]).min()), int(np.flatnonzero(dead[y]).max()))
             for y in ys_all}
present = sorted(rows_with)
for a, b in zip(present, present[1:]):
    if b - a > 1:  # hueco vertical entre lóbulos
        (la, ra), (lb, rb) = rows_with[a], rows_with[b]
        for k, y in enumerate(range(a+1, b)):
            t = (k+1)/(b-a)
            l = int(round(la*(1-t)+lb*t)); r = int(round(ra*(1-t)+rb*t))
            cx = (l+r)//2
            bridge[y, cx-max(6,(r-l)//4): cx+max(6,(r-l)//4)+1] = True  # istmo estrecho
dead_union = bridge | dead
dead_union = binary_closing(dead_union, iterations=10)
dead_union = binary_fill_holes(dead_union)
dead_union = binary_opening(dead_union, iterations=2)   # suaviza dientes del cierre
dead_union = binary_fill_holes(dead_union)
# simplificado suave: redondea el contorno sin encoger los lóbulos
from scipy.ndimage import gaussian_filter as _gf
dead_union = _gf(dead_union.astype(np.float32), 3.5) > 0.5
dead_union = binary_fill_holes(dead_union)
dlab, dn = label(dead_union)
print("Mar Muerto: piezas=", len(dead_pieces), "componentes tras union=", dn, "area=", int(dead_union.sum()))

# limpieza suave de Galilea (rellenar, quitar dientes)
galilee = binary_fill_holes(binary_closing(galilee, iterations=3))

# --- 4) Río Jordán: trazo fino = dark menos los cuerpos de agua ---
# NO abrir (destruiría la línea de 1px). Sólo quitar los cuerpos de agua dilatados.
allwater = med | galilee | dead_union | binary_dilation(blobs, iterations=2)
river_px = dark & ~binary_dilation(allwater, iterations=3)
# El Jordán es una función x(y) en el corredor central. Tomamos TODAS las
# componentes-trazo dentro del corredor (afluente norte + tramo Galilea→Mar Muerto)
# y las unimos; luego construimos la centerline continua interpolando los huecos
# (incluido el cruce por Galilea).
rl, rn = label(binary_dilation(river_px, iterations=2))
river_main = np.zeros((H, W), bool)
for i in range(1, rn+1):
    comp = rl == i
    ys = np.flatnonzero(comp.any(1)); xs = np.flatnonzero(comp.any(0))
    span = ys.max()-ys.min() if ys.size else 0
    cx = xs.mean() if xs.size else 0
    if span > 60 and 820 < cx < 1220:          # corredor del valle del rift
        river_main |= comp & binary_dilation(river_px, iterations=2)
best_span = int(np.ptp(np.flatnonzero(river_main.any(1))))

# centerline x(y): media de columnas del trazo por fila, para todo el rango vertical.
ys_r = np.flatnonzero(river_main.any(1))
y0, y1 = int(ys_r.min()), int(ys_r.max())
xs_by_y = np.full(H, np.nan)
for y in range(y0, y1+1):
    xs = np.flatnonzero(river_main[y])
    if xs.size:
        xs_by_y[y] = xs.mean()
# interpolar los huecos (p.ej. donde el trazo cruza junto a Galilea)
yy = np.arange(H)
valid = ~np.isnan(xs_by_y)
xs_by_y[y0:y1+1] = np.interp(yy[y0:y1+1], yy[valid], xs_by_y[valid])
centerline = np.stack([xs_by_y[y0:y1+1], yy[y0:y1+1]], axis=1)  # (x,y)
print("Jordán: componentes=", rn, "span vertical px=", best_span, "puntos centerline=", len(centerline))

# --- guardar máscaras + centerline ---
np.savez_compressed(os.path.join(DERIVED, "water_masks.npz"),
                    med=med, galilee=galilee, dead=dead_union,
                    river=river_main, centerline=centerline)

# debug visual
dbg = np.zeros((H, W, 3), np.uint8)
dbg[med] = (60, 90, 160)
dbg[galilee] = (40, 200, 120)
dbg[dead_union] = (220, 120, 40)
cl = np.round(centerline).astype(int)
for x, y in cl:
    if 0 <= x < W and 0 <= y < H:
        dbg[max(0,y-1):y+2, max(0,x-1):x+2] = (255, 255, 0)
save_png(dbg, os.path.join(DERIVED, "debug_masks.png"))
print("OK -> derived/water_masks.npz + debug_masks.png")
