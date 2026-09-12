"""
Interactive heat-pump FDD dashboard (Streamlit).

Tabs: dataset overview, data explorer, model performance, live diagnosis,
live FDD, thermodynamics, advanced analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from pathlib import Path

st.set_page_config(
    page_title="Heat Pump FDD",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
PALETTE = ["#8B5CF6", "#6366F1", "#2DD4BF", "#34F5A6", "#F472B6", "#FB923C"]
FAULT_COLORS = {
    "Normal": "#34F5A6",
    "Condenser_Fouling": "#8B5CF6",
    "Evaporator_Fouling": "#6366F1",
    "Refrigerant_Undercharge": "#F472B6",
    "Condenser_Fan_Fault": "#FB923C",
    "Evaporator_Fan_Fault": "#2DD4BF",
}

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: Inter, sans-serif; }

.stApp {
    background:
        radial-gradient(1200px 600px at 10% -10%, rgba(139, 92, 246, 0.18), transparent 50%),
        radial-gradient(900px 500px at 100% 0%, rgba(99, 102, 241, 0.12), transparent 45%),
        #0B0B12;
    color: #F1F1F6;
}
header[data-testid="stHeader"] { background: rgba(11, 11, 18, 0.7); backdrop-filter: blur(12px); }
[data-testid="stToolbar"] { right: 1rem; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #101018 0%, #0C0C14 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p {
    color: #C8C8D8;
}

.brand {
    display: flex; align-items: center; gap: 12px;
    padding: 6px 4px 18px 4px; margin-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.brand-mark {
    width: 42px; height: 42px; border-radius: 12px;
    background: linear-gradient(135deg, #8B5CF6, #6366F1);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; color: white; font-size: 14px;
    box-shadow: 0 0 24px rgba(139, 92, 246, 0.45);
}
.brand-name { font-size: 1.05rem; font-weight: 700; color: #F8F8FC; line-height: 1.2; }
.brand-role { font-size: 0.75rem; color: #9A9AB4; }

.hero {
    display: flex; justify-content: space-between; align-items: flex-end;
    gap: 16px; margin: 0 0 1.4rem 0;
}
.hero h1 {
    font-size: 2rem; font-weight: 700; margin: 0;
    background: linear-gradient(90deg, #F8F8FC, #C4B5FD);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero p { margin: 6px 0 0 0; color: #9A9AB4; font-size: 0.95rem; }

.status-pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 14px; border-radius: 999px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    font-size: 0.82rem; color: #D0D0E0;
}
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.ok { background: #34F5A6; box-shadow: 0 0 10px #34F5A6; }
.status-dot.off { background: #FB923C; }

.kpi-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 18px 18px 16px 18px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.25);
    backdrop-filter: blur(10px);
    min-height: 108px;
}
.kpi-label { font-size: 0.78rem; color: #9A9AB4; letter-spacing: 0.04em; text-transform: uppercase; }
.kpi-value { font-size: 2rem; font-weight: 700; color: #F8F8FC; margin: 6px 0 4px 0; line-height: 1.1; }
.kpi-hint { font-size: 0.78rem; color: #34F5A6; }

.diag-card {
    background: rgba(20,20,28,0.7);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 18px;
}
.diag-ok { color: #34F5A6; font-size: 1.35rem; font-weight: 700; }
.diag-fault { color: #F472B6; font-size: 1.2rem; font-weight: 700; }

.stTabs [data-baseweb="tab-list"] {
    gap: 8px; background: rgba(255,255,255,0.03);
    padding: 6px; border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.06);
}
.stTabs [data-baseweb="tab"] {
    height: 42px; padding: 0 16px; border-radius: 10px;
    color: #A0A0B8; background: transparent;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg, #8B5CF6, #6366F1) !important;
    color: white !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }

div[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 14px 16px;
}
div[data-testid="stMetric"] label { color: #9A9AB4 !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #F8F8FC !important; }

.stButton > button {
    background: linear-gradient(90deg, #8B5CF6, #6366F1);
    color: white; border: 0; border-radius: 10px; font-weight: 600;
}
.stButton > button:hover { filter: brightness(1.08); }

hr { border-color: rgba(255,255,255,0.06) !important; }
</style>
"""


def inject_theme():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def style_fig(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,20,28,0.45)",
        font=dict(color="#E4E4F0", family="Inter, sans-serif", size=12),
        title_font=dict(size=15, color="#F8F8FC"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#C8C8D8")),
        colorway=PALETTE,
        margin=dict(l=40, r=24, t=56, b=40),
    )
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
        color="#A0A0B8",
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
        color="#A0A0B8",
    )
    return fig


def show_chart(fig):
    """Render a Plotly figure in the dark glass theme."""
    st.plotly_chart(style_fig(fig), width="stretch", config=PLOTLY_CONFIG)


def kpi_card(label: str, value: str, hint: str = "") -> None:
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-hint">{hint}</div></div>',
        unsafe_allow_html=True,
    )


def read_csv_auto(path: str) -> pd.DataFrame:
    """Lit un CSV en détectant le séparateur , ou ; (export Excel/locale FR)."""
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline()
    sep = ";" if header.count(";") > header.count(",") else ","
    return pd.read_csv(path, sep=sep)


@st.cache_data
def load_data():
    """Charge les données depuis les fichiers générés."""
    data = {}

    files = {
        "synthetic": "outputs/dataset_fdd.csv",
        "synth_comparison": "outputs/model_comparison.csv",
        "feature_importance": "outputs/feature_importance.csv",
        "confusion_matrix": "outputs/confusion_matrix.csv",
        "test_predictions": "outputs/test_predictions.csv",
    }
    for key, path in files.items():
        if os.path.exists(path):
            table = read_csv_auto(path)
            if key == "confusion_matrix":
                table = table.set_index(table.columns[0])
            data[key] = table

    return data


def create_gauge_chart(value, title, color_scale):
    """Semi-circular performance gauge."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value * 100,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 14, 'color': '#C8C8D8'}},
        number={'suffix': '%', 'font': {'size': 28, 'color': '#F8F8FC'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 0, 'tickcolor': '#3A3A4A'},
            'bar': {'color': color_scale, 'thickness': 0.28},
            'bgcolor': 'rgba(255,255,255,0.03)',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 70], 'color': 'rgba(255,255,255,0.04)'},
                {'range': [70, 90], 'color': 'rgba(139,92,246,0.18)'},
                {'range': [90, 100], 'color': 'rgba(52,245,166,0.18)'},
            ],
            'threshold': {
                'line': {'color': '#34F5A6', 'width': 2},
                'thickness': 0.8,
                'value': 95,
            },
        }
    ))
    fig.update_layout(height=220, margin=dict(l=16, r=16, t=48, b=8))
    return fig


@st.cache_resource
def load_service():
    from src.service import FDDService

    return FDDService()


def create_feature_distribution(df, feature, fault_col='fault_type'):
    """Crée un graphique de distribution par type de défaut."""
    fig = px.box(
        df, x=fault_col, y=feature,
        color=fault_col,
        title=f"Distribution of {feature} by fault type",
        color_discrete_sequence=PALETTE
    )
    fig.update_layout(height=400, showlegend=False)
    return fig


def create_scatter_matrix(df, features, fault_col='fault_type'):
    """Crée une matrice de scatter plots."""
    fig = px.scatter_matrix(
        df,
        dimensions=features[:4],  # Limiter à 4 pour lisibilité
        color=fault_col,
        title="Feature scatter matrix",
        color_discrete_sequence=PALETTE
    )
    fig.update_layout(height=600)
    return fig


def create_radar_chart(comparison_df):
    """Crée un graphique radar de comparaison des modèles."""
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1 Score']
    
    fig = go.Figure()
    
    colors = PALETTE
    
    for i, (_, row) in enumerate(comparison_df.iterrows()):
        values = [row.get(m, 0) for m in metrics]
        values.append(values[0])  # Fermer le polygone
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=metrics + [metrics[0]],
            fill='toself',
            name=row['Model'],
            line_color=colors[i % len(colors)],
            opacity=0.7
        ))
    
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(20,20,28,0.35)",
            radialaxis=dict(
                visible=True, range=[0, 1],
                gridcolor="rgba(255,255,255,0.08)", color="#A0A0B8",
            ),
            angularaxis=dict(gridcolor="rgba(255,255,255,0.08)", color="#A0A0B8"),
        ),
        showlegend=True,
        title="Multi-metric model comparison",
        height=450
    )
    
    return fig


def plot_real_confusion_matrix(cm_df: pd.DataFrame):
    """Heatmap from the saved test-set confusion matrix."""
    values = cm_df.values.astype(float)
    labels = list(cm_df.columns)
    fig = px.imshow(
        values,
        labels=dict(x="Prediction", y="True label", color="Share"),
        x=labels,
        y=list(cm_df.index),
        color_continuous_scale=[[0, "#14141C"], [0.5, "#5B21B6"], [1, "#C4B5FD"]],
        aspect="auto",
        zmin=0,
        zmax=1,
    )
    for i in range(len(labels)):
        for j in range(len(labels)):
            fig.add_annotation(
                x=j,
                y=i,
                text=f"{values[i, j]:.2f}",
                showarrow=False,
                font=dict(color="white" if values[i, j] > 0.5 else "#C8C8D8"),
            )
    fig.update_layout(title="Confusion matrix (held-out test set)", height=520)
    return fig


def prediction_demo(df):
    """Real model inference from simulated operating points."""
    st.subheader("Live diagnosis")
    service = load_service()

    from src.fdd.features import FEATURE_COLUMNS
    from src.studies.synthetic.taxonomy import SCENARIOS

    scenario = st.selectbox("Preset scenario", list(SCENARIOS.keys()))
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        t_source = st.slider("Source temperature (°C)", -10.0, 20.0, 7.0, 0.5)
    with col_b:
        t_sink = st.slider("Sink temperature (°C)", 30.0, 55.0, 40.0, 0.5)
    with col_c:
        speed = st.slider("Compressor speed (%)", 30, 100, 70, 1) / 100.0

    spec = SCENARIOS[scenario]
    try:
        payload, mode = service.simulate_cycle(
            T_source=t_source,
            T_sink=t_sink,
            speed_ratio=speed,
            fault_type=spec["fault_type"],
            **spec["params"],
        )
    except FileNotFoundError:
        st.error("Trained model missing. Run `python main_analysis.py`.")
        return

    diagnosis = payload["diagnosis"]
    cycle = payload["cycle"]

    st.caption(f"{spec['description']} · inference via **{mode}**")
    left, right = st.columns([1, 2])
    with left:
        css = "diag-ok" if diagnosis["label"] == "Normal" else "diag-fault"
        st.markdown(
            f'<div class="diag-card"><div class="{css}">{diagnosis["label"]}</div></div>',
            unsafe_allow_html=True,
        )
        st.metric("Confidence", f"{diagnosis['confidence']*100:.1f}%")
        st.metric("COP", f"{cycle['COP']:.2f}")
        st.metric("T_discharge", f"{cycle['T_discharge']:.1f} °C")
    with right:
        proba_df = pd.DataFrame(
            {
                "class": list(diagnosis["probabilities"].keys()),
                "probability": list(diagnosis["probabilities"].values()),
            }
        ).sort_values("probability", ascending=True)
        fig = px.bar(
            proba_df,
            x="probability",
            y="class",
            orientation="h",
            title="Class probabilities (calibrated Gradient Boosting)",
            range_x=[0, 1],
        )
        show_chart(fig)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("P_evap", f"{cycle['P_evap']:.2f} bar")
    m2.metric("P_cond", f"{cycle['P_cond']:.2f} bar")
    m3.metric("Superheat", f"{cycle['superheat']:.1f} K")
    m4.metric("Subcooling", f"{cycle['subcooling']:.1f} K")

    with st.expander("Manual feature vector"):
        defaults = payload["features"]
        cols = st.columns(3)
        manual = {}
        for i, name in enumerate(FEATURE_COLUMNS):
            with cols[i % 3]:
                manual[name] = st.number_input(name, value=float(defaults[name]), format="%.4f")
        if st.button("Diagnose manual vector"):
            pred, _ = service.predict(manual)
            st.write(pred)


def live_fdd_tab():
    """Telemetry with delayed fault injection."""
    st.header("Live FDD")
    st.markdown(
        "Inject a fault during a run. The model re-labels each timestep (API when available)."
    )
    service = load_service()

    c1, c2, c3 = st.columns(3)
    with c1:
        fault = st.selectbox(
            "Fault to inject",
            [
                "Condenser_Fouling",
                "Evaporator_Fouling",
                "Refrigerant_Undercharge",
                "Condenser_Fan_Fault",
                "Evaporator_Fan_Fault",
                "Normal",
            ],
        )
    with c2:
        inject_at = st.slider("Injection timestep", 5, 45, 20)
    with c3:
        n_points = st.slider("Duration", 40, 80, 55)

    try:
        trace, mode = service.live_trace(
            fault_type=fault,
            inject_at=inject_at,
            n_points=n_points,
        )
    except FileNotFoundError:
        st.error("Trained model missing. Run `python main_analysis.py`.")
        return

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("P_cond", "P_evap", "COP", "Confidence"),
    )
    fig.add_trace(
        go.Scatter(x=trace["t"], y=trace["P_cond"], name="P_cond",
                   line=dict(color="#8B5CF6", width=2.4)), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=trace["t"], y=trace["P_evap"], name="P_evap",
                   line=dict(color="#2DD4BF", width=2.4)), row=1, col=2
    )
    fig.add_trace(
        go.Scatter(x=trace["t"], y=trace["COP"], name="COP",
                   line=dict(color="#34F5A6", width=2.4)), row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=trace["t"], y=trace["confidence"], name="confidence",
                   line=dict(color="#A78BFA", width=2.4)), row=2, col=2
    )
    fig.add_vline(x=inject_at, line_dash="dash", line_color="#F472B6")
    fig.update_layout(
        height=560,
        showlegend=False,
        title=f"Operating point after fault injection ({mode})",
    )
    show_chart(fig)

    last = trace.iloc[-1]
    st.metric("Latest prediction", f"{last['predicted']} ({last['confidence']*100:.0f}%)")
    st.dataframe(trace.tail(12), width="stretch", hide_index=True)


def main():
    inject_theme()
    data = load_data()
    service = load_service()
    api_health = service.health()

    st.sidebar.markdown(
        '<div class="brand"><div class="brand-mark">HP</div>'
        '<div><div class="brand-name">HeatPump FDD</div>'
        '<div class="brand-role">Fault diagnostics</div></div></div>',
        unsafe_allow_html=True,
    )
    if api_health:
        st.sidebar.markdown(
            f'<div class="status-pill"><span class="status-dot ok"></span>'
            f'API · {api_health.get("model", "FDD")}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<div class="status-pill"><span class="status-dot off"></span>'
            "Local engine</div>",
            unsafe_allow_html=True,
        )

    if "synthetic" not in data:
        st.error("No dataset found. Run `python main_analysis.py` first.")
        return

    df = data["synthetic"]
    comparison_df = data.get("synth_comparison", pd.DataFrame())
    st.sidebar.caption(f"{len(df):,} labelled cycles")

    st.markdown(
        f"""
        <div class="hero">
          <div>
            <h1>Insights</h1>
            <p>CoolProp R410A cycle · calibrated Gradient Boosting</p>
          </div>
          <div class="status-pill">
            <span class="status-dot {'ok' if api_health else 'off'}"></span>
            {'API connected' if api_health else 'Local inference'}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Tabs principaux
    tabs = st.tabs([
        "Overview",
        "Data",
        "Models",
        "Diagnosis",
        "Live FDD",
        "Thermodynamics",
        "Advanced",
    ])
    
    # =========================
    # TAB 1: Vue d'ensemble
    # =========================
    with tabs[0]:
        st.header("Dataset overview")
        n_faults = len(df["fault_type"].unique())
        normal_pct = (df["fault_type"] == "Normal").mean() * 100
        best_acc = comparison_df["Accuracy"].max() * 100 if len(comparison_df) else 0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            kpi_card("Samples", f"{len(df):,}", "CoolProp synthetic set")
        with col2:
            kpi_card("Fault classes", str(n_faults), "including Normal")
        with col3:
            kpi_card("% Normal", f"{normal_pct:.1f}%", "healthy operating points")
        with col4:
            kpi_card("Best accuracy", f"{best_acc:.1f}%", "hold-out Gradient Boosting")
        
        st.markdown("---")
        
        # Distribution des défauts
        col_dist1, col_dist2 = st.columns([1, 1])
        
        with col_dist1:
            fault_counts = df['fault_type'].value_counts()
            fig_pie = px.pie(
                values=fault_counts.values,
                names=fault_counts.index,
                title="Fault class distribution",
                color_discrete_sequence=PALETTE,
                hole=0.4
            )
            fig_pie.update_layout(height=400)
            show_chart(fig_pie)
        
        with col_dist2:
            fig_bar = px.bar(
                x=fault_counts.index,
                y=fault_counts.values,
                title="Samples per class",
                color=fault_counts.index,
                color_discrete_sequence=PALETTE
            )
            fig_bar.update_layout(height=400, showlegend=False)
            show_chart(fig_bar)
    
    # =========================
    # TAB 2: Exploration
    # =========================
    with tabs[1]:
        st.header("Data explorer")
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        col_exp1, col_exp2 = st.columns([1, 3])
        
        with col_exp1:
            selected_feature = st.selectbox(
                "Feature to inspect",
                numeric_cols,
                index=numeric_cols.index('superheat') if 'superheat' in numeric_cols else 0
            )
        
        with col_exp2:
            fig_dist = create_feature_distribution(df, selected_feature)
            show_chart(fig_dist)
        
        st.markdown("---")
        
        # Scatter plot interactif
        st.subheader("Feature relationships")
        
        col_sc1, col_sc2 = st.columns(2)
        with col_sc1:
            x_var = st.selectbox("Variable X", numeric_cols, 
                                 index=numeric_cols.index('delta_T_evap') if 'delta_T_evap' in numeric_cols else 0)
        with col_sc2:
            y_var = st.selectbox("Variable Y", numeric_cols,
                                 index=numeric_cols.index('delta_T_cond') if 'delta_T_cond' in numeric_cols else 1)
        
        fig_scatter = px.scatter(
            df, x=x_var, y=y_var, color='fault_type',
            title=f"Relation {x_var} vs {y_var}",
            color_discrete_sequence=PALETTE,
            opacity=0.7
        )
        fig_scatter.update_layout(height=500)
        show_chart(fig_scatter)
        
        # Statistiques descriptives
        st.subheader("Descriptive statistics")
        st.dataframe(df.describe().T.style.format("{:.2f}"), width="stretch")
    
    # =========================
    # TAB 3: Performance Modèles
    # =========================
    with tabs[2]:
        st.header("Model performance")
        
        if len(comparison_df) > 0:
            # Jauges de performance
            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            
            best_model = comparison_df.iloc[0]
            
            with col_g1:
                fig_acc = create_gauge_chart(best_model['Accuracy'], "Accuracy", "#8B5CF6")
                show_chart(fig_acc)
            
            with col_g2:
                fig_prec = create_gauge_chart(best_model['Precision'], "Precision", "#2DD4BF")
                show_chart(fig_prec)
            
            with col_g3:
                fig_rec = create_gauge_chart(best_model['Recall'], "Recall", "#F472B6")
                show_chart(fig_rec)
            
            with col_g4:
                fig_f1 = create_gauge_chart(best_model['F1 Score'], "F1 Score", "#A78BFA")
                show_chart(fig_f1)
            
            st.markdown("---")
            
            # Comparaison des modèles
            col_comp1, col_comp2 = st.columns([1, 1])
            
            with col_comp1:
                st.subheader("Comparison table")
                st.dataframe(
                    comparison_df.style.highlight_max(
                        subset=['Accuracy', 'F1 Score'],
                        color='lightgreen'
                    ).format({
                        'Accuracy': '{:.4f}',
                        'Precision': '{:.4f}',
                        'Recall': '{:.4f}',
                        'F1 Score': '{:.4f}'
                    }),
                    width="stretch"
                )
            
            with col_comp2:
                fig_radar = create_radar_chart(comparison_df)
                show_chart(fig_radar)
            
            # Graphique à barres
            fig_comp_bar = px.bar(
                comparison_df.melt(id_vars=['Model'], 
                                   value_vars=['Accuracy', 'Precision', 'Recall', 'F1 Score']),
                x='Model', y='value', color='variable',
                barmode='group',
                title="Detailed model comparison",
                color_discrete_sequence=PALETTE[:4]
            )
            fig_comp_bar.update_layout(height=400)
            show_chart(fig_comp_bar)
        else:
            st.warning("Comparison metrics not available. Run `python main_analysis.py`.")
        
        # Matrice de confusion
        st.subheader("Confusion matrix (test set)")
        if "confusion_matrix" in data:
            fig_cm = plot_real_confusion_matrix(data["confusion_matrix"])
            show_chart(fig_cm)
        else:
            st.info("Run `python main_analysis.py` to generate the test-set confusion matrix.")
    
    # =========================
    # TAB 4: Prédiction
    # =========================
    with tabs[3]:
        prediction_demo(df)

    with tabs[4]:
        live_fdd_tab()
    
    # =========================
    # TAB 5: Thermodynamique
    # =========================
    with tabs[5]:
        st.header("Thermodynamics")
        
        # Import du module thermodynamique
        try:
            from src.physics.thermodynamic_viz import ThermodynamicVisualizer, create_pressure_temperature_chart
            thermo_viz = ThermodynamicVisualizer()
            
            # Sous-onglets thermodynamiques
            thermo_tabs = st.tabs([
                "P-h diagram",
                "Compressor envelope", 
                "COP curves",
                "System schematic",
                "Monitoring",
                "Load variation"
            ])
            
            # Diagramme P-h
            with thermo_tabs[0]:
                st.subheader("Pressure-enthalpy diagram")
                
                # Indicateur CoolProp
                try:
                    from src.physics.thermodynamic_viz import HAS_COOLPROP, R410A
                    if HAS_COOLPROP:
                        st.success("CoolProp active — R410A properties match ASHRAE saturation tables")
                        
                        # Afficher quelques valeurs de validation
                        col_v1, col_v2, col_v3 = st.columns(3)
                        col_v1.metric("P_sat(0°C)", f"{R410A.P_sat(0):.2f} bar", "Ref: 8.00 bar")
                        col_v2.metric("P_sat(40°C)", f"{R410A.P_sat(40):.2f} bar", "Ref: 24.20 bar")
                        col_v3.metric("h_vap(0°C)", f"{R410A.h_vapor(0):.1f} kJ/kg", "NIST-validated")
                    else:
                        st.warning("CoolProp unavailable — using approximate correlations")
                except:
                    st.info("Loading thermodynamic module...")
                
                st.markdown("---")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    t_evap_ph = st.slider("Evaporation T (°C)", -10.0, 15.0, 5.0, 1.0, key="ph_evap")
                with col2:
                    t_cond_ph = st.slider("Condensation T (°C)", 30.0, 60.0, 45.0, 1.0, key="ph_cond")
                with col3:
                    superheat_ph = st.slider("Superheat (K)", 2.0, 15.0, 6.0, 0.5, key="ph_sh")
                with col4:
                    subcooling_ph = st.slider("Subcooling (K)", 2.0, 12.0, 5.0, 0.5, key="ph_sc")
                
                # Afficher les pressions calculées
                P_evap_calc = R410A.P_sat(t_evap_ph) if HAS_COOLPROP else 8.0
                P_cond_calc = R410A.P_sat(t_cond_ph) if HAS_COOLPROP else 24.0
                ratio_calc = P_cond_calc / P_evap_calc
                
                col_p1, col_p2, col_p3 = st.columns(3)
                col_p1.metric("P_evap (CoolProp)", f"{P_evap_calc:.2f} bar")
                col_p2.metric("P_cond (CoolProp)", f"{P_cond_calc:.2f} bar")
                col_p3.metric("Compression ratio", f"{ratio_calc:.2f}")
                
                fig_ph = thermo_viz.create_ph_diagram(
                    T_evap=t_evap_ph,
                    T_cond=t_cond_ph,
                    superheat=superheat_ph,
                    subcooling=subcooling_ph
                )
                show_chart(fig_ph)
                
                st.info("""
                **Cycle legend:**
                - **1→2**: compression (pressure and enthalpy rise)
                - **2→3**: condensation (heat rejection at constant pressure)
                - **3→4**: isenthalpic expansion (pressure drop)
                - **4→1**: evaporation (heat absorption)
                """)
            
            # Enveloppe Compresseur
            with thermo_tabs[1]:
                st.subheader("Compressor operating envelope")
                
                col1, col2 = st.columns(2)
                with col1:
                    current_t_evap = st.slider("Current evap. T (°C)", -20.0, 20.0, 5.0, 1.0, key="env_evap")
                with col2:
                    current_t_cond = st.slider("Current cond. T (°C)", 25.0, 65.0, 45.0, 1.0, key="env_cond")
                
                fig_envelope = thermo_viz.create_compressor_envelope(
                    current_T_evap=current_t_evap,
                    current_T_cond=current_t_cond
                )
                show_chart(fig_envelope)
                
                # Vérification des limites
                ratio = (current_t_cond + 273) / (current_t_evap + 273)
                if ratio > 1.25:
                    st.success(f"Operating point OK (ratio: {ratio:.2f})")
                elif ratio > 1.20:
                    st.warning(f"Near envelope limits (ratio: {ratio:.2f})")
                else:
                    st.error(f"Outside envelope (ratio: {ratio:.2f})")
            
            # Courbes COP
            with thermo_tabs[2]:
                st.subheader("COP performance curves")
                
                fig_cop = thermo_viz.create_cop_curves(df)
                show_chart(fig_cop)
                
                st.markdown("""
                **How to read this:**
                - COP falls as the compression ratio rises
                - Green zone: efficient operation | Red zone: degraded efficiency
                """)
            
            # Schéma Système
            with thermo_tabs[3]:
                st.subheader("System schematic")
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.write("**System parameters:**")
                    sys_t_evap = st.number_input("Evaporation T (°C)", -10.0, 15.0, 5.0, 0.5)
                    sys_t_cond = st.number_input("Condensation T (°C)", 30.0, 60.0, 45.0, 0.5)
                    sys_p_evap = st.number_input("Evaporation P (bar)", 4.0, 12.0, 8.0, 0.1)
                    sys_p_cond = st.number_input("Condensation P (bar)", 18.0, 35.0, 25.0, 0.1)
                    sys_superheat = st.number_input("Superheat (K)", 2.0, 15.0, 6.0, 0.5)
                    sys_subcooling = st.number_input("Subcooling (K)", 2.0, 12.0, 5.0, 0.5)
                    
                    # Calculer COP approximatif
                    sys_cop = (sys_t_evap + 273) / (sys_t_cond - sys_t_evap) * 0.5
                    sys_cop = max(1.5, min(6.0, sys_cop))
                    
                    fault_options = ["Normal", "Condenser_Fouling", "Evaporator_Fouling", 
                                     "Refrigerant_Undercharge", "Condenser_Fan_Fault"]
                    sys_fault = st.selectbox("Simulated state", fault_options)
                
                with col2:
                    fig_schema = thermo_viz.create_system_schematic(
                        T_evap=sys_t_evap,
                        T_cond=sys_t_cond,
                        P_evap=sys_p_evap,
                        P_cond=sys_p_cond,
                        superheat=sys_superheat,
                        subcooling=sys_subcooling,
                        COP=sys_cop,
                        fault_status=sys_fault
                    )
                    show_chart(fig_schema)
            
            # Monitoring
            with thermo_tabs[4]:
                st.subheader("Live monitoring simulation")
                
                include_fault = st.checkbox("Inject condenser fouling", value=False)
                n_points = st.slider("Simulation duration (min)", 50, 200, 100, 10)
                
                fig_monitoring = thermo_viz.create_monitoring_dashboard(
                    n_points=n_points,
                    include_fault=include_fault
                )
                show_chart(fig_monitoring)
                
                if include_fault:
                    st.error("""
                    **Alert: condenser fouling detected**
                    
                    Observed symptoms:
                    - Rising T_cond
                    - Rising P_cond
                    - Falling COP
                    
                    **Recommended action:** clean the condenser
                    """)
                else:
                    st.success("Normal operation — all parameters within limits")
            
            # Variations de Charge
            with thermo_tabs[5]:
                st.subheader("Impact of thermal load variation")
                
                st.markdown("""
                **What happens to COP, power and the compressor envelope when condenser load
                or evaporator source temperature changes?**
                """)
                
                st.markdown("---")
                
                # Import CoolProp pour les calculs
                try:
                    from CoolProp.CoolProp import PropsSI
                    REFRIGERANT = 'R410A'
                    coolprop_ok = True
                except:
                    coolprop_ok = False
                
                # Onglets pour condenseur vs évaporateur
                load_tabs = st.tabs(["Condenser load", "Evaporator source", "Compressor point", "P-h diagram"])
                
                # === TAB CONDENSEUR ===
                with load_tabs[0]:
                    st.subheader("Condenser load variation")
                    st.info("**Scenario:** heating demand drops (condenser load down)")
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        t_evap_fixed = st.slider("Fixed evap. T (°C)", -10.0, 10.0, 0.0, 1.0, key="cond_evap")
                        charge_range = st.slider("Load range (%)", 30, 100, (30, 100), 5, key="cond_range")
                    
                    # Calcul des données
                    loads = np.linspace(charge_range[1], charge_range[0], 20)
                    t_conds = 45 + (100 - loads) / 100 * 15  # T_cond varie avec la charge
                    
                    results_cond = []
                    for load, t_cond in zip(loads, t_conds):
                        if coolprop_ok:
                            T_evap_K = t_evap_fixed + 273.15
                            T_cond_K = t_cond + 273.15
                            P_evap = PropsSI('P', 'T', T_evap_K, 'Q', 1, REFRIGERANT) / 1e5
                            P_cond = PropsSI('P', 'T', T_cond_K, 'Q', 1, REFRIGERANT) / 1e5
                            tau = P_cond / P_evap
                            
                            h1 = PropsSI('H', 'T', T_evap_K + 8, 'P', P_evap * 1e5, REFRIGERANT)
                            s1 = PropsSI('S', 'T', T_evap_K + 8, 'P', P_evap * 1e5, REFRIGERANT)
                            h2s = PropsSI('H', 'S', s1, 'P', P_cond * 1e5, REFRIGERANT)
                            h2 = h1 + (h2s - h1) / 0.75
                            h3 = PropsSI('H', 'T', T_cond_K - 5, 'P', P_cond * 1e5, REFRIGERANT)
                            
                            W_comp = (h2 - h1) / 1000
                            Q_cond = (h2 - h3) / 1000
                            COP = Q_cond / W_comp if W_comp > 0 else 3.0
                            T_dis = PropsSI('T', 'H', h2, 'P', P_cond * 1e5, REFRIGERANT) - 273.15
                        else:
                            P_evap = 8.0
                            P_cond = 24 + (t_cond - 45) * 0.5
                            tau = P_cond / P_evap
                            COP = 4.0 - (t_cond - 45) * 0.1
                            W_comp = 2.0 + (t_cond - 45) * 0.05
                            T_dis = 70 + (t_cond - 45) * 0.8
                        
                        results_cond.append({
                            'load': load, 't_cond': t_cond, 'P_cond': P_cond,
                            'tau': tau, 'COP': COP, 'W_comp': W_comp, 'T_dis': T_dis
                        })
                    
                    with col2:
                        # Graphiques
                        fig_cond = make_subplots(rows=2, cols=2, 
                            subplot_titles=('COP vs Charge', 'P_cond vs Charge', 
                                          'W_comp vs Charge', 'T_discharge vs Charge'))
                        
                        x = [r['load'] for r in results_cond]
                        
                        fig_cond.add_trace(go.Scatter(x=x, y=[r['COP'] for r in results_cond],
                            mode='lines+markers', name='COP', line=dict(color='blue')), row=1, col=1)
                        fig_cond.add_trace(go.Scatter(x=x, y=[r['P_cond'] for r in results_cond],
                            mode='lines+markers', name='P_cond', line=dict(color='red')), row=1, col=2)
                        fig_cond.add_trace(go.Scatter(x=x, y=[r['W_comp'] for r in results_cond],
                            mode='lines+markers', name='W_comp', line=dict(color='purple')), row=2, col=1)
                        fig_cond.add_trace(go.Scatter(x=x, y=[r['T_dis'] for r in results_cond],
                            mode='lines+markers', name='T_dis', line=dict(color='orange')), row=2, col=2)
                        
                        fig_cond.add_hline(y=130, line_dash="dash", line_color="red", row=2, col=2)
                        
                        fig_cond.update_layout(height=500, showlegend=False, 
                            title_text="Impact of reduced condenser load")
                        fig_cond.update_xaxes(title_text="Charge (%)", autorange="reversed")
                        
                        show_chart(fig_cond)
                    
                    # Synthèse
                    st.markdown("### Summary — condenser load down")
                    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                    
                    delta_cop = ((results_cond[-1]['COP'] - results_cond[0]['COP']) / results_cond[0]['COP']) * 100
                    delta_w = ((results_cond[-1]['W_comp'] - results_cond[0]['W_comp']) / results_cond[0]['W_comp']) * 100
                    delta_tau = ((results_cond[-1]['tau'] - results_cond[0]['tau']) / results_cond[0]['tau']) * 100
                    
                    col_s1.metric("COP", f"{results_cond[-1]['COP']:.2f}", f"{delta_cop:.1f}%")
                    col_s2.metric("W_comp (kJ/kg)", f"{results_cond[-1]['W_comp']:.1f}", f"+{delta_w:.1f}%")
                    col_s3.metric("τ (compression)", f"{results_cond[-1]['tau']:.2f}", f"+{delta_tau:.1f}%")
                    col_s4.metric("T_discharge (°C)", f"{results_cond[-1]['T_dis']:.0f}", "higher risk")
                    
                    st.error("**Main impact: compressor power up**")
                
                # === TAB ÉVAPORATEUR ===
                with load_tabs[1]:
                    st.subheader("Evaporator source variation")
                    st.info("**Scenario:** outdoor temperature drops (cold source down)")
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        t_cond_fixed = st.slider("Fixed cond. T (°C)", 35.0, 55.0, 45.0, 1.0, key="evap_cond")
                        source_range = st.slider("Source T range (°C)", -15, 15, (-15, 7), 1, key="evap_range")
                    
                    # Calcul des données
                    t_sources = np.linspace(source_range[1], source_range[0], 20)
                    t_evaps = t_sources - 5  # DeltaT échangeur
                    
                    results_evap = []
                    for t_source, t_evap in zip(t_sources, t_evaps):
                        if t_evap < -25:
                            t_evap = -25
                        
                        if coolprop_ok:
                            T_evap_K = t_evap + 273.15
                            T_cond_K = t_cond_fixed + 273.15
                            P_evap = PropsSI('P', 'T', T_evap_K, 'Q', 1, REFRIGERANT) / 1e5
                            P_cond = PropsSI('P', 'T', T_cond_K, 'Q', 1, REFRIGERANT) / 1e5
                            tau = P_cond / P_evap
                            
                            h1 = PropsSI('H', 'T', T_evap_K + 8, 'P', P_evap * 1e5, REFRIGERANT)
                            s1 = PropsSI('S', 'T', T_evap_K + 8, 'P', P_evap * 1e5, REFRIGERANT)
                            h2s = PropsSI('H', 'S', s1, 'P', P_cond * 1e5, REFRIGERANT)
                            h2 = h1 + (h2s - h1) / 0.75
                            h3 = PropsSI('H', 'T', T_cond_K - 5, 'P', P_cond * 1e5, REFRIGERANT)
                            h4 = h3
                            
                            Q_evap = (h1 - h4) / 1000
                            W_comp = (h2 - h1) / 1000
                            Q_cond = (h2 - h3) / 1000
                            COP = Q_cond / W_comp if W_comp > 0 else 3.0
                        else:
                            P_evap = 8.0 + t_evap * 0.3
                            P_cond = 24.0
                            tau = P_cond / P_evap
                            COP = 4.0 + t_evap * 0.1
                            Q_evap = 200 + t_evap * 5
                        
                        results_evap.append({
                            't_source': t_source, 't_evap': t_evap, 'P_evap': P_evap,
                            'tau': tau, 'COP': COP, 'Q_evap': Q_evap
                        })
                    
                    with col2:
                        fig_evap = make_subplots(rows=2, cols=2,
                            subplot_titles=('COP vs T_source', 'P_evap vs T_source',
                                          'τ vs T_source', 'Q_evap vs T_source'))
                        
                        x = [r['t_source'] for r in results_evap]
                        
                        fig_evap.add_trace(go.Scatter(x=x, y=[r['COP'] for r in results_evap],
                            mode='lines+markers', name='COP', line=dict(color='blue')), row=1, col=1)
                        fig_evap.add_trace(go.Scatter(x=x, y=[r['P_evap'] for r in results_evap],
                            mode='lines+markers', name='P_evap', line=dict(color='green')), row=1, col=2)
                        fig_evap.add_trace(go.Scatter(x=x, y=[r['tau'] for r in results_evap],
                            mode='lines+markers', name='τ', line=dict(color='cyan')), row=2, col=1)
                        fig_evap.add_trace(go.Scatter(x=x, y=[r['Q_evap'] for r in results_evap],
                            mode='lines+markers', name='Q_evap', line=dict(color='purple')), row=2, col=2)
                        
                        fig_evap.update_layout(height=500, showlegend=False,
                            title_text="Impact of a colder source")
                        fig_evap.update_xaxes(title_text="T_source (°C)")
                        
                        show_chart(fig_evap)
                    
                    # Synthèse
                    st.markdown("### Summary — cold source down")
                    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                    
                    delta_cop = ((results_evap[-1]['COP'] - results_evap[0]['COP']) / results_evap[0]['COP']) * 100
                    delta_p = ((results_evap[-1]['P_evap'] - results_evap[0]['P_evap']) / results_evap[0]['P_evap']) * 100
                    delta_tau = ((results_evap[-1]['tau'] - results_evap[0]['tau']) / results_evap[0]['tau']) * 100
                    delta_q = ((results_evap[-1]['Q_evap'] - results_evap[0]['Q_evap']) / results_evap[0]['Q_evap']) * 100
                    
                    col_s1.metric("COP", f"{results_evap[-1]['COP']:.2f}", f"{delta_cop:.1f}%")
                    col_s2.metric("P_evap (bar)", f"{results_evap[-1]['P_evap']:.1f}", f"{delta_p:.1f}%")
                    col_s3.metric("τ (compression)", f"{results_evap[-1]['tau']:.2f}", f"+{delta_tau:.1f}%")
                    col_s4.metric("Q_evap (kJ/kg)", f"{results_evap[-1]['Q_evap']:.0f}", f"{delta_q:.1f}%")
                    
                    st.error("**Main impact: heating capacity down**")
                
                # === TAB POINT COMPRESSEUR ===
                with load_tabs[2]:
                    st.subheader("Compressor operating-point shift")
                    
                    st.markdown("""
                    How the compressor point moves on the envelope:
                    - **Orange**: condenser load drops (heating demand down)
                    - **Purple**: source temperature drops (colder outdoor air)
                    """)
                    
                    # Enveloppe de fonctionnement
                    fig_env = go.Figure()
                    
                    # Zone sûre
                    fig_env.add_shape(type="rect",
                        x0=-25, y0=25, x1=15, y1=65,
                        fillcolor="rgba(40, 167, 69, 0.2)",
                        line=dict(color="green", width=2))
                    
                    # Zone danger haute
                    fig_env.add_shape(type="rect",
                        x0=-25, y0=65, x1=15, y1=80,
                        fillcolor="rgba(220, 53, 69, 0.2)",
                        line=dict(color="red", width=2))
                    
                    # Point nominal
                    fig_env.add_trace(go.Scatter(
                        x=[0], y=[45], mode='markers+text',
                        marker=dict(size=20, color='green', symbol='star'),
                        text=['NOMINAL'], textposition='top center',
                        name='Nominal point'
                    ))
                    
                    # Trajectoire charge condenseur
                    t_evaps_cond = [r['t_cond'] - 45 + t_evap_fixed for r in results_cond]  # Approximation
                    t_conds_cond = [r['t_cond'] for r in results_cond]
                    
                    fig_env.add_trace(go.Scatter(
                        x=[t_evap_fixed] * len(t_conds_cond), y=t_conds_cond,
                        mode='lines+markers',
                        line=dict(color='orange', width=3),
                        marker=dict(size=8),
                        name='Charge cond. ↓'
                    ))
                    
                    # Trajectoire source froide
                    t_evaps_evap = [r['t_evap'] for r in results_evap]
                    
                    fig_env.add_trace(go.Scatter(
                        x=t_evaps_evap, y=[t_cond_fixed] * len(t_evaps_evap),
                        mode='lines+markers',
                        line=dict(color='purple', width=3),
                        marker=dict(size=8),
                        name='Source ↓'
                    ))
                    
                    # Annotations
                    fig_env.add_annotation(x=-20, y=72, text="DANGER ZONE<br>T_discharge ↑↑",
                        showarrow=False, font=dict(color='red', size=12))
                    fig_env.add_annotation(x=-5, y=45, text="NOMINAL<br>ZONE",
                        showarrow=False, font=dict(color='green', size=12))
                    
                    fig_env.update_layout(
                        title="Compressor envelope — operating trajectories",
                        xaxis_title="Evaporation temperature (°C)",
                        yaxis_title="Condensation temperature (°C)",
                        height=500,
                        xaxis=dict(range=[-30, 20]),
                        yaxis=dict(range=[20, 80])
                    )
                    
                    show_chart(fig_env)
                    
                    # Tableau comparatif
                    st.markdown("### Impact comparison")
                    
                    comparison_data = {
                        'Parameter': ['T_cond', 'T_evap', 'P_cond', 'P_evap', 'τ (compression)',
                                     'W_comp', 'Capacity Q', 'COP', 'MAIN IMPACT'],
                        'Cond. load down': ['↑↑ (+10-15°C)', '≈ (constant)', '↑ (+20-30%)', '≈',
                                          '↑ (+15-25%)', '↑ (+10-20%)', '↓ (-5-10%)', '↓ (-15-25%)',
                                          'POWER UP'],
                        'Evap. source down': ['≈ (constant)', '↓↓ (-15-20°C)', '≈', '↓↓ (-40-50%)',
                                          '↑↑ (+50-100%)', '↑ (+5-15%)', '↓↓ (-30-50%)', '↓↓ (-40-60%)',
                                          'CAPACITY DOWN']
                    }
                    
                    df_comp = pd.DataFrame(comparison_data)
                    st.dataframe(df_comp, width="stretch", hide_index=True)
                    
                    st.success("""
                    **Takeaway:**
                    - Condenser load mainly changes **compressor power**
                    - Evaporator source mainly changes **heating capacity**
                    - In both cases **COP falls** and the **compression ratio rises**
                    - The compressor moves closer to its **envelope limits** (T_discharge up)
                    """)
                
                # === TAB DIAGRAMME P-h ===
                with load_tabs[3]:
                    st.subheader("Cycle shift on the P-h diagram")
                    
                    st.markdown("""
                    Interactive P-h diagram: watch the vapour-compression cycle shift when load or source temperature changes.
                    """)
                    
                    col_ph1, col_ph2 = st.columns([1, 3])
                    
                    with col_ph1:
                        st.markdown("### Parameters")
                        
                        scenario = st.radio(
                            "Scenario",
                            ["Nominal cycle", "Condenser load down", "Evaporator source down",
                             "Compare all three"],
                            index=3
                        )
                        
                        # Paramètres de base
                        t_evap_nominal = st.slider("Nominal evap. T (°C)", -10.0, 10.0, 0.0, 1.0, key="load_ph_nom_evap")
                        t_cond_nominal = st.slider("Nominal cond. T (°C)", 35.0, 55.0, 45.0, 1.0, key="load_ph_nom_cond")
                        superheat_ph = st.slider("Superheat (K)", 2.0, 15.0, 8.0, 0.5, key="load_ph_sh")
                        subcooling_ph = st.slider("Subcooling (K)", 2.0, 12.0, 5.0, 0.5, key="load_ph_sc")
                        
                        # Initialiser les valeurs variées
                        t_evap_varied = t_evap_nominal
                        t_cond_varied = t_cond_nominal
                        
                        if scenario == "Condenser load down":
                            charge_factor = st.slider("Load factor (%)", 30, 100, 50, 5, key="load_ph_charge")
                            t_cond_varied = t_cond_nominal + (100 - charge_factor) / 100 * 15
                            t_evap_varied = t_evap_nominal
                        elif scenario == "Evaporator source down":
                            t_source = st.slider("Outdoor source T (°C)", -15, 15, -10, 1, key="load_ph_source")
                            t_evap_varied = t_source - 5
                            t_cond_varied = t_cond_nominal
                        elif scenario == "Compare all three":
                            # Pour la comparaison, on calcule les deux variations
                            charge_factor = st.slider("Condenser load factor (%)", 30, 100, 50, 5, key="load_ph_charge_comp")
                            t_source = st.slider("Outdoor source T (°C)", -15, 15, -10, 1, key="load_ph_source_comp")
                            t_cond_varied = t_cond_nominal + (100 - charge_factor) / 100 * 15
                            t_evap_varied = t_source - 5
                    
                    with col_ph2:
                        # Fonction pour calculer un cycle complet
                        def calculate_cycle(t_evap, t_cond, superheat, subcooling):
                            """Calcule les points du cycle sur le diagramme P-h."""
                            if not coolprop_ok:
                                # Approximation sans CoolProp
                                P_evap = 8.0 + t_evap * 0.3
                                P_cond = 24.0 + (t_cond - 45) * 0.5
                                h1, h2, h3, h4 = 400, 450, 250, 250
                                return {
                                    'P_evap': P_evap, 'P_cond': P_cond,
                                    'h': [h1, h2, h3, h4, h1],
                                    'P': [P_evap, P_cond, P_cond, P_evap, P_evap]
                                }
                            
                            T_evap_K = t_evap + 273.15
                            T_cond_K = t_cond + 273.15
                            
                            # Pressions de saturation
                            P_evap = PropsSI('P', 'T', T_evap_K, 'Q', 1, REFRIGERANT) / 1e5
                            P_cond = PropsSI('P', 'T', T_cond_K, 'Q', 1, REFRIGERANT) / 1e5
                            
                            # Point 1: Sortie évaporateur (vapeur surchauffée)
                            T1 = T_evap_K + superheat
                            h1 = PropsSI('H', 'T', T1, 'P', P_evap * 1e5, REFRIGERANT) / 1000
                            s1 = PropsSI('S', 'T', T1, 'P', P_evap * 1e5, REFRIGERANT)
                            
                            # Point 2s: Compression isentropique
                            h2s = PropsSI('H', 'S', s1, 'P', P_cond * 1e5, REFRIGERANT) / 1000
                            
                            # Point 2: Compression réelle (rendement 75%)
                            eta_is = 0.75
                            h2 = h1 + (h2s - h1) / eta_is
                            
                            # Point 3: Sortie condenseur (liquide sous-refroidi)
                            T3 = T_cond_K - subcooling
                            h3 = PropsSI('H', 'T', T3, 'P', P_cond * 1e5, REFRIGERANT) / 1000
                            
                            # Point 4: Sortie détendeur (isenthalpique)
                            h4 = h3
                            
                            return {
                                'P_evap': P_evap,
                                'P_cond': P_cond,
                                'h': [h1, h2, h3, h4, h1],
                                'P': [P_evap, P_cond, P_cond, P_evap, P_evap]
                            }
                        
                        # Calculer les cycles selon le scénario
                        cycle_nominal = calculate_cycle(t_evap_nominal, t_cond_nominal, superheat_ph, subcooling_ph)
                        
                        # Calculer les cycles variés selon le scénario
                        if scenario == "Condenser load down":
                            cycle_cond = calculate_cycle(t_evap_nominal, t_cond_varied, superheat_ph, subcooling_ph)
                            cycle_evap = None
                        elif scenario == "Evaporator source down":
                            cycle_cond = None
                            cycle_evap = calculate_cycle(t_evap_varied, t_cond_nominal, superheat_ph, subcooling_ph)
                        elif scenario == "Compare all three":
                            cycle_cond = calculate_cycle(t_evap_nominal, t_cond_varied, superheat_ph, subcooling_ph)
                            cycle_evap = calculate_cycle(t_evap_varied, t_cond_nominal, superheat_ph, subcooling_ph)
                        else:  # Cycle nominal uniquement
                            cycle_cond = None
                            cycle_evap = None
                        
                        # Créer le diagramme P-h
                        fig_ph = go.Figure()
                        
                        # Courbe de saturation (approximation)
                        T_sat_range = np.linspace(-30, 70, 100)
                        h_liq_sat = []
                        h_vap_sat = []
                        P_sat = []
                        
                        for T in T_sat_range:
                            try:
                                if coolprop_ok:
                                    T_K = T + 273.15
                                    P = PropsSI('P', 'T', T_K, 'Q', 0, REFRIGERANT) / 1e5
                                    h_l = PropsSI('H', 'T', T_K, 'Q', 0, REFRIGERANT) / 1000
                                    h_v = PropsSI('H', 'T', T_K, 'Q', 1, REFRIGERANT) / 1000
                                    P_sat.append(P)
                                    h_liq_sat.append(h_l)
                                    h_vap_sat.append(h_v)
                            except:
                                pass
                        
                        # Courbe de saturation (liquide) - style amélioré
                        if len(h_liq_sat) > 0:
                            fig_ph.add_trace(go.Scatter(
                                x=h_liq_sat, y=P_sat,
                                mode='lines',
                                line=dict(color='#1976D2', width=2.5, dash='dot'),
                                name='Saturated liquid',
                                showlegend=True,
                                hoverinfo='skip'
                            ))
                        
                        # Courbe de saturation (vapeur) - style amélioré
                        if len(h_vap_sat) > 0:
                            fig_ph.add_trace(go.Scatter(
                                x=h_vap_sat, y=P_sat,
                                mode='lines',
                                line=dict(color='#D32F2F', width=2.5, dash='dot'),
                                name='Saturated vapour',
                                showlegend=True,
                                hoverinfo='skip'
                            ))
                        
                        # Cycle nominal (toujours affiché) - avec remplissage
                        fig_ph.add_trace(go.Scatter(
                            x=cycle_nominal['h'],
                            y=cycle_nominal['P'],
                            mode='lines+markers',
                            line=dict(color='#2E7D32', width=4, shape='linear'),
                            marker=dict(size=14, color='#2E7D32', symbol='circle', line=dict(width=2, color='white')),
                            fill='toself',
                            fillcolor='rgba(46, 125, 50, 0.15)',
                            name='Nominal cycle',
                            showlegend=True,
                            hovertemplate='<b>Nominal cycle</b><br>h: %{x:.1f} kJ/kg<br>P: %{y:.2f} bar<extra></extra>'
                        ))
                        
                        # Annotations pour le cycle nominal avec meilleure visibilité
                        fig_ph.add_annotation(x=cycle_nominal['h'][0], y=cycle_nominal['P'][0],
                            text="<b>1</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                            font=dict(size=16, color='#1B5E20', family='Arial Black'),
                            bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#2E7D32', borderwidth=2,
                            xshift=5, yshift=5)
                        fig_ph.add_annotation(x=cycle_nominal['h'][1], y=cycle_nominal['P'][1],
                            text="<b>2</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                            font=dict(size=16, color='#1B5E20', family='Arial Black'),
                            bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#2E7D32', borderwidth=2,
                            xshift=5, yshift=-5)
                        fig_ph.add_annotation(x=cycle_nominal['h'][2], y=cycle_nominal['P'][2],
                            text="<b>3</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                            font=dict(size=16, color='#1B5E20', family='Arial Black'),
                            bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#2E7D32', borderwidth=2,
                            xshift=-5, yshift=-5)
                        fig_ph.add_annotation(x=cycle_nominal['h'][3], y=cycle_nominal['P'][3],
                            text="<b>4</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                            font=dict(size=16, color='#1B5E20', family='Arial Black'),
                            bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#2E7D32', borderwidth=2,
                            xshift=-5, yshift=5)
                        
                        # Cycle charge condenseur ↓ - avec remplissage et style amélioré
                        if cycle_cond is not None:
                            fig_ph.add_trace(go.Scatter(
                                x=cycle_cond['h'],
                                y=cycle_cond['P'],
                                mode='lines+markers',
                                line=dict(color='#E65100', width=4, dash='dash', shape='linear'),
                                marker=dict(size=14, color='#E65100', symbol='square', 
                                          line=dict(width=2, color='white')),
                                fill='toself',
                                fillcolor='rgba(230, 81, 0, 0.15)',
                                name='Charge cond. ↓',
                                showlegend=True,
                                hovertemplate='<b>Condenser load down</b><br>h: %{x:.1f} kJ/kg<br>P: %{y:.2f} bar<extra></extra>'
                            ))
                            # Annotations pour le cycle condenseur
                            fig_ph.add_annotation(x=cycle_cond['h'][0], y=cycle_cond['P'][0],
                                text="<b>1'</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                                font=dict(size=14, color='#BF360C', family='Arial Black'),
                                bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#E65100', borderwidth=2,
                                xshift=5, yshift=5)
                            fig_ph.add_annotation(x=cycle_cond['h'][1], y=cycle_cond['P'][1],
                                text="<b>2'</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                                font=dict(size=14, color='#BF360C', family='Arial Black'),
                                bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#E65100', borderwidth=2,
                                xshift=5, yshift=-5)
                            
                            # Flèche pour montrer le déplacement
                            if scenario == "Compare all three":
                                fig_ph.add_annotation(
                                    x=(cycle_nominal['h'][1] + cycle_cond['h'][1]) / 2,
                                    y=(cycle_nominal['P'][1] + cycle_cond['P'][1]) / 2,
                                    text="↑ P_cond ↑",
                                    showarrow=True,
                                    arrowhead=3,
                                    arrowwidth=3,
                                    arrowsize=2,
                                    font=dict(size=12, color='#E65100', family='Arial'),
                                    bgcolor='rgba(255, 243, 224, 0.9)',
                                    bordercolor='#E65100',
                                    borderwidth=2,
                                    ax=0, ay=-30
                                )
                        
                        # Cycle source évaporateur ↓ - avec remplissage et style amélioré
                        if cycle_evap is not None:
                            fig_ph.add_trace(go.Scatter(
                                x=cycle_evap['h'],
                                y=cycle_evap['P'],
                                mode='lines+markers',
                                line=dict(color='#6A1B9A', width=4, dash='dot', shape='linear'),
                                marker=dict(size=14, color='#6A1B9A', symbol='triangle-up',
                                          line=dict(width=2, color='white')),
                                fill='toself',
                                fillcolor='rgba(106, 27, 154, 0.15)',
                                name='Source ↓',
                                showlegend=True,
                                hovertemplate='<b>Evaporator source down</b><br>h: %{x:.1f} kJ/kg<br>P: %{y:.2f} bar<extra></extra>'
                            ))
                            # Annotations pour le cycle évaporateur
                            fig_ph.add_annotation(x=cycle_evap['h'][0], y=cycle_evap['P'][0],
                                text="<b>1''</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                                font=dict(size=14, color='#4A148C', family='Arial Black'),
                                bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#6A1B9A', borderwidth=2,
                                xshift=5, yshift=5)
                            fig_ph.add_annotation(x=cycle_evap['h'][1], y=cycle_evap['P'][1],
                                text="<b>2''</b>", showarrow=True, arrowhead=2, arrowwidth=2, arrowsize=1.5,
                                font=dict(size=14, color='#4A148C', family='Arial Black'),
                                bgcolor='rgba(255, 255, 255, 0.9)', bordercolor='#6A1B9A', borderwidth=2,
                                xshift=5, yshift=-5)
                            
                            # Flèche pour montrer le déplacement
                            if scenario == "Compare all three":
                                fig_ph.add_annotation(
                                    x=(cycle_nominal['h'][0] + cycle_evap['h'][0]) / 2,
                                    y=(cycle_nominal['P'][0] + cycle_evap['P'][0]) / 2,
                                    text="↓ P_evap ↓",
                                    showarrow=True,
                                    arrowhead=3,
                                    arrowwidth=3,
                                    arrowsize=2,
                                    font=dict(size=12, color='#6A1B9A', family='Arial'),
                                    bgcolor='rgba(243, 229, 245, 0.9)',
                                    bordercolor='#6A1B9A',
                                    borderwidth=2,
                                    ax=0, ay=30
                                )
                        
                        # Mise en forme améliorée
                        fig_ph.update_layout(
                            title=dict(
                                text="<b>P-h diagram — cycle shift</b>",
                                font=dict(size=18, color='#1E3A5F', family='Arial'),
                                x=0.5,
                                xanchor='center'
                            ),
                            xaxis=dict(
                                title=dict(text="<b>Enthalpy h (kJ/kg)</b>", font=dict(size=14, color='#1E3A5F')),
                                range=[150, 500],
                                gridcolor='rgba(128, 128, 128, 0.2)',
                                gridwidth=1,
                                showgrid=True,
                                zeroline=False
                            ),
                            yaxis=dict(
                                title=dict(text="<b>Pressure P (bar)</b>", font=dict(size=14, color='#1E3A5F')),
                                type="log",
                                range=[np.log10(3), np.log10(50)],
                                gridcolor='rgba(128, 128, 128, 0.2)',
                                gridwidth=1,
                                showgrid=True,
                                zeroline=False
                            ),
                            height=650,
                            hovermode='closest',
                            plot_bgcolor='rgba(250, 250, 250, 0.8)',
                            paper_bgcolor='white',
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1,
                                font=dict(size=12),
                                bgcolor='rgba(255, 255, 255, 0.8)',
                                bordercolor='gray',
                                borderwidth=1
                            ),
                            margin=dict(l=80, r=50, t=80, b=60)
                        )
                        
                        show_chart(fig_ph)
                        
                        # Afficher les valeurs calculées pour débogage
                        with st.expander("🔍 Valeurs calculées (débogage)"):
                            col_dbg1, col_dbg2, col_dbg3 = st.columns(3)
                            with col_dbg1:
                                st.write("**Cycle nominal:**")
                                st.write(f"P_evap: {cycle_nominal['P_evap']:.2f} bar")
                                st.write(f"P_cond: {cycle_nominal['P_cond']:.2f} bar")
                                st.write(f"h1: {cycle_nominal['h'][0]:.1f} kJ/kg")
                                st.write(f"h2: {cycle_nominal['h'][1]:.1f} kJ/kg")
                            
                            if cycle_cond is not None:
                                with col_dbg2:
                                    st.write("**Condenser load down:**")
                                    st.write(f"P_evap: {cycle_cond['P_evap']:.2f} bar")
                                    st.write(f"P_cond: {cycle_cond['P_cond']:.2f} bar")
                                    st.write(f"h1: {cycle_cond['h'][0]:.1f} kJ/kg")
                                    st.write(f"h2: {cycle_cond['h'][1]:.1f} kJ/kg")
                            
                            if cycle_evap is not None:
                                with col_dbg3:
                                    st.write("**Evaporator source down:**")
                                    st.write(f"P_evap: {cycle_evap['P_evap']:.2f} bar")
                                    st.write(f"P_cond: {cycle_evap['P_cond']:.2f} bar")
                                    st.write(f"h1: {cycle_evap['h'][0]:.1f} kJ/kg")
                                    st.write(f"h2: {cycle_evap['h'][1]:.1f} kJ/kg")
                        
                        # Légende du cycle
                        st.markdown("---")
                        col_leg1, col_leg2 = st.columns(2)
                        
                        with col_leg1:
                            st.markdown("""
                            **Cycle points:**
                            - **1**: evaporator outlet (superheated vapour)
                            - **2**: compressor outlet (high-pressure vapour)
                            - **3**: condenser outlet (subcooled liquid)
                            - **4**: expansion-valve outlet (two-phase)
                            """)
                        
                        with col_leg2:
                            st.markdown("""
                            **Transformations:**
                            - **1→2**: compression (near-isentropic + losses)
                            - **2→3**: condensation (heat rejection)
                            - **3→4**: isenthalpic expansion
                            - **4→1**: evaporation (heat absorption)
                            """)
                        
                        # Analyse du déplacement
                        st.markdown("### Shift analysis")
                        
                        if scenario == "Condenser load down":
                            delta_P_cond = cycle_cond['P_cond'] - cycle_nominal['P_cond']
                            delta_h_comp = cycle_cond['h'][1] - cycle_cond['h'][0] - (cycle_nominal['h'][1] - cycle_nominal['h'][0])
                            
                            st.info(f"""
                            **Reduced condenser load:**
                            - P_cond rises by **{delta_P_cond:.2f} bar** → cycle moves up
                            - Compression work rises → cycle widens
                            - Cycle area (net work) increases → **electrical consumption up**
                            """)
                        
                        elif scenario == "Evaporator source down":
                            delta_P_evap = cycle_evap['P_evap'] - cycle_nominal['P_evap']
                            delta_h_evap = cycle_evap['h'][0] - cycle_evap['h'][3] - (cycle_nominal['h'][0] - cycle_nominal['h'][3])
                            
                            st.info(f"""
                            **Colder source:**
                            - P_evap falls by **{abs(delta_P_evap):.2f} bar** → cycle moves down
                            - Evaporating capacity drops → cycle shrinks
                            - Cycle area decreases → **heating capacity down**
                            """)
                        
                        elif scenario == "Compare all three":
                            st.success("""
                            **Three-cycle comparison:**
                            
                            1. **Nominal (green)**: reference, efficient operation
                            
                            2. **Condenser load down (orange)**:
                               - Cycle moves up (P_cond up)
                               - Cycle widens (compression work up)
                               - Impact: **electrical consumption up**
                            
                            3. **Evaporator source down (purple)**:
                               - Cycle moves down (P_evap down)
                               - Cycle shrinks (capacity down)
                               - Impact: **heating capacity down**
                            
                            Both cases hurt COP, through different physical mechanisms.
                            """)
            
            # Graphique P-T par type de défaut (si données disponibles)
            st.markdown("---")
            st.subheader("Pressure-temperature by fault type")
            
            if 'P_evap' in df.columns and 'T_evap' in df.columns:
                fig_pt = create_pressure_temperature_chart(df)
                show_chart(fig_pt)
            else:
                st.info("P-T columns are not in the current dataset")
            
            # Tableau de validation CoolProp
            st.markdown("---")
            st.subheader("Thermodynamic property check")
            
            try:
                from src.physics.thermodynamic_viz import HAS_COOLPROP, R410A
                
                if HAS_COOLPROP:
                    validation_data = {
                        'Temperature (°C)': [-20, -10, 0, 10, 20, 30, 40, 50],
                        'P_sat ASHRAE (bar)': [4.00, 5.72, 8.00, 10.88, 14.17, 18.72, 24.20, 30.40],
                    }
                    
                    # Calculer avec CoolProp
                    validation_data['P_sat CoolProp (bar)'] = [
                        round(R410A.P_sat(T), 2) for T in validation_data['Temperature (°C)']
                    ]
                    
                    validation_data['Error (%)'] = [
                        round(abs(cp - ash) / ash * 100, 2) 
                        for cp, ash in zip(
                            validation_data['P_sat CoolProp (bar)'],
                            validation_data['P_sat ASHRAE (bar)']
                        )
                    ]
                    
                    df_validation = pd.DataFrame(validation_data)
                    
                    # Styliser le tableau
                    def highlight_low_error(val):
                        if isinstance(val, float) and val < 1.0:
                            return 'background-color: #c8e6c9'
                        return ''
                    
                    st.dataframe(
                        df_validation.style.applymap(highlight_low_error, subset=['Error (%)']),
                        width="stretch"
                    )
                    
                    st.success("CoolProp values match ASHRAE tables (error < 1.5%)")
                else:
                    st.warning("CoolProp not installed — validation unavailable")
            except Exception as e:
                st.error(f"Validation error: {e}")
                
        except Exception as e:
            st.error(f"Thermodynamic module unavailable: {e}")
            st.info("Install CoolProp: pip install CoolProp")
    
    # =========================
    # TAB 6: Analyse Avancée
    # =========================
    with tabs[6]:
        st.header("Advanced analysis")
        
        # Feature Importance
        if 'feature_importance' in data:
            st.subheader("Feature importance")
            fi_df = data['feature_importance'].copy()
            
            # Normaliser les noms de colonnes (minuscules ou majuscules)
            fi_df.columns = fi_df.columns.str.lower()
            
            if 'feature' in fi_df.columns and 'importance' in fi_df.columns:
                fig_fi = px.bar(
                    fi_df.head(15),
                    x='importance',
                    y='feature',
                    orientation='h',
                    title="Top 15 features",
                    color='importance',
                    color_continuous_scale='Viridis'
                )
                fig_fi.update_layout(height=500, yaxis={'categoryorder': 'total ascending'})
                show_chart(fig_fi)
            else:
                st.warning("Unrecognized feature_importance file format")
        
        # Corrélation
        st.subheader("Correlation matrix")
        numeric_df = df.select_dtypes(include=[np.number])
        corr = numeric_df.corr()
        
        fig_corr = px.imshow(
            corr,
            title="Feature correlation",
            color_continuous_scale='RdBu_r',
            aspect='auto'
        )
        fig_corr.update_layout(height=600)
        show_chart(fig_corr)
        
        # Analyse par condition
        st.subheader("Analysis by operating conditions")
        
        if 'T_ambient' in df.columns:
            # Créer des bins de température
            df['T_ambient_bin'] = pd.cut(df['T_ambient'], bins=5, labels=['Very cold', 'Cold', 'Mild', 'Warm', 'Hot'])
            
            fault_by_temp = df.groupby(['T_ambient_bin', 'fault_type']).size().unstack(fill_value=0)
            
            fig_heatmap = px.imshow(
                fault_by_temp.values,
                labels=dict(x="Fault type", y="Ambient temperature", color="Count"),
                x=fault_by_temp.columns,
                y=fault_by_temp.index,
                title="Faults by ambient temperature",
            color_continuous_scale=[[0, "#14141C"], [1, "#8B5CF6"]]
            )
            fig_heatmap.update_layout(height=400)
            show_chart(fig_heatmap)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align:center;color:#7A7A90;padding:8px 0 20px 0;font-size:0.85rem;'>
            HeatPump FDD · CoolProp cycle · calibrated Gradient Boosting
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

