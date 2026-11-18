(function () {
  const STORAGE_KEY = "entrainement-smc-v2";
  const HISTORY_SIZE = 20;
  const WINDOW_BEFORE = 110;
  const REVEAL_DELAY_MS = 70;
  const RR = 2;
  const TIMEFRAMES = {
    main: { tab: "tab-15m", hint: "" },
    h1: { tab: "tab-1h", seconds: 3600, hint: "1 h · 48 dernières heures · la dernière bougie est en cours" },
    h4: { tab: "tab-4h", seconds: 14400, hint: "4 h · 8 derniers jours · la dernière bougie est en cours" },
  };
  const scenarios = window.SCENARIOS || [];
  const $ = (id) => document.getElementById(id);

  const emptyStats = () => ({
    played: 0, wins: 0, losses: 0, totalR: 0, streak: 0, best: 0, agree: 0, seen: [], history: [], byPair: {},
  });

  function loadStats() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      return saved ? { ...emptyStats(), ...saved } : emptyStats();
    } catch (error) {
      return emptyStats();
    }
  }

  function saveStats() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stats));
    } catch (error) {
      console.warn("Statistiques non sauvegardées", error);
    }
  }

  let stats = loadStats();
  let game = null;
  let timer = null;
  let timeframe = "main";

  const parisTime = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit" });
  const parisDay = new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", day: "2-digit", month: "2-digit" });
  const parisDate = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Europe/Paris", weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
  });

  function formatR(value) {
    const rounded = Math.round(value * 100) / 100;
    return `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(rounded).toLocaleString("fr-FR")} R`;
  }

  function formatDuration(minutes) {
    if (minutes < 60) return `${minutes} min`;
    return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")}`;
  }

  function renderHome() {
    $("s-streak").textContent = stats.streak;
    $("s-best").textContent = stats.best;
    $("s-played").textContent = stats.played;
    $("s-rate").textContent = stats.played ? `${Math.round((stats.wins / stats.played) * 100)} %` : "–";
    $("s-r").textContent = formatR(stats.totalR).replace("+0 R", "0 R");
    $("s-agree").textContent = stats.played ? `${Math.round((stats.agree / stats.played) * 100)} %` : "–";
    $("scenario-count").textContent = scenarios.length;

    const pairs = $("pair-stats");
    pairs.replaceChildren();
    for (const pair of ["XAUUSD", "EURUSD", "GBPUSD"]) {
      const item = stats.byPair[pair] || { played: 0, wins: 0, totalR: 0 };
      const li = document.createElement("li");
      const name = document.createElement("strong");
      name.textContent = pair;
      const detail = document.createElement("span");
      detail.className = "mono";
      detail.textContent = item.played
        ? `${item.played} jouées · ${Math.round((item.wins / item.played) * 100)} % · ${formatR(item.totalR)}`
        : "pas encore jouée";
      li.append(name, detail);
      pairs.append(li);
    }

    const list = $("history-list");
    list.replaceChildren();
    for (const item of stats.history) {
      const li = document.createElement("li");
      const dot = document.createElement("span");
      dot.className = `dot ${item.r > 0 ? "dot-win" : item.r < 0 ? "dot-loss" : "dot-flat"}`;
      const text = document.createElement("span");
      const sideText = item.choice === "buy" ? "Achat" : "Vente";
      const disagreement = item.choice === item.side ? "" : ` (stratégie : ${item.side === "buy" ? "achat" : "vente"})`;
      text.textContent = `${item.pair || ""} #${item.id} · ${sideText}${disagreement}`;
      const r = document.createElement("span");
      r.className = "mono";
      r.textContent = formatR(item.r);
      li.append(dot, text, r);
      list.append(li);
    }
    $("history-empty").hidden = stats.history.length > 0;
  }

  function show(screen) {
    $("home").hidden = screen !== "home";
    $("game").hidden = screen !== "game";
    window.scrollTo(0, 0);
  }

  function pickScenario() {
    const seen = new Set(stats.seen);
    let pool = scenarios.filter((s) => !seen.has(s.id));
    if (!pool.length) {
      stats.seen = [];
      pool = scenarios;
    }
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function decode(scenario) {
    const scale = Math.pow(10, scenario.p);
    const toAbs = (rows) => rows.map((row) => row.map((v) => (v + scenario.b) / scale));
    return {
      ...scenario,
      candles: toAbs(scenario.c),
      htf: {
        h1: { t: scenario.h1.t, rows: toAbs(scenario.h1.c) },
        h4: { t: scenario.h4.t, rows: toAbs(scenario.h4.c) },
      },
    };
  }

  function price(value) {
    return CandleChart.formatPrice(value, game.s.p);
  }

  function startGame() {
    clearInterval(timer);
    const scenario = decode(pickScenario());
    game = { s: scenario, phase: "decide", revealed: scenario.d, showAnalysis: true };
    $("g-number").textContent = `${scenario.pair} · situation #${scenario.id}`;
    $("g-streak").textContent = stats.streak;
    $("g-price").textContent = `15 min · prix ${price(scenario.candles[scenario.d][3])}`;
    $("decide").hidden = false;
    $("playing").hidden = true;
    $("result").hidden = true;
    setTimeframe("main");
    show("game");
    requestAnimationFrame(render);
  }

  function setTimeframe(value) {
    timeframe = value;
    for (const [key, config] of Object.entries(TIMEFRAMES)) {
      $(config.tab).setAttribute("aria-selected", String(key === value));
    }
    $("chart-hint").textContent = TIMEFRAMES[value].hint;
    render();
  }

  function inProgressCandle(s, frame, seconds) {
    const step = s.st;
    const decisionTime = s.t + (s.d + 1) * step;
    const barStart = frame.t + frame.rows.length * seconds;
    let first = s.d;
    while (first > 0 && s.t + (first - 1) * step >= barStart) first -= 1;
    const end = Math.min(s.d, Math.round((decisionTime - s.t) / step) - 1);
    if (s.t + first * step < barStart || first > end) {
      const close = s.candles[s.d][3];
      return [close, close, close, close];
    }
    let high = -Infinity;
    let low = Infinity;
    for (let i = first; i <= end; i++) {
      high = Math.max(high, s.candles[i][1]);
      low = Math.min(low, s.candles[i][2]);
    }
    return [s.candles[first][0], high, low, s.candles[end][3]];
  }

  function render() {
    if (!game) return;
    const canvas = $("chart");
    const s = game.s;
    if (timeframe !== "main") {
      const frame = s.htf[timeframe];
      const seconds = TIMEFRAMES[timeframe].seconds;
      const rows = frame.rows.concat([inProgressCandle(s, frame, seconds)]);
      CandleChart.draw(canvas, {
        candles: rows,
        from: 0,
        to: rows.length - 1,
        decimals: s.p,
        timeLabel: (i) => {
          const date = new Date((frame.t + i * seconds) * 1000);
          return timeframe === "h4" ? parisDay.format(date) : parisTime.format(date);
        },
      });
      return;
    }
    const view = {
      candles: s.candles,
      from: Math.max(0, s.d - WINDOW_BEFORE),
      to: game.revealed,
      decimals: s.p,
      timeLabel: (i) => parisTime.format(new Date((s.t + i * s.st) * 1000)),
      lines: [],
    };
    if (game.phase !== "decide") {
      view.decisionIdx = s.d;
      view.marker = { idx: s.d, price: game.entry, side: game.choice };
      view.lines.push(
        { price: game.entry, color: "#ffffff", text: "Entrée", from: s.d, width: 1 },
        { price: game.tp, color: "#2bb39a", text: "TP", from: s.d },
        { price: game.sl, color: "#e5534b", text: "SL", from: s.d },
      );
    }
    if (game.phase === "done" && game.showAnalysis) {
      view.annotations = { ...s.a, side: s.side, until: s.d };
    }
    CandleChart.draw(canvas, view);
  }

  function choose(choice) {
    if (!game || game.phase !== "decide") return;
    const s = game.s;
    const entry = s.candles[s.d][3];
    const direction = choice === "buy" ? 1 : -1;
    Object.assign(game, {
      phase: "play",
      choice,
      entry,
      sl: entry - direction * s.risk,
      tp: entry + direction * s.risk * RR,
    });
    $("decide").hidden = true;
    $("playing").hidden = false;
    setTimeframe("main");
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      finishNow();
      return;
    }
    timer = setInterval(stepReveal, REVEAL_DELAY_MS);
  }

  function checkBar(i) {
    const [, high, low] = game.s.candles[i];
    if (game.choice === "buy") {
      if (low <= game.sl) return -1;
      if (high >= game.tp) return RR;
    } else {
      if (high >= game.sl) return -1;
      if (low <= game.tp) return RR;
    }
    return null;
  }

  function stepReveal() {
    const s = game.s;
    const next = game.revealed + 1;
    if (next >= s.candles.length) {
      const last = s.candles[s.candles.length - 1][3];
      const direction = game.choice === "buy" ? 1 : -1;
      finish(((last - game.entry) * direction) / s.risk, true);
      return;
    }
    game.revealed = next;
    const outcome = checkBar(next);
    if (outcome !== null) {
      finish(outcome, false);
      return;
    }
    $("play-status").textContent = `${formatDuration(((next - s.d) * s.st) / 60)} après l'entrée…`;
    render();
  }

  function finishNow() {
    clearInterval(timer);
    while (game.phase === "play") stepReveal();
  }

  function finish(r, expired) {
    clearInterval(timer);
    const s = game.s;
    game.phase = "done";
    game.r = r;
    const minutes = ((game.revealed - s.d) * s.st) / 60;
    game.revealed = Math.min(game.revealed + 6, s.candles.length - 1);

    stats.played += 1;
    stats.totalR = Math.round((stats.totalR + r) * 100) / 100;
    if (r > 0) {
      stats.wins += 1;
      stats.streak += 1;
      stats.best = Math.max(stats.best, stats.streak);
    } else {
      stats.losses += 1;
      stats.streak = 0;
    }
    const pairStats = stats.byPair[s.pair] || { played: 0, wins: 0, totalR: 0 };
    pairStats.played += 1;
    pairStats.wins += r > 0 ? 1 : 0;
    pairStats.totalR = Math.round((pairStats.totalR + r) * 100) / 100;
    stats.byPair[s.pair] = pairStats;
    if (game.choice === s.side) stats.agree += 1;
    stats.seen.push(s.id);
    stats.history.unshift({ id: s.id, pair: s.pair, choice: game.choice, side: s.side, r: Math.round(r * 100) / 100 });
    stats.history = stats.history.slice(0, HISTORY_SIZE);
    saveStats();

    const badge = $("r-badge");
    badge.className = `badge ${r > 0 ? "win" : r < 0 ? "loss" : "flat"}`;
    badge.textContent = expired ? "Clôturé" : r > 0 ? "Gagné" : "Perdu";
    $("r-r").textContent = formatR(r);
    const when = parisDate.format(new Date((s.t + s.d * s.st) * 1000));
    $("r-detail").textContent = expired
      ? `Ni le TP ni le SL n'ont été touchés en 36 h : position fermée au dernier prix. Situation du ${when}.`
      : `${r > 0 ? "TP" : "SL"} touché en ${formatDuration(minutes)}. Situation du ${when}.`;
    const strategySide = s.side === "buy" ? "un ACHAT" : "une VENTE";
    const extras = [s.sweep ? "avec prise de liquidité" : "sans prise de liquidité", s.fibOk ? "dans la zone Fibonacci" : "hors zone Fibonacci stricte"];
    $("r-strategy").textContent = `La stratégie voyait ${strategySide} : tendance 4 h dans ce sens, retour dans la zone puis bougie de retournement (${extras.join(", ")}). ${game.choice === s.side ? "Tu étais d'accord avec elle." : "Tu as pris le sens inverse."}`;
    $("legend").hidden = !game.showAnalysis;
    $("show-analysis").checked = game.showAnalysis;
    $("g-streak").textContent = stats.streak;
    $("playing").hidden = true;
    $("result").hidden = false;
    if (navigator.vibrate) navigator.vibrate(r > 0 ? 40 : [60, 60, 60]);
    render();
  }

  $("play").addEventListener("click", startGame);
  $("next").addEventListener("click", startGame);
  $("buy").addEventListener("click", () => choose("buy"));
  $("sell").addEventListener("click", () => choose("sell"));
  $("skip").addEventListener("click", startGame);
  $("fast").addEventListener("click", finishNow);
  for (const [key, config] of Object.entries(TIMEFRAMES)) {
    $(config.tab).addEventListener("click", () => setTimeframe(key));
  }
  $("show-analysis").addEventListener("change", (event) => {
    game.showAnalysis = event.target.checked;
    $("legend").hidden = !game.showAnalysis;
    render();
  });
  $("back").addEventListener("click", () => {
    clearInterval(timer);
    if (game && game.phase === "play") finishNow();
    game = null;
    renderHome();
    show("home");
  });
  $("reset").addEventListener("click", () => { $("reset-confirm").hidden = false; });
  $("reset-no").addEventListener("click", () => { $("reset-confirm").hidden = true; });
  $("reset-yes").addEventListener("click", () => {
    stats = emptyStats();
    saveStats();
    $("reset-confirm").hidden = true;
    renderHome();
  });
  window.addEventListener("resize", render);

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("sw.js").catch((error) => console.warn("Service worker", error));
  }

  renderHome();
})();
