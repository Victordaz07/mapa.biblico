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
        xs = gaussian_filter(xs, 4.0)
        ys = gaussian_filter(ys, 4.0)
    # decimar a pocos puntos: la curva suave (Catmull-Rom) se hace en el cliente
    step = max(1, len(xs) // 55)
    xs = np.r_[xs[::step], xs[-1]]
    ys = np.r_[ys[::step], ys[-1]]
    return [[round(float(a), 3), round(float(b), 3)] for a, b in zip(xs, ys)]

routes = []
for a, b in zip(seq, seq[1:]):
    path, c = route_through_array(cost, pts_small[a], pts_small[b],
                                  fully_connected=True, geometric=True)
    routes.append({"a": names[a], "b": names[b], "pts": smooth_decimate(path)})
    print(f"  {names[a]:>22} -> {names[b]:<12} coste={c:8.1f} puntos={len(path)}")

# --- 5b) RUTAS HISTÓRICAS documentadas (Galilea <-> Jerusalén) ---------------
# Se trazan por sus corredores reales encadenando least-cost entre waypoints
# (ciudades intermedias o puntos del valle). Colores del mapa de referencia.
def chain(waypoints_lnglat):
    """Ruta continua que pasa por cada waypoint (lng,lat)."""
    nodes = [snap_walkable(to_small(*to_px(lng, lat))) for lng, lat in waypoints_lnglat]
    allrc = []
    for a, b in zip(nodes, nodes[1:]):
        path, _ = route_through_array(cost, a, b, fully_connected=True, geometric=True)
        allrc.extend(path if not allrc else path[1:])
    return smooth_decimate(np.asarray(allrc))

# Cada ruta: id, name, cat (galjer|camino|ministerio|pablo), color, style, waypoints(lng,lat)
ROUTESPEC = [
    # --- Galilea <-> Jerusalén (afinadas: pasan por las ciudades correctas) ---
    dict(id="samaria", name="Por Samaria", cat="galjer", color="#a23b2e", style="dash",
         wp=[(35.5753,32.8808),(35.2978,32.7021),(35.2833,32.2139),(35.2625,31.9917),(35.2354,31.7780)]),
    dict(id="perea", name="Por Perea", cat="galjer", color="#3f6b3a", style="dash",
         wp=[(35.5753,32.8808),(35.6817,32.6544),(35.6114,32.4522),(35.4440,31.8700),(35.2354,31.7780)]),
    # --- Calzadas romanas (red principal, línea sólida marrón) ---
    dict(id="viamaris", name="Vía Maris", cat="camino", color="#8a6a3a", style="solid",
         wp=[(34.7550,32.0522),(34.8917,32.5000),(35.1840,32.5850),(35.5320,32.7959),(35.5753,32.8808),(35.6300,32.9100),(36.2765,33.5138)]),
    dict(id="valle", name="Camino del valle", cat="camino", color="#8a6a3a", style="solid",
         wp=[(35.5320,32.7959),(35.5000,32.5036),(35.4440,31.8700),(35.2354,31.7780)]),
    dict(id="ridge", name="Camino de la cordillera", cat="camino", color="#8a6a3a", style="solid",
         wp=[(35.2354,31.7780),(35.2833,32.2139),(35.1892,32.2764),(35.1840,32.5850)]),
    dict(id="costajer", name="Camino Jope–Jerusalén", cat="camino", color="#8a6a3a", style="solid",
         wp=[(34.7550,32.0522),(34.8925,31.9514),(34.9892,31.8390),(35.2354,31.7780)]),
    dict(id="transjordan", name="Camino de Transjordania", cat="camino", color="#8a6a3a", style="solid",
         wp=[(36.2765,33.5138),(35.6817,32.6544),(35.6114,32.4522),(35.9330,31.9500)]),
    # --- Viajes del ministerio de Jesús (guion azulado) ---
    dict(id="galilea", name="Gira por Galilea", cat="ministerio", color="#2f6f8f", style="dash",
         wp=[(35.2978,32.7021),(35.3419,32.7480),(35.5753,32.8808),(35.6300,32.9100),(35.5647,32.9106),(35.5169,32.8267),(35.3714,32.6339),(35.2978,32.7021)]),
    dict(id="cesareafilipo", name="A Cesarea de Filipo", cat="ministerio", color="#2f6f8f", style="dash",
         wp=[(35.5753,32.8808),(35.6300,32.9100),(35.6928,33.2493)]),
    # --- Hechos / Pablo (guion naranja) ---
    dict(id="damasco", name="Camino a Damasco", cat="pablo", color="#b5642a", style="dash",
         wp=[(35.2354,31.7780),(35.4440,31.8700),(35.5000,32.5036),(35.6558,32.7897),(36.2765,33.5138)]),
    dict(id="pablocesarea", name="Pablo a Cesarea", cat="pablo", color="#b5642a", style="dash",
         wp=[(35.2354,31.7780),(34.9390,32.1040),(34.8917,32.5000)]),
]
hist = []
for r in ROUTESPEC:
    hist.append({"id": r["id"], "name": r["name"], "cat": r["cat"],
                 "color": r["color"], "style": r["style"], "pts": chain(r["wp"])})
    print(f"  {r['cat']:>10} · {r['name']:<26} puntos={len(hist[-1]['pts'])}")

with open(os.path.join(os.path.dirname(PREVIEW), "web", "routes.js"), "w", encoding="utf-8") as f:
    f.write("window.ROUTES = " + json.dumps(routes, ensure_ascii=False) + ";\n")
    f.write("window.HISTROUTES = " + json.dumps(hist, ensure_ascii=False) + ";\n")

# --- 6) preview de verificación sobre el mapa anotado ---
base = Image.open(os.path.join(PREVIEW, "annotated_preview_full.png")).convert("RGB")
from PIL import ImageDraw
dr = ImageDraw.Draw(base)
def draw_poly(pts, fill, width):
    poly = [(x / 100 * W, y / 100 * H) for x, y in pts]
    for i in range(len(poly) - 1):
        dr.line([poly[i], poly[i + 1]], fill=fill, width=width)
for rt in routes:
    draw_poly(rt["pts"], (184, 146, 58), 6)
for h in hist:
    c = tuple(int(h["color"][i:i+2], 16) for i in (1, 3, 5))
    draw_poly(h["pts"], c, 9)
base.resize((W // 2, H // 2), Image.LANCZOS).save(os.path.join(PREVIEW, "routes_preview.png"))
print("OK -> web/routes.js +", len(routes), "tramos +", len(hist), "rutas históricas")
