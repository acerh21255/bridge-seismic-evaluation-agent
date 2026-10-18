"""Configurable project rules. Values here are project decisions, not code clauses; each carries its basis."""

RULES = {
    # D7: bearings without a code displacement limit use the limit most often seen in earlier lab reports.
    'bearing_displacement_provisional_limit_m': 0.0375,
    'bearing_displacement_provisional_basis': '支座未提供地震作用下的规范位移限值，暂按以往报告中出现最多的限值 0.0375 m'
                                              '（G56 K491+390 报告）评定，待补充规范依据',
    'ratio_decimals': 3,
    'overstrength_min_factor': 1.0,
}

# Allowed units per verification kind (force kN, moment kN*m, displacement m, dimensionless ratio).
UNITS = {
    'e1_capacity': ('kN',),
    'e2_moment': ('kN*m',),
    'shear': ('kN',),
    'bearing_displacement': ('m',),
    'bearing_sliding': ('kN',),
    'measures': ('kN', 'm', 'ratio'),
    'hinge_shear': ('kN',),
    'ductility_displacement': ('m',),
    'ductility_reinforcement': ('ratio',),
    'additional': ('kN', 'kN*m', 'm', 'ratio'),
}

# Verification kinds allowed for each component kind.
KINDS_BY_COMPONENT = {
    'pier': ('e1_capacity', 'e2_moment', 'shear', 'hinge_shear', 'ductility_displacement', 'ductility_reinforcement'),
    'pile': ('e1_capacity', 'e2_moment', 'shear'),
    'bearing': ('bearing_displacement', 'bearing_sliding'),
    'measure': ('measures',),
    'capbeam': ('additional',),
    'tiebeam': ('additional',),
}

# Seismic levels allowed for each kind. E1 shear is not part of this project's flow.
LEVELS_BY_KIND = {
    'e1_capacity': ('E1',),
    'e2_moment': ('E2',),
    'shear': ('E2',),
    'hinge_shear': ('E2',),
    'ductility_displacement': ('E2',),
    'ductility_reinforcement': ('E2',),
    'bearing_displacement': ('E1', 'E2'),
    'bearing_sliding': ('E1', 'E2'),
    'measures': ('E1', 'E2'),
    'additional': ('E1', 'E2'),
}

DUCTILITY_KINDS = ('hinge_shear', 'ductility_displacement', 'ductility_reinforcement')
