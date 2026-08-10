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
reglas_exclusion: reglas_6_11_anos.md   # archivo en /reglas_exclusion/
descripcion: >
  Para qué caso clínico existe este protocolo.
```

El ensamblador elige protocolo por `edad_min_meses`/`edad_max_meses`, salvo que la Fase 1 fuerce otro por diagnóstico (ej.: un niño de 3 años con selectividad severa puede requerir un protocolo específico en vez del de su edad).

### `comidas`

Define la anatomía del día. Cada comida declara qué componentes la forman.

```yaml
comidas:
  - id: desayuno
    nombre: Desayuno
    hora: "7:30 – 8:30"
    componentes: [cereal, acompanante, fruta]
```

Los `id` de componente son las llaves que verá la plantilla HTML. Si un componente no aplica un día, el renderizador lo omite y el texto fluye: no quedan huecos.

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
  estrenimiento:
    priorizar_aporta: [fibra, grasas_saludables]
```

Las llaves (`anemia`, `estrenimiento`) deben coincidir con los diagnósticos normalizados que produce la Fase 1.

---

## Cómo se conecta con la biblioteca

El ensamblador cruza dos cosas:

- del **protocolo**: qué componente toca hoy y con qué frecuencia
- de la **biblioteca** (front-matter de P1 v4.0): `momento`, `edad_min_meses`, `alergenos_presentes`, `aporta`

Por eso `momento` y `aporta` en P1 no son decorativos: son la superficie de contacto entre los dos sistemas. Si una receta declara mal su `momento`, el plan sale mal aunque la receta sea perfecta.

---

## Campos que el motor todavía no ejecuta

`ablactancia_6_meses.yaml` declara `marco_diario`, `introduccion_progresiva`,
`progresion_textura` y `exclusiones_duras`. El ensamblador los conserva y los
imprime donde corresponde, pero **aún no los hace cumplir**: la introducción
progresiva de alérgenos y la rotación de texturas siguen siendo criterio de Paty.
Están escritos ya para que el día que se implementen no haya que rehacer el archivo.

## Advertencia clínica

`escolar_6_11.yaml` es una transcripción fiel de la estructura que Paty ya tenía escrita en `fase_3_ensamblaje.md`. Sus frecuencias son suyas.

`ablactancia_6_meses.yaml` **es un esqueleto**, no una recomendación. La anatomía del archivo es correcta; los números son marcadores de posición razonables tomados de guías generales. **Paty debe revisarlos y corregirlos antes del primer uso.** Los campos marcados con `# REVISAR` son los que no debe dar por buenos.

Añadir un protocolo nuevo es copiar uno existente y cambiar los datos. No requiere tocar código ni prompts.
