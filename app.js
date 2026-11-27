(() => {
  const $ = (id) => document.getElementById(id);
  const screens = { home: $('home-screen'), game: $('game-screen'), result: $('result-screen') };
  const difficultyNames = { easy: 'РАЗМИНКА', medium: 'ВПОЛНЕ СИЛЬНО', hard: 'ДЛЯ МАСТЕРОВ' };
  const difficultyNotes = { easy: 'Для разминки', medium: 'Самое время подумать', hard: 'Брось себе вызов' };
  let difficulty = 'easy';
  let puzzles = [];
  let index = 0;
  let results = [];
  let answered = false;
  let currentHint = 0;
  let seriesNumber = Number(localStorage.getItem('iskra-series') || 0);
  let soundOn = false;
  const stats = JSON.parse(localStorage.getItem('iskra-stats') || '{"solved":0,"best":0}');
  const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
  const pick = (items) => items[Math.floor(Math.random() * items.length)];
  const int = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
  const escapeHtml = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clean = (value) => String(value ?? '').trim().toLocaleUpperCase('ru-RU').replaceAll('Ё','Е').replace(/[\s.,!?;:]+/g, '');
  const seriesLabel = () => String(seriesNumber).padStart(3, '0');
  const formatNumber = (n) => Number.isInteger(n) ? String(n) : String(Number(n.toFixed(2))).replace('.', ',');

  function showScreen(name) {
    Object.entries(screens).forEach(([key, screen]) => screen.classList.toggle('hidden', key !== name));
    window.scrollTo({top: 0, behavior: 'smooth'});
  }

  function makePuzzles() {
    const list = [];
    const add = (p) => list.push(p);
    // 1 — Алгебра
    {
      const limit = difficulty === 'easy' ? 12 : difficulty === 'medium' ? 30 : 65;
      const x = int(3, limit), a = int(2, difficulty === 'easy' ? 12 : 24);
      const op = pick(['+', '−']);
      const rhs = op === '+' ? x + a : x - a;
      add({type:'number', icon:'x', category:'АЛГЕБРА', title:'Найди неизвестное', prompt:`Какое число скрывается за x?\n\nx ${op} ${a} = ${rhs}`, answer:String(x), hint:'Сделай обратное действие: перенеси известное число через знак равенства.', explanation:`Чтобы оставить x, выполняем обратное действие: ${op === '+' ? `${rhs} − ${a}` : `${rhs} + ${a}`} = ${x}.`, suffix:'x ='});
    }
    // 2 — Числовая последовательность
    {
      let start, step, values;
      if (difficulty === 'hard' && Math.random() > .45) {
        start = int(2, 5); step = pick([2,3,4]); values = Array.from({length:5},(_,i)=>start*step**i);
      } else {
        step = int(difficulty === 'easy' ? 2 : 3, difficulty === 'easy' ? 8 : 14) * (Math.random() < .3 ? -1 : 1);
        start = int(difficulty === 'easy' ? 2 : 8, difficulty === 'easy' ? 20 : 50);
        values = Array.from({length:5},(_,i)=>start+i*step);
      }
      const delta = values[1] - values[0];
      const answer = values[4] + (difficulty === 'hard' && values[1] / values[0] === step ? values[4] * (step - 1) : delta);
      const geometric = difficulty === 'hard' && values[1] / values[0] === step;
      add({type:'number', icon:'…', category:'ЧИСЛОВОЙ РЯД', title:'Продолжи ряд', prompt:'Найди закономерность и впиши следующее число.', visual:values.join('   ')+'   ?', answer:String(answer), hint:geometric ? 'Каждое число умножается на одно и то же число.' : `Посчитай разницу между соседними числами: она каждый раз ${delta < 0 ? 'одинаково уменьшается' : 'одинакова'}.`, explanation:geometric ? `Каждый раз умножаем на ${step}: ${values[4]} × ${step} = ${answer}.` : `Шаг ряда равен ${delta}. Прибавляем его ещё раз: ${values[4]} + (${delta}) = ${answer}.`});
    }
    // 3 — Анаграмма
    {
      const words = difficulty === 'easy' ? ['РАДУГА','КОМЕТА','КАРТИНА','ПИРОГИ','РОМАШКА','ЗАМОК'] : difficulty === 'medium' ? ['ГОРИЗОНТ','КАЛЕНДАРЬ','ПРИКЛЮЧЕНИЕ','МУЗЫКАНТ','ЗАГАДКА','ПУТЕШЕСТВИЕ'] : ['ВООБРАЖЕНИЕ','РАССУЖДЕНИЕ','ПРОСТРАНСТВО','СОЗВЕЗДИЕ','НЕОЖИДАННОСТЬ','ПЕРСПЕКТИВА'];
      const answer = pick(words); let scrambled = answer.split('');
      for(let i=0;i<10 && scrambled.join('')===answer;i++) scrambled.sort(()=>Math.random()-.5);
      if(scrambled.join('')===answer) scrambled.reverse();
      add({type:'text', icon:'↗', category:'СЛОВА', title:'Буквы перепутались', prompt:'Собери из букв существительное. Каждая буква используется один раз.', visual:scrambled.join(' · '), answer, hint:`В слове ${answer.length} букв. Попробуй сначала найти знакомый слог.`, explanation:`Буквы складываются в слово «${answer}».`, placeholder:'Впиши слово'});
    }
    // 4 — Судоку 4×4
    {
      const nums = [1,2,3,4].sort(()=>Math.random()-.5);
      let grid = Array.from({length:4},(_,r)=>Array.from({length:4},(_,c)=>nums[(r*2+Math.floor(r/2)+c)%4]));
      if(Math.random()>.5) grid = grid.map(row=>[...row].reverse());
      if(Math.random()>.5) grid = [grid[1],grid[0],grid[3],grid[2]];
      const keep = difficulty==='easy'?10:difficulty==='medium'?7:5;
      const positions = Array.from({length:16},(_,i)=>i).sort(()=>Math.random()-.5);
      const given = Array.from({length:4},(_,r)=>Array.from({length:4},(_,c)=>grid[r][c]));
      positions.slice(0,16-keep).forEach(i=>given[Math.floor(i/4)][i%4]=0);
      add({type:'sudoku', icon:'▦', category:'СУДОКУ', title:'Заполни квадраты', prompt:'В каждой строке, колонке и квадрате 2 × 2 должны быть числа от 1 до 4 — без повторов.', given, solution:grid, hint:'Начни со строки или квадрата, где уже стоят три числа. В каждой ячейке может быть только один вариант.', explanation:'Проверь, чтобы цифры 1, 2, 3 и 4 встречались ровно по одному разу в каждой строке, колонке и области 2 × 2.'});
    }
    // 5 — Логическая цепочка
    {
      const people = ['Лена','Ира','Олег','Макс','Вера','Даня'];
      const names = people.slice(0, difficulty==='hard'?5:4).sort(()=>Math.random()-.5);
      const clues = names.slice(0,-1).map((name,i)=>`${name} стоит в очереди раньше, чем ${names[i+1]}.`);
      const last = names[names.length-1];
      add({type:'text', icon:'≋', category:'ЛОГИКА', title:'Кто пришёл последним?', prompt:`Люди заходили по одному. Известно, что:\n${clues.map(x=>'• '+x).join('\n')}\n\nКто вошёл последним?`, answer:last, hint:'Выстрой имена в цепочку: каждый следующий пришёл после предыдущего.', explanation:`Порядок однозначно задаётся цепочкой: ${names.join(' → ')}. Последним был(а) ${last}.`, placeholder:'Имя'});
    }
    // 6 — Загадка
    {
      const riddles = [
        {q:'Без рук, без ног, а ворота открывает. Что это?',a:'ВЕТЕР',hint:'Его не видно, но его можно почувствовать.',exp:'Это ветер: он может распахнуть ворота.'},
        {q:'Зимой и летом одним цветом. Что это?',a:'ЕЛЬ',hint:'Это дерево, которое не сбрасывает иголки на зиму.',exp:'Это ель — вечнозелёное хвойное дерево.'},
        {q:'Чем больше из неё берёшь, тем больше она становится. Что это?',a:'ЯМА',hint:'В земле может появиться, если долго копать.',exp:'Это яма: чем больше земли вынуть, тем она больше.'},
        {q:'Что можно увидеть с закрытыми глазами?',a:'СОН',hint:'Это бывает ночью, пока ты спишь.',exp:'Это сон.'},
        {q:'У него есть города, но нет домов; есть реки, но нет воды. Что это?',a:'КАРТА',hint:'Её раскрывают, чтобы найти дорогу.',exp:'Это карта — на ней обозначены города и реки.'}
      ];
      const r=pick(riddles); add({type:'text',icon:'?',category:'ЗАГАДКА',title:'Подумай образно',prompt:r.q,answer:r.a,accepted:r.a==='ЕЛЬ'?['ЕЛКА']:[],hint:r.hint,explanation:r.exp,placeholder:'Твой ответ'});
    }
    // 7 — Операции
    {
      const ops = ['+','−','×','÷']; const op = pick(ops);
      let a,b,target;
      if(op==='+'){a=int(8,32);b=int(3,19);target=a+b;} else if(op==='−'){a=int(20,60);b=int(2,Math.min(18,a-1));target=a-b;} else if(op==='×'){a=int(3,12);b=int(3,12);target=a*b;} else {b=int(2,12);target=int(3,12);a=b*target;}
      add({type:'choice',icon:'±',category:'МАТЕМАТИКА',title:'Верный знак',prompt:`Какой знак нужно поставить вместо пропуска?\n\n${a}  ?  ${b} = ${target}`,choices:ops,answer:op,hint:'Проверь по очереди: сложение, вычитание, умножение и деление. Какое действие даёт правую часть?',explanation:`Подходит знак «${op}»: ${a} ${op} ${b} = ${target}.`});
    }
    // 8 — Лишнее слово
    {
      const groups=[
        {items:['Сосна','Берёза','Ромашка','Клён'],odd:'Ромашка',hint:'Три варианта — деревья.',reason:'Ромашка — цветок, остальные — деревья.'},
        {items:['Квадрат','Треугольник','Круг','Километр'],odd:'Километр',hint:'Три варианта — геометрические фигуры.',reason:'Километр — единица длины, остальные — фигуры.'},
        {items:['Январь','Среда','Апрель','Август'],odd:'Среда',hint:'Три варианта — месяцы.',reason:'Среда — день недели, остальные — месяцы.'},
        {items:['Ложка','Тарелка','Кастрюля','Подушка'],odd:'Подушка',hint:'Три вещи можно найти на кухне.',reason:'Подушка не кухонная утварь.'},
        {items:['Скрипка','Флейта','Барабан','Палитра'],odd:'Палитра',hint:'Три варианта связаны с музыкой.',reason:'Палитра нужна художнику, остальные — музыкальные инструменты.'}
      ];
      const g=pick(groups); add({type:'choice',icon:'◌',category:'НАБЛЮДАТЕЛЬНОСТЬ',title:'Найди лишнее',prompt:'Выбери слово, которое не подходит к остальным.',choices:g.items,answer:g.odd,hint:g.hint,explanation:g.reason});
    }
    // 9 — Визуальный паттерн
    {
      const symbols = difficulty==='hard' ? ['◆','●','●','◆','●','●','◆','?'] : ['▲','●','●','▲','●','●','▲','?'];
      const answer = difficulty==='hard' ? '●' : '●';
      add({type:'choice',icon:'◈',category:'ПАТТЕРН',title:'Увидь ритм',prompt:'Какой символ должен стоять на месте вопросительного знака?',visual:symbols.join('   '),choices:difficulty==='hard'?['●','▲','■','◆']:['●','▲','■','◆'],answer,hint:'Посмотри на повторяющиеся группы символов.',explanation:'Повторяется группа из трёх символов: ◆, ●, ● (или ▲, ●, ●). После ◆ снова идут два круга.'});
    }
    // 10 — Геометрия
    {
      const a=int(difficulty==='easy'?3:5,difficulty==='easy'?9:18), b=int(difficulty==='easy'?3:5,difficulty==='easy'?10:16);
      const area = difficulty==='hard' || Math.random()>.55;
      const answer=area?a*b:2*(a+b);
      add({type:'number',icon:'▱',category:'ГЕОМЕТРИЯ',title:area?'Площадь прямоугольника':'Периметр прямоугольника',prompt:area?'Найди площадь прямоугольника со сторонами:':'Найди периметр прямоугольника со сторонами:',visual:`${a} см   ×   ${b} см`,answer:String(answer),hint:area?'Площадь равна произведению длины на ширину.':'Периметр — это сумма всех четырёх сторон.',explanation:area?`Площадь = ${a} × ${b} = ${answer} см².`:`Периметр = 2 × (${a} + ${b}) = ${answer} см.`,suffix:area?'см²':'см'});
    }
    return list;
  }

  function renderPuzzle() {
    const card = document.querySelector('.puzzle-card');
    card.classList.remove('replay');
    void card.offsetWidth;
    card.classList.add('replay');
    const p = puzzles[index]; answered=false; currentHint=0;
    $('feedback').textContent=''; $('feedback').className='feedback';
    $('solution-button').classList.remove('hidden'); $('solution-button').textContent='Показать решение ↗';
    $('hint-button').disabled=false; $('check-button').disabled=false; $('check-button').querySelector('span').textContent='Проверить';
    $('puzzle-icon').textContent=p.icon; $('puzzle-category').textContent=p.category;
    $('puzzle-title').textContent=p.title; $('puzzle-prompt').textContent=p.prompt;
    $('puzzle-difficulty').textContent=difficultyNames[difficulty];
    $('progress-label').innerHTML=`ЗАДАЧА ${String(index+1).padStart(2,'0')} <span>/ 10</span>`;
    $('progress-percent').textContent=`${(index+1)*10}%`; $('progress-bar').style.width=`${(index+1)*10}%`;
    const content=$('puzzle-content'); content.replaceChildren();
    if(p.visual){ const visual=el('div','puzzle-visual'+(p.type==='choice'?' symbol-sequence':''),p.visual); content.append(visual); }
    if(p.type==='number'||p.type==='text'){
      const row=el('div','answer-row');
      if(p.suffix==='x =') row.append(el('span','answer-suffix','x ='));
      const input=el('input','answer-input'+(p.type==='number'?' numeric':'')); input.id='answer-input'; input.type='text'; input.autocomplete='off'; input.autocapitalize='off'; input.spellcheck=false; input.placeholder=p.placeholder||'Введи ответ';
      if(p.type==='number'){input.inputMode='decimal';input.setAttribute('aria-label','Числовой ответ');}
      row.append(input); if(p.suffix&&p.suffix!=='x =') row.append(el('span','answer-suffix',p.suffix)); content.append(row);
      input.addEventListener('keydown', e=>{if(e.key==='Enter')checkAnswer();});
    } else if(p.type==='choice'){
      const choices=el('div','choice-list'); p.choices.forEach(option=>{const button=el('button','choice-button',option);button.type='button';button.addEventListener('click',()=>{choices.querySelectorAll('.choice-button').forEach(b=>b.classList.remove('selected'));button.classList.add('selected');});choices.append(button);}); content.append(choices);
    } else if(p.type==='sudoku'){
      const board=el('div','sudoku'); board.setAttribute('role','group'); board.setAttribute('aria-label','Судоку четыре на четыре');
      p.given.forEach((row,r)=>row.forEach((value,c)=>{const cell=document.createElement('input');cell.className='sudoku-cell'+(value?' given':'');cell.type='text';cell.inputMode='numeric';cell.maxLength=1;cell.setAttribute('aria-label',`Строка ${r+1}, столбец ${c+1}`);cell.dataset.r=r;cell.dataset.c=c;if(value){cell.value=value;cell.readOnly=true;}cell.addEventListener('input',()=>{cell.value=cell.value.replace(/[^1-4]/g,'').slice(-1);});board.append(cell);})); content.append(board);
    }
    if(p.clues){ const ul=el('ul','logic-clues');p.clues.forEach(c=>ul.append(el('li','',c)));content.append(ul); }
    if(p.type==='sudoku') $('puzzle-prompt').textContent=p.prompt;
    if(p.type==='number'||p.type==='text') setTimeout(()=>{const input=$('answer-input');if(input)input.focus({preventScroll:true});},50);
  }

  function currentAnswer() {
    const p=puzzles[index];
    if(p.type==='sudoku') return [...document.querySelectorAll('.sudoku-cell')].map(x=>x.value).join('');
    if(p.type==='choice') return document.querySelector('.choice-button.selected')?.textContent || '';
    return $('answer-input')?.value.trim() || '';
  }
  function isCorrect() {
    const p=puzzles[index]; const value=currentAnswer();
    if(p.type==='sudoku') return [...document.querySelectorAll('.sudoku-cell')].every((cell,i)=>cell.value===String(p.solution[Math.floor(i/4)][i%4]));
    if(p.type==='number') return Number(String(value).replace(',','.'))===Number(p.answer);
    const normalized=clean(value);
    return normalized===clean(p.answer)||(p.accepted||[]).some(a=>normalized===clean(a));
  }
  function checkAnswer() {
    if(answered)return;
    const val=currentAnswer();
    if(!val || (puzzles[index].type==='sudoku'&&val.split('').some(cell=>!cell))) { showFeedback(puzzles[index].type==='sudoku'?'Заполни все клетки, затем проверь.':'Сначала введи ответ или выбери вариант.',true); return; }
    const ok=isCorrect(); answered=true; results[index]=ok;
    showFeedback(ok?'Верно! Именно так. ✦':'Пока не совпало. Можно попробовать ещё раз или посмотреть подсказку.',!ok);
    if(!ok){answered=false;results[index]=false;}
    else { $('check-button').querySelector('span').textContent=index===9?'Результаты':'Следующая задача'; $('solution-button').classList.add('hidden'); }
    if(soundOn)playTone(ok?660:220);
  }
  function showFeedback(message,error=false){const box=$('feedback');box.textContent=message;box.className='feedback'+(error?' error':'');}
  function showHint(){const p=puzzles[index];if(currentHint===0){showFeedback('Подсказка: '+p.hint);currentHint=1;}else{showFeedback('Подсказка: '+p.hint);}}
  function revealSolution(){
    const p=puzzles[index]; const box=el('div','solution-box'); box.textContent='Решение: '+p.explanation;
    const old=$('puzzle-content').querySelector('.solution-box');if(old)old.remove();$('puzzle-content').append(box);
    $('solution-button').classList.add('hidden'); $('feedback').textContent='Ответ открыт — продолжай, когда будешь готов.'; $('feedback').className='feedback';
    results[index]=false; answered=true; $('check-button').querySelector('span').textContent=index===9?'Результаты':'Следующая задача';
  }
  function nextPuzzle(){if(index<9){index++;renderPuzzle();}else finishSeries();}
  function finishSeries(){
    const count=results.filter(Boolean).length; stats.solved=(stats.solved||0)+count; stats.best=Math.max(stats.best||0,count); localStorage.setItem('iskra-stats',JSON.stringify(stats));
    $('result-score').textContent=count; $('result-percent').textContent=`${count*10}%`;
    $('result-title').textContent=count===10?'Безупречно!':count>=7?'Отличная работа.':count>=4?'Хорошая разминка.':'Первый шаг сделан.';
    $('result-subtitle').textContent=count===10?'Все десять задач решены верно — твой ум сегодня в отличной форме.':'Ты прошёл через десять разных способов мыслить. Каждая серия делает тебя сильнее.';
    const missed=puzzles.map((p,i)=>results[i]?null:p.title).filter(Boolean);
    $('result-summary').textContent=missed.length?`Можно вернуться к новым задачам и попробовать ещё. ${missed.length===10?'В следующий раз всё получится!':`На этот раз особенно задуматься пришлось над: ${missed.join(', ')}.`}`:'Все форматы покорены. Так держать!';
    $('best-streak').textContent=stats.best; $('solved-total').textContent=stats.solved;
    showScreen('result');
  }
  function startSeries(){
    seriesNumber++;localStorage.setItem('iskra-series',String(seriesNumber));$('series-number').textContent=seriesLabel();$('game-series-number').textContent=seriesLabel();
    puzzles=makePuzzles();index=0;results=Array(10).fill(false);renderPuzzle();showScreen('game');
  }
  function goHome(){showScreen('home');$('best-streak').textContent=stats.best||0;$('solved-total').textContent=stats.solved||0;}
  function playTone(frequency){try{const ctx=new (window.AudioContext||window.webkitAudioContext)();const osc=ctx.createOscillator();const gain=ctx.createGain();osc.frequency.value=frequency;gain.gain.setValueAtTime(.07,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.12);osc.connect(gain);gain.connect(ctx.destination);osc.start();osc.stop(ctx.currentTime+.12);}catch(_){}}

  document.querySelectorAll('.difficulty-option').forEach(button=>button.addEventListener('click',()=>{difficulty=button.dataset.level;document.querySelectorAll('.difficulty-option').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',b===button?'true':'false');});$('difficulty-note').textContent=difficultyNotes[difficulty];}));
  $('start-button').addEventListener('click',startSeries);
  $('check-button').addEventListener('click',()=>answered?nextPuzzle():checkAnswer());
  $('hint-button').addEventListener('click',showHint);
  $('solution-button').addEventListener('click',revealSolution);
  $('skip-button').addEventListener('click',()=>{if(!answered)results[index]=false;nextPuzzle();});
  $('back-button').addEventListener('click',()=>{if(confirm('Выйти из серии? Текущий прогресс этой серии не сохранится.'))goHome();});
  $('again-button').addEventListener('click',startSeries); $('result-home').addEventListener('click',goHome);
  $('sound-toggle').addEventListener('click',()=>{soundOn=!soundOn;$('sound-toggle').classList.toggle('active',soundOn);$('sound-toggle').setAttribute('aria-label',soundOn?'Звук включён':'Звук выключен');if(soundOn)playTone(440);});
  $('series-number').textContent=String(seriesNumber+1).padStart(3,'0');$('best-streak').textContent=stats.best||0;$('solved-total').textContent=stats.solved||0;
  if('serviceWorker' in navigator)window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').catch(()=>{}));
})();
