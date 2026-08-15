# P2 · CRITERIO DE COMPOSICIÓN DEL PLAN v1.0 — Nutri-OS · GrowKids

*El criterio clínico y sensorial con el que se compone una comida. Lo lee quien decide qué poner en la grilla: el ensamblador cuando elige entre candidatos, y tú cuando Paty pide un cambio y hay que juzgar si ese cambio se sostiene.*

---

## QUÉ ES ESTO Y QUÉ NO ES

Este documento **no arma planes**. Los arma `motor/ensamblar.py`, que reserva primero las ranuras que las frecuencias exigen y solo después rellena, porque las frecuencias del protocolo se garantizan por construcción y no se verifican después.

Este documento tampoco **comprueba** planes. Eso lo hace `motor/reglas.py`, que recuenta desde cero y rechaza por ID.

Lo que hay aquí es lo tercero: **el criterio**. Por qué una comida está bien compuesta, qué se mira antes de decidir, y qué significa cada regla más allá de su aritmética. El generador piensa con esto; el validador verifica con el código; y las dos cosas se llaman igual —R-2, T-6, V-1— para que una conversación sobre un plan se pueda tener con una sola palabra.

**La regla de oro, y la que gobierna todo lo demás:** no se entrega un plan, se entrega **un plan que pasó el validador**. Si un slot se queda sin candidatos válidos, se escribe `[HUECO DECLARADO]`, se dice qué reglas vaciaron el conjunto y qué receta faltaría para cerrarlo. **Nunca se rellena con lo que haya.** Un hueco declarado es un resultado profesional; un cereal ocupando el slot de la proteína es un error que la nutricionista ve en tres segundos.

---

## EL ORDEN, QUE NO ES NEGOCIABLE

    perfil → gramática → candidatos filtrados por reglas duras →
    optimización sensorial → validación → reporte

Nunca al revés. Nunca «armo la grilla bonita y después reviso».

---

## CAPA 2 · La gramática de la comida

Cada franja es una plantilla de **slots tipados**. No se escriben listas de alimentos: se llenan slots, y cada slot declara qué **roles** acepta.

| Slot | Papel | Roles que acepta |
|---|---|---|
| ANCLA | el piso de ingesta | `ancla` |
| ENERGÍA | el fondo del plato | `cereal`, `tuberculo` |
| PROTEÍNA | de aquí sale el material para crecer | `proteina_animal`, `proteina_vegetal`, `menestra` |
| GRASA | densidad calórica, nombrada | `grasa` |
| VEGETAL / FRUTA | color y vitamina C | `fruta`, `verdura` |
| BEBIDA | al final, con tope | `bebida` |
| SUPLEMENTO | indicación médica, con hora | `suplemento` |

**Un alimento puede *poder* cubrir varios roles, pero en una comida dada ocupa exactamente uno.** Si la quinua entra como cereal, no cuenta además como proteína de esa comida. Es lo que impide que un desayuno de quinua licuada y avena «tenga proteína».

> **R-0.** Un alimento solo llena un slot cuyo conjunto de roles contenga uno de los suyos. Un slot obligatorio vacío invalida la comida entera. **No se cubre un slot con un alimento de otro rol aunque «se parezca».**

Esta sola regla habría bloqueado tres de los siete desayunos del primer plan real: la crema de quinua es cereal y ocupó el sitio de la proteína, los bastones de papa son tubérculo y ocuparon el mismo.

---

## CAPA 3 · Clínica

### Composición

- **R-1 · Un solo grano por comida.** Se compara `grano_base`, no el título de la receta. «Avena + panqueques de avena» son dos nombres y un solo cereal, y así salió impreso. *(El ANCLA aporta su grano y lo bloquea para el resto de la comida, no al revés.)*
- **R-2 · Proteína en toda comida principal, desayuno incluido.** Un desayuno de cereal + cereal + fruta se rechaza.
- **R-3 · Grasa en toda comida principal.** Nombrada y cuantificada. Una grasa que «viaja dentro» de otra cosa no se cuenta: se nombra, o no está.
- **R-4 · Máximo dos componentes de demanda oral ≤ N1 por comida.** Una comida entera en papilla no alimenta el tono oral: lo deja caer. *(El agua y el aceite que va en la preparación no cuentan: no son bocados.)*
- **R-5 · No se apilan dos carbohidratos.** Salvo el ANCLA, que tiene el suyo propio.

### Hierro

- **R-Fe1** · Toda comida principal con hierro no hemínico lleva vitamina C **en esa misma comida**. En otra no sirve.
- **R-Fe2** · Ninguna comida con hierro no hemínico lleva calcio, té ni infusión. Esto se comprueba en **todas** las comidas, no solo en las principales, y la asimetría con R-Fe1 es deliberada: la vitamina C que falta es una oportunidad perdida, el calcio al lado del hierro es un daño activo.
- **R-Fe3** · El suplemento aparece **en la grilla**, con su hora y con la separación de lácteos escrita. Lo que no está en la grilla, la madre no lo lee a las siete de la mañana.
- **R-Fe4** · Con déficit de hierro, el desayuno lleva vitamina C en ≥5 de 7 días.
- **R-Fe5** · Si hay menestra, la vitamina C es obligatoria en esa comida.

> Y una que no es aritmética: **la vitamina C tiene que poder comerse.** Un viernes con lentejas y kiwi cumple la regla en el papel y falla en la mesa, porque el kiwi es una corona de semillas negras y este niño no lo va a tocar. Cuando la única fuente de vitamina C de una comida está contraindicada por T-6, la comida no tiene vitamina C.

### Energía y crecimiento

- **R-6 · Objetivo declarado.** Con riesgo de talla baja o bajo peso, el plan declara kcal/día y g de proteína/kg/día objetivo.
- **R-7 · Densidad sobre volumen.** Ante dos opciones equivalentes gana la de mayor densidad calórica. **A un niño que come poco no se le pide comer más: se le da más en lo poco que come.**
- **R-8 · Fibra con techo.** En ingesta baja la fibra sacia antes de nutrir.
- **R-9 · El líquido no compite con la comida.** Agua ≤120 ml por comida principal, **ofrecida al final**. Ninguna bebida calórica sustituye una comida, salvo que sea el ANCLA.

### Lo que se escribe en la grilla

- **R-10 · Propagación total.** Las exclusiones se aplican al alimento, a los ingredientes de cada receta **y a las sustituciones que la receta sugiere**. Una idea de reemplazo que introduce un alérgeno es un fallo de seguridad, no un detalle.
- **R-11 · Prohibido lo genérico.** Todo ítem pasa tres pruebas, y si falla una no se escribe:
  1. **Nombrable.** «Mandarina», no «fruta». «Corbina», no «pescado». «Lenteja», no «menestra». «Zanahoria en bastones», no «ensalada».
  2. **Medible.** Con la unidad del alimento, y físicamente sensata. Nada de «1 porción», y media uva no existe como porción.
  3. **Verificable.** Contrastable contra una lista de exclusiones que nombra especies concretas. Si las exclusiones dicen «trucha» y «pescado de pulpa oscura», la grilla nombra la especie.
- **R-12 · La unidad la define el alimento, nunca la plantilla del slot.** De ahí salieron «Uva cortada a lo largo, ½ unidad mediana» y «Granola de kiwicha, ¾ taza (180 ml)», que rinde cinco cucharadas de sólido seco.

Y una cuarta prueba para lo que solo es seguro en cierto formato:

- **O-5 · El formato de preparación segura se imprime en la grilla.** «Naranja, 3 gajos, sin hollejo ni pepa», no «Naranja, 1 unidad». La madre lee la grilla, no el recetario, a las siete de la mañana.

---

## CAPA 4 · Integración sensorial

Comer es **una tarea motora y sensorial**, no solo una entrega de nutrientes. Un plato puede tener el hierro perfecto y ser imposible de ejecutar para esa boca en particular. Aquí se diseña la tarea, no solo el contenido.

### Demanda oral · N0–N5

| | Qué es | Qué exige | Ejemplos |
|---|---|---|---|
| **N0** | líquido colado | succión y deglución | quinua licuada, bebida de algarrobo |
| **N1** | puré liso | movimiento lingual mínimo | crema, compota, mazamorra, palta aplastada |
| **N2** | blando aplastable con la lengua | machaqueo lingual | camote y papa sancochados, plátano, gajos de cítrico limpios |
| **N3** | blando masticable, cede rápido | masticación vertical breve | panqueque, muffin, milanesa jugosa, pescado en cubo |
| **N4** | firme o fibroso | masticación sostenida, lateralización | pollo en tiras, carne de res, verdura cruda |
| **N5** | duro o crujiente seco | resistencia alta, fatiga rápida | galleta, granola, fruta con cáscara, frutos secos |

**`textura_mixta` es un flag aparte, no un nivel.** Dos consistencias en el mismo bocado —yogurt con trozos, sopa con sólidos, cereal en leche— obligan a la boca a segregar y procesar en paralelo. En hipersensibilidad táctil-oral es la categoría **más** rechazada, por encima de cualquier N5.

### Carga visual · V0–V3

| | Qué es | Ejemplos |
|---|---|---|
| **V0** | monocromo, superficie pareja | quinua licuada, crema, compota, palta aplastada |
| **V1** | un color, relieve uniforme | panqueque, muffin, milanesa, cubo de piña |
| **V2** | piezas separadas e identificables, una por color | bastones, tiras, gajos, cubos servidos aparte |
| **V3** | piezas de distinto color y tamaño mezcladas | ensalada, granola, fruta picada, guiso |

En hipersensibilidad visual, **V3 no es «un poco más difícil»: es otra categoría de tarea.** Antes de morder, el niño tiene que inspeccionar. Si hay algo que no puede clasificar, la comida terminó antes de empezar.

### Las reglas

- **T-1 · Techo de demanda.** Ningún componente supera `nivel_oral_actual`, salvo el RETO, que lo supera en **exactamente un nivel**.
- **T-2 · Piso anti-regresión.** Toda comida principal lleva al menos un componente ≥N2.
- **T-3 · Presupuesto por comida.** Suma de N, componentes ≥N3 y ≥N4, según la franja. Lo declara el protocolo en `presupuesto_sensorial`.
- **T-4 · Ancla · Reto · Reset.** Toda comida principal se ordena así:
  1. **ANCLA** — el alimento aceptado, de baja demanda. Se sirve **primero** y garantiza que el niño coma algo pase lo que pase.
  2. **RETO** — como máximo uno, y sube **un solo eje**: demanda oral **o** carga visual, nunca los dos a la vez.
  3. **RESET** — la comida cierra con algo aceptado y de baja demanda, para que la experiencia termine en éxito y no en fatiga.

  Máximo dos retos al día. **Cero retos en la cena.**
- **T-5 · La cena pesa menos que el almuerzo.** La fatiga oral es acumulativa, y a las 18:00 la mandíbula de un niño con tono bajo ya trabajó todo el día. *La regla de «cena casi idéntica al almuerzo» es correcta para un niño típico y está exactamente al revés para este perfil.*
- **T-6 · Generalización aversiva.** Cuando la ficha declara un `concepto_aversivo`, se filtra **por el rasgo, no por el alimento**. Declarado «puntos negros», quedan fuera el kiwi, la fresa entera, la uva con pepa, la granola, los granos reventados y cualquier cosa moteada, espolvoreada o con vetas —**aunque nadie los haya nombrado nunca**.

  Esto es el mecanismo mismo de la selectividad sensorial: el niño no rechaza alimentos, rechaza rasgos. Un sistema que filtra por lista de alimentos siempre va un paso atrás, porque la lista se escribe con lo que ya rechazó y el siguiente rechazo nunca está en ella.
- **T-7 · Regla de plato.** Cada componente en su propio espacio: **nada encima de nada, nada tocándose**, nada espolvoreado por encima. Las salsas van al lado o no van. Un plato es un mapa que el niño tiene que poder leer de un vistazo.
- **T-8 · Un solo cambio por vez.** Un alimento nuevo se introduce junto al ancla, en la franja de mejor disposición, **uno por semana**, y **se mantiene en el plan aunque se rechace**: la exposición sin presión es la intervención, no el consumo.

  Introducir un cárnico nuevo ocho veces en dos semanas a un niño con selectividad severa no es exposición graduada: es saturación, y garantiza el rechazo.
- **T-9 · Progresión por evidencia, no por calendario.** `nivel_oral_actual` sube en 1 solo cuando el nivel actual se acepta ≥80 % de las ocasiones durante dos semanas. Si hay rechazo, se baja un nivel y se sostiene; no se insiste en el mismo punto. **Esto lo decide Paty en el control, no el motor.**
- **T-10 · El ancla es intocable.** El alimento seguro se sirve **todos los días** y no cuenta para ninguna regla de variedad. Quitarlo para «forzar variedad» es el error clásico y el más caro: sin piso de seguridad, el niño no tiene desde dónde arriesgar.

---

## CAPA 5 · Variedad

- **V-1** · Ninguna receta más de 2 veces por semana, contadas sobre el plan completo, no por franja.
- **V-2** · Ninguna receta en días consecutivos.
- **V-3** · Mínimo de preparaciones distintas por franja y semana. Es **aviso**, no bloqueo: en selectividad, la monotonía de una franja es un dato clínico que Paty tiene que ver, no un error de aritmética.
- **V-4 · Redistribución proporcional.** Cuando un elemento de una rotación está excluido, sus cupos se reparten **proporcionalmente entre los demás de su clase**. Nunca se acumulan en uno solo: al excluir la cañihua, sus dos cupos se fueron enteros a la quinua licuada y una regla de variedad terminó produciendo monotonía.
- **V-5 · El ancla no cuenta.** Exenta de V-1, V-2 y V-3, y **no consume el cupo del slot de energía**.
- **V-6 · La intención sobre el contador.** «Preparaciones a base de huevo, 3–4 veces» no se cumple repitiendo tres veces la misma receta de panqueque. Mínimo dos preparaciones distintas por categoría exigida.
- **V-7 · Diversidad de color.** Mínimo cinco colores distintos de vegetal y fruta por semana, en formatos que respeten T-6 y T-7.

---

## CAPA 6 · Operativa

- **O-1 · Presupuesto de cocina.** Las recetas nuevas de la semana caben en `minutos_cocina_dia × 7`, y como mucho **una** receta de más de 60 min por semana.
- **O-2 · Batch consciente.** Una receta que aguanta 3 días en refrigerador puede programarse dos veces sin coste adicional de cocina, y se declara: «se cocina el lunes, se usa lunes y miércoles».
- **O-3 · Un plan y su recetario se emiten juntos o no se emiten.** Toda preparación de la grilla existe en el recetario, con el mismo identificador de instancia y el mismo nombre impreso. Si el rendimiento de la receta no coincide con la porción de la grilla, se ajusta o se declara el factor.
- **O-4 · Coherencia de despensa.** El plan no puede pedir once insumos que se usan una sola vez.
- **O-5 · Formato para el cuidador.** Ver R-11 y O-5 arriba.

---

## I-1 · Intervenciones activas

**Lo que ya está funcionando no se toca.** Cuando la historia dice que el estreñimiento se normalizó desde que recibe yogurt a diario, el yogurt dejó de ser un alimento de rotación y pasó a ser un tratamiento en curso. Ninguna regla de variedad puede bajarlo, y su modificación —en frecuencia **o en producto**— es rechazo del plan.

El plan real lo bajó de diario a tres veces por semana **y** le cambió el producto, porque no tenía dónde registrar que aquello era una intervención. Ahora la ficha tiene `intervenciones_activas` y el motor lo respeta por construcción.

---

## LO QUE SE DECIDE MIRANDO, NO CONTANDO

Estas cuatro cosas no las puede comprobar el validador y son las que más plan malo evitan. Van aquí porque son criterio:

1. **Qué es el ancla de este niño**, y en qué formatos. Sale de la anamnesis, no del catálogo.
2. **Cuál es el rasgo aversivo**, no la lista de alimentos rechazados. La lista es la consecuencia; el rasgo es la causa.
3. **Qué merece ser el reto de esta semana**, y en qué franja cae la mejor disposición del niño.
4. **Si una combinación tiene precedente en la mesa de esa familia.** El perfil se completa en la comida, no forzosamente en el plato: si el hierro va en el plato principal, la vitamina C puede ir en la fruta de después.

---

## CUANDO PATY PIDE UN CAMBIO

Llega en lenguaje de consulta: *«cámbiame las menestras del martes»*, *«este niño no come camote»*, *«súbele el desayuno»*. Casi ninguno se arregla en el motor.

| Lo que pide | Dónde se toca |
|---|---|
| Un alimento que el niño no come | `rechazos` de la ficha |
| Un alimento nuevo que quiere probar | `exposiciones_planificadas` de la ficha, con su semana |
| Porciones y reparto por comida | `porciones` de la ficha |
| Estructura del día, frecuencias, rotaciones | el `.yaml` del protocolo |
| Un techo sensorial que ya se puede subir | `perfil_sensorial` de la ficha |
| Alimentos que faltan en el sistema | `datos/alimentos_base.yaml` |
| Una técnica que no existe | P1 en modo BASE, y a `biblioteca/` |

Después se vuelve a ensamblar, validar y renderizar. **Nunca se edita `plan.json` ni el PDF a mano:** editar la salida destruye la única garantía que da el sistema.
