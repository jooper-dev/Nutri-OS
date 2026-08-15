"""
Firma visual — Nutri-OS

**La imagen no pertenece a la receta: pertenece al aspecto.**

Antes, las recetas vivían en la biblioteca con identificadores estables y cada
una tenía su foto enlazada por ese identificador. Desde que las recetas se
instancian por paciente, la misma base produce platos distintos para niños
distintos, y si cambian los ingredientes cambia el aspecto: reutilizar la foto
de la base sería enseñar una foto que no corresponde al plato.

El identificador de la receta es la pregunta equivocada. La pregunta correcta es
qué determina el aspecto, y la respuesta es esto:

    la base de la que sale
    + el formato final (licuado, colado, en bastones, en discos, entero…)
    + los ingredientes que aportan algo visible, en orden
    + el nivel de carga visual

Nada más. Añadir una cucharadita de aceite no cambia la firma; añadir manzana en
trozos, sí. Dos instancias que **se ven igual** pueden compartir foto; dos que se
ven distinto, no.

APORTE VISUAL — cada ingrediente declara el suyo en la receta instanciada:

    ninguno   desaparece en la preparación: agua, aceite, sal, una pizca de
              canela disuelta.
    color     tiñe el conjunto sin añadir piezas distinguibles: cacao, puré de
              zanahoria.
    pieza     aporta algo identificable a la vista: fruta en trozos, semillas,
              hojuelas.

Las imágenes se guardan indexadas por firma, no por receta, con un manifiesto
que registra por cada una: el archivo, qué receta y qué paciente la originaron,
la fecha y el punto focal para el recorte.

Y una regla que va en código porque es de las de «esto nunca debe salir»:
**nunca se muestra una imagen cuya firma no coincida.** Si no hay foto para esta
firma, la receta se maqueta con portada tipográfica y el reporte dice qué habría
que fotografiar. El sistema PIDE imágenes; no las fabrica.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import yaml

from comun import DIR_BIBLIOTECA, ErrorNutriOS, normalizar_texto

DIR_IMAGENES = DIR_BIBLIOTECA / "imagenes"
RUTA_MANIFIESTO = DIR_IMAGENES / "_manifiesto.yaml"

# Vocabulario cerrado del aporte visual de un ingrediente.
APORTES = {"ninguno", "color", "pieza"}

# Ancho mínimo en píxeles para que una foto pueda ocupar una página A4 a sangre.
#
# A4 son 210 mm de ancho; a 150 ppp eso son 1240 px, que es el piso por debajo
# del cual el grano se ve impreso. Una foto pixelada en un documento que va a una
# familia es peor que ninguna foto: por debajo de esto se trata como si no
# existiera y la receta sale con portada tipográfica.
ANCHO_MINIMO_PX = 1240


def _texto_firma(
    base: str, formato: str, visibles: list[str], carga_visual: int | None
) -> str:
    partes = [
        normalizar_texto(base),
        normalizar_texto(formato),
        ",".join(normalizar_texto(v) for v in visibles),
        f"v{carga_visual if carga_visual is not None else '?'}",
    ]
    return "|".join(partes)


def calcular(meta: dict) -> tuple[str, dict]:
    """La firma visual de una receta instanciada. Devuelve (firma, detalle).

    `detalle` es lo que entró en el cálculo, para poder explicarlo en el reporte
    sin tener que descifrar un hash.
    """
    base = str(meta.get("base") or meta.get("id") or "")
    formato = str(meta.get("formato_final") or "").strip()
    carga = meta.get("carga_visual")
    aporte = meta.get("aporte_visual") or {}

    if isinstance(aporte, list):
        # Forma corta: solo la lista de lo que se ve. Todo lo demás es `ninguno`.
        visibles = [str(x) for x in aporte]
    else:
        desconocidos = sorted(
            f"{k}: {v}" for k, v in aporte.items() if str(v) not in APORTES
        )
        if desconocidos:
            raise ErrorNutriOS(
                f"«{meta.get('titulo') or base}»: aporte visual no reconocido en "
                + ", ".join(desconocidos)
                + f".\n    Valores válidos: {', '.join(sorted(APORTES))}."
            )
        visibles = [str(k) for k, v in aporte.items() if str(v) != "ninguno"]

    texto = _texto_firma(base, formato, visibles, carga)
    firma = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]
    return firma, {
        "base": base,
        "formato": formato,
        "visibles": visibles,
        "carga_visual": carga,
        "texto": texto,
    }


def completa(meta: dict) -> bool:
    """¿La receta declara lo necesario para que su firma signifique algo?

    Sin `formato_final` ni `aporte_visual`, la firma se calcularía sobre campos
    vacíos y dos platos distintos darían el mismo hash — que es exactamente el
    fallo que esto viene a evitar, con un disfraz nuevo.
    """
    return bool(str(meta.get("formato_final") or "").strip()) and bool(
        meta.get("aporte_visual")
    )


# ---------------------------------------------------------------------------
# Manifiesto
# ---------------------------------------------------------------------------


def cargar_manifiesto() -> dict:
    if not RUTA_MANIFIESTO.exists():
        return {"firmas": {}}
    datos = yaml.safe_load(RUTA_MANIFIESTO.read_text(encoding="utf-8")) or {}
    datos.setdefault("firmas", {})
    return datos


def guardar_manifiesto(datos: dict) -> None:
    DIR_IMAGENES.mkdir(parents=True, exist_ok=True)
    cabecera = (
        "# Manifiesto de imágenes — Nutri-OS\n"
        "#\n"
        "# Indexado por FIRMA VISUAL, no por receta: dos instancias que se ven\n"
        "# igual comparten foto, y dos que se ven distinto no pueden compartirla\n"
        "# aunque salgan de la misma base.\n"
        "#\n"
        "# Cada entrada registra qué receta y qué paciente originaron la foto, la\n"
        "# fecha, y el punto focal —en fracción de ancho y alto— para que el\n"
        "# recorte a página completa no parta el plato. Sin punto focal, recorte\n"
        "# centrado.\n"
        "#\n"
        "# Este archivo lo escribe motor/firma_visual.py y lo lee motor/render.py.\n"
        "# Las fotos se añaden a mano: el sistema las PIDE, no las fabrica.\n"
    )
    RUTA_MANIFIESTO.write_text(
        cabecera + yaml.safe_dump(datos, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )


def registrar_pendiente(
    firma: str, detalle: dict, meta: dict, paciente: str
) -> None:
    """Anota en el manifiesto una firma que todavía no tiene foto.

    Es la lista de la compra del fotógrafo: qué plato hay que retratar, de qué
    receta y de qué caso salió, y desde cuándo está pendiente.
    """
    datos = cargar_manifiesto()
    entrada = datos["firmas"].setdefault(firma, {})
    if entrada.get("archivo"):
        return
    entrada.update(
        {
            "archivo": None,
            "receta": str(meta.get("id") or detalle["base"]),
            "base": detalle["base"],
            "titulo": str(meta.get("titulo") or ""),
            "paciente": paciente,
            "formato": detalle["formato"],
            "se_ve": detalle["visibles"],
            "carga_visual": detalle["carga_visual"],
            "pedida_el": str(date.today()),
        }
    )
    guardar_manifiesto(datos)


def imagen_de(firma: str) -> tuple[Path | None, str]:
    """La foto de esa firma, si existe y sirve. Devuelve (ruta, motivo si no).

    Tres comprobaciones, y las tres pueden decir que no:

      1. El manifiesto no tiene esa firma → nadie ha fotografiado este plato.
      2. La tiene pero el archivo no está → el manifiesto y el disco no cuadran.
      3. El archivo está pero es demasiado pequeño → una foto pixelada en un
         documento que va a una familia es peor que ninguna foto.
    """
    datos = cargar_manifiesto()
    entrada = datos["firmas"].get(firma)
    if not entrada or not entrada.get("archivo"):
        return None, "sin foto para esta firma visual"

    ruta = DIR_IMAGENES / str(entrada["archivo"])
    if not ruta.exists():
        return None, f"el manifiesto apunta a {entrada['archivo']} y el archivo no está"

    try:
        from PIL import Image

        with Image.open(ruta) as im:
            if im.width < ANCHO_MINIMO_PX:
                return None, (
                    f"{ruta.name} mide {im.width} px de ancho y hacen falta "
                    f"{ANCHO_MINIMO_PX} para una página A4: se trata como si no "
                    f"existiera"
                )
    except ImportError:
        # Sin Pillow no se puede medir. Se usa igual y se avisa arriba: el
        # chequeo de dependencias ya dice que falta.
        pass

    return ruta, ""


def punto_focal(firma: str) -> tuple[float, float]:
    """Dónde está el plato dentro de la foto, en fracción de ancho y alto.

    La proporción de la página no coincide con la de una foto normal, así que va
    a haber recorte. El punto focal es lo que impide que ese recorte parta el
    plato por la mitad. Sin punto focal declarado, recorte centrado.
    """
    entrada = cargar_manifiesto()["firmas"].get(firma) or {}
    foco = entrada.get("punto_focal")
    if isinstance(foco, (list, tuple)) and len(foco) == 2:
        try:
            x, y = float(foco[0]), float(foco[1])
            return min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
        except (TypeError, ValueError):
            pass
    return 0.5, 0.5
