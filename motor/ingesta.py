"""
Ingesta de fuentes — Nutri-OS · Fase 0

Convierte lo que Paty arrastra al chat en texto plano ANTES de que ningún modelo
lo lea, y deja constancia de qué entró.

    pacientes/<paciente>/fuentes_originales/   lo que ella pasó, intacto
    pacientes/<paciente>/fuentes/              un .md por documento, y el inventario

Existe por dos fallos del primer caso real, y los dos son el mismo fallo:

  1. Un PDF de 88 páginas y 56 MB entró entero en la ventana de contexto. Un PDF
     así se lee convirtiendo cada página en imagen: son 88 lecturas visuales
     antes de la primera decisión clínica, y todo lo que viene después se decide
     con la ventana ya saturada de material irrelevante.

  2. Nadie sabía qué documentos se habían recibido. Se adjuntó dos veces el mismo
     archivo —bit a bit idéntico— y se perdió el estudio del paciente, y el
     sistema no se enteró. El valor de hemoglobina que se buscaba estaba, quizá,
     en el archivo que faltaba. Eso no se arregla pidiendo más cuidado.

De ahí las dos salidas. El `.md` por documento es para que el pipeline lea texto
y no imágenes. El inventario es para que se pueda responder «¿qué me llegó?» sin
abrir nada: una fila por documento y por página, con lo que se pudo extraer y lo
que no.

**Una página sin capa de texto no se ignora en silencio: se marca como pendiente
de lectura visual.** Es la línea que faltaba. Si el valor de la hemoglobina
estaba en una imagen, el inventario tenía que haber dicho «página 2, sin texto,
requiere lectura visual», y en vez de eso nadie se enteró de nada.

Uso:
    python motor/ingesta.py <nombre_carpeta_paciente>
    python motor/ingesta.py <carpeta> --rehacer    reprocesa lo ya extraído
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from comun import DIR_PACIENTES, ErrorNutriOS, guardar_json

# Nombres de las dos carpetas. Están aquí y no repartidos por los módulos que
# las nombran porque el pipeline entero depende de que sean exactamente estas
# dos: `fuentes_originales/` es lo que Paty pasó y no se toca nunca;
# `fuentes/` es lo único que el pipeline lee.
DIR_ORIGINALES = "fuentes_originales"
DIR_EXTRAIDAS = "fuentes"

# A partir de aquí, un documento se parte en varios .md.
#
# No es una preferencia estética: el objetivo del paso 0 es que un documento
# largo no pueda volver a entrar entero en la ventana de contexto. Un archivo
# de 88 páginas invita a leerse de una sentada aunque sea texto; ocho archivos
# de veinte páginas con el rango en el nombre invitan a abrir el que toca.
PAGINAS_POR_ARCHIVO = 20

# Por encima de esto, el documento se etiqueta como material de referencia.
#
# Un documento así —las recomendaciones por franja de edad, la preparación para
# los exámenes— es mayormente material general y reutilizable, no datos de este
# niño. La etiqueta no decide nada clínico y no filtra contenido: solo dice
# «esto no es la anamnesis», para que la ficha lo cite página a página en lugar
# de tragárselo entero. Lo que entra al plan sigue siendo únicamente lo que la
# ficha referencia de forma explícita, y eso lo comprueba el validador.
PAGINAS_MATERIAL_REFERENCIA = 20

NL = chr(10)
CR = chr(13)
CRLF = CR + NL
TAB = chr(9)
NBSP = chr(160)
BLANCOS = NL + TAB
BLANCO_REPETIDO = "[ " + TAB + "]+"

EXT_TEXTO = {".txt", ".md", ".csv"}
EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------


@dataclass
class Pagina:
    numero: int
    texto: str = ""
    # Qué pasó al intentar leerla:
    #   "texto"          se extrajo texto utilizable
    #   "sin_texto"      la página existe y su capa de texto viene vacía
    #   "solo_imagen"    el documento ES una imagen
    #   "no_procesable"  no se pudo abrir
    estado: str = "texto"
    detalle: str = ""

    @property
    def requiere_lectura_visual(self) -> bool:
        return self.estado in {"sin_texto", "solo_imagen"}


@dataclass
class Documento:
    ruta: Path
    tipo: str
    sha256: str
    bytes: int
    paginas: list[Pagina] = field(default_factory=list)
    error: str = ""
    incrustadas: int = 0          # imágenes dentro de un .docx
    duplicado_de: str = ""

    @property
    def nombre(self) -> str:
        return self.ruta.name

    @property
    def es_referencia(self) -> bool:
        return len(self.paginas) > PAGINAS_MATERIAL_REFERENCIA

    @property
    def pendientes(self) -> list[Pagina]:
        return [p for p in self.paginas if p.requiere_lectura_visual]


# ---------------------------------------------------------------------------
# Extractores
# ---------------------------------------------------------------------------


def _desespaciar(linea: str) -> str:
    """Rehace las líneas que salen con un espacio entre cada letra.

    Los PDF de diseño —los de Canva, que son con los que trabaja Paty— colocan
    cada glifo por separado, y el extractor no tiene forma de saber dónde
    acababa una palabra: devuelve `A N Á L I S I S  D E  L A B O R A T O R I O`.

    Eso no es un problema estético. Un texto así no se puede buscar: «ferritina»
    no aparece por ninguna parte en un documento que dice `F e r r i t i n a`, y
    la trazabilidad de un dato clínico depende de poder encontrar la palabra en
    la página que la ficha cita.

    La reconstrucción se apoya en la regla que el propio formato respeta: entre
    dos palabras hay dos espacios o más, entre dos letras hay uno. Solo se
    aplica cuando la línea es mayoritariamente de fichas de un carácter —el
    patrón inequívoco—, para no juntarle las palabras a una línea normal que
    casualmente lleve siglas.
    """
    sueltas = [f for f in linea.split(" ") if f]
    if len(sueltas) < 6:
        return linea
    if sum(1 for f in sueltas if len(f) == 1) / len(sueltas) < 0.7:
        return linea
    return " ".join(p.replace(" ", "") for p in re.split(r" {2,}", linea.strip()) if p.strip())


def _limpiar(texto: str) -> str:
    """Quita el ruido de extracción sin tocar el contenido.

    Se normalizan los blancos, se rehacen las líneas letra-a-letra y se colapsan
    las líneas vacías seguidas. Nada más: cualquier arreglo más listo que esto
    acaba perdiendo un número, y aquí los números son valores de laboratorio.
    """
    texto = texto.replace(CRLF, NL).replace(CR, NL)
    texto = "".join(
        c for c in texto if c in BLANCOS or unicodedata.category(c)[0] != "C"
    )
    texto = texto.replace(NBSP, " ")
    salida: list[str] = []
    for cruda in texto.split(NL):
        l = re.sub(BLANCO_REPETIDO, " ", _desespaciar(cruda)).strip()
        if not l and salida and not salida[-1]:
            continue
        salida.append(l)
    return NL.join(salida).strip()


def extraer_pdf(ruta: Path) -> tuple[list[Pagina], str]:
    """Capa de texto de un PDF, página a página. Solo lectura.

    Una página se marca `sin_texto` únicamente cuando su capa de texto viene
    vacía de verdad. Un PDF de Canva con texto encima de una imagen SÍ tiene
    capa de texto y se extrae limpio: si sale marcado, el fallo está en este
    extractor, no en el archivo.

    Si el PDF no se puede abrir, el documento entero se marca no procesable con
    el error concreto y la ingesta sigue con el siguiente. Un archivo corrupto
    no puede tumbar la lectura de los otros cuatro.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], (
            "falta la librería pypdf, que es la que lee la capa de texto de los PDF. "
            "Instálala con: pip install -r requirements.txt"
        )

    try:
        lector = PdfReader(str(ruta))
        total = len(lector.pages)
    except Exception as e:  # noqa: BLE001 — cualquier PDF roto, con su error literal
        return [], f"pypdf no pudo abrir el archivo — {type(e).__name__}: {e}"

    paginas: list[Pagina] = []
    for i in range(total):
        try:
            crudo = lector.pages[i].extract_text() or ""
        except Exception as e:  # noqa: BLE001 — una página rota no tumba las otras
            paginas.append(
                Pagina(i + 1, "", "no_procesable", f"{type(e).__name__}: {e}")
            )
            continue
        texto = _limpiar(crudo)
        if texto:
            paginas.append(Pagina(i + 1, texto, "texto"))
        else:
            paginas.append(
                Pagina(i + 1, "", "sin_texto", "la capa de texto de esta página viene vacía")
            )
    return paginas, ""


def extraer_docx(ruta: Path) -> tuple[list[Pagina], int, str]:
    """Texto de un .docx con la librería estándar. Devuelve (páginas, imágenes, error).

    Un .docx es un ZIP con XML dentro, así que no hace falta ninguna dependencia:
    se leen los nodos de texto en orden de documento, que incluye los de dentro
    de las tablas porque una celda contiene párrafos como cualquier otra cosa.

    Word no tiene páginas hasta que alguien lo imprime. Lo que sí tiene son
    saltos de página explícitos, y por ahí se corta: si el documento no lleva
    ninguno —que es lo normal en unas notas de consulta escritas del tirón—,
    sale una sola página, y eso es la verdad.

    Las imágenes incrustadas se cuentan pero no se leen. Importa contarlas: en
    el primer caso real, la única imagen del Word de anamnesis era una captura
    de video de la madre sosteniendo un plato, y durante la revisión se llegó a
    suponer que podía ser el análisis que faltaba. Un número en el inventario
    resuelve esa duda sin abrir nada.
    """
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            if "word/document.xml" not in nombres:
                return [], 0, "el archivo no contiene word/document.xml: no es un .docx válido"
            xml = z.read("word/document.xml")
            incrustadas = sum(
                1
                for n in nombres
                if n.startswith("word/media/") and not n.endswith("/")
            )
    except (zipfile.BadZipFile, OSError) as e:
        return [], 0, f"no se pudo abrir como .docx — {type(e).__name__}: {e}"

    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as e:
        return [], 0, f"el XML interno del .docx está mal formado — {e}"

    paginas: list[Pagina] = []
    actual: list[str] = []

    def cerrar() -> None:
        texto = _limpiar("\n".join(actual))
        paginas.append(
            Pagina(len(paginas) + 1, texto, "texto" if texto else "sin_texto",
                   "" if texto else "este tramo del documento no tiene texto")
        )
        actual.clear()

    for parrafo in raiz.iter(f"{W}p"):
        trozos: list[str] = []
        corta = False
        for nodo in parrafo.iter():
            if nodo.tag == f"{W}t":
                trozos.append(nodo.text or "")
            elif nodo.tag == f"{W}tab":
                trozos.append("\t")
            elif nodo.tag == f"{W}br" and nodo.get(f"{W}type") == "page":
                corta = True
        actual.append("".join(trozos))
        if corta:
            cerrar()

    cerrar()
    return paginas, incrustadas, ""


def extraer_texto_plano(ruta: Path) -> tuple[list[Pagina], str]:
    for codificacion in ("utf-8", "cp1252", "latin-1"):
        try:
            crudo = ruta.read_text(encoding=codificacion)
            break
        except (UnicodeDecodeError, OSError):
            continue
    else:
        return [], "no se pudo leer con ninguna codificación conocida (utf-8, cp1252, latin-1)"
    texto = _limpiar(crudo)
    estado = "texto" if texto else "sin_texto"
    return [Pagina(1, texto, estado, "" if texto else "el archivo está vacío")], ""


# ---------------------------------------------------------------------------
# Ingesta
# ---------------------------------------------------------------------------


def _slug(nombre: str) -> str:
    s = unicodedata.normalize("NFD", nombre)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s.-]", "", s).strip().lower()
    return re.sub(r"[\s_]+", "-", s) or "documento"


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_documento(ruta: Path) -> Documento:
    ext = ruta.suffix.lower()
    doc = Documento(ruta=ruta, tipo=ext.lstrip(".") or "?", sha256=_sha256(ruta),
                    bytes=ruta.stat().st_size)

    if ext == ".pdf":
        doc.paginas, doc.error = extraer_pdf(ruta)
    elif ext == ".docx":
        doc.paginas, doc.incrustadas, doc.error = extraer_docx(ruta)
    elif ext in EXT_TEXTO:
        doc.paginas, doc.error = extraer_texto_plano(ruta)
    elif ext in EXT_IMAGEN:
        doc.paginas = [
            Pagina(1, "", "solo_imagen", "el documento es una imagen: no tiene capa de texto")
        ]
    else:
        doc.error = (
            f"la ingesta no sabe leer la extensión «{ext or '(ninguna)'}». "
            f"Sabe leer: pdf, docx, "
            + ", ".join(sorted(e.lstrip('.') for e in EXT_TEXTO | EXT_IMAGEN))
        )
    return doc


def _cabecera(doc: Documento, desde: int, hasta: int, partes: int) -> list[str]:
    rango = f"páginas {desde}–{hasta}" if desde != hasta else f"página {desde}"
    lineas = [
        f"# {doc.nombre}",
        "",
        f"> Texto extraído por `motor/ingesta.py`. El original está en "
        f"`{DIR_ORIGINALES}/{doc.nombre}` y no se modifica nunca.",
        "",
        f"- Tipo: `{doc.tipo}` · {doc.bytes / 1024:.0f} KB · {len(doc.paginas)} página(s)",
        f"- Este archivo: {rango}" + (f" (parte {desde // PAGINAS_POR_ARCHIVO + 1} de {partes})" if partes > 1 else ""),
        f"- Huella: `sha256:{doc.sha256[:16]}…`",
    ]
    if doc.es_referencia:
        lineas.append(
            "- **Material de referencia.** Documento largo y mayormente general "
            "(pautas por franja de edad, preparación de exámenes). No es la "
            "anamnesis de este niño: cita de aquí solo la página concreta que "
            "uses, y decláralo en `procedencia` de la ficha."
        )
    if doc.incrustadas:
        lineas.append(
            f"- **{doc.incrustadas} imagen(es) incrustada(s)**, no leídas. Si algún "
            f"dato clínico vive dentro de una de ellas, hay que abrirlas a mano."
        )
    lineas.append("")
    return lineas


def escribir_extraidas(doc: Documento, destino: Path) -> list[Path]:
    """Un .md por documento, o varios si es largo. Devuelve las rutas escritas."""
    base = _slug(doc.ruta.stem)
    if not doc.paginas:
        ruta = destino / f"{base}.md"
        ruta.write_text(
            "\n".join(
                _cabecera(doc, 0, 0, 1)
                + [
                    "## No procesable",
                    "",
                    doc.error or "no se pudo extraer nada de este documento.",
                    "",
                    "El original sigue intacto. Este documento **no ha sido leído por "
                    "nadie**: si contiene datos clínicos, hay que abrirlo a mano.",
                ]
            ),
            encoding="utf-8",
        )
        return [ruta]

    grupos = [
        doc.paginas[i : i + PAGINAS_POR_ARCHIVO]
        for i in range(0, len(doc.paginas), PAGINAS_POR_ARCHIVO)
    ]
    rutas: list[Path] = []
    for grupo in grupos:
        desde, hasta = grupo[0].numero, grupo[-1].numero
        sufijo = f".p{desde:03d}-{hasta:03d}" if len(grupos) > 1 else ""
        ruta = destino / f"{base}{sufijo}.md"
        lineas = _cabecera(doc, desde, hasta, len(grupos))
        for p in grupo:
            lineas.append(f"## Página {p.numero}")
            lineas.append("")
            if p.estado == "texto":
                lineas += [p.texto, ""]
            else:
                lineas += [
                    f"*(sin texto extraíble — {p.detalle})*",
                    "",
                    "**PENDIENTE DE LECTURA VISUAL.** Esta página no ha sido leída por "
                    "nadie. Si el dato que buscas debería estar aquí, ábrela a mano "
                    f"en `{DIR_ORIGINALES}/{doc.nombre}`.",
                    "",
                ]
        ruta.write_text("\n".join(lineas), encoding="utf-8")
        rutas.append(ruta)
    return rutas


def _marcar_duplicados(documentos: list[Documento]) -> None:
    """Dos archivos con la misma huella son el mismo archivo. Ya pasó dos veces."""
    primero: dict[str, str] = {}
    for doc in documentos:
        if doc.sha256 in primero:
            doc.duplicado_de = primero[doc.sha256]
        else:
            primero[doc.sha256] = doc.nombre


def escribir_inventario(documentos: list[Documento], destino: Path) -> Path:
    total_pag = sum(len(d.paginas) for d in documentos)
    pendientes = [(d, p) for d in documentos for p in d.pendientes]
    duplicados = [d for d in documentos if d.duplicado_de]
    rotos = [d for d in documentos if d.error]

    L = [
        "# Inventario de fuentes",
        "",
        f"{len(documentos)} documento(s) · {total_pag} página(s) · "
        f"{len(pendientes)} pendiente(s) de lectura visual",
        "",
        "Este archivo responde a «¿qué me llegó?» sin abrir nada. Lo genera "
        "`motor/ingesta.py` y se rehace entero en cada pasada.",
        "",
    ]

    if duplicados:
        L += [
            "## ⚠ Documentos duplicados",
            "",
            "Mismo contenido byte a byte con dos nombres. Casi siempre significa que "
            "se adjuntó dos veces un archivo **y que falta otro**: es exactamente lo "
            "que pasó con el estudio del primer caso real, dos veces y en dos manos "
            "distintas. Comprueba qué documento debería estar y no está.",
            "",
        ]
        L += [f"- `{d.nombre}` es idéntico a `{d.duplicado_de}`" for d in duplicados]
        L.append("")

    if rotos:
        L += ["## ⚠ Documentos no procesables", ""]
        L += [f"- `{d.nombre}` — {d.error}" for d in rotos]
        L += [
            "",
            "El original sigue intacto y sin leer. Si trae datos clínicos, hay que "
            "abrirlo a mano.",
            "",
        ]

    if pendientes:
        L += [
            "## ⚠ Pendientes de lectura visual",
            "",
            "Páginas que existen y de las que **no se pudo extraer una sola letra**. "
            "No están vacías necesariamente: lo más probable es que sean una imagen "
            "escaneada o una captura. Nadie las ha leído.",
            "",
            "Si un dato que esperabas no aparece en la ficha, empieza por aquí.",
            "",
        ]
        L += [f"- `{d.nombre}` · página {p.numero} — {p.detalle}" for d, p in pendientes]
        L.append("")

    L += [
        "## Todos los documentos",
        "",
        "| Documento | Tipo | Págs. | Con texto | Sin texto | Rol |",
        "|---|---|---|---|---|---|",
    ]
    for d in documentos:
        con = sum(1 for p in d.paginas if p.estado == "texto")
        sin = len(d.paginas) - con
        rol = "referencia" if d.es_referencia else "fuente clínica"
        if d.duplicado_de:
            rol = f"duplicado de {d.duplicado_de}"
        if d.error:
            rol = "no procesable"
        L.append(
            f"| `{d.nombre}` | {d.tipo} | {len(d.paginas) or '—'} | {con} | "
            f"{sin or '—'} | {rol} |"
        )

    L += ["", "## Página a página", "", "| Documento | Pág. | Estado | Caracteres |", "|---|---|---|---|"]
    ESTADO = {
        "texto": "texto extraído",
        "sin_texto": "**sin texto · pendiente de lectura visual**",
        "solo_imagen": "**solo imagen · pendiente de lectura visual**",
        "no_procesable": "**no procesable**",
    }
    for d in documentos:
        for p in d.paginas:
            L.append(
                f"| `{d.nombre}` | {p.numero} | {ESTADO.get(p.estado, p.estado)} | "
                f"{len(p.texto) or '—'} |"
            )

    ruta = destino / "_inventario.md"
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")
    return ruta


def datos_inventario(documentos: list[Documento]) -> dict:
    """La versión que lee el validador, no la que lee Paty."""
    return {
        "documentos": [
            {
                "nombre": d.nombre,
                "tipo": d.tipo,
                "sha256": d.sha256,
                "bytes": d.bytes,
                "paginas": len(d.paginas),
                "rol": "referencia" if d.es_referencia else "fuente_clinica",
                "duplicado_de": d.duplicado_de,
                "error": d.error,
                "imagenes_incrustadas": d.incrustadas,
                "pendientes_lectura_visual": [p.numero for p in d.pendientes],
            }
            for d in documentos
        ]
    }


def cargar_inventario(carpeta: Path) -> dict | None:
    """El inventario de un paciente ya ingerido, o None si no se ha ingerido."""
    ruta = carpeta / DIR_EXTRAIDAS / "_inventario.json"
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorNutriOS(
            f"{ruta} está corrupto y no se puede leer: {e}\n"
            f"    Vuelve a ejecutar: python motor/ingesta.py {carpeta.name}"
        ) from e


def ingerir(nombre_carpeta: str) -> tuple[list[Documento], Path, list[Path]]:
    carpeta = DIR_PACIENTES / nombre_carpeta
    if not carpeta.exists():
        raise ErrorNutriOS(f"No existe la carpeta {carpeta}")

    origen = carpeta / DIR_ORIGINALES
    if not origen.exists():
        raise ErrorNutriOS(
            f"No existe {origen}.\n"
            f"    Ahí van los archivos tal como los pasó Paty, con su nombre original.\n"
            f"    Los crea el orquestador en la Fase 0; Paty no toca carpetas."
        )

    archivos = sorted(
        (p for p in origen.iterdir() if p.is_file() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )
    if not archivos:
        raise ErrorNutriOS(
            f"{origen} está vacía: no hay nada que ingerir.\n"
            f"    Guarda ahí los adjuntos de la consulta y el mensaje que escribió Paty."
        )

    destino = carpeta / DIR_EXTRAIDAS
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.md"):
        viejo.unlink()

    documentos = [leer_documento(p) for p in archivos]
    _marcar_duplicados(documentos)

    escritos: list[Path] = []
    for doc in documentos:
        escritos += escribir_extraidas(doc, destino)

    inventario = escribir_inventario(documentos, destino)
    guardar_json(destino / "_inventario.json", datos_inventario(documentos))
    return documentos, inventario, escritos


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convierte las fuentes de un paciente en texto e inventaría qué llegó."
    )
    ap.add_argument("paciente", help="nombre de la carpeta en /pacientes/")
    ap.add_argument(
        "--rehacer",
        action="store_true",
        help="reprocesa aunque ya exista fuentes/ (es el comportamiento por defecto; "
             "la bandera está para poder escribirlo explícito en un guion)",
    )
    args = ap.parse_args()

    try:
        documentos, inventario, escritos = ingerir(args.paciente)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    total_pag = sum(len(d.paginas) for d in documentos)
    pendientes = [(d, p) for d in documentos for p in d.pendientes]

    print(f"✓ Fuentes ingeridas — {args.paciente}")
    print(f"  {len(documentos)} documento(s) · {total_pag} página(s) · {len(escritos)} archivo(s) de texto")

    for d in documentos:
        marca = "·"
        extra = ""
        if d.error:
            marca, extra = "✗", f" — {d.error}"
        elif d.duplicado_de:
            marca, extra = "⚠", f" — duplicado byte a byte de {d.duplicado_de}"
        elif d.es_referencia:
            extra = f" — material de referencia, {len(d.paginas)} págs."
        print(f"  {marca} {d.nombre} ({len(d.paginas) or '—'} pág.){extra}")

    if pendientes:
        print()
        print(f"  ⚠ {len(pendientes)} página(s) sin capa de texto, PENDIENTES DE LECTURA VISUAL:")
        for d, p in pendientes[:10]:
            print(f"      {d.nombre} · página {p.numero}")
        if len(pendientes) > 10:
            print(f"      … y {len(pendientes) - 10} más (están todas en el inventario)")
        print("    Si un dato clínico que esperabas no aparece, empieza por estas páginas.")

    duplicados = [d for d in documentos if d.duplicado_de]
    if duplicados:
        print()
        print("  ⚠ Hay documentos duplicados. Comprueba qué archivo debería estar y no está:")
        for d in duplicados:
            print(f"      {d.nombre} = {d.duplicado_de}")

    print()
    print(f"  → {inventario}")
    print(f"  El pipeline lee {DIR_EXTRAIDAS}/, nunca {DIR_ORIGINALES}/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
