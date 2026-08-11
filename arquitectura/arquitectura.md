# Arquitectura cloud propuesta

**Brandon Enrique Eroza Torres**

---

## Mermaid.Ai

Ocupe Mermaid Ai, es una herramienta y tecnología que utiliza inteligencia artificial para convertir texto, ideas o documentos en diagramas visuales de forma automática.Permite crear esquemas escribiendo código sencillo en lugar de dibujar formas a mano.


## Diagrama

![Arquitectura propuesta en Azure](diagrama.png)

---

## Flujo de la solución

| Etapa | Servicio | Qué hace en este caso |
|---|---|---|
| Ingesta | Data Factory (dentro de Fabric) | Trae los precios diarios de las fuentes en una ejecución programada |
| Almacenamiento crudo | OneLake · capa Bronze | Guarda los archivos tal como llegan, sin transformar |
| Validación | Notebook de Fabric | Fase 1: normaliza formatos, contrasta fuentes, aplica LOCF con límite |
| Almacenamiento validado | OneLake · capa Silver | Panel diario ya limpio |
| Agregación | Notebook de Fabric | Fase 2: panel mensual y transformación logarítmica |
| Almacenamiento analítico | OneLake · capa Gold | Insumo del modelo y de los tableros |
| Entrenamiento | Azure Machine Learning | Fase 3: reestima el modelo cointegrado y registra coeficientes |
| Versionado | Model Registry (Azure ML) | Guarda cada versión del modelo con sus métricas |
| Pronóstico | Azure Machine Learning | Fase 4: simulación Monte Carlo y percentiles |
| Agente | Container Apps + Azure OpenAI Service | Interfaz conversacional sobre los resultados |
| Tablero | Power BI | Seguimiento visual para la gerencia |
| Identidad | Microsoft Entra ID | Control de acceso |
| Secretos | Azure Key Vault | Claves de API fuera del código |
| Observabilidad | Application Insights | Trazas de las llamadas del agente |

### ¿Por qué este flujo?

Dicha arquitectura se eligió por su capacidad de equilibrar el robusto procesamiento de los datos juntamente con accesibilidad y seguridad de la experiencia de usuario; y se fundamentaba en 3 pilares:

- **Unificación y Gobernanza de Datos**. (Fabric y OneLake), visto en la arquitectura (Bronze, Silver, Gold) garantiza  el paso de la situación cruda de los datos a formato analítico de alto valor sin duplicación y sin silos. Fabric gestiona la ingesta y transformación, lo que lleva a reducir la complejidad operativa y el movimiento de los datos.

-  **MLOps y Escalabilidad Analítica** (Azure ML), visto en la separación entre los datos preparados (Fabric) y el modelado matemático (Azure ML) permite integrar el control de versiones de manera estricta sobre los modelos econométricos (cointegración y Monte Carlo), asegurando de esta forma la reproducibilidad, la trazabilidad de las métricas así como las actualizaciones sin interrumpir el servicio.

-  **Democratización Segura** (OpenAI + Power BI + Seguridad), ya que la arquitectura no sólo entregab un dashboard clásico para la gerencia, sino que habilitaba en el agente conversacional la adecuada conversación de forma interactiva para explorar los escenarios, todo ello bajo un perímetro de seguridad empresarial nativo (Entra ID, Key Vault) y en monitoreo continuo (Application Insights) que llevaban a saber que la información financiera confidencial no se exponía en ningún caso.

---

## Datos de los servicios (verificados)

### Microsoft Fabric

Fabric usa un modelo de capacidad, no de servicio por servicio: se compra una capacidad (SKU "F") que representa un pool de Compute Units compartido por todos los servicios Data Factory, notebooks Spark, Data Warehouse y Power BI consumen del mismo pool, con un solo costo de cómputo en lugar de cargos separados por servicio.

- **Tarifa:** $0.18 USD por CU-hora en regiones de EE.UU. F2 = 2 CUs.
- **F2 pago por uso:** $0.36/hora, ~$262–263/mes si está siempre encendida.
- **F2 con reserva a 1 año:** $156/mes (descuento aproximado del 41%).
- **Pausable:** la capacidad de pago por uso puede pausarse cuando no se usa; la reservada no.
- **Almacenamiento OneLake:** $0.023 USD/GB/mes, se cobra aparte del cómputo.
- **Suavizado de consumo:** las operaciones interactivas se promedian sobre 10 minutos y
  las de fondo sobre 24 horas, lo que permite que una capacidad pequeña ejecute cargas
  nocturnas intensas.
- **Licencias:** por debajo de F64, los consumidores de reportes de Power BI requieren
  licencia Pro individual.

### Azure Container Apps

Facturación por asignación de recursos por segundo, con escalado a cero.

- **Gratis por suscripción/mes:** 180,000 vCPU-segundos, 360,000 GiB-segundos y 2 millones
  de peticiones HTTP.
- **Tarifa activa (East US, 2026):** ~$0.000024 por vCPU-segundo y $0.000003 por GiB-segundo.
- **Tarifa inactiva:** $0.000008 por vCPU-segundo y $0.000001 por GiB-segundo.
- **Escalado a cero:** si la aplicación baja a cero réplicas, no hay cargo de cómputo.
- **Réplica considerada inactiva** cuando usa menos de 0.01 vCPU y recibe menos de 1,000
  bytes/segundo de tráfico.

### ¿Por qué Contain apps y no functions?

- **Persistencia y Estado**: los contenedores almacenan la información tanto en la memoria como en el disco durante su funcionamiento; las funciones son router (efímeras) y se eliminan cuando las tareas se completan. 
- **Tiempo de Ejecución**: los contenedores funcionan de modo continuo, 24/7; las funciones tienen controles muy estrictos con un tiempo de ejecución (pocos minutos por ejecución). 
- **Control del Entorno**: los contenedores permiten modificar el sistema operativo y librerías al gusto; las funciones dependen del entorno y herramientas limitadas que éstas entregan al proveedor de la nube.


### Azure OpenAI Service

- **GPT-4o mini:** $0.15 USD por millón de tokens de entrada y $0.60 por millón de salida.
- **Referencia de consumo:** procesar 10 millones de tokens al mes con GPT-4o mini cuesta
  del orden de $3 USD en tokens.
- Los precios por token en Azure OpenAI coinciden con los de la API directa de OpenAI;
  la diferencia está en la infraestructura y el marco de gobierno.
- No hay nivel gratuito permanente.

### ¿Por qué Azure OpenAi y no una API?

- **Privacidad Total**: Tus datos nunca serán empleados para formar los modelos públicos de OpenAI.
- **Seguridad de la Red**: Permite conectar los modelos con tus propias redes virtuales corporativas (VNet) y utilizar enlaces privados (Private Endpoints).
- **Control de Acceso**: Integración nativa con Microsoft Entra ID (anteriormente Azure AD), para gestionar permisos por roles (RBAC).
- **Normativa de cumplimiento**: Certificaciones regulatorias internacionales (HIPAA, SOC 2, ISO, GDPR), listas para auditoría.

### Azure Machine Learning

El servicio en sí no tiene costo adicional; se paga el cómputo utilizado durante el entrenamiento y la inferencia, según el tipo de instancia y las horas consumidas.

### ¿Por qué Azure ML y no un Notebook?

se debe a la necesidad de industrializar, escalar y automatizar el ciclo de vida de los modelos. Un Notebook es excelente para experimentar, pero Azure ML es una plataforma para producción.

---

## Estimación de costos mensuales


| Servicio | Supuesto de uso | Costo estimado (USD/mes) |
|---|---|---:|
| Microsoft Fabric F2 | Pago por uso, siempre encendida | 262 |
| Microsoft Fabric F2 | Alternativa: reserva 1 año | 156 |
| OneLake | < 1 GB de datos | < 1 |
| Azure OpenAI (GPT-4o mini) | 10M tokens/mes | 3 |
| Container Apps | 0.5 vCPU con escalado a cero | dentro del nivel gratuito o pocos USD |
| Azure ML | Cómputo bajo demanda, pocas horas/mes | variable |

---

## Dimensionamiento

Volumen real del caso, tomado del análisis:

| Métrica | Valor |
|---|---|
| Filas en el panel diario | 3,565 |
| Observaciones mensuales | 164 |
| Series de precios | 5 |
| Período cubierto | 2010-01 a 2023-08 |
| Tamaño total de los archivos | < 1 MB |

---

## Referencias

- Precios de Microsoft Fabric: https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/
- Precios de Azure Container Apps: https://azure.microsoft.com/en-us/pricing/details/container-apps/
- Facturación de Container Apps: https://learn.microsoft.com/en-us/azure/container-apps/billing
- Precios de Azure Machine Learning: https://azure.microsoft.com/en-us/pricing/details/machine-learning/
- Tarifas de Azure OpenAI por modelo: https://pricepertoken.com/endpoints/azure
- Calculadora de precios de Azure: https://azure.microsoft.com/pricing/calculator/
- Planeación de capacidad en Fabric: https://spendweave.com/blog/microsoft-fabric-pricing-capacity-planning/
- Guía de SKUs de Fabric 2026: https://solv-systems.com/resources/microsoft-fabric-pricing-2026
- Costos de Azure OpenAI 2026: https://www.cloudzero.com/blog/azure-openai-pricing/
