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

# Notas ("qué pasó ahí") + referencias + categoría, por nombre (LUGARES PRIMARIOS)
NOTES = {
    "Cafarnaúm": ("Centro del ministerio de Jesús en Galilea. Enseñó en su "
                  "sinagoga y sanó a muchos; hogar de Pedro.", "Mt 4:13 · Mc 2:1", "ministerio"),
    "Nazaret": ("Pueblo donde Jesús creció. Al leer en la sinagoga fue "
                "rechazado por los suyos.", "Lc 2:39-40 · Lc 4:16-30", "ministerio"),
    "Río Jordán\n(Bautismo)": ("Juan bautiza a Jesús en el Jordán; el Espíritu "
                "desciende como paloma y se oye la voz del Padre.", "Mt 3:13-17", "ministerio"),
    "Jericó": ("Jesús sana al ciego Bartimeo y se hospeda en casa de "
               "Zaqueo, el publicano.", "Mc 10:46-52 · Lc 19:1-10", "milagro"),
    "Jerusalén": ("Entrada triunfal, Última Cena, crucifixión y "
                  "resurrección. Corazón de la Pasión.", "Mt 21 · Mt 26-28", "pasion"),
    "Belén": ("Nacimiento de Jesús. Los pastores acuden y los magos "
              "siguen la estrella.", "Lc 2:1-20 · Mt 2:1-12", "nacimiento"),
}

# Gazetteer de ciudades SECUNDARIAS (lng, lat, nota, refs, categoría).
# Coordenadas geográficas reales; posiciones tomadas de "La Buena Tierra".
SECONDARY = [
    ("Caná",        35.3419, 32.7480, "Primer milagro: convirtió el agua en vino en una boda.", "Jn 2:1-11", "milagro"),
    ("Naín",        35.3714, 32.6339, "Jesús resucitó al hijo único de una viuda.", "Lc 7:11-17", "milagro"),
    ("Betsaida",    35.6300, 32.9100, "Hogar de Pedro, Andrés y Felipe; curación de un ciego.", "Mc 8:22-26", "ministerio"),
    ("Corazín",     35.5647, 32.9106, "Ciudad reprendida por Jesús por su incredulidad.", "Mt 11:20-21", "ministerio"),
    ("Tiberíades",  35.5320, 32.7959, "Ciudad junto al mar de Galilea, capital de Herodes Antipas.", "Jn 6:23", "ciudad"),
    ("Magdala",     35.5169, 32.8267, "Pueblo de María Magdalena.", "Lc 8:2", "ciudad"),
    ("Séforis",     35.2794, 32.7453, "Gran ciudad a una hora de Nazaret.", "", "ciudad"),
    ("Sicar",       35.2833, 32.2139, "Jesús habla con la samaritana junto al pozo de Jacob.", "Jn 4:5-42", "ministerio"),
    ("Escitópolis", 35.5000, 32.5036, "Principal ciudad de la Decápolis (Bet-Seán).", "", "ciudad"),
    ("Emaús",       34.9892, 31.8390, "El resucitado se aparece a dos discípulos de camino.", "Lc 24:13-35", "pasion"),
    ("Betania",     35.2564, 31.7717, "Casa de Marta, María y Lázaro; Jesús resucita a Lázaro.", "Jn 11:1-44", "milagro"),
    ("Betfagué",    35.2469, 31.7772, "Punto de partida de la entrada triunfal a Jerusalén.", "Mt 21:1-11", "pasion"),
    ("Cesarea",     34.8917, 32.5000, "Sede del gobernador romano; puerto y prisión de Pablo.", "Hch 23-26", "ciudad"),
    ("Jope",        34.7550, 32.0522, "Pedro resucita a Tabita; visión de los alimentos.", "Hch 9:36-43", "ciudad"),
]


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

    # --- lugares PRIMARIOS (viñetas + recorrido narrativo) ---
    data = []
    for name, lng, lat, kind, scale, lbl, anchor, (vdx, vdy) in PLACES:
        x, y = to_px(lng, lat)
        x += vdx; y += vdy                      # centro de la viñeta
        note, refs, cat = NOTES.get(name, ("", "", "ciudad"))
        data.append({
            "n": ORDER.get(name, 99),
            "name": name.replace("\n", " "),
            "x": round(x / W * 100, 3),
            "y": round(y / H * 100, 3),
            "r": round(scale / W * 100 * 1.15, 3),
            "note": note, "refs": refs, "cat": cat, "tier": "primary",
        })
    data.sort(key=lambda d: d["n"])

    # --- ciudades SECUNDARIAS (punto + etiqueta, fuera del recorrido) ---
    for name, lng, lat, note, refs, cat in SECONDARY:
        x, y = to_px(lng, lat)
        data.append({
            "name": name,
            "x": round(x / W * 100, 3),
            "y": round(y / H * 100, 3),
            "note": note, "refs": refs, "cat": cat, "tier": "secondary",
        })

    with open(os.path.join(WEB, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.PLACES = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")

    kb = os.path.getsize(jpg) // 1024
    np_ = sum(1 for d in data if d["tier"] == "primary")
    ns_ = sum(1 for d in data if d["tier"] == "secondary")
    print(f"OK -> web/assets/mapa.jpg ({kb} KB, {im_web.size})  ·  web/data.js "
          f"({np_} primarios + {ns_} secundarios)")


if __name__ == "__main__":
    main()
