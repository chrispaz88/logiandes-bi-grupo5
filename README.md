# Taller Práctico 2 · LogiAndes S.A. · Grupo 5

**Reto:** Convertir datos en decisiones monitoreables.
Mayra Sanchez · Noemí Fernandez · Christian Pazmiño

## Contenido

```
Taller_2_Grupo5.ipynb   # Problema y audiencias, preparación, 5 KPIs (ficha + cálculo + gráfico + resultado),
                        # estructura del dashboard, hallazgos, coherencia, reflexión y conclusiones
kpis_grupo5.py          # Capa semántica compartida: datos, ficha técnica, cálculo de KPIs y gráficos
app.py                  # Prototipo de dashboard en Streamlit
data/logiandes.csv      # Base de pedidos enero–marzo 2026 (5.798 pedidos)
outputs/                # KPIs exportados por el Notebook (el dashboard los usa para verificar coherencia)
```

## Ejecución local

```bash
git clone https://github.com/<usuario>/logiandes-bi-grupo5.git
cd logiandes-bi-grupo5
python3 -m venv env && source env/bin/activate          # Windows: env\Scripts\activate
pip install -r requirements-notebook.txt                # app + Jupyter (solo la app: requirements.txt)
jupyter nbconvert --to notebook --execute --inplace Taller_2_Grupo5.ipynb   # regenera outputs/
streamlit run app.py
```

## Despliegue

El dashboard está desplegado en **Streamlit Community Cloud** desde la rama `main`, con `app.py` como archivo principal.
Cada `git push` a `main` actualiza la app automáticamente. Si se cambian fórmulas o metas en `kpis_grupo5.py`,
hay que volver a ejecutar el Notebook y subir también `outputs/`, para que la verificación de coherencia siga en verde.

## KPIs (marzo 2026, total empresa)

| KPI | Meta | Valor | Estado |
|---|---|---|---|
| KPI 1 Cumplimiento de meta de ventas (meta ajustada por días) | ≥ 95 % | 108,6 % | 🟢 |
| KPI 2 Ticket promedio (índice vs. enero) | ≥ 100 % | 101,6 % ($24,87) | 🟢 |
| KPI 3 Tasa de reclamos | ≤ 3 % | 3,15 % | 🟡 |
| KPI 4 Mediana del tiempo de entrega | ≤ 120 min | 131 min | 🟡 |
| KPI 5 Entregas a tiempo (≤ 180 min) | ≥ 90 % | 86,9 % | 🟡 |

`kpis_grupo5.AJUSTE_CALENDARIO = False` restaura la meta fija del KPI 1 de la versión anterior (98,1 % en febrero; 108,6 % en marzo).
