import './style.css';
const $ = id => document.getElementById(id);
const storageKey = 'quiet-notes-v1';
const api = window.notesAPI;
let notes = [], selected = null, filter = 'all', search = '', saveQueue = Promise.resolve(), toastTimer;
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateFormat = timestamp => new Intl.DateTimeFormat('ru-RU', {day:'numeric',month:'long',year:'numeric'}).format(new Date(timestamp));
function notify(message) { $('toast').textContent = message; $('toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.remove('show'), 2500); }
function persist() {
  const snapshot = JSON.parse(JSON.stringify(notes));
  $('save-status').innerHTML = '<i></i> Сохранение...';
  saveQueue = saveQueue.then(async () => {
    if (api) { if (!await api.save(snapshot)) throw new Error('save failed'); }
    else localStorage.setItem(storageKey, JSON.stringify(snapshot));
    $('save-status').innerHTML = '<i></i> Сохранено';
  }).catch(() => { $('save-status').textContent = 'Ошибка сохранения'; notify('Не удалось сохранить заметки'); });
}
function renderList() {
  $('count').textContent = notes.length; $('pinned-count').textContent = notes.filter(n=>n.pinned).length;
  $('all-notes').classList.toggle('active',filter==='all'); $('pinned-notes').classList.toggle('active',filter==='pinned');
  $('list-title').textContent = filter==='all' ? 'Все заметки' : 'Закреплённые';
  const visible = notes.filter(n => (filter==='all'||n.pinned) && (n.title+' '+n.body).toLowerCase().includes(search.toLowerCase())).sort((a,b)=>Number(b.pinned)-Number(a.pinned)||b.updated-a.updated);
  $('list-count').textContent = visible.length;
  $('notes-list').innerHTML = visible.length ? visible.map(n=>`<button class="note-card ${n.id===selected?'selected':''}" data-id="${escapeHtml(n.id)}"><div class="card-head"><span class="card-title">${escapeHtml(n.title.trim()||'Без названия')}</span>${n.pinned?'<span class="pin-mark">◆</span>':''}</div><div class="card-preview">${escapeHtml(n.body.trim().replace(/\s+/g,' ')||'Пока здесь пусто')}</div><div class="card-date">${dateFormat(n.updated)}</div></button>`).join('') : '<div class="list-empty">Здесь пока нет заметок.</div>';
}
function current(){return notes.find(n=>n.id===selected)}
function renderEditor(){ const n=current(); $('editor').hidden=!n; $('empty').hidden=!!n; if(!n)return; $('title').value=n.title; $('body').value=n.body; updateMeta(n); }
function updateMeta(n){ $('date').textContent = 'Изменено ' + dateFormat(n.updated); const count=n.body.trim()?n.body.trim().split(/\s+/).length:0; $('words').textContent=count+' слов'; $('pin').classList.toggle('pinned',n.pinned); $('pin').innerHTML=n.pinned?'◆ <span>Закреплено</span>':'◇ <span>Закрепить</span>'; }
function create(){ const now=Date.now(); const n={id:crypto.randomUUID(),title:'',body:'',pinned:false,created:now,updated:now}; notes.push(n); selected=n.id; filter='all'; search=''; $('search').value=''; persist(); renderList(); renderEditor(); $('title').focus(); }
function edit(){const n=current();if(!n)return;n.title=$('title').value;n.body=$('body').value;n.updated=Date.now();updateMeta(n);renderList();persist()}
['new-note','new-small','empty-new'].forEach(id=>$(id).addEventListener('click',create));
$('title').addEventListener('input',edit); $('body').addEventListener('input',edit);
$('search').addEventListener('input',e=>{search=e.target.value;renderList()});
$('notes-list').addEventListener('click',e=>{const card=e.target.closest('[data-id]');if(card){selected=card.dataset.id;renderList();renderEditor()}});
$('all-notes').addEventListener('click',()=>{filter='all';renderList()});$('pinned-notes').addEventListener('click',()=>{filter='pinned';renderList()});
$('pin').addEventListener('click',()=>{const n=current();if(!n)return;n.pinned=!n.pinned;persist();renderList();updateMeta(n)});
$('delete').addEventListener('click',()=>{const n=current();if(!n||!confirm('Удалить эту заметку? Это действие нельзя отменить.'))return;notes=notes.filter(x=>x.id!==selected);selected=notes[0]?.id||null;persist();renderList();renderEditor();notify('Заметка удалена')});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='n'){e.preventDefault();create()}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('search').focus()}});
async function init(){try{const saved=api?await api.load():JSON.parse(localStorage.getItem(storageKey)||'null');if(Array.isArray(saved))notes=saved.filter(n=>n&&typeof n.id==='string'&&typeof n.title==='string'&&typeof n.body==='string'&&Number.isFinite(n.updated));}catch{notify('Не удалось загрузить заметки')}selected=notes.sort((a,b)=>b.updated-a.updated)[0]?.id||null;renderList();renderEditor()}
init();
