(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const LEVELS = {
    easy: {label:'Легко', note:'Хороший старт для разминки', clueCount:40},
    medium: {label:'Средне', note:'Пора применить исключение', clueCount:34},
    hard: {label:'Сложно', note:'Понадобятся точные заметки', clueCount:29},
    expert: {label:'Эксперт', note:'Каждая цифра имеет значение', clueCount:25}
  };
  const TEMPLATES = {
    easy: ['000421000412376890300005001740003200936200710085700000093182007000509100120047000','859421376412376895367895421741963258936258714285714963593182647674539182128647539'],
    medium: ['000600000070052030003074920300000079001297306097360008140000000500106702008500060','952613847874952631613874925365481279481297356297365418146728593539146782728539164'],
    hard: ['006800000030090000010243009003024106600000040045000370520000400000002060000438900','956871234432695817718243659873524196691387542245169378529716483384952761167438925'],
    expert: ['290080600007000002060001000085000207009030061000000800010000000000068040000094705','291587634857643912463921578385416297729835461146279853914752386572368149638194725']
  };
  const storageKey = 'iskra-sudoku-state-v2';
  const profileKey = 'iskra-sudoku-profile-v2';
  const LEVELS_ORDER = ['easy','medium','hard','expert'];
  let profile = readProfile();
  let state = readState();
  let history = [];
  let toastTimer = 0;
  let selectedNewLevel = 'easy';

  function readProfile() {
    try {
      const value = JSON.parse(localStorage.getItem(profileKey) || '{}');
      return {solved:Number(value.solved)||0, bestTimes:value.bestTimes||{}, todayDate:value.todayDate||'', todaySolved:Number(value.todaySolved)||0, nextId:Number(value.nextId)||1};
    } catch (_) { return {solved:0,bestTimes:{},todayDate:'',todaySolved:0,nextId:1}; }
  }
  function readState() {
    try {
      const s = JSON.parse(localStorage.getItem(storageKey) || 'null');
      if (!s || !Array.isArray(s.puzzle) || !Array.isArray(s.solution) || !Array.isArray(s.values) || s.puzzle.length!==81 || s.solution.length!==81 || s.values.length!==81 || !LEVELS[s.level]) return null;
      s.notes = Array.isArray(s.notes)&&s.notes.length===81 ? s.notes : Array.from({length:81},()=>[]);
      s.selected = Number.isInteger(s.selected)&&s.selected>=0&&s.selected<81 ? s.selected : 0;
      s.seconds = Math.max(0,Number(s.seconds)||0); s.mistakes = Math.max(0,Number(s.mistakes)||0); s.hints = Math.max(0,Number(s.hints)||0);
      s.completed = Boolean(s.completed); s.revealed = Boolean(s.revealed); s.noteMode = Boolean(s.noteMode);
      return s;
    } catch (_) { return null; }
  }
  function save() {
    try { localStorage.setItem(storageKey,JSON.stringify(state)); localStorage.setItem(profileKey,JSON.stringify(profile)); } catch (_) { /* Continue for private browsing modes that disable storage. */ }
  }
  function shuffle(values) {
    const a=values.slice();
    for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}
    return a;
  }
  function groupedPermutation() {
    return shuffle([0,1,2]).flatMap(group=>shuffle([0,1,2]).map(item=>group*3+item));
  }
  function transformedTemplate(level) {
    const [puzzleText,solutionText]=TEMPLATES[level];
    const sourcePuzzle=Array.from(puzzleText,Number), sourceSolution=Array.from(solutionText,Number);
    const rows=groupedPermutation(), cols=groupedPermutation(), digits=[0,...shuffle([1,2,3,4,5,6,7,8,9])];
    const transpose=Math.random()<.5;
    const puzzle=Array(81), solution=Array(81);
    for(let r=0;r<9;r++) for(let c=0;c<9;c++) {
      const oldR=transpose?cols[c]:rows[r], oldC=transpose?rows[r]:cols[c], old=oldR*9+oldC, now=r*9+c;
      puzzle[now]=digits[sourcePuzzle[old]];
      solution[now]=digits[sourceSolution[old]];
    }
    return {puzzle,solution};
  }
  function makeGame(level) {
    const grid=transformedTemplate(level), id=profile.nextId++;
    return {id,level,puzzle:grid.puzzle,solution:grid.solution,values:grid.puzzle.slice(),notes:Array.from({length:81},()=>[]),selected:grid.puzzle.findIndex(n=>n===0),seconds:0,mistakes:0,hints:0,noteMode:false,completed:false,revealed:false};
  }
  function formatTime(seconds) {
    const n=Math.max(0,Number(seconds)||0), mm=String(Math.floor(n/60)).padStart(2,'0'), ss=String(n%60).padStart(2,'0');
    return `${mm}:${ss}`;
  }
  function today() { return new Date().toISOString().slice(0,10); }
  function showToast(text) {
    const box=$('toast'); box.textContent=text; box.classList.add('visible'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>box.classList.remove('visible'),2200);
  }
  function openNewGame(level=state.level) {
    selectedNewLevel=level;
    document.querySelectorAll('.dialog-level').forEach(button=>button.classList.toggle('selected',button.dataset.newLevel===level));
    const dialog=$('new-game-dialog'); if(!dialog.open) dialog.showModal();
  }
  function startNewGame(level) {
    history=[]; state=makeGame(level); save(); renderAll();
    if($('new-game-dialog').open) $('new-game-dialog').close();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function addHistory() {
    history.push({values:state.values.slice(),notes:state.notes.map(row=>row.slice()),selected:state.selected});
    if(history.length>40)history.shift();
  }
  function undo() {
    if(state.completed){showToast('Партия уже завершена');return;}
    const last=history.pop();
    if(!last){showToast('Пока нечего отменять');return;}
    state.values=last.values;state.notes=last.notes;state.selected=last.selected;save();renderAll();
  }
  function boxIndex(index) { return Math.floor(Math.floor(index/9)/3)*3+Math.floor((index%9)/3); }
  function conflicts() {
    const bad=new Set();
    for(let i=0;i<81;i++){
      const v=state.values[i]; if(!v)continue;
      const r=Math.floor(i/9), c=i%9, b=boxIndex(i);
      for(let j=i+1;j<81;j++) if(state.values[j]===v){const rr=Math.floor(j/9),cc=j%9;if(r===rr||c===cc||b===boxIndex(j)){bad.add(i);bad.add(j);}}
    }
    return bad;
  }
  function renderBoard() {
    const board=$('sudoku-board'), bad=conflicts(), selected=state.selected, selectedValue=state.values[selected], sr=Math.floor(selected/9), sc=selected%9, sb=boxIndex(selected);
    const fragment=document.createDocumentFragment();
    for(let i=0;i<81;i++){
      const row=Math.floor(i/9),col=i%9,value=state.values[i], given=state.puzzle[i]!==0;
      const cell=document.createElement('button'); cell.type='button'; cell.className='cell'; cell.dataset.index=i; cell.setAttribute('role','gridcell'); cell.tabIndex=i===selected?0:-1;
      if(given)cell.classList.add('given');
      if(i===selected)cell.classList.add('selected');
      else if(row===sr||col===sc||boxIndex(i)===sb)cell.classList.add('related');
      if(selectedValue&&value===selectedValue&&i!==selected)cell.classList.add('same-value');
      if(bad.has(i))cell.classList.add('conflict');
      if(value&&value!==state.solution[i])cell.classList.add('error');
      const label=`Строка ${row+1}, колонка ${col+1}${given?`, исходная цифра ${value}`:value?`, введено ${value}`:', пустая'}`;
      cell.setAttribute('aria-label',label); cell.setAttribute('aria-selected',i===selected?'true':'false');
      if(value)cell.textContent=String(value);
      else if(state.notes[i]?.length){cell.classList.add('notes-cell');const notes=document.createElement('span');notes.className='notes-grid';for(let n=1;n<=9;n++){const mark=document.createElement('i');mark.textContent=state.notes[i].includes(n)?String(n):'';notes.append(mark);}cell.append(notes);}
      cell.addEventListener('click',()=>{state.selected=i;save();renderAll();});
      fragment.append(cell);
    }
    board.replaceChildren(fragment);
    const empty=state.values.filter(v=>!v).length, filled=81-empty;
    $('fill-count').textContent=`${String(filled).padStart(2,'0')} / 81`;
    $('fill-meter').style.transform=`scaleX(${filled/81})`;
    $('mistakes').textContent=state.mistakes;
    $('puzzle-id').textContent=String(state.id).padStart(3,'0');
    $('selected-coordinate').textContent=`${sr+1} / ${sc+1}`;
    $('selected-hint').textContent=state.completed?(state.revealed?'Решение открыто. Начни новую партию, чтобы сыграть ещё.':'Сетка решена. Отличная работа!'):state.puzzle[selected]?'Исходная цифра — её нельзя стереть.':state.values[selected]?'Твоя цифра. Выбери другую, если хочешь заменить её.':'Пустая клетка. Введи цифру или добавь заметку.';
    $('board-status').textContent=state.completed?(state.revealed?'Решение показано':'Сетка решена — отлично'):state.noteMode?'Режим заметок включён':'Выбери клетку и введи цифру';
    $('timer').textContent=formatTime(state.seconds);
    $('note-button').classList.toggle('active',state.noteMode);$('note-button').setAttribute('aria-pressed',String(state.noteMode));
    document.querySelectorAll('.level-button').forEach(button=>button.classList.toggle('active',button.dataset.level===state.level));
    $('level-caption').textContent=LEVELS[state.level].note;
    document.querySelectorAll('.number-button').forEach(button=>{const num=Number(button.dataset.number);const count=state.values.filter(v=>v===num).length;button.classList.toggle('disabled',count===9);button.setAttribute('aria-label',`Ввести цифру ${num}${count===9?', все цифры уже стоят':''}`);});
    $('undo-button').disabled=history.length===0||state.completed;
    $('hint-button').disabled=state.completed;
    $('note-button').disabled=state.completed;
    $('erase-button').disabled=state.completed;
    $('solve-button').disabled=state.completed;
    $('number-pad').setAttribute('aria-disabled',String(state.completed));
  }
  function renderProfile() {
    const date=today();if(profile.todayDate!==date){profile.todayDate=date;profile.todaySolved=0;save();}
    $('stat-solved').textContent=profile.solved;
    $('stat-best').textContent=profile.bestTimes[state.level]?formatTime(profile.bestTimes[state.level]):'—';
    $('stat-streak').textContent=profile.todaySolved;
  }
  function renderAll() {renderBoard();renderProfile();}
  function applyNumber(number) {
    if(state.completed)return;
    const i=state.selected;
    if(state.puzzle[i]){showToast('Эта цифра уже задана');return;}
    if(state.noteMode){
      addHistory();const notes=state.notes[i];const at=notes.indexOf(number);if(at>=0)notes.splice(at,1);else notes.push(number);notes.sort((a,b)=>a-b);save();renderAll();return;
    }
    if(state.values[i]===number){eraseSelected();return;}
    addHistory();state.values[i]=number;state.notes[i]=[];
    if(number!==state.solution[i]){state.mistakes++;showToast('Не совпало с решением — попробуй ещё раз');}
    save();renderAll();checkSolved();
  }
  function eraseSelected() {
    if(state.completed)return;
    const i=state.selected;
    if(state.puzzle[i]){showToast('Исходную цифру нельзя стереть');return;}
    if(!state.values[i]&&!state.notes[i].length){showToast('Клетка уже пустая');return;}
    addHistory();state.values[i]=0;state.notes[i]=[];save();renderAll();
  }
  function toggleNotes() {if(state.completed)return;state.noteMode=!state.noteMode;save();renderAll();if(state.noteMode)showToast('Заметки включены — выбери цифру');}
  function revealHint() {
    if(state.completed)return;
    const i=state.selected;if(state.puzzle[i]){showToast('Выбери пустую клетку');return;}
    addHistory();state.values[i]=state.solution[i];state.notes[i]=[];state.hints++;state.noteMode=false;save();renderAll();showToast('Цифра добавлена. Продолжай!');checkSolved();
  }
  function completeGame(revealed=false) {
    if(state.completed)return;
    state.completed=true;state.revealed=revealed;
    if(!revealed){
      profile.solved++;profile.todayDate=today();profile.todaySolved++;
      const previous=profile.bestTimes[state.level];if(!previous||state.seconds<previous)profile.bestTimes[state.level]=state.seconds;
    }
    save();renderAll();
    if(!revealed){$('win-time').textContent=formatTime(state.seconds);$('win-dialog').showModal();}
    else showToast('Решение судоку показано');
  }
  function checkSolved() {if(state.values.every((value,i)=>value===state.solution[i]))completeGame(false);}
  function solveGame() {if(state.completed)return;state.values=state.solution.slice();state.notes=Array.from({length:81},()=>[]);state.noteMode=false;completeGame(true);}
  function moveSelection(dr,dc) {
    const row=Math.floor(state.selected/9),col=state.selected%9;
    state.selected=Math.max(0,Math.min(8,row+dr))*9+Math.max(0,Math.min(8,col+dc));save();renderAll();
  }
  function chooseNextEditable(direction=1) {
    let i=state.selected;
    for(let step=0;step<81;step++){i=(i+direction+81)%81;if(!state.puzzle[i]){state.selected=i;break;}}
    save();renderAll();
  }
  function handleKey(event) {
    if(event.key==='Escape')return;
    if($('new-game-dialog').open||$('solve-dialog').open||$('win-dialog').open)return;
    if(/^[1-9]$/.test(event.key)){event.preventDefault();applyNumber(Number(event.key));return;}
    if(event.key==='ArrowUp'){event.preventDefault();moveSelection(-1,0);return;}
    if(event.key==='ArrowDown'){event.preventDefault();moveSelection(1,0);return;}
    if(event.key==='ArrowLeft'){event.preventDefault();moveSelection(0,-1);return;}
    if(event.key==='ArrowRight'){event.preventDefault();moveSelection(0,1);return;}
    if(event.key==='Backspace'||event.key==='Delete'){event.preventDefault();eraseSelected();return;}
    if(event.key.toLowerCase()==='n'){event.preventDefault();toggleNotes();return;}
    if(event.key.toLowerCase()==='u'||(event.ctrlKey&&event.key.toLowerCase()==='z')){event.preventDefault();undo();}
  }

  if(!state){state=makeGame('easy');save();}
  renderAll();
  document.querySelectorAll('.number-button').forEach(button=>button.addEventListener('click',()=>applyNumber(Number(button.dataset.number))));
  document.querySelectorAll('.level-button').forEach(button=>button.addEventListener('click',()=>openNewGame(button.dataset.level)));
  document.querySelectorAll('.dialog-level').forEach(button=>button.addEventListener('click',()=>{selectedNewLevel=button.dataset.newLevel;document.querySelectorAll('.dialog-level').forEach(b=>b.classList.toggle('selected',b===button));}));
  $('new-game-top').addEventListener('click',()=>openNewGame(state.level));
  $('start-new-game').addEventListener('click',()=>startNewGame(selectedNewLevel));
  $('win-new-game').addEventListener('click',()=>{$('win-dialog').close();openNewGame(state.level);});
  $('note-button').addEventListener('click',toggleNotes);
  $('hint-button').addEventListener('click',revealHint);
  $('erase-button').addEventListener('click',eraseSelected);
  $('undo-button').addEventListener('click',undo);
  $('solve-button').addEventListener('click',()=>{if(!state.completed)$('solve-dialog').showModal();});
  $('confirm-solve').addEventListener('click',()=>{$('solve-dialog').close();solveGame();});
  document.addEventListener('keydown',handleKey);
  setInterval(()=>{if(!state.completed){state.seconds++;$('timer').textContent=formatTime(state.seconds);save();}},1000);
})();
