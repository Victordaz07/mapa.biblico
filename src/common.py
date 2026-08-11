"""
Módulo común — mapa base Tierra Santa (iteración 2).
NO toca bbox / proyección / dimensiones / calibracion.json.
"""
import json, os
import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "input")
OUTPUT = os.path.join(ROOT, "output")
PREVIEW = os.path.join(ROOT, "preview")
DERIVED = os.path.join(INPUT, "derived")
for d in (OUTPUT, PREVIEW, DERIVED):
    os.makedirs(d, exist_ok=True)

# ---- Calibración (INMUTABLE) ----
with open(os.path.join(INPUT, "calibracion.json"), "r", encoding="utf-8") as f:
    CAL = json.load(f)
WEST, SOUTH, EAST, NORTH = CAL["bbox"]
W = CAL["width"]    # 2000
H = CAL["height"]   # 2600

# Paleta
NAVY = (13, 27, 42)      # #0D1B2A
GOLD = (184, 146, 58)    # #B8923A

# Tamaño de pixel en metros sobre el grid destino (para pendientes reales)
_latmid = (SOUTH + NORTH) / 2.0
PX_X_M = (EAST - WEST) / W * 111320.0 * np.cos(np.radians(_latmid))
PX_Y_M = (NORTH - SOUTH) / H * 110570.0


def to_px(lng, lat):
    """Convierte lng/lat -> (x,y) en px según la calibración lineal (INMUTABLE)."""
    x = (lng - WEST) / (EAST - WEST) * W
    y = (1.0 - (lat - SOUTH) / (NORTH - SOUTH)) * H
    return x, y


def load_dem_grid():
    """DEM SRTM resampleado (bilinear) al grid exacto 2000x2600 de la calibración.
    Devuelve (elev_float con NaN en nodata, mask_valid)."""
    import rasterio
    from rasterio.enums import Resampling
    with rasterio.open(os.path.join(INPUT, "dem_SRTMGL1.tif")) as ds:
        arr = ds.read(1, out_shape=(H, W), resampling=Resampling.bilinear).astype(np.float32)
        nodata = ds.nodata
    valid = arr > (nodata + 1) if nodata is not None else np.ones_like(arr, bool)
    # SRTM rellena océano/void con 0 en algunas zonas; lo tratamos como no-relieve más tarde vía máscara de agua.
    elev = arr.copy()
    elev[~valid] = np.nan
    return elev, valid


def slope_aspect(elev):
    """Pendiente (grados) y aspecto (rad, 0=Este, CCW) desde elevación en metros.
    NaN se rellena por vecindad para evitar bordes artificiales."""
    z = elev.copy()
    nan = np.isnan(z)
    if nan.any():
        # relleno suave sólo para gradientes; los NaN se re-enmascaran después
        filled = z.copy()
        filled[nan] = np.nanmean(z)
        filled = gaussian_filter(filled, 1.0)
        z = np.where(nan, filled, z)
    dzdy, dzdx = np.gradient(z, PX_Y_M, PX_X_M)  # metros/metro
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = np.arctan2(-dzdy, dzdx)  # dirección de máxima pendiente cuesta abajo
    slope[nan] = 0.0
    return slope.astype(np.float32), aspect.astype(np.float32), nan


def hillshade(elev, azimuth_deg, altitude_deg, z_factor=1.0):
    z = elev.copy()
    nan = np.isnan(z)
    if nan.any():
        filled = z.copy(); filled[nan] = np.nanmean(z)
        z = np.where(nan, gaussian_filter(filled, 1.0), z)
    dzdy, dzdx = np.gradient(z * z_factor, PX_Y_M, PX_X_M)
    slope = np.pi/2 - np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdy, dzdx)
    az = np.radians(360.0 - azimuth_deg + 90.0)
    alt = np.radians(altitude_deg)
    hs = (np.sin(alt)*np.sin(slope) +
          np.cos(alt)*np.cos(slope)*np.cos(az - aspect))
    hs = np.clip(hs, 0, 1)
    return hs.astype(np.float32)


def multi_hillshade(elev, z_factor=1.4):
    """Hillshade multidireccional (media de 4 azimuts) para dar volumen sin sesgo."""
    acc = np.zeros((H, W), np.float32)
    for az in (315, 355, 45, 270):
        acc += hillshade(elev, az, 45, z_factor)
    return acc / 4.0


# ---------- Pergamino + grano ----------
def _rng(seed):
    return np.random.default_rng(seed)

def parchment(seed=7):
    """Fondo pergamino cálido con manchas suaves y grano fino. RGB uint8 (H,W,3)."""
    rng = _rng(seed)
    base = np.array([234, 225, 202], np.float32)      # crema
    warm = np.array([210, 188, 150], np.float32)      # sombra cálida
    # campo de manchas de baja frecuencia
    low = rng.standard_normal((H//16, W//16)).astype(np.float32)
    low = gaussian_filter(low, 4)
    low = np.array(_resize(low, (H, W)))
    low = (low - low.min()) / (np.ptp(low) + 1e-6)
    # viñeteado suave hacia bordes
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W/2, H/2
    vig = np.hypot((xx-cx)/(W/2), (yy-cy)/(H/2))
    vig = np.clip(vig, 0, 1.4)
    t = np.clip(0.20*low + 0.16*(vig/1.4), 0, 1)[..., None]
    img = base*(1-t) + warm*t
    # grano fino
    grain = rng.normal(0, 3.2, (H, W, 1)).astype(np.float32)
    fine = rng.normal(0, 1.6, (H, W, 1)).astype(np.float32)
    img = img + grain + fine
    # motas ocasionales (foxing) muy sutiles
    spots = (rng.random((H, W)) > 0.9995).astype(np.float32)
    spots = gaussian_filter(spots, 1.2)[..., None] * np.array([-18, -20, -16], np.float32)
    img = img + spots
    return np.clip(img, 0, 255).astype(np.uint8)


def _resize(a, shape):
    from PIL import Image
    im = Image.fromarray(a.astype(np.float32), mode="F").resize((shape[1], shape[0]), Image.BILINEAR)
    return np.asarray(im, np.float32)


# ---------- utilidades de composición ----------
def over(dst, src_rgb, alpha):
    """alpha compositing: src sobre dst. alpha (H,W) en [0,1]. Modifica y devuelve dst float."""
    a = alpha[..., None]
    return dst*(1-a) + np.asarray(src_rgb, np.float32)*a

def save_png(arr_uint8, path):
    from PIL import Image
    Image.fromarray(arr_uint8, "RGB").save(path)
    return path

def save_preview(arr_uint8, name, scale=0.5):
    from PIL import Image
    im = Image.fromarray(arr_uint8, "RGB")
    if scale != 1.0:
        im = im.resize((int(W*scale), int(H*scale)), Image.LANCZOS)
    p = os.path.join(PREVIEW, name)
    im.save(p)
    return p
