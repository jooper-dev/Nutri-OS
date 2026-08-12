"""
Renderizador — Nutri-OS · Fase 7

Convierte el plan validado en dos PDF terminados:

    Plan_[Paciente].pdf        la parrilla semanal
    Recetario_[Paciente].pdf   solo las recetas que aparecen en ese plan

Sin Canva, sin Google Slides, sin etiquetas {{ }} que reemplazar una por una.
La "Leyenda de énfasis" de P1 la aplica la hoja de estilo: las cantidades y
los verbos salen en negrita solos.

Antes de maquetar el recetario, las recetas de este plan que no tengan foto la
consiguen solas: prompt de imagen si falta y llamada al generador. No es un paso
aparte que haya que recordar. Si no hay clave o la API falla, se avisa en una
línea y esas recetas salen con su banda de color; el render no se detiene nunca
por una fotografía.

Uso:
    python motor/render.py <nombre_carpeta_paciente>
    python motor/render.py <carpeta> --caras       dos hojas por semana
    python motor/render.py <carpeta> --sin-fotos   no genera imágenes
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML

from comun import (
    DIAS,
    DIR_BIBLIOTECA,
    DIR_PACIENTES,
    ErrorNutriOS,
    huella_plan,
    leer_front_matter,
)

PLANTILLAS = Path(__file__).resolve().parent / "plantillas"


# ---------------------------------------------------------------------------
# Lectura del cuerpo markdown de una receta
# ---------------------------------------------------------------------------


def _negritas(texto: str) -> str:
    """Convierte **x** en <strong>x</strong>, escapando el resto."""
    partes = re.split(r"\*\*(.+?)\*\*", texto)
    out = []
    for i, p in enumerate(partes):
        out.append(f"<strong>{html.escape(p)}</strong>" if i % 2 else html.escape(p))
    return "".join(out)


def _seccion(cuerpo: str, titulo: str) -> str:
    m = re.search(
        rf"^##\s+{titulo}\s*$(.*?)(?=^##\s|\Z|^---\s*NOTA PARA PATY)",
        cuerpo,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _vinetas(bloque: str) -> list[str]:
    return [_negritas(l.lstrip("• ").strip()) for l in bloque.splitlines() if l.strip().startswith("•")]


def leer_receta(rid: str) -> dict | None:
    ruta = DIR_BIBLIOTECA / f"{rid}.md"
    if not ruta.exists():
        return None
    meta, cuerpo = leer_front_matter(ruta)
    rid = str(meta.get("id") or rid)

    # La Nota para Paty es interna: nunca entra al PDF de la paciente.
    # La Nota para Paty y la descripción para el generador de imágenes son
    # internas: ninguna de las dos entra al PDF de la paciente.
    cuerpo = cuerpo.split("--- NOTA PARA PATY ---")[0]
    cuerpo = re.split(r"^##\s+Foto\s*$", cuerpo, flags=re.MULTILINE)[0]

    lineas = [l.strip() for l in cuerpo.splitlines()]
    stats = etiquetas = ""
    for l in lineas:
        if not l or l.startswith("#"):
            continue
        if not stats and "·" in l and any(c.isdigit() for c in l):
            stats = l
        elif stats and not etiquetas and "·" in l and not l.startswith("•"):
            etiquetas = l
            break

    pasos_txt = _seccion(cuerpo, "Preparación")
    pasos = [
        _negritas(re.sub(r"^\d{2}\s+", "", l.strip()))
        for l in pasos_txt.splitlines()
        if re.match(r"^\d{2}\s", l.strip())
    ]

    imagen = DIR_BIBLIOTECA / "imagenes" / f"{rid}.png"
    return {
        "imagen": imagen.resolve().as_uri() if imagen.exists() else None,
        "meta": meta,
        "stats": stats,
        "etiquetas": etiquetas,
        "nota": _seccion(cuerpo, "Nota de la Nutricionista"),
        "ingredientes": _vinetas(_seccion(cuerpo, "Ingredientes")),
        "pasos": pasos,
        "ideas": _vinetas(_seccion(cuerpo, "Ideas")),
        "conservacion": _seccion(cuerpo, "Conservación"),
    }


# ---------------------------------------------------------------------------
# Fotografía: parte del render, no un paso aparte
# ---------------------------------------------------------------------------


def asegurar_fotos(plan: dict) -> None:
    """Consigue la foto de las recetas de este plan que todavía no la tengan.

    Vive aquí dentro y no en un comando suelto por una razón medida: un paso
    opcional que hay que acordarse de ejecutar es un paso que no se ejecuta.
    `generar_imagenes.py` existía, funcionaba y estaba documentado como
    opcional — y en todo el MVP no se generó ni una sola imagen. Ahora el
    recetario pide sus fotos solo, justo antes de maquetarse.

    Blindado de punta a punta: sin clave, sin red, con la API caída o con una
    receta sin sección «Foto», se avisa en una línea y esa receta sale con su
    banda de color. **Ninguna fotografía detiene un plan.** Por eso el `except`
    es tan ancho: aquí un fallo inesperado tiene que costar una foto, nunca los
    dos PDF que Paty está esperando.
    """
    ids = list(plan.get("recetas_usadas") or [])
    if not ids:
        return

    try:
        from fotos import asegurar_prompts
        from generar_imagenes import asegurar_imagenes

        listos, avisos = asegurar_prompts(ids)
        for a in avisos:
            print(f"  ⚠ foto: {a}")
        r = asegurar_imagenes(listos)
    except Exception as e:  # noqa: BLE001 — ver el docstring
        print(f"  ⚠ fotos: no se pudieron generar ({e}). El recetario sale con la banda de color.")
        return

    pendientes = len(ids) - len(r["saltadas"]) - len(r["hechas"])

    if r["motivo"]:
        print(
            f"  ⚠ fotos: no hay clave de API — {pendientes} receta(s) salen con la banda de "
            "color. Pon GEMINI_API_KEY en .env y vuelve a renderizar."
        )
        return

    if r["hechas"]:
        print(f"  ✓ fotos: {len(r['hechas'])} nueva(s) · {len(r['saltadas'])} ya existían")
    if r["fallidas"]:
        print(f"  ⚠ fotos: {len(r['fallidas'])} fallaron y salen con la banda de color (error arriba)")
    if r["sin_prompt"]:
        print(f"  ⚠ fotos: sin prompt de imagen — {', '.join(r['sin_prompt'])}")


# ---------------------------------------------------------------------------


def construir_hojas(plan: dict, caras: bool) -> list[dict]:
    """
    Convierte el plan en hojas de horario.

    Una hoja = una página apaisada con los días en columnas y las comidas en
    filas. Con `caras`, cada semana se parte en dos (lunes–jueves / viernes–
    domingo) para que la letra respire: es lo que Paty hace a mano cuando una
    semana entera no se lee bien impresa.
    """
    hojas: list[dict] = []
    for s_ in plan["semanas"]:
        dias = [d for d in DIAS if d in s_["dias"]]
        grupos = [("Cara A", dias[:4]), ("Cara B", dias[4:])] if caras else [(None, dias)]

        for cara, subdias in grupos:
            if not subdias:
                continue
            # Las franjas horarias de esta hoja, en el orden real del día.
            franjas, vistas = [], set()
            for d in subdias:
                for cid, comida in s_["dias"][d].items():
                    if cid in vistas:
                        continue
                    vistas.add(cid)
                    franjas.append({"id": cid, "nombre": comida["nombre"], "hora": comida.get("hora", "")})

            celdas = {
                d: {f["id"]: s_["dias"][d].get(f["id"], {}).get("items", []) for f in franjas}
                for d in subdias
            }
            hojas.append({
                "semana": s_["semana"],
                "cara": cara,
                "dias": subdias,
                "franjas": franjas,
                "celdas": celdas,
                # Reparte el alto útil de la hoja entre las franjas que tenga
                # este protocolo, para que 5 comidas y 2 comidas llenen igual
                # la página. En modo caras la letra es mayor y las celdas ya
                # crecen solas: forzar el alto ahí desborda la hoja.
                "alto_fila": round(136 / max(1, len(franjas)), 1) if len(subdias) > 4 else 0,
            })
    return hojas


def _entorno() -> Environment:
    return Environment(
        loader=FileSystemLoader(PLANTILLAS),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _slug(nombre: str) -> str:
    s = re.sub(r"[^\w\s-]", "", nombre, flags=re.UNICODE).strip()
    return re.sub(r"[\s]+", "_", s)


def _escribir_pdf(doc: str, destino: Path, hojas: list[CSS], base: str) -> None:
    """Escribe el PDF, o explica en castellano por qué no pudo.

    Windows bloquea un archivo abierto en un visor, y ese es justo el estado
    normal en la Puerta de Paty: ella tiene el PDF delante, pide un cambio, y el
    render moría con una traza de Python de doce líneas sobre PermissionError.
    El plan estaba bien y el motor también; solo había una pestaña abierta.
    """
    try:
        HTML(string=doc, base_url=base).write_pdf(destino, stylesheets=hojas)
    except PermissionError as e:
        raise ErrorNutriOS(
            f"No se pudo escribir {destino.name}: está abierto en otro programa.\n"
            "    Ciérralo (visor de PDF, navegador o vista previa) y vuelve a renderizar.\n"
            "    El plan no tiene nada malo: es el archivo, que está en uso."
        ) from e


def renderizar(nombre_carpeta: str, caras: bool = False, fotos: bool = True) -> list[Path]:
    carpeta = DIR_PACIENTES / nombre_carpeta
    ruta_plan = carpeta / "plan.json"
    if not ruta_plan.exists():
        raise ErrorNutriOS(f"No existe {ruta_plan}. Ejecuta antes motor/ensamblar.py")

    reporte = carpeta / "reporte_qa.md"
    if not reporte.exists():
        raise ErrorNutriOS(
            "Falta reporte_qa.md: este plan no ha pasado por el validador.\n"
            "    Ejecuta motor/validar.py antes de renderizar."
        )
    texto_reporte = reporte.read_text(encoding="utf-8")
    if "**BLOQUEADO**" in texto_reporte:
        raise ErrorNutriOS(
            "El validador marcó este plan como BLOQUEADO. No se renderiza.\n"
            "    Revisa los errores en reporte_qa.md, corrige y vuelve a ensamblar."
        )

    # Que exista un reporte APTO no basta: tiene que ser el reporte DE ESTE plan.
    # Validar una versión y volver a ensamblar otra sin validarla dejaba en la
    # carpeta un visto bueno que no correspondía a nada, y los PDF salían igual.
    marca = re.search(r"sha256:([0-9a-f]{64})", texto_reporte)
    if not marca:
        raise ErrorNutriOS(
            "reporte_qa.md no lleva la huella del plan que validó: se generó con una "
            "versión anterior del validador.\n"
            "    Ejecuta motor/validar.py " + nombre_carpeta + " y vuelve a renderizar."
        )
    if marca.group(1) != huella_plan(ruta_plan):
        raise ErrorNutriOS(
            "plan.json ha cambiado desde que se validó: el visto bueno de reporte_qa.md "
            "no corresponde a este plan y no se renderiza.\n"
            "    Suele pasar tras volver a ensamblar sin validar después.\n"
            "    Ejecuta motor/validar.py " + nombre_carpeta + " —o motor/correr.py "
            + nombre_carpeta + ", que hace las dos cosas— y vuelve a renderizar."
        )

    plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
    env = _entorno()
    css_base = CSS(filename=str(PLANTILLAS / "estilo.css"))
    css_plan = CSS(filename=str(PLANTILLAS / "plan.css"))
    base = str(PLANTILLAS)
    salidas: list[Path] = []
    slug = _slug(plan["paciente"])

    # --- Plan ---------------------------------------------------------------
    hojas = construir_hojas(plan, caras)
    doc = env.get_template("plan.html").render(p=plan, hojas=hojas)
    destino = carpeta / f"Plan_{slug}.pdf"
    _escribir_pdf(doc, destino, [css_base, css_plan], base)
    salidas.append(destino)

    # --- Recetario ----------------------------------------------------------
    # Las fotos, antes de leer las recetas: `leer_receta` mira si el PNG existe,
    # así que una imagen generada después no entraría en el PDF de esta corrida.
    if fotos:
        asegurar_fotos(plan)

    recetas, faltantes = [], []
    for rid in plan.get("recetas_usadas", []):
        r = leer_receta(rid)
        (recetas.append(r) if r else faltantes.append(rid))
    if faltantes:
        print(f"  ⚠ recetas no encontradas en la biblioteca: {', '.join(faltantes)}")

    if recetas:
        recetas.sort(key=lambda r: r["meta"].get("titulo", ""))
        doc = env.get_template("recetario.html").render(p=plan, recetas=recetas)
        destino = carpeta / f"Recetario_{slug}.pdf"
        _escribir_pdf(doc, destino, [css_base], base)
        salidas.append(destino)

    return salidas


def main() -> int:
    ap = argparse.ArgumentParser(description="Renderiza los PDF de un paciente.")
    ap.add_argument("paciente")
    ap.add_argument(
        "--caras",
        action="store_true",
        help="parte cada semana en dos hojas (Cara A: lun–jue · Cara B: vie–dom), con letra más grande",
    )
    ap.add_argument(
        "--sin-fotos",
        action="store_true",
        help="no genera las fotos que falten; las recetas sin imagen salen con su banda de color",
    )
    args = ap.parse_args()

    try:
        salidas = renderizar(args.paciente, caras=args.caras, fotos=not args.sin_fotos)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    print("✓ PDF generados:")
    for s in salidas:
        print(f"  → {s}  ({s.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
