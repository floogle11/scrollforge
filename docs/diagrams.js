/* Audited problem figures. Unknown/legacy diagram names intentionally render nothing. */
(() => {
  'use strict';
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const path = (d, extra='') => `<path d="${d}" ${extra}/>`;
  const line = (x1,y1,x2,y2,extra='') => path(`M${x1} ${y1}L${x2} ${y2}`,extra);
  const label = (x,y,text,anchor='middle') => `<text x="${x}" y="${y}" text-anchor="${anchor}">${esc(text)}</text>`;
  const rect = (x,y,w,h) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3"/>`;
  const circle = (x,y,r,extra='') => `<circle cx="${x}" cy="${y}" r="${r}" ${extra}/>`;
  function arrow(x1,y1,x2,y2,color='#8bbfff') {
    const angle = Math.atan2(y2-y1,x2-x1), wing = a => `${x2-9*Math.cos(a)} ${y2-9*Math.sin(a)}`;
    return path(`M${x1} ${y1}L${x2} ${y2}M${wing(angle-.5)}L${x2} ${y2}L${wing(angle+.5)}`, `stroke="${color}"`);
  }
  const dimension = (x1,x2,y,text) => line(x1,y,x2,y)+line(x1,y-5,x1,y+5)+line(x2,y-5,x2,y+5)+label((x1+x2)/2,y+21,text);
  const spring = (x,y,length=130) => path(`M${x} ${y}h15l10-12 15 24 15-24 15 24 15-24 15 24 10-12h${length-110}`);
  const damper = (x,y) => path(`M${x} ${y}h45m0-14v28h45v-28m-20 2v24m0-12h65`);
  const wall = () => line(80,45,80,170)+[50,75,100,125,150].map(y=>line(68,y+12,80,y)).join('');
  const pin = (x,y) => path(`M${x} ${y}l-13 22h26Z`)+line(x-20,y+25,x+20,y+25);
  const roller = (x,y) => path(`M${x} ${y}l-13 18h26Z`)+circle(x-7,y+23,4)+circle(x+7,y+23,4)+line(x-20,y+30,x+20,y+30);
  const beam = () => line(70,120,410,120,'stroke-width="6"')+pin(80,124)+roller(400,124)+label(60,159,'A')+label(426,159,'B');
  const mass = () => rect(250,65,95,95)+label(297,119,'m');
  const reservoir = (fridge) => rect(145,20,190,33)+label(240,43,'Hot reservoir')+rect(145,180,190,33)+label(240,203,'Cold reservoir')+circle(240,115,30)+
    (fridge ? arrow(240,85,240,55)+arrow(240,178,240,147)+arrow(400,115,272,115)+label(361,99,'W in') : arrow(240,55,240,83)+arrow(240,147,240,178)+arrow(272,115,400,115)+label(361,99,'W out'))+
    label(211,75,'QH')+label(211,167,'QL');

  const drawings = {
    pipe: ['Flow through a uniform circular pipe', line(55,70,425,70)+line(55,160,425,160)+arrow(105,115,280,115)+label(193,100,'Flow')+arrow(370,115,370,73)+arrow(370,115,370,157)+label(393,121,'D')],
    pump: ['Flow enters and leaves the pump', line(40,95,196,95)+line(40,135,196,135)+line(284,95,440,95)+line(284,135,440,135)+circle(240,115,48)+arrow(85,115,175,115)+arrow(308,115,405,115)+label(240,121,'Pump')+label(100,168,'Inlet')+label(380,168,'Outlet')],
    open_tank: ['Depth is measured below the open free surface', path('M115 45v145h250V45')+line(115,75,365,75,'stroke="#8bbfff"')+label(240,48,'Atmosphere')+circle(215,155,4)+arrow(310,75,310,155)+label(328,121,'h')+label(210,179,'Pressure point')],
    sealed_tank: ['Closed rigid tank; no mass crosses the wall', rect(120,50,240,130)+label(240,110,'Fixed volume')+label(240,145,'Closed system')],
    energy_balance: ['Heat enters and work leaves the closed system', rect(170,55,140,125)+label(240,121,'System')+arrow(40,115,167,115)+arrow(313,115,440,115)+label(100,94,'Q in')+label(380,94,'W out')],
    cycle: ['Heat engine: heat flows from hot to cold, with work output', reservoir(false)],
    fridge: ['Refrigerator or heat pump: work moves heat from cold to hot', reservoir(true)],
    turbine: ['Adiabatic turbine with flow and shaft work output', path('M195 65v100l95 30V35Z')+arrow(45,95,190,95)+arrow(295,165,430,165)+arrow(245,115,425,115)+label(105,73,'Inlet')+label(365,195,'Outlet')+label(375,95,'Work out')],
    lever: ['Force perpendicular to the lever arm about the pivot', line(100,145,380,145,'stroke-width="6"')+circle(100,145,7)+arrow(350,45,350,141)+label(370,75,'F')+dimension(100,350,185,'Perpendicular distance')+label(95,124,'Pivot')],
    beam: ['Centered load on a pin and roller supported beam', beam()+arrow(240,40,240,115)+label(260,64,'P')+dimension(80,240,188,'L/2')+dimension(240,400,188,'L/2')],
    beam_eccentric: ['Off-center load: a is measured from the left support', beam()+arrow(80+320/3,40,80+320/3,115)+label(205,61,'P')+dimension(80,80+320/3,190,'a')+dimension(80+320/3,400,190,'L − a')],
    beam_udl: ['Equal downward load intensity over the loaded length', line(70,145,410,145,'stroke-width="6"')+line(80,65,400,65)+[80,144,208,272,336,400].map(x=>arrow(x,65,x,139)).join('')+label(240,44,'Uniform intensity w')+dimension(80,400,185,'Loaded length L')],
    beam_triangular: ['Load rises from zero on the left to its peak on the right', line(70,155,410,155,'stroke-width="6"')+line(80,149,400,45)+[144,208,272,336,400].map(x=>arrow(x,149-(x-80)*104/320,x,149)).join('')+label(398,32,'w max')+label(76,138,'0')+dimension(80,400,190,'Loaded length L')],
    vectors: ['Positive horizontal and vertical components form a right triangle', arrow(170,195,290,195)+arrow(170,195,170,35)+arrow(170,195,290,35,'#e9c88e')+path('M170 35h120v160','stroke-dasharray="5 5"')+label(235,222,'Fx')+label(143,119,'Fy')+label(279,100,'F')],
    member: ['Axial tension acts outward on both ends of the bar', rect(150,90,180,50)+arrow(150,115,55,115)+arrow(330,115,425,115)+label(100,93,'F')+label(380,93,'F')+label(240,172,'Cross-sectional area A')],
    stress: ['Plane stress: tensile σx, zero σy, and complementary positive shear', rect(185,65,110,110)+arrow(180,120,105,120)+arrow(300,120,375,120)+label(100,98,'σx')+label(380,98,'σx')+arrow(195,50,285,50,'#e9c88e')+arrow(310,165,310,75,'#e9c88e')+arrow(285,190,195,190,'#e9c88e')+arrow(170,75,170,165,'#e9c88e')+label(240,32,'τxy')+label(240,222,'σy = 0')],
    shaft: ['Torque about the axis of a circular shaft', path('M120 75h220a20 40 0 0 1 0 80H120')+'<ellipse cx="120" cy="115" rx="20" ry="40"/>'+line(80,115,395,115,'stroke-dasharray="6 6"')+path('M390 55Q450 115 390 175l3-16m-3 16 16-3','stroke="#e9c88e"')+label(416,47,'T')],
    rectangle: ['Width b and vertical height h; horizontal axis through the centroid', rect(180,45,120,130)+line(125,110,360,110,'stroke-dasharray="6 5"')+label(377,116,'x')+dimension(180,300,195,'b')+line(325,45,325,175)+line(320,45,330,45)+line(320,175,330,175)+label(343,90,'h')],
    spring_undamped: ['Ideal mass and spring; no damper', wall()+spring(80,110,170)+mass()+label(166,80,'k')+arrow(355,185,425,185)+label(390,213,'+x')],
    spring: ['Mass with spring and viscous damper in parallel', wall()+spring(80,85,170)+damper(80,145)+line(215,145,250,145)+mass()+label(165,57,'k')+label(165,180,'c')+arrow(355,185,425,185)+label(390,213,'+x')],
    damper: ['Viscous damper between two ends', line(70,70,70,165)+damper(70,115)+line(205,115,345,115)+line(345,75,345,155)+arrow(350,60,425,60)+label(385,42,'v relative')+label(160,163,'c')],
    parallel_springs: ['Two springs connect the same wall and mass in parallel', wall()+spring(80,80,170)+spring(80,145,170)+mass()+label(170,53,'k₁')+label(170,184,'k₂')],
    series_springs: ['Two springs connected end to end', line(45,55,45,165)+spring(45,115,145)+spring(190,115,145)+rect(335,75,95,80)+label(382,121,'m')+label(112,76,'k₁')+label(260,76,'k₂')],
    circuit: ['A resistor and capacitor in one series circuit', path('M85 95V55h70l10-10 14 20 14-20 14 20 14-20 14 20 10-10h155v45m-25 0h50m-50 22h50m-25 0v60H85v-47M60 95h50m-40 40h30')+label(200,34,'R')+label(425,116,'C')+label(115,121,'V')],
    truss: ['Exactly two non-collinear members meet at an unloaded joint', path('M90 170L240 65L390 170')+circle(240,65,5)+label(240,38,'Unloaded joint')+label(110,205,'Member 1')+label(370,205,'Member 2')],
    circle: ['Radius measured from the center to the circle', circle(240,115,80)+arrow(240,115,317,115)+label(278,100,'r')+circle(240,115,3)],
    polar: ['First-quadrant quarter circle with radius r', path('M130 185V45A140 140 0 0 1 270 185Z','fill="#244c63"')+arrow(100,185,345,185)+arrow(130,210,130,25)+line(130,185,229,86)+label(199,120,'r')+label(355,191,'x')+label(112,30,'y')+label(175,175,'θ')],
    revolution: ['Cone formed by rotating y = x about the x-axis', path('M95 115L360 40v150Z')+'<ellipse cx="360" cy="115" rx="15" ry="75"/>'+'<ellipse cx="265" cy="115" rx="10" ry="48" stroke="#e9c88e"/>'+line(65,115,425,115,'stroke-dasharray="6 5"')+label(438,121,'x')+label(260,205,'Representative disk')],
    motion: ['Motion and acceleration along the horizontal direction', rect(115,100,115,65)+circle(140,179,11)+circle(205,179,11)+arrow(260,115,410,115)+label(335,92,'+ direction')+line(70,193,430,193)],
    forces: ['Opposing horizontal forces; right force is three times left force', rect(210,85,70,70)+arrow(210,120,155,120)+arrow(280,120,445,120)+label(125,96,'Left force')+label(365,96,'Right force')+label(245,128,'m')],
    falling: ['Fall from rest through vertical height h', circle(210,55,16)+circle(210,175,16)+arrow(210,81,210,147)+label(185,119,'g')+line(285,55,285,175)+line(279,55,291,55)+line(279,175,291,175)+label(303,120,'h')+label(177,33,'Start: v = 0')+label(164,210,'After the drop')],
    collision: ['Equal carts before impact: one moving, one at rest', rect(70,95,95,65)+rect(300,95,95,65)+label(118,133,'m')+label(348,133,'m')+arrow(175,125,265,125)+label(220,101,'6 m/s')+label(350,78,'v = 0')+label(240,202,'They stick together after impact')],
    wave: ['Wavelength spans two neighboring crests', line(50,135,430,135)+path('M50 135Q95 35 140 135T230 135T320 135T410 135','stroke="#8bbfff"')+dimension(95,275,48,'λ')],
    charges: ['Equal positive point charges repel along their separation', circle(160,115,24)+circle(320,115,24)+label(160,121,'+')+label(320,121,'+')+arrow(135,115,65,115)+arrow(345,115,415,115)+dimension(160,320,180,'r')],
    field: ['A positive charge in a uniform electric field', [65,120,175].map(y=>arrow(70,y,420,y)).join('')+circle(240,120,23,'fill="#17242b"')+label(240,126,'+q')+label(438,126,'E')],
    resistor: ['One resistor across an ideal battery', path('M85 95V55h70l10-10 14 20 14-20 14 20 14-20 14 20 10-10h155v130H85v-50M60 95h50m-40 40h30')+label(200,34,'R')+label(120,121,'V')],
    capacitor: ['Opposite capacitor plates and potential difference V', line(70,120,210,120)+line(270,120,410,120)+line(210,55,210,185)+line(270,55,270,185)+label(182,80,'+')+label(298,80,'−')+label(240,220,'V across the plates')],
    magnetic: ['Current to the right, magnetic field into the page', [115,240,365].map(x=>[65,165].map(y=>path(`M${x-7} ${y-7}l14 14m0-14-14 14`)).join('')).join('')+arrow(65,115,415,115)+label(240,97,'Current I')+label(240,215,'× means B into the page')],
    coil: ['Changing magnetic flux links all N turns of the coil', [190,220,250,280].map(x=>`<ellipse cx="${x}" cy="115" rx="12" ry="65"/>`).join('')+arrow(75,115,390,115)+label(240,31,'N turns')+label(240,213,'Flux per turn changes with time')],
    lens: ['Converging lens: object at 3f; rays meet at the inverted real image', line(40,120,440,120)+'<ellipse cx="260" cy="120" rx="10" ry="80" stroke="#8bbfff"/>'+arrow(80,120,80,60)+arrow(350,120,350,150)+path('M80 60H260L350 150M80 60L350 150','stroke="#e9c88e"')+circle(200,120,3)+circle(320,120,3)+label(200,143,'F')+label(320,143,'F')+label(79,43,'Object')+label(383,178,'Image')+dimension(80,260,201,'Object distance')],
    incline: ['Frictionless 30° slope; gravity points vertically downward', path('M70 190H400L400 0Z')+path('M190 121l48-28-20-35-48 28Z')+arrow(204,95,204,182)+label(226,165,'mg')+label(117,182,'30°')],
  };

  function plot(data) {
    if (!data || !Number.isFinite(data.lower) || !Number.isFinite(data.upper) || data.lower < 0 || data.upper <= data.lower || data.upper > 10) return null;
    const a = data.coefficient;
    if (!Number.isFinite(a) || a <= 0 || a > 5) return null;
    const functions = {square: x=>x*x, parts: x=>x*Math.exp(x), substitution: x=>2*a*x*Math.exp(a*x*x), rational: x=>1/(x*(x+1))};
    const f = functions[data.function]; if (!f || (data.function === 'rational' && data.lower <= 0)) return null;
    const points = Array.from({length:81},(_,i)=>{const x=data.lower+(data.upper-data.lower)*i/80;return [x,f(x)];});
    const top = Math.max(...points.map(p=>p[1])); if (!Number.isFinite(top) || top <= 0) return null;
    const x = v=>60+345*v/data.upper, y = v=>185-125*v/top;
    const curve = points.map(([a,b],i)=>(i?'L':'M')+x(a).toFixed(3)+' '+y(b).toFixed(3)).join(' ');
    const area = `M${x(data.lower)} 185 ${curve.replace(/^M/,'L')} L${x(data.upper)} 185Z`;
    return ['Shaded integral of '+data.label+' from '+data.lower+' to '+data.upper,
      path(area,'class="diagram-area" fill="#244c63" stroke="none"')+arrow(45,185,444,185)+arrow(60,200,60,35)+path(curve,'class="diagram-curve" stroke="#8bbfff"')+
      line(x(data.lower),180,x(data.lower),190)+line(x(data.upper),180,x(data.upper),190)+label(x(data.lower),215,data.lower)+label(x(data.upper),215,data.upper)+label(451,189,'x')+label(42,34,'y')+label(250,28,data.label)];
  }
  window.ScrollForgeDiagrams = {render(card) {
    const drawing = card.diagram === 'plot' ? plot(card.diagram_data) : drawings[card.diagram];
    if (!drawing) return '';
    const caption = drawing[0]+(card.diagram === 'plot' ? '' : ' · schematic, dimensions in the question');
    return '<figure class="study-visual" data-diagram="'+esc(card.diagram)+'"><svg viewBox="0 0 480 240" role="img" aria-label="'+esc(drawing[0])+'"><g fill="none" stroke="#9aaeb8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+drawing[1]+'</g></svg><figcaption><span>'+esc(caption)+'</span>'+(card.diagram_labels||[]).map(text=>'<strong>'+esc(text)+'</strong>').join('')+'</figcaption></figure>';
  }};
})();
