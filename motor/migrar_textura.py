"""
Migración — añade el campo `textura` al catálogo y a la biblioteca.

Se ejecuta UNA VEZ, sobre el repositorio tal como esté. Edita línea a línea,
así que **conserva los comentarios y cualquier cambio propio** ya hecho en
datos/alimentos_base.yaml (etiquetas de alérgeno añadidas a mano, alimentos
nuevos, notas). No reescribe el YAML: solo inserta el campo donde falta.

Vocabulario de textura (uno por alimento, el que domina el bocado):

    seca        bastón, tacacho, galleta, pan, carne a la plancha
    crujiente   pop de cereal, frito muy seco
    blanda      papa o plátano sancochado, fruta madera en trozos
    humeda      guiso, crema, compota, mazamorra, yogurt
    liquida     refresco, batido, sopa, agua
    mixta       dos texturas en el mismo plato (arroz con guiso encima)

Uso:
    python motor/migrar_textura.py            muestra qué haría
    python motor/migrar_textura.py --aplicar  escribe los cambios
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from comun import DIR_BIBLIOTECA, DIR_DATOS, leer_front_matter

# Textura por id de alimento. Lo que no aparezca aquí toma el valor por
# defecto de su componente, y si tampoco lo hay, queda sin declarar.
POR_ID = {
    # secos y crujientes
    "arroz": "seca", "papa": "blanda", "camote": "blanda", "quinua": "humeda",
    "fideos": "humeda", "yuca": "blanda",
    "papa_pure": "humeda", "camote_pure": "humeda", "zapallo_pure": "humeda",
    "arroz_pure": "humeda",
    "avena": "humeda", "canihua": "humeda", "maca": "humeda",
    "algarrobo": "humeda", "siete_sem": "humeda",
    "kiwicha": "crujiente", "quinua_hoj": "crujiente",
    "kiwicha_pop": "crujiente", "quinua_pop": "crujiente",
    # menestras
    "lentejas": "humeda", "frejol_cast": "humeda", "panamito": "humeda",
    "garbanzo": "blanda", "arveja_part": "humeda",
    "lentejas_pure": "humeda", "panamito_pure": "humeda", "arveja_pure": "humeda",
    # proteínas
    "pollo": "seca", "pescado": "seca", "res": "seca", "huevo": "blanda",
    "pavita": "seca", "pollo_desm": "seca",
    "higado_pollo": "blanda", "sangrecita": "blanda", "bazo": "blanda",
    # verduras y ensaladas
    "zanahoria": "blanda", "zapallo": "humeda", "espinaca": "humeda",
    "brocoli": "blanda", "betarraga": "blanda", "vainita": "blanda",
    "ens_palta": "mixta", "ens_oliva": "mixta", "ens_ajonjoli": "mixta",
    # grasas
    "aceite_oliva_g": "liquida", "palta_g": "humeda",
    "mant_anacardo": "humeda", "mant_mani": "humeda", "mant_almendra": "humeda",
    # frutas
    "platano": "blanda", "manzana": "blanda", "pera": "blanda", "mango": "blanda",
    "uva_cort": "blanda", "durazno": "blanda",
    "naranja": "blanda", "mandarina": "blanda", "lima": "blanda",
    "pina_golden": "blanda", "aguaymanto": "blanda", "papaya": "blanda",
    "kiwi": "blanda", "fresa": "blanda",
    # otros
    "fruta_picada": "blanda", "yogurt": "humeda", "agua": "liquida",
}

POR_COMPONENTE = {
    "cereal": "humeda", "menestra": "humeda", "verdura": "blanda",
    "fruta": "blanda", "fruta_vitc": "blanda", "bebida": "liquida",
    "crujiente": "crujiente", "ensalada_grasa": "mixta",
}

# Recetas semilla y las creadas durante el benchmark.
RECETAS = {
    "tortilla-espinaca-queso": "blanda",
    "huevo-revuelto-palta": "humeda",
    "panqueques-avena-huevo": "blanda",
    "baston-relleno-pollo": "mixta",
    "muffins-zanahoria-avena": "blanda",
    "crema-quinua-manzana": "humeda",
    "mazamorra-kiwicha": "humeda",
    "trufas-garbanzo-cacao": "blanda",
    "paletas-mango-papaya": "humeda",
    "compota-pera-avena": "humeda",
    "barritas-kiwicha-datil": "seca",
    "tacacho-platano-bellaco": "seca",
    "bastones-yuca-dorada": "seca",
}

LINEA_ALIMENTO = re.compile(r"^(\s*-\s*\{)\s*id:\s*([A-Za-z0-9_]+)\s*,(.*)\}\s*$")
COMPONENTE = re.compile(r"^([a-z_]+):\s*$")


def migrar_catalogo(aplicar: bool) -> list[str]:
    ruta = DIR_DATOS / "alimentos_base.yaml"
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    salida, cambios, componente = [], [], ""

    for linea in lineas:
        m_comp = COMPONENTE.match(linea)
        if m_comp:
            componente = m_comp.group(1)
        m = LINEA_ALIMENTO.match(linea)
        if not m or "textura:" in linea:
            salida.append(linea)
            continue
        cabeza, ident, resto = m.groups()
        textura = POR_ID.get(ident) or POR_COMPONENTE.get(componente, "")
        if not textura:
            salida.append(linea)
            cambios.append(f"  ? {ident} ({componente}) — sin textura conocida, se deja vacío")
            continue
        salida.append(f"{cabeza}id: {ident},{resto.rstrip()}, textura: {textura}}}")
        cambios.append(f"  + {ident:<16} {textura}")

    if aplicar and cambios:
        ruta.write_text("\n".join(salida) + "\n", encoding="utf-8")
    return cambios


def migrar_biblioteca(aplicar: bool) -> list[str]:
    cambios = []
    for ruta in sorted(DIR_BIBLIOTECA.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        texto = ruta.read_text(encoding="utf-8")
        if re.search(r"^textura:", texto, re.MULTILINE):
            continue
        try:
            meta, _ = leer_front_matter(ruta)
        except Exception:
            continue
        rid = str(meta.get("id") or ruta.stem)
        textura = RECETAS.get(rid, "")
        if not textura:
            cambios.append(f"  ? {rid} — textura desconocida, decláralas a mano")
            continue
        nuevo = texto.replace("\naporta:", f"\ntextura: {textura}\naporta:", 1)
        if nuevo == texto:
            nuevo = texto.replace("\norigen:", f"\ntextura: {textura}\norigen:", 1)
        if nuevo == texto:
            cambios.append(f"  ? {rid} — no se encontró dónde insertar el campo")
            continue
        if aplicar:
            ruta.write_text(nuevo, encoding="utf-8")
        cambios.append(f"  + {rid:<28} {textura}")
    return cambios


def main() -> int:
    ap = argparse.ArgumentParser(description="Añade el campo textura al catálogo y la biblioteca.")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    print("\n— Catálogo de alimentos —")
    for c in migrar_catalogo(args.aplicar) or ["  (nada que hacer)"]:
        print(c)

    print("\n— Biblioteca de recetas —")
    for c in migrar_biblioteca(args.aplicar) or ["  (nada que hacer)"]:
        print(c)

    print()
    if args.aplicar:
        print("✓ Cambios escritos. Revisa con: git diff\n")
    else:
        print("Esto es solo una vista previa. Para escribir:  python motor/migrar_textura.py --aplicar\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
