"""Nombres visibles de los ambientes; los códigos de simulación se conservan."""
LABELS = {
    'estable': 'Condiciones estables (sin incidentes)',
    'amonio': 'Acumulación de amoníaco en el agua',
    'hipoxia': 'Falta de oxígeno por falla de aireación',
    'termico': 'Aumento de temperatura del agua',
    'ph': 'Aumento del pH del agua',
    'combinado': 'Amoníaco alto, oxígeno bajo, temperatura y pH elevados',
}

PREVIOUS = {
    'Estable': LABELS['estable'], 'Amoníaco': LABELS['amonio'],
    'Oxígeno bajo': LABELS['hipoxia'], 'Temperatura': LABELS['termico'],
    'pH': LABELS['ph'], 'Combinado': LABELS['combinado'],
}


def simulation_name(name, scenario):
    parts = [PREVIOUS.get(part, part) for part in name.split(' · ')]
    label = LABELS.get(scenario, scenario)
    if label not in parts:
        parts.append(label)
    return ' · '.join(parts)
