"""
Recetas instanciadas — Nutri-OS

Comprueba las recetas que se van a imprimir: las de
`pacientes/<paciente>/recetas/`, ya resueltas contra este niño.

Qué comprueba, y por qué cada cosa está aquí y no en un prompt:

  · **Existe una receta por cada base que usa el plan.** Sin esto, el pipeline
    volvería a imprimir bases sin adaptar, que es el fallo que se está
    arreglando. Es una comprobación de completitud, no de criterio.

  · **Ningún ingrediente nombrado como rechazado.** Bloqueo duro, sin excepción
    de exposición planificada. «No pan, ni pan con palta» significa que no hay
    versión de esa receta aceptable para ese niño, y eso no lo puede negociar
    ningún modelo por bien que argumente.

  · **Todo ingrediente fuera del repertorio va declarado.** El código no decide
    qué come el niño: exige que la decisión esté escrita. Un ingrediente nuevo
    o entra declarado como exposición planificada —y sale marcado en el informe
    para que Paty lo apruebe— o no entra.

  · **El bloque de alérgenos cuadra con la lista de ingredientes.** Verificación
    aritmética contra datos/alergenos_ingredientes.yaml. Una receta que declara
    lo que no lleva descarta pacientes sin motivo; una que calla lo que sí lleva
    llega al plato de un niño alérgico.

  · **Ninguna marca de plantilla sin resolver.** «Aplasta hasta la textura que
    corresponda a la edad» salió impreso en el documento de un paciente de 4
    años y medio. Si el sistema sabe la edad, la textura la resuelve el sistema,
    no la madre leyendo la receta.

Nada de esto juzga si la receta es buena. Eso lo juzga el modelo con
prompts/P1_RECETAS.md. Aquí solo se comprueba lo que nunca puede salir.
"""

from __future__ import annotations

import re
from pathlib import Path

from comun import (
    DIR_RECETAS_PACIENTE,
    alergenos_de_ingredientes,
    cargar_despensa_basica,
    cargar_recetas_instanciadas,
    cargar_tabla_alergenos,
    es_despensa,
    exclusiones_del_nino,
    lineas_ingredientes,
    normalizar,
    normalizar_texto,
)

# Marcadores de plantilla que no pueden llegar a un PDF. Se comparan
# normalizados, así que las tildes y las mayúsculas dan igual.
#
# La lista es corta a propósito: son los que se han visto impresos de verdad,
# no una batida preventiva contra todo lo que suene a genérico.
MARCADORES_PLANTILLA = [
    "la textura que corresponda a la edad",
    "la textura que corresponde a la edad",
    "segun la edad del paciente",
    "la cantidad que corresponda",
    "[cantidad]",
    "[ingrediente]",
    "[x]",
    "por definir",
    "a completar",
]


def _nombre_ingrediente(linea: str) -> str:
    """El ingrediente de una viñeta, sin la viñeta, la cantidad ni la métrica.

    Formato de P1:  `• **1 taza** harina de avena · 100 g`
    """
    texto = linea.lstrip("• ").strip()
    texto = re.sub(r"\*\*.*?\*\*", " ", texto)      # la cantidad en negrita
    texto = texto.split("·")[0]                      # la métrica de respaldo
    texto = re.split(r"\(", texto)[0]                # las aclaraciones
    return " ".join(texto.split()).strip(" ,.;:")


def _menciona(termino: str, texto: str) -> bool:
    """¿Aparece el término como palabra completa en el texto?

    Con los topes puestos, igual que en el resto del sistema: rechazar `res` no
    puede excluir `Fresa`, y `mani` no puede encontrar `manzana`. Y con toda la
    puntuación convertida en tope, para que una coma no rompa la comparación —
    ver `normalizar_texto`.

    Tolera el plural de la última palabra, y hace falta: la ficha escribe el
    repertorio en singular —«fresa», «pecana»— y una receta escribe «fresas
    maduras» o «mantequilla de pecanas». Sin esta tolerancia, el sistema exigía
    declarar como introducción nueva una fresa que el niño come desde siempre, y
    ese aviso falso es el que enseña a ignorar los avisos verdaderos.

    Solo la «s», y solo al final. Nada de lematizar: un plural mal deshecho une
    palabras que no son la misma, y aquí unir dos alimentos distintos es
    exactamente lo que no puede pasar.
    """
    t = normalizar_texto(termino)
    if not t:
        return False
    plano = f"_{normalizar_texto(texto)}_"
    return f"_{t}_" in plano or f"_{t}s_" in plano


def revisar_receta(
    base_id: str,
    receta: dict,
    ficha: dict,
    tabla: dict,
    despensa: set[str],
) -> tuple[list[str], list[str]]:
    """Devuelve (errores, avisos) de una receta instanciada."""
    errores: list[str] = []
    avisos: list[str] = []
    meta = receta["meta"]
    # La Nota para Paty es interna y el renderizador la corta antes de maquetar,
    # así que lo que se comprueba aquí es lo que de verdad se imprime. Sin este
    # corte, una Nota que explica «el paso decía "la textura que corresponda a la
    # edad" y lo sustituí por 2 cm» hacía saltar el detector de marcadores de
    # plantilla: el aviso se disparaba justo con la receta que había arreglado el
    # problema.
    cuerpo = receta["cuerpo"].split("--- NOTA PARA PATY ---")[0]
    ruta = receta["ruta"]
    titulo = str(meta.get("titulo") or base_id)
    donde = f"{ruta.parent.name}/{ruta.name}"

    # --- coherencia con el paciente ---------------------------------------
    if str(meta.get("paciente") or "") != str(ficha.get("paciente") or ""):
        errores.append(
            f"{donde}: la receta dice ser de «{meta.get('paciente')}» y la ficha es de "
            f"«{ficha.get('paciente')}». Una receta instanciada pertenece a un solo "
            f"niño: si esta viene de otro caso, vuelve a instanciarla contra esta ficha "
            f"en vez de copiarla."
        )

    lineas = lineas_ingredientes(cuerpo)
    if not lineas:
        errores.append(
            f"{donde}: no tiene sección «## Ingredientes» con viñetas «•», así que no "
            f"se puede comprobar ni un alérgeno ni un rechazo. Ninguna receta se "
            f"imprime sin que su lista de ingredientes sea legible por el validador."
        )
        return errores, avisos

    ingredientes = [_nombre_ingrediente(l) for l in lineas]

    # --- 1. Rechazos: bloqueo duro, sin excepción --------------------------
    for rechazo in exclusiones_del_nino(ficha):
        golpes = [i for i in ingredientes if _menciona(rechazo, i)]
        if golpes:
            errores.append(
                f"{donde} «{titulo}»: lleva {', '.join(golpes)}, y «{rechazo}» está "
                f"nombrado como rechazado en la ficha de este paciente.\n"
                f"    Un ingrediente rechazado es bloqueo duro y NO admite excepción de "
                f"exposición planificada: no hay ninguna versión de esta receta que sea "
                f"aceptable para este niño.\n"
                f"    Solución: instancia la base con otro ingrediente para ese papel, o "
                f"descarta la base entera para este paciente y vuelve a ensamblar."
            )

    # --- 2. Fuera del repertorio: o va declarado, o no va ------------------
    repertorio = [str(x) for x in (ficha.get("repertorio_aceptado") or [])]
    expuestos = meta.get("exposicion_planificada") or {}
    if isinstance(expuestos, list):
        expuestos = {str(x): "" for x in expuestos}

    if repertorio:
        for crudo, nombre in zip(lineas, ingredientes):
            if not nombre:
                continue
            if es_despensa(nombre, despensa):
                continue
            if any(_menciona(r, nombre) for r in repertorio):
                continue
            declarado = next(
                (k for k in expuestos if _menciona(k, nombre) or _menciona(nombre, k)),
                None,
            )
            if declarado:
                justificacion = str(expuestos[declarado] or "").strip()
                if not justificacion:
                    errores.append(
                        f"{donde} «{titulo}»: «{nombre}» se declara como exposición "
                        f"planificada pero sin justificación. Una introducción nueva sin "
                        f"un porqué escrito no se le puede presentar a Paty para que la "
                        f"apruebe.\n"
                        f"    Solución: en el front-matter, «exposicion_planificada: "
                        f"{{{declarado}: <por qué se introduce ahora>}}»."
                    )
                else:
                    avisos.append(
                        f"EXPOSICIÓN PLANIFICADA · {titulo}: «{nombre}» no está en el "
                        f"repertorio aceptado y se introduce a propósito — "
                        f"{justificacion} · PENDIENTE DEL VISTO BUENO DE PATY."
                    )
                continue
            errores.append(
                f"{donde} «{titulo}»: «{nombre}» no está en el repertorio aceptado de "
                f"la ficha, no es despensa básica y no se declara como exposición "
                f"planificada.\n"
                f"    Línea: {crudo}\n"
                f"    Un ingrediente nuevo no entra de tapadillo en el plato de un niño "
                f"con selectividad: o se decide introducirlo y se dice, o no entra.\n"
                f"    Solución: cámbialo por algo del repertorio, o declara "
                f"«exposicion_planificada: {{{nombre}: <justificación>}}» en el "
                f"front-matter — así saldrá marcado en el informe para que Paty lo "
                f"apruebe antes de entregarlo."
            )

    # --- 3. Alérgenos: presencias, no solo ausencias -----------------------
    declarados = {normalizar(a) for a in (meta.get("alergenos_presentes") or [])}
    implicados = alergenos_de_ingredientes(lineas, tabla)
    faltan = sorted(implicados - declarados)
    sobran = sorted(declarados - implicados)

    if meta.get("alergenos_presentes") is None:
        errores.append(
            f"{donde} «{titulo}»: no declara «alergenos_presentes» en el front-matter. "
            f"Ninguna receta sale sin bloque de alérgenos.\n"
            f"    Si no lleva ninguno, se escribe la lista vacía «[]» y el bloque dirá "
            f"que no tiene. El silencio no puede significar dos cosas distintas: hoy una "
            f"madre que ve «sin gluten · sin huevo» en una receta y NADA en la milanesa "
            f"puede leer la ausencia de etiqueta como ausencia de alérgeno."
        )
    elif faltan:
        errores.append(
            f"{donde} «{titulo}»: sus ingredientes llevan {', '.join(faltan)} y el "
            f"bloque de alérgenos no lo declara. **Esta receta no se renderiza.**\n"
            f"    Un falso negativo aquí llega al plato de un niño alérgico.\n"
            f"    Solución: añade {', '.join(faltan)} a «alergenos_presentes», o corrige "
            f"datos/alergenos_ingredientes.yaml si el término no corresponde de verdad."
        )
    if sobran:
        avisos.append(
            f"{titulo}: declara {', '.join(sobran)} y ningún ingrediente lo delata. "
            f"Declarar de más es seguro, pero descarta la receta para pacientes que sí "
            f"podrían comerla."
        )

    # --- 4. Marcadores de plantilla ----------------------------------------
    plano = normalizar(cuerpo).replace("_", " ")
    for marcador in MARCADORES_PLANTILLA:
        if normalizar(marcador).replace("_", " ") in plano:
            errores.append(
                f"{donde} «{titulo}»: conserva el marcador de plantilla «{marcador}».\n"
                f"    Eso es una instrucción sin resolver impresa en el documento de una "
                f"familia. El sistema sabe la edad del paciente "
                f"({ficha.get('edad_texto') or ficha.get('edad_meses')}): la textura, la "
                f"cantidad y el corte los resuelve la receta, no la madre leyéndola.\n"
                f"    Solución: sustitúyelo por el valor concreto para este niño."
            )

    return errores, avisos


def revisar(plan: dict, ficha: dict, carpeta: Path) -> tuple[list[str], list[str]]:
    """Todas las recetas que el plan usa. Devuelve (errores, avisos)."""
    errores: list[str] = []
    avisos: list[str] = []

    usadas = list(plan.get("recetas_usadas") or [])
    if not usadas:
        return errores, avisos

    recetas, avisos_lectura = cargar_recetas_instanciadas(carpeta)
    avisos += [f"Recetas del paciente: {a}" for a in avisos_lectura]

    faltan = [rid for rid in usadas if rid not in recetas]
    if faltan:
        errores.append(
            "El plan usa "
            + str(len(faltan))
            + " base(s) que todavía no se han instanciado para este paciente: "
            + ", ".join(faltan)
            + ".\n"
            "    Una base de /biblioteca/ es una técnica, no un plato, y no se imprime "
            "nunca. Lo que va al recetario es la base resuelta contra ESTE niño: su "
            "porción, su textura, sus ingredientes y su presentación.\n"
            "    Solución: por cada una, abre una conversación limpia con "
            "prompts/P1_RECETAS.md, pásale el bloque CONTEXTO de la ficha y la base de "
            "partida, y guarda la salida en "
            f"pacientes/{carpeta.name}/{DIR_RECETAS_PACIENTE}/<id>.md. Después vuelve a "
            "validar."
        )

    tabla = cargar_tabla_alergenos()
    despensa = cargar_despensa_basica()
    for rid in usadas:
        if rid not in recetas:
            continue
        e, a = revisar_receta(rid, recetas[rid], ficha, tabla, despensa)
        errores += e
        avisos += a

    sobrantes = sorted(set(recetas) - set(usadas))
    if sobrantes:
        avisos.append(
            "Hay recetas instanciadas que este plan ya no usa: "
            + ", ".join(sobrantes)
            + ". No estorban —son el registro de lo que se entregó en un control "
            "anterior— pero no entran en el recetario de ahora."
        )
    return errores, avisos
