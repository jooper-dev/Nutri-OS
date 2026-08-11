"""
Prompts de fotografía — Nutri-OS

Arma el prompt de imagen de cada receta a partir de:
  · la variante A–K y el acento que P1 asignó en el front-matter
  · la descripción del sujeto que P1 escribió en la sección «Foto»
  · la plantilla correspondiente de datos/biblioteca_fotografia.md

Aquí no hay criterio: la variante y el color ya los decidió P1 al crear la
receta. Este script solo rellena huecos, y por eso el resultado es idéntico
cada vez que se ejecuta.

Los prompts se guardan en biblioteca/prompts_imagen/[id].txt. Las imágenes
generadas van en biblioteca/imagenes/[id].png y el recetario las embebe solo
si existen: sin imagen, la receta sale igual, sin hueco.

Uso:
    python motor/fotos.py --todas              todas las recetas sin prompt
    python motor/fotos.py --todas --rehacer    rehace también las que ya lo tienen
    python motor/fotos.py <carpeta_paciente>   solo las recetas de ese plan
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from comun import (
    DIR_BIBLIOTECA,
    DIR_DATOS,
    DIR_PACIENTES,
    ErrorNutriOS,
    leer_front_matter,
)

DIR_PROMPTS = DIR_BIBLIOTECA / "prompts_imagen"
DIR_IMAGENES = DIR_BIBLIOTECA / "imagenes"
RUTA_LIBRERIA = DIR_DATOS / "biblioteca_fotografia.md"

# Acento de maquetación → fondo fotográfico, un punto más apagado.
# Tabla del Paso 2 de P3: los fondos funcionan más desaturados que el color
# de la página, y así la foto no compite con la tipografía.
FONDOS = {
    "#F2C4A0": ("beige durazno cálido", "#EBD3C0"),
    "#EFC7C2": ("rosa polvo apagado", "#E5C9C6"),
    "#CDE3D2": ("mint grisáceo frío", "#D9E4E0"),
    "#F2E3B3": ("crema mantequilla suave", "#EDE2C4"),
    "#D7D3E0": ("lavanda gris neutro", "#D8D5DE"),
}

# Variantes con superficie propia: ignoran la tabla de color.
SUPERFICIE_PROPIA = {"C", "H"}

VARIANTES_VALIDAS = set("ABCDEFGHIJK")


def cargar_variantes() -> dict[str, dict]:
    """Extrae las plantillas A–K de la biblioteca de fotografía."""
    if not RUTA_LIBRERIA.exists():
        raise ErrorNutriOS(f"Falta {RUTA_LIBRERIA}. Es la biblioteca de prompts de fotografía.")

    texto = RUTA_LIBRERIA.read_text(encoding="utf-8")
    bloques = re.split(r"^# VARIANTE ", texto, flags=re.MULTILINE)[1:]

    variantes: dict[str, dict] = {}
    for b in bloques:
        letra = b[0].upper()
        if letra not in VARIANTES_VALIDAS:
            continue
        nombre = b.split("\n", 1)[0][1:].strip(" —")
        m = re.search(r"```(.*?)```", b, re.DOTALL)
        if not m:
            continue
        variantes[letra] = {"nombre": nombre, "plantilla": m.group(1).strip()}

    if not variantes:
        raise ErrorNutriOS(
            f"No se encontró ninguna variante en {RUTA_LIBRERIA.name}. "
            "¿Se cambió el formato de los encabezados '# VARIANTE X'?"
        )
    return variantes


def _seccion_foto(cuerpo: str) -> str:
    cuerpo = cuerpo.split("--- NOTA PARA PATY ---")[0]
    m = re.search(r"^##\s+Foto\s*$(.*?)(?=^##\s|\Z)", cuerpo, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return " ".join(m.group(1).split()) if m else ""


def construir_prompt(ruta_receta: Path, variantes: dict[str, dict]) -> tuple[str, dict]:
    meta, cuerpo = leer_front_matter(ruta_receta)
    rid = meta.get("id") or ruta_receta.stem

    letra = str(meta.get("variante_foto") or "").strip().upper()
    if letra not in variantes:
        raise ErrorNutriOS(
            f"{ruta_receta.name}: 'variante_foto' es «{letra or 'vacío'}» y no existe en la "
            f"biblioteca. Valores válidos: {', '.join(sorted(variantes))}.\n"
            "    Lo asigna P1 al crear la receta, según la forma física del plato."
        )

    sujeto = _seccion_foto(cuerpo)
    if not sujeto:
        raise ErrorNutriOS(
            f"{ruta_receta.name}: falta la sección '## Foto' con la descripción del sujeto.\n"
            "    Sin ella el generador improvisa el plato. La escribe P1."
        )

    # Las plantillas continúan la frase después de [SUJETO] ("... Servido sobre
    # un plato de cerámica mate"), así que el punto final del párrafo sobra.
    prompt = variantes[letra]["plantilla"].replace("[SUJETO]", sujeto.rstrip(". "))

    acento = str(meta.get("acento") or "").strip().upper()
    if letra in SUPERFICIE_PROPIA:
        nombre_fondo, hex_fondo = "superficie propia de la variante", "—"
        prompt = prompt.replace("[COLOR DE FONDO]", "la superficie descrita")
    else:
        nombre_fondo, hex_fondo = FONDOS.get(acento, ("beige durazno cálido", "#EBD3C0"))
        # El color se nombra dos veces a propósito: algunos modelos lavan los
        # fondos hacia el hueso neutro si solo aparece una vez.
        prompt = prompt.replace("[COLOR DE FONDO]", f"{nombre_fondo} {hex_fondo}")

    props = str(meta.get("props_foto") or "").strip()
    prompt = prompt.replace("[PROPS]", props)
    # Sin props queda una línea vacía en medio de un bloque: se compacta.
    prompt = re.sub(r"\n{3,}", "\n\n", prompt).strip()

    info = {
        "id": rid,
        "titulo": meta.get("titulo", rid),
        "variante": letra,
        "variante_nombre": variantes[letra]["nombre"],
        "fondo": nombre_fondo,
        "fondo_hex": hex_fondo,
        "tiene_imagen": (DIR_IMAGENES / f"{rid}.png").exists(),
    }
    return prompt, info


def recetas_objetivo(args) -> list[Path]:
    if args.paciente:
        ruta_plan = DIR_PACIENTES / args.paciente / "plan.json"
        if not ruta_plan.exists():
            raise ErrorNutriOS(f"No existe {ruta_plan}.")
        plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
        rutas = [DIR_BIBLIOTECA / f"{rid}.md" for rid in plan.get("recetas_usadas", [])]
        return [r for r in rutas if r.exists()]
    return [p for p in sorted(DIR_BIBLIOTECA.glob("*.md")) if not p.name.startswith("_")]


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera los prompts de fotografía de las recetas.")
    ap.add_argument("paciente", nargs="?", help="carpeta de paciente; si se omite, usa --todas")
    ap.add_argument("--todas", action="store_true", help="toda la biblioteca")
    ap.add_argument("--rehacer", action="store_true", help="rehace los prompts ya existentes")
    args = ap.parse_args()

    if not args.paciente and not args.todas:
        ap.error("indica una carpeta de paciente o usa --todas")

    try:
        variantes = cargar_variantes()
        objetivo = recetas_objetivo(args)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    DIR_PROMPTS.mkdir(parents=True, exist_ok=True)
    DIR_IMAGENES.mkdir(parents=True, exist_ok=True)

    hechos, saltados, fallos = [], 0, []
    for ruta in objetivo:
        destino = DIR_PROMPTS / f"{ruta.stem}.txt"
        if destino.exists() and not args.rehacer:
            saltados += 1
            try:
                _, info = construir_prompt(ruta, variantes)
                hechos.append(info)
            except ErrorNutriOS:
                pass
            continue
        try:
            prompt, info = construir_prompt(ruta, variantes)
        except ErrorNutriOS as e:
            fallos.append(str(e))
            continue
        destino.write_text(prompt + "\n", encoding="utf-8")
        hechos.append(info)

    for f in fallos:
        print(f"  ✗ {f}")

    if hechos:
        print()
        print(f"  {'RECETA':<32} {'VAR':<4} {'FONDO':<26} IMAGEN")
        print(f"  {'-'*32} {'-'*4} {'-'*26} {'-'*6}")
        for i in sorted(hechos, key=lambda x: x["titulo"]):
            marca = "sí" if i["tiene_imagen"] else "—"
            print(f"  {i['titulo'][:32]:<32} {i['variante']:<4} {i['fondo'][:26]:<26} {marca}")

    reparto: dict[str, int] = {}
    for i in hechos:
        reparto[i["variante"]] = reparto.get(i["variante"], 0) + 1
    if len(hechos) >= 10:
        for v, n in sorted(reparto.items()):
            if n / len(hechos) > 0.30:
                print(f"\n  ⚠ La variante {v} acapara {n}/{len(hechos)} recetas (más del 30 %).")
                print("    Revisa esas fichas: el recetario se verá plantillado.")

    sin_imagen = [i for i in hechos if not i["tiene_imagen"]]
    print()
    print(f"✓ {len(hechos) - saltados} prompt(s) nuevo(s), {saltados} ya existían.")
    print(f"  → {DIR_PROMPTS}")
    if sin_imagen:
        print()
        print(f"  Faltan {len(sin_imagen)} imagen(es). Pega cada prompt en el generador y guarda")
        print(f"  el resultado como  {DIR_IMAGENES.name}/[id].png  con el id exacto de la receta.")
        print("  El recetario las embebe solas; sin imagen, la receta sale igual.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
