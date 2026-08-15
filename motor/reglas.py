"""
Catálogo de reglas — Nutri-OS · Capa 7

Aquí no se arma ningún plan: aquí se **comprueba** el que ya está armado, y se
rechaza por ID de regla. El generador piensa; esto verifica.

La distinción importa y es la que gobierna todo el archivo. Las reglas de
composición y sensoriales son criterio clínico y viven en `prompts/P2_PLAN.md`,
que es lo que lee quien decide qué poner. Lo que vive aquí es la aritmética que
dice si lo que se puso las cumple. Un motor que armara la grilla por fuerza
bruta a partir de estas reglas sería justo lo que este proyecto no es.

Cada regla tiene un ID estable —R-2, T-6, V-1, O-3— porque el reporte lo cita y
porque una nutricionista tiene que poder decir «tumba la T-4 de este niño» sin
describir el párrafo entero.

    R-xx    clínicas duras (composición, hierro, energía, exclusiones)
    T-xx    terapia ocupacional e integración sensorial
    V-xx    variedad y rotación
    O-xx    viabilidad operativa
    I-1     intervenciones activas

Qué NO está aquí, y por qué:

  · **R-7 (densidad sobre volumen)** y **T-9 (progresión por evidencia)** no son
    comprobables sobre un plan: son criterios de elección entre dos opciones
    equivalentes y de decisión clínica entre controles. Van al prompt.
  · **V-4 (redistribución proporcional)** no se verifica, se construye: vive en
    el reparto de rotaciones de `ensamblar.py`, que es quien reparte los cupos.
  · **R-10 (propagación de exclusiones)** se comprueba en tres sitios distintos
    —catálogo en `validar.py`, ingredientes y sustituciones en
    `recetas_paciente.py`— y aquí solo se recoge lo que falte.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from comun import (
    DIAS,
    HUECO,
    ROLES_CARBOHIDRATO,
    ROLES_PROTEICOS,
    Opcion,
    normalizar,
    normalizar_texto,
)

# Cuánta agua puede llevar una comida principal sin desplazar comida (R-9).
TOPE_AGUA_ML = 120

# Cuántas exposiciones nuevas admite una semana (T-8). Una. La exposición sin
# presión es la intervención; ocho pavitas en catorce días no son exposición
# graduada, son saturación, y garantizan el rechazo.
MAX_EXPOSICIONES_SEMANA = 1


@dataclass
class Infraccion:
    """Una regla que se rompió, con su ID y el sitio exacto."""

    id: str
    mensaje: str
    donde: str = ""
    bloquea: bool = True

    def texto(self) -> str:
        cabeza = f"[{self.id}]" + (f" {self.donde}" if self.donde else "")
        return f"{cabeza}: {self.mensaje}"


@dataclass
class Comida:
    """Una comida del plan con sus ítems ya cruzados contra el catálogo."""

    semana: int
    dia: str
    id: str
    nombre: str
    hora: str
    items: list[dict] = field(default_factory=list)
    opciones: list[Opcion] = field(default_factory=list)
    huecos: list[dict] = field(default_factory=list)

    @property
    def donde(self) -> str:
        return f"S{self.semana} · {self.dia} · {self.id}"

    def bocados(self) -> list[Opcion]:
        """Lo que la boca tiene que procesar de verdad.

        El agua y el aceite que va dentro de la preparación no son bocados, y
        contarlos distorsionaba las tres reglas que miden esfuerzo: R-4 marcaba
        «tres componentes en papilla» en un almuerzo cuyos tres eran el aceite,
        el agua y la fruta colada, y el presupuesto de T-3 se gastaba en cosas
        que nadie mastica.
        """
        return [o for o in self.opciones if o.forma_bocado]

    def suma_n(self) -> int:
        return sum(o.demanda_oral or 0 for o in self.bocados())


# ---------------------------------------------------------------------------
# Lectura del plan
# ---------------------------------------------------------------------------


def _buscar(catalogo: dict[str, Opcion], item: dict) -> Opcion | None:
    ident = item.get("receta_id") or normalizar(item.get("nombre") or "")
    return catalogo.get(ident) or next(
        (o for o in catalogo.values() if o.nombre == item.get("nombre")), None
    )


def leer_comidas(plan: dict, catalogo: dict[str, Opcion]) -> list[Comida]:
    """El plan convertido en comidas con sus opciones resueltas.

    Los huecos declarados se apartan: no son ítems que evaluar, son ausencias
    que ya vienen explicadas. Una regla que los tratara como alimentos diría
    cosas absurdas sobre ellos y taparía el hueco de verdad.
    """
    salida: list[Comida] = []
    for s in plan.get("semanas") or []:
        for dia, comidas in s["dias"].items():
            for cid, cm in comidas.items():
                c = Comida(
                    semana=s["semana"],
                    dia=dia,
                    id=cid,
                    nombre=cm.get("nombre", cid),
                    hora=cm.get("hora", ""),
                )
                for item in cm["items"]:
                    if item.get("hueco"):
                        c.huecos.append(item)
                        continue
                    c.items.append(item)
                    op = _buscar(catalogo, item)
                    if op:
                        c.opciones.append(op)
                salida.append(c)
    return salida


def _hora_inicio(texto: str) -> float | None:
    """La hora de inicio de una franja, en horas decimales.

    Los horarios del protocolo están escritos para leerse —«7:30 – 8:30», «6:00
    – 7:00»— y aquí hacen falta como número para poder medir la separación entre
    el suplemento y el lácteo más cercano (R-Fe3). Las tardes se escriben en
    formato de 12 h sin sufijo, así que una comida posterior al desayuno que dé
    una hora menor se interpreta como pm.
    """
    m = re.search(r"(\d{1,2})[:.](\d{2})", str(texto or ""))
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) / 60


def _horas_del_dia(protocolo: dict) -> dict[str, float]:
    """Hora de cada comida, ya desambiguada a formato de 24 h."""
    horas: dict[str, float] = {}
    previa = 0.0
    for comida in protocolo.get("comidas") or []:
        h = _hora_inicio(comida.get("hora"))
        if h is None:
            continue
        while h < previa:
            h += 12
        horas[str(comida.get("id"))] = h
        previa = h
    return horas


# ---------------------------------------------------------------------------
# Capa 2 · Gramática
# ---------------------------------------------------------------------------


def gramatica_de(protocolo: dict) -> dict[str, dict]:
    """El mapa componente → {papel, roles, opcional} del protocolo."""
    return {
        str(k): (v or {}) for k, v in (protocolo.get("gramatica") or {}).items()
    }


def comidas_principales(protocolo: dict) -> set[str]:
    presupuesto = protocolo.get("presupuesto_sensorial") or {}
    return {str(c) for c in (presupuesto.get("comidas_principales") or [])}


# ---------------------------------------------------------------------------
# R-0 · Tipado de slots
# ---------------------------------------------------------------------------


def r0_tipado(comidas: list[Comida], protocolo: dict, catalogo: dict) -> list[Infraccion]:
    """Un alimento solo llena un slot cuyo conjunto de roles contenga uno suyo.

    Esta sola regla habría bloqueado tres de los siete desayunos auditados. La
    «crema de quinua» es cereal y ocupó el slot del acompañante proteico; los
    «bastones de papa» son tubérculo y ocuparon el mismo. El plan salía con dos
    cereales y ninguna proteína, y nada lo señalaba porque el sistema solo sabía
    contar componentes, no papeles.
    """
    gram = gramatica_de(protocolo)
    if not gram:
        return []
    estructura = {
        str(c.get("id")): list(c.get("componentes") or [])
        for c in (protocolo.get("comidas") or [])
    }
    # Un componente que es objetivo de una regla acoplada solo se llena cuando
    # algo lo dispara: «menestra → fruta_vitc» significa que la fruta con
    # vitamina C aparece los días de menestra y no el resto. Exigirlo todos los
    # días convertiría en error el diseño del protocolo.
    dependientes = {
        str(r.get("entonces") or "").split(".")[-1]
        for r in (protocolo.get("reglas_acopladas") or [])
        if r.get("entonces")
    }
    out: list[Infraccion] = []

    for c in comidas:
        presentes = {i["componente"] for i in c.items} | {
            h["componente"] for h in c.huecos
        }
        for comp in estructura.get(c.id, []):
            slot = gram.get(comp) or {}
            if comp not in presentes and not slot.get("opcional") and comp not in dependientes:
                out.append(
                    Infraccion(
                        "R-0",
                        f"el slot obligatorio «{comp}» ({slot.get('papel', '?')}) está "
                        f"vacío y no se declaró como hueco. Un slot obligatorio sin "
                        f"llenar invalida la comida completa: o hay candidato, o hay "
                        f"{HUECO} con su motivo.",
                        c.donde,
                    )
                )

        for item in c.items:
            comp = item["componente"]
            slot = gram.get(comp)
            if slot is None:
                continue
            aceptados = list(slot.get("roles") or [])
            if not aceptados:
                continue
            op = _buscar(catalogo, item)
            if op is None:
                continue
            rol = op.rol_para(aceptados)
            if not rol:
                out.append(
                    Infraccion(
                        "R-0",
                        f"«{item['nombre']}» tiene rol {op.roles or '(sin rol declarado)'} "
                        f"y ocupa el slot «{comp}» ({slot.get('papel', '?')}), que solo "
                        f"acepta {', '.join(aceptados)}.\n"
                        f"    Un slot no se cubre con un alimento de rol distinto aunque "
                        f"«se parezca»: así fue como un cereal ocupó el sitio de la "
                        f"proteína en tres desayunos seguidos.",
                        c.donde,
                    )
                )
            elif item.get("rol") and item["rol"] != rol:
                out.append(
                    Infraccion(
                        "R-0",
                        f"«{item['nombre']}» dice llenar el slot «{comp}» con el rol "
                        f"«{item['rol']}» y el catálogo no le reconoce ese rol aquí "
                        f"(sería «{rol}»).",
                        c.donde,
                    )
                )
    return out


# ---------------------------------------------------------------------------
# R-1 a R-5 · Composición
# ---------------------------------------------------------------------------


def _rol_efectivo(item: dict, op: Opcion, gram: dict) -> str:
    """Con qué rol cuenta este ítem EN ESTA COMIDA.

    Un alimento puede poder cubrir varios roles, pero ocupa exactamente uno: si
    la quinua se usa como cereal, no cuenta además como proteína de esa comida.
    Sin esto, un desayuno de quinua + avena + fruta «tendría proteína».
    """
    if item.get("rol"):
        return str(item["rol"])
    slot = gram.get(item.get("componente") or "") or {}
    return op.rol_para(slot.get("roles") or []) or (op.roles[0] if op.roles else "")


def composicion(
    comidas: list[Comida], protocolo: dict, catalogo: dict
) -> list[Infraccion]:
    gram = gramatica_de(protocolo)
    principales = comidas_principales(protocolo)
    out: list[Infraccion] = []

    for c in comidas:
        pares = [(i, _buscar(catalogo, i)) for i in c.items]
        pares = [(i, o) for i, o in pares if o is not None]
        roles = {id(i): _rol_efectivo(i, o, gram) for i, o in pares}

        # --- R-1 · un solo grano por comida --------------------------------
        # Se evalúa sobre el grano base, no sobre el título de la receta. Es lo
        # que permite ver «Avena + Panqueques de avena»: dos nombres distintos y
        # un solo grano. El ancla aporta su grano y lo bloquea para el resto de
        # la comida, no al revés.
        granos: dict[str, list[str]] = defaultdict(list)
        for i, o in pares:
            if o.grano_base:
                granos[normalizar(o.grano_base)].append(i["nombre"])
        for grano, nombres in granos.items():
            if len(nombres) > 1:
                out.append(
                    Infraccion(
                        "R-1",
                        f"{len(nombres)} componentes de la misma comida comparten el "
                        f"grano «{grano}»: {', '.join(nombres)}.\n"
                        f"    Se compara el grano, no el título: dos nombres distintos "
                        f"pueden ser el mismo cereal.",
                        c.donde,
                    )
                )

        # --- base botánica repetida (la misma regla, un nivel más abajo) ----
        botanicas: dict[str, list[str]] = defaultdict(list)
        for i, o in pares:
            if o.base_botanica and o.base_botanica != "mezcla":
                botanicas[normalizar(o.base_botanica)].append(i["nombre"])
        for base, nombres in botanicas.items():
            if len(nombres) > 1 and base not in granos:
                out.append(
                    Infraccion(
                        "R-1",
                        f"{len(nombres)} componentes de la misma comida salen del mismo "
                        f"alimento («{base}»): {', '.join(nombres)}.",
                        c.donde,
                    )
                )

        if c.id not in principales:
            continue

        # --- R-2 · proteína en toda comida principal, desayuno incluido ----
        if not any(roles[id(i)] in ROLES_PROTEICOS for i, _ in pares):
            declarado = any(
                (gram.get(h["componente"]) or {}).get("papel") == "PROTEINA"
                for h in c.huecos
            )
            if not declarado:
                out.append(
                    Infraccion(
                        "R-2",
                        "comida principal sin proteína. Un desayuno de cereal + cereal "
                        "+ fruta se rechaza: de la proteína sale el material con el que "
                        "el niño crece.\n"
                        "    Si no hay candidato válido, el slot va como "
                        f"{HUECO}, nunca relleno con otro rol.",
                        c.donde,
                    )
                )

        # --- R-3 · grasa en toda comida principal --------------------------
        if not any(roles[id(i)] == "grasa" for i, _ in pares):
            declarado = any(
                (gram.get(h["componente"]) or {}).get("papel") == "GRASA"
                for h in c.huecos
            )
            if not declarado:
                out.append(
                    Infraccion(
                        "R-3",
                        "comida principal sin grasa nombrada. En un niño con riesgo de "
                        "talla baja la grasa es densidad calórica pura, y una grasa que "
                        "«viaja dentro» de otra cosa no se cuenta: se nombra y se "
                        "cuantifica, o no está.",
                        c.donde,
                    )
                )

        # --- R-4 · máximo dos componentes de demanda ≤1 --------------------
        blandos = [
            i["nombre"]
            for i, o in pares
            if o.forma_bocado and (o.demanda_oral or 0) <= 1
        ]
        if len(blandos) >= 3:
            out.append(
                Infraccion(
                    "R-4",
                    f"{len(blandos)} componentes de demanda oral ≤ N1 en la misma comida "
                    f"({', '.join(blandos)}). Una comida entera en papilla no alimenta "
                    f"el tono oral: lo deja caer.",
                    c.donde,
                )
            )

        # --- R-5 · no se apilan dos carbohidratos --------------------------
        carbos = [
            i["nombre"]
            for i, o in pares
            if roles[id(i)] in ROLES_CARBOHIDRATO and not o.es_ancla
        ]
        if len(carbos) > 1:
            out.append(
                Infraccion(
                    "R-5",
                    f"dos carbohidratos apilados: {', '.join(carbos)}. Si ENERGÍA ya está "
                    f"cubierto por un cereal, ningún otro slot puede llevar tubérculo ni "
                    f"cereal — salvo el ANCLA, que tiene el suyo propio.",
                    c.donde,
                )
            )
    return out


# ---------------------------------------------------------------------------
# R-Fe · Hierro
# ---------------------------------------------------------------------------


def hierro(
    comidas: list[Comida],
    ficha: dict,
    protocolo: dict,
    catalogo: dict,
    rasgos_excluidos: set[str] | None = None,
) -> list[Infraccion]:
    out: list[Infraccion] = []
    gram = gramatica_de(protocolo)
    horas = _horas_del_dia(protocolo)
    principales = comidas_principales(protocolo)

    for c in comidas:
        pares = [(i, _buscar(catalogo, i)) for i in c.items]
        pares = [(i, o) for i, o in pares if o is not None]
        con_hierro = [i["nombre"] for i, o in pares if o.hierro_no_hemo]
        hay_vitc = any(o.vitamina_c for _, o in pares)
        menestras = [
            i["nombre"]
            for i, o in pares
            if _rol_efectivo(i, o, gram) == "menestra"
        ]

        # R-Fe1 se juega en las comidas principales y en toda comida con
        # menestra, que son las tomas donde el hierro no hemínico entra en
        # cantidad. En un refrigerio la regla no protegería a nadie y sí
        # produciría catorce avisos por un vaso de quinua: una regla que suena
        # catorce veces al día deja de leerse, y entonces tampoco protege en la
        # comida donde sí importaba.
        #
        # R-Fe2 no se relaja igual, y la asimetría es deliberada: la vitamina C
        # que falta es una oportunidad perdida; el calcio al lado del hierro es
        # un daño activo, y se comprueba en TODAS las comidas.
        se_juega_aqui = c.id in principales

        if con_hierro and not hay_vitc and se_juega_aqui:
            out.append(
                Infraccion(
                    "R-Fe1",
                    f"lleva hierro no hemínico ({', '.join(con_hierro)}) y ninguna fuente "
                    f"de vitamina C en la misma comida. La vitamina C es lo que hace que "
                    f"ese hierro se absorba, y en otra comida no sirve.",
                    c.donde,
                )
            )

        if con_hierro:
            calcio = [i["nombre"] for i, o in pares if o.calcio_alto]
            if calcio:
                out.append(
                    Infraccion(
                        "R-Fe2",
                        f"hierro no hemínico junto a calcio ({', '.join(calcio)}). El "
                        f"calcio le pelea el hierro al grano justo en la toma donde más "
                        f"falta hace.",
                        c.donde,
                    )
                )

        if menestras and not hay_vitc and se_juega_aqui:
            out.append(
                Infraccion(
                    "R-Fe5",
                    f"menestra ({', '.join(menestras)}) sin vitamina C en la misma comida. "
                    f"Sin excepción y sin depender de R-Fe1.",
                    c.donde,
                )
            )

        # La vitamina C tiene que poder comerse. Una fruta contraindicada por
        # T-6 cumple la regla en el papel y falla en la mesa: ese caso lo caza
        # T-6 por su cuenta, pero conviene que el ID que se lee sea el del
        # hierro cuando es la única fuente de la comida.
        if (con_hierro or menestras) and se_juega_aqui:
            excluidos = set(rasgos_excluidos or set())
            fuentes = [o for _, o in pares if o.vitamina_c]
            if fuentes and excluidos and all(
                excluidos & {normalizar(r) for r in o.rasgos_visuales} for o in fuentes
            ):
                out.append(
                    Infraccion(
                        "R-Fe1",
                        "la única fuente de vitamina C de esta comida presenta un rasgo "
                        "que el perfil del niño rechaza. La regla del hierro se cumple en "
                        "el papel y falla en la mesa.",
                        c.donde,
                    )
                )

    # --- R-Fe3 · el suplemento, en la grilla -------------------------------
    suplementos = [s for s in (ficha.get("suplementos") or []) if s]
    if suplementos:
        filas = [c for c in comidas if any(i["componente"] == "suplemento" for i in c.items)]
        if not filas:
            out.append(
                Infraccion(
                    "R-Fe3",
                    f"la ficha declara {len(suplementos)} suplemento(s) y ninguno aparece "
                    f"como fila del plan.\n"
                    f"    Lo que no está en la grilla, la madre no lo lee a las siete de "
                    f"la mañana: en el primer caso real el Kid Cal vivía en el texto del "
                    f"enfoque y no en el horario.",
                )
            )
        else:
            hora_sup = _hora_inicio(filas[0].hora)
            separar = {
                normalizar(x)
                for s in suplementos
                for x in (s.get("separar_de") or [])
            }
            margen = max(
                [float(s.get("horas_separacion") or 0) for s in suplementos] or [0]
            )
            texto = " ".join(str(i.get("cantidad") or "") for c in filas for i in c.items)
            if separar and margen and not re.search(r"\d", texto):
                out.append(
                    Infraccion(
                        "R-Fe3",
                        "la fila del suplemento no escribe la separación de lácteos. La "
                        "hora sola no basta: la madre necesita leer cuántas horas antes "
                        "o después puede darle el yogurt.",
                    )
                )
            if hora_sup is not None and separar and margen:
                for c in comidas:
                    h = horas.get(c.id)
                    if h is None or abs(h - hora_sup) >= margen:
                        continue
                    choques = [
                        i["nombre"]
                        for i, o in ((i, _buscar(catalogo, i)) for i in c.items)
                        if o is not None
                        and (o.calcio_alto or normalizar(o.familia) in separar)
                    ]
                    if choques:
                        out.append(
                            Infraccion(
                                "R-Fe3",
                                f"{', '.join(choques)} cae a {abs(h - hora_sup):.1f} h del "
                                f"suplemento, y la ficha pide {margen:.0f} h de separación.",
                                c.donde,
                            )
                        )

    # --- R-Fe4 · vitamina C en ≥5 de 7 desayunos --------------------------
    if "anemia" in {normalizar(d) for d in (ficha.get("diagnosticos") or [])}:
        primera = next(
            (
                c["id"]
                for c in (protocolo.get("comidas") or [])
                if c["id"] in principales
            ),
            "desayuno",
        )
        por_semana: dict[int, list[Comida]] = defaultdict(list)
        for c in comidas:
            if c.id == primera:
                por_semana[c.semana].append(c)
        for semana, lista in sorted(por_semana.items()):
            con_vitc = sum(
                1
                for c in lista
                if any(
                    (o := _buscar(catalogo, i)) is not None and o.vitamina_c
                    for i in c.items
                )
            )
            if con_vitc < 5:
                out.append(
                    Infraccion(
                        "R-Fe4",
                        f"semana {semana}: solo {con_vitc} de {len(lista)} desayunos "
                        f"llevan vitamina C, y el déficit de hierro exige ≥ 5.\n"
                        f"    Una preferencia sin verificación se cumple 0 de 7 veces, "
                        f"que es exactamente lo que pasó.",
                    )
                )
    return out


# ---------------------------------------------------------------------------
# R-9, R-11, R-12 · Bebida, genéricos y unidades
# ---------------------------------------------------------------------------


def _ml_de(texto: str) -> int | None:
    m = re.search(r"(\d+)\s*ml", str(texto or ""), re.IGNORECASE)
    return int(m.group(1)) if m else None


def grilla(
    comidas: list[Comida], protocolo: dict, catalogo: dict, porciones: dict
) -> list[Infraccion]:
    out: list[Infraccion] = []
    gram = gramatica_de(protocolo)
    principales = comidas_principales(protocolo)

    for c in comidas:
        for item in c.items:
            op = _buscar(catalogo, item)
            cantidad = str(item.get("cantidad") or "")

            # --- R-11 · prohibido lo genérico ------------------------------
            if op is not None and op.generico:
                out.append(
                    Infraccion(
                        "R-11",
                        f"«{item['nombre']}» es un genérico: no dice qué alimento es, y "
                        f"por tanto no se puede contrastar contra una lista de "
                        f"exclusiones que nombra especies concretas.\n"
                        f"    Lo que no se puede validar no se escribe. Nombra el "
                        f"alimento: «Mandarina», no «fruta»; «Corbina», no «pescado».",
                        c.donde,
                    )
                )
            if re.fullmatch(r"\s*1\s*porci[oó]n\s*", cantidad, re.IGNORECASE):
                out.append(
                    Infraccion(
                        "R-11",
                        f"«{item['nombre']}» va servido como «1 porción», que no es una "
                        f"cantidad: no dice cuánta.",
                        c.donde,
                    )
                )

            # --- R-12 · la unidad la define el alimento --------------------
            if op is not None and op.unidad_natural:
                del_slot = str(porciones.get(item["componente"]) or "").strip()
                if del_slot and cantidad.strip() == del_slot and cantidad.strip() != op.unidad_natural:
                    out.append(
                        Infraccion(
                            "R-12",
                            f"«{item['nombre']}» lleva la unidad de la plantilla del slot "
                            f"«{item['componente']}» ({del_slot}) en vez de la suya "
                            f"({op.unidad_natural}).\n"
                            f"    Así salió impreso «Uva cortada a lo largo, ½ unidad "
                            f"mediana»: media uva no existe como porción.",
                            c.donde,
                        )
                    )
            elif op is not None and op.componente != "suplemento":
                out.append(
                    Infraccion(
                        "R-12",
                        f"«{item['nombre']}» no declara `unidad_natural` en el catálogo, "
                        f"así que su porción sale de la plantilla del slot y nadie ha "
                        f"comprobado que sea físicamente sensata.",
                        c.donde,
                        bloquea=False,
                    )
                )

            # --- O-5 · el formato seguro se imprime en la grilla -----------
            if op is not None and op.requiere_preparacion_segura:
                if normalizar_texto(op.requiere_preparacion_segura) not in normalizar_texto(cantidad):
                    out.append(
                        Infraccion(
                            "O-5",
                            f"«{item['nombre']}» solo es seguro «{op.requiere_preparacion_segura}» "
                            f"y la grilla no lo imprime. La madre lee la grilla, no el "
                            f"recetario, a las siete de la mañana.",
                            c.donde,
                        )
                    )

        # --- R-9 · el líquido no compite con la comida --------------------
        if c.id in principales:
            for item in c.items:
                op = _buscar(catalogo, item)
                if op is None or _rol_efectivo(item, op, gram) != "bebida":
                    continue
                ml = _ml_de(item.get("cantidad"))
                if ml is not None and ml > TOPE_AGUA_ML:
                    out.append(
                        Infraccion(
                            "R-9",
                            f"«{item['nombre']}» con {ml} ml supera los {TOPE_AGUA_ML} ml "
                            f"por comida principal. En un niño con ingesta baja el líquido "
                            f"desplaza calorías.",
                            c.donde,
                        )
                    )
                if "final" not in normalizar_texto(str(item.get("cantidad") or "")):
                    out.append(
                        Infraccion(
                            "R-9",
                            f"«{item['nombre']}» no dice que se ofrece al final de la "
                            f"comida. Al inicio, el líquido desplaza el sólido.",
                            c.donde,
                            bloquea=False,
                        )
                    )
    return out


# ---------------------------------------------------------------------------
# T-xx · Capa sensorial
# ---------------------------------------------------------------------------


def sensorial(
    comidas: list[Comida], ficha: dict, protocolo: dict, catalogo: dict,
    rasgos_excluidos: set[str],
) -> list[Infraccion]:
    perfil = ficha.get("perfil_sensorial") or {}
    techo_oral = perfil.get("nivel_oral_actual")
    techo_visual = perfil.get("nivel_visual_actual")
    presupuesto = protocolo.get("presupuesto_sensorial") or {}
    principales = comidas_principales(protocolo)
    sin_reto = {str(x) for x in (presupuesto.get("comidas_sin_reto") or [])}
    retos_dia = presupuesto.get("retos_dia")
    out: list[Infraccion] = []

    for c in comidas:
        pares = [(i, _buscar(catalogo, i)) for i in c.items]
        pares = [(i, o) for i, o in pares if o is not None]

        # --- T-6 · generalización aversiva --------------------------------
        for i, o in pares:
            choque = rasgos_excluidos & {normalizar(r) for r in o.rasgos_visuales}
            if choque:
                out.append(
                    Infraccion(
                        "T-6",
                        f"«{i['nombre']}» presenta {', '.join(sorted(choque))}, que es el "
                        f"rasgo del concepto aversivo declarado "
                        f"(«{perfil.get('concepto_aversivo')}»).\n"
                        f"    El niño no rechaza alimentos, rechaza rasgos: da igual que "
                        f"nadie haya nombrado este alimento nunca.",
                        c.donde,
                    )
                )

        # --- T-7 · regla de plato -----------------------------------------
        # `textura_mixta` es la propiedad sensorial más subestimada —dos
        # consistencias en el mismo bocado obligan a la boca a segregar y
        # procesar en paralelo— y la más rechazada EN HIPERSENSIBILIDAD
        # TÁCTIL-ORAL. Fuera de ese perfil no es un problema, así que la regla
        # se enciende con la ficha y no por defecto: un pan relleno es una
        # merienda normal para un escolar sin ese cuadro.
        rechaza_mixta = "tactil_oral" in {
            normalizar(x) for x in (perfil.get("hipersensibilidad") or [])
        }
        for i, o in pares:
            if o.textura_mixta and rechaza_mixta:
                out.append(
                    Infraccion(
                        "T-7",
                        f"«{i['nombre']}» mezcla dos consistencias en el mismo bocado. En "
                        f"hipersensibilidad táctil-oral es la categoría más rechazada, "
                        f"por encima de cualquier N5: cada componente en su propio "
                        f"espacio, nada encima de nada.",
                        c.donde,
                    )
                )
            if techo_visual is not None and (o.carga_visual or 0) > int(techo_visual) + 1:
                out.append(
                    Infraccion(
                        "T-7",
                        f"«{i['nombre']}» es V{o.carga_visual} y el techo visual de hoy es "
                        f"V{techo_visual}. Antes de morder, el niño tiene que inspeccionar: "
                        f"si hay algo que no puede clasificar, la comida terminó antes de "
                        f"empezar.",
                        c.donde,
                    )
                )

        # --- T-1 · techo de demanda ---------------------------------------
        if techo_oral is not None:
            for i, o in pares:
                n = o.demanda_oral
                if n is None:
                    continue
                if n > int(techo_oral) and not i.get("reto"):
                    out.append(
                        Infraccion(
                            "T-1",
                            f"«{i['nombre']}» es N{n} y el techo oral de hoy es "
                            f"N{techo_oral}. Solo el RETO puede superarlo, y solo en un "
                            f"nivel: un salto de N0 a N4 a las 7:30 con tono oral bajo es "
                            f"una comida que no se come.",
                            c.donde,
                        )
                    )
                elif i.get("reto") and n > int(techo_oral) + 1:
                    out.append(
                        Infraccion(
                            "T-4",
                            f"el reto «{i['nombre']}» sube {n - int(techo_oral)} niveles de "
                            f"demanda oral. Un reto sube exactamente uno.",
                            c.donde,
                        )
                    )

        if c.id not in principales:
            continue

        # --- T-2 · piso anti-regresión ------------------------------------
        bocados = [o for _, o in pares if o.forma_bocado]
        if bocados and not any((o.demanda_oral or 0) >= 2 for o in bocados):
            out.append(
                Infraccion(
                    "T-2",
                    "ningún componente llega a N2: toda la comida en papilla. En un niño "
                    "con tono oral bajo, esto no es neutro — lo empeora.",
                    c.donde,
                )
            )

        # --- T-3 · presupuesto por comida ---------------------------------
        tope = presupuesto.get(c.id) or {}
        if tope:
            suma = c.suma_n()
            n3 = sum(1 for o in bocados if (o.demanda_oral or 0) >= 3)
            n4 = sum(1 for o in bocados if (o.demanda_oral or 0) >= 4)
            if tope.get("suma_n") is not None and suma > int(tope["suma_n"]):
                out.append(
                    Infraccion(
                        "T-3",
                        f"la suma de demanda oral es {suma} y el presupuesto de esta "
                        f"franja es {tope['suma_n']}.",
                        c.donde,
                    )
                )
            if tope.get("max_n3") is not None and n3 > int(tope["max_n3"]):
                out.append(
                    Infraccion(
                        "T-3",
                        f"{n3} componentes ≥N3 y el máximo de esta franja es "
                        f"{tope['max_n3']}.",
                        c.donde,
                    )
                )
            if tope.get("max_n4") is not None and n4 > int(tope["max_n4"]):
                out.append(
                    Infraccion(
                        "T-3",
                        f"{n4} componentes ≥N4 y el máximo de esta franja es "
                        f"{tope['max_n4']}.",
                        c.donde,
                    )
                )

        # --- T-4 · un solo reto, y nunca en la cena -----------------------
        retos = [i["nombre"] for i in c.items if i.get("reto")]
        if len(retos) > 1:
            out.append(
                Infraccion(
                    "T-4",
                    f"{len(retos)} retos en la misma comida ({', '.join(retos)}). Como "
                    f"máximo uno: el niño llega al reto con reservas o no llega.",
                    c.donde,
                )
            )
        if retos and c.id in sin_reto:
            out.append(
                Infraccion(
                    "T-4",
                    f"reto en «{c.id}» ({', '.join(retos)}). A esa hora la fatiga oral es "
                    f"máxima y la comida tiene que terminar en éxito.",
                    c.donde,
                )
            )

    # --- T-4 · retos por día ---------------------------------------------
    if retos_dia is not None:
        por_dia: dict[tuple[int, str], int] = Counter()
        for c in comidas:
            por_dia[(c.semana, c.dia)] += sum(1 for i in c.items if i.get("reto"))
        for (semana, dia), n in sorted(por_dia.items()):
            if n > int(retos_dia):
                out.append(
                    Infraccion(
                        "T-4",
                        f"{n} retos en el día y el máximo son {retos_dia}.",
                        f"S{semana} · {dia}",
                    )
                )

    # --- T-5 · la cena pesa menos que el almuerzo -------------------------
    margen = presupuesto.get("margen_cena")
    if margen is not None:
        indice = {(c.semana, c.dia, c.id): c for c in comidas}
        for (semana, dia, cid), c in indice.items():
            if cid != "cena":
                continue
            almuerzo = indice.get((semana, dia, "almuerzo"))
            if almuerzo is None:
                continue
            if c.suma_n() > almuerzo.suma_n() - int(margen):
                out.append(
                    Infraccion(
                        "T-5",
                        f"la cena exige {c.suma_n()} de demanda oral y el almuerzo "
                        f"{almuerzo.suma_n()}: la cena tiene que quedar al menos "
                        f"{margen} por debajo.\n"
                        f"    A las 18:00 la mandíbula de un niño con tono bajo ya "
                        f"trabajó todo el día; la cena es la comida de MENOR demanda, no "
                        f"la repetición de la de mayor.",
                        c.donde,
                    )
                )

    # --- T-10 · el ancla es intocable ------------------------------------
    if (perfil.get("alimentos_ancla") or []):
        por_dia_ancla: dict[tuple[int, str], int] = Counter()
        for c in comidas:
            for _, o in ((i, _buscar(catalogo, i)) for i in c.items):
                if o is not None and o.es_ancla:
                    por_dia_ancla[(c.semana, c.dia)] += 1
        dias = {(c.semana, c.dia) for c in comidas}
        for semana, dia in sorted(dias):
            if not por_dia_ancla.get((semana, dia)):
                out.append(
                    Infraccion(
                        "T-10",
                        f"el día no lleva el alimento seguro "
                        f"({', '.join(perfil['alimentos_ancla'])}).\n"
                        f"    Retirar el ancla para forzar variedad es el error clásico y "
                        f"el más caro: sin piso de seguridad no hay desde dónde arriesgar.",
                        f"S{semana} · {dia}",
                    )
                )

    # --- T-8 · un solo cambio por vez ------------------------------------
    # Se cuenta la semana en que cada alimento nuevo aparece por PRIMERA vez.
    # Una exposición «se mantiene en el plan aunque se rechace»: si la segunda
    # semana volviera a contar, cumplir T-8 obligaría a retirar la introducción
    # justo cuando la exposición empieza a funcionar.
    primera_vez: dict[str, int] = {}
    for c in sorted(comidas, key=lambda x: x.semana):
        for i in c.items:
            if i.get("exposicion"):
                primera_vez.setdefault(str(i["nombre"]), c.semana)
    exposiciones: dict[int, set[str]] = defaultdict(set)
    for nombre, semana in primera_vez.items():
        exposiciones[semana].add(nombre)
    for semana, nombres in sorted(exposiciones.items()):
        if len(nombres) > MAX_EXPOSICIONES_SEMANA:
            out.append(
                Infraccion(
                    "T-8",
                    f"semana {semana}: {len(nombres)} alimentos nuevos a la vez "
                    f"({', '.join(sorted(nombres))}). Se introduce **uno** por semana, "
                    f"junto al ancla y en la franja de mejor disposición.\n"
                    f"    Introducir un cárnico nuevo ocho veces en dos semanas no es "
                    f"exposición graduada: es saturación, y garantiza el rechazo.",
                )
            )
    return out


# ---------------------------------------------------------------------------
# V-xx · Variedad
# ---------------------------------------------------------------------------


def variedad(
    comidas: list[Comida], protocolo: dict, catalogo: dict, ficha: dict | None = None
) -> list[Infraccion]:
    var = protocolo.get("variedad") or {}
    # Donde una intervención activa fija el contenido, la variedad no aplica:
    # exigirle dos yogures distintos a un tratamiento que funciona con uno es
    # pedirle al plan que deshaga lo que la regla I-1 protege.
    fijadas = {
        str(iv.get("franja") or "")
        for iv in ((ficha or {}).get("intervenciones_activas") or [])
        if iv.get("franja")
    }
    fijados = {
        normalizar(str(iv.get("alimento") or ""))
        for iv in ((ficha or {}).get("intervenciones_activas") or [])
        if iv.get("alimento")
    }
    tope = var.get("max_veces_misma_receta_semana")
    minimo_franja = var.get("min_preparaciones_por_franja_semana")
    out: list[Infraccion] = []

    semanas = sorted({c.semana for c in comidas})
    for semana in semanas:
        de_la_semana = [c for c in comidas if c.semana == semana]

        # --- V-1 · ninguna receta más de N veces por semana ---------------
        # El ancla está exenta: se sirve todos los días y no consume cupo.
        usos: Counter = Counter()
        for c in de_la_semana:
            for i in c.items:
                rid = i.get("receta_id")
                if not rid:
                    continue
                op = catalogo.get(rid)
                if op is not None and op.es_ancla:
                    continue
                usos[rid] += 1
        if tope:
            for rid, n in sorted(usos.items()):
                if n > int(tope):
                    out.append(
                        Infraccion(
                            "V-1",
                            f"semana {semana}: la receta «{rid}» aparece {n} veces y el "
                            f"tope es {tope}. Se cuenta sobre el plan completo, no por "
                            f"franja.",
                        )
                    )

        # --- V-2 · ninguna receta en días consecutivos --------------------
        posicion = {d: n for n, d in enumerate(DIAS)}
        dias_por_receta: dict[str, list[int]] = defaultdict(list)
        for c in de_la_semana:
            for i in c.items:
                rid = i.get("receta_id")
                op = catalogo.get(rid or "")
                if not rid or (op is not None and op.es_ancla):
                    continue
                dias_por_receta[rid].append(posicion.get(c.dia, -1))
        for rid, dias in sorted(dias_por_receta.items()):
            orden = sorted(set(dias))
            if any(b - a == 1 for a, b in zip(orden, orden[1:])):
                out.append(
                    Infraccion(
                        "V-2",
                        f"semana {semana}: la receta «{rid}» aparece en días consecutivos.",
                    )
                )

        # --- V-3 · mínimo N preparaciones distintas por franja ------------
        if minimo_franja:
            por_franja: dict[str, set[str]] = defaultdict(set)
            for c in de_la_semana:
                for i in c.items:
                    op = catalogo.get(i.get("receta_id") or "")
                    if op is not None and op.es_ancla:
                        continue
                    por_franja[c.id].add(i["nombre"])
            for franja, nombres in sorted(por_franja.items()):
                if franja in fijadas or franja == "suplemento":
                    continue
                if len(nombres) < int(minimo_franja):
                    out.append(
                        Infraccion(
                            "V-3",
                            f"semana {semana}, franja «{franja}»: solo {len(nombres)} "
                            f"preparación(es) distinta(s), y el mínimo es {minimo_franja}.",
                            bloquea=False,
                        )
                    )

        # --- V-6 · la intención sobre el contador -------------------------
        # «Preparaciones a base de huevo, 3–4 veces» no se cumple repitiendo
        # tres veces la misma receta de panqueque.
        for regla in protocolo.get("frecuencias_semanales") or []:
            fam = regla.get("familia")
            if not fam or regla.get("modo") == "relleno" or regla.get("cada_dias"):
                continue
            exigidas = int(regla.get("minimo") or regla.get("veces") or 0)
            if exigidas < 2:
                continue
            distintas = {
                i["nombre"]
                for c in de_la_semana
                for i in c.items
                if i["componente"] == regla["componente"]
                and (op := _buscar(catalogo, i)) is not None
                and op.responde_a(fam)
            }
            fijada = any(
                (op := catalogo.get(k)) is not None
                and normalizar(op.id) in fijados
                for k in catalogo
                if catalogo[k].responde_a(fam)
            )
            if 0 < len(distintas) < 2 and not fijada:
                out.append(
                    Infraccion(
                        "V-6",
                        f"semana {semana}: la categoría «{regla['componente']}/{fam}» pide "
                        f"{exigidas} apariciones y se cumplió repitiendo una sola "
                        f"preparación ({', '.join(distintas)}). Mínimo 2 distintas.",
                    )
                )
    return out


# ---------------------------------------------------------------------------
# O-xx · Operativa
# ---------------------------------------------------------------------------


def operativa(
    comidas: list[Comida], ficha: dict, protocolo: dict, catalogo: dict
) -> list[Infraccion]:
    out: list[Infraccion] = []
    contexto = ficha.get("contexto_hogar") or {}
    minutos_dia = contexto.get("minutos_cocina_dia")

    if minutos_dia:
        for semana in sorted({c.semana for c in comidas}):
            recetas = {
                i["receta_id"]
                for c in comidas
                if c.semana == semana
                for i in c.items
                if i.get("receta_id")
            }
            total = sum(
                (catalogo[r].tiempo_min for r in recetas if r in catalogo), 0
            )
            techo = int(minutos_dia) * 7
            if total > techo:
                out.append(
                    Infraccion(
                        "O-1",
                        f"semana {semana}: las recetas nuevas suman {total} min de cocina "
                        f"y el hogar declara {minutos_dia} min/día ({techo} min a la "
                        f"semana). Un plan que no se puede cocinar no es un plan.",
                    )
                )
            largas = [
                r for r in sorted(recetas)
                if r in catalogo and catalogo[r].tiempo_min > 60
            ]
            if len(largas) > 1:
                out.append(
                    Infraccion(
                        "O-1",
                        f"semana {semana}: {len(largas)} recetas de más de 60 min "
                        f"({', '.join(largas)}). Como máximo una por semana.",
                    )
                )
    return out


def coherencia_recetario(
    comidas: list[Comida], recetas_instanciadas: dict[str, dict]
) -> list[Infraccion]:
    """O-3 · Un plan y su recetario se emiten juntos o no se emiten.

    Este es el fallo que nadie había visto y el que tiene consecuencias de
    seguridad reales. El recetario decía en portada «estas son las preparaciones
    que aparecen en el plan» y era falso: cinco preparaciones de la grilla no
    tenían receta y siete recetas no aparecían en ningún día. Y no era azar —
    Compota de manzana / Compota de pera, Paletas de fresa / Paletas de mango,
    Trufas de pecana / Trufas de garbanzo, Bastones de papa / Bastones de yuca—:
    los dos documentos salieron de instanciaciones distintas de la misma base.

    La madre lee «Trufas de pecana» en el plan, busca la receta y encuentra una
    con mantequilla de maní. Pecana y maní no son el mismo fruto seco ni el
    mismo alérgeno.

    Se comprueba contando, no leyendo: mismo identificador de instancia y mismo
    nombre impreso, en las dos direcciones.
    """
    out: list[Infraccion] = []
    usadas: dict[str, set[str]] = defaultdict(set)
    for c in comidas:
        for i in c.items:
            if i.get("receta_id"):
                usadas[i["receta_id"]].add(str(i["nombre"]))

    faltan = sorted(set(usadas) - set(recetas_instanciadas))
    if faltan:
        out.append(
            Infraccion(
                "O-3",
                f"{len(faltan)} preparación(es) de la grilla no existen en el recetario: "
                + ", ".join(faltan)
                + ".\n    Un plan y su recetario se emiten juntos o no se emiten.",
            )
        )

    # El recetario se maqueta desde `recetas_usadas`, así que una instancia de un
    # control anterior que este plan ya no usa no entra al PDF y no rompe nada:
    # eso es un aviso del registro del paciente, no una incoherencia entre los
    # dos documentos. Lo que sí se comprueba aquí es el otro lado del §2.1: que
    # una misma instancia no aparezca en la grilla con dos nombres distintos.
    for rid, nombres in sorted(usadas.items()):
        if len(nombres) > 1:
            out.append(
                Infraccion(
                    "O-3",
                    f"la grilla llama de {len(nombres)} formas distintas a la misma "
                    f"instancia «{rid}»: {', '.join(sorted(nombres))}.\n"
                    f"    El mismo identificador tiene que llevar el mismo nombre impreso "
                    f"en los dos documentos: así fue como el plan dijo «Trufas de pecana» "
                    f"y el recetario imprimió una receta con maní.",
                )
            )
    return out


# ---------------------------------------------------------------------------
# I-1 · Intervenciones activas
# ---------------------------------------------------------------------------


def intervenciones(
    comidas: list[Comida], ficha: dict, catalogo: dict
) -> list[Infraccion]:
    """Lo que ya está funcionando no se toca.

    Cuando la historia dice que el estreñimiento se normalizó desde que recibe
    yogurt a diario, el yogurt dejó de ser un alimento de rotación y pasó a ser
    un tratamiento en curso. El plan lo bajó a tres veces por semana y encima le
    cambió el producto, porque no tenía dónde registrar que aquello era una
    intervención. Ninguna regla de variedad puede bajarlo.
    """
    out: list[Infraccion] = []
    dias_totales = len({(c.semana, c.dia) for c in comidas}) or 1

    for iv in ficha.get("intervenciones_activas") or []:
        que = str(iv.get("que") or "").strip()
        alimento = str(iv.get("alimento") or que)
        if not alimento:
            continue
        frecuencia = str(iv.get("frecuencia") or "diaria").strip().lower()
        franja = str(iv.get("franja") or "").strip()

        dias_con: set[tuple[int, str]] = set()
        for c in comidas:
            if franja and c.id != franja:
                continue
            for i in c.items:
                op = catalogo.get(i.get("receta_id") or "") or _buscar(catalogo, i)
                if op is not None and (
                    normalizar(op.id) == normalizar(alimento)
                    or normalizar(op.nombre) == normalizar(alimento)
                ):
                    dias_con.add((c.semana, c.dia))

        if frecuencia.startswith("diar") and len(dias_con) < dias_totales:
            out.append(
                Infraccion(
                    "I-1",
                    f"la intervención activa «{que}» ({iv.get('para', 'sin motivo escrito')}) "
                    f"aparece {len(dias_con)} de {dias_totales} días, y está declarada "
                    f"como diaria y NO_MODIFICAR.\n"
                    f"    Se modificó un tratamiento en curso que estaba funcionando. Si "
                    f"el cambio es deliberado, lo decide Paty y se escribe en la ficha; el "
                    f"motor no lo hace por su cuenta.",
                )
            )
        elif not dias_con:
            out.append(
                Infraccion(
                    "I-1",
                    f"la intervención activa «{que}» no aparece en ningún día del plan.",
                )
            )
    return out


# ---------------------------------------------------------------------------
# Entrada única
# ---------------------------------------------------------------------------


def evaluar(
    plan: dict,
    ficha: dict,
    protocolo: dict,
    catalogo: dict[str, Opcion],
    recetas_instanciadas: dict[str, dict] | None = None,
    rasgos_excluidos: set[str] | None = None,
) -> list[Infraccion]:
    """Todas las reglas sobre este plan, en orden de ID."""
    comidas = leer_comidas(plan, catalogo)
    porciones = ficha.get("porciones") or {}
    infracciones: list[Infraccion] = []
    infracciones += r0_tipado(comidas, protocolo, catalogo)
    infracciones += composicion(comidas, protocolo, catalogo)
    infracciones += hierro(comidas, ficha, protocolo, catalogo, rasgos_excluidos)
    infracciones += grilla(comidas, protocolo, catalogo, porciones)
    infracciones += sensorial(
        comidas, ficha, protocolo, catalogo, rasgos_excluidos or set()
    )
    infracciones += variedad(comidas, protocolo, catalogo, ficha)
    infracciones += operativa(comidas, ficha, protocolo, catalogo)
    infracciones += intervenciones(comidas, ficha, catalogo)
    if recetas_instanciadas is not None:
        infracciones += coherencia_recetario(comidas, recetas_instanciadas)
    return infracciones
