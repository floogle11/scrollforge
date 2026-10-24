(function () {
  'use strict';
  const KEYS = { seen: 'scrollforge.seen_card_ids', read: 'scrollforge.read_comment_ids', repo: 'scrollforge.repo_slug', token: 'scrollforge.github_token', pending: 'scrollforge.pending_comments' };
  const categories = {
    SPORTS: ['SPORTS / NFL', '#FB4F14'], NEWS: ['NEWS / SIGNAL', '#FB4F14'], STORY: ['FIELD STORY', '#38BDF8'],
    CHALLENGE_CURRENT: ['CURRENT CHALLENGE', '#E5A93C'], CHALLENGE_PAST: ['PAST CHALLENGE', '#E5A93C'], DEEP_CUT: ['ENGINEERING DEEP CUT', '#38BDF8']
  };
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const readStore = (key, fallback) => { try { const v = JSON.parse(localStorage.getItem(key)); return v == null ? fallback : v; } catch (_) { return fallback; } };
  const writeStore = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };
  const challenge = card => /^CHALLENGE_/.test(card.category || '');
  const shuffle = list => { const a = list.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

  // Stable export for lightweight browser/Node contract checks.
  function interleaveCards(cards, seenIds = [], mode = 'BASELINE', boundaryCards = []) {
    const seen = new Set(seenIds);
    const weightSets = {
      BASELINE: { sports: 30, story: 20, current: 30, past: 20 },
      EXAM_WINDOW: { sports: 20, story: 15, current: 55, past: 10 },
      CRUNCH_WINDOW: { sports: 25, story: 15, current: 55, past: 5 },
      EXAM_DAY: { sports: 50, story: 35, current: 15, past: 0 }
    };
    const weights = weightSets[mode] || weightSets.BASELINE;
    const unseen = shuffle(cards.filter(c => c && c.id && !seen.has(c.id)));
    const leisure = card => !challenge(card);
    const typeOf = card => {
      if (card.category === 'SPORTS' || card.category === 'NEWS') return 'sports';
      if (card.category === 'CHALLENGE_CURRENT') return 'current';
      if (card.category === 'CHALLENGE_PAST') return 'past';
      return 'story'; // STORY and DEEP_CUT share the leisure/story allocation.
    };
    const pools = {
      sports: shuffle(unseen.filter(c => typeOf(c) === 'sports')),
      story: shuffle(unseen.filter(c => typeOf(c) === 'story')),
      current: shuffle(unseen.filter(c => typeOf(c) === 'current')),
      past: shuffle(unseen.filter(c => typeOf(c) === 'past'))
    };
    const repeatableLeisure = shuffle(cards.filter(c => c && c.id && seen.has(c.id) && leisure(c)));
    let leisureRepeatIndex = 0;
    const mixed = [];
    const prior = Array.isArray(boundaryCards) ? boundaryCards : (boundaryCards ? [boundaryCards] : []);
    let run = 0;
    for (let i = prior.length - 1; i >= 0 && challenge(prior[i]); i--) run++;
    while (Object.values(pools).some(pool => pool.length)) {
      const leisureAvailable = pools.sports.length + pools.story.length > 0;
      if (run >= 2 && (leisureAvailable || repeatableLeisure.length)) {
        let card;
        if (leisureAvailable) {
          const pool = pools.sports.length ? pools.sports : pools.story;
          card = pool.shift();
        } else {
          // A repeated seen leisure card is an explicit spacer when challenges outlast leisure.
          card = repeatableLeisure[leisureRepeatIndex++ % repeatableLeisure.length];
        }
        mixed.push(card);
        if (!repeatableLeisure.some(item => item.id === card.id)) repeatableLeisure.push(card);
        run = 0;
        continue;
      }
      const active = Object.keys(pools).filter(key => pools[key].length);
      let total = active.reduce((sum, key) => sum + weights[key], 0);
      const equalWeights = total === 0;
      if (equalWeights) total = active.length;
      let roll = Math.random() * total;
      let selected = active[0];
      for (const key of active) {
        roll -= equalWeights ? 1 : weights[key];
        if (roll < 0) { selected = key; break; }
      }
      const card = pools[selected].shift();
      mixed.push(card);
      if (leisure(card) && !repeatableLeisure.some(item => item.id === card.id)) repeatableLeisure.push(card);
      run = challenge(card) ? run + 1 : 0;
    }
    return mixed;
  }
  if (typeof window !== 'undefined') {
    window.ScrollForge = window.ScrollForge || {};
    window.ScrollForge.interleaveCards = interleaveCards;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { interleaveCards };
    return;
  }

  let feed = null;
  let ordered = [];
  let cursor = 0;
  let settingsReturnFocus = null;
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
    if (Number.isNaN(+date)) return 'FIELD NOTE';
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date).toUpperCase();
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
    return '<article class="comment-item ' + (isCodex ? 'codex' : '') + '" data-comment-id="' + esc(comment.id) + '"><div class="comment-meta">' + (isCodex ? 'CODEX REPLY' : 'YOU') + (pending ? '<span class="pending-tag">QUEUED FOR NEXT RUN</span>' : '') + ' · ' + esc(dateLabel(comment.created_at)) + '</div><div class="comment-body">' + renderMarkdown(comment.body_markdown) + '</div></article>';
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
    const bodyContent = bodyWords > 75
      ? '<div class="body-preview">' + renderMarkdown(bodyTokens.slice(0, 75).join(' ')) + '…</div><div class="body-full" hidden>' + renderMarkdown(bodyText) + '</div><button type="button" class="body-expand" data-expand-label="' + (card.category === 'STORY' ? '＋ EXPAND STORY' : '＋ READ FULL SIGNAL') + '" data-collapse-label="' + (card.category === 'STORY' ? '− COLLAPSE STORY' : '− COLLAPSE SIGNAL') + '">' + (card.category === 'STORY' ? '＋ EXPAND STORY' : '＋ READ FULL SIGNAL') + '</button>'
      : renderMarkdown(bodyText);
    return '<article class="feed-card" data-card-id="' + esc(card.id) + '" style="--accent:' + accent + '">' +
      '<div class="card-topline"><span class="category-chip">' + label + '</span><span class="card-course">' + esc(card.course_tag || 'OPEN CHANNEL') + '</span><span class="card-time">' + esc(dateLabel(card.created_at)) + '</span></div>' +
      (sample ? '<div class="sample-marker">SAMPLE FEED · DEMONSTRATION CARD</div>' : '') +
      '<h2 class="card-title">' + esc(title) + '</h2><div class="card-body">' + bodyContent + '</div>' +
      '<div class="card-footer">' + (source ? '<a class="source-link" href="' + esc(source) + '" target="_blank" rel="noopener noreferrer">↗ OPEN SOURCE</a>' : '<span class="source-missing">FIELD SIGNAL</span>') +
      (card.solution_markdown ? '<button class="solution-toggle" type="button" aria-expanded="false">＋ REVEAL SOLUTION</button>' : '') +
      '<button class="comment-toggle" type="button" aria-expanded="false">↳ THREAD <span class="reply-count">' + comments.length + (codexReplies ? ' · ' + codexReplies + ' REPLIES' : '') + '</span></button>' +
      (sample ? '<span class="sample-label">SAMPLE</span>' : '') + '</div>' +
      (card.solution_markdown ? '<section class="solution-panel"><div class="solution-label">SOLUTION / CHECK YOUR MODEL</div><div class="solution-content">' + renderMarkdown(card.solution_markdown) + '</div></section>' : '') +
      '<section class="card-comments"><div class="comment-list">' + (comments.length ? comments.map(renderComment).join('') : '<div class="source-missing">No comments yet. Open the channel with a question.</div>') + '</div>' +
      '<form class="comment-form"><textarea name="comment" maxlength="2000" aria-label="Your comment" placeholder="Ask a follow-up or leave a note…" required></textarea><button type="submit">SEND ↗</button><div class="comment-feedback" role="status"></div></form></section>' +
      '<span hidden data-word-count="' + bodyWords + '"></span></article>';
  }
  function renderCurrent() {
    const stage = $('#cardStage');
    if (!ordered.length) {
      stage.innerHTML = '<div class="empty-card"><span class="loader-mark">SF</span><p>NO UNSEEN SIGNALS</p><span>YOU HAVE REACHED THE END OF THE FEED.</span>' + (feed && feed.cards.length ? '<button class="solution-toggle replay-feed" type="button">↻ REPLAY FEED</button>' : '') + '</div>';
      $('#cardPosition').textContent = '00 / 00'; $('#progressBar').style.width = '100%';
      $('#prevButton').disabled = !feed || feed.cards.length < 1; $('#nextButton').disabled = true;
      return;
    }
    cursor = Math.max(0, Math.min(cursor, ordered.length - 1));
    const card = ordered[cursor];
    stage.innerHTML = cardTemplate(card, cursor);
    hydrateMath(stage);
    $('#cardPosition').textContent = String(cursor + 1).padStart(2, '0') + ' / ' + String(ordered.length).padStart(2, '0');
    $('#progressBar').style.width = ((cursor + 1) / ordered.length * 100) + '%';
    $('#prevButton').disabled = cursor <= 0;
    $('#nextButton').disabled = false;
    const seen = new Set(readStore(KEYS.seen, [])); seen.add(card.id); writeStore(KEYS.seen, Array.from(seen));
    $('#nextButton').textContent = cursor >= ordered.length - 1 ? 'REPLAY FEED  ↻' : 'NEXT SIGNAL  →';
    $('#nextButton').setAttribute('aria-label', cursor >= ordered.length - 1 ? 'Replay feed' : 'Next card');
  }
  function navigate(delta) {
    if (!ordered.length) return;
    const next = cursor + delta;
    if (next < 0) {
      const seen = new Set(readStore(KEYS.seen, []));
      const previous = interleaveCards(feed.cards, Array.from(seen)).find(c => c.id !== ordered[cursor].id);
      if (!previous) return;
      const original = ordered; ordered = [previous].concat(original); cursor = 0;
    } else if (next >= ordered.length) {
      // Pull fresh unseen cards as the user reaches the current queue's end.
      const seen = new Set(readStore(KEYS.seen, []));
      const extra = interleaveCards(feed.cards, Array.from(seen), feed.calendar_mode || 'BASELINE', ordered.slice(Math.max(0, cursor - 1), cursor + 1));
      if (!extra.length) { replayFeed(); return; }
      ordered = ordered.concat(extra); cursor = ordered.length - extra.length;
    } else cursor = next;
    renderCurrent();
  }
  function replayFeed() {
    if (!feed) return;
    writeStore(KEYS.seen, []);
    ordered = interleaveCards(feed.cards, [], feed.calendar_mode || 'BASELINE');
    cursor = 0;
    renderCurrent();
  }
  function setNetwork(mode, message) {
    const el = $('#networkStatus'); el.className = 'network-status' + (mode ? ' ' + mode : ''); $('#networkText').textContent = message;
  }
  function applyFeed(data) {
    if (!data || !Array.isArray(data.cards)) throw new Error('Feed format is not recognized.');
    feed = data;
    let reconciled = false;
    for (const card of feed.cards) {
      const pending = localPending[card.id] || [];
      const officialIds = new Set((card.comments || []).map(comment => comment.id));
      const remaining = pending.filter(comment => !officialIds.has(comment.id));
      if (remaining.length !== pending.length) reconciled = true;
      if (remaining.length) localPending[card.id] = remaining;
      else delete localPending[card.id];
    }
    if (reconciled) writeStore(KEYS.pending, localPending);
    const seen = readStore(KEYS.seen, []);
    ordered = interleaveCards(feed.cards, seen, feed.calendar_mode || 'BASELINE');
    cursor = 0;
    $('#feedMode').textContent = String(feed.calendar_mode || 'FIELD MODE').replaceAll('_', ' ');
    const updated = new Date(feed.last_updated);
    $('#updatedAt').textContent = Number.isNaN(+updated) ? 'LOCAL FEED' : 'UPDATED ' + new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(updated).toUpperCase();
    renderCurrent(); updateInboxCount(); renderInbox();
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
    const index = ordered.findIndex(c => c.id === cardId);
    if (index >= 0) cursor = index;
    else {
      const card = feed.cards.find(c => c.id === cardId);
      if (card) { ordered = [card].concat(ordered.filter(c => c.id !== cardId)); cursor = 0; }
    }
    renderCurrent();
    const button = $('.comment-toggle', $('#cardStage'));
    if (button) { toggleThread(button, true); }
    if (commentId) setTimeout(() => { const item = $$('.comment-item', $('#cardStage')).find(el => el.dataset.commentId === commentId); if (item) item.scrollIntoView({ block: 'center' }); }, 50);
    closePanel();
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
      const receipt = 'QUEUED FOR NEXT CODEX RUN · ISSUE #' + number;
      feedback.textContent = receipt; feedback.className = 'comment-feedback success';
      renderCurrent();
      const threadButton = $('.comment-toggle', $('#cardStage')); if (threadButton) toggleThread(threadButton, true);
      const freshFeedback = $('.comment-feedback', $('#cardStage'));
      if (freshFeedback) { freshFeedback.textContent = receipt; freshFeedback.className = 'comment-feedback success'; }
    } catch (error) {
      feedback.textContent = 'SEND FAILED: ' + error.message + ' Your draft is still here; retry when ready.'; feedback.className = 'comment-feedback error';
    } finally { button.disabled = false; }
  }
  function toggleSolution(button) {
    const panel = $('.solution-panel', button.closest('.feed-card'));
    const open = !panel.classList.contains('open'); panel.classList.toggle('open', open); button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? '− HIDE SOLUTION' : '＋ REVEAL SOLUTION'; if (open) hydrateMath(panel);
  }
  function toggleBody(button) {
    const root = button.closest('.card-body');
    const preview = $('.body-preview', root), full = $('.body-full', root);
    const expanding = full.hidden;
    preview.hidden = expanding; full.hidden = !expanding;
    button.textContent = expanding ? button.dataset.collapseLabel : button.dataset.expandLabel;
  }

  $('#nextButton').addEventListener('click', () => navigate(1));
  $('#prevButton').addEventListener('click', () => navigate(-1));
  $('#settingsButton').addEventListener('click', openSettings);
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
    const replay = event.target.closest('.replay-feed');
    if (replay) { replayFeed(); return; }
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
      const solution = card && card.solution_markdown && challenge(card) ? $('.solution-toggle', $('#cardStage')) : null;
      if (solution) toggleSolution(solution); else navigate(1);
    }
    else if (event.key === 'k' || event.key === 'ArrowUp') { event.preventDefault(); navigate(-1); }
    else if (event.key.toLowerCase() === 'c') { event.preventDefault(); const b = $('.comment-toggle', $('#cardStage')); if (b) toggleThread(b); }
  });
  let touchX = null, touchY = null;
  $('#cardStage').addEventListener('touchstart', event => {
    const target = event.target;
    const expandedText = target.closest('.comment-list, .comment-form, .body-full:not([hidden]), .solution-panel.open');
    const inputTarget = target.closest('input, textarea, select, [contenteditable="true"]');
    const modalOpen = !$('#settingsModal').hidden || $('#inboxDrawer').classList.contains('open');
    if (event.touches.length !== 1 || inputTarget || expandedText || modalOpen) { touchX = touchY = null; return; }
    touchX = event.touches[0].clientX; touchY = event.touches[0].clientY;
  }, { passive: true });
  $('#cardStage').addEventListener('touchend', event => {
    if (touchX == null || !event.changedTouches.length) return;
    const dx = event.changedTouches[0].clientX - touchX, dy = event.changedTouches[0].clientY - touchY;
    touchX = touchY = null;
    const modalOpen = !$('#settingsModal').hidden || $('#inboxDrawer').classList.contains('open');
    if (modalOpen) return;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.2) navigate(dx < 0 ? 1 : -1);
    else if (Math.abs(dy) > 60 && Math.abs(dy) > Math.abs(dx) * 1.2) navigate(dy < 0 ? 1 : -1);
  }, { passive: true });
  window.addEventListener('online', () => { setNetwork('', 'CONNECTION RESTORED · FIELD UNIT READY'); if (!feed) loadFeed(); });
  window.addEventListener('offline', () => setNetwork('offline', feed ? 'OFFLINE · CACHED FEED READY' : 'OFFLINE · NO CACHED FEED AVAILABLE'));
  loadFeed();
}());
