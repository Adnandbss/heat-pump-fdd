"""
Simulateur Thermodynamique de Pompe à Chaleur
==============================================
Basé sur les équations du cycle à compression de vapeur.

Ce module implémente un modèle physique simplifié mais réaliste
permettant de simuler le comportement d'une PAC sous différentes
conditions de charge et avec différents types de défauts.

Références:
- Cycle de Carnot inversé
- Modélisation du rendement isentropique et volumétrique
- Corrélations empiriques pour les échangeurs
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import warnings

try:
    from CoolProp.CoolProp import PropsSI
    HAS_COOLPROP = True
except ImportError:
    HAS_COOLPROP = False


@dataclass
class ThermodynamicState:
    """État thermodynamique à un point du cycle."""
    temperature: float  # °C
    pressure: float     # bar
    enthalpy: float     # kJ/kg
    entropy: float      # kJ/(kg·K)
    quality: float      # Titre vapeur (0-1, ou >1 si surchauffé)
    density: float      # kg/m³


@dataclass
class CycleResults:
    """Résultats complets d'un cycle de pompe à chaleur."""
    # Pressions
    P_evap: float          # Pression évaporation (bar)
    P_cond: float          # Pression condensation (bar)
    compression_ratio: float
    
    # Températures
    T_evap: float          # Température saturation évaporateur (°C)
    T_cond: float          # Température saturation condenseur (°C)
    T_suction: float       # Température aspiration compresseur (°C)
    T_discharge: float     # Température refoulement compresseur (°C)
    superheat: float       # Surchauffe (K)
    subcooling: float      # Sous-refroidissement (K)
    
    # Puissances et performances
    Q_evap: float          # Puissance évaporateur (W)
    Q_cond: float          # Puissance condenseur (W)
    W_comp: float          # Puissance compresseur (W)
    COP: float             # Coefficient de performance
    
    # Débits
    mass_flow: float       # Débit massique (kg/s)
    
    # Rendements
    eta_isentropic: float  # Rendement isentropique
    eta_volumetric: float  # Rendement volumétrique
    
    # Indicateurs de santé
    system_health: str     # État global du système
    fault_indicators: Dict[str, float]  # Indicateurs de défauts


class RefrigerantProperties:
    """
    Propriétés R410A via CoolProp, avec corrélations de repli.
    """

    FLUID = "R410A"
    T_crit = 71.4
    P_crit = 49.0
    h_fg_ref = 220.0
    cp_vapor = 1.2
    gamma = 1.18

    @classmethod
    def saturation_pressure(cls, T: float) -> float:
        """Pression de saturation (bar)."""
        if HAS_COOLPROP:
            try:
                return PropsSI("P", "T", T + 273.15, "Q", 1, cls.FLUID) / 1e5
            except Exception as exc:
                warnings.warn(f"CoolProp P_sat fallback: {exc}")
        return 8.0 * np.exp(0.04 * T)

    @classmethod
    def saturation_temperature(cls, P: float) -> float:
        """Température de saturation (°C)."""
        if HAS_COOLPROP:
            try:
                return PropsSI("T", "P", P * 1e5, "Q", 1, cls.FLUID) - 273.15
            except Exception as exc:
                warnings.warn(f"CoolProp T_sat fallback: {exc}")
        return np.log(max(P, 0.1) / 8.0) / 0.04

    @classmethod
    def vapor_density(cls, T: float, P: float) -> float:
        """Densité vapeur (kg/m³)."""
        if HAS_COOLPROP:
            try:
                return PropsSI("D", "T", T + 273.15, "P", P * 1e5, cls.FLUID)
            except Exception:
                pass
        R = 0.0815
        return (P * 100) / (R * (T + 273.15))

    @classmethod
    def liquid_density(cls, T: float) -> float:
        if HAS_COOLPROP:
            try:
                return PropsSI("D", "T", T + 273.15, "Q", 0, cls.FLUID)
            except Exception:
                pass
        return 1200 - 3.5 * T

    @classmethod
    def enthalpy_vapor_sat(cls, T: float) -> float:
        if HAS_COOLPROP:
            try:
                return PropsSI("H", "T", T + 273.15, "Q", 1, cls.FLUID) / 1000
            except Exception:
                pass
        return 250 + 0.8 * T + cls.h_fg_ref

    @classmethod
    def enthalpy_liquid_sat(cls, T: float) -> float:
        if HAS_COOLPROP:
            try:
                return PropsSI("H", "T", T + 273.15, "Q", 0, cls.FLUID) / 1000
            except Exception:
                pass
        return 200 + 1.5 * T


class HeatPumpSimulator:
    """
    Simulateur thermodynamique complet de pompe à chaleur.
    
    Ce simulateur modélise:
    - Le cycle à compression de vapeur avec R410A
    - Les effets des variations de charge sur les échangeurs
    - L'impact des défauts (encrassement, fuites, etc.)
    - Les limites de l'enveloppe de fonctionnement du compresseur
    
    Parameters:
    -----------
    capacity_nom : float
        Capacité nominale de chauffage (W)
    cop_nom : float
        COP nominal à conditions de référence
    compressor_displacement : float
        Cylindrée du compresseur (m³/rev)
    compressor_speed_nom : float
        Vitesse nominale du compresseur (Hz)
    """
    
    def __init__(
        self,
        capacity_nom: float = 10000,
        cop_nom: float = 3.5,
        compressor_displacement: float = 15e-6,  # 15 cm³
        compressor_speed_nom: float = 50.0       # 50 Hz
    ):
        self.capacity_nom = capacity_nom
        self.cop_nom = cop_nom
        self.V_sw = compressor_displacement
        self.f_nom = compressor_speed_nom
        self.refrigerant = RefrigerantProperties()
        
        # Limites de l'enveloppe de fonctionnement
        self.T_evap_min = -25.0  # °C
        self.T_evap_max = 20.0   # °C
        self.T_cond_min = 20.0   # °C
        self.T_cond_max = 65.0   # °C
        self.T_discharge_max = 130.0  # °C
        
        # Paramètres échangeurs nominaux
        self.UA_evap_nom = 500   # W/K
        self.UA_cond_nom = 600   # W/K
    
    def calculate_isentropic_efficiency(
        self,
        compression_ratio: float,
        speed_ratio: float = 1.0
    ) -> float:
        """
        Calcule le rendement isentropique du compresseur.
        
        Le rendement dépend du taux de compression et de la vitesse.
        Basé sur des corrélations empiriques pour compresseurs scroll.
        
        η_is = η_is,max * f(τ) * g(speed)
        """
        # Rendement max à taux de compression optimal (~3)
        eta_max = 0.75
        
        # Pénalité pour taux de compression élevé
        tau_opt = 3.0
        f_tau = 1.0 - 0.05 * (compression_ratio - tau_opt) ** 2
        f_tau = np.clip(f_tau, 0.4, 1.0)
        
        # Pénalité aux extrêmes de vitesse (optimal ~50-60 Hz)
        g_speed = 1.0 - 0.3 * (speed_ratio - 0.7) ** 2
        g_speed = np.clip(g_speed, 0.6, 1.0)
        
        return eta_max * f_tau * g_speed
    
    def calculate_volumetric_efficiency(
        self,
        compression_ratio: float,
        speed_ratio: float = 1.0
    ) -> float:
        """
        Calcule le rendement volumétrique du compresseur.
        
        η_vol = 1 - C * (τ^(1/k) - 1)
        
        où C est le rapport de volumes morts (~0.05 pour scroll)
        """
        C = 0.05  # Clearance ratio
        k = self.refrigerant.gamma
        
        eta_vol = 1.0 - C * (compression_ratio ** (1/k) - 1)
        
        # Pénalité supplémentaire à basse vitesse (lubrification)
        if speed_ratio < 0.4:
            eta_vol *= (0.7 + 0.75 * speed_ratio)
        
        return np.clip(eta_vol, 0.3, 0.98)
    
    def simulate_cycle(
        self,
        T_source: float,
        T_sink: float,
        speed_ratio: float = 1.0,
        condenser_fouling: float = 0.0,
        evaporator_fouling: float = 0.0,
        refrigerant_charge: float = 1.0,
        fan_evap_ratio: float = 1.0,
        fan_cond_ratio: float = 1.0
    ) -> CycleResults:
        """
        Simule un cycle complet de pompe à chaleur.
        
        Parameters:
        -----------
        T_source : float
            Température de la source froide (air extérieur) en °C
        T_sink : float
            Température du puits chaud (eau/air intérieur) en °C
        speed_ratio : float
            Ratio de vitesse compresseur (0.3 à 1.0)
        condenser_fouling : float
            Niveau d'encrassement condenseur (0 = propre, 1 = totalement encrassé)
        evaporator_fouling : float
            Niveau d'encrassement évaporateur (0 à 1)
        refrigerant_charge : float
            Charge de réfrigérant (1.0 = nominal, <1 = sous-charge, >1 = surcharge)
        fan_evap_ratio : float
            Ratio débit ventilateur évaporateur (1.0 = nominal)
        fan_cond_ratio : float
            Ratio débit ventilateur condenseur (1.0 = nominal)

        Simulator debt: a compressor valve leak is not a knob here. It would
        need ``volumetric_efficiency_loss`` (hot-gas recirculation: mass flow
        down, discharge temperature up, capacity collapse, pressures roughly
        normal). Do not fake it by mixing undercharge and evaporator fouling.
        
        Returns:
        --------
        CycleResults : Résultats complets du cycle
        """
        # Heat-exchanger UA: fouling (dirt) vs fan (airflow) are not the same.
        # Fouling reduces the heat-transfer coefficient roughly linearly.
        # Fan faults collapse air-side convection more sharply (exponent > 1).
        UA_evap = self.UA_evap_nom * (1.0 - 0.50 * evaporator_fouling)
        UA_cond = self.UA_cond_nom * (1.0 - 0.50 * condenser_fouling)
        UA_evap *= fan_evap_ratio ** 1.45
        UA_cond *= fan_cond_ratio ** 1.45

        # Fan-evap UA already raises pinch. The extra 8 K term made T_discharge
        # rise with airflow loss, against the measured NIST sign — drop it.
        pinch_evap = (
            5.0
            + 7.0 * (1.0 - UA_evap / self.UA_evap_nom)
        )
        pinch_cond = (
            5.0
            + 7.0 * (1.0 - UA_cond / self.UA_cond_nom)
            + 8.0 * (1.0 - fan_cond_ratio)
        )
        
        # Température évaporation (doit être sous la source)
        T_evap = T_source - pinch_evap
        T_evap = np.clip(T_evap, self.T_evap_min, self.T_evap_max)
        
        # Température condensation (doit être au-dessus du puits)
        T_cond = T_sink + pinch_cond
        T_cond = np.clip(T_cond, self.T_cond_min, self.T_cond_max)
        
        # === Pressions de saturation ===
        P_evap = self.refrigerant.saturation_pressure(T_evap)
        P_cond = self.refrigerant.saturation_pressure(T_cond)
        
        # Undercharge: density / pressure collapse + starved evaporator
        if refrigerant_charge < 1.0:
            P_evap *= (0.55 + 0.45 * refrigerant_charge)
            T_evap = self.refrigerant.saturation_temperature(P_evap)
            T_evap = np.clip(T_evap, self.T_evap_min, self.T_evap_max)

        # Overcharge: extra liquid stacks in the condenser — high-side pressure rises
        if refrigerant_charge > 1.0:
            excess = refrigerant_charge - 1.0
            P_cond *= 1.0 + 0.90 * excess
            T_cond = self.refrigerant.saturation_temperature(P_cond)
            T_cond = np.clip(T_cond, self.T_cond_min, self.T_cond_max)
            P_cond = self.refrigerant.saturation_pressure(T_cond)
        
        compression_ratio = P_cond / max(P_evap, 0.5)
        
        # === Rendements compresseur ===
        eta_is = self.calculate_isentropic_efficiency(compression_ratio, speed_ratio)
        eta_vol = self.calculate_volumetric_efficiency(compression_ratio, speed_ratio)
        
        # Superheat: less indoor airflow absorbs less heat → lower superheat (NIST).
        # Evaporator fouling still lengthens the two-phase region.
        superheat = 6.0 * (1.0 + 0.85 * evaporator_fouling) * (
            1.0 - 0.20 * (1.0 - fan_evap_ratio)
        )
        if refrigerant_charge < 1.0:
            superheat *= 1.0 + 1.4 * (1.0 - refrigerant_charge)
        if refrigerant_charge > 1.0:
            superheat *= max(1.0 - 1.4 * (refrigerant_charge - 1.0), 0.25)
        
        # Subcooling: condenser blockage backs liquid up (NIST: subcooling rises).
        # A condenser-fan fault mainly lifts T_cond and slightly cuts the liquid zone.
        subcooling = 4.5 * (1.0 + 0.65 * condenser_fouling) * (
            1.0 - 0.12 * (1.0 - fan_cond_ratio)
        )
        if refrigerant_charge < 1.0:
            subcooling *= max(refrigerant_charge, 0.25)
        if refrigerant_charge > 1.0:
            subcooling *= 1.0 + 2.2 * (refrigerant_charge - 1.0)
        subcooling = max(subcooling, 0.4)
        
        # === Températures aux bornes du compresseur ===
        T_suction = T_evap + superheat
        
        # Température de refoulement (relation polytropique)
        T_suction_K = T_suction + 273.15
        k = self.refrigerant.gamma
        T_discharge_K = T_suction_K * (compression_ratio ** ((k - 1) / k))
        T_discharge_ideal = T_discharge_K - 273.15
        
        # Correction par rendement isentropique
        T_discharge = T_suction + (T_discharge_ideal - T_suction) / eta_is
        T_discharge += 10.0 * (1.0 - fan_cond_ratio)
        # Lower evaporator airflow cools suction; CR rise must not invert the NIST sign.
        T_discharge -= 25.0 * (1.0 - fan_evap_ratio)
        T_discharge = min(float(T_discharge), self.T_discharge_max)
        
        # === Débit massique ===
        rho_suction = self.refrigerant.vapor_density(T_suction, P_evap)
        f_actual = self.f_nom * speed_ratio
        mass_flow = self.V_sw * f_actual * rho_suction * eta_vol
        if refrigerant_charge < 1.0:
            mass_flow *= 0.55 + 0.45 * refrigerant_charge
        if refrigerant_charge > 1.0:
            mass_flow *= 1.0 + 0.25 * (refrigerant_charge - 1.0)
        if fan_evap_ratio < 1.0:
            mass_flow *= 0.75 + 0.25 * fan_evap_ratio
        
        # === Enthalpies aux points du cycle ===
        h1 = self.refrigerant.enthalpy_vapor_sat(T_evap) + self.refrigerant.cp_vapor * superheat
        h3 = self.refrigerant.enthalpy_liquid_sat(T_cond) - 1.5 * subcooling
        h4 = h3  # Détente isenthalpique
        
        # Travail de compression
        delta_h_ideal = self.refrigerant.cp_vapor * (T_discharge_ideal - T_suction)
        delta_h_real = delta_h_ideal / eta_is
        h2 = h1 + delta_h_real
        
        # === Puissances thermiques ===
        Q_evap = mass_flow * (h1 - h4) * 1000  # W
        Q_cond = mass_flow * (h2 - h3) * 1000  # W
        W_comp = mass_flow * delta_h_real * 1000  # W
        
        # Pertes mécaniques et électriques (~10%)
        W_comp *= 1.10
        
        # === COP ===
        COP = Q_cond / W_comp if W_comp > 0 else 0
        
        # === Indicateurs de défauts ===
        fault_indicators = self._calculate_fault_indicators(
            T_evap, T_cond, T_discharge, superheat, subcooling,
            compression_ratio, Q_evap, Q_cond
        )
        
        # === Évaluation de l'état du système ===
        system_health = self._evaluate_system_health(
            T_evap, T_cond, T_discharge, compression_ratio, fault_indicators
        )
        
        return CycleResults(
            P_evap=P_evap,
            P_cond=P_cond,
            compression_ratio=compression_ratio,
            T_evap=T_evap,
            T_cond=T_cond,
            T_suction=T_suction,
            T_discharge=T_discharge,
            superheat=superheat,
            subcooling=subcooling,
            Q_evap=Q_evap,
            Q_cond=Q_cond,
            W_comp=W_comp,
            COP=COP,
            mass_flow=mass_flow,
            eta_isentropic=eta_is,
            eta_volumetric=eta_vol,
            system_health=system_health,
            fault_indicators=fault_indicators
        )
    
    def _calculate_fault_indicators(
        self,
        T_evap: float,
        T_cond: float,
        T_discharge: float,
        superheat: float,
        subcooling: float,
        compression_ratio: float,
        Q_evap: float,
        Q_cond: float
    ) -> Dict[str, float]:
        """Calcule les indicateurs de défauts normalisés."""
        
        indicators = {}
        
        # Indicateur de pression condensation anormale
        T_cond_ref = 45.0  # Température de référence
        indicators['cond_pressure_deviation'] = (T_cond - T_cond_ref) / 10.0
        
        # Indicateur de pression évaporation anormale
        T_evap_ref = 0.0
        indicators['evap_pressure_deviation'] = (T_evap_ref - T_evap) / 10.0
        
        # Indicateur de surchauffe anormale
        superheat_ref = 6.0
        indicators['superheat_deviation'] = (superheat - superheat_ref) / 5.0
        
        # Indicateur de température de refoulement
        T_discharge_ref = 80.0
        indicators['discharge_temp_deviation'] = (T_discharge - T_discharge_ref) / 30.0
        
        # Indicateur de taux de compression
        tau_ref = 3.0
        indicators['compression_ratio_deviation'] = (compression_ratio - tau_ref) / 2.0
        
        # Ratio de capacité
        capacity_ratio = Q_cond / self.capacity_nom if self.capacity_nom > 0 else 0
        indicators['capacity_ratio'] = capacity_ratio
        
        return indicators
    
    def _evaluate_system_health(
        self,
        T_evap: float,
        T_cond: float,
        T_discharge: float,
        compression_ratio: float,
        indicators: Dict[str, float]
    ) -> str:
        """Évalue l'état de santé global du système."""
        
        # Vérification des limites critiques
        if T_discharge > self.T_discharge_max:
            return "CRITICAL: Discharge temperature exceeded"
        
        if compression_ratio > 8.0:
            return "WARNING: High compression ratio"
        
        if T_evap < self.T_evap_min:
            return "WARNING: Low evaporation temperature"
        
        # Score basé sur les déviations
        total_deviation = sum(abs(v) for v in indicators.values())
        
        if total_deviation < 1.0:
            return "NORMAL"
        elif total_deviation < 2.0:
            return "DEGRADED"
        else:
            return "FAULT"
    
    def check_envelope(self, T_evap: float, T_cond: float) -> Dict[str, bool]:
        """Vérifie si le point de fonctionnement est dans l'enveloppe."""
        return {
            'in_envelope': (
                self.T_evap_min <= T_evap <= self.T_evap_max and
                self.T_cond_min <= T_cond <= self.T_cond_max
            ),
            'evap_temp_ok': self.T_evap_min <= T_evap <= self.T_evap_max,
            'cond_temp_ok': self.T_cond_min <= T_cond <= self.T_cond_max,
        }


if __name__ == "__main__":
    # Test du simulateur
    sim = HeatPumpSimulator()
    
    print("=== Test du Simulateur de Pompe à Chaleur ===\n")
    
    # Conditions nominales
    result = sim.simulate_cycle(T_source=7.0, T_sink=35.0, speed_ratio=1.0)
    print("Conditions nominales (7°C source, 35°C puits):")
    print(f"  COP: {result.COP:.2f}")
    print(f"  Q_cond: {result.Q_cond:.0f} W")
    print(f"  W_comp: {result.W_comp:.0f} W")
    print(f"  Taux compression: {result.compression_ratio:.2f}")
    print(f"  T_refoulement: {result.T_discharge:.1f} °C")
    print(f"  État: {result.system_health}")
    
    print("\n--- Effet encrassement condenseur 30% ---")
    result_fault = sim.simulate_cycle(
        T_source=7.0, T_sink=35.0, speed_ratio=1.0,
        condenser_fouling=0.3
    )
    print(f"  COP: {result_fault.COP:.2f} (vs {result.COP:.2f})")
    print(f"  T_cond: {result_fault.T_cond:.1f} °C (vs {result.T_cond:.1f} °C)")
    print(f"  État: {result_fault.system_health}")




