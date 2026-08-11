"""
Capa de anotaciones — Vida de Jesús / N.T. (prototipo).
Coloca lugares clave con VIÑETAS PICTÓRICAS grabadas (line-art sepia/dorado,
supersampling x3 para bordes nítidos) + etiqueta serif itálica, sobre el master.

No toca la base ni la calibración: usa common.to_px(lng,lat) para posicionar.
Salida: preview/annotated_preview.png (+ thumb).
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from common import W, H, OUTPUT, PREVIEW, INPUT, to_px

# --- paleta de tinta (coherente con la base) ---
INK  = (58, 44, 24, 255)     # sepia oscuro (líneas)
INK2 = (58, 44, 24, 170)     # sepia translúcido (relleno hachura)
NAVY = (13, 27, 42, 255)
GOLD = (184, 146, 58, 255)
GOLDF= (184, 146, 58, 235)

SS = 3                        # supersampling
FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf"


# ---------------- viñetas (dibujan centradas en (cx,cy), tamaño s, en px SS) ----------------
def _lw(w):  # ancho de línea escalado
    return max(1, int(round(w * SS)))

def v_temple(dr, cx, cy, s):
    """Templo: escalinata + columnas + frontón (Jerusalén)."""
    w = s * 1.9; h = s * 1.5
    x0, x1 = cx - w/2, cx + w/2
    base = cy + h*0.55
    # escalones
    for i, k in enumerate((1.0, 0.86, 0.72)):
        dr.rectangle([cx-w/2*k, base - i*s*0.16, cx+w/2*k, base - i*s*0.16 + s*0.16],
                     outline=INK, width=_lw(1.6))
    top_cols = cy - h*0.18
    bot_cols = base - 3*s*0.16
    # columnas
    ncol = 5
    for i in range(ncol):
        x = x0 + (i+0.5)*(w/ncol)
        dr.line([x, top_cols, x, bot_cols], fill=INK, width=_lw(1.8))
    # arquitrabe
    dr.rectangle([x0, top_cols - s*0.14, x1, top_cols], outline=INK, width=_lw(1.6))
    # frontón (triángulo)
    apex = (cx, cy - h*0.62)
    dr.line([x0, top_cols - s*0.14, apex[0], apex[1]], fill=INK, width=_lw(1.8))
    dr.line([x1, top_cols - s*0.14, apex[0], apex[1]], fill=INK, width=_lw(1.8))
    dr.line([x0, top_cols - s*0.14, x1, top_cols - s*0.14], fill=INK, width=_lw(1.6))

def v_star(dr, cx, cy, s):
    """Estrella de Belén: 8 puntas doradas + destello."""
    R, r = s*0.95, s*0.36
    pts = []
    for k in range(16):
        ang = np.pi/2 + k*np.pi/8
        rad = R if k % 2 == 0 else r
        pts.append((cx + rad*np.cos(ang), cy - rad*np.sin(ang)))
    dr.polygon(pts, fill=GOLDF, outline=INK)
    dr.line(pts + [pts[0]], fill=INK, width=_lw(1.4), joint="curve")
    # rayo largo hacia abajo (guía hacia el pesebre)
    dr.line([cx, cy+R, cx, cy+R*1.9], fill=GOLD, width=_lw(1.3))

def v_walls(dr, cx, cy, s):
    """Murallas con almenas y portón (Jericó)."""
    w = s*2.0; h = s*1.1
    x0, y0, x1, y1 = cx-w/2, cy-h/2, cx+w/2, cy+h/2
    dr.rectangle([x0, y0, x1, y1], outline=INK, width=_lw(1.8))
    # almenas
    n = 6; cw = w/n
    for i in range(n):
        if i % 2 == 0:
            dr.rectangle([x0+i*cw, y0 - s*0.22, x0+(i+1)*cw, y0], outline=INK, width=_lw(1.6))
    # portón (arco)
    gw = w*0.22
    dr.rectangle([cx-gw/2, y1-h*0.55, cx+gw/2, y1], outline=INK, width=_lw(1.6))
    dr.arc([cx-gw/2, y1-h*0.75, cx+gw/2, y1-h*0.35], 180, 360, fill=INK, width=_lw(1.6))
    # hiladas
    for k in (0.35, 0.66):
        dr.line([x0, y0+h*k, x1, y0+h*k], fill=INK2, width=_lw(1.0))

def v_houses(dr, cx, cy, s):
    """Caserío de aldea: casitas a dos aguas (Nazaret)."""
    specs = [(-s*0.8, 0.0, 0.9), (s*0.05, -s*0.1, 1.1), (s*0.95, s*0.05, 0.8)]
    for ox, oy, sc in specs:
        hw = s*0.5*sc; hh = s*0.55*sc
        bx, by = cx+ox, cy+oy
        dr.rectangle([bx-hw, by, bx+hw, by+hh], outline=INK, width=_lw(1.6))
        dr.line([bx-hw, by, bx, by-hh*0.7], fill=INK, width=_lw(1.6))
        dr.line([bx+hw, by, bx, by-hh*0.7], fill=INK, width=_lw(1.6))
        dr.line([bx-hw, by, bx+hw, by], fill=INK, width=_lw(1.4))

def v_synagogue(dr, cx, cy, s):
    """Edificio con pórtico y puerta en arco (Cafarnaúm)."""
    w = s*1.5; h = s*1.25
    x0, y0, x1, y1 = cx-w/2, cy-h*0.3, cx+w/2, cy+h*0.6
    dr.rectangle([x0, y0, x1, y1], outline=INK, width=_lw(1.8))
    # tejado a dos aguas
    dr.line([x0, y0, cx, y0-h*0.5], fill=INK, width=_lw(1.8))
    dr.line([x1, y0, cx, y0-h*0.5], fill=INK, width=_lw(1.8))
    # puerta en arco
    dw = w*0.3
    dr.rectangle([cx-dw/2, y1-h*0.55, cx+dw/2, y1], outline=INK, width=_lw(1.5))
    dr.arc([cx-dw/2, y1-h*0.8, cx+dw/2, y1-h*0.3], 180, 360, fill=INK, width=_lw(1.5))
    # ventanitas
    for sx in (-1, 1):
        dr.rectangle([cx+sx*w*0.3-s*0.1, y0+h*0.15, cx+sx*w*0.3+s*0.1, y0+h*0.35],
                     outline=INK, width=_lw(1.2))

def v_baptism(dr, cx, cy, s):
    """Bautismo: paloma descendente con rayos + agua ondulada (Jordán)."""
    # rayos dorados
    for a in (-40, -20, 0, 20, 40):
        ar = np.radians(90+a)
        dr.line([cx, cy-s*0.2, cx+np.cos(ar)*s*1.1, cy-s*0.2-np.sin(ar)*s*1.1],
                fill=GOLD, width=_lw(1.1))
    # paloma estilizada (cuerpo + alas)
    dr.ellipse([cx-s*0.28, cy-s*0.15, cx+s*0.28, cy+s*0.2], outline=INK, width=_lw(1.5))
    dr.line([cx-s*0.28, cy, cx-s*0.7, cy-s*0.25], fill=INK, width=_lw(1.5))
    dr.line([cx+s*0.28, cy, cx+s*0.7, cy-s*0.25], fill=INK, width=_lw(1.5))
    # agua
    for i, yy in enumerate((s*0.55, s*0.8)):
        pts = [(cx-s*0.9 + t*s*0.3, cy+yy + (s*0.09 if (t % 2) else -s*0.09)) for t in range(7)]
        dr.line(pts, fill=NAVY, width=_lw(1.4), joint="curve")


VIGNETTE = {"temple": v_temple, "star": v_star, "walls": v_walls,
            "houses": v_houses, "synagogue": v_synagogue, "baptism": v_baptism}

# ---------------- lugares (Vida de Jesús) ----------------
# (nombre, lng, lat, viñeta, escala_px, (lbl_dx,lbl_dy), ancla, (vig_dx,vig_dy))
# vig_dx/dy desplaza la VIÑETA respecto al punto real (para no pisar el agua);
# si hay desplazamiento se dibuja un puntito-guía en la coordenada exacta.
PLACES = [
    ("Cafarnaúm",  35.5753, 32.8808, "synagogue", 32, ( 30, -60), "l", (-4, -74)),
    ("Nazaret",    35.2978, 32.7021, "houses",    32, (-44,  -6), "r", (0, 0)),
    ("Río Jordán\n(Bautismo)", 35.5312, 31.8370, "baptism", 30, (42, 0), "l", (14, 0)),
    ("Jericó",     35.4440, 31.8700, "walls",     32, (-46,  -4), "r", (0, 0)),
    ("Jerusalén",  35.2354, 31.7780, "temple",    44, (-54,   8), "r", (0, 0)),
    ("Belén",      35.2024, 31.7054, "star",      26, (-40,   4), "r", (0, 0)),
]


def main():
    base = Image.open(os.path.join(OUTPUT, "mapa_base.png")).convert("RGBA")
    layer = Image.new("RGBA", (W*SS, H*SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)

    for name, lng, lat, kind, scale, (dx, dy), anchor, (vdx, vdy) in PLACES:
        x, y = to_px(lng, lat)
        cx, cy = (x+vdx)*SS, (y+vdy)*SS
        # puntito-guía en la coordenada exacta si la viñeta va desplazada
        if vdx or vdy:
            r = 3*SS
            dr.ellipse([x*SS-r, y*SS-r, x*SS+r, y*SS+r], fill=INK)
            dr.line([x*SS, y*SS, cx, cy], fill=INK2, width=_lw(1.0))
        VIGNETTE[kind](dr, cx, cy, scale*SS)

    small = layer.resize((W, H), Image.LANCZOS)
    out = Image.alpha_composite(base, small)

    # --- etiquetas (nítidas, sin supersample para hinting limpio) ---
    dr2 = ImageDraw.Draw(out)
    for name, lng, lat, kind, scale, (dx, dy), anchor, (vdx, vdy) in PLACES:
        x, y = to_px(lng, lat)
        x, y = x + vdx, y + vdy       # etiqueta relativa a la viñeta desplazada
        big = name in ("Jerusalén",)
        fnt = ImageFont.truetype(FONT_BOLD if big else FONT_PATH, 30 if big else 25)
        tx, ty = x + dx, y + dy
        lines = name.split("\n")
        # medir para anclar a la derecha
        widths = [dr2.textlength(ln, font=fnt) for ln in lines]
        for i, ln in enumerate(lines):
            wln = widths[i]
            lx = tx - wln if anchor == "r" else tx
            ly = ty + i*(fnt.size+2)
            # halo claro para legibilidad sobre el hachurado
            for ox in (-2, 2):
                for oy in (-2, 2):
                    dr2.text((lx+ox, ly+oy), ln, font=fnt, fill=(238, 230, 208, 220))
            dr2.text((lx, ly), ln, font=fnt, fill=(46, 34, 18, 255))

    out = out.convert("RGB")
    out.save(os.path.join(PREVIEW, "annotated_preview_full.png"))
    out.resize((W//2, H//2), Image.LANCZOS).save(os.path.join(PREVIEW, "annotated_preview.png"))
    out.resize((W//5, H//5), Image.LANCZOS).save(os.path.join(PREVIEW, "annotated_thumb.png"))
    print("OK -> preview/annotated_preview.png (+ thumb).", len(PLACES), "lugares.")


if __name__ == "__main__":
    main()
