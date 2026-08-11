"""
Relieve iteración 2 — desde el DEM (misma bbox/dims que la calibración).
Dos capas:
  A) tonal: hillshade multidireccional multiplicado sobre el pergamino (op 12-18%)
  B) hachurado: trazos por rango de pendiente, longitud/opacidad/densidad crecientes,
     orientados perpendiculares al aspect (siguen la curva de nivel).
Guarda capas en input/derived/ y un preview en preview/.
"""
import os, math
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from common import (W, H, DERIVED, PREVIEW, load_dem_grid, slope_aspect,
                    multi_hillshade, parchment, save_png)

INK = (74, 58, 34)      # sepia oscuro para los trazos (contraste sobre pergamino)

print("cargando DEM…")
elev, valid = load_dem_grid()
slope, aspect, nanmask = slope_aspect(elev)

# máscara de agua (para no dibujar relieve sobre el agua)
d = np.load(os.path.join(DERIVED, "water_masks.npz"))
water = d["med"] | d["galilee"] | d["dead"]
land = valid & ~water

# ---------------- A) capa tonal hillshade ----------------
print("hillshade multidireccional…")
hs = multi_hillshade(elev, z_factor=1.7)
# realce de contraste centrado en la media (más marcado para sobrevivir al thumbnail)
hs = np.clip((hs - hs[land].mean()) * 2.2 + 0.5, 0, 1)
# refuerzo de macizos: componente tonal de baja frecuencia (relieve grande)
big = gaussian_filter(np.where(land, hs, hs.mean()), 6)
hs = np.clip(0.7*hs + 0.3*big, 0, 1)
hs = gaussian_filter(hs, 0.6)
np.save(os.path.join(DERIVED, "hillshade.npy"), hs.astype(np.float32))

# ---------------- B) hachurado por bandas de pendiente ----------------
# banda: (slope_min, slope_max, keep_prob, len_min, len_max, opacidad)
BANDS = [
    (3.0,  10.0, 0.14,  8, 11, 0.30),
    (10.0, 20.0, 0.42, 11, 15, 0.50),
    (20.0, 90.0, 0.85, 15, 20, 0.78),
]
SS = 2                       # supersampling para antialiasing
spacing = 5                  # paso de la rejilla de semillas (px @1x)
rng = np.random.default_rng(42)

# semillas jitteradas
gx = np.arange(spacing//2, W, spacing)
gy = np.arange(spacing//2, H, spacing)
GX, GY = np.meshgrid(gx, gy)
sx = (GX + rng.uniform(-spacing/2, spacing/2, GX.shape)).ravel()
sy = (GY + rng.uniform(-spacing/2, spacing/2, GY.shape)).ravel()
ix = np.clip(sx.astype(int), 0, W-1); iy = np.clip(sy.astype(int), 0, H-1)

s_at = slope[iy, ix]
a_at = aspect[iy, ix]
land_at = land[iy, ix]
u = rng.random(sx.shape)                      # para keep-prob
jit_ang = rng.uniform(-0.10, 0.10, sx.shape)  # jitter de ángulo (bajo = trazo peinado, limpio)
jit_len = rng.uniform(0.85, 1.15, sx.shape)

# Orientación del hachurado:
#   'downslope' = paralelo al aspect (cuesta abajo, grabado clásico Lehmann) -> montañas legibles
#   'contour'   = perpendicular al aspect (sigue la curva de nivel) [spec literal]
HACHURE_MODE = "downslope"
_perp = (math.pi/2) if HACHURE_MODE == "contour" else 0.0

alpha_layers = []
for (smin, smax, keep, lmin, lmax, op) in BANDS:
    sel = land_at & (s_at >= smin) & (s_at < smax) & (u < keep)
    # longitud escalada dentro de la banda según pendiente
    frac = np.clip((s_at[sel] - smin) / max(1e-3, (smax - smin)), 0, 1)
    length = (lmin + frac * (lmax - lmin)) * jit_len[sel]
    ang = a_at[sel] + _perp + jit_ang[sel]         # orientación según HACHURE_MODE
    dx = np.cos(ang) * length / 2.0
    dy = np.sin(ang) * length / 2.0
    x0 = (sx[sel]-dx)*SS; y0 = (sy[sel]-dy)*SS
    x1 = (sx[sel]+dx)*SS; y1 = (sy[sel]+dy)*SS
    layer = Image.new("L", (W*SS, H*SS), 0)
    dr = ImageDraw.Draw(layer)
    for a0, b0, a1, b1 in zip(x0.tolist(), y0.tolist(), x1.tolist(), y1.tolist()):
        dr.line((a0, b0, a1, b1), fill=255, width=SS)
    small = layer.resize((W, H), Image.LANCZOS)
    cov = np.asarray(small, np.float32) / 255.0
    alpha_layers.append(cov * op)
    print(f"  banda {smin:>4}-{smax:<4}: {int(sel.sum()):>6} trazos, op {op}")

# combinar bandas (over sucesivo) en una sola alpha de tinta
ink_alpha = np.zeros((H, W), np.float32)
for cov in alpha_layers:
    ink_alpha = ink_alpha + cov * (1 - ink_alpha)
ink_alpha[~land] = 0.0
np.save(os.path.join(DERIVED, "hachure_alpha.npy"), ink_alpha.astype(np.float32))

# ---------------- preview (pergamino + tonal + hachurado) ----------------
print("componiendo preview de relieve…")
img = parchment().astype(np.float32)
# tonal hillshade: multiply a opacidad 0.17 (sólo tierra)
a_t = 0.17
mult = (1 - a_t) + a_t * hs[..., None]
tonal = img * mult
img = np.where(land[..., None], tonal, img)
# hachurado sepia
img = img*(1 - ink_alpha[..., None]) + np.array(INK, np.float32)*ink_alpha[..., None]
img = np.clip(img, 0, 255).astype(np.uint8)

save_png(img, os.path.join(PREVIEW, "relief_preview_full.png"))
Image.fromarray(img).resize((W//2, H//2), Image.LANCZOS).save(os.path.join(PREVIEW, "relief_preview.png"))
# thumbnail para test de legibilidad "a simple vista"
Image.fromarray(img).resize((W//5, H//5), Image.LANCZOS).save(os.path.join(PREVIEW, "relief_thumb.png"))
print("OK -> preview/relief_preview.png (+ thumb)")
