"""
Exporta la capa interactiva para la web:
- web/assets/mapa.jpg  : mapa anotado (viñetas+etiquetas) optimizado
- web/data.js          : window.PLACES con {name, x%, y%, note, refs}
Coordenadas derivadas de la MISMA calibración (to_px) usada al dibujar.
"""
import os, json, shutil
from PIL import Image
from common import W, H, OUTPUT, PREVIEW, to_px
from places import PLACES

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
ASSETS = os.path.join(WEB, "assets")

# Notas ("qué pasó ahí") + referencias bíblicas, por nombre
NOTES = {
    "Cafarnaúm": ("Centro del ministerio de Jesús en Galilea. Enseñó en su "
                  "sinagoga y sanó a muchos; hogar de Pedro.", "Mt 4:13 · Mc 2:1"),
    "Nazaret": ("Pueblo donde Jesús creció. Al leer en la sinagoga fue "
                "rechazado por los suyos.", "Lc 2:39-40 · Lc 4:16-30"),
    "Río Jordán\n(Bautismo)": ("Juan bautiza a Jesús en el Jordán; el Espíritu "
                "desciende como paloma y se oye la voz del Padre.", "Mt 3:13-17"),
    "Jericó": ("Jesús sana al ciego Bartimeo y se hospeda en casa de "
               "Zaqueo, el publicano.", "Mc 10:46-52 · Lc 19:1-10"),
    "Jerusalén": ("Entrada triunfal, Última Cena, crucifixión y "
                  "resurrección. Corazón de la Pasión.", "Mt 21 · Mt 26-28"),
    "Belén": ("Nacimiento de Jesús. Los pastores acuden y los magos "
              "siguen la estrella.", "Lc 2:1-20 · Mt 2:1-12"),
}


def main():
    os.makedirs(ASSETS, exist_ok=True)

    # --- imagen web optimizada (desde el mapa anotado) ---
    src_img = os.path.join(PREVIEW, "annotated_preview_full.png")
    im = Image.open(src_img).convert("RGB")
    web_w = 1500
    im_web = im.resize((web_w, round(web_w * H / W)), Image.LANCZOS)
    jpg = os.path.join(ASSETS, "mapa.jpg")
    im_web.save(jpg, quality=84, optimize=True, progressive=True)

    # orden narrativo: nacimiento -> Pasión
    ORDER = {"Belén": 1, "Nazaret": 2, "Río Jordán\n(Bautismo)": 3,
             "Cafarnaúm": 4, "Jericó": 5, "Jerusalén": 6}

    # --- datos de puntos (hotspots) en % ---
    data = []
    for name, lng, lat, kind, scale, lbl, anchor, (vdx, vdy) in PLACES:
        x, y = to_px(lng, lat)
        x += vdx; y += vdy                      # centro de la viñeta
        note, refs = NOTES.get(name, ("", ""))
        data.append({
            "n": ORDER.get(name, 99),
            "name": name.replace("\n", " "),
            "x": round(x / W * 100, 3),
            "y": round(y / H * 100, 3),
            "r": round(scale / W * 100 * 1.15, 3),  # radio clicable en %
            "note": note,
            "refs": refs,
        })
    data.sort(key=lambda d: d["n"])

    with open(os.path.join(WEB, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.PLACES = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")

    kb = os.path.getsize(jpg) // 1024
    print(f"OK -> web/assets/mapa.jpg ({kb} KB, {im_web.size})  ·  web/data.js ({len(data)} puntos)")


if __name__ == "__main__":
    main()
