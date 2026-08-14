# Estado del proyecto — Nutri-OS

*Documento de traspaso. Léelo entero antes de tocar nada. Recoge decisiones ya tomadas y sus razones, para que no haya que rediscutirlas.*

Última actualización: 13 de agosto de 2026, tras el **primer caso real** (Haziel
S. G. F., 4 a 6 m) y la tanda de correcciones que destapó.

---

## 0. Lo que cambió tras el primer caso real

El caso salió con un 7 sobre 10 de la nutricionista. Cinco cambios de fondo:

1. **Hay un paso 0: `motor/ingesta.py`.** Las fuentes se convierten a texto
   **antes** de que ningún modelo las lea, y se inventaría qué llegó, página a
   página. Las 88 páginas y 56 MB del PDF de recomendaciones ahora son 25 KB de
   texto repartido en cinco archivos, y las 36 páginas sin capa de texto salen
   marcadas como **pendientes de lectura visual** en vez de perderse en silencio.
   El pipeline lee `fuentes/`; `fuentes_originales/` no se abre nunca.

2. **La biblioteca guarda BASES, no recetas.** Una base es técnica + esqueleto +
   reglas de seguridad, y **no se imprime jamás**. Lo que va al recetario es la
   base instanciada contra ese niño, y vive en `pacientes/<paciente>/recetas/`.
   El error del caso real no fue tener una receta de pan con palta: fue servirla
   sin adaptar a un niño cuya anamnesis dice «no pan, ni pan con palta». Lo que
   se acumula entre pacientes es la técnica; el plato, no.

3. **Capa de parada clínica** (`motor/parada_clinica.py`). Cuatro criterios paran
   el pipeline —falla de medro, alérgeno sospechado sin documentar, diagnóstico
   sin protocolo que lo soporte, edad fuera de todos los protocolos— y uno avisa
   destacado: selectividad extrema, con derivación a valorar. El caso real tenía
   cuatro de las seis señales de derivación y el sistema no destacó ninguna.

4. **Los alérgenos declaran presencias, no solo ausencias.** Antes las etiquetas
   solo decían «sin gluten · sin huevo», con tope de tres, y faltaban en la mitad
   de las recetas: unas barritas con mantequilla de maní no lo decían en ninguna
   parte y la milanesa salía muda. Ahora toda receta lleva bloque, sin tope, y el
   validador **impide renderizar** si no cuadra con su lista de ingredientes.

5. **El informe no recorta información clínica por lo que haya en catálogo.** El
   «no consume» salía con cuatro alimentos que resultaron ser, exactamente, los
   únicos rechazos que además existían en la biblioteca. Ahora sale íntegro.

Y un puñado de bugs de comparación que se descubrieron probando lo anterior:
`normalizar` no trataba el guion como separador (un rechazo no excluía la base
que lo llevaba en el id), la puntuación rompía la comparación de palabra
completa, y faltaba tolerancia de plural. Los topes que impiden que `res`
excluya `Fresa` siguen en pie: hay prueba corrida.

---

## 1. Qué es esto y para quién

Sistema de generación de planes alimentarios pediátricos para **GrowKids**, la consulta de la Nut. Patricia López (Paty), nutricionista pediátrica en Trujillo, Perú.

El problema que resuelve: cada plan personalizado le costaba horas de trabajo manual. El objetivo no es automatizar su criterio clínico, es quitarle el trabajo mecánico que hay alrededor.

**Dos personas usan el repositorio, y hacen cosas distintas:**

- **Danny** (desarrollador) construye. Trabaja en Claude Code, hace commits, toca protocolos y motor.
- **Paty** (nutricionista) opera. Trabaja en Claude Cowork, nunca ve una terminal, procesa pacientes.

Si estás leyendo esto en una sesión de desarrollo, eres el primer caso.

---

## 2. El principio que sostiene todo

| Va a un modelo | Va a código |
|---|---|
| Leer el caso clínico | Contar frecuencias |
| Escribir y auditar recetas | Filtrar por alergias, edad y textura |
| Redactar la voz de la marca | Validar el plan |
| Describir el plato para la foto | Armar el prompt de imagen |
| — | Maquetar los PDF |

**Nunca cuentes tú.** Si te descubres verificando "¿hay tres menestras esta semana?", estás haciendo el trabajo del validador y lo vas a hacer peor. Ejecuta el script.

La versión anterior de este proyecto falló exactamente por lo contrario: cinco fases encadenadas donde un modelo contaba, se auditaba a sí mismo y maquetaba. Producía planes que parecían bien y no lo estaban.

---

## 3. Anatomía

```
CLAUDE.md          orquestador: las fases y dónde pararse
GUIA_PATY.md       manual de uso, sin nada técnico
ESTADO.md          este archivo

prompts/           PC_CLINICO (F1) · P1_RECETAS v4.3 (F3)
protocolos/        un .yaml por tipo de plan — estructura y frecuencias
reglas_exclusion/  restricciones por edad, con evidencia
biblioteca/        una receta por archivo; crece con el uso
  prompts_imagen/  prompt de foto por receta (generado)
  imagenes/        la foto de cada receta (una vez y para siempre)
datos/             alimentos base · biblioteca de fotografía · consultas.csv
motor/             revisar · ensamblar · validar · fotos · generar_imagenes
                   render · registrar · metricas · migrar_textura · correr
pacientes/         casos reales — FUERA de git
salidas/           metricas.html
```

**Fases:** F0 entrada por chat (el sistema crea la carpeta y guarda el material) → F1 lectura clínica (modelo) → F2 ensamblaje (código) → F3 recetas nuevas (modelo, contexto limpio por receta) → F4 validación (código) → F5 render, **fotografía incluida** (código) → **F6 Puerta de Paty (humano, sobre los PDF)** → F7 registro.

---

## 4. Decisiones tomadas — no las revisites sin motivo nuevo

**Los PDF se generan en local con WeasyPrint, no en Canva ni Google Slides.** Un plan de 4 semanas son ~1.200 etiquetas de texto; reemplazarlas una por una es frágil venga de donde venga. Efecto secundario importante: el sistema ya no usa Google Workspace para nada, así que no hay OAuth ni tokens que caduquen ni credenciales que filtrar.

**La biblioteca de recetas es un caché, no un catálogo cerrado.** No se digitaliza nada por adelantado. Cuando falta una receta, P1 la crea y se guarda; la siguiente paciente que la necesite la tiene gratis. A los pocos meses la mayoría de los planes salen de recetas ya validadas.

**Las frecuencias del protocolo se garantizan por construcción, no se verifican después.** El ensamblador reserva primero las ranuras que las reglas exigen y solo después rellena. Un plan que viola una frecuencia es un bug del motor, no un descuido.

**El validador es independiente y determinista.** Relee protocolo y ficha por su cuenta y recuenta desde cero. Sustituye a la antigua "self-QA" donde un modelo se auditaba a sí mismo.

**La Puerta de Paty no se salta, pero va DESPUÉS del render.** *(Cambiado el 11/08/2026; antes iba antes.)* Paty no lee markdown, así que pedirle que aprobara `reporte_qa.md` antes de generar los PDF era pedirle que revisara un documento que no puede leer: una puerta de mentira. El orden es validar → renderizar → ella revisa los PDF → si pide cambios, se corrige en el origen y se regenera. Lo que no cambió es el bloqueo automático: `render.py` se niega a trabajar si el validador marcó BLOQUEADO, y esa sí es una puerta que cierra sola. La firma clínica sigue siendo suya, ahora sobre el documento terminado.

**Un tipo de plan nuevo es un archivo .yaml nuevo en `protocolos/`, nunca un parche al ensamblador.**

**El protocolo nombra alimentos en dos niveles: el cajón (`familia`) o el alimento (`id`).** `{camote: 2, tuberculo: 2, grano: resto}` es una rotación válida. El cajón deja entrar a la región sin tocar el protocolo; el id conserva el criterio clínico fino donde lo hay. Fue la condición para poder ampliar el catálogo: antes las rotaciones nombraban los alimentos uno a uno y un alimento nuevo no podía aparecer en un plan por muchos que se añadieran.

**Dos listas explícitas en `comun.py` gobiernan a qué componentes se les aplica cada regla.** Están escritas con su porqué encima porque son decisiones clínicas, no detalles de implementación:

- `COMPONENTES_SIN_FILTRO_TEXTURA` — bebida, grasa, ensalada_grasa. `texturas_excluidas` describe cómo come el niño, no cómo bebe ni de qué está hecho un plato por dentro. Sin esto, a un paciente que no tolera lo húmedo el filtro le quitaba el agua y toda la grasa del plan.
- `COMPONENTES_SIN_EXIGENCIA_DE_VARIEDAD` — carbohidrato, base_energetica, grasa, ensalada_grasa, crujiente, bebida. Que el arroz vaya a diario es normal; que el snack sea el mismo 28 veces no. El resto de componentes exige variedad aunque estén cubiertos por un alimento base.

**Cuando el sistema no puede comprobar una restricción de seguridad, se detiene.** Ya valía para una alergia sin etiqueta en el catálogo; ahora vale también para un plan con `texturas_excluidas` donde algún alimento no declara su textura. Un veredicto APTO sobre una restricción no verificada es el peor modo de fallo posible.

**`nunca_recomendar: true` en el catálogo es una exclusión absoluta**, para todos los pacientes, antes que la edad y las alergias, con bloqueo del validador si aparece igualmente. Hoy solo la lleva la sangrecita, por decisión clínica sostenida de Paty. No se borra el alimento del catálogo: se deja marcado para que la regla sea visible y nadie lo vuelva a añadir creyendo que faltaba.

**`riesgo_disfagia` es un campo distinto de `texturas_excluidas`, y suelen contradecirse.** Uno dice lo que el niño no se come; el otro, lo que le puede hacer daño al tragar. En aversión textural lo seco es a la vez lo único que acepta y el perfil de bolo que se impacta. El sistema no resuelve esa tensión —es criterio clínico— pero la mide y la pone delante de Paty: PC_CLINICO la detecta, P1 ajusta humectación, tamaño de bocado, corte y líquido acompañante, y el validador avisa cuando el plan carga de seco.

**Las fotos de receta se generan una sola vez en la vida de la receta.** Esto no reemplaza el flujo de Canva de los recetarios que Paty vende: son productos distintos con listón distinto. Aquí se trata del anexo personalizado de cada paciente.

**La fotografía es parte del render, no un paso propio.** *(Cambiado el 11/08/2026.)* `generar_imagenes.py` existía, funcionaba y estaba documentado como F3b opcional — y en todo el MVP no se generó ni una sola imagen. Un paso opcional que hay que acordarse de ejecutar es un paso que no se ejecuta: el fallo estaba en el diseño del flujo, no en el script. Hoy `render.py` mira, antes de maquetar el recetario, qué recetas del plan no tienen foto, escribe el prompt que falte y llama al generador. Los dos comandos sueltos siguen existiendo para trabajar la biblioteca entera. **Ninguna foto detiene un plan:** sin clave, sin red o con la API caída se avisa en una línea y esas recetas salen con su banda de color.

**El sistema entra por el chat, no por una carpeta.** *(Cambiado el 11/08/2026.)* Paty no va a crear `pacientes/[Nombre]/fuente/`; va a arrastrar los archivos al chat y escribir *"hazme un plan de dos semanas para este paciente"*. La carpeta la crea el sistema, y ahí dentro guarda también **lo que ella escribió en el mensaje**: *"son dos semanas"*, *"no come nada verde"*, *"la familia viene de la selva"* es información clínica, y si vive solo en el chat desaparece del caso en la siguiente sesión. La única pregunta permitida al arrancar es el nombre del niño, y solo si no está en el material.

**Las claves de API viven solo en `.env`** (ignorado por git) o en variables de entorno. Nunca en un archivo del proyecto, nunca en un chat. El repositorio ya se filtró una vez por esto.

---

## 4b. Dónde se toca cada cosa

Esto es un MVP y va a cambiar en cuanto Paty lo use de verdad. Casi todos sus pedidos van a llegar en lenguaje de consulta —*"a este niño dale más en el desayuno"*, *"quiero menos menestras"*, *"añádeme la zarandaja"*— y **casi ninguno se arregla en el motor**. El motor es la parte que menos debería moverse: si un cambio de este tipo termina en un `if` dentro de `ensamblar.py`, se ha parcheado el sitio equivocado y el sistema pierde la garantía de que el plan cumple el protocolo.

| Lo que pide | Dónde se toca |
|---|---|
| Porciones y reparto calórico por comida | la ficha del paciente y `prompts/PC_CLINICO.md` |
| Estructura del día, frecuencias, rotaciones | el `.yaml` del protocolo |
| Alimentos nuevos | `datos/alimentos_base.yaml` |
| Recetas nuevas | P1, y aterrizan en `biblioteca/` |
| Un entregable nuevo (p. ej. una guía de implementación para la familia) | plantilla HTML + CSS nuevos en `motor/plantillas/`, llamados desde `render.py` |
| Estilo visual de los PDF | `motor/plantillas/*.css` |

Dos matices que se pierden si solo se lee la tabla:

- **Ficha o PC_CLINICO** no son lo mismo. La ficha es este paciente; PC_CLINICO es cómo se leen todos. Si Paty dice *"a Thiago dale más en el desayuno"*, es la ficha. Si dice *"yo siempre reparto 25/30/35/10"*, es PC_CLINICO, y entonces cambia para todos los que vengan.
- **Un tipo de plan nuevo es un `.yaml` nuevo**, copiado de uno existente. Nunca una rama nueva en el ensamblador. Lo mismo vale para un entregable nuevo: plantilla propia, no un modo especial dentro de las que ya hay.

Un cambio toca el motor solo cuando lo que falla es una cuenta, un filtro o una garantía: el validador no ve algo que debería ver, el filtro de alergias deja pasar un alimento, una frecuencia no se cumple. Eso sí es un bug y ahí sí se entra al código.

---

## 5. Reglas que no se rompen

- `pacientes/` nunca se sube a git. Son historiales clínicos de menores.
- `plan.json` no se edita a mano. Si algo está mal, se corrige en el protocolo, en la biblioteca o en la ficha, y se vuelve a ensamblar. Editar la salida destruye la única garantía que da el sistema.
- Las recetas no se inventan dentro del plan. Pasan por P1, con su auditoría de seguridad pediátrica, y aterrizan en `biblioteca/` antes de aparecer en un menú.
- **Si una alergia de la ficha no coincide con ninguna etiqueta del catálogo, se etiqueta el catálogo. Nunca se borra la alergia de la ficha para que el validador calle.**
- Cuando un script falla, se muestra el error tal cual. Los mensajes están escritos para leerse enteros.

---

## 6. El benchmark Thiago y lo que reveló

`pacientes/_BENCHMARK_Thiago/` es un caso sintético difícil a propósito: esofagitis eosinofílica con eliminación de cuatro alimentos, selectividad severa (nueve alimentos aceptados), aversión a texturas mixtas y húmedas, sospecha de alfa-gal sin documentar, familia amazónica recién mudada a la costa, abuela cocinando el almuerzo sin manejar la dieta, y datos contradictorios entre documentos.

**El sistema pasó 10 de 11 controles.** Se detuvo donde debía, detectó que el protocolo `escolar_6_11` era imposible para este paciente (exige huevo y yogurt, ambos eliminados), y creó `escolar_eliminacion_4.yaml` en su lugar. Detectó que la etiqueta `carne_mamifero` no existía en el catálogo y que por tanto la alergia no filtraba nada — y paró a preguntar en vez de arreglarlo solo.

**Reveló un agujero grande, ya tapado:** el sistema no tenía concepto de textura. Cuatro preparaciones húmedas ocupaban las 28 ranuras de media mañana y media tarde de un niño cuya madre dijo "nada aguado" como primera frase. El nombre de un plato nunca delata su textura: "compota de pera" no contiene la palabra "aguado". Se añadió el campo `textura` a alimentos y recetas y `texturas_excluidas` a la ficha. Al revalidar el plan viejo con el filtro nuevo salieron **86 errores**.

**Y reveló, en la tanda del 11/08, tres agujeros más — los tres ya tapados:**

- **La migración de textura se había aplicado al catálogo y nunca a la biblioteca.** El filtro solo miraba alimentos base y toda receta le pasaba por debajo. El plan salía APTO con 22 raciones de textura excluida dentro —compota ×6, mazamorra ×6, paletas ×6, crema ×4— para un niño con impactación documentada, y lo único que lo delataba era un aviso entre nueve. Hoy las 13 recetas declaran su textura y la restricción no comprobada bloquea.
- **El filtro de textura tumbaba el agua y las grasas.** `agua` es `liquida` y las tres grasas son `humeda` o `liquida`: el plan no se podía ensamblar, y el error no decía por qué. De ahí la lista de exentos.
- **La comprobación de biblioteca insuficiente daba por resuelto cualquier componente con un alimento base.** El plan se llenaba con "Fruta picada" 10 de 28 veces y el motor lo daba por bueno. En selectividad severa eso no es aburrido: encoge el repertorio que el plan tendría que ampliar.

**Estado actual del caso:** Thiago ensambla, valida sin errores y tiene sus dos PDF. Ver 7.2.

---

## 7. Pendientes, por prioridad

### 7.1 Catálogo regional — el más importante, a medio camino

`datos/alimentos_base.yaml` es costeño, y ni siquiera trujillano: faltan zarandaja, pallares, bonito, jurel y pota tanto como el plátano bellaco o la cocona. En el benchmark el plan salía con arroz y papa, comida que ese niño no come.

**Hecho:** el mecanismo. Las rotaciones ya pueden pedir un cajón (`tuberculo`, `grano`, `hojuelas`, `aceite`, `fruto_graso`) en vez de nombrar los alimentos uno a uno, así que un alimento regional nuevo entra en los planes sin tocar ningún protocolo. `revisar.py` comprueba que las 47 claves de rotación y frecuencia de los tres protocolos correspondan a algún alimento.

**Falta:** los alimentos. Y antes de escribirlos, **la respuesta de Paty al Bloque 1** — tres preguntas de encuadre: cómo se reparten sus familias por región, si los niños andinos y amazónicos que viven en Trujillo siguen comiendo lo de su tierra o ya comen como la costa, y qué alimentos regionales no quiere recomendar nunca. Su respuesta decide el tamaño de la lista. Después hace falta, por alimento: disponibilidad real en Trujillo (siempre / por temporada / difícil / no se consigue), precio en tres cajones, edad mínima segura, textura y alérgeno.

**Diseño ya acordado, no implementado:** tres campos por alimento —`region`, `mercado`, `costo`— y dos en la ficha —`origen_familiar`, `compras`—, todos opcionales y con valor por defecto que no toca ninguna línea existente. `mercado: no_hay` filtra duro; la coincidencia de región sube la prioridad en `puntaje()`; y un aviso nuevo del validador cuando la familia es de una región y el plan no tiene ni un alimento de ella.

### 7.2 Caso Thiago — cerrado hasta el registro

Ensambla, valida sin errores y tiene sus dos PDF (`--caras`), ya **con las seis recetas fotografiadas**. Se crearon con P1 cuatro recetas: `chifles-platano-bellaco` y `galletas-quinua-camote` (base, media mañana y tarde), `pollo-dorado-tiras` (acompanante, desayuno) y `granola-kiwicha-quinua` (cereal, desayuno).

**Falta:** que Paty revise los PDF, y `registrar.py` con el importe. Y hay tres decisiones suyas encima de la mesa, todas en el reporte: el choque entre `riesgo_disfagia` y `texturas_excluidas` en este niño concreto; cuatro recetas nuevas de golpe en un paciente con selectividad severa cuando el protocolo topa la novedad en 3; y si autoriza el ajonjolí, que la ficha permite.

### 7.3 Reglas de protocolo declaradas pero no implementadas

El motor las ignora y el validador solo avisa:

- `max_recetas_nuevas_semana` (selectividad) — relevante clínicamente: en selectividad severa la novedad es el riesgo.
- `introduccion_progresiva`, `progresion_textura`, `exclusiones_duras` (protocolo de ablactancia).

### 7.4 Hoja para el cuidador secundario

El benchmark lo dejó claro: si el almuerzo lo cocina la abuela y no maneja la dieta, el 30 % de las calorías depende de alguien que no leyó el plan. Haría falta un tercer entregable corto, en lenguaje directo, con lo que esa persona necesita saber.

### 7.5 Generación de imágenes — hecha y verificada

*(Cerrado el 11/08/2026.)* Ejecutada con clave real contra `gemini-3.1-flash-image`: las seis recetas del plan de Thiago tienen foto, el recorte sale exacto a proporción A4 (0.707) por el borde inferior, y el recetario las embebe sangrando a los cuatro bordes. La banda de color del acento y el fondo de la fotografía combinan como preveía la tabla de `fotos.py`.

Quedan 11 recetas de la biblioteca sin imagen (las que ningún plan ha usado todavía). Se generarán solas la primera vez que un plan las lleve; para adelantarlo, `python motor/generar_imagenes.py --todas`.

### 7.6 Etiquetas de alérgeno demasiado gruesas

`frutos_secos` es un solo cajón para maní, almendra, anacardo y coco, que clínicamente no son la misma alergia. En el caso Thiago apareció tres veces estrechando el repertorio de un niño que tiene ocho alimentos: descarta sus dos únicos snacks secos previos —barritas de kiwicha y trufas de garbanzo— y bloqueó dos veces el aceite de coco, que era el mejor candidato por densidad calórica. Partir la etiqueta afecta a todo el catálogo y a las recetas ya escritas: decisión de Paty.

### 7.7 Desfases entre los prompts y el motor

`P1_RECETAS.md` describe `familia` como si sirviera solo para las reglas de frecuencia y dice que se deje vacío si no aplica. Desde las familias funcionales eso ya no es cierto: `familia` es también el cajón de las rotaciones, y una receta de `cereal` con el campo vacío solo puede entrar por degradación. Hay que actualizar esa regla del front-matter. Es el tipo de desfase que hay que buscar cada vez que cambie el motor: los prompts no se revalidan solos.

### 7.8 Higiene

- Fusionar la rama `codex/replace-with-zip` a `main`.
- Rotar la clave de Gemini: pasó por un chat.
- Confirmar que el cliente OAuth de Google del repositorio antiguo (`nutrios-492116`) fue eliminado. Borrar los archivos no bastaba, seguían en el historial de git.
- `plan.json` y `reporte_qa.md` se regeneran en cada corrida y ensucian `git status`. Valorar ignorarlos; `ficha.md` sí conviene conservarla.
- `motor/migrar_textura.py` ya cumplió su función (catálogo y biblioteca al día). Se puede borrar cuando se prefiera, pero documenta el vocabulario de texturas y de momento sirve de referencia.

---

## 8. Entorno

Windows. Python 3.12.

WeasyPrint necesita las bibliotecas nativas de GTK, que en Windows no vienen con el paquete de pip. Ya está resuelto en la máquina de Danny: MSYS2 en `C:\msys64`, `pacman -S mingw-w64-x86_64-pango`, y la variable de entorno `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`. Verificado: los PDF se generan.

Comprobación de salud del sistema, siempre lo primero:

```bash
python motor/revisar.py
```

---

## 9. Cómo se ve un ciclo completo

```bash
# F0: Paty arrastra los archivos al chat y pide el plan.
#     El sistema crea pacientes/[Nombre]/fuente/ y guarda ahí los adjuntos
#     Y su mensaje. Ella no toca el sistema de archivos.
# F1: con prompts/PC_CLINICO.md → ficha.md

python motor/correr.py [Nombre]          # ensambla y valida
# si falla por biblioteca insuficiente → F3 con P1, contexto limpio por receta

python motor/render.py [Nombre] --caras  # genera las fotos que falten y maqueta;
                                         # no corre si el validador bloqueó

# Paty revisa los DOS PDF y dice qué cambiar, si hay algo.
# Se corrige en la ficha, el protocolo o la biblioteca — nunca en plan.json —
# se vuelve a ensamblar, validar y renderizar, y se le entregan otra vez.

python motor/registrar.py [Nombre] --costo 189 --tipo primera_vez
python motor/metricas.py --html
```
