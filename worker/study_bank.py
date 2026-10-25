"""Original illustrated review questions with calculated, reproducible answers.

Run ``python -m worker.study_bank`` to merge the bank into the existing feed.
Numerical variants change the givens, not just the answer order. No source
textbook pages, lecture figures, or private student files are published.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

STAMP = "2026-10-25T00:00:00Z"
COURSES = {"fluids": "ME-3310", "thermo": "ENGR-2300", "statics": "ME-2010",
           "design": "ME-3140", "dynamics": "ME-3010"}


def _number(value: float) -> str:
    return f"{value:.4g}"


def build_bank() -> list[dict]:
    cards = []

    def add(key, course, title, body, answer, wrong, solution, diagram, labels=(), topic=""):
        options = [str(answer), *(str(value) for value in wrong)]
        if not 4 <= len(options) <= 8 or len(options) != len(set(options)):
            raise ValueError(f"Invalid answer choices: {key}")
        rng = random.Random(hashlib.sha256(key.encode()).hexdigest())
        rng.shuffle(options)
        cards.append({"id": "study_" + key, "created_at": STAMP,
                      "category": "CHALLENGE_PAST" if course == "statics" else "CHALLENGE_CURRENT",
                      "course_tag": COURSES[course], "title": title, "body_markdown": body,
                      "solution_markdown": solution, "source_url": None, "parent_card_id": None,
                      "comments": [], "quiz": {"options": options, "correct_index": options.index(str(answer))},
                      "diagram": diagram, "diagram_labels": list(labels), "topic": topic or title})

    def numeric(key, course, title, body, value, unit, solution, diagram, labels=()):
        correct = f"{_number(value)} {unit}".strip()
        distractors = [f"{_number(value * factor)} {unit}".strip() for factor in (0.5, 2, 4)]
        add(key, course, title, body + " Choose the closest value.", correct, distractors,
            solution + f"\nThe result is **{correct}**. Check the units before choosing.", diagram, labels)

    for v in range(4):
        # Fluids: continuity, similitude, energy balances, and pipe losses.
        q, d = 0.008 + 0.004*v, 0.08 + 0.02*v
        speed = q / (math.pi*d*d/4)
        numeric(f"continuity_{v}", "fluids", "How fast is the water moving?",
                f"Steady incompressible water flows at $Q={q:g}$ m³/s in a circular pipe of inside diameter $D={d:g}$ m. Find the mean speed.",
                speed, "m/s", "$A=\\pi D^2/4$ and $V=Q/A$. Use the inside diameter.", "pipe", [f"Q = {q:g} m³/s", f"D = {d:g} m"])
        velocity, area = 1.5+v, 0.003+0.001*v
        numeric(f"flowrate_{v}", "fluids", "Turn velocity into flow rate",
                f"A uniform mean speed of {velocity:g} m/s crosses an area of {area:g} m². What is the volume flow rate?",
                velocity*area*1000, "L/s", "$Q=AV$. Convert m³/s to L/s by multiplying by 1000.", "pipe", [f"V = {velocity:g} m/s", f"A = {area:g} m²"])
        velocity, d = 0.01+0.005*v, 0.05
        re = 1000*velocity*d/0.001
        numeric(f"reynolds_{v}", "fluids", "A quick Reynolds-number check",
                f"Water has density 1000 kg/m³ and viscosity 0.001 Pa·s. In a {d:g} m pipe its mean speed is {velocity:g} m/s. Find Reynolds number.",
                re, "", "$Re=\\rho VD/\\mu$. Reynolds number is dimensionless.", "pipe", [f"V = {velocity:g} m/s", "D = 0.05 m"])
        f, length, d, vel = .02, 10+5*v, .1, 2+v
        numeric(f"darcy_{v}", "fluids", "What head does the pipe lose?",
                f"Use a Darcy friction factor of {f:g}, pipe length {length:g} m, diameter {d:g} m and speed {vel:g} m/s. Find frictional head loss. Take $g=9.81$ m/s².",
                f*length/d*vel**2/(2*9.81), "m", "$h_L=f(L/D)V^2/(2g)$. This is the Darcy factor, not the Fanning factor.", "pipe", [f"L = {length} m", "D = 0.1 m", f"V = {vel} m/s"])
        head = 3+2*v
        numeric(f"head_pressure_{v}", "fluids", "Head and pressure are different units",
                f"A pump raises water pressure by a head of {head} m. With density 1000 kg/m³ and $g=9.81$ m/s², what pressure rise does that represent?",
                1000*9.81*head/1000, "kPa", "$\\Delta p=\\rho gh$. Divide pascals by 1000 to obtain kPa.", "pump", [f"Head rise = {head} m"])
        flow, head, eta = .01+.005*v, 8+2*v, .8
        numeric(f"pump_power_{v}", "fluids", "What does the pump draw at the shaft?",
                f"A pump supplies water at {flow:g} m³/s with a {head} m head rise. Density is 1000 kg/m³, gravity is 9.81 m/s² and pump efficiency is 80%. Find required shaft power.",
                1000*9.81*flow*head/eta/1000, "kW", "$P_{fluid}=\\rho gQh_p$; required shaft power is $P_{fluid}/\\eta$.", "pump", [f"Q = {flow:g} m³/s", f"Head = {head} m", "η = 80%"])
        k, vel = 1+v, 2+v
        numeric(f"minor_loss_{v}", "fluids", "The fitting has a cost too",
                f"A fitting has loss coefficient $K={k}$ based on a reference speed of {vel} m/s. Find its head loss using $g=9.81$ m/s².",
                k*vel*vel/(2*9.81), "m", "$h_L=KV^2/(2g)$. Use the velocity on which the coefficient is based.", "pipe", [f"K = {k}", f"Reference V = {vel} m/s"])
        re = 400+200*v
        numeric(f"laminar_factor_{v}", "fluids", "Darcy factor in laminar flow",
                f"Fully developed laminar flow in a circular pipe has Reynolds number {re}. What is its Darcy friction factor?",
                64/re, "", "$f_D=64/Re$ for fully developed laminar circular-pipe flow.", "pipe", [f"Re = {re}", "Fully developed; circular pipe"])
        depth = .5+.5*v
        numeric(f"hydrostatic_{v}", "fluids", "Pressure below the free surface",
                f"An open tank holds water of density 1000 kg/m³. Find the gauge pressure {depth:g} m below the free surface. Use $g=9.81$ m/s².",
                1000*9.81*depth/1000, "kPa", "$p_g=\\rho gh$. Atmospheric pressure cancels when using gauge pressure.", "tank", [f"Depth = {depth:g} m", "Open to atmosphere"])
        factor = v+2
        numeric(f"laminar_scaling_{v}", "fluids", "A wider pipe, same flow rate",
                f"In fully developed laminar flow, pressure drop at fixed flow rate and length scales as $D^{{-4}}$. Multiply the diameter by {factor}. By what factor does the original pressure drop exceed the new drop?",
                factor**4, "", "$\\Delta p\\propto Q/D^4$. The ratio of original to new pressure drop is the diameter ratio to the fourth power.", "pipe", [f"D₂ = {factor}D₁", "Q and L fixed"])

        # Thermodynamics: explicit signs, absolute temperatures and device balances.
        heat, work = 50+10*v, 10+5*v
        numeric(f"first_law_{v}", "thermo", "Track what stays inside the system",
                f"A closed system receives {heat} kJ of heat and does {work} kJ of work. Neglect kinetic and potential energy changes. Find its internal-energy increase.",
                heat-work, "kJ", "$\\Delta U=Q-W$ with heat in positive and work out positive.", "tank", [f"Heat in = {heat} kJ", f"Work out = {work} kJ"])
        mass, dt, cv = 2+v, 20+10*v, .718
        numeric(f"ideal_gas_du_{v}", "thermo", "Heating the gas in a rigid tank",
                f"An ideal gas has mass {mass} kg and constant $c_v=0.718$ kJ/(kg·K). Its temperature rises by {dt} K. Find its change in internal energy.",
                mass*cv*dt, "kJ", "$\\Delta U=mc_v\\Delta T$ for an ideal gas with constant specific heat.", "tank", [f"m = {mass} kg", f"ΔT = {dt} K"])
        work = 15+5*v
        numeric(f"paddle_work_{v}", "thermo", "Insulated does not mean no energy change",
                f"A rigid insulated tank receives {work} kJ of paddle-wheel shaft work. All other energy transfers and kinetic/potential changes are negligible. Find the increase in internal energy.",
                work, "kJ", "$Q=0$ and work done by the system is negative: $W=-W_{in}$. Thus $\\Delta U=W_{in}$.", "tank", [f"Shaft work in = {work} kJ", "Rigid and insulated"])
        hin, hout = 3100+100*v, 2600
        numeric(f"turbine_{v}", "thermo", "Enthalpy drop to turbine work",
                f"A steady adiabatic turbine has inlet enthalpy {hin} kJ/kg and outlet enthalpy {hout} kJ/kg. Ignore speed and elevation changes. Find specific work output.",
                hin-hout, "kJ/kg", "$w_{out}=h_{in}-h_{out}$ under the stated steady-flow assumptions.", "turbine", [f"h in = {hin} kJ/kg", f"h out = {hout} kJ/kg"])
        hot, cold = 600+100*v, 300
        numeric(f"carnot_engine_{v}", "thermo", "The efficiency ceiling",
                f"A heat engine works between reservoirs at {hot} K and {cold} K. What is the largest theoretically possible thermal efficiency?",
                (1-cold/hot)*100, "%", "$\\eta_{max}=1-T_C/T_H$. Temperatures must be absolute kelvin.", "cycle", [f"Hot = {hot} K", f"Cold = {cold} K"])
        qh, qc = 500+100*v, 300
        numeric(f"engine_efficiency_{v}", "thermo", "Where did the heat go?",
                f"Over a complete cycle an engine receives {qh} kJ and rejects {qc} kJ. What is its thermal efficiency?",
                (qh-qc)/qh*100, "%", "$W_{net}=Q_H-Q_C$ and $\\eta=W_{net}/Q_H$.", "cycle", [f"Q hot = {qh} kJ", f"Q cold = {qc} kJ"])
        ql, win = 600+100*v, 200
        numeric(f"refrigerator_{v}", "thermo", "How much cooling per unit work?",
                f"A refrigerator removes {ql} kJ from a cold space using {win} kJ of work input. Find its coefficient of performance.",
                ql/win, "", "$COP_R=Q_L/W_{in}$. COP is not an efficiency percentage and can exceed one.", "fridge", [f"Cooling = {ql} kJ", f"Work in = {win} kJ"])
        qh, win = 800+100*v, 200
        numeric(f"heat_pump_{v}", "thermo", "A heat pump's useful output",
                f"A heat pump delivers {qh} kJ of heat to a room for {win} kJ of work input. Find its heating COP.",
                qh/win, "", "$COP_{HP}=Q_H/W_{in}$. The useful output is heat delivered to the warm space.", "fridge", [f"Heat delivered = {qh} kJ", f"Work in = {win} kJ"])
        cold, hot = 260+5*v, 300+5*v
        numeric(f"carnot_fridge_{v}", "thermo", "The ideal refrigeration limit",
                f"An ideal reversible refrigerator operates between {cold} K and {hot} K. Find its maximum refrigeration COP.",
                cold/(hot-cold), "", "$COP_{R,max}=T_L/(T_H-T_L)$. The temperature difference is the temperature lift.", "fridge", [f"Cold = {cold} K", f"Hot = {hot} K"])
        mass, dt = 2+v, 10+5*v
        numeric(f"liquid_heat_{v}", "thermo", "Warm up a mass of water",
                f"Heat {mass} kg of liquid water by {dt} K. Treat it as incompressible with $c=4.18$ kJ/(kg·K), negligible work, and negligible kinetic/potential changes. Find heat input.",
                mass*4.18*dt, "kJ", "$Q=\\Delta U\\approx mc\\Delta T$ under the stated assumptions.", "tank", [f"m = {mass} kg", f"ΔT = {dt} K"])

        # Statics: original short equilibrium and resultant-load examples.
        force, arm = 20+10*v, .2+.1*v
        numeric(f"moment_{v}", "statics", "Use the perpendicular moment arm",
                f"A force of {force} N has a perpendicular distance of {arm:g} m from a pivot. Find the magnitude of its moment about the pivot.",
                force*arm, "N·m", "$|M|=Fd_\\perp$. The distance must be perpendicular to the force's line of action.", "beam", [f"F = {force} N", f"Perpendicular arm = {arm:g} m"])
        load = 8+4*v
        numeric(f"beam_center_{v}", "statics", "One centered load, two supports",
                f"A simply supported beam carries only a centered downward point load of {load} kN. Neglect beam weight. Find the upward reaction at the left support.",
                load/2, "kN", "$R_A+R_B=P$. Symmetry gives $R_A=R_B=P/2$.", "beam", [f"Centered P = {load} kN", "Equal half spans"])
        length, load, a = 6, 12+6*v, 2
        numeric(f"beam_eccentric_{v}", "statics", "A load closer to one support",
                f"A simply supported beam is {length} m long. A downward {load} kN point load acts {a} m from the left support. Neglect beam weight. Find the right support reaction.",
                load*a/length, "kN", "Take moments about the left support: $R_B L=Pa$. Then $R_B=Pa/L$.", "beam_eccentric", [f"P = {load} kN", "a = 2 m; L = 6 m"])
        w, length = 2+v, 4+v
        numeric(f"uniform_load_{v}", "statics", "Replace a distributed load",
                f"A uniform downward load of {w} kN/m covers a {length} m beam. What is its total equivalent force for external equilibrium?",
                w*length, "kN", "$F_{eq}=wL$, acting at the midpoint of the loaded length.", "beam_udl", [f"w = {w} kN/m", f"Loaded length = {length} m"])
        peak, length = 6+2*v, 3+v
        numeric(f"triangular_load_{v}", "statics", "The area under the triangular load",
                f"A triangular load rises from zero to {peak} kN/m over {length} m. Find the magnitude of the resultant force.",
                peak*length/2, "kN", "The resultant equals the triangle's area: $F=\\tfrac12 w_{max}L$.", "beam_triangular", [f"Peak w = {peak} kN/m", f"Length = {length} m"])
        fx, fy = 3*(v+1), 4*(v+1)
        numeric(f"force_resultant_{v}", "statics", "Combine perpendicular force components",
                f"A force has perpendicular components of {fx} N horizontally and {fy} N vertically. Find its magnitude.",
                math.hypot(fx,fy), "N", "$F=\\sqrt{F_x^2+F_y^2}$. Components form the legs of a right triangle.", "vectors", [f"Fx = {fx} N", f"Fy = {fy} N"])

        # Machine design: material stress, torsion, bending and stress concentration.
        force, area = 12000+4000*v, 200+50*v
        numeric(f"axial_stress_{v}", "design", "A first stress estimate",
                f"A prismatic bar carries an axial tensile force of {force} N across an area of {area} mm². Ignore stress concentrations. Find average normal stress.",
                force/area, "MPa", "$\\sigma=F/A$. One N/mm² equals one MPa.", "stress", [f"F = {force} N", f"A = {area} mm²"])
        moment, c, inertia = 100+50*v, 20, 80000
        numeric(f"bending_stress_{v}", "design", "Stress at the beam's outer fiber",
                f"Elastic bending has moment {moment} N·m, outer-fiber distance {c} mm and second moment of area {inertia} mm⁴. Find the magnitude of bending stress.",
                moment*1000*c/inertia, "MPa", "$|\\sigma|=Mc/I$. Convert N·m to N·mm before substituting.", "beam", [f"M = {moment} N·m", "c = 20 mm", "I = 80000 mm⁴"])
        torque, diameter = 20+10*v, 20
        numeric(f"torsion_stress_{v}", "design", "Twist a solid circular shaft",
                f"A solid circular shaft of diameter {diameter} mm carries torque {torque} N·m. Using elastic torsion, find the maximum shear stress.",
                16*torque*1000/(math.pi*diameter**3), "MPa", "$\\tau_{max}=Tc/J=16T/(\\pi d^3)$ for a solid circular shaft.", "shaft", [f"T = {torque} N·m", "d = 20 mm"])
        sx, sy, txy = 40+10*v, 0, 30
        principal = (sx+sy)/2+math.sqrt(((sx-sy)/2)**2+txy**2)
        numeric(f"principal_stress_{v}", "design", "Find the larger in-plane principal stress",
                f"Plane stress has $\\sigma_x={sx}$ MPa, $\\sigma_y=0$, and $\\tau_{{xy}}={txy}$ MPa. Find the larger in-plane principal normal stress.",
                principal, "MPa", "$\\sigma_{max,in}=(\\sigma_x+\\sigma_y)/2+\\sqrt{[(\\sigma_x-\\sigma_y)/2]^2+\\tau_{xy}^2}$.", "stress", [f"σx = {sx} MPa", "σy = 0", "τxy = 30 MPa"])
        high, low = 80+20*v, -20
        numeric(f"absolute_shear_{v}", "design", "The largest of the three Mohr circles",
                f"The ordered principal stresses are {high} MPa, 10 MPa and {low} MPa. Find the absolute maximum shear stress.",
                (high-low)/2, "MPa", "$\\tau_{max,abs}=(\\sigma_1-\\sigma_3)/2$. Use the largest and smallest of all three principal stresses.", "mohr", [f"σ₁ = {high} MPa", "σ₂ = 10 MPa", "σ₃ = −20 MPa"])
        nominal, kt = 20+10*v, 2.5
        numeric(f"stress_concentration_{v}", "design", "A shoulder changes local stress",
                f"Nominal elastic normal stress is {nominal} MPa. The theoretical stress concentration factor based on the same nominal section is $K_t=2.5$. Estimate peak local elastic stress.",
                kt*nominal, "MPa", "$\\sigma_{peak}=K_t\\sigma_{nom}$. The concentration factor must use the same reference section.", "shaft", [f"Nominal σ = {nominal} MPa", "Kt = 2.5"])
        width, height = 10+5*v, 20
        numeric(f"rectangle_inertia_{v}", "design", "A rectangle's bending stiffness geometry",
                f"A rectangular section has width {width} mm and vertical height {height} mm. Find its second moment of area about the horizontal centroidal axis.",
                width*height**3/12, "mm⁴", "$I_x=bh^3/12$. The dimension perpendicular to the bending axis is cubed.", "rectangle", [f"b = {width} mm", "h = 20 mm"])
        original, factor = 80, v+2
        numeric(f"shaft_scaling_{v}", "design", "What does a larger shaft buy you?",
                f"A solid circular shaft has maximum torsional shear stress of {original} MPa. Increase its diameter by a factor of {factor}, keeping torque unchanged. Find the new maximum shear stress.",
                original/factor**3, "MPa", "$\\tau_{max}\\propto d^{-3}$ at fixed torque for a solid circular shaft.", "shaft", [f"Initial τ = {original} MPa", f"New diameter = {factor}d"])

        # System dynamics: force models, natural response and a first-order circuit.
        force, mass = 20+10*v, 4+v
        numeric(f"newton_{v}", "dynamics", "Net force sets acceleration",
                f"A net horizontal force of {force} N acts on a translating {mass} kg mass. Find horizontal acceleration.",
                force/mass, "m/s²", "$a=F_{net}/m$. Use the resultant force, not one isolated load.", "spring", [f"Net F = {force} N", f"m = {mass} kg"])
        k, displacement = 200+100*v, .02+.01*v
        numeric(f"spring_force_{v}", "dynamics", "A spring resists displacement",
                f"A linear spring has stiffness {k} N/m and extension {displacement:g} m from its unloaded length. Find the magnitude of its restoring force.",
                k*displacement, "N", "$|F_s|=k|x|$. The restoring force points opposite to displacement.", "spring", [f"k = {k} N/m", f"Extension = {displacement:g} m"])
        mass, k = 2+v, 200+100*v
        numeric(f"natural_frequency_{v}", "dynamics", "The undamped natural frequency",
                f"A mass of {mass} kg is attached to a linear spring of stiffness {k} N/m. Neglect damping. Find the natural angular frequency.",
                math.sqrt(k/mass), "rad/s", "$\\omega_n=\\sqrt{k/m}$. Angular frequency is in rad/s, not hertz.", "spring", [f"m = {mass} kg", f"k = {k} N/m"])
        mass, k = 1+v, 100
        numeric(f"critical_damping_{v}", "dynamics", "How much damping is critical?",
                f"A single-degree-of-freedom system has mass {mass} kg and stiffness {k} N/m. Find the critical viscous damping coefficient.",
                2*math.sqrt(k*mass), "N·s/m", "$c_c=2\\sqrt{km}$ for a linear mass–spring–damper system.", "spring", [f"m = {mass} kg", "k = 100 N/m"])
        c, mass, k = 2+v, 1, 100
        numeric(f"damping_ratio_{v}", "dynamics", "Compare damping with the critical value",
                f"A system has mass 1 kg, stiffness 100 N/m and viscous damping coefficient {c} N·s/m. Find the damping ratio.",
                c/(2*math.sqrt(k*mass)), "", "$\\zeta=c/(2\\sqrt{km})$. A damping ratio between zero and one is underdamped.", "spring", ["m = 1 kg; k = 100 N/m", f"c = {c} N·s/m"])
        omega = 5+5*v
        numeric(f"period_{v}", "dynamics", "From angular frequency to period",
                f"An undamped oscillator has angular natural frequency {omega} rad/s. What is its oscillation period?",
                2*math.pi/omega, "s", "$T=2\\pi/\\omega_n$. One full cycle spans $2\\pi$ radians.", "spring", [f"ωn = {omega} rad/s"])
        resistance, cap = 10+5*v, 100
        numeric(f"rc_time_{v}", "dynamics", "A circuit has a time scale too",
                f"A first-order series RC circuit has resistance {resistance} kΩ and capacitance {cap} μF. Find its time constant.",
                resistance*1000*cap*1e-6, "s", "$\\tau=RC$. Convert kΩ to Ω and μF to F first.", "circuit", [f"R = {resistance} kΩ", "C = 100 μF"])
        k1, k2 = 100+50*v, 200+50*v
        numeric(f"parallel_springs_{v}", "dynamics", "Springs sharing the same motion",
                f"Two linear springs of stiffness {k1} and {k2} N/m act in parallel on the same translating mass. Find their equivalent stiffness.",
                k1+k2, "N/m", "Parallel springs have equal displacement and their forces add: $k_{eq}=k_1+k_2$.", "parallel_springs", [f"k₁ = {k1} N/m", f"k₂ = {k2} N/m", "Parallel connection"])
        torque, inertia = 4+2*v, .5
        numeric(f"angular_acceleration_{v}", "dynamics", "The rotational version of Newton's law",
                f"A rigid rotor has fixed-axis mass moment of inertia {inertia:g} kg·m² and net torque {torque} N·m. Find angular acceleration.",
                torque/inertia, "rad/s²", "$\\alpha=\\tau_{net}/J$ for rotation about a fixed axis.", "shaft", [f"Net torque = {torque} N·m", "J = 0.5 kg·m²"])
        c, vel = 10+5*v, .2+.1*v
        numeric(f"damper_force_{v}", "dynamics", "Velocity controls a viscous damper",
                f"A linear viscous damper has coefficient {c} N·s/m and relative end velocity {vel:g} m/s. Find the magnitude of the damping force.",
                c*vel, "N", "$|F_d|=c|v_{relative}|$. Damping resists relative velocity, not displacement.", "spring", [f"c = {c} N·s/m", f"Relative v = {vel:g} m/s"])

    concepts = [
        ("series_pipes", "fluids", "What stays equal in series pipes?", "Steady incompressible flow passes through two pipe segments connected in series without leaks. Which quantity must be the same in both segments?", "Volume flow rate", ["Mean speed", "Pressure", "Friction factor"], "Continuity requires the same flow rate through both segments. Different areas produce different velocities.", "pipe"),
        ("parallel_pipes", "fluids", "Parallel branches share a constraint", "Two pipe branches connect the same two junctions. In steady flow, which statement must hold?", "Both branches have the same total head drop", ["Both have the same flow rate", "Both have the same velocity", "Both have zero friction loss"], "Each branch connects the same head endpoints. Its own resistance determines the flow rate.", "pipe"),
        ("fully_rough", "fluids", "Fully rough turbulence", "In the fully rough turbulent limit, the Darcy friction factor depends primarily on what?", "Relative roughness", ["Reynolds number alone", "Pipe length alone", "Atmospheric pressure"], "In this limiting regime, friction factor depends on relative roughness and is approximately independent of Reynolds number.", "pipe"),
        ("pump_operating", "fluids", "Where does the pump actually run?", "For a fixed-speed pump serving a pipe system, what determines the steady operating point?", "The intersection of pump and system curves", ["The pump's maximum possible flow alone", "The highest pump efficiency alone", "The tank volume alone"], "The pump must supply exactly the head the system requires at the same flow rate.", "pump"),
        ("ideal_bernoulli", "fluids", "Before using ideal Bernoulli", "Which situation requires an extended energy balance rather than the ideal, lossless Bernoulli equation between the two sections?", "A pump adds shaft work between the sections", ["The pipe diameter changes smoothly", "The elevation changes", "The mean speed changes"], "Pump work and irreversible losses need explicit terms in the extended energy equation.", "pump"),
        ("laminar_profile", "fluids", "Velocity across a laminar pipe", "Fully developed laminar flow of a Newtonian fluid in a stationary circular pipe has which velocity profile?", "Parabolic with zero wall velocity", ["Uniform right to the wall", "Maximum velocity at the wall", "Linear with radius everywhere"], "No-slip gives zero wall velocity; the laminar circular-pipe solution is parabolic with its maximum at the centerline.", "pipe"),
        ("rigid_boundary", "thermo", "What does a rigid tank rule out?", "A closed tank has fixed volume. Which energy transfer is necessarily zero?", "Moving-boundary work", ["Shaft work", "Heat transfer", "Electrical work"], "Boundary work is the integral of pressure with respect to volume. Fixed volume makes it zero.", "tank"),
        ("adiabatic_entropy", "thermo", "Adiabatic and isentropic are different", "A closed system undergoes an adiabatic process with internal friction. What can happen to its entropy?", "It increases due to entropy generation", ["It must stay constant", "It must decrease", "It becomes zero"], "Adiabatic means no heat transfer. Irreversibility can still generate entropy.", "tank"),
        ("throttling", "thermo", "Across a throttling valve", "For steady throttling with no shaft work and negligible kinetic and potential changes, which specific property is approximately conserved?", "Enthalpy", ["Entropy", "Pressure", "Density"], "The steady-flow first law reduces to equal inlet and outlet enthalpy. Entropy need not be constant.", "pipe"),
        ("cop_relation", "thermo", "One cycle, two useful outputs", "For the same refrigeration cycle, how are heat-pump and refrigerator COP related?", "COP of the heat pump is COP of the refrigerator plus one", ["They are always equal", "Their product is one", "The heat pump COP is always below one"], "Energy conservation gives QH = QL + Win. Divide every term by work input.", "fridge"),
        ("ideal_gas_energy", "thermo", "An ideal gas's internal energy", "For an ideal gas of fixed composition, specific internal energy depends on which independent variable?", "Temperature", ["Pressure alone", "Volume alone", "Mass flow rate alone"], "For an ideal gas, internal energy is a function of temperature. This does not make all real fluids ideal gases.", "tank"),
        ("entropy_work", "thermo", "Which transfer carries no entropy?", "Which interaction transfers energy across a system boundary without directly transferring entropy?", "Work", ["Heat transfer at finite boundary temperature", "A flowing mass stream", "Both heat and flowing mass"], "Work transfers energy but no entropy. Heat and flowing mass can transport entropy.", "cycle"),
        ("pin_reactions", "statics", "Replace a planar pin correctly", "How many independent reaction components does an ideal planar pin provide?", "Two forces and no reaction couple", ["One force only", "Two forces and a reaction couple", "One couple only"], "A pin prevents translation in both directions but permits rotation in the plane.", "beam"),
        ("roller_reaction", "statics", "A frictionless roller's direction", "A frictionless roller rests against a smooth inclined surface. Its reaction acts in which direction?", "Normal to the surface", ["Always vertically upward", "Along the surface", "Opposite to the applied moment"], "A frictionless contact cannot supply a tangential reaction. The local surface normal sets the direction.", "beam"),
        ("zero_member", "statics", "Spot a zero-force joint", "An unloaded ideal truss joint connects exactly two non-collinear members and has no support reaction. What are their axial forces?", "Both are zero", ["Equal tension of unknown magnitude", "Equal compression of unknown magnitude", "One is tension and one compression"], "With no external load, the two non-collinear force vectors can balance only if both magnitudes are zero.", "truss"),
        ("couple_invariant", "statics", "A couple's moment depends on…", "A pure couple acts on a rigid body. How does its moment change when the reference point moves?", "It stays the same", ["It becomes zero at the centroid", "It doubles at a support", "It changes with the reference point's distance"], "A couple has zero resultant force and the same resultant moment about every point.", "beam"),
        ("principal_planes", "design", "What happens on a principal plane?", "Which statement describes traction on a principal plane of stress?", "Shear stress is zero", ["Normal stress is always zero", "Normal stress must be tensile", "Shear stress is necessarily largest"], "Principal directions diagonalize the symmetric stress tensor; shear components vanish on those planes.", "stress"),
        ("plane_third", "design", "Plane stress still has a third principal stress", "The two in-plane principal stresses are 60 MPa and 20 MPa in plane stress. What is the third principal stress?", "0 MPa", ["20 MPa", "40 MPa", "60 MPa"], "The out-of-plane stress is zero in plane stress. Include zero when ordering all three principal stresses.", "stress"),
        ("inertia_units", "design", "Two different kinds of inertia", "Which are the units of the second moment of area used in the elastic beam-bending equation?", "m⁴", ["kg·m²", "m²", "N·m"], "Area moment of inertia is an integral of distance squared over area. It differs from mass moment of inertia.", "beam"),
        ("bending_neutral", "design", "At the neutral axis", "In simple linear elastic bending of a homogeneous beam with no axial load, what is the bending normal stress at the neutral axis?", "Zero", ["The tensile maximum", "The compressive maximum", "Equal to the shear stress everywhere"], "The flexure formula is proportional to signed distance from the neutral axis. At zero distance the bending normal stress vanishes.", "beam"),
        ("damping_kind", "dynamics", "Which system oscillates as it decays?", "A linear free-response mass–spring–damper system has damping ratio 0.3. How is it classified?", "Underdamped", ["Critically damped", "Overdamped", "Undamped"], "A damping ratio strictly between zero and one produces a decaying oscillatory free response.", "spring"),
        ("stable_pole", "dynamics", "Read a simple continuous-time pole", "A first-order continuous-time system has its only pole at s = −4 s⁻¹. With zero input, what does its natural response do?", "Decays exponentially", ["Grows exponentially", "Oscillates with constant amplitude", "Stays constant for every initial condition"], "A negative real pole produces an exponential decay term. Its time constant is the reciprocal of the pole's magnitude.", "spring"),
        ("transfer_initial", "dynamics", "A transfer function's initial-condition assumption", "When defining the transfer function as the Laplace-domain output divided by input, what initial conditions are assumed?", "Zero initial conditions", ["Arbitrary nonzero initial conditions", "A unit initial displacement only", "Infinite initial velocity"], "The transfer function describes the zero-state input–output relation. Initial-condition response is treated separately.", "circuit"),
        ("series_springs", "dynamics", "Two equal springs in series", "Two identical massless linear springs, each of stiffness k, are connected in series. What is their equivalent stiffness?", "k/2", ["2k", "k", "4k"], "Series springs carry equal force while their deflections add. Their stiffness reciprocals add.", "series_springs"),
    ]
    for key, course, title, body, answer, wrong, explanation, diagram in concepts:
        add(key, course, title, body, answer, wrong,
            explanation + "\nCheck the assumptions before applying the rule to a different system.", diagram)
    explainers = [
        ("flow_tradeoff", "fluids", "A wider pipe changes more than one thing", "At a fixed incompressible flow rate, $V=Q/A$. Doubling circular-pipe diameter multiplies area by four and divides mean speed by four.\n\nThe words **fixed flow rate** matter. If speed were fixed instead, the wider pipe would carry four times the flow.", "pipe"),
        ("regime_first", "fluids", "Before picking a friction factor, find the regime", "$Re=\\rho VD/\\mu$ compares inertial and viscous effects. For fully developed laminar circular-pipe flow, the **Darcy** friction factor is $64/Re$.\n\nDo not carry that formula into turbulent flow. In the fully rough turbulent limit, relative roughness controls the friction factor.", "pipe"),
        ("friction_convention", "fluids", "Darcy or Fanning? The factor-of-four trap", "The Darcy friction factor is **four times** the Fanning friction factor. Darcy–Weisbach head loss uses $h_L=f_D(L/D)V^2/(2g)$.\n\nBefore reading a chart or copying a number, check which convention the source uses. A dimensionless factor can still be the wrong factor.", "pipe"),
        ("network_bookkeeping", "fluids", "Series and parallel need different bookkeeping", "In series pipes without leaks, flow rate stays equal and head losses add. In parallel branches connecting the same two junctions, total head drops are equal and branch flow rates add.\n\nEqual head drop does **not** imply equal branch flow. Geometry and resistance determine the split.", "pipe"),
        ("signs_first", "thermo", "Pick the energy sign convention before the equation", "For a closed system with negligible kinetic and potential changes, $\\Delta U=Q-W$ when heat **into** the system and work **done by** the system are positive.\n\nA paddle wheel doing work on the system has negative $W$. Insulation removes heat transfer, not shaft work.", "tank"),
        ("enthalpy_flow", "thermo", "Why turbines use enthalpy", "Fluid crossing a control surface carries internal energy and performs flow work. Combining those terms gives specific enthalpy, $h=u+pv$.\n\nFor a steady adiabatic turbine with negligible speed and elevation changes, $w_{out}=h_{in}-h_{out}$. Check the control-volume assumptions before using the shortcut.", "turbine"),
        ("entropy_direction", "thermo", "Energy conservation does not tell the whole story", "The first law balances energy. The entropy balance also accounts for irreversibility: entropy generation is nonnegative.\n\nAn adiabatic process can generate entropy through friction or mixing. **Adiabatic** and **isentropic** are equivalent only with the additional reversible idealization and suitable system assumptions.", "tank"),
        ("absolute_scale", "thermo", "Carnot ratios need an absolute temperature scale", "The heat-engine ceiling is $\\eta_{max}=1-T_C/T_H$. Use kelvin, because the ratio requires absolute temperatures.\n\nA temperature **difference** of one degree Celsius equals one kelvin. A temperature **ratio** formed from Celsius readings does not preserve the correct physical ratio.", "cycle"),
        ("fbd_habit", "statics", "The most useful statics step happens before algebra", "Isolate one body and replace each support with the reactions it can actually supply. A planar pin has two force components; a frictionless roller has one normal force; a fixed support can also supply a couple.\n\nAn equilibrium equation cannot repair a force missing from the free-body diagram.", "beam"),
        ("moment_shortcut", "statics", "Use a moment center that removes unknowns", "A force whose line of action passes through the moment center contributes zero moment there. Choosing a support as the moment center can eliminate its unknown reaction components.\n\nFor the remaining forces, use perpendicular lever arms and state a consistent clockwise or counterclockwise sign convention.", "beam_eccentric"),
        ("load_resultants", "statics", "A load diagram is also an area calculation", "The equivalent force of a distributed load is the area under its intensity diagram. Its line of action passes through that area's centroid.\n\nA uniform load acts at the midpoint. A triangular load acts one-third of the loaded length from the **larger-intensity end**. This preserves external force and moment, not every internal diagram.", "beam_triangular"),
        ("sections_shortcut", "statics", "A good truss cut saves a lot of joints", "The method of sections exposes selected member forces by cutting the truss and balancing one side. For a planar rigid-body free body, there are three independent equilibrium equations.\n\nA cut through at most three unknown member forces is usually useful. Take moments about an intersection that eliminates two of them when possible.", "truss"),
        ("flexure_units", "design", "The flexure formula is a unit check waiting to happen", "Elastic bending stress has magnitude $Mc/I$. If $c$ is in millimetres and $I$ in mm⁴, use moment in N·mm. The resulting N/mm² is MPa.\n\nThe second moment of **area** is not a mass moment of inertia. Their units and physical roles differ.", "rectangle"),
        ("three_principals", "design", "Remember the third principal stress", "Plane stress still has three principal stresses. One is zero in the out-of-plane direction. Order **all three** before calculating absolute maximum shear.\n\nThe governing circle spans the smallest to largest principal stress: $\\tau_{max,abs}=(\\sigma_1-\\sigma_3)/2$. The in-plane circle need not be the largest.", "mohr"),
        ("local_vs_nominal", "design", "Nominal stress is not always the local peak", "A shoulder, hole, or fillet can concentrate elastic stress. A theoretical factor $K_t$ scales the nominal normal stress defined for the chart's reference section.\n\nCheck geometry ratios and the reference section before multiplying. A factor derived for torsion is not interchangeable with one for normal stress.", "shaft"),
        ("shaft_diameter", "design", "Diameter is powerful in torsion", "For a solid circular shaft in elastic torsion, $\\tau_{max}=16T/(\\pi d^3)$. With torque fixed, doubling diameter reduces peak shear stress by eight.\n\nThe polar second moment itself scales with $d^4$, but the outer-fiber radius in $Tc/J$ contributes one factor of $d$ back.", "shaft"),
        ("spring_or_damper", "dynamics", "Springs notice position. Dampers notice velocity.", "A linear spring resists relative displacement: $F_s=-kx$. A linear viscous damper resists relative velocity: $F_d=-c\\dot{x}$.\n\nFor a translating mass connected to fixed ground, these combine into $m\\ddot{x}+c\\dot{x}+kx=F(t)$. Define the positive direction before assigning signs.", "spring"),
        ("hertz_vs_radians", "dynamics", "Hertz and radians per second are not interchangeable", "For an undamped single-degree-of-freedom system, $\\omega_n=\\sqrt{k/m}$ is in rad/s. Ordinary frequency is $f_n=\\omega_n/(2\\pi)$ in hertz.\n\nPeriod is $T=1/f_n=2\\pi/\\omega_n$. Keep that factor of $2\\pi$ when moving between frequency conventions.", "spring"),
        ("pole_time", "dynamics", "A real pole tells you the decay time", "A stable first-order pole at $s=-a$ produces an exponential natural-response term $e^{-at}$, with time constant $\\tau=1/a$.\n\nFor an RC circuit, $\\tau=RC$. At one time constant, a decaying initial response has about 37% of its original magnitude remaining.", "circuit"),
        ("zero_state", "dynamics", "A transfer function describes the zero-state response", "For a linear time-invariant system, the transfer function $G(s)=Y(s)/U(s)$ assumes zero initial conditions.\n\nA nonzero initial displacement or velocity creates an additional natural response. Keep that initial-condition contribution separate when solving a complete response problem.", "spring"),
    ]
    for key, course, title, body, diagram in explainers:
        cards.append({"id": "study_note_" + key, "created_at": STAMP, "category": "DEEP_CUT",
                      "course_tag": COURSES[course], "title": title, "body_markdown": body,
                      "solution_markdown": None, "source_url": None, "parent_card_id": None,
                      "comments": [], "diagram": diagram, "topic": title})
    return cards


def main():
    from .run_pipeline import FEED_PATH, _load_feed, atomic_write, merge_feed
    feed = _load_feed(FEED_PATH)
    cards = build_bank()
    merged = merge_feed(feed, new_cards=cards, replies=[], issues=[], calendar=feed)
    atomic_write(FEED_PATH, merged)
    print(f"Merged {len(cards)} illustrated review posts into {len(merged['cards'])} posts.")


if __name__ == "__main__":
    main()
