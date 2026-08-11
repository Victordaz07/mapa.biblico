"""
Composición final — mapa base Tierra Santa (iteración 2).
Apila, en orden, las capas ya generadas por los scripts previos:

  1. pergamino (fondo cálido con grano)
  2. relieve   -> tonal hillshade (multiply, sólo tierra) + hachurado sepia
                  (derived/hillshade.npy, hachure_alpha.npy, land_mask.npy)
  3. agua      -> relleno navy sólido + oleaje dorado
                  (derived/water_masks.npz + sea_layer.npz)
  4. río Jordán-> trazo navy + borde dorado, sólo sobre tierra
                  (derived/jordan_layer.npz)

Exporta:
  output/mapa_base.png   — master a resolución nativa 2000x2600
  output/mapa_base.webp  — versión web (<600KB, calidad ajustada automáticamente)
  output/calibracion.json— copia de la calibración (marco geográfico inmutable)
  preview/final_preview.png / final_thumb.png
"""
import os, json, shutil
import numpy as np
from PIL import Image
from common import (W, H, INPUT, OUTPUT, DERIVED, PREVIEW, NAVY, GOLD,
                    parchment, save_png)

INK = (74, 58, 34)   # sepia del hachurado (igual que relief.py)

# ---- cargar todas las capas derivadas ----
hs = np.load(os.path.join(DERIVED, "hillshade.npy"))
ink = np.load(os.path.join(DERIVED, "hachure_alpha.npy"))
land = np.load(os.path.join(DERIVED, "land_mask.npy"))

wm = np.load(os.path.join(DERIVED, "water_masks.npz"))
water = wm["med"] | wm["galilee"] | wm["dead"]

sea = np.load(os.path.join(DERIVED, "sea_layer.npz"))
sea_gold = sea["gold"].astype(np.float32)          # oleaje/contornos dorados

jr = np.load(os.path.join(DERIVED, "jordan_layer.npz"))
river_navy = jr["navy"].astype(np.float32)
river_gold = jr["gold"].astype(np.float32)

navy = np.array(NAVY, np.float32)
gold = np.array(GOLD, np.float32)

# ============ 1) pergamino ============
img = parchment().astype(np.float32)

# ============ 2) relieve ============
# tonal hillshade: multiply a 17% sólo sobre tierra (idéntico a relief.py)
a_t = 0.17
mult = (1 - a_t) + a_t * hs[..., None]
img = np.where(land[..., None], img * mult, img)
# hachurado sepia
img = img * (1 - ink[..., None]) + np.array(INK, np.float32) * ink[..., None]

# ============ 3) agua ============
img[water] = navy                                  # relleno navy sólido
ga = sea_gold[..., None]                           # oleaje dorado sobre el agua
img = img * (1 - ga) + gold * ga

# ============ 4) río Jordán ============
rg = river_gold[..., None]                          # borde dorado (más ancho)
img = img * (1 - rg) + gold * rg
rn = river_navy[..., None]                           # núcleo navy encima
img = img * (1 - rn) + navy * rn

master = np.clip(img, 0, 255).astype(np.uint8)

# ============ export ============
os.makedirs(OUTPUT, exist_ok=True)
png_path = os.path.join(OUTPUT, "mapa_base.png")
save_png(master, png_path)

# WebP web <600KB: baja la calidad hasta cumplir el presupuesto
im = Image.fromarray(master, "RGB")
webp_path = os.path.join(OUTPUT, "mapa_base.webp")
budget = 600 * 1024
q = 92
while True:
    im.save(webp_path, "WEBP", quality=q, method=6)
    size = os.path.getsize(webp_path)
    if size <= budget or q <= 40:
        break
    q -= 6
print(f"WebP: quality={q}, {size/1024:.0f} KB (<=600KB: {size <= budget})")

# calibración junto al master (marco geográfico inmutable)
with open(os.path.join(INPUT, "calibracion.json"), "r", encoding="utf-8") as f:
    cal = json.load(f)
with open(os.path.join(OUTPUT, "calibracion.json"), "w", encoding="utf-8") as f:
    json.dump(cal, f, ensure_ascii=False, indent=2)

# previews
save_png(master, os.path.join(PREVIEW, "final_preview_full.png"))
im.resize((W // 2, H // 2), Image.LANCZOS).save(os.path.join(PREVIEW, "final_preview.png"))
im.resize((W // 5, H // 5), Image.LANCZOS).save(os.path.join(PREVIEW, "final_thumb.png"))

print(f"OK -> output/mapa_base.png ({os.path.getsize(png_path)/1024/1024:.1f} MB) "
      f"+ mapa_base.webp + calibracion.json")
