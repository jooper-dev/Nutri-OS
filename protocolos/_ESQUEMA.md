# Esquema de Protocolos — Nutri-OS

Un **protocolo** es la estructura de un tipo de plan alimentario expresada como datos, no como prompt.

En el sistema anterior esta información vivía dentro de `fase_3_ensamblaje.md`: cereales andinos, menestras 3x, rotación de carnes. Eso servía para un solo tipo de plan y bloqueaba todos los demás. Aquí cada tipo de plan es un archivo `.yaml` independiente, y el ensamblador los lee sin que nadie toque un prompt.

**Regla de oro:** si un dato se cuenta, se compara o se rota, va en el protocolo y lo ejecuta código. Nunca en un prompt.

---

## Estructura del archivo

### Cabecera

```yaml
id: escolar_6_11              # nombre del archivo, sin extensión
nombre: Escolar 6–11 años     # etiqueta legible
edad_min_meses: 72            # rango de aplicación, SIEMPRE en meses
edad_max_meses: 143
descripcion: >
  Para qué caso clínico existe este protocolo.
```

La Fase 1 propone el protocolo, y el código comprueba que la edad caiga en su rango; si no cae y la ficha no declara una justificación, el pipeline se detiene. Lo comprueban `motor/validar.py` —como error bloqueante— y `motor/revisar.py`, sobre todas las fichas que ya estén en `pacientes/`.

**Solo se admiten las claves de primer nivel que el motor consume.** La lista cerrada vive en `motor/comun.py` (`CLAVES_PROTOCOLO_CONSUMIDAS`, `CLAVES_PROTOCOLO_SOLO_AVISO`, `CLAVES_PROTOCOLO_DOCUMENTALES`) y `motor/revisar.py` falla si un protocolo trae cualquier otra: una clave que nadie lee hace creer que la regla se aplica.

### `comidas`

Define la anatomía del día. Cada comida declara qué componentes la forman.

```yaml
comidas:
  - id: desayuno
    nombre: Desayuno
    hora: "7:30 – 8:30"
    componentes: [cereal, acompanante, fruta]
  - id: media_tarde
    nombre: Media tarde
    hora: "3:30 – 4:30"
    componentes: [base]
    activo_desde_semana: 3      # opcional; por defecto 1
```

Los `id` de componente son las llaves que verá la plantilla HTML. Si un componente no aplica un día, el renderizador lo omite y el texto fluye: no quedan huecos.

`activo_desde_semana` es para las comidas que no arrancan el primer día: antes de esa semana la comida no existe, no se le reparten ranuras y no se imprime. El validador bloquea el plan si aparece antes. Hoy ningún protocolo del repositorio lo usa.

### `frecuencias_semanales`

El corazón del sistema. Cada regla es una restricción que el ensamblador **garantiza por construcción**, no que verifica después.

```yaml
frecuencias_semanales:
  - componente: menestra
    en: [almuerzo, cena]
    veces: 3
    modo: exacto          # exacto | minimo | maximo
```

`modo: exacto` significa exacto. Si el protocolo dice 3 y el plan trae 4, es un bug del ensamblador, no un descuido del modelo — y el validador lo detiene.

### `rotaciones`

Reparto de un componente entre alternativas dentro de la semana.

```yaml
rotaciones:
  - componente: cereal
    en: [desayuno]
    reparto: {avena: 2, canihua: 2, harinas: 2, hojuelas: resto}
```

`en` acota el reparto a unas comidas concretas: la misma rotación puede repetirse
para almuerzo y para cena con cupos distintos. Las claves de `reparto` son
**familias** (`familia` en el front-matter de la receta o del alimento base);
si un alimento base no declara familia, su propio `id` hace de familia.

La suma de números enteros no puede exceder las ranuras del ámbito. Solo un valor
puede ser `resto`.

### `reglas_acopladas`

Condiciones del tipo "si aparece A, tiene que aparecer B".

```yaml
reglas_acopladas:
  - si: menestra
    entonces: fruta_vitc
    ambito: misma_comida   # misma_comida | mismo_dia
    razon: absorción de hierro no hemínico
```

`razon` no la lee el código: se imprime en el reporte de QA para que Paty entienda por qué el sistema tomó una decisión.

### `variedad`

```yaml
variedad:
  no_repetir_dia_completo: true    # entre semanas
  max_veces_misma_receta_semana: 2
  min_recetas_distintas_semana: 12
```

### `preferencias_clinicas`

Ajustes que el ensamblador aplica según el diagnóstico extraído en Fase 1. Sesga la selección; no inventa reglas nuevas.

```yaml
preferencias_clinicas:
  anemia:
    priorizar_aporta: [hierro, vitamina_c]
    subir_frecuencia: {componente: menestra, a: 4}
  aplv:
    exclusiones_extra: [lacteos]
  estrenimiento:
    priorizar_aporta: [fibra, grasas_saludables]
    nota_qa: revisar aporte hídrico total del plan
```

Las llaves (`anemia`, `estrenimiento`) deben coincidir con los diagnósticos normalizados que produce la Fase 1. Los cuatro ajustes que el motor aplica de verdad son:

- `priorizar_aporta` — sesga la selección hacia las opciones que aportan esos nutrientes.
- `subir_frecuencia: {componente, familia (opcional), a}` — sube el `veces` de esa regla de `frecuencias_semanales`. Solo sube, nunca baja. Si no hay ninguna regla que corresponda, el ensamblador se detiene: un ajuste clínico declarado que no se aplica es peor que no declararlo.
- `exclusiones_extra: [etiquetas]` — filtran **exactamente igual que una alergia de la ficha**, y caen bajo la misma comprobación: una etiqueta que el catálogo no conoce bloquea el plan en vez de dejarlo pasar sin filtrar nada.
- `nota_qa` — texto que se copia al reporte de QA.

Cualquier otra clave produce un aviso en el reporte diciendo que el motor no la aplica. La lista de las implementadas está en `motor/validar.py` (`IMPLEMENTADAS`); ampliarla sin implementar la funcionalidad apaga el aviso que protege la revisión clínica.

### `decisiones_pendientes`

Lista de cadenas. Lo que no resuelve ninguna guía pública y sí resuelve Paty: sus preferencias de práctica. El validador las repite en cada reporte hasta que se cierren, y van todas aquí para que no acaben como comentarios sueltos por el archivo.

```yaml
decisiones_pendientes:
  - >
    Una misma receta puede repetirse hasta 4 veces por semana. ¿Cuántas? (un número)
```

---

## Cómo se conecta con la biblioteca

El ensamblador cruza dos cosas:

- del **protocolo**: qué componente toca hoy y con qué frecuencia
- de la **biblioteca** (front-matter de P1 v4.0): `momento`, `edad_min_meses`, `alergenos_presentes`, `aporta`

Por eso `momento` y `aporta` en P1 no son decorativos: son la superficie de contacto entre los dos sistemas. Si una receta declara mal su `momento`, el plan sale mal aunque la receta sea perfecta.

---

## Campos que el motor todavía no ejecuta

`introduccion_progresiva`, `progresion_textura` y `exclusiones_duras` se declaran
en `ablactancia_6_meses.yaml` y el motor **no los hace cumplir**: la introducción
progresiva de alérgenos y la rotación de texturas siguen siendo criterio de Paty.
El validador los repite como aviso en cada reporte para que consten en la revisión
clínica y nadie los dé por aplicados. La lista está en `motor/comun.py`
(`CLAVES_PROTOCOLO_SOLO_AVISO`).

`/reglas_exclusion/` es **material de lectura humana**: evidencia y restricciones
por edad, escritas en prosa. Ningún módulo del motor lo lee, y los protocolos ya
no lo referencian. Lo que tiene que filtrar de verdad vive en
`datos/alimentos_base.yaml` (`edad_min_meses`, `alergenos`, `nunca_recomendar`),
que es lo que el código sí puede comprobar.

## Advertencia clínica

`escolar_6_11.yaml` es una transcripción fiel de la estructura que Paty ya tenía escrita en `fase_3_ensamblaje.md`. Sus frecuencias son suyas.

`ablactancia_6_meses.yaml` lleva la fuente pública citada en la línea de cada valor que la tiene (OMS 2023 para legumbres, MINSA/INS Perú para número de comidas y consistencia). Lo que sigue siendo criterio de Paty está reunido en su bloque `decisiones_pendientes`, y el validador lo repite en cada reporte.

Añadir un protocolo nuevo es copiar uno existente y cambiar los datos. No requiere tocar código ni prompts.
