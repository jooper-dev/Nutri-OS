"""
Renderizador — Nutri-OS · Fase 7

Convierte el plan validado en dos PDF terminados:

    Plan_[Paciente].pdf        la parrilla semanal
    Recetario_[Paciente].pdf   solo las recetas que aparecen en ese plan

Sin Canva, sin Google Slides, sin etiquetas {{ }} que reemplazar una por una.
La "Leyenda de énfasis" de P1 la aplica la hoja de estilo: las cantidades y
los verbos salen en negrita solos.

Cada receta ocupa DOS páginas: portada e instrucciones. La portada es la foto a
sangre con el nombre, la edad mínima y los alérgenos encima; y cuando no hay
foto —que hoy es el caso normal— es una portada tipográfica con el nombre y la
nota de la nutricionista en grande. Nunca se deja en blanco ni se rellena con un
marcador.

**El render no genera ninguna imagen.** Usa la que corresponda a la firma visual
de la receta, y si no hay, lo dice y sigue. El sistema pide fotos; no las
fabrica.

Uso:
    python motor/render.py <nombre_carpeta_paciente>
    python motor/render.py <carpeta> --caras       dos hojas por semana
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

import firma_visual
from comun import (
    DIAS,
    DIR_PACIENTES,
    DIR_RECETAS_PACIENTE,
    ErrorNutriOS,
    cargar_recetas_instanciadas,
    huella_plan,
    leer_front_matter,
    normalizar,
)

PLANTILLAS = Path(__file__).resolve().parent / "plantillas"

# Cómo se escribe cada identificador interno cuando lo va a leer una madre.
#
# La portada del plan imprimía «ALERGIAS: lacteos» y «NO CONSUME: pescado» tal
# cual salían del sistema: en minúscula, sin tildes y con el identificador
# interno. Es un documento que recibe la familia de un paciente, no un volcado
# de la base de datos.
#
# Vive aquí, en la capa de presentación, y solo aquí: los identificadores de
# datos/alimentos_base.yaml y de las fichas no cambian, porque de ellos dependen
# el filtrado y el recuento. Lo que se traduce es la impresión.
NOMBRES_VISIBLES = {
    # Etiquetas de alérgeno del catálogo
    "lacteos": "Lácteos",
    "gluten": "Gluten",
    "huevo": "Huevo",
    "mani": "Maní",
    "frutos_secos": "Frutos secos",
    "pescado": "Pescado",
    "soya": "Soya",
    "ajonjoli": "Ajonjolí",
    "carne_mamifero": "Carnes rojas (res, cerdo, cordero)",
    # Alimentos que suelen aparecer escritos como rechazo
    "res": "Carne de res",
    "pollo": "Pollo",
    "pavita": "Pavita",
    "higado": "Hígado",
    "sangrecita": "Sangrecita",
    "menestra": "Menestras",
    "brocoli": "Brócoli",
    "espinaca": "Espinaca",
    "vainita": "Vainita",
    "betarraga": "Betarraga",
    "zanahoria": "Zanahoria",
    "zapallo": "Zapallo",
    "camote": "Camote",
    "platano": "Plátano",
    "papaya": "Papaya",
    "quinua": "Quinua",
    "kiwicha": "Kiwicha",
    "canihua": "Cañihua",
    "yuca": "Yuca",
    "avena": "Avena",
    "yogurt": "Yogurt",
    "ensalada": "Ensaladas",
}


def nombre_visible(clave: str) -> str:
    """El identificador interno, escrito como se imprime."""
    conocido = NOMBRES_VISIBLES.get(normalizar(clave))
    if conocido:
        return conocido
    # Lo que no esté en la tabla se imprime tal como lo escribió Paty en la
    # ficha, solo con la primera letra en mayúscula: si ella puso «brócoli» con
    # tilde, sale con tilde.
    texto = str(clave).replace("_", " ").strip()
    return texto[:1].upper() + texto[1:]


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


def _encabezado(cuerpo: str) -> tuple[str, str]:
    """Los stats y el bloque de alérgenos, leídos SOLO del encabezado.

    El bug que arregla esta función salía impreso. `Dura: 3 días refri · 1
    congelador` aparecía **dos veces** en Compota de pera, Milanesa de pollo y
    Panqueques de avena —una vez pegada a la cabecera y otra al final— y en
    Quinua licuada se quedaba huérfana ocupando una página ella sola.

    La causa no era de maquetación: era de lectura. La versión anterior buscaba
    el bloque de alérgenos recorriendo el cuerpo ENTERO en busca de «la primera
    línea con un · que no empiece por viñeta». En las recetas que sí lo tenían,
    lo encontraba y paraba. En las que no —que son justamente las que salieron
    sin ninguna etiqueta— seguía bajando, atravesaba ingredientes y preparación,
    y se topaba con `Dura: 3 días refri · 1 congelador`, que cumple la condición
    al pie de la letra. Lo pintaba como etiquetas arriba, y la sección de
    Conservación lo volvía a pintar abajo.

    Las dos anomalías del §2.2.c y del §2.3 eran la misma: las recetas con el
    pie duplicado son exactamente las que no tenían bloque de alérgenos.

    Ahora se mira solo la región del encabezado —entre el `# Título` y el primer
    `## `—, que es donde P1 los pone. Fuera de ahí no hay nada que buscar.
    """
    cabeza = re.split(r"^##\s", cuerpo, maxsplit=1, flags=re.MULTILINE)[0]
    stats = alergenos = ""
    for cruda in cabeza.splitlines():
        l = cruda.strip()
        if not l or l.startswith("#") or l.startswith("•"):
            continue
        if not stats and "·" in l and any(c.isdigit() for c in l):
            stats = l
        elif stats and not alergenos:
            alergenos = l
            break
    return stats, alergenos


def leer_receta(rid: str, carpeta: Path, paciente: str = "") -> dict | None:
    """La receta instanciada de este paciente. Nunca la base.

    Lo que se imprime vive en `pacientes/<paciente>/recetas/`, resuelto contra
    este niño. `/biblioteca/` guarda bases, y una base no se imprime jamás.

    La fotografía ya NO se comparte por identificador de receta: se comparte por
    **firma visual**. La misma base produce platos distintos para niños
    distintos, y si cambian los ingredientes cambia el aspecto: la crema de
    quinua sin fruta se ve igual para cualquier niño y puede heredar la foto,
    pero la crema con manzana en trozos tiene otra firma y no puede.
    """
    ruta = carpeta / DIR_RECETAS_PACIENTE / f"{rid}.md"
    if not ruta.exists():
        recetas, _ = cargar_recetas_instanciadas(carpeta)
        if rid not in recetas:
            return None
        ruta = recetas[rid]["ruta"]
    meta, cuerpo = leer_front_matter(ruta)
    base = str(meta.get("base") or meta.get("id") or rid)

    # La Nota para Paty y la descripción para el generador de imágenes son
    # internas: ninguna de las dos entra al PDF de la paciente.
    cuerpo = cuerpo.split("--- NOTA PARA PATY ---")[0]
    cuerpo = re.split(r"^##\s+Foto\s*$", cuerpo, flags=re.MULTILINE)[0]

    stats, alergenos = _encabezado(cuerpo)

    pasos_txt = _seccion(cuerpo, "Preparación")
    pasos = [
        _negritas(re.sub(r"^\d{2}\s+", "", l.strip()))
        for l in pasos_txt.splitlines()
        if re.match(r"^\d{2}\s", l.strip())
    ]

    # --- La foto, por firma visual y nunca por identificador ---------------
    # Cuatro puertas, y las cuatro pueden decir que no: la receta no declara su
    # firma, no hay foto para esa firma, el archivo no está, o la resolución no
    # da para una página A4. En los cuatro casos la receta sale con portada
    # tipográfica, que es el caso normal hoy y no la excepción.
    imagen = None
    firma = ""
    motivo_sin_foto = ""
    detalle: dict = {}
    if firma_visual.completa(meta):
        firma, detalle = firma_visual.calcular(meta)
        ruta_img, motivo_sin_foto = firma_visual.imagen_de(firma)
        if ruta_img is not None:
            imagen = ruta_img.resolve().as_uri()
        else:
            firma_visual.registrar_pendiente(firma, detalle, meta, paciente)
    else:
        motivo_sin_foto = (
            "la receta no declara `formato_final` ni `aporte_visual`, así que su "
            "firma visual no se puede calcular y ninguna foto le corresponde"
        )

    foco_x, foco_y = firma_visual.punto_focal(firma) if firma else (0.5, 0.5)

    return {
        "imagen": imagen,
        "firma": firma,
        "detalle_firma": detalle,
        "motivo_sin_foto": motivo_sin_foto,
        "foco": f"{foco_x * 100:.0f}% {foco_y * 100:.0f}%",
        "meta": meta,
        "stats": stats,
        # Nunca vacío: si la receta no declara alérgenos, se dice con todas las
        # letras. El silencio no puede significar dos cosas distintas —«no lleva»
        # y «nadie lo miró»— en un documento que lee la madre de un niño.
        "alergenos": alergenos or "No contiene alérgenos declarables",
        "nota": _seccion(cuerpo, "Nota de la Nutricionista"),
        "ingredientes": _vinetas(_seccion(cuerpo, "Ingredientes")),
        "pasos": pasos,
        "ideas": _vinetas(_seccion(cuerpo, "Ideas")),
        "conservacion": _seccion(cuerpo, "Conservación"),
    }


# ---------------------------------------------------------------------------
# Fotografía: parte del render, no un paso aparte
# ---------------------------------------------------------------------------


def informe_de_fotos(recetas: list[dict]) -> None:
    """Qué falta fotografiar, descrito para que alguien pueda hacerlo.

    **El render ya no genera ninguna imagen.** El sistema las pide; no las
    fabrica. Antes el recetario llamaba solo a la API justo antes de maquetarse
    —lo que resolvía el problema de un paso opcional que nadie ejecutaba—, pero
    con las recetas instanciadas por paciente eso significaba generar una foto
    nueva por cada niño y por cada variante, y decidir sin criterio humano qué
    plato se retrata.

    Lo que hace ahora es dejar la lista escrita: qué firma visual no tiene foto,
    de qué plato es y qué se ve en él. Los comandos sueltos siguen existiendo
    para trabajar la biblioteca aparte.
    """
    faltan = [r for r in recetas if not r["imagen"]]
    if not faltan:
        print(f"  ✓ fotos: las {len(recetas)} recetas tienen imagen para su firma visual")
        return

    print(
        f"  · fotos: {len(faltan)} de {len(recetas)} receta(s) salen con portada "
        f"tipográfica. No es un fallo: es que nadie ha fotografiado todavía ese "
        f"plato con ese aspecto."
    )
    anotadas = 0
    for r in faltan:
        titulo = r["meta"].get("titulo", "?")
        d = r.get("detalle_firma") or {}
        if not r["firma"]:
            # Sin firma no hay nada que encargar: la receta ni siquiera dice
            # cómo se ve. Se pide el dato, no la foto.
            print(f"      {titulo} · {r['motivo_sin_foto']}")
            continue
        anotadas += 1
        se_ve = ", ".join(d.get("visibles") or []) or "nada distinguible"
        print(
            f"      {titulo} · firma {r['firma']} · {r['motivo_sin_foto']}\n"
            f"        qué fotografiar: {d.get('formato', '?')}, se ve {se_ve}, "
            f"carga visual V{d.get('carga_visual', '?')}"
        )
    if anotadas:
        print(
            f"      {anotadas} firma(s) anotadas en "
            f"{firma_visual.RUTA_MANIFIESTO.name} para fotografiar."
        )


# ---------------------------------------------------------------------------


def _comprobar_par(plan: dict, instanciadas: dict, titulos: dict) -> None:
    """Que la grilla y el recetario coincidan pieza por pieza. Si no, no se emite.

    Tres comprobaciones, y las tres se hacen contando:

      1. Toda preparación de la grilla tiene su receta instanciada.
      2. Toda receta que va a imprimirse aparece en algún día de la grilla.
      3. Cada instancia lleva el mismo nombre en los dos documentos.

    Las recetas instanciadas de un control anterior que este plan ya no usa no
    entran en el recetario y no cuentan: el recetario se maqueta desde
    `recetas_usadas`, no desde la carpeta.
    """
    en_grilla: dict[str, set[str]] = {}
    for s_ in plan["semanas"]:
        for dia in s_["dias"].values():
            for comida in dia.values():
                for item in comida["items"]:
                    rid = item.get("receta_id")
                    if rid:
                        en_grilla.setdefault(rid, set()).add(str(item["nombre"]))

    a_imprimir = set(plan.get("recetas_usadas") or [])
    problemas: list[str] = []

    sin_receta = sorted(set(en_grilla) - set(instanciadas))
    if sin_receta:
        problemas.append(
            f"{len(sin_receta)} preparación(es) de la grilla no tienen receta en el "
            f"recetario: {', '.join(sin_receta)}"
        )

    fuera = sorted(a_imprimir - set(en_grilla))
    if fuera:
        problemas.append(
            f"{len(fuera)} receta(s) irían al recetario sin aparecer en ningún día del "
            f"plan: {', '.join(fuera)}"
        )

    for rid in sorted(en_grilla):
        titulo = titulos.get(rid)
        if not titulo:
            continue
        distintos = sorted(n for n in en_grilla[rid] if n != titulo)
        if distintos:
            problemas.append(
                f"«{rid}» se llama «{titulo}» en el recetario y "
                f"«{', '.join(distintos)}» en la grilla"
            )

    if problemas:
        raise ErrorNutriOS(
            "El plan y el recetario no coinciden, así que no se emite ninguno de los "
            "dos:\n  - " + "\n  - ".join(problemas) + "\n"
            "    Un recetario que no corresponde al plan es peor que no tener recetario: "
            "la madre lee un nombre en la grilla, busca la receta y encuentra otra cosa. "
            "En el primer caso real eso significó buscar unas trufas de pecana y "
            "encontrar una receta con mantequilla de maní.\n"
            "    Solución: instancia con prompts/P1_RECETAS.md las que falten, retira de "
            f"{DIR_RECETAS_PACIENTE}/ las que ya no correspondan, y vuelve a ensamblar y "
            "validar."
        )


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


def renderizar(nombre_carpeta: str, caras: bool = False) -> list[Path]:
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
    # Solo para imprimir: el plan en disco conserva sus identificadores.
    plan["alergias_visibles"] = [nombre_visible(a) for a in plan.get("alergias") or []]
    plan["rechazos_visibles"] = [nombre_visible(x) for x in plan.get("rechazos") or []]

    # En la parrilla se imprime el nombre de la RECETA de este niño, no el de la
    # base. El plan.json guarda el nombre de la base porque es lo que el
    # ensamblador eligió —«Panqueques de cereal», «Bastones de tubérculo»—, y
    # esos son nombres de técnica: útiles dentro del sistema e inútiles en la
    # nevera. La madre lee «Panqueques de cereal» en el horario, va al recetario
    # a buscarlo y encuentra «Panqueques de avena».
    #
    # Se sustituye aquí, en la capa de presentación, y no en el plan: los
    # identificadores del plan no se tocan, porque de ellos dependen el validador
    # y su huella.
    instanciadas, _ = cargar_recetas_instanciadas(carpeta)
    titulos = {
        rid: str(r["meta"].get("titulo") or "")
        for rid, r in instanciadas.items()
        if r["meta"].get("titulo")
    }
    for s_ in plan["semanas"]:
        for dia in s_["dias"].values():
            for comida in dia.values():
                for item in comida["items"]:
                    titulo = titulos.get(item.get("receta_id") or "")
                    if titulo:
                        item["nombre"] = titulo
    # --- O-3 · el plan y su recetario se emiten juntos o no se emiten -------
    # El recetario decía en portada «estas son las preparaciones que aparecen en
    # el plan» y era falso: cinco preparaciones de la grilla no tenían receta y
    # siete recetas no aparecían en ningún día. Y no era azar — Compota de
    # manzana / Compota de pera, Paletas de fresa / Paletas de mango, Trufas de
    # pecana / Trufas de garbanzo—: los dos documentos salieron de
    # instanciaciones distintas de la misma base.
    #
    # La consecuencia no es cosmética. La madre lee «Trufas de pecana» en el
    # plan, busca la receta y encuentra una con mantequilla de maní. Pecana y
    # maní no son el mismo fruto seco ni el mismo alérgeno.
    #
    # Se comprueba contando, no leyendo, y aquí y no en el validador porque esto
    # es una propiedad de lo que se IMPRIME. Si falla, no sale ninguno de los
    # dos PDF: medio par no sirve de nada.
    _comprobar_par(plan, instanciadas, titulos)

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
    recetas, faltantes = [], []
    for rid in plan.get("recetas_usadas", []):
        r = leer_receta(rid, carpeta, plan.get("paciente", ""))
        (recetas.append(r) if r else faltantes.append(rid))
    if faltantes:
        print(
            f"  ⚠ sin receta instanciada para: {', '.join(faltantes)}. "
            f"Se escriben con prompts/P1_RECETAS.md en modo INSTANCIA y se guardan en "
            f"{DIR_RECETAS_PACIENTE}/."
        )

    if recetas:
        informe_de_fotos(recetas)
        recetas.sort(key=lambda r: r["meta"].get("titulo", ""))
        doc = env.get_template("recetario.html").render(p=plan, recetas=recetas)
        destino = carpeta / f"Recetario_{slug}.pdf"
        _escribir_pdf(doc, destino, [css_base], base)
        salidas.append(destino)
    else:
        # Un PDF donde se esperaban dos, y hasta ahora sin una palabra que lo
        # explicara. El plan es correcto: es la biblioteca la que no cubre este
        # protocolo todavía.
        print(
            f"  · Sin recetario: este plan no usa ninguna receta de biblioteca/.\n"
            f"    Todas sus preparaciones son alimentos base, que se preparan sin\n"
            f"    instrucciones y por eso no tienen ficha. El reporte de QA dice qué\n"
            f"    componentes del protocolo «{plan.get('protocolo')}» no tienen ninguna\n"
            f"    receta todavía; se escriben con prompts/P1_RECETAS.md (Fase 3)."
        )

    return salidas


def main() -> int:
    ap = argparse.ArgumentParser(description="Renderiza los PDF de un paciente.")
    ap.add_argument("paciente")
    ap.add_argument(
        "--caras",
        action="store_true",
        help="parte cada semana en dos hojas (Cara A: lun–jue · Cara B: vie–dom), con letra más grande",
    )
    args = ap.parse_args()

    try:
        salidas = renderizar(args.paciente, caras=args.caras)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    print("✓ PDF generados:")
    for s in salidas:
        print(f"  → {s}  ({s.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
