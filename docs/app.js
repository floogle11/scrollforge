(function () {
  'use strict';
  const KEYS = { seen: 'scrollforge.seen_card_ids', seenSources: 'scrollforge.seen_source_urls', read: 'scrollforge.read_comment_ids', repo: 'scrollforge.repo_slug', token: 'scrollforge.github_token', pending: 'scrollforge.pending_comments', answers: 'scrollforge.quiz_answers' };
  const categories = {
    INTEREST: ['Interests', '#b7df9c'], SPORTS: ['NFL', '#ffac85'], NEWS: ['News', '#8bbfff'], STORY: ['Story', '#d7b0f3'],
    CHALLENGE_CURRENT: ['Current challenge', '#e9c88e'], CHALLENGE_PAST: ['Practice challenge', '#e9c88e'], DEEP_CUT: ['Engineering', '#c9d98c']
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const readStore = (key, fallback) => { try { const v = JSON.parse(localStorage.getItem(key)); return v == null ? fallback : v; } catch (_) { return fallback; } };
  const writeStore = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };
  const challenge = card => /^CHALLENGE_/.test(card.category || '');
  const shuffle = list => { const a = list.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

  function freshCard(card, now = Date.now()) {
    const days = card.category === 'SPORTS' || card.category === 'NEWS' ? 7 : card.category === 'STORY' ? 30 : null;
    if (days === null) return true;
    const created = Date.parse(card.created_at);
    return Number.isFinite(created) && created >= now - days * 86400000;
  }
  function sourceKey(card) {
    if (!card) return null;
    if (!['SPORTS', 'NEWS', 'STORY'].includes(card.category) || !card.source_url) return null;
    try {
      const url = new URL(card.source_url);
      url.hash = '';
      for (const key of [...url.searchParams.keys()]) if (/^(utm_|fbclid$|gclid$)/i.test(key)) url.searchParams.delete(key);
      url.pathname = url.pathname.replace(/\/$/, '');
      return url.href;
    } catch (_) { return null; }
  }
  function eligibleCards(cards, now = Date.now()) {
    const ids = new Set(), sources = new Set();
    return cards.filter(card => card && card.id).slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).filter(card => {
      const source = sourceKey(card);
      if (!card || !card.id || ids.has(card.id) || !freshCard(card, now) || (source && sources.has(source))) return false;
      ids.add(card.id); if (source) sources.add(source); return true;
    });
  }
  // Explicit, reversible signals only. Reading a post is not treated as approval.
  function interestFeatures(card) {
    const features = ['category:' + card.category];
    for (const key of ['sport', 'team', 'course_tag']) if (card[key]) features.push(key + ':' + card[key]);
    const text = [card.title, card.topic, String(card.body_markdown || '').slice(0, 600)].join(' ').toLowerCase();
    if (card.category === 'SPORTS') {
      if (/\bbroncos\b/.test(text)) features.push('team:Denver Broncos');
      if (/\bmammoth\b/.test(text)) features.push('team:Utah Mammoth');
      if (/\b(avalanche|avs)\b/.test(text)) features.push('team:Colorado Avalanche');
    }
    const topics = {
      space: /\b(nasa|space|astronaut|orbit|galaxy|lunar|mars|telescope)\b/,
      technology: /\b(technology|software|artificial intelligence|openai|robot|robots|cybersecurity|semiconductor)\b/,
      science: /\b(science|scientist|scientists|discovery|research|fossil|quantum)\b/,
      history: /\b(history|historic|ancient|archaeology|archaeologist|medieval)\b/,
      politics: /\b(election|congress|senate|president|politics|parliament)\b/,
      economy: /\b(economy|inflation|stocks|market|tariff|tariffs|interest rates)\b/,
      climate: /\b(climate|warming|renewable|emissions|hurricane|wildfire)\b/,
      drama: /\b(drama|aita|aitah|pettyrevenge|relationship|relationships)\b/,
      football: /\b(nfl|broncos|football|touchdown|quarterback)\b/,
      chess: /\b(chess|italian game|giuoco|knight|bishop)\b/,
      hockey: /\b(nhl|hockey|mammoth|avalanche|puck)\b/
    };
    for (const [topic, pattern] of Object.entries(topics)) if (pattern.test(text)) features.push('topic:' + topic);
    // Bank topics are stable subject labels; title-length topics are intentionally ignored.
    if (card.topic && card.topic.length <= 32) features.push('topic:' + card.topic.toLowerCase());
    try {
      const url = new URL(card.source_url);
      const subreddit = /(^|\.)reddit\.com$/.test(url.hostname) && url.pathname.match(/^\/r\/([^/]+)/i);
      features.push('source:' + (subreddit ? 'r/' + subreddit[1].toLowerCase() : url.hostname.replace(/^www\./, '')));
    } catch (_) {}
    return [...new Set(features)];
  }
  function preferenceProfile(votes, now = Date.now()) {
    const profile = Object.create(null);
    for (const vote of Object.values(votes || {})) {
      if (!vote || ![1, -1].includes(vote.value) || !Array.isArray(vote.features) || !Number.isFinite(vote.at)) continue;
      const decay = Math.pow(0.5, Math.max(0, now - vote.at) / (45 * 86400000));
      for (const feature of vote.features.slice(0, 16)) if (typeof feature === 'string') profile[feature] = (profile[feature] || 0) + vote.value * decay;
    }
    return profile;
  }
  function preferenceWeight(card, profile = {}) {
    let score = 0;
    for (const feature of interestFeatures(card)) {
      const strength = feature.startsWith('category:') ? 0.12 : feature.startsWith('source:') ? 0.25 : 0.65;
      score += Math.tanh((profile[feature] || 0) / 3) * strength;
    }
    // Keep discovery alive, even after strong preferences.
    return 0.25 + 0.75 * Math.exp(Math.max(-1.4, Math.min(1.4, score)));
  }
  // News and stories are consumed once. Evergreen notes can space a review-only tail.
  function interleaveCards(cards, seenIds = [], mode = 'BASELINE', boundaryCards = [], profile = {}) {
    const seen = new Set(seenIds);
    const weightSets = {
      BASELINE: { sports: 25, hockey: 20, news: 25, story: 11, drama: 4, current: 10, past: 5, interest: 8 },
      EXAM_WINDOW: { sports: 20, hockey: 15, news: 20, story: 10, drama: 3, current: 27, past: 5, interest: 8 },
      CRUNCH_WINDOW: { sports: 20, hockey: 15, news: 20, story: 10, drama: 3, current: 27, past: 5, interest: 8 },
      EXAM_DAY: { sports: 25, hockey: 20, news: 25, story: 11, drama: 4, current: 15, past: 0, interest: 8 }
    };
    const weights = weightSets[mode] || weightSets.BASELINE;
    const typeOf = card => card.category === 'SPORTS' ? (card.sport === 'hockey' ? 'hockey' : 'sports') : card.category === 'NEWS' ? 'news' :
      card.category === 'CHALLENGE_CURRENT' || card.category === 'DEEP_CUT' ? 'current' : card.category === 'CHALLENGE_PAST' ? 'past' : card.category === 'INTEREST' ? 'interest' : card.topic === 'drama' ? 'drama' : 'story';
    const unique = cards.filter((card, i) => card && card.id && cards.findIndex(item => item.id === card.id) === i);
    const pools = {sports: [], hockey: [], news: [], story: [], drama: [], current: [], past: [], interest: []};
    const ranked = unique.filter(card => !seen.has(card.id)).map(card => ({card, rank: -Math.log(Math.max(Number.EPSILON, Math.random())) / preferenceWeight(card, profile)})).sort((a, b) => a.rank - b.rank);
    for (const {card} of ranked) pools[typeOf(card)].push(card);
    const spacers = shuffle(unique.filter(card => card.category === 'DEEP_CUT'));
    const mixed = [];
    let spacerCursor = 0, run = 0;
    const prior = Array.isArray(boundaryCards) ? boundaryCards : [boundaryCards].filter(Boolean);
    const history = prior.slice(-3);
    const group = card => challenge(card) || card.category === 'DEEP_CUT' ? 'study' : typeOf(card);
    const poolWeights = Object.fromEntries(Object.entries(pools).map(([key, pool]) => [key, weights[key] * (pool.length ? pool.reduce((sum, card) => sum + preferenceWeight(card, profile), 0) / pool.length : 1)]));
    const push = card => { mixed.push(card); history.push(card); if (history.length > 3) history.shift(); run = challenge(card) ? run + 1 : 0; };
    for (let i = prior.length - 1; i >= 0 && challenge(prior[i]); i--) run++;
    while (Object.values(pools).some(pool => pool.length)) {
      if (run >= 2) {
        const leisure = [pools.sports, pools.hockey, pools.news, pools.story, pools.drama].find(pool => pool.length) || [];
        if (leisure.length || spacers.length) {
          push(leisure.length ? leisure.shift() : spacers[spacerCursor++ % spacers.length]);
          run = 0; continue;
        }
      }
      let active = Object.keys(pools).filter(key => pools[key].length);
      const last = history[history.length - 1];
      const alternatives = active.filter(key => group(pools[key][0]) !== (last && group(last)));
      if (alternatives.length) active = alternatives;
      const total = active.reduce((sum, key) => sum + poolWeights[key], 0);
      let roll = Math.random() * (total || active.length), selected = active[0];
      for (const key of active) { roll -= total ? poolWeights[key] : 1; if (roll < 0) { selected = key; break; } }
      // Avoid adjacent publishers, teams, courses, and recognized subjects when inventory allows.
      const recent = last ? new Set(interestFeatures(last).filter(f => !f.startsWith('category:') && !f.startsWith('sport:'))) : new Set();
      const index = pools[selected].findIndex(card => !interestFeatures(card).some(f => recent.has(f)));
      const card = pools[selected].splice(index < 0 ? 0 : index, 1)[0]; push(card);
    }
    return mixed;
  }
  const publicFunctions = {interleaveCards, eligibleCards, freshCard, interestFeatures, preferenceProfile, preferenceWeight};
  if (typeof window !== 'undefined') window.ScrollForge = publicFunctions;
  if (typeof module !== 'undefined' && module.exports) { module.exports = publicFunctions; return; }

  let feed = null;
  let ordered = [];
  let cursor = 0;
  let viewObserver = null;
  let scrollFrame = null;
  let replyPollTimer = null;
  let replyPollInFlight = false;
  let settingsReturnFocus = null;
  let activeTopic = 'all';
  const interestReviewIds = new Set();
  let tailObserver = null;
  const PAGE_SIZE = 24;
  const VOTES_KEY = 'scrollforge.preferences.v1';
  let votes = readStore(VOTES_KEY, {});
  if (!votes || typeof votes !== 'object' || Array.isArray(votes)) votes = {};
  votes = Object.fromEntries(Object.entries(votes).filter(([, vote]) => vote && [1, -1].includes(vote.value) && Array.isArray(vote.features) && Number.isFinite(vote.at)).sort((a, b) => b[1].at - a[1].at).slice(0, 500));
  const savedAnswers = readStore(KEYS.answers, {});
  const localPending = readStore(KEYS.pending, {});
  const readIds = new Set(readStore(KEYS.read, []));

  const safeUrl = value => {
    if (!value || typeof value !== 'string') return null;
    try { const u = new URL(value, location.href); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch (_) { return null; }
  };
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  function inlineMarkdown(text) {
    const math = [];
    let out = String(text).replace(/(\$\$[\s\S]+?\$\$|\$(?:\\.|[^$])+?\$)/g, value => {
      math.push(esc(value)); return '\u0001MATH' + (math.length - 1) + '\u0001';
    });
    out = esc(out);
    // Code spans are held while formatting the surrounding text.
    const code = [];
    out = out.replace(/`([^`]+)`/g, (_, value) => { code.push('<code>' + value + '</code>'); return '\u0000' + (code.length - 1) + '\u0000'; });
    out = out.replace(/\[([^\]]+)\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g, (_, label, rawUrl) => {
      let url = rawUrl.replace(/&amp;/g, '&').replace(/&quot;/g, '"');
      const href = safeUrl(url);
      return href ? '<a href="' + esc(href) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>' : label;
    });
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*]+)\*/g, '<em>$1</em>');
    return out.replace(/\u0000(\d+)\u0000/g, (_, i) => code[Number(i)])
      .replace(/\u0001MATH(\d+)\u0001/g, (_, i) => math[Number(i)]);
  }
  function renderMarkdown(markdown) {
    // Raw HTML is escaped before this deliberately small Markdown subset is applied.
    const lines = String(markdown || '').replace(/\r/g, '').split('\n');
    const blocks = [];
    let paragraph = [], list = [], quote = [], code = null;
    const flushParagraph = () => { if (paragraph.length) { blocks.push('<p>' + paragraph.map(inlineMarkdown).join('<br>') + '</p>'); paragraph = []; } };
    const flushList = () => { if (list.length) { blocks.push('<ul>' + list.map(x => '<li>' + inlineMarkdown(x) + '</li>').join('') + '</ul>'); list = []; } };
    const flushQuote = () => { if (quote.length) { blocks.push('<blockquote><p>' + quote.map(inlineMarkdown).join('<br>') + '</p></blockquote>'); quote = []; } };
    for (const line of lines) {
      if (code) { if (/^\s*```/.test(line)) { blocks.push('<pre><code>' + esc(code.join('\n')) + '</code></pre>'); code = null; } else code.push(line); continue; }
      if (/^\s*```/.test(line)) { flushParagraph(); flushList(); flushQuote(); code = []; continue; }
      if (!line.trim()) { flushParagraph(); flushList(); flushQuote(); continue; }
      const li = line.match(/^\s*[-*+]\s+(.+)/);
      const q = line.match(/^\s*&gt;\s?(.*)$/) || line.match(/^\s*>\s?(.*)$/);
      if (li) { flushParagraph(); flushQuote(); list.push(li[1]); continue; }
      if (q) { flushParagraph(); flushList(); quote.push(q[1]); continue; }
      flushList(); flushQuote(); paragraph.push(line);
    }
    if (code) blocks.push('<pre><code>' + esc(code.join('\n')) + '</code></pre>');
    flushParagraph(); flushList(); flushQuote();
    return blocks.join('');
  }
  function hydrateMath(root) {
    if (window.renderMathInElement) window.renderMathInElement(root, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }], throwOnError: false, ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] });
  }
  function dateLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(+date)) return 'Field note';
    const hours = Math.max(0, Math.floor((Date.now() - date) / 3600000));
    if (hours < 1) return 'Just now';
    if (hours < 24) return hours + 'h ago';
    if (hours < 168) return Math.floor(hours / 24) + 'd ago';
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
  }
  function communityLabel(card) {
    const names = {broncos: 'Denver Broncos', nfl: 'NFL.com', espn_nfl: 'ESPN', bbc_world: 'BBC News',
      bbc_technology: 'BBC Technology', npr: 'NPR', guardian_us: 'The Guardian', nasa: 'NASA', smithsonian: 'Smithsonian Magazine',
      espn_nhl: 'ESPN NHL', espn_avalanche: 'Colorado Avalanche · ESPN', espn_mammoth: 'Utah Mammoth · ESPN',
      nhl_mammoth: 'Utah Mammoth', nhl_avalanche: 'Colorado Avalanche'};
    const match = String(card.id).match(/^rss_(.+)_[^_]+$/);
    const source = safeUrl(card.source_url);
    if (source) {
      const url = new URL(source);
      const subreddit = /(^|\.)reddit\.com$/.test(url.hostname) && url.pathname.match(/^\/r\/([^/]+)/i);
      if (subreddit) return 'r/' + subreddit[1];
      if (match && names[match[1]]) return names[match[1]];
      return url.hostname.replace(/^www\./, '');
    }
    return card.category === 'INTEREST' ? 'Your interests' : card.course_tag || (card.category === 'DEEP_CUT' ? 'Engineering' : card.category === 'STORY' ? 'Stories' : 'Your study notes');
  }
  function getComments(card) {
    const combined = Array.isArray(card.comments) ? card.comments.slice() : [];
    const pending = localPending[card.id] || [];
    for (const item of pending) if (!combined.some(c => c.id === item.id)) combined.push(item);
    return combined.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }
  function markThreadRead(card) {
    for (const comment of getComments(card)) if (comment.author === 'CODEX') readIds.add(comment.id);
    writeStore(KEYS.read, Array.from(readIds));
    updateInboxCount();
  }
  function unreadCodexCount() {
    if (!feed) return 0;
    return feed.cards.reduce((n, card) => n + (card.comments || []).filter(c => c.author === 'CODEX' && c.unread && !readIds.has(c.id)).length, 0);
  }
  function updateInboxCount() {
    const count = unreadCodexCount();
    const badge = $('#inboxCount'); badge.textContent = count > 99 ? '99+' : String(count); badge.hidden = count === 0;
  }
  function renderComment(comment) {
    const isCodex = comment.author === 'CODEX';
    const pending = comment.pending === true;
    return '<article class="comment-item ' + (isCodex ? 'codex' : '') + '" data-comment-id="' + esc(comment.id) + '"><div class="comment-meta">' + (isCodex ? 'CODEX REPLY' : 'YOU') + (pending ? '<span class="pending-tag">QUEUED FOR LOCAL CODEX</span>' : '') + ' · ' + esc(dateLabel(comment.created_at)) + '</div><div class="comment-body">' + renderMarkdown(comment.body_markdown) + '</div></article>';
  }
  function selectedAnswer(card) {
    const saved = savedAnswers[card.id];
    return saved && card.quiz && saved.signature === quizSignature(card) && Number.isInteger(saved.index) && saved.index >= 0 && saved.index < card.quiz.options.length ? saved.index : null;
  }
  function quizSignature(card) {
    return JSON.stringify([card.body_markdown, card.quiz.options, card.quiz.correct_index]);
  }
  function quizTemplate(card) {
    const quiz = card.quiz;
    if (!quiz || !Array.isArray(quiz.options) || quiz.options.length < 4 || quiz.options.length > 8 || !Number.isInteger(quiz.correct_index) || quiz.correct_index < 0 || quiz.correct_index >= quiz.options.length) return '';
    const selected = selectedAnswer(card);
    const answered = selected !== null;
    return '<div class="quiz"><fieldset><legend>What do you think?</legend><div class="quiz-options">' + quiz.options.map((option, i) => {
      const result = answered && i === quiz.correct_index ? ' correct' : answered && i === selected ? ' incorrect' : '';
      return '<button type="button" class="quiz-option' + result + '" data-answer="' + i + '" aria-pressed="' + (i === selected) + '"' + (answered ? ' disabled' : '') + '><span class="option-letter">' + String.fromCharCode(65+i) + '</span><span>' + inlineMarkdown(option) + '</span>' + (answered && i === quiz.correct_index ? '<span class="answer-mark">✓</span>' : answered && i === selected ? '<span class="answer-mark">×</span>' : '') + '</button>';
    }).join('') + '</div></fieldset><div class="quiz-feedback" role="status" tabindex="-1">' + (answered ? (selected === quiz.correct_index ? 'Correct. ' : 'Not quite. The correct answer is ' + String.fromCharCode(65+quiz.correct_index) + '. ') + 'The worked answer is below. <button type="button" class="quiz-retry">Try again</button>' : 'Pick one answer. No grades, just a quick check.') + '</div></div>';
  }
  function diagramTemplate(card) {
    return window.ScrollForgeDiagrams ? window.ScrollForgeDiagrams.render(card) : '';
  }
  function chessTemplate(card) {
    if (!card.chess || typeof card.chess.svg !== 'string') return '';
    const side = card.chess.fen.split(' ')[1] === 'b' ? 'Black' : 'White';
    // SVG is isolated as an image; never insert model/feed markup into the page.
    return '<figure class="chess-board"><img loading="lazy" width="390" height="390" alt="Chess position, ' + side + ' to move" src="data:image/svg+xml;charset=utf-8,' + esc(encodeURIComponent(card.chess.svg)) + '"><figcaption>' + side + ' to move · Board built with python-chess</figcaption></figure>';
  }
  function redditEmbedUrl(value) {
    try {
      const source = new URL(value);
      if (!/(^|\.)reddit\.com$/.test(source.hostname) || !/^\/r\/[\w]+\/comments\/[a-z0-9]+(?:\/[^/]+)?\/?$/i.test(source.pathname)) return null;
      const url = new URL(source.pathname, 'https://embed.reddit.com');
      url.search = new URLSearchParams({embed: 'true', theme: 'dark', showmedia: 'true', ref_source: 'embed', ref: 'share'}).toString();
      return url.href;
    } catch (_) { return null; }
  }
  function toggleReddit(button) {
    const card = button.closest('.feed-card');
    let preview = $('.reddit-preview', card);
    if (!preview) {
      const source = ordered[Number(card.dataset.cardIndex)].source_url;
      const url = redditEmbedUrl(source); if (!url) return;
      preview = document.createElement('div'); preview.className = 'reddit-preview';
      const frame = document.createElement('iframe'); frame.src = url;
      frame.title = 'Original Reddit post'; frame.loading = 'lazy';
      frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-popups');
      frame.height = '550'; preview.append(frame);
      const fallback = document.createElement('p');
      const link = document.createElement('a'); link.href = source; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'Open the post and discussion on Reddit ↗';
      fallback.append(link); preview.append(fallback); card.append(preview);
      button.setAttribute('aria-expanded', 'true'); button.textContent = 'Hide Reddit post';
    } else {
      preview.hidden = !preview.hidden;
      button.setAttribute('aria-expanded', String(!preview.hidden)); button.textContent = preview.hidden ? 'Show Reddit post' : 'Hide Reddit post';
    }
  }
  function cardTemplate(card, index) {
    const [defaultLabel, accent] = categories[card.category] || ['Post', '#8bbfff'];
    const label = card.sport === 'hockey' ? (card.team || 'NHL') : card.topic === 'drama' ? 'Reddit drama' : defaultLabel;
    const answered = selectedAnswer(card) !== null;
    const comments = getComments(card);
    const codexReplies = comments.filter(c => c.author === 'CODEX').length;
    const source = safeUrl(card.source_url);
    const sample = /^SAMPLE\b/i.test(card.title || '');
    const title = sample ? card.title.replace(/^SAMPLE\s*[:—-]?\s*/i, '') : card.title;
    const bodyText = String(card.body_markdown || '').trim();
    const bodyTokens = bodyText.split(/\s+/).filter(Boolean);
    const bodyWords = bodyTokens.length;
    const bodyContent = bodyWords > 55 && !challenge(card)
      ? '<div class="body-preview">' + renderMarkdown(bodyTokens.slice(0, 55).join(' ')) + '…</div><div class="body-full" hidden>' + renderMarkdown(bodyText) + '</div><button type="button" class="body-expand" data-expand-label="Read more" data-collapse-label="Show less">Read more</button>'
      : renderMarkdown(bodyText);
    const community = communityLabel(card);
    return '<article class="feed-card" tabindex="-1" data-card-index="' + index + '" data-card-id="' + esc(card.id) + '" style="--accent:' + accent + '">' +
      '<div class="card-topline"><span class="community-avatar" aria-hidden="true">' + esc(community.replace(/^r\//, '').charAt(0).toUpperCase()) + '</span>' +
      (source ? '<a class="community-name" href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + esc(community) + '</a>' : '<span class="community-name">' + esc(community) + '</span>') +
      '<span aria-hidden="true">·</span><time class="card-time" datetime="' + esc(card.created_at) + '">' + esc(dateLabel(card.created_at)) + '</time><span class="card-course">' + esc(card.course_tag || '') + '</span></div>' +
      (sample ? '<div class="sample-marker">SAMPLE FEED · DEMONSTRATION CARD</div>' : '') +
      '<h2 class="card-title">' + (source ? '<a href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + esc(title) + '</a>' : esc(title)) + '</h2><span class="category-chip">' + esc(label) + '</span><div class="card-body">' + bodyContent + '</div>' +
      (safeUrl(card.image_url) ? '<img class="post-image" src="' + esc(safeUrl(card.image_url)) + '" alt="' + esc(title) + '" loading="lazy" referrerpolicy="no-referrer">' : '') + diagramTemplate(card) + chessTemplate(card) + quizTemplate(card) +
      '<div class="card-footer">' +
      '<button class="preference-button" type="button" data-preference="1" aria-pressed="' + (votes[card.id]?.value === 1) + '" title="Favor related topics, teams, subjects and sources">↑ More like this</button>' +
      '<button class="preference-button" type="button" data-preference="-1" aria-pressed="' + (votes[card.id]?.value === -1) + '" title="See fewer related posts">↓ Less like this</button>' +
      '<button class="comment-toggle" type="button" aria-expanded="false"><svg class="ui-icon" aria-hidden="true"><use href="#icon-comment"/></svg> Comments <span class="reply-count">' + comments.length + (codexReplies ? ' · ' + codexReplies + ' replies' : '') + '</span></button>' +
      (card.solution_markdown ? '<button class="solution-toggle" type="button" aria-expanded="' + answered + '">' + (answered ? 'Hide answer' : 'Reveal answer') + '</button>' : '') +
      (redditEmbedUrl(source) ? '<button class="reddit-toggle" type="button" aria-expanded="false">Show Reddit post</button>' : '') +
      (source ? '<a class="source-link" href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + (community.startsWith('r/') ? 'View on Reddit ↗' : 'Read article ↗') + '</a>' : '') +
      (sample ? '<span class="sample-label">SAMPLE</span>' : '') + '</div>' +
      (card.solution_markdown ? '<section class="solution-panel' + (answered ? ' open' : '') + '"><div class="solution-label">The worked answer</div><div class="solution-content">' + renderMarkdown(card.solution_markdown) + '</div></section>' : '') +
      '<section class="card-comments"><div class="comment-list">' + (comments.length ? comments.map(renderComment).join('') : '<div class="source-missing">Start the conversation. Ask a question or add a thought.</div>') + '</div>' +
      '<form class="comment-form"><textarea name="comment" maxlength="2000" aria-label="Your comment" placeholder="Ask a follow-up or leave a note…" required></textarea><button type="submit">SEND ↗</button><div class="comment-feedback" role="status"></div></form></section>' +
      '<span hidden data-word-count="' + bodyWords + '"></span></article>';
  }
  function endTemplate() {
    return '<section class="feed-end"><div class="feed-tail-copy"><div class="eyebrow">END OF CURRENT FEED</div><h2>You\'re caught up.</h2>' +
      '<p>New posts arrive throughout the day. There is more practice in the school feed whenever you want it.</p></div>' +
      '<button class="load-more" type="button" hidden>Keep scrolling · load more</button>' +
      '<div class="end-actions"><button class="solution-toggle refresh-feed" type="button">Refresh posts</button>' +
      '<button class="solution-toggle review-engineering" type="button">REVIEW ENGINEERING</button></div></section>';
  }
  function syncPosition() {
    const nodes = $$('.feed-card', $('#cardStage')).filter(node => !node.hidden);
    if (!nodes.length) { $('#cardPosition').textContent = '00 / 00'; $('#progressBar').style.width = '100%'; return; }
    const target = $('.topbar').getBoundingClientRect().bottom + 30;
    let closest = null, distance = Infinity;
    for (const node of nodes) {
      const rect = node.getBoundingClientRect();
      const score = rect.top <= target && rect.bottom >= target ? 0 : Math.min(Math.abs(rect.top - target), Math.abs(rect.bottom - target));
      if (score < distance) { closest = node; distance = score; }
    }
    if (closest) cursor = Number(closest.dataset.cardIndex);
    for (const node of $$('.feed-card', $('#cardStage'))) node.toggleAttribute('data-active', !node.hidden && Number(node.dataset.cardIndex) === cursor);
    const position = nodes.findIndex(node => Number(node.dataset.cardIndex) === cursor) + 1;
    const total = matchingCards().length;
    $('#cardPosition').textContent = position + ' / ' + total;
    $('#progressBar').style.width = (position / Math.max(1, total) * 100) + '%';
  }
  function observeCards() {
    if (viewObserver) viewObserver.disconnect();
    viewObserver = new IntersectionObserver(entries => {
      const seen = new Set(readStore(KEYS.seen, []));
      const seenSources = new Set(readStore(KEYS.seenSources, []));
      for (const entry of entries) {
        if (entry.target.isConnected && entry.isIntersecting && entry.intersectionRect.height >= Math.min(entry.boundingClientRect.height * .5, innerHeight * .35)) {
          seen.add(entry.target.dataset.cardId);
          const key = sourceKey(ordered[Number(entry.target.dataset.cardIndex)]);
          if (key) seenSources.add(key);
        }
      }
      writeStore(KEYS.seen, [...seen]); writeStore(KEYS.seenSources, [...seenSources]); syncPosition();
    }, {threshold: [0, .1, .25, .5, .75, 1], rootMargin: '-64px 0px 0px 0px'});
    for (const node of $$('.feed-card', $('#cardStage'))) viewObserver.observe(node);
    syncPosition();
  }
  function renderFeed() {
    const stage = $('#cardStage');
    if (tailObserver) tailObserver.disconnect();
    stage.innerHTML = '<div class="empty-card" id="filterEmpty" hidden role="status"><p>No posts here right now. Try another topic or search.</p></div>' + endTemplate();
    applyFilters();
    tailObserver = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) appendPage();
    }, {rootMargin: '900px 0px'});
    tailObserver.observe($('.feed-end', stage));
  }
  function matchingCards() {
    const query = $('#feedSearch').value.trim().toLocaleLowerCase();
    const matchesTopic = card => activeTopic === 'all' ||
      (activeTopic === 'sports' && card.category === 'SPORTS' && card.sport !== 'hockey') ||
      (activeTopic === 'hockey' && card.sport === 'hockey') ||
      (activeTopic === 'mammoth' && card.team === 'Utah Mammoth') ||
      (activeTopic === 'avalanche' && card.team === 'Colorado Avalanche') ||
      (activeTopic === 'interests' && card.category === 'INTEREST') ||
      (activeTopic === 'chess' && card.topic === 'chess') ||
      (activeTopic === 'news' && card.category === 'NEWS') ||
      (activeTopic === 'stories' && card.category === 'STORY') ||
      (activeTopic === 'drama' && card.topic === 'drama') ||
      (activeTopic === 'engineering' && (challenge(card) || card.category === 'DEEP_CUT'));
    const ids = new Set();
    const cards = ordered.filter(card => {
      if (ids.has(card.id)) return false; ids.add(card.id);
      return (activeTopic !== 'all' || !interestReviewIds.has(card.id)) && matchesTopic(card) && (activeTopic !== 'engineering' || !$('#studyCourse').value || card.course_tag === $('#studyCourse').value) && [card.title, card.body_markdown, communityLabel(card), card.course_tag || '', card.topic || '', card.team || ''].join(' ').toLocaleLowerCase().includes(query);
    });
    if ($('#feedSort').value === 'new') cards.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
    return cards;
  }
  function updateTail() {
    const mounted = new Set($$('.feed-card', $('#cardStage')).map(node => node.dataset.cardId));
    const remaining = matchingCards().filter(card => !mounted.has(card.id)).length;
    $('.load-more').hidden = remaining === 0;
    $('.feed-tail-copy').hidden = remaining > 0;
    $('.end-actions').hidden = remaining > 0;
    $('#filterEmpty').hidden = matchingCards().length > 0;
  }
  function appendPage() {
    const stage = $('#cardStage'); if (!$('#filterEmpty')) return;
    const mounted = new Set($$('.feed-card', stage).map(node => node.dataset.cardId));
    const next = matchingCards().filter(card => !mounted.has(card.id)).slice(0, PAGE_SIZE);
    if (!next.length) { updateTail(); return; }
    for (const card of next) $('#filterEmpty').insertAdjacentHTML('beforebegin', cardTemplate(card, ordered.indexOf(card)));
    const rank = new Map(matchingCards().map((card, index) => [card.id, index]));
    const sorted = $$('.feed-card', stage).sort((a, b) => (rank.get(a.dataset.cardId) ?? Infinity) - (rank.get(b.dataset.cardId) ?? Infinity));
    for (const node of sorted) stage.insertBefore(node, $('#filterEmpty'));
    for (const card of next) hydrateMath($$('.feed-card', stage).find(node => node.dataset.cardId === card.id));
    observeCards(); updateTail();
  }
  function applyFilters() {
    const matching = matchingCards();
    const rank = new Map(matching.map((card, index) => [card.id, index]));
    const nodes = $$('.feed-card', $('#cardStage'));
    nodes.sort((a, b) => (rank.get(a.dataset.cardId) ?? Infinity) - (rank.get(b.dataset.cardId) ?? Infinity));
    for (const node of nodes) {
      node.hidden = !rank.has(node.dataset.cardId);
      $('#cardStage').insertBefore(node, $('#filterEmpty'));
    }
    // Fill the first page for a new filter, including posts not mounted yet.
    const firstPage = matching.slice(0, PAGE_SIZE);
    for (const card of firstPage) if (!nodes.some(node => node.dataset.cardId === card.id)) $('#filterEmpty').insertAdjacentHTML('beforebegin', cardTemplate(card, ordered.indexOf(card)));
    const mounted = $$('.feed-card', $('#cardStage'));
    mounted.sort((a, b) => (rank.get(a.dataset.cardId) ?? Infinity) - (rank.get(b.dataset.cardId) ?? Infinity));
    for (const node of mounted) $('#cardStage').insertBefore(node, $('#filterEmpty'));
    hydrateMath($('#cardStage')); observeCards(); updateTail();
    const titles = {interests: 'Your interests', chess: 'Chess · Italian Game', all: 'Home', sports: 'NFL & Broncos', hockey: 'Hockey', mammoth: 'Utah Mammoth', avalanche: 'Colorado Avalanche', news: 'News', stories: 'Stories & discoveries', drama: 'Reddit drama', engineering: 'Engineering'};
    $('#feedTitle').textContent = titles[activeTopic];
    $('#studyFilter').hidden = activeTopic !== 'engineering';
    $$('[data-topic]').forEach(button => {
      const selected = button.dataset.topic === activeTopic;
      button.classList.toggle('active', selected); button.setAttribute('aria-pressed', String(selected));
    });
    syncPosition();
  }
  function activeCardElement() { return $$('.feed-card', $('#cardStage')).find(node => Number(node.dataset.cardIndex) === cursor); }
  function navigate(delta) {
    let visible = $$('.feed-card', $('#cardStage')).filter(node => !node.hidden);
    if (!visible.length) return;
    const current = visible.findIndex(node => Number(node.dataset.cardIndex) === cursor);
    if (delta > 0 && current === visible.length - 1) { appendPage(); visible = $$('.feed-card', $('#cardStage')).filter(node => !node.hidden); }
    cursor = Number(visible[Math.max(0, Math.min(visible.length - 1, current + delta))].dataset.cardIndex);
    const node = activeCardElement(); if (node) node.scrollIntoView({block: 'start', behavior: 'auto'});
    syncPosition();
  }
  function reviewEngineering() {
    if (!feed) return;
    activeTopic = 'engineering'; $('#feedSearch').value = '';
    ordered = interleaveCards(feed.cards.filter(card => challenge(card) || card.category === 'DEEP_CUT'), [], feed.calendar_mode || 'BASELINE', [], preferenceProfile(votes));
    cursor = 0; renderFeed(); $('#cardStage').scrollIntoView({block: 'start'});
  }
  function setNetwork(mode, message) {
    const el = $('#networkStatus'); el.className = 'network-status' + (mode ? ' ' + mode : ''); $('#networkText').textContent = message;
  }
  function reconcilePendingComments(cards) {
    let reconciled = false;
    for (const card of cards) {
      const pending = localPending[card.id] || [];
      const officialIds = new Set((card.comments || []).map(comment => comment.id));
      const remaining = pending.filter(comment => !officialIds.has(comment.id));
      if (remaining.length !== pending.length) reconciled = true;
      if (remaining.length) localPending[card.id] = remaining;
      else delete localPending[card.id];
    }
    if (reconciled) writeStore(KEYS.pending, localPending);
  }
  function applyFeed(data) {
    if (!data || !Array.isArray(data.cards)) throw new Error('Feed format is not recognized.');
    feed = data;
    interestReviewIds.clear();
    reconcilePendingComments(feed.cards);
    $('#newSignalsButton').hidden = true;
    const seen = readStore(KEYS.seen, []);
    const seenSources = new Set(readStore(KEYS.seenSources, []));
    for (const card of feed.cards) if (seenSources.has(sourceKey(card))) seen.push(card.id);
    ordered = interleaveCards(eligibleCards(feed.cards), seen, feed.calendar_mode || 'BASELINE', [], preferenceProfile(votes));
    cursor = 0;
    $('#feedMode').textContent = 'Your daily mix';
    const available = eligibleCards(feed.cards);
    $('#feedStats').innerHTML = '<div><strong>' + available.filter(card => ['SPORTS', 'NEWS'].includes(card.category)).length + '</strong>headlines</div><div><strong>' + available.filter(card => card.category === 'STORY').length + '</strong>stories</div>';
    const updated = new Date(feed.last_updated);
    $('#updatedAt').textContent = Number.isNaN(+updated) ? 'LOCAL FEED' : 'UPDATED ' + new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(updated).toUpperCase();
    renderFeed(); updateInboxCount(); renderInbox();
  }
  async function loadFeed() {
    try {
      const response = await fetch('./data/feed.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error('Feed returned HTTP ' + response.status + '.');
      applyFeed(await response.json());
      setNetwork(navigator.onLine ? '' : 'offline', navigator.onLine ? 'FEED LOADED · FIELD UNIT READY' : 'OFFLINE · CACHED FEED READY');
    } catch (error) {
      setNetwork('error', navigator.onLine ? 'FEED UNAVAILABLE · RETRYING ON RELOAD' : 'OFFLINE · NO CACHED FEED AVAILABLE');
      if (!feed) $('#cardStage').innerHTML = '<div class="empty-card"><span class="loader-mark">SF</span><p>FEED LINK UNAVAILABLE</p><span>' + esc(error.message) + ' Check your connection and reload.</span><button class="solution-toggle" id="retryFeed" type="button">RETRY FEED</button></div>';
      const retry = $('#retryFeed'); if (retry) retry.addEventListener('click', loadFeed);
    }
  }
  async function refreshReplies() {
    if (!feed || replyPollInFlight || document.hidden || !navigator.onLine) return false;
    replyPollInFlight = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      // Most polls transfer only this tiny version marker, rather than the full archive.
      try {
        const marker = await fetch('./data/feed-meta.json', {cache: 'no-cache', signal: controller.signal});
        if (marker.ok && (await marker.json()).last_updated === feed.last_updated) return true;
      } catch (_) { if (controller.signal.aborted) return false; }
      const response = await fetch('./data/feed.json', {cache: 'no-cache', signal: controller.signal});
      if (!response.ok) return false;
      const next = await response.json();
      if (!next || !Array.isArray(next.cards) || Date.parse(next.last_updated) < Date.parse(feed.last_updated)) return false;
      const previousComments = new Map(feed.cards.map(card => [card.id, JSON.stringify(getComments(card))]));
      const latestById = new Map(next.cards.map(card => [card.id, card]));
      reconcilePendingComments(next.cards);
      // Keep displayed cards and their DOM in place; only thread contents change in the background.
      feed = next;
      ordered = ordered.map(card => latestById.get(card.id) || card);
      for (const node of $$('.feed-card', $('#cardStage'))) {
        const card = latestById.get(node.dataset.cardId);
        if (!card || previousComments.get(card.id) === JSON.stringify(getComments(card))) continue;
        const comments = getComments(card);
        $('.comment-list', node).innerHTML = comments.length ? comments.map(renderComment).join('') : '<div class="source-missing">No comments yet.</div>';
        const replies = comments.filter(comment => comment.author === 'CODEX').length;
        $('.reply-count', node).textContent = comments.length + (replies ? ' · ' + replies + ' REPLIES' : '');
        hydrateMath($('.comment-list', node));
      }
      updateInboxCount(); renderInbox();
      const seen = new Set(readStore(KEYS.seen, []));
      const seenSources = new Set(readStore(KEYS.seenSources, []));
      const displayed = new Set(ordered.map(card => card.id));
      const additions = eligibleCards(next.cards).filter(card => !displayed.has(card.id) && !seen.has(card.id) && !seenSources.has(sourceKey(card))).length;
      const notice = $('#newSignalsButton');
      notice.hidden = additions === 0;
      notice.textContent = additions + ' NEW SIGNAL' + (additions === 1 ? '' : 'S') + ' - REFRESH';
      return true;
    } catch (_) {
      return false; // Keep the cached feed usable during a temporary network failure.
    } finally {
      clearTimeout(timeout); replyPollInFlight = false;
    }
  }
  function scheduleReplyPolling(refreshNow = false) {
    if (replyPollTimer !== null) { clearInterval(replyPollTimer); replyPollTimer = null; }
    if (document.hidden || !navigator.onLine) return;
    if (refreshNow) void refreshReplies();
    replyPollTimer = setInterval(refreshReplies, 300000);
  }
  window.ScrollForge.refreshReplies = refreshReplies;
  function renderInbox() {
    const root = $('#inboxList'); if (!feed) return;
    const entries = [];
    for (const card of feed.cards) for (const comment of card.comments || []) if (comment.author === 'CODEX') entries.push({ card, comment });
    entries.sort((a, b) => new Date(b.comment.created_at) - new Date(a.comment.created_at));
    root.innerHTML = entries.length ? entries.map(({ card, comment }) => {
      const unread = comment.unread && !readIds.has(comment.id);
      return '<button class="inbox-item ' + (unread ? 'unread' : '') + '" type="button" data-card-id="' + esc(card.id) + '" data-comment-id="' + esc(comment.id) + '"><div class="inbox-item-title">' + esc(card.title.replace(/^SAMPLE\s*[:—-]?\s*/i, '')) + '</div><div class="inbox-item-copy">' + esc(comment.body_markdown) + '</div><div class="inbox-item-meta">' + (unread ? 'UNREAD · ' : 'READ · ') + esc(dateLabel(comment.created_at)) + '</div></button>';
    }).join('') : '<div class="inbox-empty">No Codex replies in this feed yet. When a reply lands, it will appear here.</div>';
  }
  function openThread(cardId, commentId) {
    let node = $$('.feed-card', $('#cardStage')).find(card => card.dataset.cardId === cardId);
    if (!node) {
      const card = feed.cards.find(card => card.id === cardId); if (!card) return;
      const index = ordered.push(card) - 1;
      $('.feed-end', $('#cardStage')).insertAdjacentHTML('beforebegin', cardTemplate(card, index));
      node = $$('.feed-card', $('#cardStage')).find(card => card.dataset.cardId === cardId);
      hydrateMath(node); observeCards();
    }
    closePanel();
    node.hidden = false;
    cursor = Number(node.dataset.cardIndex);
    toggleThread($('.comment-toggle', node), true);
    node.scrollIntoView({block: 'start', behavior: 'auto'}); node.focus({preventScroll: true});
    syncPosition();
  }
  function toggleThread(button, forceOpen) {
    const cardEl = button.closest('.feed-card'); const panel = $('.card-comments', cardEl);
    const open = forceOpen == null ? !panel.classList.contains('open') : forceOpen;
    panel.classList.toggle('open', open); button.setAttribute('aria-expanded', String(open));
    if (open) { const card = feed.cards.find(c => c.id === cardEl.dataset.cardId); if (card) markThreadRead(card); hydrateMath(panel); }
  }
  function repoGuess() {
    const saved = localStorage.getItem(KEYS.repo); if (saved) return saved;
    const path = location.pathname.split('/').filter(Boolean);
    const host = location.hostname;
    if (host.endsWith('.github.io') && path.length) return host.slice(0, -10) + '/' + path[0];
    try {
      const response = fetch('./data/repo.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).then(d => {
        const repository = d && (typeof d.repository === 'string' ? d.repository : d.repo);
        if (typeof repository === 'string' && !localStorage.getItem(KEYS.repo) && !$('#repoSlug').value.trim()) {
          localStorage.setItem(KEYS.repo, repository);
          $('#repoSlug').value = repository;
        }
      }).catch(() => {});
      void response;
    } catch (_) {}
    return '';
  }
  function openSettings() {
    settingsReturnFocus = document.activeElement;
    $('#repoSlug').value = repoGuess(); $('#repoToken').value = localStorage.getItem(KEYS.token) || '';
    $('#settingsFeedback').textContent = '';
    updatePreferenceSummary();
    loadCurrentInterests();
    $('#appShell').inert = true;
    $('#scrim').hidden = false; $('#settingsModal').hidden = false; $('#settingsModal').setAttribute('aria-hidden', 'false');
    $('#repoSlug').focus();
  }
  function interestsConnection() {
    const repo = repoGuess();
    const token = localStorage.getItem(KEYS.token) || '';
    return {repo, token, url: 'https://api.github.com/repos/' + repo.split('/').map(encodeURIComponent).join('/') + '/issues',
      headers: {Accept: 'application/vnd.github+json', ...(token ? {Authorization: 'Bearer ' + token} : {}), 'Content-Type': 'application/json'}};
  }
  async function findInterestsIssue(connection) {
    for (let page = 1; ; page++) {
      const response = await fetch(connection.url + '?state=open&creator=' + encodeURIComponent(connection.repo.split('/')[0]) + '&sort=created&direction=desc&per_page=100&page=' + page, {headers: connection.headers});
      if (!response.ok) throw new Error('Cannot load shared interests (HTTP ' + response.status + ').');
      const issues = await response.json();
      for (const issue of issues) {
        if (issue.title !== 'ScrollForge current interests' || issue.pull_request) continue;
        const payload = JSON.parse(issue.body || '{}');
        if (payload.kind === 'scrollforge-interests-v1') {
          if (!Array.isArray(payload.interests) || payload.interests.some(s => typeof s !== 'string')) throw new Error('Invalid shared interests.');
          return {number: issue.number, interests: payload.interests};
        }
      }
      if (issues.length < 100) return null;
    }
  }
  async function loadCurrentInterests() {
    const input = $('#currentInterests'), button = $('#saveInterests'), feedback = $('#interestsFeedback');
    input.disabled = button.disabled = true;
    feedback.textContent = 'Loading shared interests…';
    try {
      const issue = await findInterestsIssue(interestsConnection());
      const response = issue ? null : await fetch('./data/interests.json');
      if (response && !response.ok) throw new Error('Cannot load default interests.');
      input.value = (issue ? issue.interests : await response.json()).join('\n');
      feedback.textContent = 'Loaded. Changes apply to future generated posts.';
      input.disabled = button.disabled = false;
    } catch (error) { feedback.textContent = error.message + ' Reopen Settings to retry.'; }
  }
  $('#interestsForm').addEventListener('submit', async event => {
    event.preventDefault();
    const feedback = $('#interestsFeedback'), button = $('#saveInterests');
    const interests = [...new Map($('#currentInterests').value.split('\n').map(s => s.trim()).filter(Boolean).map(s => [s.toLowerCase(), s])).values()];
    if (interests.length > 12 || interests.some(s => s.length > 160)) { feedback.textContent = 'Use up to 12 interests, each at most 160 characters.'; return; }
    const connection = interestsConnection();
    if (!connection.token) { feedback.textContent = 'Save the repository and Issues token below, then save your interests.'; return; }
    button.disabled = true;
    feedback.textContent = 'Saving shared interests…';
    try {
      const issue = await findInterestsIssue(connection);
      const response = await fetch(connection.url + (issue ? '/' + issue.number : ''), {
        method: issue ? 'PATCH' : 'POST', headers: connection.headers,
        body: JSON.stringify({title: 'ScrollForge current interests', body: JSON.stringify({kind: 'scrollforge-interests-v1', interests})})
      });
      if (!response.ok) throw new Error('GitHub could not save interests (HTTP ' + response.status + ').');
      const saved = await response.json();
      if (saved.user?.login.toLowerCase() !== connection.repo.split('/')[0].toLowerCase()) throw new Error('Use the repository owner’s token so the generator can trust this configuration.');
      feedback.textContent = interests.length ? 'Saved for the next scheduled content batch.' : 'Saved. Interest generation is paused; existing posts remain available.';
    } catch (error) { feedback.textContent = error.message; }
    finally { button.disabled = false; }
  });
  function openInbox() {
    renderInbox();
    settingsReturnFocus = document.activeElement;
    $('#appShell').inert = true;
    $('#scrim').hidden = false;
    const drawer = $('#inboxDrawer'); drawer.classList.add('open'); drawer.setAttribute('aria-hidden', 'false'); drawer.inert = false;
    $('[data-close-panel]', drawer).focus();
  }
  function closePanel() {
    $('#scrim').hidden = true;
    $('#appShell').inert = false;
    const drawer = $('#inboxDrawer'); drawer.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); drawer.inert = true;
    const modal = $('#settingsModal'); modal.hidden = true; modal.setAttribute('aria-hidden', 'true');
    if (settingsReturnFocus && settingsReturnFocus.focus) settingsReturnFocus.focus();
  }
  async function sendComment(form) {
    const cardEl = form.closest('.feed-card'); const card = feed.cards.find(c => c.id === cardEl.dataset.cardId);
    const textarea = $('textarea', form); const button = $('button[type="submit"]', form); const feedback = $('.comment-feedback', form);
    const text = textarea.value.trim();
    if (!text) return;
    const repo = (localStorage.getItem(KEYS.repo) || '').trim(); const token = localStorage.getItem(KEYS.token) || '';
    if (!repo || !token) { feedback.textContent = 'Save repository and token in Settings before sending.'; feedback.className = 'comment-feedback error'; openSettings(); return; }
    button.disabled = true; feedback.textContent = 'SENDING TO GITHUB…'; feedback.className = 'comment-feedback';
    try {
      const response = await fetch('https://api.github.com/repos/' + repo.split('/').map(encodeURIComponent).join('/') + '/issues', {
        method: 'POST', headers: { Accept: 'application/vnd.github+json', Authorization: 'Bearer ' + token, 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Comment on Card: ' + card.id, labels: ['pending-codex'], body: JSON.stringify({ card_id: card.id, course_tag: card.course_tag || null, user_comment: text }) })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.message || 'GitHub returned HTTP ' + response.status + '.');
      const number = result.number;
      const comment = { id: 'issue-' + number + '-user', author: 'USER', body_markdown: text, created_at: new Date().toISOString(), unread: false, issue_number: number, pending: true };
      localPending[card.id] = localPending[card.id] || [];
      localPending[card.id] = localPending[card.id].filter(c => c.id !== comment.id).concat(comment);
      writeStore(KEYS.pending, localPending);
      textarea.value = '';
      const receipt = 'QUEUED FOR LOCAL CODEX RUN · ISSUE #' + number;
      feedback.textContent = receipt; feedback.className = 'comment-feedback success';
      for (const node of $$('.feed-card', $('#cardStage')).filter(node => node.dataset.cardId === card.id)) {
        $('.comment-list', node).innerHTML = getComments(card).map(renderComment).join('');
        const comments = getComments(card);
        $('.reply-count', node).textContent = comments.length + (comments.some(c => c.author === 'CODEX') ? ' · ' + comments.filter(c => c.author === 'CODEX').length + ' REPLIES' : '');
        hydrateMath($('.comment-list', node));
      }
    } catch (error) {
      feedback.textContent = 'SEND FAILED: ' + error.message + ' Your draft is still here; retry when ready.'; feedback.className = 'comment-feedback error';
    } finally { button.disabled = false; }
  }
  function toggleSolution(button) {
    const panel = $('.solution-panel', button.closest('.feed-card'));
    const open = !panel.classList.contains('open'); panel.classList.toggle('open', open); button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? 'Hide answer' : 'Reveal answer'; if (open) hydrateMath(panel);
  }
  function toggleBody(button) {
    const root = button.closest('.card-body');
    const preview = $('.body-preview', root), full = $('.body-full', root);
    const expanding = full.hidden;
    preview.hidden = expanding; full.hidden = !expanding;
    button.textContent = expanding ? button.dataset.collapseLabel : button.dataset.expandLabel;
  }

  $$('[data-topic]').forEach(button => button.addEventListener('click', () => {
    activeTopic = button.dataset.topic;
    if (feed && ['chess', 'interests'].includes(activeTopic)) {
      for (const card of eligibleCards(feed.cards).filter(card => card.category === 'INTEREST')) {
        if (!ordered.some(item => item.id === card.id)) { ordered.push(card); interestReviewIds.add(card.id); }
      }
    }
    applyFilters(); window.scrollTo({top: 0});
  }));
  $('#feedSearch').addEventListener('input', () => { if (feed) applyFilters(); });
  $('#feedSort').addEventListener('change', () => { if (feed) { applyFilters(); window.scrollTo({top: 0}); } });
  $('#settingsButton').addEventListener('click', openSettings);
  $('#studyCourse').addEventListener('change', applyFilters);
  $('#newSignalsButton').addEventListener('click', () => loadFeed().then(() => window.scrollTo({top: 0})));
  $('#inboxButton').addEventListener('click', openInbox);
  $('#scrim').addEventListener('click', closePanel);
  $$('[data-close-panel]').forEach(b => b.addEventListener('click', closePanel));
  $('#settingsForm').addEventListener('submit', event => {
    event.preventDefault();
    const repo = $('#repoSlug').value.trim().replace(/^https?:\/\/github\.com\//, '').replace(/\.git$/, '').replace(/\/$/, '');
    if (!/^[^/\s]+\/[^/\s]+$/.test(repo)) { $('#settingsFeedback').textContent = 'Enter a repository as owner/name.'; return; }
    localStorage.setItem(KEYS.repo, repo);
    const token = $('#repoToken').value.trim(); if (token) localStorage.setItem(KEYS.token, token);
    $('#settingsFeedback').textContent = 'CONFIGURATION SAVED ON THIS DEVICE.';
  });
  $('#clearSettings').addEventListener('click', () => { localStorage.removeItem(KEYS.repo); localStorage.removeItem(KEYS.token); $('#repoSlug').value = ''; $('#repoToken').value = ''; $('#settingsFeedback').textContent = 'SAVED CONFIGURATION CLEARED.'; });
  function updatePreferenceSummary() {
    const profile = preferenceProfile(votes);
    const trends = Object.entries(profile).filter(([, score]) => Math.abs(score) >= 0.1).sort((a, b) => Number(a[0].startsWith('category:')) - Number(b[0].startsWith('category:')) || Math.abs(b[1]) - Math.abs(a[1])).slice(0, 8);
    $('#preferenceSummary').textContent = trends.length ? trends.map(([key, score]) => {
      const label = key.slice(key.indexOf(':') + 1);
      return (score > 0 ? 'More ' : 'Less ') + (key.startsWith('category:') ? categories[label]?.[0] || label : label);
    }).join(' · ') : 'No preferences yet. Use the arrows on posts to shape your mix.';
  }
  function remixRemaining() {
    if (!feed) return;
    const nodes = $$('.feed-card', $('#cardStage'));
    const mounted = new Set(nodes.map(node => node.dataset.cardId));
    const activeId = ordered[cursor]?.id;
    const kept = ordered.filter(card => mounted.has(card.id));
    ordered = kept.concat(interleaveCards(ordered.filter(card => !mounted.has(card.id)), [], feed.calendar_mode || 'BASELINE', kept.slice(-3), preferenceProfile(votes)));
    const indices = new Map(ordered.map((card, index) => [card.id, index]));
    for (const node of nodes) node.dataset.cardIndex = indices.get(node.dataset.cardId);
    cursor = indices.get(activeId) ?? 0;
    updateTail();
  }
  $('#resetPreferences').addEventListener('click', () => {
    votes = {}; writeStore(VOTES_KEY, votes);
    $$('.preference-button').forEach(button => button.setAttribute('aria-pressed', 'false'));
    remixRemaining(); updatePreferenceSummary();
    $('#preferenceStatus').textContent = 'Preferences reset. Upcoming posts use the default mix.';
  });
  $('#inboxList').addEventListener('click', event => { const button = event.target.closest('.inbox-item'); if (button) openThread(button.dataset.cardId, button.dataset.commentId); });
  $('#cardStage').addEventListener('click', event => {
    const preference = event.target.closest('[data-preference]');
    if (preference) {
      const node = preference.closest('.feed-card');
      const card = ordered[Number(node.dataset.cardIndex)];
      const value = Number(preference.dataset.preference);
      if (votes[card.id]?.value === value) delete votes[card.id];
      else votes[card.id] = {value, features: interestFeatures(card), at: Date.now()};
      votes = Object.fromEntries(Object.entries(votes).sort((a, b) => b[1].at - a[1].at).slice(0, 500));
      writeStore(VOTES_KEY, votes);
      $$('[data-preference]', node).forEach(button => button.setAttribute('aria-pressed', String(votes[card.id]?.value === Number(button.dataset.preference))));
      remixRemaining();
      $('#preferenceStatus').textContent = votes[card.id] ? 'Saved. Upcoming posts will reflect your interests.' : 'Preference removed.';
      return;
    }
    const reddit = event.target.closest('.reddit-toggle');
    if (reddit) { toggleReddit(reddit); return; }
    const answer = event.target.closest('[data-answer]');
    const retryQuiz = event.target.closest('.quiz-retry');
    if (answer || retryQuiz) {
      const node = (answer || retryQuiz).closest('.feed-card');
      const card = ordered[Number(node.dataset.cardIndex)];
      if (!card.quiz) return;
      if (retryQuiz) delete savedAnswers[card.id];
      else {
        const index = Number(answer.dataset.answer);
        if (!Number.isInteger(index) || index < 0 || index >= card.quiz.options.length) return;
        savedAnswers[card.id] = {index, signature: quizSignature(card)};
      }
      writeStore(KEYS.answers, savedAnswers);
      $('.quiz', node).outerHTML = quizTemplate(card);
      const solution = $('.solution-panel', node);
      if (solution) {
        solution.classList.toggle('open', !retryQuiz);
        const toggle = $('.solution-toggle', node); toggle.setAttribute('aria-expanded', String(!retryQuiz)); toggle.textContent = retryQuiz ? 'Reveal answer' : 'Hide answer';
      }
      hydrateMath(node);
      $('.quiz-feedback', node).focus({preventScroll: true});
      return;
    }
    if (event.target.closest('.load-more')) { appendPage(); return; }
    const bodyExpand = event.target.closest('.body-expand');
    if (bodyExpand) { toggleBody(bodyExpand); return; }
    if (event.target.closest('.review-engineering')) { reviewEngineering(); return; }
    if (event.target.closest('.refresh-feed')) { loadFeed().then(() => window.scrollTo({top: 0})); return; }
    const solution = event.target.closest('.solution-toggle');
    if (solution && $('.solution-panel', solution.closest('.feed-card'))) { toggleSolution(solution); return; }
    const thread = event.target.closest('.comment-toggle'); if (thread) { toggleThread(thread); return; }
    const retry = event.target.closest('#retryFeed'); if (retry) loadFeed();
  });
  window.addEventListener('message', event => {
    if (event.origin !== 'https://embed.reddit.com') return;
    const frame = $$('.reddit-preview iframe').find(node => node.contentWindow === event.source); if (!frame) return;
    try {
      const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      if (data && data.type === 'resize.embed') {
        const height = Number(data.data);
        if (Number.isFinite(height) && height >= 100 && height <= 3000) frame.height = String(height);
      }
    } catch (_) {}
  });
  $('#cardStage').addEventListener('submit', event => { if (event.target.matches('.comment-form')) { event.preventDefault(); sendComment(event.target); } });
  document.addEventListener('keydown', event => {
    const target = event.target;
    const typing = target && (target.matches('input, textarea, select') || target.isContentEditable);
    const settingsOpen = !$('#settingsModal').hidden;
    const inboxOpen = $('#inboxDrawer').classList.contains('open');
    const modalOpen = settingsOpen || inboxOpen;
    if (event.key === 'Escape' && !$('#scrim').hidden) { closePanel(); return; }
    if (modalOpen && event.key === 'Tab') {
      const panel = settingsOpen ? $('#settingsModal') : $('#inboxDrawer');
      const focusable = $$('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])', panel).filter(el => !el.hidden && el.getClientRects().length);
      if (focusable.length) {
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
      }
      return;
    }
    if (typing || modalOpen || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'j' || event.key === 'ArrowDown') { event.preventDefault(); navigate(1); }
    else if (event.key === ' ') {
      event.preventDefault();
      const card = ordered[cursor];
      const solution = card && card.solution_markdown && (challenge(card) || card.category === 'INTEREST') ? $('.solution-toggle', activeCardElement()) : null;
      if (solution) toggleSolution(solution); else navigate(1);
    }
    else if (event.key === 'k' || event.key === 'ArrowUp') { event.preventDefault(); navigate(-1); }
    else if (event.key.toLowerCase() === 'c') { event.preventDefault(); const node = activeCardElement(); const b = node && $('.comment-toggle', node); if (b) { toggleThread(b, true); $('textarea', node).focus({preventScroll: true}); } }
  });
  // Keep touch and wheel scrolling entirely native; keyboard navigation only moves the viewport.
  window.addEventListener('scroll', () => {
    if (scrollFrame !== null) return;
    scrollFrame = requestAnimationFrame(() => { scrollFrame = null; syncPosition(); });
  }, {passive: true});
  document.addEventListener('visibilitychange', () => scheduleReplyPolling(true));
  window.addEventListener('online', () => { setNetwork('', 'CONNECTION RESTORED · FIELD UNIT READY'); if (!feed) loadFeed(); scheduleReplyPolling(true); });
  window.addEventListener('offline', () => { scheduleReplyPolling(); setNetwork('offline', feed ? 'OFFLINE · CACHED FEED READY' : 'OFFLINE · NO CACHED FEED AVAILABLE'); });
  loadFeed().then(() => scheduleReplyPolling());
}());
