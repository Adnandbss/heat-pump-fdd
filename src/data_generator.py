"""
Générateur de Données pour FDD (Fault Detection & Diagnostics)
===============================================================

Ce module génère des datasets synthétiques réalistes pour l'entraînement
de modèles de Machine Learning de détection de défauts.

Les défauts simulés incluent:
- Encrassement du condenseur (Condenser Fouling)
- Encrassement/obstruction de l'évaporateur (Evaporator Fouling)
- Sous-charge en réfrigérant (Refrigerant Leakage)
- Sur-charge en réfrigérant (Refrigerant Overcharge)
- Défaillance ventilateur condenseur (Condenser Fan Fault)
- Défaillance ventilateur évaporateur (Evaporator Fan Fault)
- Fuite au compresseur (Compressor Valve Leak)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from tqdm import tqdm

from .simulator import HeatPumpSimulator
from .features import FEATURE_COLUMNS, cycle_to_features


class FaultType(Enum):
    """Types de défauts simulés."""
    NORMAL = "Normal"
    CONDENSER_FOULING = "Condenser_Fouling"
    EVAPORATOR_FOULING = "Evaporator_Fouling"
    REFRIGERANT_UNDERCHARGE = "Refrigerant_Undercharge"
    REFRIGERANT_OVERCHARGE = "Refrigerant_Overcharge"
    CONDENSER_FAN_FAULT = "Condenser_Fan_Fault"
    EVAPORATOR_FAN_FAULT = "Evaporator_Fan_Fault"
    COMPRESSOR_VALVE_LEAK = "Compressor_Valve_Leak"


@dataclass
class FaultConfig:
    """Configuration d'un défaut."""
    fault_type: FaultType
    severity_min: float  # Sévérité minimale (0-1)
    severity_max: float  # Sévérité maximale (0-1)
    description: str


class FaultDataGenerator:
    """
    Générateur de données de défauts pour pompes à chaleur.
    
    Génère des datasets synthétiques avec différents niveaux de défauts
    pour l'entraînement de modèles de classification ML.
    
    Parameters:
    -----------
    simulator : HeatPumpSimulator
        Instance du simulateur thermodynamique
    random_seed : int
        Graine pour reproductibilité
    """
    
    def __init__(
        self,
        simulator: Optional[HeatPumpSimulator] = None,
        random_seed: int = 42
    ):
        self.simulator = simulator or HeatPumpSimulator()
        self.rng = np.random.default_rng(random_seed)
        
        # Configuration des défauts par défaut
        self.fault_configs = {
            FaultType.NORMAL: FaultConfig(
                FaultType.NORMAL, 0.0, 0.0,
                "Fonctionnement normal sans défaut"
            ),
            FaultType.CONDENSER_FOULING: FaultConfig(
                FaultType.CONDENSER_FOULING, 0.15, 0.50,
                "Encrassement du condenseur (15-50%)"
            ),
            FaultType.EVAPORATOR_FOULING: FaultConfig(
                FaultType.EVAPORATOR_FOULING, 0.15, 0.50,
                "Encrassement de l'évaporateur (15-50%)"
            ),
            FaultType.REFRIGERANT_UNDERCHARGE: FaultConfig(
                FaultType.REFRIGERANT_UNDERCHARGE, 0.10, 0.35,
                "Sous-charge réfrigérant (10-35%)"
            ),
            FaultType.REFRIGERANT_OVERCHARGE: FaultConfig(
                FaultType.REFRIGERANT_OVERCHARGE, 0.10, 0.30,
                "Sur-charge réfrigérant (10-30%)"
            ),
            FaultType.CONDENSER_FAN_FAULT: FaultConfig(
                FaultType.CONDENSER_FAN_FAULT, 0.20, 0.60,
                "Défaillance ventilateur condenseur (20-60%)"
            ),
            FaultType.EVAPORATOR_FAN_FAULT: FaultConfig(
                FaultType.EVAPORATOR_FAN_FAULT, 0.20, 0.60,
                "Défaillance ventilateur évaporateur (20-60%)"
            ),
            FaultType.COMPRESSOR_VALVE_LEAK: FaultConfig(
                FaultType.COMPRESSOR_VALVE_LEAK, 0.10, 0.40,
                "Fuite clapet compresseur (10-40%)"
            ),
        }
        
        # Plages de conditions opératoires
        self.T_source_range = (-10.0, 20.0)    # Température source (°C)
        self.T_sink_range = (30.0, 55.0)        # Température puits (°C)
        self.speed_ratio_range = (0.3, 1.0)     # Ratio vitesse compresseur
    
    def _apply_fault(
        self,
        fault_type: FaultType,
        severity: float
    ) -> Dict:
        """
        Convertit un type de défaut en paramètres de simulation.
        
        Returns:
        --------
        Dict avec les paramètres à passer au simulateur
        """
        params = {
            'condenser_fouling': 0.0,
            'evaporator_fouling': 0.0,
            'refrigerant_charge': 1.0,
            'fan_evap_ratio': 1.0,
            'fan_cond_ratio': 1.0,
        }
        
        if fault_type == FaultType.CONDENSER_FOULING:
            params['condenser_fouling'] = severity
            
        elif fault_type == FaultType.EVAPORATOR_FOULING:
            params['evaporator_fouling'] = severity
            
        elif fault_type == FaultType.REFRIGERANT_UNDERCHARGE:
            params['refrigerant_charge'] = 1.0 - severity
            
        elif fault_type == FaultType.REFRIGERANT_OVERCHARGE:
            # Sur-charge : augmente pression condensation
            params['refrigerant_charge'] = 1.0 + severity * 0.5
            params['condenser_fouling'] = severity * 0.2  # Effet indirect
            
        elif fault_type == FaultType.CONDENSER_FAN_FAULT:
            params['fan_cond_ratio'] = 1.0 - severity
            
        elif fault_type == FaultType.EVAPORATOR_FAN_FAULT:
            params['fan_evap_ratio'] = 1.0 - severity
            
        elif fault_type == FaultType.COMPRESSOR_VALVE_LEAK:
            # Fuite clapet : réduit rendement volumétrique effectif
            # Simulé par une combinaison de facteurs
            params['refrigerant_charge'] = 1.0 - severity * 0.3
            params['evaporator_fouling'] = severity * 0.15
        
        return params
    
    def generate_single_sample(
        self,
        T_source: float,
        T_sink: float,
        speed_ratio: float,
        fault_type: FaultType,
        severity: float
    ) -> Dict:
        """
        Génère un échantillon unique de données.
        
        Returns:
        --------
        Dict contenant toutes les features et le label
        """
        # Appliquer le défaut
        fault_params = self._apply_fault(fault_type, severity)
        
        # Simuler le cycle
        result = self.simulator.simulate_cycle(
            T_source=T_source,
            T_sink=T_sink,
            speed_ratio=speed_ratio,
            **fault_params
        )
        baseline = self.simulator.simulate_cycle(
            T_source=T_source,
            T_sink=T_sink,
            speed_ratio=speed_ratio,
        )
        
        # Ajouter du bruit de mesure réaliste
        noise_scale = {
            'temperature': 0.5,   # ±0.5°C
            'pressure': 0.02,     # ±2% pression
            'power': 0.03,        # ±3% puissance
        }
        
        def add_noise(value, scale_type):
            if scale_type == 'temperature':
                return value + self.rng.normal(0, noise_scale['temperature'])
            elif scale_type == 'pressure':
                return value * (1 + self.rng.normal(0, noise_scale['pressure']))
            else:
                return value * (1 + self.rng.normal(0, noise_scale['power']))
        
        sample = cycle_to_features(
            result,
            T_source,
            T_sink,
            speed_ratio,
            self.simulator.capacity_nom,
            baseline=baseline,
            simulator=self.simulator,
        )
        sample["T_ambient"] = add_noise(sample["T_ambient"], "temperature")
        sample["T_setpoint"] = add_noise(sample["T_setpoint"], "temperature")
        sample["P_evap"] = add_noise(sample["P_evap"], "pressure")
        sample["P_cond"] = add_noise(sample["P_cond"], "pressure")
        sample["T_evap"] = add_noise(sample["T_evap"], "temperature")
        sample["T_cond"] = add_noise(sample["T_cond"], "temperature")
        sample["T_suction"] = add_noise(sample["T_suction"], "temperature")
        sample["T_discharge"] = add_noise(sample["T_discharge"], "temperature")
        sample["superheat"] = add_noise(sample["superheat"], "temperature")
        sample["subcooling"] = add_noise(sample["subcooling"], "temperature")
        sample["W_comp"] = add_noise(sample["W_comp"], "power")
        sample["Q_cond"] = add_noise(sample["Q_cond"], "power")
        sample["d_T_discharge"] = sample["T_discharge"] - baseline.T_discharge
        sample["d_superheat"] = sample["superheat"] - baseline.superheat
        sample["d_subcooling"] = sample["subcooling"] - baseline.subcooling
        sample["d_COP"] = sample["COP"] - baseline.COP
        sample["d_W_comp"] = sample["W_comp"] - baseline.W_comp
        sample["fault_type"] = fault_type.value
        sample["fault_severity"] = severity
        sample["is_faulty"] = 0 if fault_type == FaultType.NORMAL else 1
        
        return sample
    
    def generate_dataset(
        self,
        n_samples: int = 5000,
        fault_distribution: Optional[Dict[FaultType, float]] = None,
        include_severity_labels: bool = True,
        show_progress: bool = True
    ) -> pd.DataFrame:
        """
        Génère un dataset complet pour l'entraînement ML.
        
        Parameters:
        -----------
        n_samples : int
            Nombre total d'échantillons
        fault_distribution : Dict[FaultType, float]
            Distribution des défauts (doit sommer à 1.0)
            Par défaut : 40% Normal, 10% chaque défaut
        include_severity_labels : bool
            Inclure la sévérité des défauts dans les labels
        show_progress : bool
            Afficher une barre de progression
        
        Returns:
        --------
        pd.DataFrame avec toutes les données
        """
        # Distribution par défaut
        if fault_distribution is None:
            n_fault_types = len(FaultType) - 1  # Exclure NORMAL
            fault_distribution = {
                FaultType.NORMAL: 0.40,
            }
            fault_prob = 0.60 / n_fault_types
            for ft in FaultType:
                if ft != FaultType.NORMAL:
                    fault_distribution[ft] = fault_prob
        
        # Calculer le nombre d'échantillons par type
        samples_per_type = {
            ft: int(n_samples * prob)
            for ft, prob in fault_distribution.items()
        }
        
        # Ajuster pour atteindre exactement n_samples
        diff = n_samples - sum(samples_per_type.values())
        if diff != 0:
            # Ajouter la différence au premier type disponible
            first_type = list(samples_per_type.keys())[0]
            samples_per_type[first_type] += diff
        
        # Générer les échantillons
        all_samples = []
        
        iterator = samples_per_type.items()
        if show_progress:
            iterator = tqdm(list(iterator), desc="Generating fault types")
        
        for fault_type, n in iterator:
            config = self.fault_configs[fault_type]
            
            for _ in range(n):
                # Conditions aléatoires
                T_source = self.rng.uniform(*self.T_source_range)
                T_sink = self.rng.uniform(*self.T_sink_range)
                speed_ratio = self.rng.uniform(*self.speed_ratio_range)
                
                # Sévérité aléatoire dans la plage du défaut
                if fault_type == FaultType.NORMAL:
                    severity = 0.0
                else:
                    severity = self.rng.uniform(
                        config.severity_min,
                        config.severity_max
                    )
                
                try:
                    sample = self.generate_single_sample(
                        T_source, T_sink, speed_ratio,
                        fault_type, severity
                    )
                    all_samples.append(sample)
                except Exception as e:
                    # Skip samples qui causent des erreurs numériques
                    continue
        
        df = pd.DataFrame(all_samples)
        
        # Nettoyer les valeurs aberrantes
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna()
        
        return df
    
    def generate_time_series_dataset(
        self,
        n_sequences: int = 100,
        sequence_length: int = 100,
        fault_injection_point: float = 0.5,
        degradation_rate: float = 0.01
    ) -> pd.DataFrame:
        """
        Génère un dataset de séries temporelles avec dégradation progressive.
        
        Utile pour la détection précoce de défauts (pronostic).
        
        Parameters:
        -----------
        n_sequences : int
            Nombre de séquences
        sequence_length : int
            Durée de chaque séquence (timesteps)
        fault_injection_point : float
            Point d'injection du défaut (0-1)
        degradation_rate : float
            Taux de dégradation par timestep
        
        Returns:
        --------
        pd.DataFrame avec colonnes sequence_id, timestep, features...
        """
        all_samples = []
        
        for seq_id in tqdm(range(n_sequences), desc="Generating sequences"):
            # Choisir un type de défaut pour cette séquence
            fault_type = self.rng.choice(list(FaultType)[1:])  # Exclure NORMAL
            config = self.fault_configs[fault_type]
            
            # Conditions fixes pour la séquence
            T_source = self.rng.uniform(*self.T_source_range)
            T_sink = self.rng.uniform(*self.T_sink_range)
            speed_ratio = self.rng.uniform(0.5, 0.9)
            
            # Point d'injection
            injection_timestep = int(sequence_length * fault_injection_point)
            
            for t in range(sequence_length):
                # Calculer la sévérité
                if t < injection_timestep:
                    severity = 0.0
                    current_fault = FaultType.NORMAL
                else:
                    steps_since_fault = t - injection_timestep
                    severity = min(
                        config.severity_max,
                        config.severity_min + steps_since_fault * degradation_rate
                    )
                    current_fault = fault_type
                
                # Légère variation des conditions
                T_source_t = T_source + self.rng.normal(0, 1)
                
                try:
                    sample = self.generate_single_sample(
                        T_source_t, T_sink, speed_ratio,
                        current_fault, severity
                    )
                    sample['sequence_id'] = seq_id
                    sample['timestep'] = t
                    sample['time_to_failure'] = max(0, sequence_length - t - 1)
                    all_samples.append(sample)
                except:
                    continue
        
        return pd.DataFrame(all_samples)
    
    def get_feature_columns(self) -> List[str]:
        """Retourne la liste des colonnes de features pour le ML."""
        return list(FEATURE_COLUMNS)
    
    def get_label_column(self) -> str:
        """Retourne le nom de la colonne label."""
        return 'fault_type'
    
    def get_binary_label_column(self) -> str:
        """Retourne le nom de la colonne label binaire."""
        return 'is_faulty'


# Pour compatibilité avec le code existant dans le rapport
def generate_synthetic_data(n_samples: int = 1000) -> pd.DataFrame:
    """
    Fonction de génération simplifiée compatible avec le code du rapport.
    
    Parameters:
    -----------
    n_samples : int
        Nombre d'échantillons à générer
    
    Returns:
    --------
    pd.DataFrame compatible avec le format du rapport original
    """
    generator = FaultDataGenerator()
    
    # Distribution simplifiée : 3 classes comme dans le rapport
    distribution = {
        FaultType.NORMAL: 0.40,
        FaultType.CONDENSER_FOULING: 0.30,
        FaultType.EVAPORATOR_FOULING: 0.30,
    }
    
    df = generator.generate_dataset(
        n_samples=n_samples,
        fault_distribution=distribution,
        show_progress=False
    )
    
    # Renommer pour compatibilité
    df['fault_type'] = df['fault_type'].replace({
        'Normal': 'Normal',
        'Condenser_Fouling': 'Condenser_Fault',
        'Evaporator_Fouling': 'Evaporator_Fault',
    })
    
    return df


if __name__ == "__main__":
    # Test du générateur
    print("=== Test du Générateur de Données FDD ===\n")
    
    generator = FaultDataGenerator(random_seed=42)
    
    # Générer un petit dataset
    print("Génération de 1000 échantillons...")
    df = generator.generate_dataset(n_samples=1000, show_progress=True)
    
    print(f"\nDataset généré : {len(df)} échantillons")
    print(f"Colonnes : {list(df.columns)}")
    
    print("\nDistribution des défauts :")
    print(df['fault_type'].value_counts())
    
    print("\nStatistiques des features principales :")
    print(df[['P_evap', 'P_cond', 'COP', 'T_discharge']].describe())



