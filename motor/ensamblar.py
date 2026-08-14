"""
Ensamblador de planes — Nutri-OS · Fase 4

Convierte (protocolo + ficha del paciente + biblioteca) en un plan completo.

Principio: las frecuencias del protocolo se garantizan POR CONSTRUCCIÓN.
No se generan menús para después revisarlos: se reservan primero las ranuras
que las reglas exigen y solo después se rellena el resto. Un plan que viole
una frecuencia es un fallo del motor, no un descuido — y el validador lo para.

Uso:
    python motor/ensamblar.py <nombre_carpeta_paciente> [--semilla N]
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import parada_clinica
from comun import (
    COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD,
    DIAS,
    DIR_PACIENTES,
    ErrorNutriOS,
    Opcion,
    ajustes_clinicos,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_ficha,
    cargar_protocolo,
    comidas_activas,
    comprobar_rango_edad,
    guardar_json,
    normalizar,
    resolver_regla_acoplada,
)

MAX_INTENTOS = 60


# ---------------------------------------------------------------------------
# Selección de opciones
# ---------------------------------------------------------------------------


class Repertorio:
    """Todas las opciones disponibles, ya filtradas para este paciente."""

    def __init__(
        self,
        opciones: list[Opcion],
        ficha: dict,
        protocolo: dict,
        frecuencias: list[dict],
        exclusiones_extra: set[str] | None = None,
    ):
        self.ficha = ficha
        self.descartes: list[tuple[str, str]] = []
        self.por_componente: dict[str, list[Opcion]] = defaultdict(list)

        for o in opciones:
            apta, motivo = o.apta_para(ficha, exclusiones_extra)
            if apta:
                self.por_componente[o.componente].append(o)
            else:
                self.descartes.append((o.nombre, motivo))

        # Familias con cupo propio en el protocolo: no pueden usarse como
        # relleno improvisado, o se desbordaría su frecuencia.
        self.reguladas = {
            normalizar(r["familia"])
            for r in frecuencias
            if r.get("familia") and r.get("modo") != "relleno"
        }
        prefs = (protocolo.get("preferencias_clinicas") or {})
        self.priorizar: set[str] = set()
        for dx in ficha.get("diagnosticos") or []:
            self.priorizar |= set((prefs.get(dx) or {}).get("priorizar_aporta") or [])

        # `prioridades` del protocolo: el orden en que Paty prefiere los
        # alimentos de un componente. Desempata, no manda: la variedad va
        # primero, así que decide cuál de las frutas cítricas abre la semana y
        # cuál entra después, no cuáles aparecen.
        self.prioridades: dict[str, list[str]] = {
            comp: [str(x) for x in (lista or [])]
            for comp, lista in (protocolo.get("prioridades") or {}).items()
        }

    def candidatas(self, componente: str, comida: str, familia: str = "") -> list[Opcion]:
        salida = []
        for o in self.por_componente.get(componente, []):
            # Dos niveles: la clave del protocolo puede ser un cajón (familia)
            # o un alimento concreto (id). Ver Opcion.responde_a.
            if familia and not o.responde_a(familia):
                continue
            # Una receta solo entra en los momentos que declara.
            if o.es_receta and o.momento and comida not in o.momento:
                continue
            salida.append(o)
        return salida

    def elegir(
        self,
        componente: str,
        comida: str,
        familia: str,
        usos: dict[str, int],
        tope_semana: int,
        rng: random.Random,
        excluir_reguladas: bool = False,
    ) -> Opcion | None:
        pool = self.candidatas(componente, comida, familia)
        # Si la ranura no pide una familia concreta, no puede tomar prestada una
        # familia que tiene cupo propio en el protocolo: se desbordaría su
        # frecuencia (el hígado 1x/semana acabaría apareciendo cuatro veces).
        if not familia or excluir_reguladas:
            pool = [o for o in pool if normalizar(o.familia) not in self.reguladas] or pool
        if not pool:
            return None

        disponibles = [
            o for o in pool if (not o.es_receta) or usos[o.id] < tope_semana
        ]
        if not disponibles:
            return None

        orden = self.prioridades.get(componente) or []

        def preferencia(o: Opcion) -> int:
            for i, clave in enumerate(orden):
                if o.responde_a(clave):
                    return i
            return len(orden)   # lo que no está en la lista va al final

        def puntaje(o: Opcion) -> tuple:
            clinico = -len(self.priorizar & set(o.aporta))   # menor = mejor
            return (
                usos[o.id],
                clinico,
                preferencia(o),
                0 if o.validada_en_cocina else 1,
                rng.random(),
            )

        return min(disponibles, key=puntaje)


# ---------------------------------------------------------------------------
# Construcción de una semana
# ---------------------------------------------------------------------------


def _ranuras(
    protocolo: dict, componente: str, comidas_validas: list[str], n_semana: int
) -> list[tuple[int, str]]:
    """Todas las (dia, comida) donde este componente puede existir esta semana.

    `n_semana` no sobra: una comida con `activo_desde_semana` todavía no existe
    en las semanas anteriores, y contar sus ranuras como disponibles hacía que
    una frecuencia se repartiera sobre días que nunca se imprimen.
    """
    out = []
    for comida in comidas_activas(protocolo, n_semana):
        if comida["id"] not in comidas_validas:
            continue
        if componente not in comida["componentes"]:
            continue
        for d in range(7):
            out.append((d, comida["id"]))
    return out


def _reparto(reparto: dict, total: int) -> list[str]:
    """Convierte {avena:2, canihua:2, resto:...} en una lista de N familias."""
    fijas, resto_key = [], None
    for fam, n in reparto.items():
        if str(n).strip() == "resto":
            if resto_key:
                raise ErrorNutriOS("Una rotación no puede tener dos valores 'resto'.")
            resto_key = fam
        else:
            fijas += [fam] * int(n)
    if len(fijas) > total:
        raise ErrorNutriOS(
            f"Rotación imposible: pide {len(fijas)} apariciones para {total} ranuras."
        )
    faltan = total - len(fijas)
    if resto_key:
        fijas += [resto_key] * faltan
    elif faltan:
        fijas += [None] * faltan
    return fijas


def construir_semana(
    protocolo: dict,
    frecuencias: list[dict],
    ficha: dict,
    rep: Repertorio,
    rng: random.Random,
    n_semana: int,
) -> dict:
    porciones = ficha.get("porciones") or {}
    tope = int((protocolo.get("variedad") or {}).get("max_veces_misma_receta_semana", 99))
    usos: dict[str, int] = defaultdict(int)
    activas = comidas_activas(protocolo, n_semana)
    ids_activas = [c["id"] for c in activas]

    # semana[dia][comida][componente] = Opcion
    semana: dict = {d: {c["id"]: {} for c in activas} for d in range(7)}

    # --- componentes que NO se llenan siempre -------------------------------
    acopladas = protocolo.get("reglas_acopladas") or []
    acopladas_resueltas = []
    for regla in acopladas:
        resuelta, _ = resolver_regla_acoplada(regla, protocolo)
        if resuelta:
            acopladas_resueltas.append((regla, resuelta))
    dependientes = {
        resuelta["objetivo_componente"] for _, resuelta in acopladas_resueltas
    }

    # --- 1. Reglas de frecuencia con familia (proteína, huevo, yogurt...) ---
    familia_forzada: dict[tuple[int, str, str], str] = {}
    limitados: dict[str, int] = {}

    for regla in frecuencias:
        comp = regla["componente"]
        comidas_validas = regla.get("en") or ids_activas
        ranuras = _ranuras(protocolo, comp, comidas_validas, n_semana)
        modo = regla.get("modo", "exacto")

        if regla.get("familia"):
            if modo == "relleno" or regla.get("cada_dias"):
                continue  # se resuelven después
            n = int(regla.get("minimo") or regla.get("veces") or 0)
            libres = [r for r in ranuras if (r[0], r[1], comp) not in familia_forzada]
            if n > len(libres):
                raise ErrorNutriOS(
                    f"Protocolo imposible: {comp}/{regla['familia']} pide {n} "
                    f"apariciones y solo hay {len(libres)} ranuras libres."
                )
            for d, c in rng.sample(libres, n):
                familia_forzada[(d, c, comp)] = regla["familia"]
        else:
            veces = regla.get("veces")
            if veces is not None and int(veces) < len(ranuras):
                limitados[comp] = (int(veces), comidas_validas)

    # --- 2. Rotaciones ------------------------------------------------------
    for rot in protocolo.get("rotaciones") or []:
        comp = rot["componente"]
        comidas_validas = rot.get("en") or ids_activas
        ranuras = _ranuras(protocolo, comp, comidas_validas, n_semana)
        ranuras = [r for r in ranuras if (r[0], r[1], comp) not in familia_forzada]
        familias = _reparto(rot["reparto"], len(ranuras))
        rng.shuffle(familias)
        for (d, c), fam in zip(ranuras, familias):
            if fam:
                familia_forzada[(d, c, comp)] = fam

    # --- 3. Ranuras a llenar -----------------------------------------------
    # Las reglas con 'veces' se reparten sobre TODAS las comidas de su ámbito,
    # no una vez por comida: 'menestra 3 veces en [almuerzo, cena]' son 3 en
    # total sobre las 14 ranuras de la semana, no 3 en cada una.
    a_llenar: list[tuple[int, str, str]] = []
    cubiertos: set[tuple[str, str]] = set()

    for comp, (veces, comidas_validas) in limitados.items():
        ranuras = _ranuras(protocolo, comp, comidas_validas, n_semana)
        a_llenar += [(d, c, comp) for d, c in rng.sample(ranuras, veces)]
        cubiertos |= {(comp, c) for c in comidas_validas}

    for comida in activas:
        for comp in comida["componentes"]:
            if (comp, comida["id"]) in cubiertos or comp in dependientes:
                continue
            a_llenar += [(d, comida["id"], comp) for d in range(7)]

    # --- 4. Reglas acopladas ------------------------------------------------
    for regla, resuelta in acopladas_resueltas:
        disparador = resuelta["disparador_componente"]
        familia_disparador = resuelta["disparador_familia"]
        objetivo = resuelta["objetivo_componente"]
        ambito = resuelta["ambito"]
        nuevas = []
        for d, c, comp in a_llenar:
            if comp != disparador or c not in resuelta["comidas_disparador"]:
                continue
            if familia_disparador and not normalizar(
                familia_forzada.get((d, c, comp), "")
            ) == normalizar(familia_disparador):
                continue
            comida_obj = c if ambito == "misma_comida" else None
            candidatas_comida = (
                [comida_obj]
                if comida_obj
                else resuelta["comidas_objetivo"]
            )
            for cm in candidatas_comida:
                # Solo entre las comidas ACTIVAS esta semana: colocar el objetivo
                # en una comida que todavía no existe deja la regla sin cumplir y
                # el validador la marca sin que se entienda por qué.
                estructura = next((m for m in activas if m["id"] == cm), None)
                if estructura and objetivo in estructura["componentes"]:
                    if (d, cm, objetivo) not in a_llenar:
                        nuevas.append((d, cm, objetivo))
                    break
            else:
                raise ErrorNutriOS(
                    f"La regla acoplada «{regla.get('si')} -> {regla.get('entonces')}» del "
                    f"protocolo «{protocolo.get('id')}» se dispara en la semana {n_semana} "
                    f"({DIAS[d]} · {c}) y no tiene dónde colocar «{objetivo}»: ninguna de las "
                    f"comidas que lo declaran ({', '.join(resuelta['comidas_objetivo'])}) está "
                    f"activa todavía esa semana.\n"
                    f"    Solución: añade «{objetivo}» a los componentes de una comida activa "
                    f"desde la semana 1, o adelanta el «activo_desde_semana» de la comida "
                    f"objetivo en protocolos/{protocolo.get('id')}.yaml."
                )
        a_llenar += nuevas

    # --- 5. Relleno de familias sobrantes -----------------------------------
    for regla in frecuencias:
        if regla.get("modo") != "relleno" or not regla.get("familia"):
            continue
        comp = regla["componente"]
        comidas_validas = regla.get("en") or ids_activas
        for d, c in _ranuras(protocolo, comp, comidas_validas, n_semana):
            familia_forzada.setdefault((d, c, comp), regla["familia"])

    # --- 5b. Comprobación de viabilidad -------------------------------------
    # Antes de elegir nada: ¿alcanza la biblioteca para llenar estas ranuras
    # sin romper el tope de repetición? Si no alcanza, reintentar es inútil.
    demanda: dict[tuple[str, str], int] = defaultdict(int)
    for d, c, comp in set(a_llenar):
        demanda[(comp, c)] += 1
    for (comp, c), n in demanda.items():
        opciones = rep.candidatas(comp, c)
        # Antes se saltaba cualquier componente que tuviera un alimento base,
        # dándolo por resuelto. Eso hacía invisible el peor hueco posible: un
        # solo alimento base cubriendo 14 ranuras. Ahora la exención es por
        # componente y está escrita en comun.py, con el porqué.
        if comp in COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD:
            continue
        techo = len(opciones) * tope
        if opciones and n > techo:
            raise ErrorNutriOS(
                f"Biblioteca insuficiente para «{comp}» en «{c}»: hacen falta {n} "
                f"apariciones por semana y solo hay {len(opciones)} opción(es) "
                f"disponible(s) para este paciente, con un tope de {tope} usos "
                f"por semana (máximo alcanzable: {techo}).\n"
                f"    Solución: añade al menos "
                f"{math.ceil(n / tope) - len(opciones)} receta(s) más de "
                f"componente '{comp}' con momento '{c}', o sube "
                f"'max_veces_misma_receta_semana' en el protocolo."
            )

    # --- 5c. Suficiencia de RECETAS, que es distinto de suficiencia de ranuras
    # El chequeo de arriba pregunta "¿puedo llenar las ranuras?". Casi siempre la
    # respuesta es sí, porque hay un alimento base detrás de casi todo. La
    # pregunta que quedaba sin hacer es la otra: "¿puedo llenarlas con las N
    # recetas distintas que el protocolo pide?". Un plan lleno de arroz, papa y
    # pollo cumple todas las frecuencias y no lleva recetario, y eso se
    # despachaba con un aviso al final que no accionaba nada.
    #
    # Aquí sí acciona: es el mensaje que arranca el ciclo F2 → F3 y hace crecer
    # la biblioteca, que es el único mecanismo que tiene para crecer.
    minimo_recetas = int(
        (protocolo.get("variedad") or {}).get("min_recetas_distintas_semana") or 0
    )
    if minimo_recetas:
        recetas_posibles: set[str] = set()
        ranuras_con_receta = 0
        huecos: list[tuple[int, str]] = []
        for (comp, c), n in sorted(demanda.items()):
            if comp in COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD:
                continue
            disponibles = {o.id for o in rep.candidatas(comp, c) if o.es_receta}
            recetas_posibles |= disponibles
            ranuras_con_receta += n if disponibles else 0
            if len(disponibles) < n:
                huecos.append(
                    (n - len(disponibles), f"{comp} en {c}: {len(disponibles)} receta(s) "
                                           f"disponible(s) para {n} ranura(s)")
                )
        # Más recetas distintas que ranuras donde ponerlas no sirve de nada: el
        # techo real es el menor de los dos.
        techo_recetas = min(len(recetas_posibles), ranuras_con_receta)
        if techo_recetas < minimo_recetas:
            huecos.sort(key=lambda h: -h[0])
            listado = "\n      - ".join(h[1] for h in huecos[:8])
            raise ErrorNutriOS(
                f"Biblioteca insuficiente: el protocolo «{protocolo.get('id')}» pide al menos "
                f"{minimo_recetas} receta(s) distinta(s) del recetario por semana y, con los "
                f"filtros de este paciente, como mucho pueden entrar {techo_recetas}.\n"
                f"    Faltan {minimo_recetas - techo_recetas} receta(s).\n"
                f"    Dónde hacen falta:\n      - {listado}\n"
                f"    Solución: escribe esas recetas con prompts/P1_RECETAS.md (Fase 3), una "
                f"por conversación limpia, con el 'componente' y el 'momento' de la línea que "
                f"corresponda en su front-matter, y guárdalas en biblioteca/. Después vuelve "
                f"a ensamblar."
            )

    # --- 6. Elección concreta ----------------------------------------------
    sin_opcion: list[str] = []
    degradaciones: set[str] = set()
    orden = sorted(set(a_llenar), key=lambda t: (t[0], t[1], t[2]))
    for d, c, comp in orden:
        fam = familia_forzada.get((d, c, comp), "")
        elegida = rep.elegir(comp, c, fam, usos, tope, rng)
        if elegida is None and fam:
            # La familia que pedía el protocolo no tiene ninguna opción viable
            # para este paciente (alergia, rechazo o edad). Se degrada a otra,
            # pero NUNCA en silencio: queda registrado para el reporte de QA.
            degradaciones.add(
                f"{comp}/{fam}: sin opciones para este paciente; se sustituyó por otra familia"
            )
            elegida = rep.elegir(comp, c, "", usos, tope, rng, excluir_reguladas=True)
        if elegida is None:
            sin_opcion.append(f"{DIAS[d]} · {c} · {comp}" + (f" ({fam})" if fam else ""))
            continue
        usos[elegida.id] += 1
        semana[d][c][comp] = elegida

    if sin_opcion:
        raise ErrorNutriOS(
            "No hay opciones disponibles para estas ranuras (biblioteca insuficiente "
            "o filtros del paciente demasiado restrictivos):\n  - "
            + "\n  - ".join(sin_opcion[:12])
            + (f"\n  ... y {len(sin_opcion) - 12} más" if len(sin_opcion) > 12 else "")
        )

    # --- 7. Serialización ---------------------------------------------------
    salida = {"semana": n_semana, "dias": {}, "degradaciones": sorted(degradaciones)}
    for d in range(7):
        dia = {}
        for comida in activas:
            items = []
            for comp in comida["componentes"]:
                o = semana[d][comida["id"]].get(comp)
                if not o:
                    continue
                items.append(
                    {
                        "componente": comp,
                        "nombre": o.nombre,
                        "cantidad": porciones.get(comp, ""),
                        "receta_id": o.id if o.es_receta else None,
                    }
                )
            if items:
                dia[comida["id"]] = {
                    "nombre": comida["nombre"],
                    "hora": comida.get("hora", ""),
                    "items": items,
                }
        salida["dias"][DIAS[d]] = dia
    return salida


# ---------------------------------------------------------------------------
# Plan completo
# ---------------------------------------------------------------------------


def firma_dia(dia: dict) -> str:
    return "|".join(
        f"{c}:" + ",".join(i["nombre"] for i in v["items"]) for c, v in sorted(dia.items())
    )


def _familias_protegidas(protocolo: dict, frecuencias: list[dict]) -> set[tuple[str, str]]:
    """Las (componente, clave) que otra regla ya reservó y nadie puede pisar.

    Una regla de frecuencia con familia y una rotación con cupo fijo no son
    sugerencias: son las ranuras que el ensamblador reservó primero para poder
    garantizar el protocolo por construcción. Quien venga después escribe en lo
    que quede libre, que es el relleno.
    """
    protegidas: set[tuple[str, str]] = set()
    for regla in frecuencias:
        if regla.get("cada_dias") or regla.get("modo") == "relleno":
            continue
        if regla.get("familia"):
            protegidas.add((regla["componente"], normalizar(regla["familia"])))
    for rot in protocolo.get("rotaciones") or []:
        for fam, cupo in (rot.get("reparto") or {}).items():
            if str(cupo).strip() != "resto":
                protegidas.add((rot["componente"], normalizar(fam)))
    return protegidas


def aplicar_reglas_periodicas(
    plan: dict,
    protocolo: dict,
    frecuencias: list[dict],
    rep: Repertorio,
    rng: random.Random,
):
    """Reglas del tipo '1 vez cada 15 días', que exceden la semana.

    Estas reglas llegan al final, cuando las semanas ya están construidas, y
    sustituyen el contenido de una ranura. El problema es a quién se lo quitan:
    antes elegían una ranura al azar entre todas las del componente y pisaban lo
    que hubiera, incluido el pescado que la regla de frecuencia acababa de
    reservar. Uno de cada cinco planes salía BLOQUEADO por eso, con un mensaje
    aritméticamente correcto y clínicamente incomprensible ("pescado aparece 1
    vez; el protocolo exige 2"), y como esto corre FUERA del bucle de reintentos,
    los 60 intentos no lo arreglaban nunca.

    Ahora la res solo puede ocupar una ranura de relleno: lo que ninguna otra
    regla había reservado.
    """
    dias_totales = len(plan["semanas"]) * 7
    protegidas = _familias_protegidas(protocolo, frecuencias)
    catalogo = {
        o.nombre: o for lista in rep.por_componente.values() for o in lista
    }

    def reservada(item: dict, comp: str) -> bool:
        opcion = catalogo.get(item["nombre"])
        if opcion is None:
            # Si no se puede identificar, se trata como reservada: quitarle la
            # ranura a algo que no sabemos qué es rompe más de lo que arregla.
            return True
        return any(c == comp and opcion.responde_a(clave) for c, clave in protegidas)

    for regla in frecuencias:
        if not regla.get("cada_dias"):
            continue
        comp, fam = regla["componente"], regla.get("familia", "")
        n = max(0, round(dias_totales / int(regla["cada_dias"]) * int(regla.get("veces", 1))))
        if n == 0:
            continue
        candidatas = rep.candidatas(comp, (regla.get("en") or [""])[0], fam)
        if not candidatas:
            continue
        ranuras = [
            (s["semana"], d, c)
            for s in plan["semanas"]
            for d, dia in s["dias"].items()
            for c, cm in dia.items()
            if c in (regla.get("en") or [])
            and any(
                i["componente"] == comp and not reservada(i, comp) for i in cm["items"]
            )
        ]
        if not ranuras:
            continue
        for sem, d, c in rng.sample(ranuras, min(n, len(ranuras))):
            elegida = rng.choice(candidatas)
            bloque = next(s for s in plan["semanas"] if s["semana"] == sem)
            for item in bloque["dias"][d][c]["items"]:
                if item["componente"] == comp and not reservada(item, comp):
                    item["nombre"] = elegida.nombre
                    item["receta_id"] = elegida.id if elegida.es_receta else None


def ensamblar(nombre_carpeta: str, semilla: int | None = None) -> dict:
    carpeta = DIR_PACIENTES / nombre_carpeta
    if not carpeta.exists():
        raise ErrorNutriOS(f"No existe la carpeta {carpeta}")

    ficha = cargar_ficha(carpeta)
    protocolo = cargar_protocolo(ficha["protocolo_sugerido"])

    # Antes de construir nada: ¿este caso debe tener un plan?
    #
    # Se comprueba aquí y no solo en el validador porque un caso que hay que
    # derivar o estudiar antes no necesita que se le calculen catorce días de
    # menús. Parar temprano también es más honesto: quien lo ejecuta ve el
    # motivo clínico, no un plan terminado con una nota al pie.
    paradas = parada_clinica.bloqueantes(parada_clinica.revisar(ficha, protocolo))
    if paradas:
        raise ErrorNutriOS(
            "El caso no pasa la revisión clínica previa, así que no se ensambla plan:\n\n"
            + "\n\n".join(f"  · {h.mensaje}" for h in paradas)
        )

    estado_rango, mensaje_rango = comprobar_rango_edad(protocolo, ficha)
    if estado_rango == "fuera_sin_justificar":
        raise ErrorNutriOS(mensaje_rango)

    # Los ajustes por diagnóstico se resuelven ANTES de tocar nada: suben las
    # frecuencias que el protocolo pide subir y añaden las exclusiones que el
    # diagnóstico impone. Un ajuste declarado que no se puede aplicar detiene el
    # ensamblaje: seguir sería construir un plan al que le falta un ajuste
    # clínico y no decirlo.
    frecuencias, exclusiones_extra, problemas = ajustes_clinicos(protocolo, ficha)
    if problemas:
        raise ErrorNutriOS("\n  - ".join(["Ajustes clínicos que no se pueden aplicar:"] + problemas))

    recetas, avisos = cargar_biblioteca()
    rep = Repertorio(
        recetas + cargar_alimentos_base(), ficha, protocolo, frecuencias, exclusiones_extra
    )

    variedad = protocolo.get("variedad") or {}
    n_semanas = int(ficha["semanas_plan"])
    base = semilla if semilla is not None else 0

    for intento in range(MAX_INTENTOS):
        rng = random.Random(base + intento)
        try:
            semanas = [
                construir_semana(protocolo, frecuencias, ficha, rep, rng, i + 1)
                for i in range(n_semanas)
            ]
        except ErrorNutriOS as e:
            if "Biblioteca insuficiente" in str(e) or intento >= 3:
                raise
            continue

        if variedad.get("no_repetir_dia_completo") and n_semanas > 1:
            firmas = [firma_dia(d) for s in semanas for d in s["dias"].values()]
            if len(firmas) != len(set(firmas)):
                continue
        break
    else:
        raise ErrorNutriOS(
            "No se logró un plan que cumpla las reglas de variedad. "
            "La biblioteca probablemente es demasiado pequeña para este paciente."
        )

    plan = {
        "paciente": ficha["paciente"],
        "edad_texto": ficha.get("edad_texto", f"{ficha['edad_meses']} meses"),
        "edad_meses": ficha["edad_meses"],
        "fecha": str(ficha.get("fecha", "")),
        "diagnostico_texto": ficha.get("diagnostico_texto", ""),
        "diagnosticos": ficha.get("diagnosticos") or [],
        "alergias": ficha.get("alergias") or [],
        # Íntegro. Lo que sale en el informe es lo que dice la ficha, y la
        # biblioteca del sistema no filtra nunca lo que se le comunica a la
        # familia: que un alimento no tenga base en el catálogo no es motivo
        # para ocultarle a la madre que su hijo no lo come.
        "rechazos": ficha.get("rechazos") or [],
        "datos_sin_fuente": ficha.get("datos_sin_fuente") or [],
        "protocolo": protocolo["id"],
        "protocolo_nombre": protocolo["nombre"],
        "semanas": semanas,
        "marco_diario": protocolo.get("marco_diario") or {},
        "avisos_biblioteca": avisos,
        "degradaciones": sorted({d for s_ in semanas for d in s_["degradaciones"]}),
    }
    aplicar_reglas_periodicas(plan, protocolo, frecuencias, rep, random.Random(base))

    plan["recetas_usadas"] = sorted(
        {
            i["receta_id"]
            for s in plan["semanas"]
            for dia in s["dias"].values()
            for cm in dia.values()
            for i in cm["items"]
            if i["receta_id"]
        }
    )
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensambla el plan de un paciente.")
    ap.add_argument("paciente", help="nombre de la carpeta en /pacientes/")
    ap.add_argument("--semilla", type=int, default=None)
    args = ap.parse_args()

    try:
        plan = ensamblar(args.paciente, args.semilla)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    destino = DIR_PACIENTES / args.paciente / "plan.json"
    guardar_json(destino, plan)

    n_dias = len(plan["semanas"]) * 7
    print(f"✓ Plan ensamblado para {plan['paciente']}")
    print(f"  {len(plan['semanas'])} semana(s) · {n_dias} días · protocolo {plan['protocolo']}")
    print(f"  {len(plan['recetas_usadas'])} recetas del recetario")
    for a in plan["avisos_biblioteca"] + plan["degradaciones"]:
        print(f"  ⚠ {a}")
    print(f"  → {destino.relative_to(Path.cwd()) if destino.is_relative_to(Path.cwd()) else destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
