// 群消息待办整理 Agent —— 前端（原生 JS，无框架）
const $ = (s) => document.querySelector(s);
const input = $('#input');
const list = $('#list');
const stats = $('#stats');
const btnRun = $('#btnRun');
const dot = $('#dot');
const statusText = $('#statusText');

const SAMPLE = `2026年11月23日 09:12
@所有人 第48届世界技能大赛将于11月26日至30日在中国上海举办，欢迎学生报名观赛。
完成时间：学生11月25日中午12:00前完成注册预约并提交。

2026年11月23日 10:04
明天13:00-14:00在小程序订过书的来教学楼领书

2026年11月23日 10:10
哈哈哈哈笑死我了

2026年11月23日 11:02
@所有人 移动应用课程作业老师已经发在iclass了，11.28晚12点之前交给我`;

const BUCKET_CLASS = {
  '已过期': 'expired', '今天': 'today', '三天内': 'soon',
  '一周内': 'week', '更晚': 'later', '未知': 'unknown'
};

function setStatus(kind, text) {
  dot.className = 'dot' + (kind ? ' ' + kind : '');
  statusText.textContent = text;
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}

function render(items, meta) {
  list.innerHTML = '';
  if (!items.length) {
    const e = el('div', 'empty');
    e.innerHTML = '<div class="empty-icon">✅</div><p>没有识别到待办。可能是纯聊天或通知，也可能是需要人工复核的边界消息。</p>';
    list.appendChild(e);
    return;
  }
  for (const it of items) {
    const card = el('div', 'card' + (it.need_review ? ' review' : ''));
    card.dataset.bucket = it.bucket;

    const top = el('div', 'card-top');
    const cb = el('input', 'check');
    cb.type = 'checkbox';
    cb.addEventListener('change', () => card.classList.toggle('done', cb.checked));

    const task = el('div', 'task', it.task);
    task.contentEditable = 'true';
    task.spellcheck = false;

    const badge = el('span', 'badge ' + (BUCKET_CLASS[it.bucket] || 'unknown'), it.bucket);
    top.append(cb, task, badge);

    const meta2 = el('div', 'card-meta');
    meta2.append(el('span', 'tag', it.category));

    const due = el('span', 'due');
    const b = el('b', null, it.due_text || '未提及时间');
    due.append('截止：', b);
    if (it.due_iso) due.append(el('span', 'norm', '→ ' + it.due_iso.replace('T', ' ')));
    meta2.append(due);

    const conf = it.clf_prob == null ? 0 : it.clf_prob;
    const bar = el('span', 'bar');
    const fill = el('i');
    fill.style.width = Math.round(conf * 100) + '%';
    bar.appendChild(fill);
    meta2.append(el('span', null, '置信 ' + conf.toFixed(2)), bar);

    if (it.need_review) meta2.append(el('span', 'review-flag', '⚠ 建议人工确认'));
    card.append(top, meta2);

    if (it.source_text) {
      const d = document.createElement('details');
      d.className = 'source';
      const s = document.createElement('summary');
      s.textContent = '查看原文';
      const p = el('p', null, it.source_text);
      d.append(s, p);
      card.appendChild(d);
    }
    list.appendChild(card);
  }
}

function renderStats(meta) {
  stats.innerHTML = '';
  const add = (cls, html) => {
    const c = el('span', 'chip' + (cls ? ' ' + cls : ''));
    c.innerHTML = html;
    stats.appendChild(c);
  };
  add('', `消息 <b>${meta.messages}</b> 条`);
  add('', `待办 <b>${meta.todos}</b> 条`);
  add(meta.review_count ? 'warn' : 'muted', `需复核 <b>${meta.review_count}</b> 条`);
  add('muted', `耗时 <b>${(meta.elapsed_ms / 1000).toFixed(1)}s</b>`);
  $('#footStat').textContent = `最近一次：${meta.messages} 条消息 / ${meta.todos} 条待办`;
}

async function run() {
  const text = input.value.trim();
  if (!text) { input.focus(); return; }
  btnRun.disabled = true;
  btnRun.innerHTML = '<span class="spinner"></span>分析中';
  setStatus('busy', '处理中…');
  const t0 = performance.now();
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '请求失败');
    render(data.items, data);
    renderStats(data);
    setStatus('', `完成 · ${((performance.now() - t0) / 1000).toFixed(1)}s`);
  } catch (e) {
    const offline = /Failed to fetch|NetworkError|Load failed|fetch/i.test(e.message);
    setStatus('err', offline ? '服务未连接' : '出错：' + e.message);
    list.innerHTML = offline
      ? '<div class="empty"><div class="empty-icon">🔌</div><p><b>连不上本地服务</b><br>'
        + '这个页面只是外壳，真正的分析逻辑在后台的 Python 进程里。<br>'
        + '请双击项目根目录的 <code>启动.bat</code>，看到「服务已启动」后刷新本页。</p></div>'
      : `<div class="empty"><div class="empty-icon">⚠️</div><p>${e.message}</p></div>`;
  } finally {
    btnRun.disabled = false;
    btnRun.textContent = '开始分析';
  }
}

async function exportFile(fmt) {
  const cards = [...list.querySelectorAll('.card')];
  if (!cards.length) return;
  const items = cards.map((card) => ({
    task: card.querySelector('.task').textContent.trim(),
    due_text: (card.querySelector('.due b') || {}).textContent || '',
    due_iso: (card.querySelector('.norm') || {}).textContent || '',
    category: (card.querySelector('.tag') || {}).textContent || '',
    bucket: (card.querySelector('.badge') || {}).textContent || '',
    need_review: card.classList.contains('review'),
    source_text: (card.querySelector('details p') || {}).textContent || ''
  }));
  setStatus('busy', '导出中…');
  const res = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items, fmt })
  });
  if (!res.ok) { setStatus('err', '导出失败'); return; }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = fmt === 'docx' ? '待办清单.docx' : '待办清单.xlsx';
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus('', '已导出');
}

btnRun.addEventListener('click', run);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) run();
});
$('#btnSample').addEventListener('click', () => { input.value = SAMPLE; input.focus(); });
$('#btnClear').addEventListener('click', () => {
  input.value = '';
  list.innerHTML = '<div class="empty"><div class="empty-icon">🗂️</div><p>左侧粘贴消息，点「开始分析」</p></div>';
  stats.innerHTML = '';
  setStatus('', '就绪');
});
$('#btnXlsx').addEventListener('click', () => exportFile('xlsx'));
$('#btnDocx').addEventListener('click', () => exportFile('docx'));

fetch('/api/health').then((r) => r.json())
  .then(() => setStatus('', '就绪 · 模型已加载'))
  .catch(() => {
    setStatus('err', '服务未连接 · 请双击 启动.bat');
    if (!list.querySelector('.card')) {
      list.innerHTML = '<div class="empty"><div class="empty-icon">🔌</div><p><b>后台服务没有运行</b><br>'
        + '双击项目根目录的 <code>启动.bat</code>，再刷新本页即可。</p></div>';
    }
  });

// ?auto=1：用于截图/录屏演示，自动填入示例并分析
if (new URLSearchParams(location.search).has('auto')) {
  input.value = SAMPLE;
  setTimeout(run, 300);
}
