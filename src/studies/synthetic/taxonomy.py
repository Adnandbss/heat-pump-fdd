"""Labels and default severities for the synthetic heating study."""

FAULT_PARAM_MAP = {
    "Normal": {},
    "Condenser_Fouling": {"condenser_fouling": 0.40},
    "Evaporator_Fouling": {"evaporator_fouling": 0.25},
    "Refrigerant_Undercharge": {"refrigerant_charge": 0.80},
    "Refrigerant_Overcharge": {"refrigerant_charge": 1.10},
    "Condenser_Fan_Fault": {"fan_cond_ratio": 0.55},
    "Evaporator_Fan_Fault": {"fan_evap_ratio": 0.55},
}

SCENARIOS = {
    "Normal": {
        "fault_type": "Normal",
        "params": {},
        "description": "Nominal A7/W40 operation",
    },
    "Condenser fouling 40%": {
        "fault_type": "Condenser_Fouling",
        "params": {"condenser_fouling": 0.40},
        "description": "Dirty condenser, heat rejection degraded",
    },
    "Evaporator fouling 25%": {
        "fault_type": "Evaporator_Fouling",
        "params": {"evaporator_fouling": 0.25},
        "description": "Dirty evaporator, source exchange degraded",
    },
    "Refrigerant leak 20%": {
        "fault_type": "Refrigerant_Undercharge",
        "params": {"refrigerant_charge": 0.80},
        "description": "20% undercharge from a leak",
    },
    "Refrigerant overcharge 10%": {
        "fault_type": "Refrigerant_Overcharge",
        "params": {"refrigerant_charge": 1.10},
        "description": "10% overcharge — extra liquid in the condenser",
    },
    "Condenser fan fault": {
        "fault_type": "Condenser_Fan_Fault",
        "params": {"fan_cond_ratio": 0.55},
        "description": "Condenser airflow reduced",
    },
    "Evaporator fan fault": {
        "fault_type": "Evaporator_Fan_Fault",
        "params": {"fan_evap_ratio": 0.55},
        "description": "Evaporator airflow reduced",
    },
}
