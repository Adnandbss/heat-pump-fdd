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
"""

import warnings

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from tqdm import tqdm

from ...fdd.features import DEFAULT_CAPACITY_NOM, FEATURE_COLUMNS, cycle_to_features
from ...physics.simulator import HeatPumpSimulator

NOISE_SCALE = {
    "temperature": 0.5,  # ±0.5 °C
    "pressure": 0.02,    # ±2 %
    "power": 0.03,       # ±3 %
}

SENSOR_NOISE = {
    "T_ambient": "temperature",
    "T_setpoint": "temperature",
    "P_evap": "pressure",
    "P_cond": "pressure",
    "T_evap": "temperature",
    "T_cond": "temperature",
    "T_suction": "temperature",
    "T_discharge": "temperature",
    "superheat": "temperature",
    "subcooling": "temperature",
    "W_comp": "power",
    "Q_cond": "power",
}

BASELINE_SENSOR_NOISE = {
    "P_evap": "pressure",
    "P_cond": "pressure",
    "T_evap": "temperature",
    "T_cond": "temperature",
    "T_discharge": "temperature",
    "superheat": "temperature",
    "subcooling": "temperature",
    "W_comp": "power",
    "Q_cond": "power",
}


def recompute_derived(sample: Dict, capacity_nom: float = DEFAULT_CAPACITY_NOM) -> Dict:
    """Rebuild ratios, COP and pinches from the (possibly noisy) sensor columns.

    Call this *after* measurement noise. Leaving the simulator's pre-noise
    values in place is how ``d_COP`` used to equal the detection label.
    """
    p_evap = float(sample["P_evap"])
    p_cond = float(sample["P_cond"])
    w_comp = float(sample["W_comp"])
    q_cond = float(sample["Q_cond"])
    sample["compression_ratio"] = p_cond / p_evap if p_evap else 0.0
    sample["pressure_ratio"] = p_cond / p_evap if p_evap else 0.0
    sample["COP"] = q_cond / w_comp if w_comp else 0.0
    sample["delta_T_evap"] = float(sample["T_ambient"]) - float(sample["T_evap"])
    sample["delta_T_cond"] = float(sample["T_cond"]) - float(sample["T_setpoint"])
    sample["capacity_ratio"] = q_cond / capacity_nom if capacity_nom else 0.0
    return sample


class FaultType(Enum):
    """Types de défauts simulés."""
    NORMAL = "Normal"
    CONDENSER_FOULING = "Condenser_Fouling"
    EVAPORATOR_FOULING = "Evaporator_Fouling"
    REFRIGERANT_UNDERCHARGE = "Refrigerant_Undercharge"
    REFRIGERANT_OVERCHARGE = "Refrigerant_Overcharge"
    CONDENSER_FAN_FAULT = "Condenser_Fan_Fault"
    EVAPORATOR_FAN_FAULT = "Evaporator_Fan_Fault"


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
        self.n_rejected = 0
        self.n_dropped_nan = 0
        
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
            # Extra charge only. Do not piggy-back condenser fouling: that
            # contamination made overcharge look like fouling by construction.
            params['refrigerant_charge'] = 1.0 + severity * 0.5
            
        elif fault_type == FaultType.CONDENSER_FAN_FAULT:
            params['fan_cond_ratio'] = 1.0 - severity
            
        elif fault_type == FaultType.EVAPORATOR_FAN_FAULT:
            params['fan_evap_ratio'] = 1.0 - severity
        
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
        
        def add_noise(value, scale_type):
            if scale_type == "temperature":
                return value + self.rng.normal(0, NOISE_SCALE["temperature"])
            if scale_type == "pressure":
                return value * (1 + self.rng.normal(0, NOISE_SCALE["pressure"]))
            return value * (1 + self.rng.normal(0, NOISE_SCALE["power"]))
        
        sample = cycle_to_features(
            result,
            T_source,
            T_sink,
            speed_ratio,
            self.simulator.capacity_nom,
            baseline=baseline,
            simulator=self.simulator,
        )
        for col, kind in SENSOR_NOISE.items():
            sample[col] = add_noise(sample[col], kind)
        capacity_nom = self.simulator.capacity_nom
        recompute_derived(sample, capacity_nom)

        # The healthy reference is a sensor reading too — noise it independently,
        # then rebuild its COP from the noisy powers, otherwise d_* keep a
        # noise-free half of the subtraction.
        ref = {
            "T_ambient": T_source,
            "T_setpoint": T_sink,
            "P_evap": baseline.P_evap,
            "P_cond": baseline.P_cond,
            "T_evap": baseline.T_evap,
            "T_cond": baseline.T_cond,
            "T_discharge": baseline.T_discharge,
            "superheat": baseline.superheat,
            "subcooling": baseline.subcooling,
            "W_comp": baseline.W_comp,
            "Q_cond": baseline.Q_cond,
        }
        for col, kind in BASELINE_SENSOR_NOISE.items():
            ref[col] = add_noise(ref[col], kind)
        recompute_derived(ref, capacity_nom)

        sample["d_T_discharge"] = sample["T_discharge"] - ref["T_discharge"]
        sample["d_superheat"] = sample["superheat"] - ref["superheat"]
        sample["d_subcooling"] = sample["subcooling"] - ref["subcooling"]
        sample["d_COP"] = sample["COP"] - ref["COP"]
        sample["d_W_comp"] = sample["W_comp"] - ref["W_comp"]
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
        
        all_samples = []
        self.n_rejected = 0
        self.n_dropped_nan = 0

        iterator = samples_per_type.items()
        if show_progress:
            iterator = tqdm(list(iterator), desc="Generating fault types")

        for fault_type, n in iterator:
            config = self.fault_configs[fault_type]
            produced = 0
            attempts = 0
            max_attempts = max(n * 50, n + 1)
            while produced < n and attempts < max_attempts:
                attempts += 1
                T_source = self.rng.uniform(*self.T_source_range)
                T_sink = self.rng.uniform(*self.T_sink_range)
                speed_ratio = self.rng.uniform(*self.speed_ratio_range)
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
                    produced += 1
                except Exception:
                    self.n_rejected += 1
            if produced < n:
                warnings.warn(
                    f"{fault_type.value}: {produced}/{n} samples after {attempts} attempts "
                    f"({self.n_rejected} rejected)",
                    RuntimeWarning,
                    stacklevel=2,
                )

        df = pd.DataFrame(all_samples)
        n_before = len(df)
        df = df.replace([np.inf, -np.inf], np.nan).dropna()
        self.n_dropped_nan = n_before - len(df)
        if self.n_rejected or self.n_dropped_nan:
            warnings.warn(
                f"generator dropped {self.n_rejected} failed cycles and "
                f"{self.n_dropped_nan} non-finite rows "
                f"(kept {len(df)}/{n_samples})",
                RuntimeWarning,
                stacklevel=2,
            )
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
                except Exception:
                    self.n_rejected += 1
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



