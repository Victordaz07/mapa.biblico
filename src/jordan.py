"""
Río Jordán iteración 2 — spline suave estilo grabado antiguo.
Usa la centerline x(y) recuperada de la iteración 1 (input/derived/water_masks.npz),
la suaviza a un trazo elegante y la rasteriza como línea navy de ~4px con borde
dorado de ~1px. Sólo se dibuja sobre tierra: los tramos que caen dentro de los
cuerpos de agua (Galilea, Mar Muerto) quedan ocultos, de modo que el río conecta
de orilla a orilla — afluente norte (alto Jordán) y tramo Galilea -> Mar Muerto.
Preview: agua + río sobre pergamino.
"""
import os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, gaussian_filter1d, distance_transform_edt
from common import (W, H, DERIVED, PREVIEW, NAVY, GOLD, parchment, save_png)

d = np.load(os.path.join(DERIVED, "water_masks.npz"))
MED, GAL, DEAD = d["med"], d["galilee"], d["dead"]
CL = d["centerline"].astype(np.float64)          # (N,2) -> (x,y), una fila por y

# ---- 1) centerline como función x(y) suavizada ----
y0, y1 = int(CL[:, 1].min()), int(CL[:, 1].max())
xline = np.full(H, np.nan)
xline[CL[:, 1].astype(int)] = CL[:, 0]
yy = np.arange(H)
valid = ~np.isnan(xline)
xline[y0:y1 + 1] = np.interp(yy[y0:y1 + 1], yy[valid], xline[valid])
# suavizado: quita el aliasing de 1px del trazo original y da meandro elegante
xs_s = gaussian_filter1d(xline[y0:y1 + 1], sigma=9.0)

# ---- 2) máscara fina de la centerline (subpíxel -> AA por distance transform) ----
seed = np.zeros((H, W), bool)
ys = np.arange(y0, y1 + 1)
xi = np.clip(np.round(xs_s).astype(int), 0, W - 1)
seed[ys, xi] = True
# densifica en diagonales (evita huecos donde x salta >1px entre filas)
xi_prev = np.r_[xi[0], xi[:-1]]
for lo, hi, yr in zip(np.minimum(xi, xi_prev), np.maximum(xi, xi_prev), ys):
    if hi - lo > 0:
        seed[yr, lo:hi + 1] = True

Dcl = distance_transform_edt(~seed).astype(np.float32)

# ---- 3) trazo navy + borde dorado (con leve taper norte->sur) ----
# radio del núcleo: ~1.6px arriba (afluente delgado) -> ~2.2px al desembocar
taper = np.interp(yy, [y0, y1], [1.6, 2.2]).astype(np.float32)
core_r = np.zeros((H, W), np.float32)
core_r[:] = taper[:, None]
gold_r = core_r + 1.0                                  # borde dorado ~1px

navy_a = np.clip(core_r + 0.5 - Dcl, 0.0, 1.0)         # AA de ~1px en el borde
gold_a = np.clip(gold_r + 0.5 - Dcl, 0.0, 1.0)         # incluye núcleo; se pisa con navy

# sólo sobre tierra: oculta los tramos que cruzan los cuerpos de agua
water = MED | GAL | DEAD
land = ~water
navy_a *= land
gold_a *= land

# ---- 4) componer preview: pergamino -> agua -> río ----
img = parchment().astype(np.float32)

# agua (reusa la capa del mar si existe; si no, relleno navy simple)
sea_path = os.path.join(DERIVED, "sea_layer.npz")
if os.path.exists(sea_path):
    s = np.load(sea_path)
    fill, sgold = s["fill"], s["gold"].astype(np.float32)
    img[fill] = np.array(NAVY, np.float32)
    ga = sgold[..., None]
    img = img * (1 - ga) + np.array(GOLD, np.float32) * ga
else:
    img[water] = np.array(NAVY, np.float32)

# río: primero el borde dorado (más ancho), luego el núcleo navy encima
ga = gold_a[..., None]
img = img * (1 - ga) + np.array(GOLD, np.float32) * ga
na = navy_a[..., None]
img = img * (1 - na) + np.array(NAVY, np.float32) * na
img = np.clip(img, 0, 255).astype(np.uint8)

# ---- 5) guardar capa para compose + previews ----
np.savez_compressed(os.path.join(DERIVED, "jordan_layer.npz"),
                    navy=navy_a.astype(np.float32), gold=gold_a.astype(np.float32))

save_png(img, os.path.join(PREVIEW, "jordan_preview_full.png"))
Image.fromarray(img).resize((W // 2, H // 2), Image.LANCZOS).save(os.path.join(PREVIEW, "jordan_preview.png"))
Image.fromarray(img).resize((W // 5, H // 5), Image.LANCZOS).save(os.path.join(PREVIEW, "jordan_thumb.png"))
print("OK -> preview/jordan_preview.png (+ thumb). navy/gold alpha del Jordán listos.")
