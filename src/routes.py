"""
Rutas realistas entre lugares — camino de MÍNIMO COSTE sobre el DEM.

En vez de líneas rectas, cada tramo sigue el terreno como lo harían los caminos
antiguos: baja por los valles, rodea las montañas y evita el agua. El coste de
cada celda usa la FUNCIÓN DE MARCHA DE TOBLER (velocidad de caminata según la
pendiente); se minimiza el tiempo total con skimage.route_through_array (MCP).

Salida:
  web/routes.js            -> window.ROUTES = [{a,b,pts:[[x%,y%],...]}, ...]
  preview/routes_preview.png (verificación sobre el mapa anotado)
"""
import os, json
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation, distance_transform_edt
from skimage.graph import route_through_array
from common import (W, H, INPUT, PREVIEW, DERIVED, PX_X_M, PX_Y_M,
                    load_dem_grid, to_px)
from places import PLACES

F = 4                                  # factor de reducción para el pathfinding
SW, SH = W // F, H // F                # grid reducido

# --- 1) DEM + agua en grid reducido ---
elev, valid = load_dem_grid()
elev_s = np.asarray(Image.fromarray(elev.astype(np.float32), "F")
                    .resize((SW, SH), Image.BILINEAR), np.float32)
wm = np.load(os.path.join(DERIVED, "water_masks.npz"))
water = wm["med"] | wm["galilee"] | wm["dead"]
water_s = np.asarray(Image.fromarray(water.astype(np.uint8) * 255)
                     .resize((SW, SH), Image.NEAREST)) > 127
water_s = binary_dilation(water_s, iterations=1)   # pequeño margen de costa

# --- 2) pendiente (grados) en el grid reducido ---
pxm = PX_X_M * F
pym = PX_Y_M * F
z = np.nan_to_num(elev_s, nan=float(np.nanmedian(elev_s)))
z = gaussian_filter(z, 1.0)
dzdy, dzdx = np.gradient(z, pym, pxm)
slope_tan = np.hypot(dzdx, dzdy)                   # pendiente como tangente (m/m)

# --- 3) coste = tiempo por celda (Tobler) ; agua = impasable ---
# Tobler: v = 6 * exp(-3.5 * |S + 0.05|)  km/h   (S = pendiente, dh/dx)
speed = 6.0 * np.exp(-3.5 * np.abs(slope_tan + 0.05))
speed = np.clip(speed, 0.12, 6.0)
cost = 1.0 / speed                                 # h/km ~ tiempo por distancia
cost += 0.15 * (np.clip(z, 0, None) / 800.0)       # leve preferencia por tierras bajas
cost[water_s] = 5000.0                             # el agua no se cruza

# --- 4) endpoints = posición de los marcadores (igual que data.js) ---
def marker_px(lng, lat, vdx, vdy):
    x, y = to_px(lng, lat)
    return x + vdx, y + vdy

def to_small(x, y):
    return int(round(np.clip(y / F, 0, SH - 1))), int(round(np.clip(x / F, 0, SW - 1)))

def snap_walkable(rc):
    r, c = rc
    if not water_s[r, c]:
        return rc
    # celda transitable más cercana
    free = ~water_s
    D, (ir, ic) = distance_transform_edt(~free, return_indices=True)  # dist a free? no
    # más simple: busca en anillos crecientes
    for rad in range(1, 60):
        r0, r1 = max(0, r - rad), min(SH, r + rad + 1)
        c0, c1 = max(0, c - rad), min(SW, c + rad + 1)
        sub = ~water_s[r0:r1, c0:c1]
        if sub.any():
            ys, xs = np.nonzero(sub)
            j = np.argmin((ys + r0 - r) ** 2 + (xs + c0 - c) ** 2)
            return (ys[j] + r0, xs[j] + c0)
    return rc

pts_small = []
for name, lng, lat, kind, scale, (dx, dy), anchor, (vdx, vdy) in PLACES:
    x, y = marker_px(lng, lat, vdx, vdy)
    pts_small.append(snap_walkable(to_small(x, y)))

names = [p[0].replace("\n", " ") for p in PLACES]

# --- 5) rutas por tramos consecutivos (orden narrativo por 'n' = el de PLACES web) ---
# usamos el mismo orden narrativo de la web: Belén,Nazaret,Jordán,Cafarnaúm,Jericó,Jerusalén
ORDER = ["Belén", "Nazaret", "Río Jordán (Bautismo)", "Cafarnaúm", "Jericó", "Jerusalén"]
idx = {names[i]: i for i in range(len(names))}
seq = [idx[n] for n in ORDER]

def smooth_decimate(path_rc):
    # path_rc: array (N,2) en (row,col) del grid reducido -> % del lienzo, suavizado
    rc = np.asarray(path_rc, np.float32)
    xs = rc[:, 1] * F / W * 100.0
    ys = rc[:, 0] * F / H * 100.0
    if len(xs) > 5:
        xs = gaussian_filter(xs, 2.5)
        ys = gaussian_filter(ys, 2.5)
    # decimar a ~cada 6 celdas para archivo ligero
    step = max(1, len(xs) // 90)
    xs = np.r_[xs[::step], xs[-1]]
    ys = np.r_[ys[::step], ys[-1]]
    return [[round(float(a), 3), round(float(b), 3)] for a, b in zip(xs, ys)]

routes = []
for a, b in zip(seq, seq[1:]):
    path, c = route_through_array(cost, pts_small[a], pts_small[b],
                                  fully_connected=True, geometric=True)
    routes.append({"a": names[a], "b": names[b], "pts": smooth_decimate(path)})
    print(f"  {names[a]:>22} -> {names[b]:<12} coste={c:8.1f} puntos={len(path)}")

with open(os.path.join(os.path.dirname(PREVIEW), "web", "routes.js"), "w", encoding="utf-8") as f:
    f.write("window.ROUTES = " + json.dumps(routes, ensure_ascii=False) + ";\n")

# --- 6) preview de verificación sobre el mapa anotado ---
base = Image.open(os.path.join(PREVIEW, "annotated_preview_full.png")).convert("RGB")
from PIL import ImageDraw
dr = ImageDraw.Draw(base)
for rt in routes:
    poly = [(x / 100 * W, y / 100 * H) for x, y in rt["pts"]]
    for i in range(len(poly) - 1):
        dr.line([poly[i], poly[i + 1]], fill=(184, 146, 58), width=6)
base.resize((W // 2, H // 2), Image.LANCZOS).save(os.path.join(PREVIEW, "routes_preview.png"))
print("OK -> web/routes.js +", len(routes), "tramos · preview/routes_preview.png")
