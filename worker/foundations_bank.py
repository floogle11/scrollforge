"""Original calculated Calc I–III, linear algebra, ODE and physics practice.

Eight or four concepts per subject, each with four numerical variants. No
private course documents or external figures are needed to regenerate these.
"""
import math

COURSES = {"calc1": "CALC-I", "calc2": "CALC-II", "calc3": "CALC-III",
           "linear": "LINEAR-ALG", "ode": "DIFF-EQ", "physics1": "PHYS-I", "physics2": "PHYS-II"}


def extend_bank(add, numeric):
    for v in range(4):
        a, b, n = v + 2, v + 1, v + 3

        # Calculus I: limits, derivatives, accumulation, and optimization.
        numeric(f"calc1_limit_{v}", "calc1", "A removable discontinuity",
                f"Find $\\lim_{{x\\to {a}}}(x^2-{a*a})/(x-{a})$.",
                2*a, "", f"Factor $x^2-{a*a}=(x-{a})(x+{a})$. Cancel away from $x={a}$, then take the limit.", "limit", [f"Approach x = {a}"])
        numeric(f"calc1_power_{v}", "calc1", "Slope from the power rule",
                f"For $f(x)=x^{n}$, find $f'(2)$.", n*2**(n-1), "",
                f"The power rule gives $f'(x)={n}x^{{{n-1}}}$. Substitute $x=2$.", "tangent", [f"f(x) = x^{n}", "Evaluate at x = 2"])
        numeric(f"calc1_chain_{v}", "calc1", "Remember the inner derivative",
                f"For $f(x)=({a}x+1)^3$, find $f'(0)$.", 3*a, "",
                f"Chain rule: $f'(x)={3*a}({a}x+1)^2$. At zero the squared factor is one.", "tangent", ["Chain rule", "Evaluate at x = 0"])
        numeric(f"calc1_product_{v}", "calc1", "Two changing factors",
                f"For $f(x)=x^2 e^{{{a}x}}$, find $f'(1)$.", (2+a)*math.exp(a), "",
                f"Product and chain rules give $f'(x)=e^{{{a}x}}(2x+{a}x^2)$. Evaluate at one.", "tangent", ["Product rule and chain rule"])
        numeric(f"calc1_integral_{v}", "calc1", "Accumulation under a parabola",
                f"Evaluate $\\int_0^{a} x^2\\,dx$.", a**3/3, "",
                f"An antiderivative is $x^3/3$. Evaluate at {a} and subtract the value at zero.", "area", [f"Bounds: 0 to {a}", "Integrand: x²"])
        numeric(f"calc1_ftc_{v}", "calc1", "The upper limit moves too",
                f"Let $F(x)=\\int_0^{{x^2}}(t+{a})\\,dt$. Find $F'(1)$.", 2*(1+a), "",
                f"FTC plus chain rule gives $F'(x)=(x^2+{a})(2x)$. Evaluate at one.", "integral", ["Moving upper limit: x²"])
        numeric(f"calc1_optimize_{v}", "calc1", "A fixed perimeter, the largest area",
                f"A rectangle has perimeter {8*a} m. What width maximizes its area?",
                2*a, "m", f"Write $A(w)=w({4*a}-w)$. Its derivative is ${4*a}-2w$, and $A''=-2<0$.", "rectangle", [f"Perimeter = {8*a} m"])
        numeric(f"calc1_related_{v}", "calc1", "An expanding circle",
                f"A circle's radius is {a} m and grows at {b} m/s. Find its instantaneous area growth rate.",
                2*math.pi*a*b, "m²/s", "$A=\\pi r^2$ implies $dA/dt=2\\pi r\\,dr/dt$. Insert the instantaneous radius and radial rate.", "circle", [f"r = {a} m", f"dr/dt = {b} m/s"])

        # Calculus II: integration techniques, improper integrals and series.
        numeric(f"calc2_substitution_{v}", "calc2", "Spot the substitution",
                f"Evaluate $\\int_0^1 {2*a}x e^{{{a}x^2}}\\,dx$.", math.exp(a)-1, "",
                f"Set $u={a}x^2$, so $du={2*a}x\\,dx$. The new bounds are zero and {a}, giving $e^{a}-1$.", "integral", ["Use u = a x²"])
        numeric(f"calc2_parts_{v}", "calc2", "One integration by parts",
                f"Evaluate $\\int_0^{a} x e^x\\,dx$.", (a-1)*math.exp(a)+1, "",
                "Choose $u=x$, $dv=e^x dx$. An antiderivative is $(x-1)e^x$; subtract its lower-bound value of -1.", "integral", ["Integration by parts"])
        numeric(f"calc2_improper_{v}", "calc2", "Does the tail converge?",
                f"Evaluate $\\int_1^\\infty x^{{-{n}}}\\,dx$.", 1/(n-1), "",
                f"Since {n}>1, the p-integral converges. The antiderivative $x^{{1-{n}}}/(1-{n})$ vanishes at infinity.", "integral", [f"p = {n} > 1"])
        numeric(f"calc2_geometric_{v}", "calc2", "An infinite geometric sum",
                f"Find $\\sum_{{k=0}}^\\infty ({1}/{a})^k$.", 1/(1-1/a), "",
                f"The common ratio is $r=1/{a}$ with $|r|<1$. Starting at k=0 gives $1/(1-r)$.", "series", [f"Ratio r = 1/{a}", "First term = 1"])
        numeric(f"calc2_taylor_{v}", "calc2", "A local exponential approximation",
                f"Use the degree-two Maclaurin polynomial of $e^x$ to approximate $e^{{{b/10:g}}}$.",
                1+b/10+(b/10)**2/2, "", "$P_2(x)=1+x+x^2/2$. Substitute the requested x; this is an approximation, not the exact exponential.", "series", ["Degree 2", f"x = {b/10:g}"])
        numeric(f"calc2_disk_{v}", "calc2", "Rotate a region into a solid",
                f"Rotate the region below $y=x$ and above the x-axis, from $x=0$ to $x={a}$, about the x-axis. Find the volume.",
                math.pi*a**3/3, "units³", f"Disks have radius x. Thus $V=\\pi\\int_0^{a}x^2 dx=\\pi({a}^3)/3$.", "revolution", ["Axis of rotation: x", f"Bounds: 0 to {a}"])
        numeric(f"calc2_polar_{v}", "calc2", "Area in polar coordinates",
                f"Find the area inside the polar curve $r={a}$ for $0\\leq\\theta\\leq\\pi/2$.",
                math.pi*a*a/4, "units²", f"Use $A=\\tfrac12\\int r^2 d\\theta$. A quarter circle gives $A=\\pi {a}^2/4$.", "polar", [f"Radius = {a}", "First quadrant"])
        numeric(f"calc2_partial_{v}", "calc2", "Split a rational integrand",
                f"Evaluate $\\int_1^{a} [1/(x(x+1))]\\,dx$.", math.log(2*a/(a+1)), "",
                "$1/[x(x+1)]=1/x-1/(x+1)$. Evaluate $\\ln x-\\ln(x+1)$ at both positive bounds.", "integral", ["Partial fractions", f"Bounds: 1 to {a}"])

        # Calculus III: multivariable derivatives, integration and vector calculus.
        numeric(f"calc3_partial_{v}", "calc3", "Hold the other variable fixed",
                f"For $f(x,y)=x^2y+{a}y^2$, find $f_x(2,{b})$.", 4*b, "",
                f"Treat y as constant: $f_x=2xy$. At $(2,{b})$ this becomes $4({b})$.", "axes3d", ["Partial derivative with respect to x"])
        numeric(f"calc3_gradient_{v}", "calc3", "How steep is the fastest ascent?",
                f"For $f(x,y)=x^2+y^2$, find $|\\nabla f({a},{b})|$.", 2*math.hypot(a,b), "",
                f"$\\nabla f=(2x,2y)$. Its magnitude at the point is $2\\sqrt{{{a}^2+{b}^2}}$.", "axes3d", [f"Point: ({a}, {b})"])
        numeric(f"calc3_direction_{v}", "calc3", "Direction must be a unit vector",
                f"For $f(x,y)=x^2+y^2$, find the directional derivative at $({a},{b})$ along the unit vector $(3/5,4/5)$.",
                (6*a+8*b)/5, "", "$D_{u}f=\\nabla f\\cdot u$. Dot $(2x,2y)$ with the supplied unit vector.", "axes3d", ["Direction u = (3/5, 4/5)"])
        numeric(f"calc3_double_{v}", "calc3", "Integrate over a rectangle",
                f"Evaluate $\\int_0^{a}\\int_0^{b}(x+y)\\,dy\\,dx$.", b*a*a/2+a*b*b/2, "",
                f"The inner integral is ${b}x+{b}^2/2$. Integrate this in x from zero to {a}.", "rectangle", [f"0 ≤ x ≤ {a}", f"0 ≤ y ≤ {b}"])
        numeric(f"calc3_triple_{v}", "calc3", "A constant density in a box",
                f"A box has $0\\leq x\\leq {a}$, $0\\leq y\\leq {b}$, $0\\leq z\\leq 2$ m and uniform density 3 kg/m³. Find its mass.",
                6*a*b, "kg", f"$m=\\iiint\\rho dV$. Constant density times volume is $3({a})({b})(2)$.", "axes3d", ["Uniform density = 3 kg/m³"])
        numeric(f"calc3_divergence_{v}", "calc3", "A local measure of outward flow",
                f"For $\\mathbf F=({a}x,{b}y,2z)$, find $\\nabla\\cdot\\mathbf F$.", a+b+2, "",
                f"Add the matching component derivatives: $\\partial F_x/\\partial x+\\partial F_y/\\partial y+\\partial F_z/\\partial z={a}+{b}+2$.", "axes3d", ["Divergence: sum of component derivatives"])
        numeric(f"calc3_curl_{v}", "calc3", "A rotational vector field",
                f"For $\\mathbf F=(-{a}y,{a}x,0)$, find the z component of $\\nabla\\times\\mathbf F$.",
                2*a, "", f"The z component is $\\partial F_y/\\partial x-\\partial F_x/\\partial y={a}-(-{a})$.", "axes3d", ["Curl about the z-axis"])
        numeric(f"calc3_line_{v}", "calc3", "A conservative field saves an integral",
                f"Find $\\int_C\\nabla(x^2+y^2)\\cdot d\\mathbf r$ from $(0,0)$ to $({a},{b})$ along any smooth path.",
                a*a+b*b, "", f"The gradient field has potential $f=x^2+y^2$. The integral is $f({a},{b})-f(0,0)$.", "axes3d", ["Gradient field", "Only endpoints matter"])

        # Linear algebra: operations with independent reference calculations.
        numeric(f"linear_det_{v}", "linear", "A two-by-two determinant",
                f"Find the determinant of $\\begin{{pmatrix}}{a}&1\\\\2&{a+1}\\end{{pmatrix}}$.",
                a*(a+1)-2, "", f"For a 2×2 matrix, determinant is $ad-bc={a}({a+1})-1(2)$.", "matrix", ["2 × 2 determinant"])
        numeric(f"linear_system_{v}", "linear", "Solve two simultaneous equations",
                f"Solve $x+y={a+b}$ and $x-y={a-b}$. What is x?", a, "",
                f"Add the equations to eliminate y: $2x={2*a}$. Divide by two.", "matrix", ["Eliminate y by addition"])
        numeric(f"linear_eigen_{v}", "linear", "Read an eigenvalue from a triangular matrix",
                f"The matrix is $A=\\begin{{pmatrix}}{a}&1\\\\0&{a+2}\\end{{pmatrix}}$. What is its larger eigenvalue?",
                a+2, "", f"A triangular matrix's eigenvalues are its diagonal entries, {a} and {a+2}.", "matrix", ["Upper triangular matrix"])
        numeric(f"linear_projection_{v}", "linear", "The size of a vector projection",
                f"Find the magnitude of the orthogonal projection of $({a},{b})$ onto the x-axis.", a, "",
                f"The unit axis vector is $(1,0)$. The projection is $({a},0)$, with magnitude {a}.", "axes2d", ["Projection onto x-axis"])

        # Differential equations: decay, IVPs, equilibria and characteristic roots.
        numeric(f"ode_decay_{v}", "ode", "Solve a first-order decay IVP",
                f"Solve $y'=-{a}y$, $y(0)={10*b}$. What is $y(1)$?", 10*b*math.exp(-a), "",
                f"Separate variables to get $y=Ce^{{-{a}t}}$. The initial value sets $C={10*b}$; evaluate at t=1.", "decay", [f"Decay rate = {a}", f"y(0) = {10*b}"])
        numeric(f"ode_forcing_{v}", "ode", "A constant forcing reaches equilibrium",
                f"For $y'+{a}y={a*3*b}$, what is the equilibrium value of y?", 3*b, "",
                f"At equilibrium $y'=0$. Solve ${a}y={a*3*b}$. The positive coefficient also makes this equilibrium stable.", "decay", ["Set the derivative to zero"])
        numeric(f"ode_ivp_{v}", "ode", "Integrate a simple initial-value problem",
                f"Given $y'={2*a}t$ and $y(0)={b}$, find $y(2)$.", 4*a+b, "",
                f"Integrate to $y={a}t^2+C$. The initial value gives $C={b}$, then substitute t=2.", "integral", [f"y(0) = {b}"])
        numeric(f"ode_roots_{v}", "ode", "Find the faster exponential decay",
                f"The ODE is $y''+{2*a+1}y'+{a*(a+1)}y=0$. What is the magnitude of its more negative characteristic root?",
                a+1, "", f"The characteristic polynomial factors as $(r+{a})(r+{a+1})$. Roots are -{a} and -{a+1}.", "decay", ["Constant-coefficient second-order ODE"])

        # Physics I: mechanics, rotation, oscillation and waves.
        numeric(f"physics1_velocity_{v}", "physics1", "Constant acceleration changes velocity",
                f"A cart starts at {b} m/s and accelerates at {a} m/s² for 3 s. Find its final velocity.",
                b+3*a, "m/s", "$v=v_0+at$ for constant acceleration. All supplied directions are positive.", "motion", [f"a = {a} m/s²", "t = 3 s"])
        numeric(f"physics1_projectile_{v}", "physics1", "Time to the top of the arc",
                f"A projectile launches with upward velocity {9.81*b:g} m/s. Neglect air resistance and take g=9.81 m/s². Find time to maximum height.",
                b, "s", "At maximum height the vertical velocity is zero. From $v_y=v_{0y}-gt$, $t=v_{0y}/g$.", "projectile", ["No air resistance", "g = 9.81 m/s²"])
        numeric(f"physics1_newton_{v}", "physics1", "Net force controls acceleration",
                f"A {a} kg cart has a {6*a} N force right and a {2*a} N force left. Find acceleration to the right.",
                4, "m/s²", f"Net force is ${6*a}-{2*a}={4*a}$ N. Divide by the {a} kg mass using Newton's second law.", "forces", [f"Right force = {6*a} N", f"Left force = {2*a} N"])
        numeric(f"physics1_energy_{v}", "physics1", "A drop converts potential energy",
                f"A mass falls from rest through {a} m. Neglect drag and use g=9.81 m/s². Find speed after the drop.",
                math.sqrt(2*9.81*a), "m/s", "$mgh=mv^2/2$, so $v=\\sqrt{2gh}$. Mass cancels.", "falling", [f"Drop = {a} m", "Initial speed = 0"])
        numeric(f"physics1_momentum_{v}", "physics1", "Two carts stick together",
                f"A {a} kg cart moving at 6 m/s strikes an identical stationary cart and sticks to it. With negligible external impulse, find their shared speed.",
                3, "m/s", f"Momentum conservation gives $({a})(6)=(2\\times {a})v$. Kinetic energy is not conserved in this collision.", "motion", ["Equal masses", "Perfectly inelastic collision"])
        numeric(f"physics1_rotation_{v}", "physics1", "Rotational kinetic energy",
                f"A rotor has fixed-axis inertia {a} kg·m² and angular speed {b+2} rad/s. Find its rotational kinetic energy.",
                a*(b+2)**2/2, "J", "$K_{rot}=I\\omega^2/2$. Angular speed must be in radians per second.", "shaft", [f"I = {a} kg·m²", f"ω = {b+2} rad/s"])
        numeric(f"physics1_spring_{v}", "physics1", "A spring sets the oscillation period",
                f"An ideal mass-spring system has mass {a} kg and stiffness {100*a} N/m. Find its period.",
                2*math.pi/10, "s", "$T=2\\pi\\sqrt{m/k}$. Here $k/m=100$ s⁻², so angular frequency is 10 rad/s.", "spring", [f"m = {a} kg", f"k = {100*a} N/m"])
        numeric(f"physics1_wave_{v}", "physics1", "Frequency times wavelength",
                f"A traveling wave has frequency {5*a} Hz and wavelength {b} m. Find wave speed.",
                5*a*b, "m/s", "$v=f\\lambda$. Frequency counts cycles per second; wavelength is length per cycle.", "wave", [f"f = {5*a} Hz", f"λ = {b} m"])

        # Physics II: electric fields, circuits, magnetism, induction and optics.
        numeric(f"physics2_coulomb_{v}", "physics2", "Force between two point charges",
                f"Two positive point charges of {a} µC each are separated by {b} m in vacuum. Using k=8.988×10⁹ N·m²/C², find force magnitude.",
                8.988e9*(a*1e-6)**2/b**2, "N", "$F=k|q_1q_2|/r^2$. Convert each microcoulomb to 10⁻⁶ C. Like charges repel.", "charges", [f"q₁ = q₂ = {a} µC", f"Separation = {b} m"])
        numeric(f"physics2_field_{v}", "physics2", "Force from a uniform electric field",
                f"A positive {a} µC charge is in a uniform 2000 N/C electric field. Find electric force magnitude.",
                a*1e-6*2000, "N", "$|F|=|q|E$. A positive charge accelerates along the field.", "field", ["Uniform E = 2000 N/C"])
        numeric(f"physics2_potential_{v}", "physics2", "Potential energy per charge",
                f"A {a} C positive charge moves through a potential increase of {b} V. Find its change in electric potential energy.",
                a*b, "J", "$\\Delta U=q\\Delta V$. A positive charge gains potential energy when potential increases.", "field", [f"q = {a} C", f"ΔV = +{b} V"])
        numeric(f"physics2_ohm_{v}", "physics2", "Current through one resistor",
                f"An ideal {6*a} V battery drives one {3*b} Ω resistor. Neglect wire resistance. Find current.",
                2*a/b, "A", "$I=V/R$ by Ohm's law. The full battery voltage appears across the only resistor.", "resistor", [f"V = {6*a} V", f"R = {3*b} Ω"])
        numeric(f"physics2_capacitor_{v}", "physics2", "Energy stored in a capacitor",
                f"A {a} µF capacitor has {10*b} V across it. Find stored energy in millijoules.",
                .5*a*1e-6*(10*b)**2*1000, "mJ", "$U=CV^2/2$. Convert µF to F, then joules to millijoules.", "capacitor", [f"C = {a} µF", f"V = {10*b} V"])
        numeric(f"physics2_magnetic_{v}", "physics2", "Magnetic force at a right angle",
                f"A straight {b} m wire carries {a} A perpendicular to a uniform 0.4 T magnetic field. Find magnetic force magnitude.",
                .4*a*b, "N", "$F=ILB\\sin\\theta$. Perpendicular means $\\theta=90°$ and the sine is one.", "magnetic", ["B is into the page", "Current is to the right"])
        numeric(f"physics2_faraday_{v}", "physics2", "Changing flux creates an emf",
                f"Flux per turn through a {10*a}-turn coil changes uniformly from zero to {b/100:g} Wb in 0.5 s. Find induced emf magnitude.",
                10*a*(b/100)/.5, "V", "$|\\mathcal E|=N|\\Delta\\Phi/\\Delta t|$. Flux is per turn, so multiply by the turn count.", "magnetic", [f"N = {10*a}", "Uniform flux change"])
        numeric(f"physics2_lens_{v}", "physics2", "An image from the thin-lens equation",
                f"A converging thin lens has focal length {5*a} cm. A real object is {15*a} cm from the lens. Find the positive image distance.",
                7.5*a, "cm", "$1/f=1/d_o+1/d_i$, so $d_i=fd_o/(d_o-f)$. Both object and real image distances are positive here.", "lens", [f"f = {5*a} cm", f"Object distance = {15*a} cm"])
