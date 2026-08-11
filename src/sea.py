"""
Agua iteración 2 — mar y lagos con estética de grabado antiguo.
Sin anillos concéntricos: relleno navy sólido + líneas de oleaje HORIZONTALES
onduladas (amplitud/fase aleatorizadas por línea). Cerca de la costa (40px) las
líneas siguen levemente la orilla y se difuminan rápido. Lagos con contorno dorado.
Preview: agua sola sobre pergamino.
"""
import os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt
from common import (W, H, DERIVED, PREVIEW, NAVY, GOLD, parchment, save_png)

d = np.load(os.path.join(DERIVED, "water_masks.npz"))
MED, GAL, DEAD = d["med"], d["galilee"], d["dead"]

Y = np.repeat(np.arange(H)[:, None], W, axis=1).astype(np.float32)


def wave_alpha(mask, spacing, amp, seed, op_lo, op_hi, coast_follow=False,
               coast_band=40.0, coast_spacing=9.0):
    """Alpha (H,W) de las líneas de oleaje doradas dentro de `mask`."""
    rng = np.random.default_rng(seed)
    # ruido suave, más correlacionado en X que en Y -> ondulaciones horizontales
    n0 = rng.standard_normal((H, W)).astype(np.float32)
    noise = gaussian_filter(n0, (2.2, 46.0))
    noise = noise / (noise.std() + 1e-6) * amp
    psi = Y + noise
    r = psi / spacing
    lid = np.round(r)
    distp = np.abs(r - lid) * spacing
    core = np.clip(1.0 - (distp - 0.5) / 0.5, 0.0, 1.0)   # línea ~1px con AA
    tbl = rng.uniform(op_lo, op_hi, 4096).astype(np.float32)
    op = tbl[np.mod(lid.astype(np.int64), 4096)]
    alpha_h = core * op

    if coast_follow:
        D = distance_transform_edt(mask).astype(np.float32)
        cf = np.clip((coast_band - D) / coast_band, 0.0, 1.0)  # 1 en costa -> 0 a 40px
        alpha_h = alpha_h * (1.0 - 0.75 * cf)                  # desvanece horizontales junto a la orilla
        rc = D / coast_spacing
        lidc = np.round(rc)
        distc = np.abs(rc - lidc) * coast_spacing
        corec = np.clip(1.0 - (distc - 0.5) / 0.5, 0.0, 1.0)   # iso-líneas paralelas a la costa
        opc = 0.22 * cf
        alpha_c = corec * opc
        alpha = alpha_h + alpha_c * (1.0 - alpha_h)
    else:
        alpha = alpha_h
    return (alpha * mask).astype(np.float32)


def gold_contour(mask, width_px=1.5, op=0.85):
    Dm = distance_transform_edt(mask).astype(np.float32)
    ring = (Dm > 0) & (Dm <= width_px)
    return (ring.astype(np.float32) * op)


def lake_spacing(mask, n_lines=3):
    ys = np.flatnonzero(mask.any(1))
    h = (ys.max() - ys.min()) if ys.size else 100
    return max(24.0, h / (n_lines + 0.5))


# ---- construir capa de agua sobre pergamino (preview del mar solo) ----
img = parchment().astype(np.float32)

# 1) relleno navy sólido
fill = MED | GAL | DEAD
img[fill] = np.array(NAVY, np.float32)

# 2) líneas de oleaje (dorado) por cuerpo
gold = np.zeros((H, W), np.float32)
gold = np.maximum(gold, wave_alpha(MED, spacing=11.0, amp=3.0, seed=11,
                                   op_lo=0.15, op_hi=0.25, coast_follow=True))
gold = np.maximum(gold, wave_alpha(GAL, spacing=lake_spacing(GAL), amp=2.2, seed=22,
                                   op_lo=0.16, op_hi=0.24))
gold = np.maximum(gold, wave_alpha(DEAD, spacing=lake_spacing(DEAD), amp=2.6, seed=33,
                                   op_lo=0.16, op_hi=0.24))

# 3) contorno dorado fino en lagos
gold = np.maximum(gold, gold_contour(GAL, 1.5, 0.85))
gold = np.maximum(gold, gold_contour(DEAD, 1.5, 0.85))

# componer dorado sobre navy
ga = gold[..., None]
img = img * (1 - ga) + np.array(GOLD, np.float32) * ga
img = np.clip(img, 0, 255).astype(np.uint8)

# guardar capas para compose
np.savez_compressed(os.path.join(DERIVED, "sea_layer.npz"),
                    fill=fill, gold=gold.astype(np.float32))

save_png(img, os.path.join(PREVIEW, "sea_preview_full.png"))
Image.fromarray(img).resize((W // 2, H // 2), Image.LANCZOS).save(os.path.join(PREVIEW, "sea_preview.png"))
Image.fromarray(img).resize((W // 5, H // 5), Image.LANCZOS).save(os.path.join(PREVIEW, "sea_thumb.png"))
print("OK -> preview/sea_preview.png (+ thumb). med/gal/dead alpha listos.")
