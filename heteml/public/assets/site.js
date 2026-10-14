// ReleaseTune の動き（Next.js 版の各コンポーネントの onClick・useState からの移植）
// - ジャケット画像を読めないときの ♪ 表示（Jacket.tsx）
// - GA4 のイベント（data-ga 属性。GoogleAnalytics.tsx の gaEvent と同じ名前・値）
// - 日付ページの前日・翌日・今日に戻る・カレンダー（DatePageClient.tsx）
// - X・Threads のシェア（TrackDetailClient.tsx）
// - 検索フォーム（SearchPageClient.tsx）

function rtJacketError(img) {
  var box = img.parentElement;
  box.setAttribute("style", box.getAttribute("data-fallback-style"));
  box.textContent = "♪";
}

function gaEvent(name, params) {
  if (typeof window.gtag === "function") window.gtag("event", name, params || {});
}

document.addEventListener("click", function (e) {
  var ga = e.target.closest("[data-ga]");
  if (ga) gaEvent(ga.getAttribute("data-ga"), JSON.parse(ga.getAttribute("data-ga-params") || "{}"));
  var nav = e.target.closest("button[data-href]");
  if (nav) location.href = nav.getAttribute("data-href");
});

// ── 日付ページのカレンダー ───────────────────────────────

(function () {
  var nav = document.querySelector("[data-cal-nav]");
  if (!nav) return;
  var mmdd = nav.getAttribute("data-mmdd");
  var curM = parseInt(mmdd.slice(0, 2), 10), curD = parseInt(mmdd.slice(3), 10);
  var base = nav.querySelector("button[data-href]").getAttribute("data-href").replace(/\/date\/\d\d-\d\d$/, "");
  var open = false;
  // 表示年の初期値（Next.js 版と同じく 1〜2月は 2025、それ以外は 2026）
  var calYear = curM <= 2 ? 2025 : 2026, calMonth = curM;
  var cal = null;
  var MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
  var DOWS = ["日", "月", "火", "水", "木", "金", "土"];
  var pad = function (n) { return (n < 10 ? "0" : "") + n; };

  function render() {
    if (cal) cal.remove();
    cal = null;
    nav.classList.toggle("dp-navCalOpen", open);
    var back = nav.querySelector("[data-cal-back]");
    if (back) back.classList.toggle("dp-backTodayCalOpen", open);
    nav.querySelector("[data-cal-hint]").textContent = open ? "▲ 閉じる" : "タップで日付選択";
    if (!open) return;

    var firstDow = new Date(calYear, calMonth - 1, 1).getDay();
    var daysInMonth = new Date(calYear, calMonth, 0).getDate();
    var todayStr = new Date().toLocaleDateString("sv-SE");
    var todayMonth = parseInt(todayStr.slice(5, 7), 10), todayDay = parseInt(todayStr.slice(8, 10), 10);

    cal = document.createElement("div");
    cal.className = "dp-calendar";
    var head = document.createElement("div");
    head.className = "dp-calHeader";
    head.innerHTML = '<button class="dp-calMonthBtn" data-cal-prev>◀</button><span class="dp-calMonthLabel">' + MONTHS[calMonth - 1] +
      '</span><button class="dp-calMonthBtn" data-cal-next>▶</button>';
    cal.appendChild(head);
    var dows = document.createElement("div");
    dows.className = "dp-calDows";
    DOWS.forEach(function (d, i) {
      var el = document.createElement("div");
      el.className = "dp-calDow" + (i === 0 ? " dp-calDowSun" : i === 6 ? " dp-calDowSat" : "");
      el.textContent = d;
      dows.appendChild(el);
    });
    cal.appendChild(dows);
    var days = document.createElement("div");
    days.className = "dp-calDays";
    for (var i = 0; i < firstDow; i++) days.appendChild(document.createElement("div"));
    for (var d = 1; d <= daysInMonth; d++) {
      var dow = (firstDow + d - 1) % 7;
      var b = document.createElement("button");
      b.className = ["dp-calDay", dow === 0 && "dp-calDaySun", dow === 6 && "dp-calDaySat",
        calMonth === todayMonth && d === todayDay && "dp-calDayToday",
        calMonth === curM && d === curD && "dp-calDaySelected"].filter(Boolean).join(" ");
      b.textContent = d;
      b.setAttribute("data-cal-day", d);
      days.appendChild(b);
    }
    cal.appendChild(days);
    nav.appendChild(cal);
  }

  nav.addEventListener("click", function (e) {
    if (e.target.closest("[data-cal-toggle]")) { open = !open; render(); return; }
    if (e.target.closest("[data-cal-prev]")) {
      if (calMonth === 1) { calYear--; calMonth = 12; } else calMonth--;
      render(); return;
    }
    if (e.target.closest("[data-cal-next]")) {
      if (calMonth === 12) { calYear++; calMonth = 1; } else calMonth++;
      render(); return;
    }
    var day = e.target.closest("[data-cal-day]");
    if (day) {
      var next = pad(calMonth) + "-" + pad(parseInt(day.getAttribute("data-cal-day"), 10));
      open = false; render();
      gaEvent("navigate_date", { date: next });
      location.href = base + "/date/" + next;
    }
  });
})();

// ── シェア ───────────────────────────────────────────────

// lib/utils.ts の artistHashtag と同じ。共演名義は1つのタグにすると別の言葉になるので作らない
function artistHashtag(artist) {
  if (/[&＆、,，×\/／]| x |feat\.|featuring/i.test(artist)) return null;
  var tag = artist.replace(/[^\p{L}\p{M}\p{N}_]/gu, "");
  return /\p{L}/u.test(tag) ? tag : null;
}

(function () {
  var box = document.querySelector("[data-share-id]");
  if (!box) return;
  var id = box.getAttribute("data-share-id"), title = box.getAttribute("data-share-title");
  var artist = box.getAttribute("data-share-artist"), releaseDate = box.getAttribute("data-share-date");
  var tag = artistHashtag(artist);

  // 押した時点の日付で文面を作る（リリース日の当日は周年を先頭に出す）
  function shareText(tags) {
    var now = new Date();
    var years = now.getFullYear() - parseInt(releaseDate.slice(0, 4), 10);
    var todayMmdd = String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
    var song = artist + "「" + title.replace(/ - Single$/, "") + "」";
    var date = releaseDate.slice(0, 4) + "年" + parseInt(releaseDate.slice(5, 7), 10) + "月" + parseInt(releaseDate.slice(8, 10), 10) + "日リリース";
    var body = years > 0 && releaseDate.slice(5) === todayMmdd
      ? "🎉 今日で発売から" + years + "年\n" + song + "\n📅 " + date
      : "📅" + date + "\n" + song + (years > 0 ? "（" + years + "年前！）" : "");
    return body + "\n\n" + tags.map(function (t) { return "#" + t; }).join(" ") + "\nhttps://releasetune.com/track/" + id;
  }

  box.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-share]");
    if (!btn) return;
    if (btn.getAttribute("data-share") === "x") {
      gaEvent("share", { method: "X", track_title: title, artist: artist });
      window.open("https://x.com/intent/tweet?text=" + encodeURIComponent(shareText(tag ? [tag, "ReleaseTune"] : ["ReleaseTune"])), "_blank");
    } else {
      gaEvent("share", { method: "Threads", track_title: title, artist: artist });
      // Threads はタグが1投稿に1つまでなので、見つけてもらいやすいアーティスト名を優先する
      window.open("https://www.threads.net/intent/post?text=" + encodeURIComponent(shareText([tag || "ReleaseTune"])), "_blank");
    }
  });
})();

// ── 検索フォーム ─────────────────────────────────────────

(function () {
  var form = document.querySelector("[data-search-form]");
  if (!form) return;
  var input = form.querySelector("input[name=q]"), submit = form.querySelector("button[type=submit]");
  function sync() {
    var has = input.value.trim() !== "";
    submit.disabled = !has;
    submit.classList.toggle("sp-submitActive", has);
  }
  input.addEventListener("input", sync);
  form.addEventListener("submit", function (e) {
    var q = input.value.trim();
    if (!q) { e.preventDefault(); return; }
    input.value = q;
    gaEvent("search", { search_term: q });
    submit.textContent = "検索中...";
    submit.disabled = true;
  });
})();
