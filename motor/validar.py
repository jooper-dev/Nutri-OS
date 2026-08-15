"""
Validador clínico — Nutri-OS · Fase 5

Vuelve a comprobar el plan ya ensamblado, sin confiar en el ensamblador.
Es deliberadamente independiente: lee el protocolo y la ficha por su cuenta y
recuenta todo desde cero. Si el motor tuviera un error, aquí se cae.

Sustituye a la antigua "Fase 4 · Self-QA", donde un modelo se auditaba a sí mismo.
Aquí no hay criterio ni interpretación: hay aritmética.

Salidas:
  ERROR   detiene el pipeline. Nada llega al PDF.
  AVISO   no detiene, pero aparece arriba del todo para que Paty lo lea.

Uso:
    python motor/validar.py <nombre_carpeta_paciente>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import parada_clinica
import recetas_paciente
import reglas
from comun import (
    HUECO,
    cargar_despensa_basica,
    cargar_recetas_instanciadas,
    conceder_ancla,
    es_despensa,
    exposiciones_declaradas,
    rasgos_aversivos,
    CAMPOS_CLINICOS_CON_PROCEDENCIA,
    CLAVES_PROTOCOLO_SOLO_AVISO,
    COMPONENTES_SIN_FILTRO_TEXTURA,
    DIR_PACIENTES,
    ErrorNutriOS,
    Opcion,
    ajustes_clinicos,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_ficha,
    cargar_protocolo,
    coincide_alimento,
    coincide_rechazo,
    comidas_activas,
    comprobar_rango_edad,
    huella_plan,
    normalizar,
    resolver_regla_acoplada,
)


class Reporte:
    def __init__(self) -> None:
        self.errores: list[str] = []
        self.avisos: list[str] = []
        # Lo que Paty tiene que leer ANTES que ninguna otra cosa. Va aparte
        # porque el problema del primer caso real no fue que el aviso faltara:
        # fue que estaba en la línea 40 de una lista de 60, entre notas sobre
        # claves de protocolo no implementadas.
        self.destacados: list[str] = []

    def error(self, msg: str) -> None:
        self.errores.append(msg)

    def aviso(self, msg: str) -> None:
        self.avisos.append(msg)

    def destacado(self, msg: str) -> None:
        self.destacados.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errores


def _items(plan: dict, con_huecos: bool = False):
    """Recorre todos los ítems del plan: (semana, dia, comida, item).

    Los huecos declarados quedan fuera salvo que se pidan. No son alimentos: son
    ausencias que ya vienen con su motivo y su receta faltante escritos. Contar
    un hueco como si fuera un ítem hacía dos cosas malas a la vez — daba la
    ranura por cubierta en el recuento de frecuencias, y producía media docena
    de errores sobre un plato que no existe.
    """
    for s in plan["semanas"]:
        for dia, comidas in s["dias"].items():
            for cid, comida in comidas.items():
                for item in comida["items"]:
                    if item.get("hueco") and not con_huecos:
                        continue
                    yield s["semana"], dia, cid, item


def validar(nombre_carpeta: str, ruta_alterna: str = "") -> tuple[Reporte, dict]:
    """Comprueba el plan de ese paciente contra el protocolo y la ficha.

    `ruta_alterna` permite pasar por el validador un plan que no es el vigente
    —el de un control anterior, o uno guardado antes de un cambio de reglas—.
    Sirve para lo que suena: comprobar si las reglas nuevas habrían cazado lo que
    salió impreso la vez pasada. Un validador que no muerde sobre el plan que
    produjo los errores no sirve de nada, y esta es la forma de comprobarlo.
    """
    carpeta = DIR_PACIENTES / nombre_carpeta
    ruta_plan = Path(ruta_alterna) if ruta_alterna else carpeta / "plan.json"
    if not ruta_plan.exists():
        raise ErrorNutriOS(f"No existe {ruta_plan}. Ejecuta antes motor/ensamblar.py")

    plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
    ficha = cargar_ficha(carpeta)
    protocolo = cargar_protocolo(ficha["protocolo_sugerido"])
    recetas, avisos_bib = cargar_biblioteca()
    opciones = recetas + cargar_alimentos_base()
    # El ancla se concede igual que en el ensamblador, y por su cuenta: si el
    # validador no supiera cuál es el alimento seguro, contaría sus catorce
    # apariciones como una receta repetida y bloquearía el plan por cumplir
    # T-10.
    huerfanas_ancla = conceder_ancla(opciones, ficha)
    catalogo = {o.id: o for o in opciones}

    r = Reporte()
    for a in avisos_bib:
        r.aviso(f"Biblioteca: {a}")
    if huerfanas_ancla:
        r.error(
            "La ficha declara como alimento ancla algo que el sistema no conoce: "
            + ", ".join(huerfanas_ancla)
            + ".\n    El slot ANCLA se quedaría vacío todos los días."
        )

    # --- 0. ¿Debe este caso tener un plan? ----------------------------------
    # Va primero porque es la pregunta previa a todas las demás. El validador
    # comprueba que el plan cumple el protocolo; esto comprueba que el caso no
    # necesite otra cosa antes que un plan.
    for h in parada_clinica.revisar(ficha, protocolo):
        (r.error if h.bloquea else r.destacado)(h.mensaje)

    # --- 0b. Procedencia de los datos clínicos ------------------------------
    # Ningún dato clínico se imprime sin decir de qué documento y de qué página
    # salió. No es burocracia: en el primer caso real nadie sabía si el valor de
    # hemoglobina que se buscaba estaba en un documento que se perdió, en uno
    # que se duplicó, o en el recuerdo de la consulta.
    procedencia = ficha.get("procedencia") or {}
    sin_procedencia = [
        campo
        for campo in CAMPOS_CLINICOS_CON_PROCEDENCIA
        if ficha.get(campo) not in (None, "", [], {})
        and not str(procedencia.get(campo) or "").strip()
    ]
    if sin_procedencia:
        r.error(
            "Estos datos clínicos aparecen en la ficha sin decir de dónde salieron: "
            + ", ".join(sin_procedencia)
            + ".\n"
            "    Un dato sin procedencia no se imprime. O se le pone el documento y la "
            "página de los que sale, o se retira de la ficha y se lista como dato "
            "faltante — que es información útil, no un hueco.\n"
            "    Solución: en el front-matter de ficha.md, «procedencia: {peso_kg: "
            "\"documento.pdf · p. 5\", ...}». Los calculados se marcan como tales: "
            "«edad_meses: \"derivado: f. nac. 2021-02-14\"»."
        )

    faltantes = [str(d) for d in (ficha.get("datos_sin_fuente") or []) if str(d).strip()]
    if faltantes:
        r.destacado(
            "DATOS CLÍNICOS QUE NO ESTÁN EN NINGUNA FUENTE: "
            + ", ".join(faltantes)
            + ".\n"
            "    El plan se construyó sin ellos. Lo que haga por esos frentes es "
            "preventivo, no correctivo, y esto no puede quedarse en una frase enterrada "
            "en la portada.\n"
            "    Si alguno lo tienes en otro documento, pásalo y se rehace la ficha; si "
            "está pedido y pendiente, esto es el recordatorio de que el plan se revisa "
            "cuando llegue."
        )

    estado_rango, mensaje_rango = comprobar_rango_edad(protocolo, ficha)
    if estado_rango == "fuera_sin_justificar":
        r.error(mensaje_rango)
    elif estado_rango == "fuera_justificado":
        r.aviso(mensaje_rango)

    # Los ajustes por diagnóstico se resuelven aquí de nuevo, desde el protocolo y
    # la ficha, sin mirar el plan: el validador tiene que llegar a la misma
    # frecuencia efectiva que el ensamblador por su cuenta, o no está validando
    # nada.
    frecuencias, exclusiones_dx, problemas_ajustes = ajustes_clinicos(protocolo, ficha)
    for p in problemas_ajustes:
        r.error(p)

    # --- 1. Coherencia paciente / plan -------------------------------------
    if plan.get("paciente") != ficha["paciente"]:
        r.error("El plan no corresponde a la ficha: los nombres de paciente no coinciden.")
    if plan.get("edad_meses") != ficha["edad_meses"]:
        r.error("La edad del plan no coincide con la de la ficha.")
    if len(plan["semanas"]) != int(ficha["semanas_plan"]):
        r.error(
            f"La ficha pide {ficha['semanas_plan']} semana(s) y el plan trae "
            f"{len(plan['semanas'])}."
        )

    # --- 2. Riesgo vital: alergias, rechazos y edad ------------------------
    alergias = {normalizar(a) for a in ficha.get("alergias") or []}
    rechazos = {normalizar(x) for x in ficha.get("rechazos") or []}

    # Una alergia que no coincide con ninguna etiqueta del catálogo no está
    # filtrando nada: el plan parece seguro y no lo es. Es el fallo más
    # peligroso posible del sistema, así que se detecta explícitamente.
    etiquetas_catalogo = {normalizar(a) for o in catalogo.values() for a in o.alergenos}
    for a in sorted(alergias):
        if a not in etiquetas_catalogo:
            r.error(
                f"La alergia «{a}» no corresponde a ninguna etiqueta de alérgeno del "
                f"catálogo, así que NO está excluyendo nada.\n"
                f"    Etiquetas reconocidas: {', '.join(sorted(etiquetas_catalogo)) or '(ninguna)'}.\n"
                f"    Añade esa etiqueta a los alimentos que la contengan en "
                f"datos/alimentos_base.yaml y al front-matter de las recetas afectadas, "
                f"o corrige el nombre en la ficha."
            )

    # Misma comprobación para lo que excluye el protocolo por diagnóstico, y por
    # la misma razón: una `exclusiones_extra` con una etiqueta que el catálogo no
    # conoce no excluye nada, y el caso concreto —APLV— termina con el niño
    # comiendo lácteos sin que nadie se entere.
    for e in sorted(exclusiones_dx - alergias):
        if e not in etiquetas_catalogo:
            r.error(
                f"El protocolo «{protocolo.get('id')}» excluye «{e}» por el diagnóstico del "
                f"paciente, pero esa etiqueta no existe en el catálogo: NO está excluyendo "
                f"nada.\n"
                f"    Etiquetas reconocidas: {', '.join(sorted(etiquetas_catalogo)) or '(ninguna)'}.\n"
                f"    Corrige «exclusiones_extra» en preferencias_clinicas del protocolo, o "
                f"etiqueta con «{e}» los alimentos que la lleven en datos/alimentos_base.yaml "
                f"y en el front-matter de las recetas afectadas."
            )

    # Igual para los rechazos, pero como aviso: un rechazo mal escrito molesta,
    # no hace daño.
    for x in sorted(rechazos):
        if x and not any(coincide_rechazo(x, o) for o in catalogo.values()):
            r.aviso(
                f"El rechazo «{x}» no coincide con ningún alimento del catálogo: "
                f"no está excluyendo nada. Revisa cómo se escribe."
            )

    for sem, dia, cid, item in _items(plan):
        # Un hueco declarado no es un alimento: es una ausencia ya explicada.
        # Tratarlo como ítem produce media docena de errores absurdos sobre él
        # y tapa el hueco de verdad, que es lo único que hay que leer ahí.
        if item.get("hueco"):
            continue
        ident = item.get("receta_id") or normalizar(item["nombre"])
        opcion = catalogo.get(ident) or next(
            (o for o in catalogo.values() if o.nombre == item["nombre"]), None
        )
        donde = f"S{sem} · {dia} · {cid}"

        # El suplemento lo inyecta la ficha con su dosis y su hora: no sale del
        # catálogo y no tiene por qué estar ahí.
        if item.get("componente") == "suplemento":
            if not str(item.get("cantidad") or "").strip():
                r.error(f"{donde}: el suplemento «{item['nombre']}» va sin dosis ni hora.")
            continue

        if opcion is None:
            r.error(f"{donde}: «{item['nombre']}» no existe en la biblioteca ni en alimentos base.")
            continue

        if opcion.nunca_recomendar:
            r.error(
                f"{donde}: «{item['nombre']}» está marcado 'nunca_recomendar' en el "
                f"catálogo y no puede aparecer en ningún plan.\n"
                f"    Es una decisión clínica de Paty, no un filtro por paciente: "
                f"si está aquí, el motor tiene un fallo."
            )

        etiquetas_opcion = {normalizar(a) for a in opcion.alergenos}
        choque = alergias & etiquetas_opcion
        if choque:
            r.error(f"{donde}: «{item['nombre']}» contiene {', '.join(sorted(choque))} — ALERGIA declarada.")
        choque_dx = (exclusiones_dx - alergias) & etiquetas_opcion
        if choque_dx:
            r.error(
                f"{donde}: «{item['nombre']}» contiene {', '.join(sorted(choque_dx))}, que el "
                f"protocolo excluye por el diagnóstico de este paciente."
            )

        if any(coincide_rechazo(x, opcion) for x in rechazos):
            r.error(f"{donde}: «{item['nombre']}» está en la lista de rechazos.")

        if opcion.edad_min_meses > ficha["edad_meses"]:
            r.error(
                f"{donde}: «{item['nombre']}» exige {opcion.edad_min_meses} meses y "
                f"el paciente tiene {ficha['edad_meses']}."
            )

        if not item.get("cantidad"):
            r.error(f"{donde}: «{item['nombre']}» va sin cantidad (regla de cero orfandad).")
        elif "[" in str(item["cantidad"]) or "]" in str(item["cantidad"]):
            r.error(f"{donde}: la cantidad de «{item['nombre']}» conserva corchetes.")

    # --- 2b. Texturas -------------------------------------------------------
    # Una textura excluida en la ficha solo filtra a los alimentos que la
    # declaran. Los que no la declaran pasan sin que nadie los mire, y el plan
    # sale con sello de válido sin que la restricción se haya comprobado nunca.
    # Eso es un ERROR y detiene el pipeline, con el mismo criterio que una
    # alergia sin etiqueta en el catálogo: cuando el sistema no puede verificar
    # una restricción de seguridad, se para en vez de firmar.
    excluidas = {normalizar(t) for t in ficha.get("texturas_excluidas") or []}
    if excluidas:
        sin_declarar: set[str] = set()
        for sem, dia, cid, item in _items(plan):
            op = catalogo.get(item.get("receta_id") or "") or next(
                (o for o in catalogo.values() if o.nombre == item["nombre"]), None
            )
            if op is None:
                continue
            # Misma lista de exentos que usa el ensamblador. Si el validador no
            # la respetara, marcaría como error el agua y el aceite que el motor
            # acaba de poner a propósito, y los dos no pueden contradecirse.
            if op.componente in COMPONENTES_SIN_FILTRO_TEXTURA:
                continue
            if normalizar(op.textura) in excluidas:
                r.error(
                    f"S{sem} · {dia} · {cid}: «{item['nombre']}» es de textura "
                    f"{op.textura}, excluida para este paciente."
                )
            elif not op.textura:
                sin_declarar.add(item["nombre"])
        if sin_declarar:
            r.error(
                "La ficha excluye texturas ("
                + ", ".join(sorted(excluidas))
                + ") y estos alimentos del plan no declaran la suya, así que el "
                "filtro no los ha mirado y la restricción NO está comprobada: "
                + ", ".join(sorted(sin_declarar))
                + ".\n    Declara `textura` en el front-matter de esas recetas "
                "—python motor/migrar_textura.py— o en datos/alimentos_base.yaml. "
                "No se firma un plan cuya restricción de textura nadie ha podido "
                "verificar."
            )

    # --- 2c. Carga de seco en un paciente con riesgo de disfagia -----------
    # `texturas_excluidas` dice lo que el niño no se come; `riesgo_disfagia`
    # dice lo que le puede hacer daño al tragar. En aversión textural los dos
    # apuntan en direcciones opuestas: lo seco y lo crujiente es a la vez lo
    # único que acepta y el perfil de bolo que se impacta en un esófago
    # inflamado o estrecho.
    #
    # Esa tensión no la resuelve el motor, porque es criterio clínico. Pero sí
    # puede medirla y ponerla delante de Paty, en vez de dejarla enterrada en la
    # nota de una receta que quizá nadie abra. Por eso es AVISO y no ERROR: aquí
    # no hay una regla que se viole, hay una decisión que alguien tiene que
    # tomar mirando al paciente.
    if ficha.get("riesgo_disfagia"):
        SECAS = {"seca", "crujiente"}
        total = secas = 0
        solo_seco: list[str] = []
        for s in plan["semanas"]:
            for dia, comidas in s["dias"].items():
                for cid, comida in comidas.items():
                    txt = []
                    for item in comida["items"]:
                        op = catalogo.get(item.get("receta_id") or "") or next(
                            (o for o in catalogo.values() if o.nombre == item["nombre"]),
                            None,
                        )
                        # Las bebidas y los vehículos de grasa no forman bolo:
                        # se excluyen del recuento igual que del filtro.
                        if op is None or op.componente in COMPONENTES_SIN_FILTRO_TEXTURA:
                            continue
                        txt.append(normalizar(op.textura))
                    if not txt:
                        continue
                    total += len(txt)
                    secas += sum(1 for x in txt if x in SECAS)
                    if all(x in SECAS for x in txt):
                        solo_seco.append(f"S{s['semana']} · {dia} · {cid}")

        if solo_seco:
            extra = f" y {len(solo_seco) - 5} más" if len(solo_seco) > 5 else ""
            r.aviso(
                f"Riesgo de disfagia: {len(solo_seco)} comida(s) del plan no llevan "
                f"ningún elemento blando que ayude a bajar el bolo — "
                + "; ".join(solo_seco[:5])
                + extra
                + ". Conviene comprobar que cada una salga con bebida al lado y "
                "bocados pequeños."
            )
        if total and secas * 2 > total:
            r.aviso(
                f"Riesgo de disfagia: {secas} de {total} raciones del plan "
                f"({secas * 100 // total} %) son de textura seca o crujiente, que es "
                f"el perfil de bolo que se impacta. Si la ficha además excluye las "
                f"texturas húmedas, esta contradicción es clínica y no la resuelve "
                f"el motor: decide Paty, y a veces la respuesta es derivar."
            )

    # --- 2d. Comidas que todavía no deberían existir ------------------------
    # `activo_desde_semana` es la única forma que tiene un protocolo de decir
    # "esta comida entra más tarde". Si el plan la trae antes, el niño está
    # recibiendo un tiempo de comida que el protocolo no ha abierto todavía.
    for s in plan["semanas"]:
        activas = {c["id"] for c in comidas_activas(protocolo, s["semana"])}
        desde = {
            c["id"]: c.get("activo_desde_semana")
            for c in protocolo.get("comidas") or []
        }
        for dia, comidas in s["dias"].items():
            for cid in comidas:
                if cid in activas:
                    continue
                r.error(
                    f"S{s['semana']} · {dia}: la comida «{cid}» aparece en la semana "
                    f"{s['semana']}, y el protocolo la activa desde la semana "
                    f"{desde.get(cid, '?')}."
                )

    # --- 3. Frecuencias del protocolo, recontadas ---------------------------
    for s in plan["semanas"]:
        n = s["semana"]
        conteo_comp: Counter = Counter()
        opciones_en: dict[tuple[str, str], list] = {}
        for dia, comidas in s["dias"].items():
            for cid, comida in comidas.items():
                for item in comida["items"]:
                    # Un hueco declarado no cubre la ranura: si contara, un plan
                    # con siete huecos de proteína cumpliría «proteína 7 veces».
                    if item.get("hueco"):
                        continue
                    conteo_comp[(item["componente"], cid)] += 1
                    op = catalogo.get(item.get("receta_id") or "") or next(
                        (o for o in catalogo.values() if o.nombre == item["nombre"]), None
                    )
                    if op:
                        opciones_en.setdefault((item["componente"], cid), []).append(op)

        for regla in frecuencias:
            if regla.get("cada_dias") or regla.get("modo") == "relleno":
                continue
            comp = regla["componente"]
            ambito = regla.get("en") or [c["id"] for c in comidas_activas(protocolo, n)]
            fam = regla.get("familia")
            veces = regla.get("veces")
            if veces is None:
                continue

            if fam:
                # Se cuenta con el mismo criterio de dos niveles que usa el
                # ensamblador (familia o id). Si aquí se contara solo por
                # familia, una regla escrita con un alimento concreto —
                # 'proteina/pavita'— daría siempre cero y bloquearía un plan
                # que en realidad la cumple.
                real = sum(
                    1
                    for c in ambito
                    for op in opciones_en.get((comp, c), [])
                    if op.responde_a(fam)
                )
                etiqueta = f"{comp}/{fam}"
            else:
                real = sum(conteo_comp[(comp, c)] for c in ambito)
                etiqueta = comp

            modo = regla.get("modo", "exacto")
            minimo = regla.get("minimo")
            # Comparación exacta contra la etiqueta que escribe el ensamblador
            # ("proteina/pescado: sin opciones para este paciente; ..."), no por
            # subcadena: con `in`, una degradación de «proteina/pescado» rebajaba
            # a aviso el error de cualquier regla llamada «proteina» a secas, que
            # es justo el error que no se puede perdonar.
            degradada = any(
                d.split(":", 1)[0].strip() == etiqueta for d in plan.get("degradaciones", [])
            )

            if modo == "exacto" and real != int(veces):
                (r.aviso if degradada else r.error)(
                    f"Semana {n}: {etiqueta} aparece {real} vez/veces; el protocolo exige "
                    f"exactamente {veces}." + (" (degradado por restricción del paciente)" if degradada else "")
                )
            elif modo == "maximo" and real > int(veces):
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el máximo es {veces}.")
            elif modo == "minimo" and real < int(veces):
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el mínimo es {veces}.")
            if minimo is not None and real < int(minimo) and not degradada:
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el mínimo es {minimo}.")

    # --- 4. Reglas acopladas ------------------------------------------------
    for regla in protocolo.get("reglas_acopladas") or []:
        resuelta, problema = resolver_regla_acoplada(regla, protocolo)
        if not resuelta:
            r.error(
                f"Regla acoplada «{regla.get('si', '?')} -> "
                f"{regla.get('entonces', '?')}» no resoluble: {problema}."
            )
            continue
        disp = resuelta["disparador_componente"]
        familia_disp = resuelta["disparador_familia"]
        obj = resuelta["objetivo_componente"]
        ambito = resuelta["ambito"]

        def dispara(comida_id: str, comida: dict) -> bool:
            if comida_id not in resuelta["comidas_disparador"]:
                return False
            for item in comida["items"]:
                if item["componente"] != disp:
                    continue
                if not familia_disp:
                    return True
                ident = item.get("receta_id") or normalizar(item["nombre"])
                opcion = catalogo.get(ident) or next(
                    (o for o in catalogo.values() if o.nombre == item["nombre"]), None
                )
                if opcion and opcion.responde_a(familia_disp):
                    return True
            return False

        def tiene_objetivo(comida_id: str, comida: dict) -> bool:
            return comida_id in resuelta["comidas_objetivo"] and any(
                item["componente"] == obj for item in comida["items"]
            )

        for s in plan["semanas"]:
            for dia, comidas in s["dias"].items():
                if ambito == "misma_comida":
                    for cid, comida in comidas.items():
                        if dispara(cid, comida) and not tiene_objetivo(cid, comida):
                            r.error(
                                f"S{s['semana']} · {dia} · {cid}: hay {regla['si']} "
                                f"sin {regla['entonces']} "
                                f"({regla.get('razon', 'regla acoplada')})."
                            )
                else:
                    hay_disparador = any(dispara(cid, comida) for cid, comida in comidas.items())
                    hay_objetivo = any(
                        tiene_objetivo(cid, comida) for cid, comida in comidas.items()
                    )
                    if hay_disparador and not hay_objetivo:
                        r.error(
                            f"S{s['semana']} · {dia}: hay {regla['si']} sin "
                            f"{regla['entonces']} en todo el día "
                            f"({regla.get('razon', 'regla acoplada')})."
                        )

    # --- 5. Variedad --------------------------------------------------------
    var = protocolo.get("variedad") or {}
    firmas: dict[str, str] = {}
    for s in plan["semanas"]:
        usos = Counter()
        for dia, comidas in s["dias"].items():
            firma = "|".join(
                f"{c}:" + ",".join(i["nombre"] for i in v["items"]) for c, v in sorted(comidas.items())
            )
            if var.get("no_repetir_dia_completo") and firma in firmas:
                r.error(
                    f"S{s['semana']} · {dia} repite exactamente el día {firmas[firma]}."
                )
            firmas[firma] = f"S{s['semana']} {dia}"
            for c in comidas.values():
                for i in c["items"]:
                    # V-5. El ancla está exenta de toda regla de variedad: se
                    # sirve TODOS los días y ocupa su propio slot. Sin esta
                    # exención, cumplir T-10 rompía V-1 y el plan correcto salía
                    # bloqueado por hacer lo que se le pedía.
                    rid = i.get("receta_id")
                    if rid and not (rid in catalogo and catalogo[rid].es_ancla):
                        usos[rid] += 1

        tope = var.get("max_veces_misma_receta_semana")
        if tope:
            for rid, n_usos in usos.items():
                if n_usos > int(tope):
                    r.error(f"Semana {s['semana']}: la receta «{rid}» aparece {n_usos} veces (tope {tope}).")

        minimo = var.get("min_recetas_distintas_semana")
        if minimo and len(usos) < int(minimo):
            r.aviso(
                f"Semana {s['semana']}: solo {len(usos)} recetas distintas del recetario "
                f"(el protocolo sugiere {minimo}). La biblioteca necesita crecer."
            )

    # --- 5b. Un plan sin recetario ------------------------------------------
    # Cuando `recetas_usadas` sale vacío no hay Recetario_[Paciente].pdf, y hasta
    # ahora eso ocurría sin que nada lo explicara: Paty recibía un PDF donde
    # esperaba dos. No es un error —el plan es correcto—, pero tiene que decirse
    # y tiene que decirse por qué.
    if not plan.get("recetas_usadas"):
        componentes_protocolo = {
            c for m in protocolo.get("comidas") or [] for c in m["componentes"]
        }
        con_receta = {op.componente for op in recetas}
        sin_receta = sorted(componentes_protocolo - con_receta)
        r.aviso(
            "Este plan no usa ninguna receta del recetario, así que solo se generará el "
            "PDF del plan y no habrá Recetario.\n"
            "    Motivo: de los componentes que pide el protocolo «"
            + str(protocolo.get("id"))
            + "», estos no tienen ninguna receta en biblioteca/: "
            + (", ".join(sin_receta) or "(ninguno; las hay, pero ninguna encaja con este paciente)")
            + ".\n    Se llenan con alimentos base, que se preparan sin instrucciones."
        )

    # --- 5c. Las recetas que se van a imprimir ------------------------------
    # La biblioteca guarda bases y una base no se imprime nunca. Lo que llega al
    # recetario son las recetas de pacientes/<paciente>/recetas/, ya resueltas
    # contra este niño. Aquí se comprueba que existan y que ninguna traiga lo
    # que no puede salir: un ingrediente rechazado, un alérgeno callado, un
    # ingrediente nuevo sin declarar, o una marca de plantilla sin resolver.
    errores_recetas, avisos_recetas = recetas_paciente.revisar(plan, ficha, carpeta)
    for e in errores_recetas:
        r.error(e)
    for a in avisos_recetas:
        # Las exposiciones planificadas suben a destacado: son introducciones
        # nuevas en el plato de un niño con selectividad, y Paty tiene que
        # aprobarlas una a una antes de que el plan salga por la puerta.
        (r.destacado if a.startswith("EXPOSICIÓN PLANIFICADA") else r.aviso)(a)

    # --- 5d. Alimentos base fuera del repertorio aceptado -------------------
    # La regla de los ingredientes vive en las recetas, y ahí es un error que
    # bloquea. Un alimento base es otra cosa: una pera servida como pera es una
    # exposición visible, que la madre ve venir y puede manejar, no algo colado
    # dentro de una preparación. Por eso avisa y no bloquea.
    #
    # Pero se dice. En un repertorio estrecho, saber cuántas cosas del plan son
    # nuevas es justo lo que decide si el plan es ambicioso o es papel mojado.
    repertorio = [str(x) for x in (ficha.get("repertorio_aceptado") or [])]
    if repertorio:
        despensa = cargar_despensa_basica()
        conocidos = repertorio + list(exposiciones_declaradas(ficha))
        nuevos: dict[str, None] = {}
        for _sem, _dia, _cid, item in _items(plan):
            # Ni la receta ni el suplemento: la primera declara sus propias
            # exposiciones ingrediente por ingrediente, y el segundo es una
            # indicación médica, no un alimento que el niño acepte o rechace.
            if item.get("receta_id") or item.get("componente") == "suplemento":
                continue
            nombre = str(item["nombre"])
            # El aceite y el agua no se «aceptan»: son despensa. Listarlos como
            # introducciones nuevas ahoga el aviso que sí protege al niño.
            if es_despensa(nombre, despensa):
                continue
            if not any(coincide_alimento(x, Opcion(id="", nombre=nombre, componente="",
                                                   edad_min_meses=0)) for x in conocidos):
                nuevos[nombre] = None
        if nuevos:
            r.aviso(
                f"{len(nuevos)} alimento(s) base del plan no están en el repertorio "
                f"aceptado de la ficha: " + ", ".join(sorted(nuevos)) + ".\n"
                "    No es un error —un alimento servido tal cual es una exposición "
                "visible, no algo colado dentro de una preparación— pero conviene "
                "saber cuántas cosas nuevas trae el plan antes de entregarlo."
            )

    # --- 6. Recetas sin validar en cocina -----------------------------------
    sin_probar = [
        rid for rid in plan.get("recetas_usadas", [])
        if rid in catalogo and catalogo[rid].es_receta and not catalogo[rid].validada_en_cocina
    ]
    if sin_probar:
        r.aviso(
            f"{len(sin_probar)} receta(s) del plan no están marcadas como probadas en cocina: "
            + ", ".join(sin_probar)
        )

    # --- 6b. Reglas del protocolo que el motor todavía no aplica ------------
    # Mejor decirlo que dejar creer que se cumplieron.
    # Solo lo que ensamblar.py aplica de verdad: ampliar esta lista sin implementar
    # la funcionalidad apaga el aviso que protege la revisión clínica.
    IMPLEMENTADAS = {"priorizar_aporta", "subir_frecuencia", "exclusiones_extra"}
    for dx in ficha.get("diagnosticos") or []:
        ajuste = (protocolo.get("preferencias_clinicas") or {}).get(dx) or {}
        for clave in ajuste:
            if clave not in IMPLEMENTADAS and clave != "nota_qa":
                r.aviso(
                    f"El protocolo declara «{clave}» para {dx}, pero el motor todavía "
                    f"no lo aplica: queda a criterio de Paty."
                )
        if ajuste.get("nota_qa"):
            r.aviso(f"Nota del protocolo ({dx}): {ajuste['nota_qa']}")

    if exclusiones_dx:
        r.aviso(
            "Exclusiones aplicadas por el diagnóstico, además de las alergias de la "
            "ficha: " + ", ".join(sorted(exclusiones_dx)) + "."
        )

    for clave in sorted(CLAVES_PROTOCOLO_SOLO_AVISO):
        if protocolo.get(clave):
            r.aviso(
                f"El protocolo declara «{clave}», que el motor aún no hace cumplir. "
                f"Revísalo a mano."
            )

    # --- 6c. Decisiones que el protocolo deja abiertas ----------------------
    # Los números sin respaldo público no se adivinan: se dejan como están y se
    # repiten aquí, en un solo sitio, hasta que Paty los cierre.
    for pendiente in protocolo.get("decisiones_pendientes") or []:
        r.aviso(f"Decisión pendiente del protocolo: {' '.join(str(pendiente).split())}")

    # --- 7. Degradaciones del ensamblador -----------------------------------
    for d in plan.get("degradaciones", []):
        r.aviso(f"Sustitución forzada: {d}")

    # --- 8. Capa 7 · el catálogo de reglas, por ID --------------------------
    # Aquí es donde el plan se rechaza por R-2, T-6, V-1 u O-3, y no por una
    # frase que haya que interpretar. El ID es lo que permite decir «tumba la
    # T-4 de este niño» sin describir el párrafo entero, y lo que hace que un
    # reporte se pueda comparar con el de la semana pasada.
    rasgos_excluidos, problemas_rasgos = rasgos_aversivos(ficha)
    for p in problemas_rasgos:
        r.error(p)

    instanciadas, _ = cargar_recetas_instanciadas(carpeta)
    for infra in reglas.evaluar(
        plan, ficha, protocolo, catalogo, instanciadas, rasgos_excluidos
    ):
        (r.error if infra.bloquea else r.aviso)(infra.texto())

    # --- 9. Huecos declarados -----------------------------------------------
    # No son errores: son el resultado profesional de un slot que se quedó sin
    # candidatos válidos. Van arriba, con las exposiciones, porque cada uno es
    # una receta que hay que encargar antes del próximo control.
    for h in plan.get("huecos") or []:
        r.destacado(
            f"{HUECO} · S{h.get('semana')} · {h.get('dia')} · {h.get('comida')} · "
            f"{h.get('componente')}: {h.get('motivo')}\n"
            f"    Reglas que vaciaron el conjunto: {h.get('reglas')}\n"
            f"    Qué falta: {h.get('receta_que_falta')}"
        )

    # --- 10. Exposiciones declaradas en la ficha ----------------------------
    # Las de las recetas ya suben a destacado desde recetas_paciente. Estas son
    # las del plan: alimentos servidos tal cual que el niño no tiene en su
    # repertorio y que se introducen a propósito. Se aprueban una a una.
    servidos = {
        str(i["nombre"]) for _s, _d, _c, i in _items(plan) if i.get("exposicion")
    }
    for clave, datos in sorted(exposiciones_declaradas(ficha).items()):
        r.destacado(
            f"EXPOSICIÓN PLANIFICADA · «{clave}» desde la semana "
            f"{datos['desde_semana']}"
            + (f" — aparece como {', '.join(sorted(servidos))}" if servidos else "")
            + f". {datos['porque']} · PENDIENTE DEL VISTO BUENO DE PATY."
        )

    return r, plan


def escribir_reporte(carpeta: Path, r: Reporte, plan: dict) -> Path:
    lineas = [
        f"# Reporte de validación — {plan.get('paciente','?')}",
        "",
        f"Protocolo: {plan.get('protocolo_nombre','?')}  ·  "
        f"{len(plan['semanas'])} semana(s)  ·  fecha {plan.get('fecha','')}",
        "",
        "## Resultado",
        "",
        "**APTO PARA REVISIÓN** — sin errores bloqueantes."
        if r.ok
        else f"**BLOQUEADO** — {len(r.errores)} error(es). El plan no debe renderizarse.",
        "",
    ]
    if r.destacados:
        lineas += [
            "## ⚠ Léelo antes que nada",
            "",
            "Lo de esta sección no bloquea el plan, y por eso mismo es lo que más fácil "
            "se pasa por alto. Va arriba a propósito.",
            "",
        ]
        lineas += [f"- {d}" for d in r.destacados] + [""]
    if r.errores:
        lineas += ["## Errores", ""] + [f"- {e}" for e in r.errores] + [""]
    if r.avisos:
        lineas += ["## Avisos", ""] + [f"- {a}" for a in r.avisos] + [""]
    if not r.errores and not r.avisos:
        lineas += ["Sin avisos.", ""]
    lineas += [
        "---",
        "",
        "Este reporte lo genera código, no un modelo de lenguaje: los conteos son "
        "aritmética sobre el plan ya construido. Un error aquí siempre es real.",
        "",
        # La huella ata este reporte AL plan que se validó. El renderizador la
        # comprueba y se niega a maquetar si no coincide: un reporte que dice
        # APTO sobre un plan que ya no existe no es una puerta, es un adorno.
        f"Huella del plan validado: `sha256:{huella_plan(carpeta / 'plan.json')}`",
        "",
        "Revisión final y firma clínica: Nut. Patricia López.",
    ]
    destino = carpeta / "reporte_qa.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida el plan ensamblado de un paciente.")
    ap.add_argument("paciente")
    ap.add_argument(
        "--plan",
        default="",
        help="ruta a otro plan.json del mismo paciente; útil para pasar por las "
             "reglas de hoy un plan de un control anterior. No escribe reporte.",
    )
    args = ap.parse_args()

    try:
        r, plan = validar(args.paciente, args.plan)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 2

    # Un plan alterno no sobrescribe el reporte del vigente: se está auditando
    # otra cosa, y dejar su veredicto en reporte_qa.md haría que el renderizador
    # maquetara un plan con el visto bueno de otro.
    destino = (
        None if args.plan else escribir_reporte(DIR_PACIENTES / args.paciente, r, plan)
    )

    for d in r.destacados:
        print(f"  ‼ {d}")
    for e in r.errores:
        print(f"  ✗ {e}")
    for a in r.avisos:
        print(f"  ⚠ {a}")
    print()
    if r.ok:
        print(f"✓ Plan válido. {len(r.avisos)} aviso(s) para revisar.")
    else:
        print(f"✗ Plan BLOQUEADO: {len(r.errores)} error(es).")
    if destino:
        print(f"  → {destino}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
