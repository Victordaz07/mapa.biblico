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
    ("Tiberíades",  35.5320, 32.7959, "De sus orillas zarparon barcas hacia el lugar donde Jesús multiplicó los panes.", "Jn 6:23", "ciudad"),
    ("Magdala",     35.5169, 32.8267, "Pueblo de María Magdalena, de quien Jesús expulsó siete demonios.", "Lc 8:2", "ministerio"),
    ("Séforis",     35.2794, 32.7453, "Capital herodiana a una hora de Nazaret; la tradición dice que José trabajó en su reconstrucción.", "Tradición", "ciudad"),
    ("Sicar",       35.2833, 32.2139, "Jesús habla con la samaritana junto al pozo de Jacob.", "Jn 4:5-42", "ministerio"),
    ("Escitópolis", 35.5000, 32.5036, "La mayor ciudad de la Decápolis (Bet-Seán); su región oyó la fama de Jesús.", "Mc 7:31", "ciudad"),
    ("Emaús",       34.9892, 31.8390, "El resucitado se aparece a dos discípulos de camino.", "Lc 24:13-35", "pasion"),
    ("Betania",     35.2564, 31.7717, "Casa de Marta, María y Lázaro; Jesús resucita a Lázaro.", "Jn 11:1-44", "milagro"),
    ("Betfagué",    35.2469, 31.7772, "Punto de partida de la entrada triunfal a Jerusalén.", "Mt 21:1-11", "pasion"),
    ("Cesarea",     34.8917, 32.5000, "Sede del gobernador romano; puerto y prisión de Pablo.", "Hch 23-26", "ciudad"),
    ("Jope",        34.7550, 32.0522, "Pedro resucita a Tabita; visión de los alimentos.", "Hch 9:36-43", "ciudad"),
    # + gazetteer ampliado (Decápolis, Samaria, Damasco, sitios de la Pasión)
    ("Monte de las Bienaventuranzas", 35.5528, 32.8737, "Sermón del Monte: las Bienaventuranzas.", "Mt 5-7", "ministerio"),
    ("Samaria (Sebastia)", 35.1892, 32.2764, "Ciudad reconstruida por Herodes; región donde Felipe predicó con gran poder.", "Hch 8:5-8", "ciudad"),
    ("Damasco", 36.2765, 33.5138, "Conversión de Pablo en el camino a esta ciudad.", "Hch 9:1-19", "ciudad"),
    ("Cesarea de Filipo", 35.6928, 33.2493, "Pedro confiesa que Jesús es el Cristo.", "Mt 16:13-20", "ministerio"),
    ("Gamala", 35.7420, 32.8880, "Escenario de una resistencia heroica en la guerra judía (67 d.C.), narrada por Josefo.", "Josefo, Guerra IV", "ciudad"),
    ("Pela", 35.6114, 32.4522, "Ciudad de la Decápolis; la tradición dice que los cristianos huyeron aquí antes del 70 d.C.", "Eusebio, Hist. Ecl. III.5", "ciudad"),
    ("Gerasa", 35.8919, 32.2811, "Tradicionalmente asociada a la sanación del endemoniado geraseno.", "Mc 5:1-20", "milagro"),
    ("Gadara", 35.6817, 32.6544, "Sitio alternativo de la sanación del endemoniado (región de los gadarenos).", "Mt 8:28-34", "ciudad"),
    ("Hipos", 35.6558, 32.7897, "Ciudad de la Decápolis; de su región acudían multitudes a oír a Jesús.", "Mt 4:25", "ministerio"),
    ("Monte Guerizim", 35.2725, 32.1958, "Monte sagrado samaritano, mencionado en la conversación con la samaritana.", "Jn 4:20-21", "ministerio"),
    ("Lida", 34.8925, 31.9514, "Pedro sana a Eneas, paralítico de ocho años.", "Hch 9:32-35", "milagro"),
    ("Arimatea", 34.9800, 31.9800, "Ciudad natal de José, que sepultó a Jesús en su propia tumba.", "Mt 27:57-60", "pasion"),
    ("Efraín", 35.2625, 31.9917, "Jesús se retiró aquí con sus discípulos antes de la Pasión final.", "Jn 11:54", "pasion"),
    ("Herodión", 35.2436, 31.6653, "Fortaleza-palacio donde fue sepultado Herodes el Grande, cerca de Belén.", "Josefo, Guerra I", "ciudad"),
    ("Hebrón", 35.0998, 31.5326, "Ciudad de los patriarcas; tumba de Abraham, Isaac y Jacob.", "Gn 23:19 · 2 S 2:1-4", "ciudad"),
    ("Masada", 35.3536, 31.3156, "Fortaleza de Herodes sobre el Mar Muerto; último reducto de la revuelta judía (73 d.C.).", "Contexto histórico — Josefo", "ciudad"),
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
        if name == "Jerusalén":
            data[-1]["link"] = "jerusalen.html"   # drill-down a la vista de ciudad
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
