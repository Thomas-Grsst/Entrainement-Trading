(function () {
  const COLORS = {
    up: "#2bb39a",
    down: "#e5534b",
    grid: "#1f2937",
    axis: "#8592a6",
    text: "#e6ebf2",
    panel: "#161d28",
    liq: "#ff8a50",
    bos: "#e6ebf2",
    ob: "rgba(149, 117, 205, 0.32)",
    obEdge: "rgba(179, 157, 219, 0.9)",
    fvg: "rgba(240, 180, 41, 0.28)",
    fvgEdge: "rgba(240, 180, 41, 0.9)",
    fib: "rgba(79, 195, 247, 0.22)",
    fibEdge: "rgba(79, 195, 247, 0.85)",
    entry: "#ffffff",
    decision: "rgba(240, 180, 41, 0.55)",
  };
  const PRICE_AXIS = 66;
  const TIME_AXIS = 20;
  const TOP_PAD = 26;

  function formatPrice(value, decimals = 0) {
    return value.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
      .replace(/\u202f|\u00a0/g, " ");
  }

  function niceStep(range, targetTicks) {
    const raw = range / targetTicks;
    const power = Math.pow(10, Math.floor(Math.log10(raw)));
    const unit = raw / power;
    const nice = unit < 1.5 ? 1 : unit < 3 ? 2 : unit < 7 ? 5 : 10;
    return nice * power;
  }

  function setupCanvas(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  function label(ctx, text, x, y, color, align) {
    ctx.font = "600 10px system-ui, sans-serif";
    const width = ctx.measureText(text).width + 8;
    const left = align === "right" ? x - width : x;
    ctx.fillStyle = "rgba(14, 19, 27, 0.85)";
    ctx.fillRect(left, y - 8, width, 16);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(left + 0.5, y - 7.5, width - 1, 15);
    ctx.fillStyle = color;
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    ctx.fillText(text, left + 4, y);
  }

  function draw(canvas, view) {
    const { ctx, width, height } = setupCanvas(canvas);
    const { candles, from, to } = view;
    const plotW = width - PRICE_AXIS;
    const plotH = height - TIME_AXIS - TOP_PAD;
    const count = to - from + 1;
    const slot = plotW / (count + 2);
    const body = Math.max(1, Math.min(slot * 0.7, 14));

    let low = Infinity;
    let high = -Infinity;
    for (let i = from; i <= to; i++) {
      low = Math.min(low, candles[i][2]);
      high = Math.max(high, candles[i][1]);
    }
    for (const line of view.lines || []) {
      low = Math.min(low, line.price);
      high = Math.max(high, line.price);
    }
    const pad = (high - low) * 0.06 || 10;
    low -= pad;
    high += pad;

    const x = (i) => (i - from + 1) * slot;
    const y = (p) => TOP_PAD + (high - p) / (high - low) * plotH;

    const step = niceStep(high - low, 5);
    ctx.font = "500 10px ui-monospace, Menlo, monospace";
    ctx.textBaseline = "middle";
    for (let p = Math.ceil(low / step) * step; p <= high; p += step) {
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, Math.round(y(p)) + 0.5);
      ctx.lineTo(plotW, Math.round(y(p)) + 0.5);
      ctx.stroke();
      ctx.fillStyle = COLORS.axis;
      ctx.textAlign = "left";
      ctx.fillText(formatPrice(p, view.decimals), plotW + 6, y(p));
    }

    if (view.timeLabel) {
      const every = Math.max(1, Math.ceil(count / 5));
      ctx.fillStyle = COLORS.axis;
      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      for (let i = from + Math.ceil(every / 2); i <= to; i += every) {
        if (x(i) > 22 && x(i) < plotW - 18) ctx.fillText(view.timeLabel(i), x(i), height - 6);
      }
    }

    const span = (startIdx, endIdx) => [Math.max(x(startIdx) - slot / 2, 0), Math.min(x(endIdx) + slot / 2, plotW)];
    const a = view.annotations;
    if (a) {
      const right = a.until;
      const zone = (startIdx, lo, hi, fill, edge) => {
        const [x0, x1] = span(startIdx, right);
        ctx.fillStyle = fill;
        ctx.fillRect(x0, y(hi), x1 - x0, y(lo) - y(hi));
        ctx.strokeStyle = edge;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(x0 + 0.5, y(hi) + 0.5, x1 - x0 - 1, y(lo) - y(hi) - 1);
        ctx.setLineDash([]);
      };
      zone(a.ob[0], a.ob[1], a.ob[2], COLORS.ob, COLORS.obEdge);
      zone(a.fvg[0] + 1, a.fvg[1], a.fvg[2], COLORS.fvg, COLORS.fvgEdge);
      const [anchorIdx, extremeIdx, anchor, extreme] = a.fib;
      const range = extreme - anchor;
      const f618 = extreme - 0.618 * range;
      const f705 = extreme - 0.705 * range;
      zone(anchorIdx, Math.min(f618, f705), Math.max(f618, f705), COLORS.fib, COLORS.fibEdge);
      ctx.strokeStyle = COLORS.fibEdge;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(x(anchorIdx), y(anchor));
      ctx.lineTo(x(extremeIdx), y(extreme));
      ctx.stroke();
      ctx.setLineDash([]);

      const hline = (i0, i1, price, color, text) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(x(i0), y(price));
        ctx.lineTo(x(i1), y(price));
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.lineWidth = 1;
        label(ctx, text, Math.max(x(i0) - 2, 2), y(price) + (a.side === "buy" ? -12 : 12), color, "left");
      };
      if (a.liq) hline(a.liq[0], a.liq[1] + 1, a.liq[2], COLORS.liq, "Liquidité");
      hline(a.bos[0], a.bos[1], a.bos[2], COLORS.bos, "BOS");
    }

    for (let i = from; i <= to; i++) {
      const [o, h, l, c] = candles[i];
      const color = c >= o ? COLORS.up : COLORS.down;
      const faded = view.dimAfter !== undefined && i > view.dimAfter;
      ctx.globalAlpha = faded ? 0.95 : 1;
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(Math.round(x(i)) + 0.5, y(h));
      ctx.lineTo(Math.round(x(i)) + 0.5, y(l));
      ctx.stroke();
      const top = y(Math.max(o, c));
      const bottom = y(Math.min(o, c));
      ctx.fillRect(x(i) - body / 2, top, body, Math.max(1, bottom - top));
    }
    ctx.globalAlpha = 1;

    if (view.decisionIdx !== undefined && view.decisionIdx < to) {
      ctx.strokeStyle = COLORS.decision;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x(view.decisionIdx) + slot / 2, TOP_PAD - 10);
      ctx.lineTo(x(view.decisionIdx) + slot / 2, TOP_PAD + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    for (const line of view.lines || []) {
      const startX = line.from !== undefined ? x(line.from) : 0;
      ctx.strokeStyle = line.color;
      ctx.lineWidth = line.width || 1.5;
      ctx.setLineDash(line.dash || []);
      ctx.beginPath();
      ctx.moveTo(startX, y(line.price));
      ctx.lineTo(plotW, y(line.price));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineWidth = 1;
      if (line.text) label(ctx, line.text, plotW - 2, y(line.price), line.color, "right");
    }

    if (view.marker) {
      const mx = x(view.marker.idx);
      const my = y(view.marker.price);
      const up = view.marker.side === "buy";
      ctx.fillStyle = COLORS.entry;
      ctx.beginPath();
      ctx.moveTo(mx, my + (up ? -1 : 1));
      ctx.lineTo(mx - 6, my + (up ? 10 : -10));
      ctx.lineTo(mx + 6, my + (up ? 10 : -10));
      ctx.closePath();
      ctx.fill();
    }

    const last = candles[to];
    ctx.fillStyle = last[3] >= last[0] ? COLORS.up : COLORS.down;
    const ly = y(last[3]);
    ctx.fillRect(plotW + 1, ly - 9, PRICE_AXIS - 2, 18);
    ctx.fillStyle = "#0b0f15";
    ctx.font = "700 10px ui-monospace, Menlo, monospace";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(formatPrice(last[3], view.decimals), plotW + 5, ly);
  }

  window.CandleChart = { draw, formatPrice };
})();
