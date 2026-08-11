"""
Chequeo del sistema — Nutri-OS

Verifica de una sola pasada que el entorno y los datos están sanos:
dependencias, protocolos, biblioteca y fichas de pacientes.

Es lo primero que hay que correr tras clonar el repositorio o tras
tocar un protocolo a mano.

Uso:
    python motor/revisar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

errores: list[str] = []
avisos: list[str] = []


def linea(ok: bool, texto: str) -> None:
    print(f"  {'✓' if ok else '✗'} {texto}")


print("\n— Dependencias —")
for mod, paquete in [("yaml", "PyYAML"), ("jinja2", "Jinja2"), ("weasyprint", "weasyprint")]:
    try:
        __import__(mod)
        linea(True, paquete)
    except ImportError:
        linea(False, f"{paquete} — falta. Instala con: pip install -r requirements.txt")
        errores.append(paquete)

if errores:
    print("\n✗ Faltan dependencias; el resto del chequeo no puede ejecutarse.\n")
    raise SystemExit(1)

import yaml  # noqa: E402

sys.path.insert(0, str(RAIZ / "motor"))
from comun import (  # noqa: E402
    DIR_BIBLIOTECA,
    DIR_DATOS,
    DIR_PACIENTES,
    DIR_PROTOCOLOS,
    ErrorNutriOS,
    cargar_biblioteca,
    leer_front_matter,
)

print("\n— Protocolos —")
for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
    try:
        d = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        faltan = [c for c in ("id", "nombre", "comidas") if c not in d]
        if faltan:
            linea(False, f"{ruta.name} — faltan campos: {', '.join(faltan)}")
            errores.append(ruta.name)
        else:
            comps = {c for m in d["comidas"] for c in m["componentes"]}
            linea(True, f"{ruta.name} — {len(d['comidas'])} comidas, {len(comps)} componentes")
    except yaml.YAMLError as e:
        linea(False, f"{ruta.name} — YAML mal formado: {str(e).splitlines()[0]}")
        errores.append(ruta.name)

print("\n— Alimentos base —")
try:
    d = yaml.safe_load((DIR_DATOS / "alimentos_base.yaml").read_text(encoding="utf-8"))
    total = sum(len(v or []) for v in d.values())
    linea(True, f"{total} alimentos en {len(d)} componentes")
except Exception as e:
    linea(False, f"alimentos_base.yaml — {e}")
    errores.append("alimentos_base.yaml")

def _fm(receta) -> bool:
    try:
        meta, _ = leer_front_matter(RAIZ / receta.ruta)
        return bool(str(meta.get("variante_foto") or "").strip())
    except Exception:
        return False


print("\n— Biblioteca —")
try:
    recetas, avs = cargar_biblioteca()
    linea(True, f"{len(recetas)} receta(s) legible(s)")
    for a in avs:
        linea(False, a)
        errores.append(a)
    sin_probar = [r.id for r in recetas if not r.validada_en_cocina]
    if sin_probar:
        avisos.append(f"{len(sin_probar)} receta(s) sin validar en cocina")
    huerfanas = [r.id for r in recetas if not r.momento]
    if huerfanas:
        avisos.append(f"sin campo 'momento' (no entrarán en ningún plan): {', '.join(huerfanas)}")
except ErrorNutriOS as e:
    linea(False, str(e))
    errores.append("biblioteca")

print("\n— Fotografía —")
try:
    from fotos import DIR_IMAGENES, DIR_PROMPTS, cargar_variantes
    variantes = cargar_variantes()
    linea(True, f"{len(variantes)} variantes en la biblioteca ({', '.join(sorted(variantes))})")
    n_prompts = len(list(DIR_PROMPTS.glob("*.txt"))) if DIR_PROMPTS.exists() else 0
    n_img = len(list(DIR_IMAGENES.glob("*.png"))) if DIR_IMAGENES.exists() else 0
    linea(True, f"{n_prompts} prompt(s) generado(s) · {n_img} imagen(es) guardada(s)")
    sin_variante = [r.id for r in recetas if not _fm(r)]
    if sin_variante:
        avisos.append(f"sin 'variante_foto': {', '.join(sin_variante)}")
    if n_img < len(recetas):
        avisos.append(f"{len(recetas) - n_img} receta(s) sin imagen (el recetario sale igual, sin foto)")
except ErrorNutriOS as e:
    linea(False, str(e))
    errores.append("fotografia")

print("\n— Pacientes —")
carpetas = [p for p in sorted(DIR_PACIENTES.iterdir()) if p.is_dir()]
if not carpetas:
    linea(True, "sin carpetas de paciente")
for c in carpetas:
    ficha = c / "ficha.md"
    if not ficha.exists():
        linea(True, f"{c.name} — sin ficha todavía (falta la Fase 1)")
        continue
    try:
        meta, _ = leer_front_matter(ficha)
        if meta.get("bloqueantes"):
            linea(False, f"{c.name} — ficha con bloqueantes: {meta['bloqueantes']}")
            avisos.append(f"{c.name}: ficha bloqueada")
        else:
            linea(True, f"{c.name} — {meta.get('edad_texto','?')}, protocolo {meta.get('protocolo_sugerido','?')}")
    except ErrorNutriOS as e:
        linea(False, f"{c.name} — {e}")
        errores.append(c.name)

print()
for a in avisos:
    print(f"  ⚠ {a}")
print()
if errores:
    print(f"✗ {len(errores)} problema(s) que hay que corregir.\n")
    raise SystemExit(1)
print("✓ Todo en orden.\n")
