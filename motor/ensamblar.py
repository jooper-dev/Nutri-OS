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
    HUECO,
    ErrorNutriOS,
    Opcion,
    ajustes_clinicos,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_despensa_basica,
    cargar_ficha,
    cargar_protocolo,
    coincide_alimento,
    exposiciones_declaradas,
    comidas_activas,
    comprobar_rango_edad,
    conceder_ancla,
    es_despensa,
    guardar_json,
    normalizar,
    rasgos_aversivos,
    resolver_regla_acoplada,
)

MAX_INTENTOS = 60


# ---------------------------------------------------------------------------
# Selección de opciones
# ---------------------------------------------------------------------------


class Repertorio:
    """Todas las opciones disponibles, ya filtradas para este paciente.

    El filtrado va en capas y el orden importa, porque cada una explica un
    descarte distinto en el reporte: primero lo que este niño no puede comer
    (alergia, exclusión, edad, textura, rasgo aversivo), después lo que su boca
    no puede procesar hoy (techo oral y visual), y por último lo que no está en
    su repertorio y nadie ha declarado como exposición.
    """

    def __init__(
        self,
        opciones: list[Opcion],
        ficha: dict,
        protocolo: dict,
        frecuencias: list[dict],
        exclusiones_extra: set[str] | None = None,
        rasgos_excluidos: set[str] | None = None,
        n_semana: int = 1,
    ):
        self.ficha = ficha
        self.protocolo = protocolo
        self.gramatica = {
            str(k): (v or {}) for k, v in (protocolo.get("gramatica") or {}).items()
        }
        self.descartes: list[tuple[str, str]] = []
        # Cuántas reglas duras rompió la última elección. Lo lee quien llama
        # para decidir si degrada la familia de la rotación.
        self.ultima_rompe = 0
        self.por_componente: dict[str, list[Opcion]] = defaultdict(list)
        self.anclas: list[Opcion] = []

        perfil = ficha.get("perfil_sensorial") or {}
        self.techo_oral = perfil.get("nivel_oral_actual")
        self.techo_visual = perfil.get("nivel_visual_actual")

        despensa = cargar_despensa_basica()
        repertorio = [str(x) for x in (ficha.get("repertorio_aceptado") or [])]
        # T-8 · una exposición entra a partir de SU semana y se queda: la
        # exposición sin presión es la intervención, no el consumo, así que un
        # alimento nuevo se mantiene en el plan aunque se rechace.
        declaradas = exposiciones_declaradas(ficha)
        expuestos = [
            clave
            for clave, datos in declaradas.items()
            if datos["desde_semana"] <= n_semana
        ]
        self.expuestos = expuestos
        self.expuestos_nuevos = [
            clave
            for clave, datos in declaradas.items()
            if datos["desde_semana"] == n_semana
        ]

        for o in opciones:
            apta, motivo = o.apta_para(ficha, exclusiones_extra, rasgos_excluidos)
            if not apta:
                self.descartes.append((o.nombre, motivo))
                continue

            # R-11 · prohibido lo genérico. «Fruta picada» no dice qué fruta
            # ni cuánta, y no se puede contrastar contra una lista de
            # exclusiones que nombra especies. El validador lo rechazaría
            # igualmente: no tiene sentido elegirlo para tumbar el plan después.
            if o.generico:
                self.descartes.append((o.nombre, "R-11: nombre genérico, no verificable"))
                continue

            # T-1 · techo de demanda oral. Un componente que lo supera solo
            # puede entrar como RETO, y el reto lo coloca el generador a
            # propósito: no se cuela por relleno. Es lo que evita un salto de N0
            # a N4 a las 7:30 con tono oral bajo.
            if (
                self.techo_oral is not None
                and o.demanda_oral is not None
                and o.demanda_oral > int(self.techo_oral)
            ):
                self.descartes.append(
                    (o.nombre, f"T-1: N{o.demanda_oral} sobre el techo N{self.techo_oral}")
                )
                continue

            # T-7 · techo de carga visual, con un nivel de margen. V3 no es «un
            # poco más difícil»: es otra categoría de tarea.
            if (
                self.techo_visual is not None
                and o.carga_visual is not None
                and o.carga_visual > int(self.techo_visual) + 1
            ):
                self.descartes.append(
                    (o.nombre, f"T-7: V{o.carga_visual} sobre el techo V{self.techo_visual}")
                )
                continue

            # T-8 · fuera del repertorio, o va declarado, o no va. La regla ya
            # existía para los ingredientes de una receta y no para el alimento
            # servido tal cual, y por ahí entró la pavita ocho veces en catorce
            # días sin que nadie la hubiera nombrado en la anamnesis.
            if repertorio and not o.es_receta and not es_despensa(o.nombre, despensa):
                conocido = any(coincide_alimento(r, o) for r in repertorio)
                declarado = any(coincide_alimento(e, o) for e in expuestos)
                if not conocido and not declarado:
                    self.descartes.append(
                        (o.nombre, "fuera del repertorio y sin declarar como exposición")
                    )
                    continue

            self.por_componente[o.componente].append(o)
            if o.es_ancla:
                self.anclas.append(o)

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

    # -- Capa 2 · la gramática decide de dónde salen los candidatos --------

    def _fuentes(self, componente: str) -> list[str]:
        slot = self.gramatica.get(componente)
        if slot is None:
            return [componente]
        fuentes = slot.get("fuentes")
        if fuentes is None:
            return [componente]
        return [str(f) for f in fuentes]

    def roles_de(self, componente: str) -> list[str]:
        return [str(r) for r in ((self.gramatica.get(componente) or {}).get("roles") or [])]

    def candidatas(self, componente: str, comida: str, familia: str = "") -> list[Opcion]:
        """Lo que puede ocupar este slot en esta comida.

        Dos filtros y en este orden: de dónde sale (las `fuentes` del slot) y
        con qué rol entra (R-0). El rol es lo que impide que un tubérculo llene
        el sitio de la proteína aunque esté guardado en el mismo cajón.
        """
        roles = self.roles_de(componente)
        if "ancla" in roles:
            pool = list(self.anclas)
        else:
            pool = [o for f in self._fuentes(componente) for o in self.por_componente.get(f, [])]

        salida = []
        vistos: set[str] = set()
        for o in pool:
            if o.id in vistos:
                continue
            # Dos niveles: la clave del protocolo puede ser un cajón (familia)
            # o un alimento concreto (id). Ver Opcion.responde_a.
            if familia and not o.responde_a(familia):
                continue
            # Una receta solo entra en los momentos que declara.
            if o.es_receta and o.momento and comida not in o.momento:
                continue
            if roles and not o.rol_para(roles):
                continue
            vistos.add(o.id)
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
        presupuesto: dict | None = None,
        contexto: dict | None = None,
    ) -> Opcion | None:
        """Elige qué llena este slot, con las reglas duras delante.

        `contexto` es lo que ya hay en esta comida y lo que pasó ayer. Sin él,
        el generador elegía a ciegas y el validador rechazaba después: un
        desayuno con ancla líquida, grasa untable y fruta colada cumple todas
        las frecuencias y rompe R-4 —tres componentes en papilla—, y una cena
        que copia el almuerzo rompe T-5. Mirar el conjunto al elegir no es armar
        la grilla por fuerza bruta: es no meter a sabiendas lo que va a salir
        rechazado.
        """
        pool = self.candidatas(componente, comida, familia)
        # Si la ranura no pide una familia concreta, no puede tomar prestada una
        # familia que tiene cupo propio en el protocolo: se desbordaría su
        # frecuencia (el hígado 1x/semana acabaría apareciendo cuatro veces).
        if not familia or excluir_reguladas:
            pool = [o for o in pool if normalizar(o.familia) not in self.reguladas] or pool
        if not pool:
            return None

        # El ancla está exenta del tope de repetición: se sirve todos los días y
        # no cuenta para ninguna regla de variedad (V-5, T-10).
        disponibles = [
            o for o in pool if o.es_ancla or (not o.es_receta) or usos[o.id] < tope_semana
        ]
        if not disponibles:
            return None

        orden = self.prioridades.get(componente) or []

        def preferencia(o: Opcion) -> int:
            for i, clave in enumerate(orden):
                if o.responde_a(clave):
                    return i
            return len(orden)   # lo que no está en la lista va al final

        # T-3 y R-7 juntos, como criterio de desempate y no como filtro: donde
        # la franja tiene presupuesto sensorial apretado —la cena—, la opción
        # más suave gana; y a igualdad, la de mayor densidad calórica, porque a
        # un niño que come poco no se le pide comer más, se le da más en lo poco
        # que come.
        sentido = str((presupuesto or {}).get("sentido") or "")
        densidad = {"alta": 0, "media": 1, "baja": 2}
        ctx = contexto or {}
        puestas: list[Opcion] = list(ctx.get("opciones") or [])
        tope_franja: dict = ctx.get("tope_franja") or {}
        tope_suma_dia = ctx.get("tope_suma_dia")
        ayer: set[str] = set(ctx.get("ayer") or set())

        # Lo que todavía va a entrar en esta comida. Sin esto, el generador
        # elegía cada slot mirando solo lo ya puesto y se quedaba sin salida al
        # final: con el ancla líquida y la fruta colada ya dentro, ninguna grasa
        # untable podía entrar sin romper R-4 — y la comida sí tenía solución si
        # la fruta se elegía sabiendo que después venía una grasa de N1.
        pend_blandos: int = int(ctx.get("pendientes_blandos") or 0)
        pend_suma: int = int(ctx.get("pendientes_suma") or 0)

        def rompe(o: Opcion) -> int:
            """Cuántas reglas duras rompería meter esto aquí. Menos es mejor."""
            fallos = 0
            # R-1 · un solo grano por comida, y una sola base botánica. Es lo
            # que impide «avena + panqueques de avena» y «barritas de kiwicha +
            # kiwicha pop»: dos nombres distintos y un solo cereal. Se comprueba
            # sobre el grano, no sobre el título, y también sobre lo que no
            # forma bocado, porque un aceite de ajonjolí sigue siendo ajonjolí.
            if o.grano_base and any(
                x.grano_base == o.grano_base for x in puestas
            ):
                fallos += 1
            if o.base_botanica and o.base_botanica != "mezcla" and any(
                x.base_botanica == o.base_botanica for x in puestas
            ):
                fallos += 1
            if not o.forma_bocado:
                return fallos
            bocados = [x for x in puestas if x.forma_bocado] + [o]
            # R-4 · máximo dos componentes en papilla por comida.
            blandos = sum(1 for x in bocados if (x.demanda_oral or 0) <= 1)
            if blandos + pend_blandos > 2:
                fallos += 1
            suma = sum(x.demanda_oral or 0 for x in bocados) + pend_suma
            n3 = sum(1 for x in bocados if (x.demanda_oral or 0) >= 3)
            n4 = sum(1 for x in bocados if (x.demanda_oral or 0) >= 4)
            # T-3 · presupuesto de la franja.
            if tope_franja.get("suma_n") is not None and suma > int(tope_franja["suma_n"]):
                fallos += 1
            if tope_franja.get("max_n3") is not None and n3 > int(tope_franja["max_n3"]):
                fallos += 1
            if tope_franja.get("max_n4") is not None and n4 > int(tope_franja["max_n4"]):
                fallos += 1
            # T-5 · la cena pesa menos que el almuerzo del mismo día.
            if tope_suma_dia is not None and suma > int(tope_suma_dia):
                fallos += 1
            return fallos

        def puntaje(o: Opcion) -> tuple:
            clinico = -len(self.priorizar & set(o.aporta))   # menor = mejor
            # La demanda oral pesa más que la variedad en las dos franjas que
            # tienen presupuesto propio, y en direcciones opuestas:
            #
            #   cena      lo más suave. A las 18:00 la fatiga oral es máxima y
            #             la comida tiene que terminar en éxito (T-4, T-5).
            #   almuerzo  lo más exigente que quepa en el presupuesto. Es la
            #             comida de trabajo: si también aquí se eligiera lo
            #             blando, la cena no tendría por dónde quedar dos
            #             puntos por debajo y T-5 sería imposible de cumplir.
            #
            # `rompe()` es el que impide pasarse del techo por arriba; esto solo
            # decide hacia dónde tira dentro de lo que ya cabe.
            #
            # El ancla queda fuera de las dos direcciones, y de la rotación. No
            # compite: es el mismo alimento seguro todos los días, lo elige la
            # lista de prioridades del protocolo y nada más. Sin esta excepción,
            # el desayuno prefería la papa amarilla (N2) a la quinua licuada
            # (N0) por ser «más de trabajo», y el alimento seguro del niño
            # desaparecía del plan por segunda vez y por otro camino.
            n = o.demanda_oral or 0
            if o.es_ancla:
                esfuerzo = 0
            elif sentido == "suave":
                esfuerzo = n
            elif sentido == "trabajo":
                esfuerzo = -n
            else:
                esfuerzo = 0
            rotacion = 0 if o.es_ancla else usos[o.id]
            return (
                rompe(o),
                # V-2 · ninguna receta en días consecutivos. El ancla exenta.
                1 if (o.es_receta and not o.es_ancla and o.id in ayer) else 0,
                *((esfuerzo, rotacion) if sentido else (rotacion, esfuerzo)),
                clinico,
                preferencia(o),
                densidad.get(o.densidad_kcal, 1),
                0 if o.validada_en_cocina else 1,
                rng.random(),
            )

        mejor = min(disponibles, key=puntaje)
        self.ultima_rompe = rompe(mejor)
        return mejor


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


def _reparto(
    reparto: dict, total: int, viables: set[str] | None = None
) -> list[str]:
    """Convierte {avena:2, canihua:2, resto:...} en una lista de N familias.

    **V-4 · Redistribución proporcional.** Cuando una familia de la rotación no
    tiene ningún candidato para este paciente, sus cupos se reparten entre las
    demás **en proporción a lo que ya tenían**, y no se acumulan sobre una sola.

    Esto salió de un plan real: al excluir la cañihua, sus dos cupos semanales
    se fueron enteros a la quinua licuada. Una regla de variedad terminó
    produciendo monotonía, que es exactamente lo contrario de lo que la regla
    existe para hacer.

    `viables` son las claves que sí tienen candidatos. Si no se pasa, no se
    redistribuye nada y el comportamiento es el de siempre.
    """
    fijas, resto_key = [], None
    cupos: dict[str, int] = {}
    for fam, n in reparto.items():
        if str(n).strip() == "resto":
            if resto_key:
                raise ErrorNutriOS("Una rotación no puede tener dos valores 'resto'.")
            resto_key = fam
        else:
            cupos[fam] = int(n)

    if viables is not None:
        caidas = {f: n for f, n in cupos.items() if f not in viables}
        vivas = {f: n for f, n in cupos.items() if f in viables}
        huerfanos = sum(caidas.values())
        if huerfanos and vivas:
            base = sum(vivas.values()) or 1
            reparto_extra = {
                f: huerfanos * n // base for f, n in vivas.items()
            }
            sobra = huerfanos - sum(reparto_extra.values())
            # Lo que no cae en cuenta redonda va a las de mayor cupo, en orden
            # estable: el reparto no puede depender de cómo iteró el diccionario.
            for f, _ in sorted(vivas.items(), key=lambda kv: (-kv[1], kv[0]))[:sobra]:
                reparto_extra[f] += 1
            cupos = {f: n + reparto_extra[f] for f, n in vivas.items()}
        elif huerfanos:
            cupos = vivas

    for fam, n in cupos.items():
        fijas += [fam] * n

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
        # V-4: qué claves de la rotación tienen de verdad algún candidato para
        # este paciente. Las que no, ceden su cupo proporcionalmente.
        viables = {
            fam
            for fam in (rot.get("reparto") or {})
            if str(rot["reparto"][fam]).strip() == "resto"
            or any(rep.candidatas(comp, c, fam) for c in comidas_validas)
        }
        familias = _reparto(rot["reparto"], len(ranuras), viables)
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
            # El suplemento no se elige: lo inyecta la ficha con su dosis, su
            # hora y su separación de lácteos. Buscarle candidatos en el
            # catálogo declararía siete huecos al día por un slot que sí está
            # lleno.
            if comp == "suplemento":
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

    # --- 4b. Intervenciones activas: el producto, no la categoría ----------
    # I-1. La frecuencia del protocolo pide la familia («yogurt, media tarde»);
    # la intervención activa refina a QUÉ yogurt, porque «el estreñimiento se
    # normalizó desde que recibe yogurt a diario» se refiere al que ya toma.
    # El plan anterior lo bajó a tres veces por semana Y le cambió el producto:
    # las dos cosas modifican un tratamiento en curso que estaba funcionando.
    for iv in ficha.get("intervenciones_activas") or []:
        alimento = str(iv.get("alimento") or "").strip()
        if not alimento:
            continue
        franja = str(iv.get("franja") or "").strip()
        for clave, fam in list(familia_forzada.items()):
            d, c, comp = clave
            if franja and c != franja:
                continue
            concretas = [
                o for o in rep.candidatas(comp, c, fam)
                if normalizar(o.id) == normalizar(alimento)
            ]
            if concretas:
                familia_forzada[clave] = alimento

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
        # El tope de repetición solo lo tienen las recetas: un alimento base
        # puede ir a diario y nadie espera lo contrario del arroz. Contarlo
        # todo con tope bloqueaba planes que sí se podían construir, y la
        # señal que sí importa —una sola preparación cubriendo la franja
        # entera— la da V-3 en el reporte, como aviso clínico y no como error
        # de aritmética.
        con_receta = sum(1 for o in opciones if o.es_receta)
        hay_base = any(not o.es_receta for o in opciones)
        techo = float("inf") if hay_base else con_receta * tope
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
    # Aquí es donde la v2 se separa del motor anterior: si un slot se queda sin
    # candidatos válidos NO se rellena con lo que haya. Se declara el hueco, se
    # dice qué reglas vaciaron el conjunto y qué receta lo cerraría.
    #
    # Un hueco declarado es un resultado profesional. Un cereal ocupando el slot
    # de la proteína es un error que la nutricionista ve en tres segundos.
    presupuesto = protocolo.get("presupuesto_sensorial") or {}
    # Dónde conviene elegir lo más suave a igualdad de todo lo demás: en las
    # comidas donde no se admite ningún reto. A las 18:00 la mandíbula de un niño
    # con tono bajo ya trabajó todo el día, y la cena tiene que cerrar en éxito.
    # En el almuerzo NO se aplica: ahí preferir siempre lo blando produciría el
    # otro error, una comida de trabajo sin trabajo.
    suaves = {str(x) for x in (presupuesto.get("comidas_sin_reto") or [])}
    degradaciones: set[str] = set()
    huecos: dict[tuple[int, str, str], dict] = {}
    # El orden importa: dentro de un día, el almuerzo se construye antes que la
    # cena, y por eso T-5 puede mirar cuánto pesó el almuerzo al elegir la cena.
    orden_comida = {c["id"]: n for n, c in enumerate(protocolo.get("comidas") or [])}
    #
    # Y dentro de una comida, primero el slot con menos candidatos. El orden
    # alfabético dejaba la grasa para el final, y cuando le tocaba ya había dos
    # componentes en papilla delante: ninguna grasa untable podía entrar sin
    # romper R-4, aunque la comida sí tenía solución si se elegía al revés.
    anchura = {
        (c, comp): len(rep.candidatas(comp, c))
        for _d, c, comp in set(a_llenar)
    }
    orden = sorted(
        set(a_llenar),
        key=lambda t: (
            t[0],
            orden_comida.get(t[1], 99),
            anchura.get((t[1], t[2]), 99),
            t[2],
        ),
    )
    suma_dia: dict[tuple[int, str], int] = {}
    usados_por_dia: dict[int, set[str]] = defaultdict(set)

    for d, c, comp in orden:
        fam = familia_forzada.get((d, c, comp), "")
        aprieta = {"sentido": "suave"} if c in suaves else (
            {"sentido": "trabajo"} if presupuesto.get(c) else {}
        )
        puestas = [o for o in semana[d][c].values()]
        tope_suma_dia = None
        margen = presupuesto.get("margen_cena")
        if c == "cena" and margen is not None and (d, "almuerzo") in suma_dia:
            tope_suma_dia = suma_dia[(d, "almuerzo")] - int(margen)
        # Qué queda por llenar de esta comida, para que el que elige ahora sepa
        # cuánta demanda oral se va a gastar después.
        pendientes = [
            x
            for (dd, cc, xx) in orden
            if dd == d and cc == c and xx not in semana[d][c] and xx != comp
            for x in [xx]
        ]
        pend_blandos = 0
        pend_suma = 0
        for otro in pendientes:
            opciones_otro = rep.candidatas(otro, c, familia_forzada.get((d, c, otro), ""))
            bocados_otro = [o for o in opciones_otro if o.forma_bocado]
            if not bocados_otro:
                continue
            minimo = min((o.demanda_oral or 0) for o in bocados_otro)
            pend_suma += minimo
            if all((o.demanda_oral or 0) <= 1 for o in bocados_otro):
                pend_blandos += 1

        contexto = {
            "opciones": puestas,
            "tope_franja": presupuesto.get(c) or {},
            "tope_suma_dia": tope_suma_dia,
            "ayer": usados_por_dia.get(d - 1, set()),
            "pendientes_blandos": pend_blandos,
            "pendientes_suma": pend_suma,
        }
        elegida = rep.elegir(
            comp, c, fam, usos, tope, rng, presupuesto=aprieta, contexto=contexto
        )
        # La rotación pedía una familia y esa familia rompe una regla dura aquí:
        # la palta de la cena es un bocado más y deja la cena por encima del
        # almuerzo (T-5). Se degrada a otra familia del mismo componente, y
        # NUNCA en silencio. Solo se hace cuando el componente no tiene regla de
        # frecuencia propia: una frecuencia escrita no se degrada por
        # comodidad sensorial, se declara el conflicto y lo resuelve Paty.
        regulado = any(
            f.get("componente") == comp and f.get("veces") is not None
            for f in frecuencias
        )
        if elegida is not None and fam and rep.ultima_rompe and not regulado:
            alterna = rep.elegir(
                comp, c, "", usos, tope, rng,
                excluir_reguladas=True, presupuesto=aprieta, contexto=contexto,
            )
            if alterna is not None and rep.ultima_rompe == 0:
                degradaciones.add(
                    f"{comp}/{fam}: la rotación pedía «{fam}» y aquí rompía una regla "
                    f"sensorial; se sustituyó por «{alterna.familia or alterna.id}»"
                )
                elegida = alterna
        if elegida is None and fam:
            # La familia que pedía el protocolo no tiene ninguna opción viable
            # para este paciente (alergia, rechazo o edad). Se degrada a otra,
            # pero NUNCA en silencio: queda registrado para el reporte de QA.
            degradaciones.add(
                f"{comp}/{fam}: sin opciones para este paciente; se sustituyó por otra familia"
            )
            elegida = rep.elegir(
                comp,
                c,
                "",
                usos,
                tope,
                rng,
                excluir_reguladas=True,
                presupuesto=aprieta,
                contexto=contexto,
            )
        if elegida is None:
            huecos[(d, c, comp)] = _declarar_hueco(rep, comp, c, fam, ficha)
            continue
        usos[elegida.id] += 1
        semana[d][c][comp] = elegida
        usados_por_dia[d].add(elegida.id)
        if elegida.forma_bocado:
            suma_dia[(d, c)] = suma_dia.get((d, c), 0) + (elegida.demanda_oral or 0)

    # --- 7. Serialización ---------------------------------------------------
    gram = {str(k): (v or {}) for k, v in (protocolo.get("gramatica") or {}).items()}
    salida = {
        "semana": n_semana,
        "dias": {},
        "degradaciones": sorted(degradaciones),
        "huecos": [],
    }
    for d in range(7):
        dia = {}
        for comida in activas:
            items = []
            for comp in comida["componentes"]:
                hueco = huecos.get((d, comida["id"], comp))
                if hueco:
                    items.append(
                        {
                            "componente": comp,
                            "rol": (gram.get(comp) or {}).get("papel", ""),
                            "nombre": HUECO,
                            "cantidad": "",
                            "receta_id": None,
                            "hueco": True,
                            **hueco,
                        }
                    )
                    salida["huecos"].append(
                        {"dia": DIAS[d], "comida": comida["id"], "componente": comp, **hueco}
                    )
                    continue
                o = semana[d][comida["id"]].get(comp)
                if not o:
                    continue
                item = {
                    "componente": comp,
                    # Con qué rol llena ESTE slot. Un alimento puede poder cubrir
                    # varios, pero en una comida dada ocupa exactamente uno: si la
                    # quinua entra como cereal, no cuenta además como proteína.
                    "rol": o.rol_para(rep.roles_de(comp)),
                    "nombre": o.nombre,
                    # R-12 y O-5: la unidad la pone el alimento, y su formato
                    # seguro se imprime aquí, en la grilla, no solo en la receta.
                    "cantidad": o.porcion_impresa(porciones.get(comp, "")),
                    "receta_id": o.id if o.es_receta else None,
                }
                # Solo los alimentos base se marcan aquí. Una receta declara
                # sus propias exposiciones en su front-matter, ingrediente por
                # ingrediente, y marcarla entera porque su id contiene la
                # palabra «zanahoria» convertía un muffin que el niño ya come en
                # una introducción nueva.
                if not o.es_receta and any(
                    coincide_alimento(e, o) for e in rep.expuestos
                ):
                    item["exposicion"] = True
                items.append(item)
            if items:
                dia[comida["id"]] = {
                    "nombre": comida["nombre"],
                    "hora": comida.get("hora", ""),
                    "items": items,
                }
        salida["dias"][DIAS[d]] = dia
    return salida


def _declarar_hueco(
    rep: Repertorio, comp: str, comida: str, familia: str, ficha: dict
) -> dict:
    """Qué falta para cerrar este slot, escrito para que se pueda encargar.

    No basta con decir que está vacío: hay que decir qué receta habría que
    escribir —qué rol, qué techo de demanda oral, qué carga visual máxima y qué
    restricciones— para que alguien pueda sentarse a escribirla con P1.
    """
    perfil = ficha.get("perfil_sensorial") or {}
    slot = rep.gramatica.get(comp) or {}
    roles = ", ".join(rep.roles_de(comp)) or "(sin roles declarados)"
    motivos = [m for _, m in rep.descartes]
    frecuentes = sorted({m.split(":")[0] for m in motivos})[:5]
    return {
        "motivo": (
            f"ningún candidato de rol [{roles}]"
            + (f" en la familia «{familia}»" if familia else "")
            + f" pasa los filtros de este paciente."
        ),
        "reglas": ", ".join(frecuentes) or "—",
        "receta_que_falta": (
            f"receta de componente «{comp}», momento «{comida}», rol [{roles}], "
            f"demanda oral ≤ N{perfil.get('nivel_oral_actual', '?')}, carga visual ≤ "
            f"V{perfil.get('nivel_visual_actual', '?')}"
            + (
                f", sin el rasgo «{perfil['concepto_aversivo']}»"
                if perfil.get("concepto_aversivo")
                else ""
            )
            + ". Se escribe con prompts/P1_RECETAS.md en modo BASE."
        ),
    }


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
                    # La porción viaja con el alimento, no con la ranura. Sin
                    # esto, la res entraba con la unidad del pollo al que
                    # sustituía y sin su formato seguro impreso (R-12, O-5).
                    item["cantidad"] = elegida.porcion_impresa(item.get("cantidad", ""))
                    item["rol"] = elegida.roles[0] if elegida.roles else item.get("rol", "")


def _inyectar_suplementos(plan: dict, ficha: dict, protocolo: dict) -> None:
    """R-Fe3 · El suplemento es una fila del plan, no una nota al pie.

    No pasa por el catálogo, y es deliberado: un suplemento es de este paciente
    —marca, dosis, horario y separación—, no un alimento que el sistema elija.
    Lo que hace el motor es asegurarse de que se imprima, con su hora y con la
    separación de lácteos escrita con todas las letras.

    En el primer caso real, «Kid Cal 7.5 ml en ayunas» vivía en el texto del
    enfoque. Lo que no está en la grilla, la madre no lo lee a las siete de la
    mañana.
    """
    suplementos = [s for s in (ficha.get("suplementos") or []) if s]
    if not suplementos:
        return
    franja = next(
        (c for c in (protocolo.get("comidas") or []) if "suplemento" in (c.get("componentes") or [])),
        None,
    )
    if franja is None:
        return

    items = []
    for s in suplementos:
        partes = [str(s.get("dosis") or "").strip(), str(s.get("horario") or "").strip()]
        separar = [str(x) for x in (s.get("separar_de") or []) if str(x).strip()]
        horas = s.get("horas_separacion")
        if separar and horas:
            partes.append(
                f"{horas} h de separación de {', '.join(separar)}"
            )
        items.append(
            {
                "componente": "suplemento",
                "rol": "suplemento",
                "nombre": str(s.get("nombre") or "Suplemento"),
                "cantidad": " · ".join(p for p in partes if p),
                "receta_id": None,
            }
        )

    for s_ in plan["semanas"]:
        for dia in s_["dias"].values():
            dia[franja["id"]] = {
                "nombre": franja.get("nombre", "Suplemento"),
                "hora": franja.get("hora", ""),
                "items": [dict(i) for i in items],
            }
            # El orden de las comidas del día lo fija el protocolo, y el
            # suplemento va primero: se acaba de añadir al final del dict.
            orden = [c["id"] for c in (protocolo.get("comidas") or [])]
            for cid in orden:
                if cid in dia:
                    dia[cid] = dia.pop(cid)


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

    # T-6 · el concepto aversivo se traduce a rasgos ANTES de filtrar nada. Si
    # la ficha declara uno que el sistema no conoce, se detiene: un concepto que
    # no filtra nada es peor que no declararlo, porque hace creer que la
    # aversión está contemplada y el kiwi vuelve al plato.
    rasgos_excluidos, problemas_rasgos = rasgos_aversivos(ficha)
    if problemas_rasgos:
        raise ErrorNutriOS("\n".join(problemas_rasgos))

    recetas, avisos = cargar_biblioteca()
    opciones = recetas + cargar_alimentos_base()

    # El ancla no es una propiedad del alimento: es de ESTE niño. Se concede
    # aquí, sobre las opciones ya cargadas, antes de construir el repertorio.
    huerfanas = conceder_ancla(opciones, ficha)
    if huerfanas:
        raise ErrorNutriOS(
            "La ficha declara como alimento ancla algo que no existe en el catálogo ni "
            "en la biblioteca: " + ", ".join(huerfanas) + ".\n"
            "    El slot ANCLA se quedaría vacío todos los días, que es exactamente lo "
            "que pasó cuando el alimento seguro desapareció 8 de 14 días del plan.\n"
            "    Solución: escribe el ancla con el nombre con que el sistema conoce el "
            "alimento (datos/alimentos_base.yaml o el id de una base), o añade el "
            "alimento al catálogo."
        )

    rep = Repertorio(
        opciones,
        ficha,
        protocolo,
        frecuencias,
        exclusiones_extra,
        rasgos_excluidos,
    )

    variedad = protocolo.get("variedad") or {}
    n_semanas = int(ficha["semanas_plan"])
    base = semilla if semilla is not None else 0

    for intento in range(MAX_INTENTOS):
        rng = random.Random(base + intento)
        try:
            semanas = [
                construir_semana(
                    protocolo,
                    frecuencias,
                    ficha,
                    Repertorio(
                        opciones,
                        ficha,
                        protocolo,
                        frecuencias,
                        exclusiones_extra,
                        rasgos_excluidos,
                        n_semana=i + 1,
                    ),
                    rng,
                    i + 1,
                )
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
        "huecos": [
            {"semana": s_["semana"], **h} for s_ in semanas for h in s_.get("huecos", [])
        ],
    }
    _inyectar_suplementos(plan, ficha, protocolo)
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
