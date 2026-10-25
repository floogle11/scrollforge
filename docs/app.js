(function () {
  'use strict';
  const KEYS = { seen: 'scrollforge.seen_card_ids', seenSources: 'scrollforge.seen_source_urls', read: 'scrollforge.read_comment_ids', repo: 'scrollforge.repo_slug', token: 'scrollforge.github_token', pending: 'scrollforge.pending_comments' };
  const categories = {
    SPORTS: ['NFL', '#ffac85'], NEWS: ['News', '#8bbfff'], STORY: ['Story', '#d7b0f3'],
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
  // News and stories are consumed once. Only evergreen engineering notes may act as a repeat spacer.
  function interleaveCards(cards, seenIds = [], mode = 'BASELINE', boundaryCards = []) {
    const seen = new Set(seenIds);
    const weightSets = {
      BASELINE: { sports: 35, news: 30, story: 20, current: 10, past: 5 },
      EXAM_WINDOW: { sports: 25, news: 25, story: 15, current: 30, past: 5 },
      CRUNCH_WINDOW: { sports: 25, news: 25, story: 15, current: 30, past: 5 },
      EXAM_DAY: { sports: 35, news: 30, story: 20, current: 15, past: 0 }
    };
    const weights = weightSets[mode] || weightSets.BASELINE;
    const typeOf = card => card.category === 'SPORTS' ? 'sports' : card.category === 'NEWS' ? 'news' :
      card.category === 'CHALLENGE_CURRENT' ? 'current' : card.category === 'CHALLENGE_PAST' ? 'past' : 'story';
    const unique = cards.filter((card, i) => card && card.id && cards.findIndex(item => item.id === card.id) === i);
    const pools = {sports: [], news: [], story: [], current: [], past: []};
    for (const card of shuffle(unique.filter(card => !seen.has(card.id)))) pools[typeOf(card)].push(card);
    const spacers = shuffle(unique.filter(card => card.category === 'DEEP_CUT'));
    const mixed = [];
    let spacerCursor = 0, run = 0;
    const prior = Array.isArray(boundaryCards) ? boundaryCards : [boundaryCards].filter(Boolean);
    for (let i = prior.length - 1; i >= 0 && challenge(prior[i]); i--) run++;
    while (Object.values(pools).some(pool => pool.length)) {
      if (run >= 2) {
        const leisure = pools.sports.length ? pools.sports : pools.news.length ? pools.news : pools.story;
        if (leisure.length || spacers.length) {
          mixed.push(leisure.length ? leisure.shift() : spacers[spacerCursor++ % spacers.length]);
          run = 0; continue;
        }
      }
      const active = Object.keys(pools).filter(key => pools[key].length);
      const total = active.reduce((sum, key) => sum + weights[key], 0);
      let roll = Math.random() * (total || active.length), selected = active[0];
      for (const key of active) { roll -= total ? weights[key] : 1; if (roll < 0) { selected = key; break; } }
      const card = pools[selected].shift(); mixed.push(card); run = challenge(card) ? run + 1 : 0;
    }
    return mixed;
  }
  if (typeof window !== 'undefined') window.ScrollForge = {interleaveCards, eligibleCards, freshCard};
  if (typeof module !== 'undefined' && module.exports) { module.exports = {interleaveCards, eligibleCards, freshCard}; return; }

  let feed = null;
  let ordered = [];
  let cursor = 0;
  let viewObserver = null;
  let scrollFrame = null;
  let replyPollTimer = null;
  let replyPollInFlight = false;
  let settingsReturnFocus = null;
  let activeTopic = 'all';
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
      bbc_technology: 'BBC Technology', npr: 'NPR', guardian_us: 'The Guardian', nasa: 'NASA', smithsonian: 'Smithsonian Magazine'};
    const match = String(card.id).match(/^rss_(.+)_[^_]+$/);
    const source = safeUrl(card.source_url);
    if (source) {
      const url = new URL(source);
      const subreddit = /(^|\.)reddit\.com$/.test(url.hostname) && url.pathname.match(/^\/r\/([^/]+)/i);
      if (subreddit) return 'r/' + subreddit[1];
      if (match && names[match[1]]) return names[match[1]];
      return url.hostname.replace(/^www\./, '');
    }
    return card.course_tag || (card.category === 'DEEP_CUT' ? 'Engineering' : card.category === 'STORY' ? 'Stories' : 'Your study notes');
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
  function cardTemplate(card, index) {
    const [label, accent] = categories[card.category] || ['FIELD SIGNAL', '#38BDF8'];
    const comments = getComments(card);
    const codexReplies = comments.filter(c => c.author === 'CODEX').length;
    const source = safeUrl(card.source_url);
    const sample = /^SAMPLE\b/i.test(card.title || '');
    const title = sample ? card.title.replace(/^SAMPLE\s*[:—-]?\s*/i, '') : card.title;
    const bodyText = String(card.body_markdown || '').trim();
    const bodyTokens = bodyText.split(/\s+/).filter(Boolean);
    const bodyWords = bodyTokens.length;
    const bodyContent = bodyWords > 55
      ? '<div class="body-preview">' + renderMarkdown(bodyTokens.slice(0, 55).join(' ')) + '…</div><div class="body-full" hidden>' + renderMarkdown(bodyText) + '</div><button type="button" class="body-expand" data-expand-label="Read more" data-collapse-label="Show less">Read more</button>'
      : renderMarkdown(bodyText);
    const community = communityLabel(card);
    return '<article class="feed-card" tabindex="-1" data-card-index="' + index + '" data-card-id="' + esc(card.id) + '" style="--accent:' + accent + '">' +
      '<div class="card-topline"><span class="community-avatar" aria-hidden="true">' + esc(community.replace(/^r\//, '').charAt(0).toUpperCase()) + '</span>' +
      (source ? '<a class="community-name" href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + esc(community) + '</a>' : '<span class="community-name">' + esc(community) + '</span>') +
      '<span aria-hidden="true">·</span><time class="card-time" datetime="' + esc(card.created_at) + '">' + esc(dateLabel(card.created_at)) + '</time><span class="card-course">' + esc(card.course_tag || '') + '</span></div>' +
      (sample ? '<div class="sample-marker">SAMPLE FEED · DEMONSTRATION CARD</div>' : '') +
      '<h2 class="card-title">' + (source ? '<a href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + esc(title) + '</a>' : esc(title)) + '</h2><span class="category-chip">' + label + '</span><div class="card-body">' + bodyContent + '</div>' +
      '<div class="card-footer">' +
      '<button class="comment-toggle" type="button" aria-expanded="false"><svg class="ui-icon" aria-hidden="true"><use href="#icon-comment"/></svg> Comments <span class="reply-count">' + comments.length + (codexReplies ? ' · ' + codexReplies + ' replies' : '') + '</span></button>' +
      (card.solution_markdown ? '<button class="solution-toggle" type="button" aria-expanded="false">Reveal answer</button>' : '') +
      (source ? '<a class="source-link" href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">' + (community.startsWith('r/') ? 'View on Reddit ↗' : 'Read article ↗') + '</a>' : '') +
      (sample ? '<span class="sample-label">SAMPLE</span>' : '') + '</div>' +
      (card.solution_markdown ? '<section class="solution-panel"><div class="solution-label">The worked answer</div><div class="solution-content">' + renderMarkdown(card.solution_markdown) + '</div></section>' : '') +
      '<section class="card-comments"><div class="comment-list">' + (comments.length ? comments.map(renderComment).join('') : '<div class="source-missing">Start the conversation. Ask a question or add a thought.</div>') + '</div>' +
      '<form class="comment-form"><textarea name="comment" maxlength="2000" aria-label="Your comment" placeholder="Ask a follow-up or leave a note…" required></textarea><button type="submit">SEND ↗</button><div class="comment-feedback" role="status"></div></form></section>' +
      '<span hidden data-word-count="' + bodyWords + '"></span></article>';
  }
  function endTemplate() {
    return '<section class="feed-end"><div class="eyebrow">END OF CURRENT FEED</div><h2>You\'re caught up.</h2>' +
      '<p>Fresh headlines appear after the next refresh. Engineering is here whenever you want another pass.</p>' +
      '<div class="end-actions"><button class="solution-toggle refresh-feed" type="button">REFRESH FEED</button>' +
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
    for (const node of nodes) node.toggleAttribute('data-active', Number(node.dataset.cardIndex) === cursor);
    const position = nodes.findIndex(node => Number(node.dataset.cardIndex) === cursor) + 1;
    $('#cardPosition').textContent = position + ' / ' + nodes.length;
    $('#progressBar').style.width = (position / nodes.length * 100) + '%';
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
    stage.innerHTML = ordered.map(cardTemplate).join('') + '<div class="empty-card" id="filterEmpty" hidden role="status"><p>No posts here right now. Try another topic or search.</p></div>' + endTemplate();
    hydrateMath(stage); applyFilters(); observeCards();
  }
  function applyFilters() {
    const query = $('#feedSearch').value.trim().toLocaleLowerCase();
    const matchesTopic = card => activeTopic === 'all' ||
      (activeTopic === 'sports' && card.category === 'SPORTS') ||
      (activeTopic === 'news' && card.category === 'NEWS') ||
      (activeTopic === 'stories' && card.category === 'STORY') ||
      (activeTopic === 'engineering' && (challenge(card) || card.category === 'DEEP_CUT'));
    const nodes = $$('.feed-card', $('#cardStage'));
    const newest = $('#feedSort').value === 'new';
    nodes.sort((a, b) => newest ? Date.parse(ordered[Number(b.dataset.cardIndex)].created_at) - Date.parse(ordered[Number(a.dataset.cardIndex)].created_at) || Number(a.dataset.cardIndex) - Number(b.dataset.cardIndex) : Number(a.dataset.cardIndex) - Number(b.dataset.cardIndex));
    for (const node of nodes) {
      const card = ordered[Number(node.dataset.cardIndex)];
      node.hidden = !matchesTopic(card) || ![card.title, card.body_markdown, communityLabel(card), card.course_tag || ''].join(' ').toLocaleLowerCase().includes(query);
      $('#cardStage').insertBefore(node, $('#filterEmpty'));
    }
    const visible = nodes.filter(node => !node.hidden);
    $('#filterEmpty').hidden = visible.length > 0;
    const titles = {all: 'Home', sports: 'NFL & Broncos', news: 'News', stories: 'Stories & discoveries', engineering: 'Engineering'};
    $('#feedTitle').textContent = titles[activeTopic];
    $$('[data-topic]').forEach(button => {
      const selected = button.dataset.topic === activeTopic;
      button.classList.toggle('active', selected); button.setAttribute('aria-pressed', String(selected));
    });
    syncPosition();
  }
  function activeCardElement() { return $$('.feed-card', $('#cardStage')).find(node => Number(node.dataset.cardIndex) === cursor); }
  function navigate(delta) {
    const visible = $$('.feed-card', $('#cardStage')).filter(node => !node.hidden);
    if (!visible.length) return;
    const current = visible.findIndex(node => Number(node.dataset.cardIndex) === cursor);
    cursor = Number(visible[Math.max(0, Math.min(visible.length - 1, current + delta))].dataset.cardIndex);
    const node = activeCardElement(); if (node) node.scrollIntoView({block: 'start', behavior: 'auto'});
    syncPosition();
  }
  function reviewEngineering() {
    if (!feed) return;
    activeTopic = 'engineering'; $('#feedSearch').value = '';
    ordered = interleaveCards(feed.cards.filter(card => challenge(card) || card.category === 'DEEP_CUT'), [], feed.calendar_mode || 'BASELINE');
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
    reconcilePendingComments(feed.cards);
    $('#newSignalsButton').hidden = true;
    const seen = readStore(KEYS.seen, []);
    const seenSources = new Set(readStore(KEYS.seenSources, []));
    for (const card of feed.cards) if (seenSources.has(sourceKey(card))) seen.push(card.id);
    ordered = interleaveCards(eligibleCards(feed.cards), seen, feed.calendar_mode || 'BASELINE');
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
    replyPollTimer = setInterval(refreshReplies, 60000);
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
    $('#appShell').inert = true;
    $('#scrim').hidden = false; $('#settingsModal').hidden = false; $('#settingsModal').setAttribute('aria-hidden', 'false');
    $('#repoSlug').focus();
  }
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
    activeTopic = button.dataset.topic; applyFilters(); window.scrollTo({top: 0});
  }));
  $('#feedSearch').addEventListener('input', () => { if (feed) applyFilters(); });
  $('#feedSort').addEventListener('change', () => { if (feed) { applyFilters(); window.scrollTo({top: 0}); } });
  $('#settingsButton').addEventListener('click', openSettings);
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
  $('#inboxList').addEventListener('click', event => { const button = event.target.closest('.inbox-item'); if (button) openThread(button.dataset.cardId, button.dataset.commentId); });
  $('#cardStage').addEventListener('click', event => {
    const bodyExpand = event.target.closest('.body-expand');
    if (bodyExpand) { toggleBody(bodyExpand); return; }
    if (event.target.closest('.review-engineering')) { reviewEngineering(); return; }
    if (event.target.closest('.refresh-feed')) { loadFeed().then(() => window.scrollTo({top: 0})); return; }
    const solution = event.target.closest('.solution-toggle');
    if (solution && $('.solution-panel', solution.closest('.feed-card'))) { toggleSolution(solution); return; }
    const thread = event.target.closest('.comment-toggle'); if (thread) { toggleThread(thread); return; }
    const retry = event.target.closest('#retryFeed'); if (retry) loadFeed();
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
      const solution = card && card.solution_markdown && challenge(card) ? $('.solution-toggle', activeCardElement()) : null;
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
