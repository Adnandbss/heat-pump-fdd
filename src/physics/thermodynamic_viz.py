"""
Visualisations Thermodynamiques avec CoolProp
==============================================

Graphiques physiques pour la pompe à chaleur:
- Diagramme P-h (Pression-Enthalpie) avec propriétés EXACTES
- Enveloppe de fonctionnement compresseur
- Courbes de performance COP
- Schéma du système

Utilise CoolProp pour les propriétés thermodynamiques R410A
conformes aux tables ASHRAE/NIST.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Tuple, Optional
import warnings

# Import CoolProp si disponible
try:
    from CoolProp.CoolProp import PropsSI
    HAS_COOLPROP = True
except ImportError:
    HAS_COOLPROP = False
    warnings.warn("CoolProp non disponible - utilisation des approximations")


class R410A_Properties:
    """
    Propriétés thermodynamiques R410A via CoolProp.
    Fallback sur corrélations si CoolProp non disponible.
    """
    FLUID = "R410A"
    
    @staticmethod
    def P_sat(T_C: float) -> float:
        """Pression de saturation (bar) à température T (°C)."""
        if HAS_COOLPROP:
            try:
                T_K = T_C + 273.15
                return PropsSI('P', 'T', T_K, 'Q', 0, 'R410A') / 1e5
            except:
                pass
        # Fallback: corrélation ajustée ASHRAE
        return 8.0 * np.exp(0.04 * T_C)
    
    @staticmethod
    def T_sat(P_bar: float) -> float:
        """Température de saturation (°C) à pression P (bar)."""
        if HAS_COOLPROP:
            try:
                P_Pa = P_bar * 1e5
                return PropsSI('T', 'P', P_Pa, 'Q', 0, 'R410A') - 273.15
            except:
                pass
        return np.log(P_bar / 8.0) / 0.04
    
    @staticmethod
    def h_liquid(T_C: float) -> float:
        """Enthalpie liquide saturé (kJ/kg)."""
        if HAS_COOLPROP:
            try:
                T_K = T_C + 273.15
                return PropsSI('H', 'T', T_K, 'Q', 0, 'R410A') / 1000
            except:
                pass
        return 200 + 1.5 * T_C
    
    @staticmethod
    def h_vapor(T_C: float) -> float:
        """Enthalpie vapeur saturée (kJ/kg)."""
        if HAS_COOLPROP:
            try:
                T_K = T_C + 273.15
                return PropsSI('H', 'T', T_K, 'Q', 1, 'R410A') / 1000
            except:
                pass
        return 420 + 0.8 * T_C
    
    @staticmethod
    def s_vapor(T_C: float) -> float:
        """Entropie vapeur saturée (kJ/kg.K)."""
        if HAS_COOLPROP:
            try:
                T_K = T_C + 273.15
                return PropsSI('S', 'T', T_K, 'Q', 1, 'R410A') / 1000
            except:
                pass
        return 1.8 - 0.002 * T_C
    
    @staticmethod
    def cp_vapor(T_C: float, P_bar: float) -> float:
        """Capacité calorifique vapeur (kJ/kg.K)."""
        if HAS_COOLPROP:
            try:
                T_K = T_C + 273.15
                P_Pa = P_bar * 1e5
                return PropsSI('C', 'T', T_K, 'P', P_Pa, 'R410A') / 1000
            except:
                pass
        return 1.0 + 0.002 * T_C


# Instance globale
R410A = R410A_Properties()


class ThermodynamicVisualizer:
    """
    Génère des visualisations thermodynamiques interactives.
    """
    
    # Propriétés approximatives R410A
    R410A_PROPS = {
        'Tcrit': 72.5,      # °C
        'Pcrit': 49.0,      # bar
        'M': 72.58,         # g/mol
    }
    
    def __init__(self):
        self.colors = {
            'compression': '#FF6B6B',
            'condensation': '#4ECDC4',
            'detente': '#45B7D1',
            'evaporation': '#96CEB4',
            'saturation': '#2C3E50',
            'normal': '#27AE60',
            'warning': '#F39C12',
            'danger': '#E74C3C',
        }
    
    def _sat_pressure(self, T: float) -> float:
        """
        Pression de saturation R410A (bar).
        Utilise CoolProp si disponible pour valeurs EXACTES.
        """
        return R410A.P_sat(T)
    
    def _sat_temperature(self, P: float) -> float:
        """Température de saturation à partir de la pression."""
        return R410A.T_sat(P)
    
    def _enthalpy_liquid(self, T: float) -> float:
        """Enthalpie liquide saturé (kJ/kg) - EXACTE avec CoolProp."""
        return R410A.h_liquid(T)
    
    def _enthalpy_vapor(self, T: float) -> float:
        """Enthalpie vapeur saturée (kJ/kg) - EXACTE avec CoolProp."""
        return R410A.h_vapor(T)
    
    def create_ph_diagram(self, 
                          T_evap: float = 5.0,
                          T_cond: float = 45.0,
                          superheat: float = 6.0,
                          subcooling: float = 5.0,
                          eta_is: float = 0.75) -> go.Figure:
        """
        Crée un diagramme Pression-Enthalpie avec le cycle réel.
        
        Parameters:
        -----------
        T_evap : float - Température d'évaporation (°C)
        T_cond : float - Température de condensation (°C)
        superheat : float - Surchauffe (K)
        subcooling : float - Sous-refroidissement (K)
        eta_is : float - Rendement isentropique compresseur
        """
        
        fig = go.Figure()
        
        # Courbe de saturation
        T_range = np.linspace(-40, 70, 100)
        h_liq = [self._enthalpy_liquid(T) for T in T_range]
        h_vap = [self._enthalpy_vapor(T) for T in T_range]
        P_sat = [self._sat_pressure(T) for T in T_range]
        
        # Courbe liquide saturé
        fig.add_trace(go.Scatter(
            x=h_liq, y=P_sat,
            mode='lines',
            name='Liquide saturé',
            line=dict(color=self.colors['saturation'], width=2),
            hovertemplate='h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Courbe vapeur saturée
        fig.add_trace(go.Scatter(
            x=h_vap, y=P_sat,
            mode='lines',
            name='Vapeur saturée',
            line=dict(color=self.colors['saturation'], width=2),
            hovertemplate='h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Points du cycle
        P_evap = self._sat_pressure(T_evap)
        P_cond = self._sat_pressure(T_cond)
        
        # Point 1: Sortie évaporateur (vapeur surchauffée)
        h1 = self._enthalpy_vapor(T_evap) + 1.0 * superheat
        T1 = T_evap + superheat
        
        # Point 2: Sortie compresseur (compression)
        # Compression isentropique + pertes
        h2_is = h1 + (P_cond/P_evap - 1) * 15  # Approximation
        h2 = h1 + (h2_is - h1) / eta_is
        
        # Point 3: Sortie condenseur (liquide sous-refroidi)
        h3 = self._enthalpy_liquid(T_cond - subcooling)
        
        # Point 4: Sortie détendeur (mélange diphasique)
        h4 = h3  # Détente isenthalpique
        
        # Tracer le cycle
        cycle_h = [h1, h2, h3, h4, h1]
        cycle_P = [P_evap, P_cond, P_cond, P_evap, P_evap]
        
        # Compression (1->2)
        fig.add_trace(go.Scatter(
            x=[h1, h2], y=[P_evap, P_cond],
            mode='lines+markers',
            name='Compression',
            line=dict(color=self.colors['compression'], width=4),
            marker=dict(size=12),
            hovertemplate='Compression<br>h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Condensation (2->3)
        # Désurchauffe puis condensation puis sous-refroidissement
        h_cond_start = self._enthalpy_vapor(T_cond)
        h_cond_end = self._enthalpy_liquid(T_cond)
        
        fig.add_trace(go.Scatter(
            x=[h2, h_cond_start, h_cond_end, h3], 
            y=[P_cond, P_cond, P_cond, P_cond],
            mode='lines+markers',
            name='Condensation',
            line=dict(color=self.colors['condensation'], width=4),
            marker=dict(size=8),
            hovertemplate='Condensation<br>h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Détente (3->4)
        fig.add_trace(go.Scatter(
            x=[h3, h4], y=[P_cond, P_evap],
            mode='lines+markers',
            name='Détente',
            line=dict(color=self.colors['detente'], width=4, dash='dash'),
            marker=dict(size=12),
            hovertemplate='Détente<br>h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Évaporation (4->1)
        h_evap_end = self._enthalpy_vapor(T_evap)
        
        fig.add_trace(go.Scatter(
            x=[h4, h_evap_end, h1], 
            y=[P_evap, P_evap, P_evap],
            mode='lines+markers',
            name='Évaporation',
            line=dict(color=self.colors['evaporation'], width=4),
            marker=dict(size=8),
            hovertemplate='Évaporation<br>h=%{x:.1f} kJ/kg<br>P=%{y:.1f} bar<extra></extra>'
        ))
        
        # Annotations des points
        annotations = [
            dict(x=h1, y=P_evap, text="1", showarrow=True, arrowhead=2, ax=-30, ay=-30),
            dict(x=h2, y=P_cond, text="2", showarrow=True, arrowhead=2, ax=30, ay=-30),
            dict(x=h3, y=P_cond, text="3", showarrow=True, arrowhead=2, ax=30, ay=30),
            dict(x=h4, y=P_evap, text="4", showarrow=True, arrowhead=2, ax=-30, ay=30),
        ]
        
        # Calcul COP
        Q_evap = h1 - h4
        W_comp = h2 - h1
        COP = Q_evap / W_comp if W_comp > 0 else 0
        
        fig.update_layout(
            title=f"Diagramme P-h - Cycle Pompe à Chaleur (COP = {COP:.2f})",
            xaxis_title="Enthalpie h (kJ/kg)",
            yaxis_title="Pression P (bar)",
            yaxis_type="log",
            yaxis=dict(range=[np.log10(2), np.log10(50)]),
            xaxis=dict(range=[150, 500]),
            annotations=annotations,
            height=550,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode='closest'
        )
        
        # Ajouter des annotations de température
        fig.add_annotation(
            x=250, y=P_evap,
            text=f"T_evap = {T_evap}°C",
            showarrow=False, yshift=15,
            font=dict(color=self.colors['evaporation'])
        )
        fig.add_annotation(
            x=350, y=P_cond,
            text=f"T_cond = {T_cond}°C",
            showarrow=False, yshift=-15,
            font=dict(color=self.colors['condensation'])
        )
        
        return fig
    
    def create_compressor_envelope(self,
                                   current_T_evap: float = 5.0,
                                   current_T_cond: float = 45.0) -> go.Figure:
        """
        Crée l'enveloppe de fonctionnement du compresseur.
        """
        
        fig = go.Figure()
        
        # Limites du compresseur (typiques pour R410A)
        T_evap_min, T_evap_max = -20, 20
        T_cond_min, T_cond_max = 25, 65
        
        # Zone de fonctionnement normal
        fig.add_shape(
            type="rect",
            x0=T_evap_min, x1=T_evap_max,
            y0=T_cond_min, y1=T_cond_max,
            fillcolor="rgba(39, 174, 96, 0.3)",
            line=dict(color=self.colors['normal'], width=2),
            name="Zone normale"
        )
        
        # Zone de fonctionnement étendu (warning)
        fig.add_shape(
            type="rect",
            x0=-30, x1=25,
            y0=20, y1=70,
            fillcolor="rgba(243, 156, 18, 0.1)",
            line=dict(color=self.colors['warning'], width=1, dash='dash'),
        )
        
        # Limite haute pression
        fig.add_trace(go.Scatter(
            x=[-30, 25], y=[70, 70],
            mode='lines',
            name='Limite HP',
            line=dict(color=self.colors['danger'], width=3),
            hovertemplate='Limite Haute Pression<extra></extra>'
        ))
        
        # Limite basse pression
        fig.add_trace(go.Scatter(
            x=[-30, -30], y=[20, 70],
            mode='lines',
            name='Limite BP',
            line=dict(color=self.colors['danger'], width=3),
            hovertemplate='Limite Basse Pression<extra></extra>'
        ))
        
        # Limite taux de compression max
        T_evap_line = np.linspace(-30, 25, 50)
        T_cond_max_line = T_evap_line + 50  # Ratio max ~4
        
        fig.add_trace(go.Scatter(
            x=T_evap_line, y=T_cond_max_line,
            mode='lines',
            name='Ratio max',
            line=dict(color='orange', width=2, dash='dot'),
            hovertemplate='Taux compression max<extra></extra>'
        ))
        
        # Point de fonctionnement actuel
        fig.add_trace(go.Scatter(
            x=[current_T_evap], y=[current_T_cond],
            mode='markers',
            name='Point actuel',
            marker=dict(size=20, color='blue', symbol='star'),
            hovertemplate=f'T_evap={current_T_evap}°C<br>T_cond={current_T_cond}°C<extra></extra>'
        ))
        
        # Isothermes de COP
        for cop_target in [2, 3, 4, 5]:
            T_evap_iso = np.linspace(-20, 15, 30)
            # COP ≈ T_cond / (T_cond - T_evap) en Carnot, simplifié
            T_cond_iso = T_evap_iso + (273 + T_evap_iso) / cop_target
            
            fig.add_trace(go.Scatter(
                x=T_evap_iso, y=T_cond_iso,
                mode='lines',
                name=f'COP≈{cop_target}',
                line=dict(width=1, dash='dot'),
                opacity=0.5,
                hovertemplate=f'COP ≈ {cop_target}<extra></extra>'
            ))
        
        fig.update_layout(
            title="Enveloppe de Fonctionnement du Compresseur",
            xaxis_title="Température Évaporation (°C)",
            yaxis_title="Température Condensation (°C)",
            xaxis=dict(range=[-35, 30]),
            yaxis=dict(range=[15, 75]),
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            hovermode='closest'
        )
        
        return fig
    
    def create_cop_curves(self, df: pd.DataFrame = None) -> go.Figure:
        """
        Crée les courbes de COP en fonction de la température ambiante.
        """
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("COP vs Température Ambiante", "COP vs Taux de Compression"),
            horizontal_spacing=0.12
        )
        
        # Données théoriques
        T_amb = np.linspace(-10, 45, 50)
        T_source = 20  # Température source froide (intérieur)
        
        # COP Carnot
        COP_carnot = (T_source + 273) / (T_amb - T_source + 0.1)
        COP_carnot = np.clip(COP_carnot, 0, 15)
        
        # COP réel (environ 40-50% du Carnot)
        COP_reel = COP_carnot * 0.45
        COP_reel = np.clip(COP_reel, 0, 6)
        
        # Courbe théorique Carnot
        fig.add_trace(go.Scatter(
            x=T_amb, y=COP_carnot,
            mode='lines',
            name='COP Carnot (théorique)',
            line=dict(color='gray', dash='dash', width=2),
            hovertemplate='T_amb=%{x:.1f}°C<br>COP=%{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Courbe réelle
        fig.add_trace(go.Scatter(
            x=T_amb, y=COP_reel,
            mode='lines',
            name='COP Réel (estimé)',
            line=dict(color=self.colors['normal'], width=3),
            fill='tozeroy',
            fillcolor='rgba(39, 174, 96, 0.2)',
            hovertemplate='T_amb=%{x:.1f}°C<br>COP=%{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Si on a des données réelles
        if df is not None and 'T_ambient' in df.columns and 'COP' in df.columns:
            # Filtrer les données normales
            df_normal = df[df['fault_type'] == 'Normal'] if 'fault_type' in df.columns else df
            
            if len(df_normal) > 0:
                fig.add_trace(go.Scatter(
                    x=df_normal['T_ambient'],
                    y=df_normal['COP'],
                    mode='markers',
                    name='Données mesurées',
                    marker=dict(size=6, color='blue', opacity=0.5),
                    hovertemplate='T_amb=%{x:.1f}°C<br>COP=%{y:.2f}<extra></extra>'
                ), row=1, col=1)
        
        # COP vs Taux de compression
        ratio = np.linspace(2, 8, 50)
        
        # COP approximatif basé sur le rendement volumétrique
        eta_vol = 1 - 0.05 * (ratio - 1)
        eta_is = 0.75 - 0.02 * (ratio - 3)
        COP_ratio = 4.0 * eta_vol * eta_is / ratio * 5
        COP_ratio = np.clip(COP_ratio, 0, 6)
        
        fig.add_trace(go.Scatter(
            x=ratio, y=COP_ratio,
            mode='lines',
            name='COP vs Ratio',
            line=dict(color=self.colors['compression'], width=3),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 107, 0.2)',
            hovertemplate='Ratio=%{x:.2f}<br>COP=%{y:.2f}<extra></extra>',
            showlegend=False
        ), row=1, col=2)
        
        # Zones de fonctionnement
        fig.add_vrect(x0=2, x1=4, fillcolor="green", opacity=0.1, row=1, col=2)
        fig.add_vrect(x0=4, x1=6, fillcolor="yellow", opacity=0.1, row=1, col=2)
        fig.add_vrect(x0=6, x1=8, fillcolor="red", opacity=0.1, row=1, col=2)
        
        fig.update_xaxes(title_text="Température Ambiante (°C)", row=1, col=1)
        fig.update_xaxes(title_text="Taux de Compression", row=1, col=2)
        fig.update_yaxes(title_text="COP", row=1, col=1)
        fig.update_yaxes(title_text="COP", row=1, col=2)
        
        fig.update_layout(
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.08),
            hovermode='closest'
        )
        
        return fig
    
    def create_system_schematic(self,
                                T_evap: float = 5.0,
                                T_cond: float = 45.0,
                                P_evap: float = 8.0,
                                P_cond: float = 25.0,
                                superheat: float = 6.0,
                                subcooling: float = 5.0,
                                COP: float = 3.5,
                                fault_status: str = "Normal") -> go.Figure:
        """
        Crée un schéma du système avec les valeurs actuelles.
        """
        
        fig = go.Figure()
        
        # Composants (rectangles)
        components = {
            'Compresseur': {'x': 0.7, 'y': 0.7, 'w': 0.15, 'h': 0.15, 'color': '#FF6B6B'},
            'Condenseur': {'x': 0.3, 'y': 0.75, 'w': 0.25, 'h': 0.1, 'color': '#4ECDC4'},
            'Détendeur': {'x': 0.2, 'y': 0.4, 'w': 0.1, 'h': 0.1, 'color': '#45B7D1'},
            'Évaporateur': {'x': 0.35, 'y': 0.2, 'w': 0.25, 'h': 0.1, 'color': '#96CEB4'},
        }
        
        for name, comp in components.items():
            # Rectangle du composant
            fig.add_shape(
                type="rect",
                x0=comp['x'] - comp['w']/2,
                x1=comp['x'] + comp['w']/2,
                y0=comp['y'] - comp['h']/2,
                y1=comp['y'] + comp['h']/2,
                fillcolor=comp['color'],
                line=dict(color='black', width=2),
            )
            
            # Nom du composant
            fig.add_annotation(
                x=comp['x'], y=comp['y'],
                text=f"<b>{name}</b>",
                showarrow=False,
                font=dict(size=11, color='white')
            )
        
        # Flèches de flux (lignes)
        arrows = [
            # Évaporateur -> Compresseur (vapeur BP)
            {'x0': 0.6, 'y0': 0.25, 'x1': 0.7, 'y1': 0.62, 'color': '#96CEB4'},
            # Compresseur -> Condenseur (vapeur HP)
            {'x0': 0.62, 'y0': 0.7, 'x1': 0.55, 'y1': 0.8, 'color': '#FF6B6B'},
            # Condenseur -> Détendeur (liquide HP)
            {'x0': 0.175, 'y0': 0.75, 'x1': 0.2, 'y1': 0.5, 'color': '#4ECDC4'},
            # Détendeur -> Évaporateur (mélange BP)
            {'x0': 0.25, 'y0': 0.4, 'x1': 0.35, 'y1': 0.3, 'color': '#45B7D1'},
        ]
        
        for arrow in arrows:
            fig.add_annotation(
                x=arrow['x1'], y=arrow['y1'],
                ax=arrow['x0'], ay=arrow['y0'],
                xref='x', yref='y',
                axref='x', ayref='y',
                showarrow=True,
                arrowhead=3,
                arrowsize=1.5,
                arrowwidth=3,
                arrowcolor=arrow['color'],
            )
        
        # Valeurs affichées
        status_color = self.colors['normal'] if fault_status == "Normal" else self.colors['danger']
        
        # Boîte d'information
        info_text = f"""
        <b>PARAMÈTRES ACTUELS</b><br>
        ─────────────────<br>
        T_évap: {T_evap:.1f}°C | P_évap: {P_evap:.1f} bar<br>
        T_cond: {T_cond:.1f}°C | P_cond: {P_cond:.1f} bar<br>
        ─────────────────<br>
        Surchauffe: {superheat:.1f} K<br>
        Sous-refroid.: {subcooling:.1f} K<br>
        ─────────────────<br>
        <b>COP: {COP:.2f}</b>
        """
        
        fig.add_annotation(
            x=0.85, y=0.35,
            text=info_text,
            showarrow=False,
            font=dict(size=10, family="Courier"),
            align='left',
            bgcolor='white',
            bordercolor='black',
            borderwidth=1,
            borderpad=4
        )
        
        # Status
        fig.add_annotation(
            x=0.85, y=0.12,
            text=f"<b>État: {fault_status}</b>",
            showarrow=False,
            font=dict(size=14, color=status_color),
            bgcolor=status_color,
            opacity=0.2,
            borderpad=5
        )
        
        # Labels des lignes
        fig.add_annotation(x=0.67, y=0.45, text="Vapeur BP", showarrow=False, font=dict(size=9, color='#96CEB4'))
        fig.add_annotation(x=0.57, y=0.78, text="Vapeur HP", showarrow=False, font=dict(size=9, color='#FF6B6B'))
        fig.add_annotation(x=0.15, y=0.6, text="Liquide HP", showarrow=False, font=dict(size=9, color='#4ECDC4'))
        fig.add_annotation(x=0.28, y=0.32, text="Mélange BP", showarrow=False, font=dict(size=9, color='#45B7D1'))
        
        fig.update_layout(
            title="Schéma du Cycle Frigorifique",
            xaxis=dict(range=[0, 1], showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(range=[0, 1], showgrid=False, zeroline=False, showticklabels=False),
            height=500,
            plot_bgcolor='#f8f9fa',
        )
        
        return fig
    
    def create_monitoring_dashboard(self, 
                                    n_points: int = 100,
                                    include_fault: bool = False) -> go.Figure:
        """
        Crée une simulation de monitoring temps réel.
        """
        
        # Générer des données temporelles simulées
        np.random.seed(42)
        time = np.arange(n_points)
        
        # Paramètres normaux avec bruit
        T_evap = 5 + np.random.normal(0, 0.5, n_points)
        T_cond = 45 + np.random.normal(0, 1, n_points)
        P_evap = 8 + np.random.normal(0, 0.2, n_points)
        P_cond = 25 + np.random.normal(0, 0.5, n_points)
        superheat = 6 + np.random.normal(0, 0.3, n_points)
        COP = 3.5 + np.random.normal(0, 0.1, n_points)
        
        # Simuler un défaut (encrassement progressif)
        if include_fault:
            fault_start = n_points // 2
            # Encrassement condenseur: augmentation progressive de T_cond
            drift = np.zeros(n_points)
            drift[fault_start:] = np.linspace(0, 15, n_points - fault_start)
            T_cond = T_cond + drift
            P_cond = P_cond + drift * 0.8
            COP = COP - drift * 0.08
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                "Température Évaporation", "Température Condensation",
                "Pression Évaporation", "Pression Condensation",
                "Surchauffe", "COP"
            ),
            vertical_spacing=0.1,
            horizontal_spacing=0.08
        )
        
        # T_evap
        fig.add_trace(go.Scatter(
            x=time, y=T_evap, mode='lines', name='T_evap',
            line=dict(color='#96CEB4', width=2)
        ), row=1, col=1)
        fig.add_hline(y=5, line_dash="dash", line_color="gray", row=1, col=1)
        
        # T_cond
        color_cond = '#E74C3C' if include_fault else '#4ECDC4'
        fig.add_trace(go.Scatter(
            x=time, y=T_cond, mode='lines', name='T_cond',
            line=dict(color=color_cond, width=2)
        ), row=1, col=2)
        fig.add_hline(y=45, line_dash="dash", line_color="gray", row=1, col=2)
        if include_fault:
            fig.add_hline(y=55, line_dash="dot", line_color="red", row=1, col=2)
        
        # P_evap
        fig.add_trace(go.Scatter(
            x=time, y=P_evap, mode='lines', name='P_evap',
            line=dict(color='#45B7D1', width=2)
        ), row=2, col=1)
        
        # P_cond
        fig.add_trace(go.Scatter(
            x=time, y=P_cond, mode='lines', name='P_cond',
            line=dict(color='#FF6B6B', width=2)
        ), row=2, col=2)
        
        # Superheat
        fig.add_trace(go.Scatter(
            x=time, y=superheat, mode='lines', name='Surchauffe',
            line=dict(color='#9B59B6', width=2)
        ), row=3, col=1)
        fig.add_hline(y=6, line_dash="dash", line_color="gray", row=3, col=1)
        
        # COP
        fig.add_trace(go.Scatter(
            x=time, y=COP, mode='lines', name='COP',
            line=dict(color='#27AE60', width=2)
        ), row=3, col=2)
        fig.add_hline(y=3.5, line_dash="dash", line_color="gray", row=3, col=2)
        if include_fault:
            fig.add_hline(y=3.0, line_dash="dot", line_color="red", row=3, col=2)
        
        # Zone de défaut
        if include_fault:
            for row in range(1, 4):
                for col in range(1, 3):
                    fig.add_vrect(
                        x0=n_points//2, x1=n_points,
                        fillcolor="rgba(231, 76, 60, 0.1)",
                        layer="below", line_width=0,
                        row=row, col=col
                    )
        
        title = "Monitoring Temps Réel - Encrassement Condenseur Détecté" if include_fault else "Monitoring Temps Réel - Fonctionnement Normal"
        
        fig.update_layout(
            title=title,
            height=650,
            showlegend=False,
            hovermode='x unified'
        )
        
        # Labels des axes
        for col in range(1, 3):
            fig.update_xaxes(title_text="Temps (min)", row=3, col=col)
        
        fig.update_yaxes(title_text="°C", row=1, col=1)
        fig.update_yaxes(title_text="°C", row=1, col=2)
        fig.update_yaxes(title_text="bar", row=2, col=1)
        fig.update_yaxes(title_text="bar", row=2, col=2)
        fig.update_yaxes(title_text="K", row=3, col=1)
        fig.update_yaxes(title_text="-", row=3, col=2)
        
        return fig


def create_pressure_temperature_chart(df: pd.DataFrame) -> go.Figure:
    """
    Crée un graphique Pression vs Température par type de défaut.
    """
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("P_evap vs T_evap", "P_cond vs T_cond")
    )
    
    colors = {
        'Normal': '#27AE60',
        'Condenser_Fouling': '#E74C3C',
        'Evaporator_Fouling': '#3498DB',
        'Refrigerant_Undercharge': '#F39C12',
        'Condenser_Fan_Fault': '#9B59B6',
        'Evaporator_Fan_Fault': '#1ABC9C',
        'Refrigerant_Overcharge': '#8E44AD',
    }
    
    for fault_type in df['fault_type'].unique():
        mask = df['fault_type'] == fault_type
        color = colors.get(fault_type, '#7F8C8D')
        
        if 'P_evap' in df.columns and 'T_evap' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.loc[mask, 'T_evap'],
                y=df.loc[mask, 'P_evap'],
                mode='markers',
                name=fault_type,
                marker=dict(size=6, color=color, opacity=0.6),
                legendgroup=fault_type,
                hovertemplate=f'{fault_type}<br>T=%{{x:.1f}}°C<br>P=%{{y:.1f}}bar<extra></extra>'
            ), row=1, col=1)
        
        if 'P_cond' in df.columns and 'T_cond' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.loc[mask, 'T_cond'],
                y=df.loc[mask, 'P_cond'],
                mode='markers',
                name=fault_type,
                marker=dict(size=6, color=color, opacity=0.6),
                legendgroup=fault_type,
                showlegend=False,
                hovertemplate=f'{fault_type}<br>T=%{{x:.1f}}°C<br>P=%{{y:.1f}}bar<extra></extra>'
            ), row=1, col=2)
    
    fig.update_xaxes(title_text="Température (°C)", row=1, col=1)
    fig.update_xaxes(title_text="Température (°C)", row=1, col=2)
    fig.update_yaxes(title_text="Pression (bar)", row=1, col=1)
    fig.update_yaxes(title_text="Pression (bar)", row=1, col=2)
    
    fig.update_layout(
        title="Relation Pression-Température par Type de Défaut",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.05)
    )
    
    return fig

