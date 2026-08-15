"""
Utilidades compartidas del motor Nutri-OS.

Todo lo que lee archivos del repositorio pasa por aquí, para que exista
un solo sitio donde cambiar formatos.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def consola_utf8() -> None:
    """Deja la salida en UTF-8 para que un ✓ no tumbe un script entero.

    En Windows, cuando la salida va a un archivo o a una tubería —o la consola
    está en cp1252—, Python elige esa codificación y cualquier símbolo de los
    que usa el sistema (✓ ✗ ⚠ · → —) lanza UnicodeEncodeError.

    No es un problema estético. `ensamblar.py` guarda plan.json ANTES de
    imprimir su resumen: el plan salía correcto, el script moría en el `print`
    siguiente, y quien lo ejecutaba veía una traza roja y daba por hecho que el
    sistema había fallado.

    `errors="replace"` es la red por debajo: si ni siquiera se puede pasar a
    UTF-8, es preferible un símbolo sustituido por '?' que una traza.

    Se llama al importar este módulo, que es lo primero que hace cualquier
    script del motor. Es un efecto de importación deliberado: la alternativa
    era repetir estas seis líneas en los diez puntos de entrada.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


consola_utf8()

RAIZ = Path(__file__).resolve().parent.parent

DIR_PROTOCOLOS = RAIZ / "protocolos"
DIR_BIBLIOTECA = RAIZ / "biblioteca"
DIR_DATOS = RAIZ / "datos"
DIR_PACIENTES = RAIZ / "pacientes"
DIR_SALIDAS = RAIZ / "salidas"

# Las tres carpetas de un paciente, por nombre, en un solo sitio.
#
#   fuentes_originales/  lo que Paty pasó, intacto y sin abrir jamás por el
#                        pipeline. Un PDF de 88 páginas vive aquí y aquí se queda.
#   fuentes/             el texto extraído por motor/ingesta.py, más el
#                        inventario. Es LO ÚNICO que el pipeline lee.
#   recetas/             las recetas ya instanciadas para este niño. Es lo que
#                        se imprime, y el registro de lo que se entregó de verdad.
DIR_ORIGINALES = "fuentes_originales"
DIR_EXTRAIDAS = "fuentes"
DIR_RECETAS_PACIENTE = "recetas"

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Claves de primer nivel que puede llevar un protocolo.
#
# Están aquí, y no repartidas por los módulos que las leen, porque motor/revisar.py
# necesita una lista cerrada contra la que comparar: una clave que nadie consume no
# falla en ninguna parte —el motor simplemente no la mira— y quien escribió el
# protocolo se queda creyendo que la regla se aplica. Eso ya pasó con
# `reglas_exclusion:`, `prioridades:` y `cena_puede_repetir_almuerzo:`.
#
# Si añades una clave al esquema, añádela también aquí, en el grupo que le toque.
CLAVES_PROTOCOLO_CONSUMIDAS = {
    "id",
    "nombre",
    "edad_min_meses",
    "edad_max_meses",
    "marco_diario",
    "comidas",
    "gramatica",
    "frecuencias_semanales",
    "rotaciones",
    "reglas_acopladas",
    "prioridades",
    "variedad",
    "preferencias_clinicas",
    "presupuesto_sensorial",
    "decisiones_pendientes",
}

# Declaradas en el protocolo, leídas por el validador y repetidas en el reporte,
# pero NO hechas cumplir por el motor. Se avisan en cada validación para que nadie
# las dé por aplicadas.
CLAVES_PROTOCOLO_SOLO_AVISO = {
    "introduccion_progresiva",
    "progresion_textura",
    "exclusiones_duras",
}

# Prosa para quien abre el archivo. Ningún módulo la lee, y está bien que así sea.
CLAVES_PROTOCOLO_DOCUMENTALES = {"descripcion"}

# Componentes exentos del filtro de `texturas_excluidas`.
#
# `texturas_excluidas` describe cómo COME el niño, no cómo bebe ni de qué está
# hecho por dentro un plato. Aplicarla a estos tres componentes es aplicarla
# donde no corresponde, y el daño no era cosmético: a un paciente que no tolera
# lo húmedo el filtro le quitaba el agua —que tiene textura `liquida`— y las
# tres grasas, es decir, la bebida y toda la densidad calórica del plan, que en
# un caso de bajo peso es justamente lo que hay que subir.
#
#   bebida          nadie con aversión textural deja de beber agua.
#   grasa           el aceite y la palta no se comen solos: son ingrediente.
#   ensalada_grasa  ídem. La textura que decide si el plato se come o termina
#                   en arcada es la del plato terminado, no la del aceite.
#
# Va como lista explícita y no como excepción dentro del filtro para que se vea
# al abrir el archivo: exonerar un componente del filtro de textura es una
# decisión clínica, y tiene que poder discutirse leyendo esta línea.
COMPONENTES_SIN_FILTRO_TEXTURA = {"bebida", "grasa", "ensalada_grasa", "suplemento"}

# El vocabulario cerrado de roles de la Capa 1. Un alimento puede PODER cubrir
# varios, pero en una comida dada ocupa exactamente uno: si «Crema de quinua» se
# usa como cereal, no cuenta como proteína de esa comida.
#
# `ancla` no se escribe en el catálogo. Lo concede la ficha del niño, en
# `perfil_sensorial.alimentos_ancla`, porque el alimento seguro es de ESE niño y
# no una propiedad del alimento.
ROLES_VALIDOS = {
    "cereal",
    "tuberculo",
    "menestra",
    "proteina_animal",
    "proteina_vegetal",
    "grasa",
    "fruta",
    "verdura",
    "lacteo",
    "bebida",
    "suplemento",
    "ancla",
}

# Los cuatro roles que cuentan como proteína para R-2.
ROLES_PROTEICOS = {"proteina_animal", "proteina_vegetal", "menestra", "lacteo"}

# Los dos roles que cuentan como carbohidrato para R-5.
ROLES_CARBOHIDRATO = {"cereal", "tuberculo"}

# Cómo se llama en la grilla un slot que se quedó sin ningún candidato válido.
#
# Un hueco declarado es un resultado profesional: dice qué falta, por qué reglas
# se vació el conjunto y qué receta lo cerraría. Un cereal ocupando el slot de la
# proteína es un error que la nutricionista ve en tres segundos.
HUECO = "[HUECO DECLARADO]"

# Componentes que NO exigen variedad: pueden repetirse sin límite y no cuentan
# para la comprobación de suficiencia de la biblioteca.
#
# El motor confundía dos cosas distintas bajo una sola condición ("¿es receta o
# alimento base?"). Que el arroz vaya a diario y que el agua vaya dos veces al
# día es normal: son fondo de plato y bebida, y nadie espera variedad ahí. Que
# el snack de media mañana sea el mismo las 14 veces de la quincena no lo es —
# y en selectividad severa no es solo aburrido, es contraproducente: la
# monotonía impuesta encoge el repertorio que el plan tendría que ampliar.
#
#   fondo de plato, guarnición, topping y bebida
#       carbohidrato · base_energetica · grasa · ensalada_grasa · crujiente ·
#       bebida
#   el plato en sí
#       base · acompanante · cereal · proteina · proteina_hierro · menestra ·
#       fruta · fruta_vitc · verdura
#
# `ensalada_grasa` y `crujiente` están en la primera lista por su papel, no por
# su nombre. La primera cumple el de `grasa` —vehículo de grasa que acompaña—,
# hasta el punto de que escolar_eliminacion_4 sustituye una por la otra. El
# `crujiente` son dos o tres cucharadas de grano inflado por encima de otra
# cosa: la variedad de esa comida la aporta la `base` que va debajo. Exigirles
# variedad no protege a nadie y hace imposibles protocolos que las piden a
# diario, que es rigor puesto donde no toca.
#
# Solo la primera lista vive aquí, porque es la excepción. Todo lo demás exige
# variedad, incluido lo que no aparezca en ninguna de las dos: si mañana se
# añade un componente y nadie se acuerda de clasificarlo, el sistema pecará de
# exigente y lo dirá, que es el lado correcto por el que equivocarse.
# Datos clínicos que no se imprimen sin decir de dónde salieron.
#
# La regla nació del primer caso real. El plan afirmaba en portada que «la
# hemoglobina de junio no está en ninguna fuente», y era verdad: no estaba. Pero
# nadie podía saber si eso significaba que el dato nunca existió, que vivía en un
# archivo que se perdió al adjuntar, o que estaba en una de las 88 páginas que
# nadie leyó entera. Las tres cosas se parecen mucho desde fuera y ninguna se
# arregla igual.
#
# Con procedencia, cada número del front-matter dice su documento y su página, y
# la pregunta se responde mirando la ficha. Sin ella, no se imprime: el dato se
# lista como faltante, que es información y no un hueco.
#
# Solo entra aquí lo que es un hallazgo clínico. `semanas_plan` o `porciones` no:
# el primero lo pide Paty en el chat y el segundo es aritmética sobre los otros.
CAMPOS_CLINICOS_CON_PROCEDENCIA = (
    "edad_meses",
    "peso_kg",
    "talla_cm",
    "zscore_pt",
    "zscore_te",
    "diagnosticos",
    "alergias",
    "requerimiento_kcal",
)

COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD = {
    "carbohidrato",
    "base_energetica",
    "grasa",
    "ensalada_grasa",
    "crujiente",
    "bebida",
    # El ancla y el suplemento se añadieron con la capa sensorial, y por la razón
    # contraria a la de los demás: no es que la variedad ahí no importe, es que
    # ahí la variedad está prohibida. El alimento seguro se sirve todos los días
    # y es el mismo; el suplemento es una indicación médica, no una rotación.
    "ancla",
    "suplemento",
}


class ErrorNutriOS(Exception):
    """Fallo controlado del motor. Se imprime limpio, sin traza."""


# ---------------------------------------------------------------------------
# Front-matter
# ---------------------------------------------------------------------------

_FM = re.compile(r"\A\s*---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def leer_front_matter(ruta: Path) -> tuple[dict, str]:
    """Devuelve (metadatos, cuerpo) de un .md con front-matter YAML."""
    texto = ruta.read_text(encoding="utf-8")
    m = _FM.match(texto)
    if not m:
        raise ErrorNutriOS(
            f"{ruta.name}: no tiene front-matter YAML delimitado por '---'."
        )
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ErrorNutriOS(f"{ruta.name}: front-matter mal formado — {e}") from e
    if not isinstance(meta, dict):
        raise ErrorNutriOS(f"{ruta.name}: el front-matter no es un diccionario.")
    return meta, m.group(2)


def normalizar(s: str) -> str:
    """Minúsculas, sin tildes, y un solo separador de palabra: el guion bajo.

    El guion normal se convierte también, y eso no es cosmético. El sistema
    compara «palabra completa» poniendo topes de guion bajo alrededor
    (`coincide_rechazo`), de modo que rechazar `res` no pueda excluir **Fresa**.
    Pero los ids de la biblioteca se escriben con guiones —`chifles-platano-
    bellaco`—, y con el guion sin convertir ese id no contenía nunca `_bellaco_`:
    la comparación fallaba en silencio y **un rechazo escrito en la ficha no
    excluía la base que lo llevaba en el nombre**.

    Es el mismo bug de los topes, del otro lado. Uno excluía de más y este
    excluía de menos, que es el lado por el que hace daño: el alimento rechazado
    llega al plato.
    """
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def coincide_rechazo(rechazo: str, opcion: "Opcion") -> bool:
    """¿El rechazo aparece como palabra o secuencia completa en la opción?

    Tolera el plural de la última palabra —solo la «s», solo al final—, y hace
    falta en las dos direcciones: la ficha escribe «frejol» y el catálogo dice
    «Frejol castilla» y «Frejoles»; escribe «lenteja» y el catálogo dice
    «Lentejas». Sin la tolerancia, un rechazo escrito en singular no excluía el
    alimento escrito en plural, que es el lado por el que hace daño.

    Lo que NO se toca es el tope: `res` sigue sin encontrar `Fresa`, porque los
    guiones bajos siguen puestos alrededor.
    """
    r = normalizar_texto(rechazo)
    if not r:
        return False
    for valor in (opcion.id, opcion.familia, opcion.nombre):
        if not valor:
            continue
        plano = f"_{normalizar_texto(valor)}_"
        if f"_{r}_" in plano or f"_{r}s_" in plano:
            return True
    return False


def exclusiones_del_nino(ficha: dict) -> list[str]:
    """Todo lo que este niño no puede comer, por el motivo que sea.

    La v2 separa las exclusiones en dos clases porque no se manejan igual:

      exclusiones_absolutas    alergia, intolerancia o indicación médica. No
                               cambian con el tiempo ni con la exposición.
      exclusiones_de_aversion  rechazo del niño. Reversible con exposición
                               planificada, pero **hoy es bloqueo duro**: «no
                               pan, ni pan con palta» significa que no hay
                               ninguna versión de ese plato aceptable hoy.

    El campo histórico `rechazos` es el nombre viejo del segundo, y se sigue
    leyendo: hay fichas escritas con él y ninguna razón para reescribirlas. Las
    tres listas se unen aquí, en un solo sitio, para que ningún filtro del motor
    mire una y se olvide de otra — que es exactamente cómo un rechazo escrito en
    la ficha llegaba al plato.
    """
    terminos: list[str] = []
    for clave in ("rechazos", "exclusiones_de_aversion", "exclusiones_absolutas"):
        for x in ficha.get(clave) or []:
            texto = str(x).strip()
            if texto and texto not in terminos:
                terminos.append(texto)
    return terminos


def exposiciones_declaradas(ficha: dict) -> dict[str, dict]:
    """Los alimentos nuevos que el plan introduce a propósito, normalizados.

    Admite las dos formas de escribirlo en la ficha, porque las dos se leen bien
    y obligar a la larga cuando basta la corta solo produce fichas más difíciles
    de revisar:

        exposiciones_planificadas:
          zanahoria: se introduce porque…                   # entra la semana 1
          naranja: {desde_semana: 2, porque: se introduce…}

    `desde_semana` existe por T-8: se introduce **un** alimento nuevo por
    semana, junto al ancla y en la franja de mejor disposición. Ocho pavitas en
    catorce días no son exposición graduada; son saturación.
    """
    salida: dict[str, dict] = {}
    for clave, valor in (ficha.get("exposiciones_planificadas") or {}).items():
        if isinstance(valor, dict):
            salida[str(clave)] = {
                "desde_semana": int(valor.get("desde_semana") or 1),
                "porque": str(valor.get("porque") or "").strip(),
            }
        else:
            salida[str(clave)] = {"desde_semana": 1, "porque": str(valor or "").strip()}
    return salida


def cargar_despensa_basica() -> set[str]:
    """Lo que puede aparecer sin estar en el repertorio aceptado del paciente.

    Vive aquí y no en el módulo de recetas porque ahora la usan dos: la
    comprobación de ingredientes de una receta instanciada y el filtro de
    repertorio del ensamblador. Nadie «acepta» la maicena ni rechaza el agua.
    """
    ruta = DIR_DATOS / "despensa_basica.yaml"
    if not ruta.exists():
        raise ErrorNutriOS(
            f"Falta {ruta.name}. Sin esa lista, cada receta tendría que declarar la "
            f"sal y el agua como introducciones nuevas, y el aviso que de verdad "
            f"protege al niño se ahogaría entre avisos que no protegen a nadie."
        )
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {
        normalizar(x)
        for grupo in datos.values()
        for x in (grupo or [])
        if str(x).strip()
    }


def es_despensa(nombre: str, despensa: set[str]) -> bool:
    """¿Este ingrediente es despensa básica?

    Se compara por el PRINCIPIO del nombre, no buscando la palabra en cualquier
    posición, y la diferencia importa: «cacao sin azúcar» contiene la palabra
    «azúcar», que sí es despensa, y con una comparación por contención el cacao
    entero quedaba exento. Un ingrediente con entidad propia se colaba en el
    plato de un niño con selectividad **por llevar la palabra "azúcar" en el
    nombre**, sin declararse como introducción nueva.

    Por el principio funciona: «aceite de oliva suave» empieza por «aceite»,
    «de sal» es «sal», y «cacao sin azúcar» no empieza por ningún básico.
    """
    n = normalizar_texto(nombre)
    for prefijo in ("de_", "del_", "la_", "el_"):
        if n.startswith(prefijo):
            n = n[len(prefijo):]
            break
    return any(
        n == b or n.startswith(b + "_")
        for b in (normalizar_texto(x) for x in despensa)
    )


def cargar_conceptos_aversivos() -> dict:
    ruta = DIR_DATOS / "conceptos_aversivos.yaml"
    if not ruta.exists():
        raise ErrorNutriOS(
            f"Falta {ruta.name}, que traduce el concepto aversivo del niño a los "
            f"rasgos visuales que hay que excluir.\n"
            f"    Sin él, «puntos negros» no filtra nada y el kiwi vuelve al plato."
        )
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def rasgos_aversivos(ficha: dict) -> tuple[set[str], list[str]]:
    """Los rasgos visuales que hay que excluir para este niño. (rasgos, problemas).

    Devuelve el conjunto ya normalizado y la lista de problemas: un concepto
    declarado en la ficha que no existe en el catálogo de conceptos no filtra
    nada, y eso es peor que no declararlo, porque hace creer que la aversión
    está contemplada. Quien llama decide si eso bloquea (el validador) o
    detiene (el ensamblador).
    """
    perfil = ficha.get("perfil_sensorial") or {}
    declarado = str(perfil.get("concepto_aversivo") or "").strip()
    if not declarado:
        return set(), []

    catalogo = (cargar_conceptos_aversivos().get("conceptos") or {})
    indice = {normalizar(k): v for k, v in catalogo.items()}
    entrada = indice.get(normalizar(declarado))
    if not entrada:
        return set(), [
            f"La ficha declara el concepto aversivo «{declarado}» y no existe en "
            f"datos/conceptos_aversivos.yaml, así que NO está excluyendo ningún rasgo.\n"
            f"    Conceptos reconocidos: {', '.join(sorted(catalogo)) or '(ninguno)'}.\n"
            f"    Un concepto que no filtra nada es peor que no declararlo: hace creer "
            f"que la aversión está contemplada. Añádelo al archivo con sus rasgos, o "
            f"corrige la frase en la ficha."
        ]
    return {normalizar(r) for r in (entrada.get("rasgos") or [])}, []


def conceder_ancla(opciones: list["Opcion"], ficha: dict) -> list[str]:
    """Marca como ancla las opciones que la ficha nombra alimento seguro.

    El ancla no es una propiedad del alimento sino de este niño, así que no
    puede vivir en el catálogo. Se concede aquí, sobre las opciones ya cargadas,
    y a partir de ese momento el alimento tiene el rol `ancla` disponible.

    Devuelve los términos de `alimentos_ancla` que no encontraron a nadie: un
    ancla que no existe en el catálogo deja el slot ANCLA vacío todos los días,
    que es exactamente lo que pasó cuando el alimento seguro desapareció 8 de
    14 días del plan.
    """
    declarados = [
        str(x).strip()
        for x in ((ficha.get("perfil_sensorial") or {}).get("alimentos_ancla") or [])
        if str(x).strip()
    ]
    huerfanos: list[str] = []
    for termino in declarados:
        golpes = [o for o in opciones if coincide_alimento(termino, o)]
        if not golpes:
            huerfanos.append(termino)
        for o in golpes:
            o.es_ancla = True
    return huerfanos


def coincide_alimento(termino: str, opcion: "Opcion") -> bool:
    """¿El término nombra a ESTE alimento? Solo id y nombre, nunca familia.

    Es la comparación que usan el repertorio aceptado, las exposiciones
    planificadas y el ancla, y se separa de `coincide_rechazo` a propósito.

    Un rechazo sí tiene que mirar la familia: «menestra» retira todas las
    menestras, y ese es su sentido. El repertorio es lo contrario: la familia
    es un cajón del protocolo, no un alimento, y usarla ensancha la lista sin
    que nadie lo escriba. Con la familia dentro pasaron dos cosas a la vez, y
    las dos malas: «pollo» en el repertorio dejaba entrar la **pavita**, que no
    aparece ni una vez en la anamnesis y salió ocho veces en catorce días; y
    declarar la **naranja** como exposición abría la puerta a la zanahoria y al
    zapallo, que comparten el cajón `verdura_naranja`.

    Lo que sí se conserva son los topes y la tolerancia de plural: «corbina»
    encuentra «Corbina en cubos», y «pecana» encuentra «Mantequilla de pecanas».
    """
    t = normalizar_texto(termino)
    if not t:
        return False
    for valor in (opcion.id, opcion.nombre):
        if not valor:
            continue
        plano = f"_{normalizar_texto(valor)}_"
        if f"_{t}_" in plano or f"_{t}s_" in plano:
            return True
    return False


def comprobar_rango_edad(protocolo: dict, ficha: dict) -> tuple[str, str]:
    """Comprueba el rango del protocolo y distingue los desvíos justificados."""
    edad = int(ficha["edad_meses"])
    protocolo_id = str(protocolo.get("id") or "(sin id)")
    edad_min = protocolo.get("edad_min_meses")
    edad_max = protocolo.get("edad_max_meses")
    if edad_min is None or edad_max is None:
        return (
            "fuera_sin_justificar",
            f"No se puede comprobar la edad del paciente ({edad} meses) contra el "
            f"protocolo «{protocolo_id}»: no declara un rango completo "
            "edad_min_meses–edad_max_meses.",
        )

    edad_min = int(edad_min)
    edad_max = int(edad_max)
    base = (
        f"La edad del paciente ({edad} meses) está fuera del rango del protocolo "
        f"«{protocolo_id}» ({edad_min}–{edad_max} meses)"
    )
    if edad_min <= edad <= edad_max:
        return (
            "dentro_de_rango",
            f"La edad del paciente ({edad} meses) está dentro del rango del protocolo "
            f"«{protocolo_id}» ({edad_min}–{edad_max} meses).",
        )

    justificacion = str(ficha.get("protocolo_fuera_de_rango") or "").strip()
    if justificacion:
        return (
            "fuera_justificado",
            f"{base}. Justificación declarada: {justificacion}",
        )
    return (
        "fuera_sin_justificar",
        f"{base} y la ficha no declara «protocolo_fuera_de_rango».",
    )


def comidas_activas(protocolo: dict, n_semana: int) -> list[dict]:
    """Las comidas que existen en esa semana del plan.

    `activo_desde_semana` sirve para las comidas que no arrancan el primer día:
    una media tarde que entra cuando el niño ya tolera dos tiempos, por ejemplo.
    Sin este filtro el campo era decorativo y la comida aparecía desde el lunes
    de la semana 1, que es justo lo contrario de lo que el protocolo declaraba.

    Ausente o vacío significa 1: activa desde el principio.
    """
    activas = []
    for comida in protocolo.get("comidas") or []:
        desde = comida.get("activo_desde_semana")
        if desde is None or int(desde) <= n_semana:
            activas.append(comida)
    return activas


def ajustes_clinicos(protocolo: dict, ficha: dict) -> tuple[list[dict], set[str], list[str]]:
    """Aplica los `preferencias_clinicas` de los diagnósticos de esta ficha.

    Devuelve tres cosas:

      frecuencias   la lista `frecuencias_semanales` del protocolo con
                    `subir_frecuencia` ya aplicado. Copia: el protocolo no se toca.
      exclusiones   las etiquetas de `exclusiones_extra`, normalizadas. Filtran
                    exactamente igual que una alergia declarada en la ficha.
      problemas     ajustes declarados que no se pueden aplicar, con su porqué.

    Es una función pura de (protocolo, ficha). El validador la llama por su
    cuenta y llega al mismo resultado sin mirar nada que haya producido el
    ensamblador: esa independencia es la razón de ser del validador y no se
    negocia. Lo que ambos comparten es la lectura del protocolo, no el plan.
    """
    protocolo_id = str(protocolo.get("id") or "(sin id)")
    prefs = protocolo.get("preferencias_clinicas") or {}
    frecuencias = [dict(r) for r in (protocolo.get("frecuencias_semanales") or [])]
    exclusiones: set[str] = set()
    problemas: list[str] = []

    for dx in ficha.get("diagnosticos") or []:
        ajuste = prefs.get(dx) or {}

        for etiqueta in ajuste.get("exclusiones_extra") or []:
            if str(etiqueta).strip():
                exclusiones.add(normalizar(etiqueta))

        subir = ajuste.get("subir_frecuencia")
        if not subir:
            continue
        for regla in subir if isinstance(subir, list) else [subir]:
            comp = regla.get("componente")
            familia = regla.get("familia")
            objetivo = regla.get("a")
            if not comp or objetivo is None:
                problemas.append(
                    f"«subir_frecuencia» de {dx} en el protocolo «{protocolo_id}» está "
                    f"incompleta: necesita «componente» y «a». Trae: {regla}."
                )
                continue
            candidatas = [
                r
                for r in frecuencias
                if r.get("componente") == comp
                and normalizar(r.get("familia") or "") == normalizar(familia or "")
                and r.get("modo") != "relleno"
                and not r.get("cada_dias")
                and r.get("veces") is not None
            ]
            if not candidatas:
                etiqueta = f"{comp}/{familia}" if familia else comp
                problemas.append(
                    f"«subir_frecuencia» de {dx} en el protocolo «{protocolo_id}» apunta a "
                    f"{etiqueta}, que no tiene ninguna regla de frecuencia con «veces» en "
                    f"«frecuencias_semanales»: no hay nada que subir y el ajuste no se "
                    f"aplica.\n"
                    f"    Solución: añade esa regla al protocolo, o corrige el nombre del "
                    f"componente/familia en «preferencias_clinicas»."
                )
                continue
            for r in candidatas:
                if int(objetivo) > int(r["veces"]):
                    r["veces"] = int(objetivo)
                if r.get("minimo") is not None and int(objetivo) > int(r["minimo"]):
                    r["minimo"] = int(objetivo)

    return frecuencias, exclusiones, problemas


def resolver_regla_acoplada(regla: dict, protocolo: dict) -> tuple[dict | None, str]:
    """Resuelve una regla acoplada o explica por qué no se puede aplicar."""
    protocolo_id = str(protocolo.get("id") or "(sin id)")
    comidas = {
        str(comida.get("id") or ""): set(comida.get("componentes") or [])
        for comida in protocolo.get("comidas") or []
        if comida.get("id")
    }
    componentes = {componente for lista in comidas.values() for componente in lista}
    disparador = str(regla.get("si") or "").strip()
    objetivo = str(regla.get("entonces") or "").strip()
    ambito = str(regla.get("ambito") or "misma_comida")

    if not disparador:
        return None, f"la regla del protocolo «{protocolo_id}» no declara «si»"
    if not objetivo:
        return None, f"la regla «{disparador}» del protocolo «{protocolo_id}» no declara «entonces»"
    if ambito not in {"misma_comida", "mismo_dia"}:
        return None, f"el ámbito «{ambito}» no es «misma_comida» ni «mismo_dia»"

    partes_disparador = disparador.split(".")
    if len(partes_disparador) == 1:
        componente_disparador = partes_disparador[0]
        familia_disparador = ""
        comidas_disparador = [
            comida for comida, comps in comidas.items() if componente_disparador in comps
        ]
        if not comidas_disparador:
            return None, (
                f"el disparador «{disparador}» no es un componente declarado en ninguna "
                f"comida del protocolo «{protocolo_id}»"
            )
    elif len(partes_disparador) == 2:
        primero, segundo = partes_disparador
        if primero in comidas:
            componente_disparador = segundo
            familia_disparador = ""
            if segundo not in comidas[primero]:
                return None, (
                    f"la comida «{primero}» no declara el componente «{segundo}» en el "
                    f"protocolo «{protocolo_id}»"
                )
            comidas_disparador = [primero]
        elif primero in componentes:
            componente_disparador = primero
            familia_disparador = segundo
            comidas_disparador = [
                comida for comida, comps in comidas.items() if primero in comps
            ]
        else:
            return None, (
                f"«{primero}» no es id de comida ni componente declarado en el "
                f"protocolo «{protocolo_id}»"
            )
    else:
        return None, f"el disparador «{disparador}» tiene más de un punto"

    partes_objetivo = objetivo.split(".")
    if len(partes_objetivo) == 1:
        componente_objetivo = partes_objetivo[0]
        comidas_objetivo = [
            comida for comida, comps in comidas.items() if componente_objetivo in comps
        ]
        if not comidas_objetivo:
            return None, (
                f"el objetivo «{objetivo}» no es un componente de ninguna comida del "
                f"protocolo «{protocolo_id}»"
            )
    elif len(partes_objetivo) == 2:
        comida_objetivo, componente_objetivo = partes_objetivo
        if comida_objetivo not in comidas:
            return None, (
                f"la comida objetivo «{comida_objetivo}» no existe en el protocolo "
                f"«{protocolo_id}»"
            )
        if componente_objetivo not in comidas[comida_objetivo]:
            return None, (
                f"la comida «{comida_objetivo}» no declara el componente objetivo "
                f"«{componente_objetivo}» en el protocolo «{protocolo_id}»"
            )
        comidas_objetivo = [comida_objetivo]
    else:
        return None, f"el objetivo «{objetivo}» tiene más de un punto"

    if ambito == "misma_comida":
        faltantes = [c for c in comidas_disparador if c not in comidas_objetivo]
        if faltantes:
            return None, (
                f"el objetivo «{objetivo}» no puede colocarse en "
                f"{', '.join(faltantes)}, donde puede dispararse «{disparador}»"
            )

    return (
        {
            "disparador_componente": componente_disparador,
            "disparador_familia": familia_disparador,
            "comidas_disparador": comidas_disparador,
            "objetivo_componente": componente_objetivo,
            "comidas_objetivo": comidas_objetivo,
            "ambito": ambito,
        },
        "",
    )


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


@dataclass
class Opcion:
    """Una cosa que puede ocupar una ranura del plan: receta o alimento base."""

    id: str
    nombre: str
    componente: str
    edad_min_meses: int
    alergenos: list[str] = field(default_factory=list)
    familia: str = ""
    momento: list[str] = field(default_factory=list)
    aporta: list[str] = field(default_factory=list)
    textura: str = ""
    nunca_recomendar: bool = False
    contraindicado_si: list[str] = field(default_factory=list)
    es_receta: bool = False
    validada_en_cocina: bool = False
    ruta: str = ""

    # --- Capa 1 · los tags sobre los que operan las reglas -----------------
    # Sin ellos ninguna regla se puede evaluar, así que van aquí y no en un
    # diccionario suelto: el día que falte uno, el validador lo dice por su
    # nombre en vez de fallar con un KeyError a mitad de una comprobación.
    roles: list[str] = field(default_factory=list)
    base_botanica: str = ""
    grano_base: str = ""
    demanda_oral: int | None = None
    carga_visual: int | None = None
    textura_mixta: bool = False
    unidad_natural: str = ""
    requiere_preparacion_segura: str = ""
    rasgos_visuales: list[str] = field(default_factory=list)
    hierro_no_hemo: bool = False
    hierro_hemo: bool = False
    vitamina_c: bool = False
    calcio_alto: bool = False
    fibra_alta: bool = False
    densidad_kcal: str = ""
    generico: bool = False
    forma_bocado: bool = True
    tiempo_min: int = 0
    refri_dias: int = 0
    # Se rellena en tiempo de ejecución, no viene del catálogo: el alimento
    # seguro es de ESTE niño. Ver `conceder_ancla`.
    es_ancla: bool = False

    def porcion_impresa(self, respaldo: str = "") -> str:
        """Lo que se escribe en la grilla al lado del nombre.

        Dos reglas juntas, y las dos salieron de un plan impreso:

        · **R-12 — la unidad la define el alimento, nunca el slot.** «Uva
          cortada a lo largo, ½ unidad mediana» y «Granola de kiwicha, ¾ taza
          (180 ml)» son el mismo error: la plantilla del componente imponiendo
          su unidad a lo que cayera dentro. Media uva no existe como porción, y
          la granola rinde cinco cucharadas de sólido seco.

        · **O-5 — el formato seguro se imprime en la grilla, no solo en la
          receta.** La madre lee la grilla, no el recetario, a las siete de la
          mañana. «Naranja, 3 gajos, sin hollejo ni pepa», no «Naranja, 1
          unidad».

        `respaldo` es la porción del slot, que solo se usa cuando el alimento no
        declara la suya. Es el camino de compatibilidad con los alimentos que
        todavía no tienen `unidad_natural`, y el validador lo marca.
        """
        base = (self.unidad_natural or respaldo or "").strip()
        formato = (self.requiere_preparacion_segura or "").strip()
        if base and formato:
            return f"{base}, {formato}"
        return base or formato

    def rol_para(self, roles_del_slot: list[str] | set[str]) -> str:
        """El rol con el que esta opción llenaría ese slot, o "" si no encaja.

        Es R-0. Un alimento solo puede ocupar un slot cuyo conjunto de roles
        aceptados contenga uno de los suyos, y el generador **no puede** cubrir
        un slot con un alimento de rol distinto aunque «se parezca». Esta sola
        regla habría bloqueado tres de los siete desayunos auditados: la crema
        de quinua es cereal y ocupó el slot de la proteína; el bastón de papa es
        tubérculo y ocupó el mismo.
        """
        aceptados = set(roles_del_slot or [])
        if not aceptados:
            return self.roles[0] if self.roles else ""
        mios = list(self.roles)
        if self.es_ancla and "ancla" not in mios:
            mios.append("ancla")
        for rol in mios:
            if rol in aceptados:
                return rol
        return ""

    def responde_a(self, clave: str) -> bool:
        """¿Este alimento responde a una clave del protocolo? Familia o id.

        El protocolo nombra alimentos en dos niveles, y los dos son legítimos:

          {tuberculo: 4}   el cajón — "cuatro tubérculos por semana", y que el
                           catálogo decida cuál según el paciente y su región.
          {camote: 2}      el alimento — cuando hay una razón clínica para ESE
                           alimento y no para su cajón.

        Sin el segundo nivel, escribir un protocolo obligaría a elegir entre
        abrirlo a la región o conservar el criterio clínico fino. Con los dos,
        una misma rotación puede mezclarlos: {camote: 2, tuberculo: 2, grano: resto}.
        """
        if not clave:
            return True
        c = normalizar(clave)
        return c == normalizar(self.familia) or c == normalizar(self.id)

    def apta_para(
        self,
        ficha: dict,
        exclusiones_extra: set[str] | None = None,
        rasgos_excluidos: set[str] | None = None,
    ) -> tuple[bool, str]:
        """¿Puede esta opción entrar en el plan de este paciente?

        `exclusiones_extra` son las etiquetas que el protocolo excluye por el
        diagnóstico (APLV → lácteos, por ejemplo). Filtran exactamente igual que
        una alergia escrita en la ficha, y a propósito: la madre de un niño con
        APLV no tiene por qué escribir "lácteos" en la lista de alergias para que
        el motor deje de ponerle yogurt.
        """
        # Va primero, antes que la edad y antes que las alergias: no depende de
        # este paciente ni admite excepción. Es una decisión clínica de Paty
        # escrita en el catálogo para que no dependa de que alguien se acuerde.
        if self.nunca_recomendar:
            return False, "marcado 'nunca_recomendar' en el catálogo"
        # Una base puede declarar en qué cuadro clínico no se usa. Las reglas de
        # seguridad de una base son prosa —para quien cocina— y el motor no las
        # lee: `contraindicado_si` es la parte de esa prosa que sí tiene que
        # poder leer, porque decide si la base entra o no.
        #
        # Sin este campo pasó lo previsible: la base de barritas dice, con esas
        # palabras, «con riesgo de disfagia esta base no se usa: es seca,
        # compacta y pegajosa a la vez, que es el peor perfil de bolo posible»,
        # y el ensamblador se la puso igual a un paciente con riesgo de disfagia
        # declarado. La advertencia estaba escrita y no servía de nada.
        for bandera in self.contraindicado_si:
            if ficha.get(str(bandera)):
                return False, f"contraindicada si «{bandera}»"

        if self.edad_min_meses > ficha["edad_meses"]:
            return False, f"edad mínima {self.edad_min_meses} m"
        alergias = {normalizar(a) for a in ficha.get("alergias") or []}
        etiquetas = {normalizar(a) for a in self.alergenos}
        choque = alergias & etiquetas
        if choque:
            return False, f"alérgeno: {', '.join(sorted(choque))}"
        choque_dx = (exclusiones_extra or set()) & etiquetas
        if choque_dx:
            return False, f"excluido por diagnóstico: {', '.join(sorted(choque_dx))}"
        for termino in exclusiones_del_nino(ficha):
            if coincide_rechazo(termino, self):
                return False, "rechazo declarado"

        # T-6 · Generalización aversiva. Se filtra por el RASGO, no por el
        # alimento. Declarado «puntos negros», quedan fuera el kiwi, la fresa
        # entera, la uva con pepa, la granola y los granos reventados aunque
        # nadie los haya nombrado nunca. Un sistema que filtra por lista de
        # alimentos siempre va un paso atrás del niño: la lista se escribe con
        # lo que ya rechazó, y el siguiente rechazo nunca está en ella.
        choque_rasgo = set(rasgos_excluidos or set()) & {
            normalizar(r) for r in self.rasgos_visuales
        }
        if choque_rasgo:
            return False, f"T-6 rasgo aversivo: {', '.join(sorted(choque_rasgo))}"

        # La aversión a una textura no es una manía: en selectividad severa y en
        # disfagia decide si el plato se come o si termina en arcada. Se filtra
        # igual que un rechazo, pero por su propio campo, porque el nombre del
        # alimento nunca la delata ("compota de pera" no dice "aguado").
        excluidas = {normalizar(t) for t in ficha.get("texturas_excluidas") or []}
        if (
            excluidas
            and self.componente not in COMPONENTES_SIN_FILTRO_TEXTURA
            and normalizar(self.textura) in excluidas
        ):
            return False, f"textura {self.textura}"
        return True, ""


# ---------------------------------------------------------------------------
# Cargadores
# ---------------------------------------------------------------------------


def cargar_protocolo(id_protocolo: str) -> dict:
    ruta = DIR_PROTOCOLOS / f"{id_protocolo}.yaml"
    if not ruta.exists():
        disponibles = sorted(p.stem for p in DIR_PROTOCOLOS.glob("*.yaml"))
        raise ErrorNutriOS(
            f"No existe el protocolo '{id_protocolo}'. Disponibles: {', '.join(disponibles)}"
        )
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ErrorNutriOS(
            f"El protocolo '{id_protocolo}.yaml' tiene YAML mal formado.\n"
            f"    Detalle: {e}"
        ) from e


def _entero_o_none(valor: Any) -> int | None:
    """N0–N5 y V0–V3 admiten el cero, así que `or None` no sirve aquí."""
    if valor is None or str(valor).strip() == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _tags_sensoriales(d: dict) -> dict:
    """Los campos de la Capa 1, leídos igual desde el catálogo y desde una base.

    Vive en una sola función porque el alimento y la receta se etiquetan con el
    mismo vocabulario y las reglas no distinguen entre los dos: R-1 compara
    `grano_base` de una avena con el `grano_base` de unos panqueques de avena, y
    si cada lado lo leyera a su manera volveríamos a tener «avena + panqueques
    de avena» en el mismo desayuno.
    """
    conservacion = d.get("conservacion") or {}
    return {
        "roles": [str(r) for r in (d.get("roles") or [])],
        "base_botanica": str(d.get("base_botanica") or ""),
        "grano_base": str(d.get("grano_base") or ""),
        "demanda_oral": _entero_o_none(d.get("demanda_oral")),
        "carga_visual": _entero_o_none(d.get("carga_visual")),
        "textura_mixta": bool(d.get("textura_mixta", False)),
        "unidad_natural": str(d.get("unidad_natural") or ""),
        "requiere_preparacion_segura": str(d.get("requiere_preparacion_segura") or ""),
        "rasgos_visuales": [str(r) for r in (d.get("rasgos_visuales") or [])],
        "hierro_no_hemo": bool(d.get("hierro_no_hemo", False)),
        "hierro_hemo": bool(d.get("hierro_hemo", False)),
        "vitamina_c": bool(d.get("vitamina_c", False)),
        "calcio_alto": bool(d.get("calcio_alto", False)),
        "fibra_alta": bool(d.get("fibra_alta", False)),
        "densidad_kcal": str(d.get("densidad_kcal") or ""),
        "generico": bool(d.get("generico", False)),
        "forma_bocado": bool(d.get("forma_bocado", True)),
        "tiempo_min": int(d.get("tiempo_min") or 0),
        "refri_dias": int(conservacion.get("refri_dias") or 0),
    }


def cargar_alimentos_base() -> list[Opcion]:
    ruta = DIR_DATOS / "alimentos_base.yaml"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    opciones: list[Opcion] = []
    for componente, lista in datos.items():
        for a in lista or []:
            opciones.append(
                Opcion(
                    id=a["id"],
                    nombre=a["nombre"],
                    componente=componente,
                    edad_min_meses=int(a.get("edad_min_meses", 0)),
                    alergenos=a.get("alergenos") or [],
                    familia=a.get("familia") or a["id"],
                    aporta=a.get("aporta") or [],
                    textura=str(a.get("textura") or ""),
                    nunca_recomendar=bool(a.get("nunca_recomendar", False)),
                    es_receta=False,
                    ruta=str(ruta.relative_to(RAIZ)),
                    **_tags_sensoriales(a),
                )
            )
    return opciones


def cargar_biblioteca() -> tuple[list[Opcion], list[str]]:
    """Lee /biblioteca/*.md. Devuelve (opciones, avisos).

    Lo que hay en /biblioteca/ son BASES, no recetas terminadas. Una base es una
    técnica más un esqueleto de ingredientes más sus reglas de seguridad
    —«lenteja colada sin cáscara», «pescado de pulpa blanca dorado, sin vetas
    oscuras»—, y **no se imprime nunca**.

    El cambio no es de nomenclatura. Antes, cuando un requerimiento del paciente
    coincidía con una receta de la biblioteca, el motor la metía tal cual, y así
    fue como a un niño que en la anamnesis dice literalmente «no pan, ni pan con
    palta» le salió el pan con palta en el plan. Paty nunca sirve una receta tal
    cual: adapta porción, textura, ingredientes y presentación a cada niño.

    Lo que se acumula y mejora entre pacientes es la técnica. El plato, no.

    `alergenos_posibles` es lo que la técnica PUEDE traer según cómo se
    instancie, y se usa para filtrar: una base que puede llevar huevo no se le
    ofrece a un niño alérgico al huevo aunque exista una versión sin él, porque
    el margen de error no compensa.
    """
    opciones: list[Opcion] = []
    avisos: list[str] = []
    obligatorios = ("id", "titulo", "edad_min_meses", "componente")

    for ruta in sorted(DIR_BIBLIOTECA.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        try:
            meta, _ = leer_front_matter(ruta)
        except ErrorNutriOS as e:
            avisos.append(str(e))
            continue

        faltan = [c for c in obligatorios if meta.get(c) in (None, "")]
        if faltan:
            avisos.append(f"{ruta.name}: faltan campos {', '.join(faltan)} — se omite.")
            continue

        if str(meta.get("tipo") or "") != "base":
            avisos.append(
                f"{ruta.name}: no declara «tipo: base». Desde el rediseño de la "
                f"biblioteca, /biblioteca/ guarda bases —técnica + esqueleto + reglas "
                f"de seguridad—, no recetas terminadas; una receta terminada aquí "
                f"volvería a servirse tal cual a un niño al que no se le adaptó. "
                f"Se omite."
            )
            continue

        opciones.append(
            Opcion(
                id=str(meta["id"]),
                nombre=str(meta["titulo"]),
                componente=str(meta["componente"]),
                edad_min_meses=int(meta["edad_min_meses"]),
                alergenos=meta.get("alergenos_posibles") or [],
                familia=str(meta.get("familia") or ""),
                momento=meta.get("momento") or [],
                aporta=meta.get("aporta") or [],
                textura=str(meta.get("textura") or ""),
                nunca_recomendar=bool(meta.get("nunca_recomendar", False)),
                contraindicado_si=meta.get("contraindicado_si") or [],
                es_receta=True,
                validada_en_cocina=bool(meta.get("validada_en_cocina", False)),
                ruta=str(ruta.relative_to(RAIZ)),
                **_tags_sensoriales(meta),
            )
        )
    return opciones, avisos


def cargar_ficha(carpeta_paciente: Path) -> dict:
    ruta = carpeta_paciente / "ficha.md"
    if not ruta.exists():
        raise ErrorNutriOS(
            f"No existe {ruta}. Ejecuta primero la Fase 1 (prompts/PC_CLINICO.md)."
        )
    meta, cuerpo = leer_front_matter(ruta)

    obligatorios = ["paciente", "edad_meses", "semanas_plan", "protocolo_sugerido", "porciones"]
    faltan = [c for c in obligatorios if meta.get(c) in (None, "")]
    if faltan:
        raise ErrorNutriOS(f"ficha.md: faltan campos obligatorios: {', '.join(faltan)}")

    if meta.get("bloqueantes"):
        raise ErrorNutriOS(
            "La ficha declara bloqueantes; el pipeline se detiene:\n  - "
            + "\n  - ".join(meta["bloqueantes"])
        )

    meta["_cuerpo"] = cuerpo
    return meta


# ---------------------------------------------------------------------------
# Alérgenos: de la lista de ingredientes a las etiquetas
# ---------------------------------------------------------------------------
#
# Vive aquí, y no en el script que lo usa, porque ahora lo usan tres: revisar.py
# audita la biblioteca, validar.py bloquea el render de una receta cuyo bloque
# de alérgenos no cuadre con sus ingredientes, y la instanciación lo usa para
# escribir el bloque en vez de adivinarlo.
#
# Que la misma pregunta —«¿qué alérgenos lleva esta lista de ingredientes?»— se
# respondiera en dos sitios con dos códigos distintos es exactamente cómo la
# avena acabó etiquetada de tres formas diferentes en tres recetas.


def cargar_tabla_alergenos() -> dict:
    ruta = DIR_DATOS / "alergenos_ingredientes.yaml"
    if not ruta.exists():
        raise ErrorNutriOS(
            f"Falta {ruta.name}, que es la tabla de ingrediente → alérgeno.\n"
            f"    Sin ella no se puede comprobar si una receta declara lo que lleva, "
            f"y eso es lo único que separa a un niño alérgico de su alérgeno."
        )
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def normalizar_texto(s: str) -> str:
    """Como `normalizar`, pero para prosa: TODA puntuación separa palabras.

    `normalizar` sirve para ids, donde solo hay letras, guiones y guiones bajos.
    Una línea de ingredientes es otra cosa: lleva comas, paréntesis, asteriscos
    de negrita y el punto medio de la métrica.

    Sin esto, la coma se comía la comparación. `• **50 g** filete de pechuga de
    pollo, sin piel` no contenía `_pollo_` —después de «pollo» venía una coma, no
    un tope— y el sistema concluía que el pollo no estaba en el repertorio de un
    niño que come pollo. Del mismo modo, `mantequilla de maní, de pecanas` no
    activaba la excepción de lácteos y la receta salía declarando un alérgeno que
    no lleva.

    Los dos fallos son el mismo y son la otra cara del bug de `res`/`Fresa`: si
    los topes son la herramienta, todo lo que separa palabras tiene que ser tope.
    """
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c if c.isalnum() else "_" for c in s.lower())
    return re.sub(r"_+", "_", s).strip("_")


def _con_topes(texto: str) -> str:
    """La línea normalizada y con topes, para buscar palabras completas.

    'mani' no puede encontrar 'manzana' ni 'mandarina', y 'res' no puede
    encontrar 'fresa'. Por eso se compara con los guiones bajos puestos.
    """
    return "_" + normalizar_texto(texto) + "_"


def lineas_ingredientes(cuerpo: str) -> list[str]:
    """Las viñetas de la sección '## Ingredientes' de una receta."""
    m = re.search(
        r"^##\s+Ingredientes\s*$(.*?)(?=^##\s|\Z)",
        cuerpo,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    return [l.strip() for l in m.group(1).splitlines() if l.strip().startswith("•")]


def alergenos_de_ingredientes(lineas: list[str], tabla: dict) -> set[str]:
    """Qué alérgenos delatan estas líneas de ingredientes."""
    hallados: set[str] = set()
    for linea in lineas:
        clave = _con_topes(linea)
        for etiqueta, regla in tabla.items():
            if any(_con_topes(x) in clave for x in (regla.get("excepciones") or [])):
                continue
            if any(_con_topes(t) in clave for t in (regla.get("terminos") or [])):
                hallados.add(etiqueta)
    return hallados


# ---------------------------------------------------------------------------
# Recetas instanciadas para un paciente
# ---------------------------------------------------------------------------


def cargar_recetas_instanciadas(carpeta_paciente: Path) -> tuple[dict[str, dict], list[str]]:
    """Lee pacientes/<paciente>/recetas/*.md. Devuelve ({id_base: receta}, avisos).

    Estas son las recetas que se imprimen. La biblioteca guarda bases —técnica,
    esqueleto y reglas de seguridad—, y una base no se imprime nunca: lo que
    llega al recetario es la base ya resuelta contra ESTE niño, con su porción,
    su textura y sus ingredientes.

    La clave del diccionario es el id de la base, porque es lo que el plan
    escribe en `receta_id`.
    """
    directorio = carpeta_paciente / DIR_RECETAS_PACIENTE
    recetas: dict[str, dict] = {}
    avisos: list[str] = []
    if not directorio.exists():
        return recetas, avisos

    for ruta in sorted(directorio.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        try:
            meta, cuerpo = leer_front_matter(ruta)
        except ErrorNutriOS as e:
            avisos.append(str(e))
            continue
        base = str(meta.get("base") or meta.get("id") or ruta.stem)
        recetas[base] = {"meta": meta, "cuerpo": cuerpo, "ruta": ruta}
    return recetas, avisos


def huella_plan(ruta: Path) -> str:
    """SHA-256 del plan.json tal cual está en disco.

    El validador la escribe en el reporte y el renderizador la comprueba antes
    de maquetar. Sin esto, "el renderizador se niega a trabajar si el validador
    marcó BLOQUEADO" era una garantía que se saltaba con dos comandos: validar
    un plan bueno y volver a ensamblar otro sin validarlo dejaba en la carpeta
    un reporte APTO junto a un plan que nadie había mirado.
    """
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def guardar_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
