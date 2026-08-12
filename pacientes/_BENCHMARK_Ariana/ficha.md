---
paciente: "Ariana V. Ch."
edad_meses: 9
edad_texto: "9 meses (edad corregida) · 11 meses de nacida"
fecha: 2026-08-11
sexo: F
peso_kg: 7.7
talla_cm: 70.5
zscore_pt: -1.09
zscore_te: 0.14
semanas_plan: 4
protocolo_sugerido: ablactancia_9_11
requerimiento_kcal: 610
metodo_kcal: "FAO/WHO/UNU 2004, niñas 9–11 m: 79 kcal/kg/día × 7.7 kg. Sobre edad CORREGIDA. De ese total, la fórmula aporta la mitad larga; el reparto exacto no se puede fijar sin el volumen diario de fórmula (ver bloqueantes)."

diagnosticos: [anemia, estrenimiento, aplv]
diagnostico_texto: >
  Prematura de 33+2 semanas (peso al nacer 1,910 g), con indicación expresa de
  neonatología de usar edad corregida hasta los 24 meses. Anemia microcítica
  hipocrómica: Hb 9.6 g/dL, VCM 68 fL, HCM 22 pg, RDW 16.8 % (lab 04/08/2026),
  sin perfil de hierro. Índice de Mentzer derivado = 15.7, compatible con
  ferropenia. Sobre ese cuadro: sulfato ferroso profiláctico prescrito desde el
  mes de vida y administrado de forma irregular —frasco dispensado en junio,
  aún casi lleno—. Estreñimiento de ~2 meses con deposiciones cada 3–4 días,
  esfuerzo, llanto y fisura anal superficial. APLV no IgE mediada diagnosticada
  a los 4 meses (deposiciones con sangre y dermatitis), resuelta con fórmula
  extensamente hidrolizada, SIN prueba de provocación realizada.
  Crecimiento adecuado para edad corregida: no hay desnutrición.

alergias: [lacteos]
rechazos: [papa, brocoli]
texturas_excluidas: []
riesgo_disfagia: false
favoritos: [lentejas, higado, pollo, zapallo, zanahoria, camote, platano, pera, papaya, avena, arroz]

porciones:
  base_energetica: "3 cdas"
  proteina_hierro: "2 cdas (≈30 g cocido)"
  verdura: "1 cda"
  grasa: "1 cdta"
  fruta: "3 cdas"
  fruta_vitc: "2 cdas"

bloqueantes:
  - "Fórmula extensamente hidrolizada: marca exacta, volumen diario, número de tomas y cuánto tarro cubre realmente el SIS al mes. No figura en ninguna fuente. A esta edad la leche es más de la mitad de la energía del día: sin ese dato no se puede repartir el requerimiento ni escribir el marco diario del plan."
  - "Qué leche toma a partir del 2 de septiembre. La pediatra indicó leche entera de vaca al año y retirar la fórmula; la APLV nunca se sometió a prueba de provocación. El plan de 4 semanas empieza el 1.º de septiembre y cruza esa fecha en su día 2. No se puede imprimir un plan de un mes que deja indefinida la bebida principal de tres de sus cuatro semanas."
---

## Lectura del caso

**El dato que reordena todo el caso es la edad.** Ariana nació a las 33+2
semanas con FPP 21/10/2025. Hoy tiene 11 meses y 9 días de nacida, pero **9 meses
y 21 días de edad corregida**, y la epicrisis de neonatología lo deja por escrito
en mayúsculas: la edad corregida se usa para el desarrollo y para la alimentación
complementaria hasta los 24 meses. La mamá lo menciona de pasada, como si ya no
contara —Paty lo anotó—, y a partir de ahí todo el material del caso la trata
como una niña de once meses. No lo es.

**Corregida la edad, el crecimiento deja de ser el problema.** Sobre edad
corregida: peso/edad −0.54 DE, talla/edad **+0.14 DE**, peso/talla −1.09 DE. Los
tres dentro de rango, y la talla justo en la mediana. Sobre edad cronológica los
mismos números dan −1.02 y −0.58 DE, que es la lectura que invita a diagnosticar
bajo peso donde no lo hay.

**El aplanamiento de junio a agosto es un artefacto de medición, no una
detención del crecimiento.** El propio carné avisa: la fila del 12/06/2026 está
escrita con otro lapicero y otra letra, y la mamá dice que ese día la pesaron
vestida y con zapatos. Si se descarta ese punto, el tramo 16/05 → 09/08 da
**+1,100 g en 85 días = 12.9 g/día**, que es velocidad normal —incluso buena—
para 9–11 meses. Con el punto de junio dentro, el tramo junio–agosto da 5.2 g/día
y el mayo–junio da 29.6 g/día: dos cifras imposibles que se cancelan entre sí y
que son la firma aritmética de una sola pesada mala. En el mismo período creció
5.0 cm. **No hay estancamiento que explicar.**

Eso no absuelve a la fórmula diluida. Dos meses echando una medida menos de polvo
es dilución de energía, de proteína y de todos los micronutrientes del tarro
—incluido el hierro fortificado—, más agua libre de sobra. Que la niña haya
seguido creciendo no lo vuelve inocuo: es un problema de acceso que sigue activo
hoy y que hay que cerrar con el SIS, no un hallazgo antropométrico.

**Lo que sí está descompensado es el hierro, y por partida triple.** Prematura
—reservas bajas de origen y necesidad aumentada—, sulfato ferroso prescrito desde
el mes de vida pero administrado "cuando se acuerda" con el frasco de junio casi
lleno, y fórmula diluida. Encima, el patrón de comidas trabaja en contra: el
biberón se da *junto con* el almuerzo, y el calcio de la fórmula compite
directamente con el hierro de esa comida. Hb 9.6 con VCM 68 no es un hallazgo
incidental: es anemia moderada en una lactante, y la profilaxis a 2 mg/kg/día ya
no es la respuesta.

**Y hay una exposición de riesgo abierta ahora mismo.** La abuela le da agüita de
miel con limón por las noches desde hace tres semanas. Miel antes de los 12 meses
es riesgo de botulismo del lactante, y la aclaración de la mamá —"es miel pura de
la sierra, no es de la del súper"— apunta en la dirección contraria a la que ella
cree: la miel artesanal sin procesar es la de mayor carga de esporas. Está en la
lista de exclusiones duras del protocolo y en `reglas_9_11_meses.md`. Esto no
espera al plan.

## Estrategia nutricional

**Hierro como eje del plan, con la aritmética de absorción respetada.** Hierro
hemínico a diario (hígado, sangrecita, pollo, bofe), vitamina C de fruta entera
en la misma comida, y **separación estricta de la fórmula respecto de las comidas
principales** —al menos una hora—. Retirar el biberón de acompañamiento del
almuerzo es, por sí solo, una de las intervenciones de mayor rendimiento del caso.
Las menestras, que además le encantan, siempre acopladas a fruta con vitamina C.

**Fibra y agua para el estreñimiento, por vía de alimento entero, no de jugo.**
Menestras, pera, papaya, ciruela, avena, verdura. Bajar el peso relativo de la
manzana rallada y del plátano maduro en la rotación de fruta. Agua en taza a
sorbos entre comidas; el jugo de naranja en biberón sale del plan por doble
motivo —jugo y biberón—. Grasa a diario (aceite, palta) como ablandador y como
densidad calórica en volumen pequeño.

**Textura de 9–11 meses, no de 6.** Picado, desmenuzado y dados del tamaño de un
garbanzo; el puré liso deja de ser la base. Ariana ya almuerza de la olla familiar
y acepta prácticamente todo: la ventana de textura está abierta y conviene usarla.

**Sodio cero añadido.** Nada de sal ni de ajinomoto en su porción. La operativa es
separar su ración de la olla **antes** de sazonar, no cocinar aparte: la abuela no
va a hacer dos almuerzos, y pedírselo es garantizar que no se cumpla.

**Densidad, no volumen.** Requerimiento total ≈ 610 kcal/día, de los que la
fórmula bien preparada cubre la mitad larga. La comida complementaria aporta el
resto en 3 comidas de ¾ de taza más una fruta: son porciones pequeñas y cada
cucharada tiene que trabajar.

## Señales de derivación

De las seis señales de la lista, **el caso presenta una**, y conviene decir
también cuáles descarté y por qué, porque el material invita a marcar dos que no
corresponden.

**Presente — sospecha de causa médica no estudiada.** Cuatro frentes, todos
médicos y ninguno resoluble con un plan alimentario:

1. **Anemia sin estudiar.** Hb 9.6 g/dL, VCM 68 fL, RDW 16.8 %. El laboratorio
   anota que no se procesó ferritina ni perfil de hierro porque no figuraba en la
   orden (laboratorio.txt). El índice de Mentzer derivado (15.7) apunta a
   ferropenia y no a talasemia, pero es un cálculo, no un diagnóstico. Corresponde
   dosis terapéutica y control de Hb, no continuar con profilaxis.
2. **APLV sin prueba de provocación, con una decisión de leche encima.** La nota
   de la pediatra lo dice: "Prueba de provocación NO realizada aún"
   (nota_pediatra.txt), y en la misma nota indica iniciar leche entera de vaca al
   año. Esas dos frases no pueden convivir sin que alguien las resuelva.
3. **Tos de tres semanas en una ex-prematura de 33 semanas.** Aparece solo como
   justificación de la miel (notas_consulta_paty.txt, whatsapp_mama.txt); nadie la
   está siguiendo como síntoma. En una ex-prematura merece que la vea la pediatra.
4. **Fisura anal con ciclo de dolor–retención instalado.** Deposiciones cada 3–4
   días con esfuerzo y llanto desde hace dos meses (nota_pediatra.txt). La fibra y
   el agua trabajan sobre la consistencia; el miedo a defecar por dolor necesita
   además tratamiento tópico de la fisura y, si no cede, valoración digestiva.

**Descartadas, con su razón:**

- **Estancamiento del crecimiento entre controles — NO.** Es el punto que más
  invita a marcarla y no corresponde: descartada la pesada dudosa de junio, la
  velocidad real es de 12.9 g/día. Ver la aritmética en la Nota para Paty.
- **Repertorio reducido — NO.** Acepta prácticamente todo lo que se le ofrece; el
  WhatsApp de la mamá lista once alimentos ya probados y aceptados, y rechaza
  exactamente dos. No es selectividad.
- **Arcadas, atragantamientos, vómitos o miedo a comer — NO.** El único vómito
  descrito es con el sulfato ferroso, que es efecto adverso del suplemento y no
  conducta alimentaria. Por eso `riesgo_disfagia: false`.
- **Rechazo por textura, temperatura o color sostenido — NO.** Papa y brócoli son
  aversiones a dos alimentos concretos, no a una forma de comer.
- **Comidas largas o que terminan en llanto — NO.** El llanto descrito es al
  defecar, no al comer.

## Cómo se derivaron las porciones

Requerimiento total 79 kcal/kg/día × 7.7 kg = **610 kcal/día** (FAO/WHO/UNU 2004,
niñas 9–11 meses, sobre edad corregida). A 9–11 meses la fórmula bien preparada
cubre algo más de la mitad; a la alimentación complementaria le corresponden
≈ 280–300 kcal/día repartidas en 3 comidas principales más una fruta de media
tarde.

Traducido a medida casera con el criterio MINSA para 9–11 meses: **¾ de taza por
comida principal** (≈ 5 cucharadas de plato armado), con 2 cucharadas de alimento
de origen animal en cada una. De ahí salen las porciones del front-matter:
3 cdas de base energética + 2 cdas de proteína de hierro + 1 cda de verdura +
1 cdta de grasa ≈ ¾ de taza.

**Advertencia sobre estos números:** el reparto entre fórmula y comida está
calculado sobre una fórmula bien preparada y a volumen habitual para la edad. Hoy
no sabemos ni la marca, ni el volumen, ni cuántas tomas recibe —y sabemos que
lleva dos meses diluida—. Las porciones quedan como estimación provisional hasta
que se cierre el primer bloqueante.

--- NOTA PARA PATY ---

### 1. Bloqueantes

**El pipeline se detiene aquí.** Hay dos, y ninguno lo puedo resolver leyendo el
material: los dos se resuelven con una llamada.

**a) La fórmula: marca, volumen diario, número de tomas y qué cubre el SIS.**
Lo busqué en la nota de la pediatra, en tus notas de consulta y en el WhatsApp de
la mamá. En los tres aparece "fórmula extensamente hidrolizada" sin una sola cifra
detrás. A los 9–11 meses la leche es más de la mitad de la energía del día: sin
ese número no puedo repartir las 610 kcal ni escribir el marco diario, que en este
protocolo es lo primero que se imprime. Y hay un motivo extra para preguntarlo
ahora: lleva dos meses tomándola diluida, así que el volumen *nominal* y el
volumen *efectivo* no son el mismo dato. Necesito los dos.

**b) Qué toma a partir del 2 de septiembre.** Este es el importante, y es de
calendario tanto como de clínica. El plan es de 4 semanas, la mamá entra a
trabajar el 1.º y el 2 Ariana cumple 12 meses: **la transición cae en el día 2 del
plan.** Tres de las cuatro semanas impresas quedan bajo una bebida principal que
hoy está sin definir, y las tres cosas que chocan son estas:

- La pediatra indicó leche entera de vaca, 2 vasos al día, retirando la fórmula.
- La misma nota dice que la **prueba de provocación no se ha hecho**. Sustituir la
  fórmula hidrolizada por leche de vaca en casa, sin supervisión, *es* una prueba
  de provocación —solo que sin control y ejecutada por la abuela.
- Aunque la APLV estuviera resuelta, **2 vasos de leche de vaca al día en una
  lactante con Hb 9.6 empujan en la dirección contraria a lo que necesita**: la
  leche de vaca es mala fuente de hierro, su calcio inhibe la absorción del poco
  que come, desplaza comida, y en exceso se asocia a pérdida digestiva oculta.
  Este argumento es nutricional y vale por sí solo, independientemente de la
  alergia.

Añado el dato de edad para la conversación con la Dra. Zavaleta: el 2 de
septiembre Ariana cumple 12 meses **cronológicos**, pero tiene **10 meses y 12
días corregidos**. Para el hito de la leche de vaca la referencia habitual es la
edad cronológica; lo que decide aquí no es esa distinción sino la provocación
pendiente. Lo mismo, al revés, con la miel: el umbral de los 12 meses para el
botulismo es cronológico, así que el 2 de septiembre deja de ser un riesgo
—aunque no por eso conviene ofrecérsela, porque azúcares añadidos antes de los 24
meses siguen fuera.

### 2. Antes que el plan — cosas que no esperan a que se desbloquee esto

Las pongo aquí arriba a propósito. Si esta semana solo se pudiera hacer una
llamada a la mamá, sería esta lista y no el plan:

1. **Retirar la miel hoy.** Botulismo del lactante. La abuela se la da por la tos,
   de noche, desde hace tres semanas. Hay que decirle explícitamente que "miel
   pura de la sierra" es **más** riesgosa que la del súper, no menos: es
   exactamente lo contrario de lo que la mamá entendió, y si eso no se corrige la
   indicación no se va a cumplir. Y hay que darle a la abuela algo que ponga en su
   lugar, porque un "no" a secas contra una tos que "le calma harto" no gana.
2. **Restituir la dilución correcta de la fórmula.** Una medida rasa por cada
   30 mL de agua, como diga el tarro. La mamá te lo contó bajando la voz, con la
   abuela al lado: no es descuido, es que no le alcanza. Si el SIS no ha aprobado
   el cambio, arreglar el suministro es parte del tratamiento, no un trámite
   aparte. Lo trataría como la gestión más urgente del caso después de la miel.
3. **Separar el biberón del almuerzo.** Se lo dan junto "para que pase la comida",
   y así el calcio bloquea el hierro de la única comida del día que lo trae. Al
   menos una hora de distancia. Coste cero, efecto inmediato.
4. **Sulfato ferroso: dosis, horario y adherencia.** El frasco de junio está casi
   lleno; en la práctica no lo está recibiendo. Con Hb 9.6 y VCM 68 la profilaxis
   a 2 mg/kg/día se queda corta —a dosis terapéutica de 3 mg/kg/día serían
   ≈ 23 mg de hierro elemental al día—, pero la dosis la fijas tú o la pediatra,
   no la ficha. Sobre el vómito: separarlo de la fórmula, darlo entre comidas y
   partirlo en dos tomas suele resolverlo.
5. **Responder lo del jugo de naranja: no en biberón y no como jugo.** La mamá
   preguntó si puede darle el hierro con el juguito para que pase. La intención es
   correcta —la vitamina C mejora la absorción— y el vehículo no: los jugos están
   prohibidos a esta edad y el biberón agrava lo del hierro y los dientes. La
   misma vitamina C, en fruta entera aplastada en la comida, hace el trabajo mejor.
6. **Sal y ajinomoto fuera de su porción.** Separar su ración antes de sazonar.
   Ver el punto 7 sobre por qué esto hay que planteárselo a la abuela y no a la
   mamá.
7. **La tos de tres semanas, a la pediatra.** Nadie la está mirando como síntoma;
   solo aparece como excusa de la miel.

### 3. Trazabilidad

| Valor | Origen |
|---|---|
| `edad_meses` 9 | **calculado — edad CORREGIDA** desde FPP 21/10/2025 (alta_neonatologia.txt) a 11/08/2026 = 9 m 21 d |
| edad cronológica 11 m 9 d | calculado desde f. nac. 02/09/2025 (alta_neonatologia.txt, carnet_cred.txt, nota_pediatra.txt — coinciden las tres) |
| corrección aplicada | calculado. FPP − f. nac. = 49 días = **7.0 semanas**. Coherente con 33+2 sem de EG (Capurro) |
| `peso_kg` 7.7 | notas_consulta_paty.txt, 11/08/2026 (peso en consultorio). Coincide con carnet_cred.txt del 09/08/2026 |
| `talla_cm` 70.5 | notas_consulta_paty.txt, 11/08/2026 (tallímetro, echada). Coincide con carnet_cred.txt del 09/08/2026 |
| `zscore_pt` −1.09 | calculado. **Peso/talla** WHO 2006 niñas, 70.5 cm (L −0.3833, M 8.441, S 0.0856) |
| `zscore_te` +0.14 | calculado. **Talla/edad corregida** WHO 2006 niñas, 9 m (L 1, M 70.1435, S 0.0375) |
| peso/edad −0.54 | calculado. WHO 2006 niñas, 9 m corregidos (L −0.1085, M 8.2254, S 0.12204). No va al front-matter, que solo tiene dos campos |
| `requerimiento_kcal` 610 | calculado. FAO/WHO/UNU 2004, niñas 9–11 m, 79 kcal/kg/d × 7.7 kg |
| Hb 9.6 / VCM 68 / HCM 22 / RDW 16.8 | laboratorio.txt, toma 04/08/2026 |
| Índice de Mentzer 15.7 | **derivado** de laboratorio.txt: RBC = Hto 29.4 / VCM 68 × 10 = 4.32 M/µL; Mentzer = 68 / 4.32. >13 orienta a ferropenia. Es un cálculo orientativo, no reemplaza el perfil de hierro |
| Serie de peso y talla | carnet_cred.txt (15/01, 14/03, 16/05, 12/06, 09/08 de 2026) |
| `semanas_plan` 4 | mensaje_2026-08-11.md ("necesito el mes completo") |
| `alergias` [lacteos] | nota_pediatra.txt (APLV no IgE, dx a los 4 meses), notas_consulta_paty.txt |
| `rechazos` [papa, brocoli] | whatsapp_mama.txt y notas_consulta_paty.txt — coinciden |

**Sobre `zscore_pt`:** el campo lleva **peso/talla**, que a esta edad sí existe en
la referencia WHO (a diferencia del caso de Thiago, donde llevaba IMC/edad). Lo
apunto porque el número entra en el PDF.

**Los tres z-score van sobre edad corregida**, que es lo indicado para prematuros
hasta los 24 meses y lo que pide expresamente la epicrisis. Peso/talla no depende
de la edad, así que ese no cambia.

### 4. Discrepancias

**a) Edad: 10 meses (nota_pediatra.txt, 21/07) vs 11 meses cronológicos vs 9 meses
corregidos.** La nota de la pediatra dice "Edad: 10 meses" en una fecha en que
tenía 10 meses y 19 días cronológicos: coherente. Ninguna fuente salvo la
epicrisis usa edad corregida. **Usé la corregida, y es la decisión más importante
de esta ficha.** Cambia el protocolo, cambia las texturas, cambia la lectura
antropométrica y cambia si este caso es "una niña que no sube de peso" o no lo es.
Fundamento: indicación expresa de neonatología en la epicrisis, y práctica
estándar en prematuros hasta los 24 meses.

**b) Peso del 12/06/2026 (7.4 kg): la descarté.** Es la discrepancia que más pesa
en la lectura del caso, así que dejo la aritmética entera para que la audites:

| Tramo | Días | Ganancia | g/día |
|---|---|---|---|
| 15/01 → 14/03 | 58 | +700 g | 12.1 |
| 14/03 → 16/05 | 63 | +500 g | 7.9 |
| 16/05 → **12/06** | 27 | +800 g | **29.6** |
| **12/06** → 09/08 | 58 | +300 g | **5.2** |
| **16/05 → 09/08 (sin el punto de junio)** | **85** | **+1,100 g** | **12.9** |

29.6 g/día seguidos de 5.2 g/día no son dos hechos: son una sola pesada
sobreestimada que infla el tramo anterior y desinfla el siguiente. Tres cosas
independientes apuntan a lo mismo: el carné anota esa fila con otro lapicero y
otra letra, la mamá dice que la pesaron vestida y con zapatos, y tú misma
escribiste en consulta que esa cifra te daba desconfianza. Descartada, la
velocidad real del trimestre es 12.9 g/día, **normal para 9–11 meses**. En el
mismo período creció 5.0 cm y la talla/edad quedó en la mediana.

Por eso **no puse `bajo_peso` en `diagnosticos`**, y quiero que sea una decisión
tuya y no un descuido mío: ponerlo habría activado los ajustes de recuperación del
protocolo y habría convertido un caso de anemia en un caso de desnutrición que los
números no sostienen. La ropa y los zapatos de un bebé de 7 kg pesan del orden de
300–500 g, que es justo el tamaño del error.

**c) Peso al alta 2,280 g vs peso al nacer 1,910 g** (alta_neonatologia.txt): no es
discrepancia, es la evolución de 21 días de hospitalización. Lo anoto para que
nadie lo lea como dos mediciones del mismo día.

**d) "Cambio de fórmula 06/26 — coordinar con SIS"**, nota manuscrita al margen del
carné, marcada como difícil de leer. Encaja exactamente con lo que te contó la
mamá en consulta sobre la demora del SIS y el inicio de la dilución en junio. Dos
fuentes independientes, misma fecha: lo tomo como confirmado.

### 5. Dudas de alergia

**a) El yogurt "hipoalergénico de bebé" — la más urgente de responder.** La mamá lo
compró y está esperando tu visto bueno (whatsapp_mama.txt). La inmensa mayoría de
los yogures infantiles que se venden como "hipoalergénicos" son de **leche de vaca
con proteína parcialmente hidrolizada**, que no es lo mismo que extensamente
hidrolizada y **no es seguro en una APLV**. "Hipoalergénico" en un envase es una
declaración comercial, no una categoría clínica. Hasta ver la etiqueta con la
lista de ingredientes, va excluido por `lacteos`. Merece la pena pedirle una foto
del envase: es respuesta de dos minutos y la mamá está esperando para dárselo.

**b) `lacteos` cubre la APLV, pero conviene revisar las trazas.** El protocolo lo
anota en `preferencias_clinicas.aplv` ("verificar trazas en productos
procesados"). No es una duda de la ficha, es un aviso para el material de entrega:
la abuela cocina de la olla familiar y ahí entran caldos, cubitos y margarinas.

**c) Ninguna alergia nueva ni etiqueta fuera de catálogo.** `lacteos` ya existe en
`datos/alimentos_base.yaml`, así que no hay aquí nada parecido al agujero de
`carne_mamifero` del caso de Thiago. El validador no debería parar por esto.

**d) La miel no es una alergia, es una exclusión dura por edad.** Lo aclaro porque
no aparece en `alergias` y no quiero que se lea como un olvido: está en
`exclusiones_duras` del protocolo y en `reglas_9_11_meses.md`, y el motor la
excluye por esa vía.

### 6. Elección de protocolo — y por qué el pipeline se va a detener otra vez

Escribí `protocolo_sugerido: ablactancia_9_11`, **que no existe**. Lo hago a
propósito, en vez de forzar el que hay, y esto es lo que hay detrás.

`ablactancia_6_meses` es el único protocolo de lactante del repositorio y declara
`edad_min_meses: 6, edad_max_meses: 6`. Ariana tiene 9 corregidos: **queda fuera
por rango**, así que el ensamblador va a fallar de todos modos. Y si se forzara,
sería peor que fallar:

- Su `progresion_textura` va de papilla lisa a "aplastado con grumos suaves".
  `reglas_9_11_meses.md` dice lo contrario para esta edad: pinza fina, dados de
  tamaño garbanzo, picado y desmenuzado, y **el puré liso ya no debe ser la base**.
  Ariana lleva un mes almorzando de la olla familiar: retrocederla a papilla sería
  cerrar una ventana de textura que ya está abierta.
- Su rotación de `base_energetica` reparte `papa_pure: 2` por semana. **La papa es
  el único rechazo consistente de Ariana**, en las dos fuentes.
- Su rotación de `verdura` es `{zanahoria: 3, zapallo: resto}`, con espinaca y
  brócoli deliberadamente fuera "a los 6 meses". A los 9–11 ese argumento ya no
  aplica y la variedad se queda muy corta para cuatro semanas.
- El día tiene **una sola comida principal** más una media tarde desde la semana 3.
  A 9–11 meses corresponden 3 comidas más una lapsa. Es la diferencia entre un
  plan y medio plan.
- Está marcado como **ESQUELETO** en su primera línea, con las frecuencias de
  hígado y menestra sin revisar por ti y con "los números son marcadores de
  posición, no una recomendación". No lo estrenaría con una paciente real sin que
  le des una pasada.

Según la regla del proyecto, un tipo de plan que no existe **se crea copiando uno
existente en `/protocolos/`, nunca parcheando el ensamblador**. Eso es lo que
corresponde aquí: `ablactancia_9_11` a partir de `ablactancia_6_meses`, con tres
comidas, textura de 9–11 meses, la papa fuera de la rotación y las frecuencias de
hierro subidas. **No lo he creado: los números clínicos de un protocolo llevan tu
firma, no la mía.**

### 7. La biblioteca no tiene con qué armar este plan

Lo adelanto para ahorrarte un viaje, aunque sea de la fase siguiente. Las 17
recetas de `/biblioteca/` se crearon para el protocolo escolar: sus componentes
son `base`, `acompanante` y `cereal`, y sus momentos, `desayuno`, `media_manana` y
`media_tarde`. **Ninguna es de `almuerzo`, y ninguna usa los componentes del
protocolo de lactante** (`base_energetica`, `proteina_hierro`, `verdura`, `grasa`).
Por edad, solo tres declaran `edad_min_meses: 6` —compota de pera y avena, crema
de quinua y manzana, y huevo revuelto con palta—, y de esas la del huevo lleva
`alergenos_presentes: [huevo]`.

Traducido: cuando se desbloquee el caso, F2 va a pedir prácticamente **toda** la
biblioteca de lactante de cero, del orden de 15 a 25 recetas nuevas por P1 antes
de que exista un plan de cuatro semanas. Es trabajo de una sesión larga, no de un
comando, y conviene que lo sepas antes de prometerle la fecha a la mamá.

Un consuelo: casi todas van a salir de lo que Ariana ya come y acepta —lentejas,
hígado, pollo, zapallo, zanahoria, camote, avena, pera, papaya—, así que son
recetas de bajo riesgo de rechazo, y quedan en la biblioteca para el siguiente
lactante con APLV que entre por la puerta.

### 8. Contexto de ejecución — quien cocina no es quien te consultó

Tres cosas que no entran en el front-matter y que deciden si el plan se cumple:

- **La abuela materna es la cocinera, y el plan se lo van a entregar en papel.**
  Es la misma persona que sazona con sal y ajinomoto porque "si no la comida no
  sabe a nada", y la que da la miel. No está en contra: no le han explicado nada.
  El material de entrega necesita **una hoja escrita para ella**, en lenguaje
  directo, con las tres cosas que la afectan —sal, miel, biberón separado del
  almuerzo— y el porqué de cada una. Un plan dirigido a la mamá, que a partir del
  1.º no está en la casa a la hora de almuerzo, es un papel.
- **La operativa de la sal tiene que ser "separar antes de sazonar", no "cocinar
  aparte".** Nadie hace dos almuerzos todos los días. Si la instrucción es cocinar
  aparte, a la semana se abandona y vuelve la sal.
- **La mamá pregunta qué le compra para el cumpleaños del 2 de septiembre** para
  "empezar con la leche como dijo la doctora". Esa compra va a ocurrir con o sin
  respuesta tuya, y la fecha es en tres semanas. Conviene que la respuesta llegue
  antes que la leche.
