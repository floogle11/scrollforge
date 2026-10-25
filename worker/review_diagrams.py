"""Assign only figures whose geometry and assumptions match the actual question.

No fallback artwork: an unrelated drawing is worse than a text-only question.
Plot data identifies the actual function and bounds, never a decorative curve.
"""

PRESETS = {
    'pipe': ('continuity', 'flowrate', 'reynolds', 'darcy', 'minor_loss', 'laminar_factor', 'laminar_scaling', 'fully_rough', 'laminar_profile'),
    'pump': ('head_pressure', 'pump_power'),
    'open_tank': ('hydrostatic',),
    'energy_balance': ('first_law',),
    'sealed_tank': ('ideal_gas_du', 'paddle_work', 'rigid_boundary'),
    'cycle': ('carnot_engine', 'engine_efficiency'),
    'fridge': ('refrigerator', 'heat_pump', 'carnot_fridge', 'cop_relation'),
    'turbine': ('turbine',),
    'lever': ('moment',),
    'beam': ('beam_center',),
    'beam_eccentric': ('beam_eccentric',),
    'beam_udl': ('uniform_load',),
    'beam_triangular': ('triangular_load', 'extra_triangle_centroid'),
    'vectors': ('force_resultant',),
    'member': ('axial_stress', 'extra_two_force', 'extra_axial_extension'),
    'stress': ('principal_stress',),
    'shaft': ('torsion_stress', 'shaft_scaling', 'angular_acceleration'),
    'rectangle': ('rectangle_inertia', 'extra_bending_scale'),
    'spring_undamped': ('natural_frequency', 'physics1_spring', 'extra_frequency_mass'),
    'spring': ('critical_damping', 'damping_ratio', 'damping_kind', 'extra_damped_frequency'),
    'damper': ('damper_force',),
    'parallel_springs': ('parallel_springs',),
    'series_springs': ('series_springs',),
    'circuit': ('rc_time',),
    'truss': ('zero_member',),
    'circle': ('calc1_related',),
    'polar': ('calc2_polar',),
    'revolution': ('calc2_disk',),
    'motion': ('physics1_velocity',),
    'forces': ('physics1_newton',),
    'falling': ('physics1_energy',),
    'collision': ('physics1_momentum',),
    'wave': ('physics1_wave',),
    'charges': ('physics2_coulomb',),
    'field': ('physics2_field',),
    'resistor': ('physics2_ohm',),
    'capacitor': ('physics2_capacitor',),
    'magnetic': ('physics2_magnetic',),
    'coil': ('physics2_faraday',),
    'lens': ('physics2_lens',),
    'incline': ('extra_incline',),
}


def attach_diagram(card):
    key = card['id'].removeprefix('study_')
    parts = key.rsplit('_', 1)
    v = int(parts[1]) if parts[-1].isdigit() else None
    name = parts[0] if v is not None else key
    card['diagram'] = next((kind for kind, names in PRESETS.items() if name in names), None)
    card.pop('diagram_data', None)
    if v is not None:
        a = v+2
        plots = {
            'calc1_integral': ('square', 0, a, 1, 'y = x²'),
            'calc2_parts': ('parts', 0, a, 1, 'y = x eˣ'),
            'calc2_substitution': ('substitution', 0, 1, a, f'y = {2*a}x exp({a}x²)'),
            'calc2_partial': ('rational', 1, a, 1, 'y = 1/[x(x+1)]'),
        }
        if name in plots:
            function, lower, upper, coefficient, label = plots[name]
            card['diagram'] = 'plot'
            card['diagram_data'] = dict(function=function, lower=lower, upper=upper, coefficient=coefficient, label=label)
            card['diagram_labels'] = [f'Lower bound = {lower}', f'Upper bound = {upper}']
    if not card['diagram']:
        card['diagram_labels'] = []
