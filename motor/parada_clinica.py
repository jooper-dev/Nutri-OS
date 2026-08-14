"""
Capa de parada clínica — Nutri-OS

El validador comprueba que el plan cumple el protocolo. Esto comprueba otra
cosa: que **este caso deba tener un plan**.

Son preguntas distintas y el sistema solo sabía hacer la primera. En el primer
caso real el paciente tenía riesgo de talla baja y selectividad severa con
cuatro de las seis señales de derivación, y salió un plan de dos semanas
aritméticamente impecable sin una palabra de eso arriba del informe. El plan no
estaba mal calculado; es que había algo más urgente que calcular.

Cinco criterios. Cuatro paran y uno avisa:

  PARADA   falla de medro — peso que cae o se estanca con la talla subiendo
  PARADA   alérgeno sospechado y sin documentar
  PARADA   diagnóstico que el protocolo elegido no sabe tratar
  PARADA   edad fuera del rango de TODOS los protocolos disponibles
  AVISO    selectividad extrema, con derivación a terapia de alimentación

Por qué el último no para: la selectividad extrema no invalida el plan —de
hecho el plan es parte del tratamiento—, pero sí cambia lo primero que Paty
tiene que leer. Un aviso destacado arriba del informe es la respuesta correcta;
bloquear le quitaría a la familia un plan que sí necesita.

Nada de esto decide QUÉ come el niño. Decide si el sistema puede firmar un plan
sin que un humano mire primero.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from comun import DIR_PROTOCOLOS, normalizar

# Por debajo de esto, el repertorio aceptado deja de ser «come poca variedad» y
# pasa a ser un criterio de derivación reconocido en selectividad alimentaria.
# El número sale de la lista de señales de PC_CLINICO.md («orientativamente,
# menos de 20»), y es orientativo ahí y aquí: por eso avisa y no bloquea.
REPERTORIO_ESTRECHO = 20


class Hallazgo:
    """Un criterio que se disparó. `bloquea` decide si para el pipeline."""

    def __init__(self, clave: str, bloquea: bool, mensaje: str) -> None:
        self.clave = clave
        self.bloquea = bloquea
        self.mensaje = mensaje

    def __repr__(self) -> str:  # pragma: no cover — depuración
        return f"<Hallazgo {self.clave} {'BLOQUEA' if self.bloquea else 'aviso'}>"


def _serie_antropometrica(ficha: dict) -> list[dict]:
    """Los controles anteriores más el actual, en orden cronológico.

    `antropometria_previa` la escribe la Fase 1 leyendo los controles que haya
    en las fuentes. Si no hay ninguno —primera consulta—, la serie tiene un solo
    punto y no se puede juzgar una tendencia, que es exactamente lo que se
    reporta en vez de inventarse una.
    """
    serie = [dict(p) for p in (ficha.get("antropometria_previa") or [])]
    serie.append(
        {
            "fecha": str(ficha.get("fecha") or "control actual"),
            "peso_kg": ficha.get("peso_kg"),
            "talla_cm": ficha.get("talla_cm"),
            "actual": True,
        }
    )
    return [p for p in serie if p.get("peso_kg") is not None]


def _falla_de_medro(ficha: dict) -> Hallazgo | None:
    """Peso que baja o no se mueve mientras la talla sigue subiendo.

    Es el patrón que distingue al niño que está creciendo despacio del niño que
    ha dejado de acumular masa, y no se ve en una sola medición: hace falta la
    serie. Un plan alimentario no es la respuesta a esto por sí solo, así que el
    sistema no lo firma sin que Paty lo mire.
    """
    serie = _serie_antropometrica(ficha)
    if len(serie) < 2:
        return None

    primero, ultimo = serie[0], serie[-1]
    delta_peso = float(ultimo["peso_kg"]) - float(primero["peso_kg"])

    tallas = [p for p in serie if p.get("talla_cm") is not None]
    delta_talla = (
        float(tallas[-1]["talla_cm"]) - float(tallas[0]["talla_cm"])
        if len(tallas) >= 2
        else None
    )

    if delta_peso > 0.2:
        return None
    # Peso perdido o estancado. Si además la talla sube, el niño está estirando
    # sin material con el que hacerlo, que es el cuadro que hay que parar.
    if delta_talla is not None and delta_talla <= 0.5 and delta_peso > -0.3:
        return None

    linea = " → ".join(
        f"{p.get('fecha', '?')}: {p['peso_kg']} kg"
        + (f" / {p['talla_cm']} cm" if p.get("talla_cm") is not None else "")
        for p in serie
    )
    tendencia = "perdió peso" if delta_peso < 0 else "no ganó peso"
    con_talla = (
        f" mientras la talla subía {delta_talla:.1f} cm"
        if delta_talla is not None and delta_talla > 0.5
        else ""
    )
    return Hallazgo(
        "falla_de_medro",
        True,
        f"FALLA DE MEDRO: entre el primer control y el último el paciente "
        f"{tendencia} ({delta_peso:+.2f} kg){con_talla}.\n"
        f"    Serie: {linea}\n"
        f"    Un peso que cae o se estanca con la talla en aumento no es un problema "
        f"de menú: es un cuadro que se estudia antes de dar un plan, y el sistema no "
        f"lo firma solo.\n"
        f"    Qué hacer: revísalo con Paty. Si la serie está mal transcrita, corrige "
        f"«antropometria_previa» en la ficha. Si el cuadro es real y ella decide que "
        f"el plan procede igual, que lo declare en «parada_clinica_revisada» de la "
        f"ficha con su motivo, y el pipeline continúa.",
    )


def _alergia_sin_documentar(ficha: dict) -> Hallazgo | None:
    """Una alergia mencionada de pasada y que nadie ha confirmado con un papel.

    «Le cae mal la leche» no es un diagnóstico, pero tampoco es nada: es una
    sospecha, y el sistema tiene dos formas de equivocarse con ella. Si la
    ignora, el niño come el alérgeno. Si la trata como confirmada, le retira un
    grupo entero de alimentos a un niño que quizá no lo necesita —y en un caso
    de talla baja eso hace daño de verdad.

    Así que no elige: para y pide el documento.
    """
    sospechadas = [str(a).strip() for a in (ficha.get("alergias_sospechadas") or []) if str(a).strip()]
    if not sospechadas:
        return None
    declaradas = {normalizar(a) for a in (ficha.get("alergias") or [])}
    pendientes = [a for a in sospechadas if normalizar(a) not in declaradas]
    if not pendientes:
        return None
    return Hallazgo(
        "alergia_sin_documentar",
        True,
        f"ALERGIA SOSPECHADA SIN DOCUMENTAR: {', '.join(pendientes)}.\n"
        f"    El material del caso la menciona y no hay ningún documento que la "
        f"confirme ni que la descarte.\n"
        f"    No se sigue por los dos lados: darle el alimento a un niño que "
        f"reacciona es un evento adverso, y retirárselo a un niño que no reacciona "
        f"le quita un grupo entero de alimentos sin motivo.\n"
        f"    Qué hacer: consigue la prueba (IgE específica, prick test o informe del "
        f"alergólogo) y anótala en «procedencia». Si Paty la confirma por clínica, "
        f"pásala a «alergias» y quítala de «alergias_sospechadas»; si la descarta, "
        f"quítala de las dos listas. En ambos casos el pipeline continúa.",
    )


def _diagnostico_sin_protocolo(ficha: dict, protocolo: dict) -> Hallazgo | None:
    """Un diagnóstico que el protocolo elegido no sabe tratar.

    El motor solo aplica los diagnósticos que el protocolo declara en
    `preferencias_clinicas`. Uno que no esté ahí no falla en ninguna parte: el
    plan sale entero, correcto, y sin el ajuste. Escribir «anemia» en la ficha y
    que no pase nada es peor que no escribirlo, porque quien lea la ficha da el
    ajuste por hecho.
    """
    declarados = set((protocolo.get("preferencias_clinicas") or {}).keys())
    dx = [str(d) for d in (ficha.get("diagnosticos") or []) if str(d) != "ninguno"]
    huerfanos = [d for d in dx if d not in declarados]
    if not huerfanos:
        return None
    return Hallazgo(
        "diagnostico_sin_protocolo",
        True,
        f"DIAGNÓSTICO SIN PROTOCOLO QUE LO SOPORTE: {', '.join(huerfanos)}.\n"
        f"    El protocolo «{protocolo.get('id')}» no declara «preferencias_clinicas» "
        f"para {'ese diagnóstico' if len(huerfanos) == 1 else 'esos diagnósticos'}, así "
        f"que el motor no aplicaría ningún ajuste y el plan saldría igual que el de un "
        f"niño sin ese diagnóstico — sin decirlo.\n"
        f"    Diagnósticos que este protocolo sí trata: "
        f"{', '.join(sorted(declarados)) or '(ninguno)'}.\n"
        f"    Qué hacer: añade el bloque de ese diagnóstico a «preferencias_clinicas» "
        f"en protocolos/{protocolo.get('id')}.yaml, o corrige la etiqueta en la ficha "
        f"si el diagnóstico se llama de otra forma en el sistema.",
    )


def protocolos_que_cubren(edad_meses: int) -> list[str]:
    """Los protocolos cuyo rango declarado incluye esa edad."""
    cubren: list[str] = []
    for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
        try:
            d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        lo, hi = d.get("edad_min_meses"), d.get("edad_max_meses")
        if lo is None or hi is None:
            continue
        if int(lo) <= int(edad_meses) <= int(hi):
            cubren.append(str(d.get("id") or ruta.stem))
    return cubren


def _franja_sin_protocolo(ficha: dict) -> Hallazgo | None:
    """La edad del paciente no cae en el rango de ningún protocolo.

    Y aquí el sistema se niega limpiamente, sin proponer el protocolo más
    cercano. La tentación es obvia —«20 meses, tira de ablactancia, que es lo
    que más se le parece»— y es justo lo que no se puede hacer: un protocolo
    equivocado no falla, deforma en silencio todos los planes de esa franja.
    Una receta mala se ve y se prueba; un protocolo mal elegido no se ve.

    Los protocolos los escribe Paty. Lo único que hace el sistema es decir que
    falta.
    """
    edad = ficha.get("edad_meses")
    if edad is None:
        return None
    if protocolos_que_cubren(int(edad)):
        return None

    rangos = []
    for ruta in sorted(DIR_PROTOCOLOS.glob("*.yaml")):
        try:
            d = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if d.get("edad_min_meses") is None:
            continue
        rangos.append(
            f"{d.get('id')} ({d['edad_min_meses']}–{d.get('edad_max_meses')} m)"
        )

    return Hallazgo(
        "franja_sin_protocolo",
        True,
        f"FRANJA ETARIA NO SOPORTADA: el paciente tiene {edad} meses y ningún "
        f"protocolo del repositorio cubre esa edad.\n"
        f"    Rangos disponibles: {'; '.join(rangos) or '(ninguno)'}.\n"
        f"    No se propone «el más cercano» a propósito. Un protocolo equivocado no "
        f"da error: da un plan entero, coherente y con las frecuencias y las porciones "
        f"de otra edad. Una receta mala se ve al probarla; un protocolo mal elegido "
        f"deforma en silencio todos los planes de la franja.\n"
        f"    Qué hacer: el protocolo de esta franja lo escribe Paty, copiando uno "
        f"existente en protocolos/ y ajustando frecuencias, porciones y horarios. "
        f"Hasta entonces este caso no tiene plan automático.",
    )


def _selectividad_extrema(ficha: dict) -> Hallazgo | None:
    """Repertorio muy estrecho: avisa fuerte, no bloquea.

    El plan sigue siendo parte del tratamiento, así que se entrega. Lo que
    cambia es qué es lo primero que Paty lee en el informe.
    """
    dx = {normalizar(d) for d in (ficha.get("diagnosticos") or [])}
    repertorio = ficha.get("repertorio_aceptado") or []
    n = len(repertorio)
    if "selectividad" not in dx and not (repertorio and n < REPERTORIO_ESTRECHO):
        return None

    cuenta = (
        f"El repertorio aceptado que recoge la ficha son {n} alimento(s)"
        + (f", por debajo de los {REPERTORIO_ESTRECHO} que se usan como referencia"
           if n < REPERTORIO_ESTRECHO else "")
        + "."
        if repertorio
        else "La ficha no enumera el repertorio aceptado, así que su amplitud no se "
             "ha podido medir; conviene contarlo en consulta."
    )

    return Hallazgo(
        "selectividad_extrema",
        False,
        f"SELECTIVIDAD ALIMENTARIA — VALORAR DERIVACIÓN. {cuenta}\n"
        f"    Un plan no amplía por sí solo un repertorio estrecho, y cuando debajo "
        f"hay un componente sensorial o motor —bajo tono oral, fatiga masticatoria, "
        f"aversión textural sostenida— la parte que el menú no alcanza es "
        f"precisamente la que mantiene el cuadro.\n"
        f"    Corresponde valorar derivación a terapia de alimentación (terapia "
        f"ocupacional o fonoaudiología con formación en alimentación pediátrica). "
        f"La decisión es de Paty; esto solo se asegura de que no se le pase.",
    )


def revisar(ficha: dict, protocolo: dict | None = None) -> list[Hallazgo]:
    """Todos los criterios, en orden de gravedad. Función pura."""
    hallazgos: list[Hallazgo] = []
    for h in (
        _franja_sin_protocolo(ficha),
        _falla_de_medro(ficha),
        _alergia_sin_documentar(ficha),
        _diagnostico_sin_protocolo(ficha, protocolo) if protocolo else None,
        _selectividad_extrema(ficha),
    ):
        if h:
            hallazgos.append(h)

    # Una parada que Paty ya miró y decidió seguir deja de parar, pero no
    # desaparece: baja a aviso y se sigue imprimiendo. La firma clínica es suya;
    # lo que el sistema no permite es que la decisión no exista.
    revisadas = {normalizar(k) for k in (ficha.get("parada_clinica_revisada") or {})}
    for h in hallazgos:
        if h.bloquea and normalizar(h.clave) in revisadas:
            motivo = (ficha.get("parada_clinica_revisada") or {}).get(h.clave)
            h.bloquea = False
            h.mensaje = (
                f"{h.mensaje.splitlines()[0]}\n"
                f"    REVISADO POR PATY, el pipeline continúa: {motivo}"
            )
    return hallazgos


def bloqueantes(hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    return [h for h in hallazgos if h.bloquea]
