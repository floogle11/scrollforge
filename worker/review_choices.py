"""Exact choices for mental review; distractors reflect specific algebra errors.

The first entry is correct. Shuffling belongs to the bank, not this module.
Keep transcendental constants unevaluated unless estimation is the objective.
"""
from fractions import Fraction


def fraction(n, d=1):
    q = Fraction(str(n)) / Fraction(str(d))
    return str(q.numerator) if q.denominator == 1 else rf"\frac{{{q.numerator}}}{{{q.denominator}}}"


def multiple(coefficient, expression):
    return expression if coefficient == 1 else f"{coefficient}{expression}"


def choices(key, value, unit):
    name, _, variant = key.rpartition('_')
    v = int(variant)
    a, b, n = v + 2, v + 1, v + 3
    exp = f"e^{{{a}}}"
    symbolic = {
        'calc1_product': [multiple(a+2, exp), multiple(2, exp), f'{a}e^{{{a-1}}}', f'{a+2}e^{{{a-1}}}'],
        'calc1_related': [multiple(2*a*b, r'\pi'), multiple(a*b, r'\pi'), multiple(-2*a*b, r'\pi'), multiple(2*a*a*b, r'\pi')],
        'calc2_substitution': [f'{exp}-1', exp, f'{exp}+1', f'{fraction(1,a)}({exp}-1)'],
        'calc2_parts': [f'{multiple(a-1, exp)}+1', f'{multiple(a-1, exp)}-1', multiple(a, exp), f'{multiple(a+1, exp)}-1'],
        'calc2_improper': [fraction(1,n-1), fraction(1,n), fraction(-1,n-1), r'\infty'],
        'calc2_geometric': [fraction(a,a-1), fraction(1,a-1), fraction(a-1,a), fraction(a,a+1)],
        'calc2_disk': [multiple(fraction(a**3,3), r'\pi'), multiple(a**3, r'\pi'), multiple(fraction(a*a,2), r'\pi'), fraction(a**3,3)],
        'calc2_polar': [multiple(fraction(a*a,4), r'\pi'), multiple(fraction(a*a,2), r'\pi'), multiple(a*a, r'\pi'), fraction(a*a,4)],
        'calc2_partial': [rf'\ln\left({fraction(2*a,a+1)}\right)', rf'\ln\left({fraction(a,a+1)}\right)', rf'\ln\left({fraction(a+1,2*a)}\right)', rf'\ln({a})'],
        'calc3_gradient': [rf'2\sqrt{{{a*a+b*b}}}', str(a*a+b*b), str(2*(a+b)), rf'\sqrt{{{a*a+b*b}}}'],
        'ode_decay': [f'{10*b}e^{{-{a}}}', f'{10*b}e^{{{a}}}', f'e^{{-{a}}}', str(10*b-a)],
        'physics1_energy': [rf'\sqrt{{{2*9.81*a:g}}}', rf'\sqrt{{{9.81*a:g}}}', f'{2*9.81*a:g}', rf'2\sqrt{{{9.81*a:g}}}'],
        'physics1_spring': [r'\frac{\pi}{5}', r'\frac{1}{10}', r'\frac{\pi}{10}', r'20\pi'],
    }
    if name == 'period':
        omega = 5+5*v
        symbolic[name] = [multiple(fraction(2,omega), r'\pi'), fraction(1,omega), multiple(fraction(1,omega), r'\pi'), multiple(2*omega, r'\pi')]
    if name == 'torsion_stress':
        coefficient = 2*(20+10*v)
        symbolic[name] = [rf'\frac{{{coefficient}}}{{\pi}}', rf'\frac{{{coefficient//2}}}{{\pi}}', rf'\frac{{{2*coefficient}}}{{\pi}}', rf'{coefficient}\pi']
    if name == 'principal_stress':
        center = (40+10*v)//2
        radius = rf'\sqrt{{{center**2+900}}}'
        symbolic[name] = [f'{center}+{radius}', f'{center}-{radius}', radius, str(2*center+30)]
    if name == 'critical_damping':
        root = rf'\sqrt{{{v+1}}}'
        symbolic[name] = [f'20{root}', f'10{root}', str(200*(v+1)), f'-20{root}']
    if name == 'continuity':
        q = Fraction(8+4*v, 1000)
        diameter = Fraction(8+2*v, 100)
        coefficient = 4*q/diameter**2
        def over_pi(q):
            denominator = multiple(q.denominator, r'\pi')
            return rf'\frac{{{q.numerator}}}{{{denominator}}}'
        symbolic[name] = [over_pi(coefficient), over_pi(coefficient/4), over_pi(coefficient*4), multiple(fraction(coefficient), r'\pi')]
    if name in symbolic:
        expressions = symbolic[name]
    else:
        # Arithmetic choices target omitted terms, sign, units and wrong operations.
        mistakes = {
            'calc1_limit': [2*a, a, 0, a*a],
            'calc1_power': [n*2**(n-1), 2**n, n*2**n, 2**(n-1)],
            'calc1_chain': [3*a, 3, a, 3*a*a],
            'calc1_integral': [Fraction(a**3,3), a**3, a*a, Fraction(a**3,2)],
            'calc1_ftc': [2*(1+a), 1+a, 2*a, a],
            'calc1_optimize': [2*a, 4*a, a, 8*a],
            'calc2_taylor': [Fraction(1)+Fraction(b,10)+Fraction(b*b,200), Fraction(1)+Fraction(b,10), Fraction(1)+Fraction(b,10)+Fraction(b*b,100), Fraction(b,10)+Fraction(b*b,200)],
            'calc3_partial': [4*b, 4*b+2*a*b, 2*b, 4+2*a*b],
            'calc3_direction': [Fraction(6*a+8*b,5), 6*a+8*b, Fraction(6*a+8*b,25), Fraction(6*a-8*b,5)],
            'calc3_double': [Fraction(a*b*(a+b),2), a*b*(a+b), Fraction(a*b*(a+b),4), a+b],
            'calc3_triple': [6*a*b, 2*a*b, 3*a*b, a*b],
            'calc3_divergence': [a+b+2, a*b*2, a+b, 0],
            'calc3_curl': [2*a, 0, -2*a, a],
            'calc3_line': [a*a+b*b, 2*(a*a+b*b), a+b, 0],
            'linear_det': [a*(a+1)-2, a*(a+1)+2, 2*a+1, a*(a+1)],
            'linear_system': [a, b, 2*a, a+b],
            'linear_eigen': [a+2, a, 2*a+2, a*(a+2)],
            'linear_projection': [a, b, a*a, a+b],
            'ode_forcing': [3*b, a*3*b, -3*b, 0],
            'ode_ivp': [4*a+b, 4*a, 2*a+b, 8*a+b],
            'ode_roots': [a+1, a, 2*a+1, a*(a+1)],
            'physics1_velocity': [b+3*a, 3*a, b+a, b+Fraction(9*a,2)],
            'physics1_projectile': [b, 2*b, Fraction(b,2), b*b+1],
            'physics1_newton': [4, 8, 6, -4],
            'physics1_momentum': [3, 6, 12, 0],
            'physics1_rotation': [Fraction(a*(b+2)**2,2), a*(b+2)**2, Fraction(a*(b+2),2), Fraction((b+2)**2,2)],
            'physics1_wave': [5*a*b, Fraction(5*a,b), Fraction(b,5*a), 5*a+b],
            'physics2_ohm': [Fraction(2*a,b), Fraction(b,2*a), 2*a*b, 18*a*b],
            'physics2_lens': [Fraction(15*a,2), Fraction(15*a,4), 10*a, -Fraction(15*a,2)],
        }
        if name in mistakes:
            values = mistakes[name]
            # Some variants collapse common mistakes (e.g. multiplying by one).
            unique = list(dict.fromkeys(values))
            for candidate in (-value, 0, value+1, 3*value):
                if len(unique) == 4:
                    break
                if candidate not in unique:
                    unique.append(candidate)
            expressions = [fraction(x) for x in unique]
        else:
            return [f'{x:.4g} {unit}'.strip() for x in (value, value*.5, value*2, value*4)], False
    suffix = f' {unit}' if unit else ''
    return [f'${expression}${suffix}' for expression in expressions], True
