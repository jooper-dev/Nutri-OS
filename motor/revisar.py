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

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Lo mismo que hace comun.consola_utf8, repetido aquí a propósito: este script
# tiene que poder decir "falta PyYAML" con sus ✓ y ✗, y comun.py importa yaml
# en su cabecera, así que no se le puede pedir ayuda antes de comprobarlo.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass

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
    CLAVES_PROTOCOLO_CONSUMIDAS,
    CLAVES_PROTOCOLO_DOCUMENTALES,
    CLAVES_PROTOCOLO_SOLO_AVISO,
    DIR_BIBLIOTECA,
    DIR_DATOS,
    DIR_PACIENTES,
    DIR_PROTOCOLOS,
    ErrorNutriOS,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_protocolo,
    comprobar_rango_edad,
    leer_front_matter,
    normalizar,
    resolver_regla_acoplada,
)

CLAVES_PROTOCOLO_VALIDAS = (
    CLAVES_PROTOCOLO_CONSUMIDAS
    | CLAVES_PROTOCOLO_SOLO_AVISO
    | CLAVES_PROTOCOLO_DOCUMENTALES
)

print("\n— Protocolos —")
for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
    try:
        d = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        faltan = [
            c
            for c in ("id", "nombre", "edad_min_meses", "edad_max_meses", "comidas")
            if c not in d
        ]
        if faltan:
            linea(False, f"{ruta.name} — faltan campos: {', '.join(faltan)}")
            errores.append(ruta.name)
        else:
            comps = {c for m in d["comidas"] for c in m["componentes"]}
            linea(True, f"{ruta.name} — {len(d['comidas'])} comidas, {len(comps)} componentes")

        # Una clave que el motor no consume no falla en ninguna parte: el motor
        # sencillamente no la mira, y quien escribió el protocolo se queda
        # creyendo que la regla se aplica. Así vivieron años 'reglas_exclusion',
        # 'prioridades' y 'cena_puede_repetir_almuerzo'.
        sobrantes = sorted(set(d) - CLAVES_PROTOCOLO_VALIDAS)
        if sobrantes:
            linea(
                False,
                f"{ruta.name} — claves que el motor no consume: {', '.join(sobrantes)}. "
                f"O se implementan, o se retiran del archivo: dejarlas ahí hace creer "
                f"que la regla se aplica. Las válidas están en "
                f"motor/comun.py (CLAVES_PROTOCOLO_*).",
            )
            errores.append(ruta.name)
    except yaml.YAMLError as e:
        linea(False, f"{ruta.name} — YAML mal formado: {str(e).splitlines()[0]}")
        errores.append(ruta.name)

print("\n— Reglas acopladas —")
for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
    try:
        d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        continue
    problemas = []
    for regla in d.get("reglas_acopladas") or []:
        _, problema = resolver_regla_acoplada(regla, d)
        if problema:
            problemas.append(
                f"«{regla.get('si', '?')} -> {regla.get('entonces', '?')}»: {problema}"
            )
    if problemas:
        for problema in problemas:
            linea(False, f"{ruta.name} — regla no resoluble {problema}")
        errores.append(ruta.name)
    else:
        linea(
            True,
            f"{ruta.name} — {len(d.get('reglas_acopladas') or [])} regla(s) resuelven",
        )

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

print("\n— Claves de los protocolos —")
# Una clave de rotación o de frecuencia que no corresponde a ningún alimento no
# falla en ninguna parte: el motor no encuentra candidatos, degrada la ranura y
# el plan sale con otra cosa. Un 'camotes' por 'camote' se pierde así. Se
# comprueba aquí, que es lo que se ejecuta después de editar un protocolo.
if "biblioteca" in errores:
    linea(False, "no se puede comprobar: la biblioteca no cargó")
else:
    universo = recetas + cargar_alimentos_base()
    for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
        d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        claves = [
            (r["componente"], k)
            for r in (d.get("rotaciones") or [])
            for k in (r.get("reparto") or {})
        ]
        claves += [
            (r["componente"], r["familia"])
            for r in (d.get("frecuencias_semanales") or [])
            if r.get("familia")
        ]
        claves += [
            (comp, alimento)
            for comp, lista in (d.get("prioridades") or {}).items()
            for alimento in (lista or [])
        ]
        huerfanas = sorted(
            {
                f"{comp}/{clave}"
                for comp, clave in claves
                if not any(o.componente == comp and o.responde_a(clave) for o in universo)
            }
        )
        if huerfanas:
            linea(False, f"{ruta.name} — sin ningún alimento detrás: {', '.join(huerfanas)}")
            errores.append(ruta.name)
        else:
            linea(True, f"{ruta.name} — {len(claves)} clave(s) de rotación/frecuencia resuelven")

print("\n— Frecuencias contra la edad del protocolo —")
# Que una familia tenga alimentos detrás no basta: tienen que ser alimentos que
# ese paciente pueda comer a la edad del protocolo. El protocolo de 6 meses pedía
# 2 menestras por semana cuando las tres menestras del catálogo empezaban a los 7
# y 8 meses: contradicción entre protocolo y catálogo, imposible de cumplir por
# construcción, y el resultado era un plan degradado en silencio con la misma
# proteína seis días de siete. Este chequeo tenía que haberlo cazado.
if "biblioteca" in errores:
    linea(False, "no se puede comprobar: la biblioteca no cargó")
else:
    for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
        d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        edad_min = d.get("edad_min_meses")
        edad_max = d.get("edad_max_meses")
        if edad_min is None or edad_max is None:
            continue
        imposibles, tardias = [], []
        for regla in d.get("frecuencias_semanales") or []:
            comp = regla.get("componente")
            fam = regla.get("familia")
            etiqueta = f"{comp}/{fam}" if fam else str(comp)
            viables = [
                o
                for o in universo
                if o.componente == comp and not o.nunca_recomendar and o.responde_a(fam or "")
            ]
            if not viables:
                continue  # ya lo dice el bloque anterior
            edades = sorted(o.edad_min_meses for o in viables)
            if edades[0] > int(edad_max):
                imposibles.append(f"{etiqueta} (la más temprana, {edades[0]} m)")
            elif edades[0] > int(edad_min):
                tardias.append(f"{etiqueta} (nada antes de los {edades[0]} m)")
        for texto in imposibles:
            linea(
                False,
                f"{ruta.name} — {texto}: ninguna opción es apta dentro del rango "
                f"{edad_min}–{edad_max} m que declara el protocolo. La regla no se puede "
                f"cumplir nunca y el motor degradará la ranura en silencio. "
                f"Corrige 'edad_min_meses' en datos/alimentos_base.yaml si el alimento sí "
                f"es apto a esa edad, o retira la frecuencia del protocolo.",
            )
            errores.append(ruta.name)
        for texto in tardias:
            avisos.append(f"{ruta.name}: {texto}; los pacientes más pequeños del rango la degradarán")
        if not imposibles:
            linea(True, f"{ruta.name} — todas las frecuencias tienen opción en {edad_min}–{edad_max} m")

print("\n— Alérgenos declarados contra ingredientes —")
# La misma avena estaba etiquetada de tres formas distintas en tres recetas, así
# que un niño con evitación de gluten quedaba filtrado de una y expuesto a las
# otras dos. Declarar el alérgeno a mano receta por receta se desincroniza solo;
# esto lo comprueba contra la lista de ingredientes.
RUTA_ALERGENOS = DIR_DATOS / "alergenos_ingredientes.yaml"


def _clave(texto: str) -> str:
    """La línea normalizada y con topes, para buscar palabras completas."""
    return "_" + normalizar(texto) + "_"


def _lineas_ingredientes(cuerpo: str) -> list[str]:
    m = re.search(
        r"^##\s+Ingredientes\s*$(.*?)(?=^##\s|\Z)", cuerpo, re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    if not m:
        return []
    return [l.strip() for l in m.group(1).splitlines() if l.strip().startswith("•")]


def _alergenos_implicados(lineas: list[str], tabla: dict) -> set[str]:
    hallados: set[str] = set()
    for linea in lineas:
        clave = _clave(linea)
        for etiqueta, regla in tabla.items():
            if any(_clave(x) in clave for x in (regla.get("excepciones") or [])):
                continue
            if any(_clave(t) in clave for t in (regla.get("terminos") or [])):
                hallados.add(etiqueta)
    return hallados


if "biblioteca" in errores:
    linea(False, "no se puede comprobar: la biblioteca no cargó")
elif not RUTA_ALERGENOS.exists():
    linea(False, f"falta {RUTA_ALERGENOS.name}, que es la tabla de ingredientes → alérgeno")
    errores.append(RUTA_ALERGENOS.name)
else:
    tabla = yaml.safe_load(RUTA_ALERGENOS.read_text(encoding="utf-8")) or {}
    desajustes = 0
    for receta in recetas:
        try:
            meta, cuerpo = leer_front_matter(RAIZ / receta.ruta)
        except ErrorNutriOS:
            continue
        lineas = _lineas_ingredientes(cuerpo)
        if not lineas:
            avisos.append(f"{receta.id}: no se encontró la sección '## Ingredientes'")
            continue
        declarados = {normalizar(a) for a in (meta.get("alergenos_presentes") or [])}
        implicados = _alergenos_implicados(lineas, tabla)
        faltan = sorted(implicados - declarados)
        sobran = sorted(declarados - implicados)
        if faltan:
            desajustes += 1
            linea(
                False,
                f"{receta.id} — sus ingredientes llevan {', '.join(faltan)} y "
                f"'alergenos_presentes' no lo declara. Un falso negativo aquí llega al "
                f"plato de un niño alérgico: añádelo al front-matter, o corrige la "
                f"tabla de datos/alergenos_ingredientes.yaml si el término no "
                f"corresponde.",
            )
            errores.append(receta.id)
        if sobran:
            avisos.append(
                f"{receta.id}: declara {', '.join(sobran)} y ningún ingrediente lo delata "
                f"(declarar de más es seguro, pero descarta la receta para pacientes que "
                f"sí podrían comerla)"
            )
    if not desajustes:
        linea(True, f"{len(recetas)} receta(s) coherentes con sus ingredientes")

print("\n— Componentes sin receta —")
# El recetario solo puede crecer si se sabe dónde le falta. Hoy las 17 recetas
# cubren tres componentes de los escolares y ninguno del protocolo de 6 meses,
# y eso no se veía por ningún lado: el plan de un lactante salía con un solo
# PDF y nadie explicaba por qué.
if "biblioteca" in errores:
    linea(False, "no se puede comprobar: la biblioteca no cargó")
else:
    con_receta = {r.componente for r in recetas}
    for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
        d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        comps = sorted({c for m in d.get("comidas") or [] for c in m["componentes"]})
        sin = [c for c in comps if c not in con_receta]
        if sin:
            # Ni ✓ ni ✗: es un hueco de biblioteca, no un fallo de configuración.
            print(f"  · {ruta.name} — {len(sin)} de {len(comps)} componentes sin ninguna receta")
            avisos.append(
                f"{ruta.name}: sin ninguna receta en la biblioteca — {', '.join(sin)}. "
                f"Esas ranuras solo pueden llenarse con alimentos base."
            )
        else:
            linea(True, f"{ruta.name} — todos los componentes tienen alguna receta")

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
            continue
        linea(True, f"{c.name} — {meta.get('edad_texto','?')}, protocolo {meta.get('protocolo_sugerido','?')}")

        # El protocolo lo elige un modelo en la Fase 1, y un escolar con el
        # protocolo de ablactancia produce un plan entero, válido y equivocado.
        # Comprobarlo es aritmética, y por eso lo hace el código.
        if meta.get("edad_meses") is None or not meta.get("protocolo_sugerido"):
            continue
        protocolo = cargar_protocolo(str(meta["protocolo_sugerido"]))
        estado, mensaje = comprobar_rango_edad(protocolo, meta)
        if estado == "fuera_sin_justificar":
            linea(False, f"{c.name} — {mensaje}")
            errores.append(c.name)
        elif estado == "fuera_justificado":
            avisos.append(f"{c.name}: {mensaje}")
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
