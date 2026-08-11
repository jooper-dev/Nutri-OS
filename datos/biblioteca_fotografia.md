# Biblioteca de Prompts — Fotografía Editorial de Recetas A4
**GrowKids** · v2 · Once variantes derivadas de las portadas reales del recetario de referencia

---

## REGLA GENERAL (aplica a todas)

- **Formato:** A4 vertical, relación 210:297, full bleed. Si el generador no acepta esa relación, usa la más cercana (2:3) y recorta después **siempre por el borde inferior**.
- **Zona editorial reservada:** el tercio superior queda limpio, sin comida ni props. Ahí van el título y los iconos en Canva. Es la regla que más se rompe: insístela.
- **Cero texto:** ninguna letra, número, logo, marca de agua ni elemento de maquetación dentro de la imagen.
- **Sin personas**, salvo en las variantes G y H, donde aparece una sola mano adulta y nunca el rostro ni el cuerpo.
- **Familia visual común:** luz de estudio suave y difusa, sombras presentes pero blandas, acabado editorial limpio, nunca publicitario ni hiperbrillante. Vajilla mate y sencilla, coherente en todo el recetario.
- **Placeholders a rellenar:** `[SUJETO]` · `[COLOR DE FONDO]` · `[PROPS]`.
- **Imagen de referencia (opcional):** si existe foto del plato en el material fuente, adjúntala y abre el prompt con: *"El sujeto principal de la imagen adjunta es la receta que debes fotografiar. Úsala para reconocer el alimento, pero crea una composición editorial nueva: no copies su fondo, vajilla, props ni disposición."* Si no hay foto, omite ese párrafo: los prompts ya se sostienen solos.

---

# VARIANTE A — Tres cuartos alto + fondo sólido + plato secundario cortado

**Cuándo usarla:** platos servidos con relieve moderado, salados de plato, panes, bocaditos sobre vajilla.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido sobre un plato de cerámica mate color marfil.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo de tres cuartos alto, aproximadamente 55-65° sobre la superficie.

COMPOSICIÓN
Sitúa el plato principal en la mitad inferior del encuadre, ligeramente desplazado hacia un lateral, nunca centrado con exactitud.
Introduce un segundo plato con la misma preparación en el lado opuesto y más arriba, deliberadamente cortado por el borde del encuadre y visible solo en parte.
Deja el tercio superior completamente limpio, sin comida ni objetos.
[PROPS]

FONDO
Superficie continua, lisa y mate de [COLOR DE FONDO], sin línea de horizonte visible ni cambio de tono entre suelo y pared. El color debe leerse con claridad, nunca lavado hacia el blanco.

ILUMINACIÓN
Luz difusa amplia desde arriba-izquierda. Sombras suaves y direccionales, colores limpios, textura del alimento bien definida.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE B — Cenital + fondo sólido + plato secundario cortado

**Cuándo usarla:** platos de superficie plana o con acompañamiento repartido, donde lo que importa es ver el conjunto desde arriba.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido sobre un plato de cerámica mate en tono claro.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Plano cenital de aproximadamente 80-90°, prácticamente perpendicular a la mesa.

COMPOSICIÓN
Coloca el plato principal en la mitad inferior, ocupando buena parte del ancho.
Añade un segundo plato en la esquina superior de un lateral, cortado por el borde y visible solo parcialmente, para dar profundidad sin llenar el encuadre.
El tercio superior central queda limpio.
[PROPS]

FONDO
Superficie lisa y mate de [COLOR DE FONDO], uniforme en todo el encuadre. El tono debe percibirse con nitidez, nunca casi blanco.

ILUMINACIÓN
Luz cenital-lateral suave desde arriba-izquierda, sombras cortas y blandas, buena definición del relieve del alimento.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE C — Cenital 90° + superficie de piedra + props temáticos

**Cuándo usarla:** recetas con identidad cultural o de origen marcado, donde un objeto contextual aporta relato.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido en un bol de cerámica artesanal de borde irregular.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Plano cenital exacto de 90°.

COMPOSICIÓN
El bol principal ocupa la zona inferior del encuadre, desplazado hacia un lateral y parcialmente cortado por el borde inferior.
Coloca un cuenco pequeño con un complemento de la receta en el lado contrario, más pequeño por escala.
Introduce un elemento alargado en diagonal —un utensilio propio de la receta— cruzando la zona media del encuadre.
Deja el tercio superior despejado.
[PROPS]

FONDO
Superficie de piedra clara, mármol blanco veteado o cemento pulido en tono neutro frío. Textura sutil y visible, nunca protagonista. Puede aparecer una estera o mantel natural bajo una parte de la escena.

ILUMINACIÓN
Luz natural difusa desde una ventana lateral. Sombras suaves y alargadas que revelen la textura de la superficie.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE D — Cenital 90° + superficie neutra + cuenco auxiliar

**Cuándo usarla:** el caso más versátil. Preparaciones que se sirven en plato y se acompañan de una salsa, crema o topping aparte.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido en un plato ovalado o redondo de cerámica moteada en tono hueso.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Plano cenital exacto de 90°.

COMPOSICIÓN
El plato principal se sitúa en el centro-inferior del encuadre, generoso, ocupando cerca de la mitad del ancho.
A un lateral y ligeramente más arriba, un cuenco pequeño con el acompañamiento, claramente subordinado en tamaño.
Un utensilio sencillo puede apoyarse dentro o junto al plato principal, en diagonal suave.
Tercio superior limpio.
[PROPS]

FONDO
Superficie mate y lisa, en una de estas dos opciones según la receta: neutra en gris muy claro o blanco cálido, o bien un color sólido saturado de [COLOR DE FONDO]. En ambos casos, uniforme y sin horizonte.

ILUMINACIÓN
Luz difusa cenital, sombras muy suaves, alta fidelidad de color. Aspecto limpio y sereno.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE E — Unidades repetidas en hilera + una partida

**Cuándo usarla:** barras, galletas, bocaditos, cuadrados, cualquier alimento en piezas iguales donde el interior importa.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Varias unidades iguales, y una de ellas partida o volteada para mostrar con claridad su corte interior y sus capas.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Plano cenital exacto de 90°.

COMPOSICIÓN
Dispón las unidades en una hilera vertical ligeramente irregular que recorra la mitad inferior del encuadre, algunas cortadas por los bordes laterales o inferior.
Evita filas perfectas, simetría rígida y presentación tipo catálogo.
Coloca la pieza partida hacia el centro de la hilera, como punto focal.
Apoya todo sobre una hoja de papel de horno blanco roto, ligeramente arrugada, dejando ver el fondo alrededor.
Permite solo las migas o partículas que caen naturalmente del propio alimento.
Tercio superior limpio.
[PROPS]

FONDO
Superficie clara mate de [COLOR DE FONDO], uniforme y ligeramente desaturada. El tono debe distinguirse con claridad del papel de horno.

ILUMINACIÓN
Luz cenital-lateral suave desde arriba-izquierda. Sombras mínimas pero naturales, excelente definición de texturas.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE F — Tres cuartos bajo + dos platos escalonados en profundidad

**Cuándo usarla:** postres con volumen, porciones donde el perfil y las capas laterales son lo que vende.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Presentado en dos porciones servidas en platos individuales, de modo que se aprecien con nitidez la altura y las capas laterales.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo de tres cuartos bajo, aproximadamente 25-35° sobre la superficie.

COMPOSICIÓN
La porción principal ocupa la zona inferior del encuadre, cerca del observador y desplazada a un lateral.
La segunda porción se sitúa detrás y hacia el lado contrario, más arriba en el encuadre y más pequeña por perspectiva, ligeramente desenfocada.
El escalonado entre ambas crea la profundidad de la escena.
Tercio superior completamente limpio.
[PROPS]

FONDO
Superficie continua y mate de [COLOR DE FONDO], sin horizonte visible, con el mismo tono en plano horizontal y vertical. El color debe leerse saturado, nunca lavado.

ILUMINACIÓN
Luz de estudio grande y difusa desde arriba-izquierda. Sombra proyectada suave y visible bajo los platos, profundidad de campo moderada.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE G — Mano en acción con utensilio

**Cuándo usarla:** recetas donde el gesto explica el plato: espolvorear, servir, verter, decorar.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium, con un gesto en movimiento.

SUJETO
[SUJETO]. Servido en dos recipientes iguales sobre un plato o bandeja.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo de tres cuartos, aproximadamente 40-50° sobre la superficie.

COMPOSICIÓN
Los recipientes se sitúan en la mitad inferior del encuadre, agrupados y ligeramente desplazados a un lateral.
Desde la zona superior entra una sola mano adulta sosteniendo un utensilio sencillo, ejecutando la acción sobre la preparación. Se ve la mano y parte del antebrazo; nunca el rostro ni el cuerpo.
El gesto debe sentirse espontáneo y físicamente creíble, con el material en movimiento cayendo de forma natural si corresponde.
La mano entra por un lateral superior y deja libre el resto del tercio superior.
[PROPS]

FONDO
Superficie continua y mate de [COLOR DE FONDO], sin horizonte visible, tono claramente perceptible.

ILUMINACIÓN
Luz editorial suave desde arriba y lateral, con contraste suficiente para congelar el movimiento sin dureza. Foco principal en la zona de la acción.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE H — Mano tomando una pieza + vasija central + unidades dispersas

**Cuándo usarla:** untables, cremas, dips, salsas y todo lo que se come mojando o tomando con la mano.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium, con un gesto en movimiento.

SUJETO
[SUJETO]. Presentado en un recipiente de cerámica de pared recta y acabado mate, acompañado de las piezas con las que se come.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo de tres cuartos alto, aproximadamente 50-60° sobre la superficie.

COMPOSICIÓN
El recipiente principal ocupa el centro del encuadre, en la mitad inferior.
Alrededor, repartidas de forma irregular sobre la superficie, varias de las piezas que acompañan la receta, algunas cortadas por los bordes.
Desde arriba entra una sola mano adulta sosteniendo una de esas piezas, recién retirada del recipiente y con el contenido cayendo o adherido de forma natural. Se ven solo los dedos y parte de la mano.
Evita llenar el tercio superior: la mano entra desde un borde y el resto queda despejado.
[PROPS]

FONDO
Superficie clara y mate con textura fina, en gris muy claro o blanco cálido; opcionalmente un mantel de patrón discreto bajo la escena.

ILUMINACIÓN
Luz difusa amplia, sombras suaves, colores limpios y apetitosos. Foco nítido en la pieza sostenida.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE I — Bebida hero vertical + props dispersos

**Cuándo usarla:** bebidas, batidos, refrescos, cualquier preparación líquida servida en vaso.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido en un vaso de vidrio liso y transparente, lleno hasta cerca del borde, con el color y la textura de la bebida claramente visibles.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo bajo, casi a la altura del vaso, aproximadamente 15-25° sobre la superficie, para que la bebida se lea como un objeto vertical.

COMPOSICIÓN
El vaso ocupa el centro del encuadre en su mitad inferior, como único protagonista.
A su alrededor, sobre la superficie, elementos sueltos relacionados con la receta —fruta cortada, hielo, hierbas— repartidos de forma dispersa y natural, algunos cortados por los bordes.
Tercio superior limpio por encima del vaso.
[PROPS]

FONDO
Superficie clara y mate de [COLOR DE FONDO], sin horizonte marcado, tono suave pero perceptible.

ILUMINACIÓN
Luz difusa lateral que atraviese parcialmente el vaso y revele la transparencia y la condensación. Sombras suaves, sin reflejos duros ni brillos especulares intensos.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE J — Objeto único centrado + espacio para callouts

**Cuándo usarla:** recetas con variaciones u opciones que se rotularán después en Canva, y bases que se preparan una vez y se usan de varias formas.

```
Crea una fotografía gastronómica editorial para un recetario contemporáneo premium, de aire limpio y gráfico.

SUJETO
[SUJETO]. Un solo objeto protagonista, aislado, sin acompañamientos ni vajilla adicional.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo frontal ligeramente elevado, aproximadamente 20-30°, con el objeto perfectamente definido de arriba abajo.

COMPOSICIÓN
El objeto se sitúa en el centro del encuadre, algo por debajo de la mitad, ocupando una porción moderada del alto.
Todo el espacio alrededor queda deliberadamente vacío: esa amplitud es intencional y sirve para colocar después burbujas de información.
No añadas props ni elementos decorativos: la limpieza del entorno es el objetivo de esta variante.

FONDO
Superficie continua de [COLOR DE FONDO] con un degradado muy suave, algo más luminoso detrás del objeto y ligeramente más profundo en las esquinas. Sin horizonte visible.

ILUMINACIÓN
Luz suave y envolvente que modele el volumen del objeto sin sombras duras. Un reflejo tenue en la base ancla el objeto a la superficie.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

# VARIANTE K — Utensilio levantando una porción suspendida

**Cuándo usarla:** preparaciones de hebra, cubos o piezas que se toman con utensilio y ganan al verse en el aire: pastas, salteados, guisos con trozos, cualquier cosa donde la textura se aprecia al levantarla.

```
Crea una fotografía gastronómica editorial dinámica para un recetario contemporáneo premium.

SUJETO
[SUJETO]. Servido generosamente en un bol o plato hondo de cerámica blanca mate, y una porción del mismo alimento levantada en el aire por un utensilio.

FORMATO
A4 vertical, relación 210:297, full bleed.

CÁMARA
Ángulo frontal, casi a la altura de la mesa, aproximadamente 10-20° sobre la superficie, para que la porción suspendida se recorte contra el fondo limpio.

COMPOSICIÓN
El bol principal ocupa la zona inferior del encuadre, muy cerca del observador, cortado por el borde inferior y sin que se vea completo.
Desde un lateral entra el utensilio —tenedor, cuchara o palillos, según la receta— sosteniendo una porción del alimento suspendida a media altura, por encima del bol.
Esa porción suspendida es el punto focal absoluto y debe conectar visualmente con el bol mediante una caída natural: hebras colgando, salsa goteando o piezas a punto de caer.
El gesto tiene que sentirse físicamente creíble, capturado en movimiento.
No aparece ninguna mano ni persona: solo el utensilio entrando en el encuadre.
Deja limpio el tercio superior, por encima de la porción suspendida.
[PROPS]

FONDO
Superficie continua y mate de [COLOR DE FONDO], sin horizonte visible, especialmente limpia en la parte superior. El tono debe leerse con claridad y contrastar con el alimento.

ILUMINACIÓN
Luz difusa amplia desde arriba y ligeramente lateral. Enfoque nítido en la porción suspendida; el bol inferior puede quedar apenas más suave. Sin bokeh exagerado ni estética publicitaria.

Genera exclusivamente la fotografía base. No incluyas texto, iconos, líneas, gráficos, logos ni elementos de maquetación.
```

---

## RESUMEN DE VARIANTES

| | Variante | Cámara | Fondo | Rasgo distintivo |
|---|---|---|---|---|
| **A** | ¾ alto + plato secundario | 55-65° | Sólido | Segundo plato cortado arriba |
| **B** | Cenital + plato secundario | 80-90° | Sólido | Conjunto visto desde arriba |
| **C** | Cenital + piedra + props | 90° | Piedra / mármol | Utensilio en diagonal |
| **D** | Cenital + cuenco auxiliar | 90° | Neutro o sólido | Plato + acompañamiento |
| **E** | Unidades en hilera | 90° | Sólido claro | Una pieza partida |
| **F** | ¾ bajo escalonado | 25-35° | Sólido | Dos porciones en profundidad |
| **G** | Mano con utensilio | 40-50° | Sólido | Gesto en movimiento |
| **H** | Mano tomando pieza | 50-60° | Neutro texturado | Vasija + piezas dispersas |
| **I** | Bebida hero | 15-25° | Claro | Vaso vertical + props sueltos |
| **J** | Objeto único | 20-30° | Degradado | Vacío para callouts |
| **K** | Porción suspendida | 10-20° | Sólido | Utensilio en el aire, sin mano |

**Cambios frente a la v1:** las dos portadas con mano en acción, antes fundidas en una sola variante, se separaron en **G** (utensilio, gesto sobre el plato) y **H** (mano tomando una pieza de un recipiente). Se deshizo el solapamiento entre las tres cenitales, que ahora se distinguen por superficie y por acompañamiento. Todas dejaron de depender de una imagen adjunta: cada prompt se sostiene solo. Y se incorporó la **K**, de porción suspendida en utensilio, derivada de las portadas de carbonara y tofu sticky.
