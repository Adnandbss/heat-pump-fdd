"""
Visualisations pour FDD (Fault Detection & Diagnostics)
========================================================

Ce module fournit des visualisations professionnelles pour:
- Matrices de confusion
- Courbes ROC et AUC
- Importance des features
- Distribution des données
- Comparaison des modèles
- Diagrammes thermodynamiques (P-h)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import seaborn as sns

# Style professionnel
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'primary': '#2E86AB',      # Bleu profond
    'secondary': '#A23B72',    # Magenta
    'success': '#F18F01',      # Orange
    'danger': '#C73E1D',       # Rouge
    'neutral': '#3B1F2B',      # Noir-brun
    'light': '#E8E8E8',        # Gris clair
    'normal': '#2ECC71',       # Vert
    'fault': '#E74C3C',        # Rouge
}

CLASS_COLORS = {
    'Normal': '#2ECC71',
    'Condenser_Fouling': '#E74C3C',
    'Evaporator_Fouling': '#3498DB',
    'Refrigerant_Undercharge': '#F39C12',
    'Refrigerant_Overcharge': '#9B59B6',
    'Condenser_Fan_Fault': '#1ABC9C',
    'Evaporator_Fan_Fault': '#E91E63',
    'Compressor_Valve_Leak': '#795548',
    # Anciennes classes compatibles
    'Condenser_Fault': '#E74C3C',
    'Evaporator_Fault': '#3498DB',
}


class FDDVisualizer:
    """
    Classe de visualisation pour l'analyse FDD.
    
    Génère des graphiques publication-ready pour les résultats
    de diagnostic de défauts sur pompes à chaleur.
    """
    
    def __init__(self, figsize: Tuple[int, int] = (10, 8), dpi: int = 100):
        self.figsize = figsize
        self.dpi = dpi
        self.figures = {}
    
    def plot_confusion_matrix(
        self,
        cm: np.ndarray,
        class_names: List[str],
        title: str = "Matrice de Confusion",
        normalize: bool = True,
        cmap: str = 'Blues',
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche une matrice de confusion stylisée.
        
        Parameters:
        -----------
        cm : np.ndarray
            Matrice de confusion
        class_names : List[str]
            Noms des classes
        title : str
            Titre du graphique
        normalize : bool
            Normaliser par ligne (rappel)
        cmap : str
            Colormap Matplotlib
        save_path : str, optional
            Chemin pour sauvegarder
        
        Returns:
        --------
        plt.Figure
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        if normalize:
            cm_display = cm.astype('float') / cm.sum(axis=1, keepdims=True)
            fmt = '.2f'
            vmax = 1.0
        else:
            cm_display = cm
            fmt = 'd'
            vmax = cm.max()
        
        # Heatmap
        sns.heatmap(
            cm_display,
            annot=True,
            fmt=fmt,
            cmap=cmap,
            xticklabels=class_names,
            yticklabels=class_names,
            ax=ax,
            vmin=0,
            vmax=vmax,
            linewidths=0.5,
            linecolor='white',
            cbar_kws={'label': 'Proportion' if normalize else 'Compte'}
        )
        
        ax.set_xlabel('Prédiction', fontsize=12, fontweight='bold')
        ax.set_ylabel('Réalité', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        
        # Rotation des labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        plt.setp(ax.get_yticklabels(), rotation=0)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['confusion_matrix'] = fig
        return fig
    
    def plot_roc_curves(
        self,
        roc_data: Dict[str, Dict],
        title: str = "Courbes ROC par Classe",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche les courbes ROC pour chaque classe.
        
        Parameters:
        -----------
        roc_data : Dict
            Données ROC avec fpr, tpr, auc par classe
        """
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        
        for class_name, data in roc_data.items():
            color = CLASS_COLORS.get(class_name, COLORS['primary'])
            ax.plot(
                data['fpr'], data['tpr'],
                color=color,
                linewidth=2,
                label=f"{class_name} (AUC = {data['auc']:.3f})"
            )
        
        # Ligne de référence
        ax.plot([0, 1], [0, 1], 'k--', linewidth=1, alpha=0.5, label='Aléatoire')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Taux de Faux Positifs (FPR)', fontsize=12)
        ax.set_ylabel('Taux de Vrais Positifs (TPR)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['roc_curves'] = fig
        return fig
    
    def plot_feature_importance(
        self,
        feature_importance: pd.DataFrame,
        top_n: int = 15,
        title: str = "Importance des Variables",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche un graphique d'importance des features.
        """
        fig, ax = plt.subplots(figsize=(10, 8), dpi=self.dpi)
        
        # Top N features
        df_top = feature_importance.head(top_n).copy()
        df_top = df_top.sort_values('importance', ascending=True)
        
        # Barres horizontales avec gradient
        colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(df_top)))
        
        bars = ax.barh(
            df_top['feature'],
            df_top['importance'],
            color=colors,
            edgecolor='white',
            linewidth=0.5
        )
        
        # Annotations
        for bar, imp in zip(bars, df_top['importance']):
            ax.text(
                bar.get_width() + 0.002,
                bar.get_y() + bar.get_height() / 2,
                f'{imp:.3f}',
                va='center',
                fontsize=9
            )
        
        ax.set_xlabel('Importance', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlim([0, df_top['importance'].max() * 1.15])
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['feature_importance'] = fig
        return fig
    
    def plot_model_comparison(
        self,
        comparison_df: pd.DataFrame,
        title: str = "Comparaison des Modèles",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche une comparaison radar ou barplot des modèles.
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=self.dpi)
        
        # Barplot groupé
        ax1 = axes[0]
        metrics = ['Accuracy', 'Precision', 'Recall', 'F1 Score']
        x = np.arange(len(comparison_df))
        width = 0.2
        
        colors = [COLORS['primary'], COLORS['secondary'], COLORS['success'], COLORS['danger']]
        
        for i, metric in enumerate(metrics):
            ax1.bar(
                x + i * width,
                comparison_df[metric],
                width,
                label=metric,
                color=colors[i],
                alpha=0.85
            )
        
        ax1.set_ylabel('Score', fontsize=12)
        ax1.set_title('Métriques par Modèle', fontsize=12, fontweight='bold')
        ax1.set_xticks(x + width * 1.5)
        ax1.set_xticklabels(comparison_df['Model'], rotation=45, ha='right')
        ax1.legend(loc='lower right')
        ax1.set_ylim([0, 1.05])
        ax1.grid(axis='y', alpha=0.3)
        
        # Radar chart
        ax2 = axes[1]
        
        # Préparer données radar
        categories = metrics
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]  # Fermer le polygone
        
        ax2 = plt.subplot(122, polar=True)
        
        model_colors = plt.cm.Set2(np.linspace(0, 1, len(comparison_df)))
        
        for idx, row in comparison_df.iterrows():
            values = [row[m] for m in metrics]
            values += values[:1]
            
            ax2.plot(angles, values, 'o-', linewidth=2, 
                    label=row['Model'], color=model_colors[idx])
            ax2.fill(angles, values, alpha=0.15, color=model_colors[idx])
        
        ax2.set_xticks(angles[:-1])
        ax2.set_xticklabels(categories, fontsize=10)
        ax2.set_ylim([0, 1])
        ax2.set_title('Profil de Performance', fontsize=12, fontweight='bold', pad=20)
        ax2.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['model_comparison'] = fig
        return fig
    
    def plot_data_distribution(
        self,
        df: pd.DataFrame,
        features: List[str],
        label_col: str = 'fault_type',
        title: str = "Distribution des Données par Classe",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche la distribution des features par classe.
        """
        n_features = len(features)
        n_cols = 3
        n_rows = (n_features + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows), dpi=self.dpi)
        axes = axes.flatten() if n_rows > 1 else [axes] if n_cols == 1 else axes
        
        unique_classes = df[label_col].unique()
        palette = {c: CLASS_COLORS.get(c, '#666666') for c in unique_classes}
        
        for idx, feature in enumerate(features):
            ax = axes[idx]
            
            for class_name in unique_classes:
                data = df[df[label_col] == class_name][feature]
                sns.kdeplot(
                    data=data,
                    ax=ax,
                    label=class_name,
                    color=palette[class_name],
                    fill=True,
                    alpha=0.3
                )
            
            ax.set_xlabel(feature, fontsize=10)
            ax.set_ylabel('Densité', fontsize=10)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
        
        # Cacher les axes vides
        for idx in range(len(features), len(axes)):
            axes[idx].set_visible(False)
        
        plt.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['data_distribution'] = fig
        return fig
    
    def plot_pairplot_key_features(
        self,
        df: pd.DataFrame,
        features: List[str],
        label_col: str = 'fault_type',
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Crée un pairplot des features clés.
        """
        unique_classes = df[label_col].unique()
        palette = {c: CLASS_COLORS.get(c, '#666666') for c in unique_classes}
        
        g = sns.pairplot(
            df[features + [label_col]],
            hue=label_col,
            palette=palette,
            diag_kind='kde',
            plot_kws={'alpha': 0.6, 's': 30},
            diag_kws={'fill': True, 'alpha': 0.5}
        )
        
        g.fig.suptitle('Relations entre Variables Clés', y=1.02, fontsize=14, fontweight='bold')
        
        if save_path:
            g.fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['pairplot'] = g.fig
        return g.fig
    
    def plot_ph_diagram(
        self,
        cycle_points: Dict[str, Tuple[float, float]],
        title: str = "Diagramme Pression-Enthalpie (P-h)",
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche un diagramme P-h simplifié du cycle.
        
        Parameters:
        -----------
        cycle_points : Dict
            Points du cycle {'1': (h1, P1), '2': (h2, P2), ...}
        """
        fig, ax = plt.subplots(figsize=(12, 8), dpi=self.dpi)
        
        # Extraire les points
        points = []
        labels = ['1 (Aspiration)', '2 (Refoulement)', '3 (Sortie Cond.)', '4 (Entrée Évap.)']
        
        for i, (key, (h, P)) in enumerate(cycle_points.items()):
            points.append((h, P))
            ax.scatter(h, P, s=100, zorder=5, c=COLORS['primary'])
            ax.annotate(
                labels[i] if i < len(labels) else key,
                (h, P), xytext=(10, 10),
                textcoords='offset points',
                fontsize=10, fontweight='bold'
            )
        
        # Tracer le cycle
        if len(points) >= 4:
            h_vals = [p[0] for p in points]
            P_vals = [p[1] for p in points]
            
            # Fermer le cycle
            h_cycle = h_vals + [h_vals[0]]
            P_cycle = P_vals + [P_vals[0]]
            
            ax.plot(h_cycle, P_cycle, 'b-', linewidth=2, alpha=0.7)
            
            # Zones colorées
            ax.fill(h_cycle, P_cycle, alpha=0.1, color=COLORS['primary'])
        
        # Lignes isobares
        ax.axhline(y=points[0][1], color='green', linestyle='--', alpha=0.5, label='P_évaporation')
        ax.axhline(y=points[1][1], color='red', linestyle='--', alpha=0.5, label='P_condensation')
        
        ax.set_xlabel('Enthalpie (kJ/kg)', fontsize=12)
        ax.set_ylabel('Pression (bar)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='upper left')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['ph_diagram'] = fig
        return fig
    
    def plot_compressor_envelope(
        self,
        operating_points: Optional[List[Tuple[float, float]]] = None,
        T_evap_limits: Tuple[float, float] = (-25, 20),
        T_cond_limits: Tuple[float, float] = (20, 65),
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Affiche l'enveloppe de fonctionnement du compresseur.
        """
        fig, ax = plt.subplots(figsize=(10, 8), dpi=self.dpi)
        
        # Zone admissible
        envelope = plt.Rectangle(
            (T_evap_limits[0], T_cond_limits[0]),
            T_evap_limits[1] - T_evap_limits[0],
            T_cond_limits[1] - T_cond_limits[0],
            fill=True, facecolor='lightgreen', edgecolor='green',
            alpha=0.3, linewidth=2, label='Zone Admissible'
        )
        ax.add_patch(envelope)
        
        # Zones critiques
        # Zone haute température refoulement
        high_temp_zone = plt.Polygon(
            [[T_evap_limits[0], T_cond_limits[1]],
             [T_evap_limits[0], T_cond_limits[1] + 15],
             [T_evap_limits[1], T_cond_limits[1] + 15],
             [T_evap_limits[1], T_cond_limits[1]]],
            facecolor='orange', alpha=0.4, edgecolor='darkorange',
            linewidth=2, label='Zone Haute T° Refoulement'
        )
        ax.add_patch(high_temp_zone)
        
        # Zone basse pression évaporation
        low_evap_zone = plt.Polygon(
            [[T_evap_limits[0] - 10, T_cond_limits[0]],
             [T_evap_limits[0] - 10, T_cond_limits[1]],
             [T_evap_limits[0], T_cond_limits[1]],
             [T_evap_limits[0], T_cond_limits[0]]],
            facecolor='red', alpha=0.3, edgecolor='darkred',
            linewidth=2, label='Zone Basse P° Évaporation'
        )
        ax.add_patch(low_evap_zone)
        
        # Points de fonctionnement
        if operating_points:
            T_evaps = [p[0] for p in operating_points]
            T_conds = [p[1] for p in operating_points]
            ax.scatter(T_evaps, T_conds, c=COLORS['primary'], s=50, zorder=5,
                      label='Points de fonctionnement', alpha=0.7)
        
        # Lignes iso-tau
        for tau in [2, 3, 4, 5]:
            # T_cond = T_evap + delta (approximation)
            T_evap_range = np.linspace(-25, 20, 50)
            T_cond_range = T_evap_range + 10 * tau
            ax.plot(T_evap_range, T_cond_range, '--', alpha=0.4, 
                   label=f'τ ≈ {tau}' if tau == 3 else None)
        
        ax.set_xlabel('Température Évaporation (°C)', fontsize=12)
        ax.set_ylabel('Température Condensation (°C)', fontsize=12)
        ax.set_title("Enveloppe de Fonctionnement du Compresseur", fontsize=14, fontweight='bold')
        ax.set_xlim([-35, 25])
        ax.set_ylim([15, 80])
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['compressor_envelope'] = fig
        return fig
    
    def create_report_figure(
        self,
        results_dict: Dict,
        df: pd.DataFrame,
        feature_cols: List[str],
        label_col: str = 'fault_type',
        save_path: Optional[str] = None
    ) -> plt.Figure:
        """
        Crée une figure de synthèse pour le rapport.
        """
        fig = plt.figure(figsize=(16, 12), dpi=self.dpi)
        gs = GridSpec(2, 3, figure=fig, hspace=0.3, wspace=0.3)
        
        # Récupérer le meilleur résultat
        best_name = max(results_dict.keys(), key=lambda k: results_dict[k].f1_macro)
        best_result = results_dict[best_name]
        
        # 1. Matrice de confusion (grande)
        ax1 = fig.add_subplot(gs[0, :2])
        cm = best_result.confusion_matrix
        class_names = list(set(df[label_col]))
        cm_norm = cm.astype('float') / cm.sum(axis=1, keepdims=True)
        
        sns.heatmap(cm_norm, annot=True, fmt='.2f', cmap='Blues',
                   xticklabels=class_names, yticklabels=class_names, ax=ax1)
        ax1.set_xlabel('Prédiction')
        ax1.set_ylabel('Réalité')
        ax1.set_title(f'Matrice de Confusion - {best_name}', fontweight='bold')
        
        # 2. Métriques
        ax2 = fig.add_subplot(gs[0, 2])
        metrics = ['Accuracy', 'Precision', 'Recall', 'F1']
        values = [best_result.accuracy, best_result.precision_macro,
                 best_result.recall_macro, best_result.f1_macro]
        colors = [COLORS['primary'], COLORS['secondary'], COLORS['success'], COLORS['danger']]
        
        bars = ax2.barh(metrics, values, color=colors)
        ax2.set_xlim([0, 1.1])
        for bar, val in zip(bars, values):
            ax2.text(val + 0.02, bar.get_y() + bar.get_height()/2,
                    f'{val:.3f}', va='center', fontweight='bold')
        ax2.set_title('Métriques de Performance', fontweight='bold')
        
        # 3. Importance des features
        ax3 = fig.add_subplot(gs[1, 0])
        if best_result.feature_importance is not None:
            top_features = best_result.feature_importance.head(8)
            ax3.barh(top_features['feature'], top_features['importance'],
                    color=plt.cm.viridis(np.linspace(0.3, 0.9, len(top_features))))
            ax3.set_xlabel('Importance')
            ax3.set_title('Top 8 Variables', fontweight='bold')
        
        # 4. Distribution COP par classe
        ax4 = fig.add_subplot(gs[1, 1])
        if 'COP' in df.columns:
            for class_name in df[label_col].unique():
                data = df[df[label_col] == class_name]['COP']
                sns.kdeplot(data, ax=ax4, label=class_name,
                           color=CLASS_COLORS.get(class_name, '#666666'), fill=True, alpha=0.3)
            ax4.set_xlabel('COP')
            ax4.set_title('Distribution du COP par État', fontweight='bold')
            ax4.legend(fontsize=8)
        
        # 5. Scatter P_evap vs P_cond
        ax5 = fig.add_subplot(gs[1, 2])
        for class_name in df[label_col].unique():
            subset = df[df[label_col] == class_name]
            ax5.scatter(subset['P_evap'], subset['P_cond'], 
                       label=class_name, alpha=0.5, s=20,
                       c=CLASS_COLORS.get(class_name, '#666666'))
        ax5.set_xlabel('P_évaporation (bar)')
        ax5.set_ylabel('P_condensation (bar)')
        ax5.set_title('Espace des Pressions', fontweight='bold')
        ax5.legend(fontsize=8)
        
        plt.suptitle('Rapport de Diagnostic FDD - Pompe à Chaleur',
                    fontsize=16, fontweight='bold', y=1.02)
        
        if save_path:
            fig.savefig(save_path, bbox_inches='tight', dpi=self.dpi)
        
        self.figures['report'] = fig
        return fig
    
    def save_all_figures(self, output_dir: str):
        """Sauvegarde toutes les figures générées."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        for name, fig in self.figures.items():
            path = os.path.join(output_dir, f'{name}.png')
            fig.savefig(path, bbox_inches='tight', dpi=self.dpi)
            print(f"Sauvegardé: {path}")


if __name__ == "__main__":
    # Test des visualisations
    print("=== Test des Visualisations FDD ===\n")
    
    viz = FDDVisualizer()
    
    # Matrice de confusion exemple
    cm = np.array([
        [85, 10, 5],
        [8, 82, 10],
        [7, 12, 81]
    ])
    class_names = ['Normal', 'Condenser_Fault', 'Evaporator_Fault']
    
    fig = viz.plot_confusion_matrix(cm, class_names)
    plt.show()
    
    print("Test terminé.")




