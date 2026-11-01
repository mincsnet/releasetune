// ReleaseTune の動き（Next.js 版の各コンポーネントの onClick・useState からの移植）
// - ジャケット画像を読めないときの ♪ 表示（Jacket.tsx）
// - GA4 のイベント（data-ga 属性。GoogleAnalytics.tsx の gaEvent と同じ名前・値。配信ボタンには link_type を追加）
// - 日付ページの前日・翌日・今日に戻る・カレンダー（DatePageClient.tsx）
// - X・Threads のシェア（TrackDetailClient.tsx）
// - 検索フォーム（SearchPageClient.tsx）

function rtJacketError(img) {
  var box = img.parentElement;
  box.classList.add("c-jkNone");
  box.textContent = "♪";
}

function gaEvent(name, params) {
  if (typeof window.gtag === "function") window.gtag("event", name, params || {});
}

document.addEventListener("click", function (e) {
  var ga = e.target.closest("[data-ga]");
  if (ga) {
    var params = JSON.parse(ga.getAttribute("data-ga-params") || "{}");
    // 配信ボタンの曲名・アーティストは、ボタンを囲む枠に1回だけ書いてある（site.php の svc_wrap）
    var ctx = ga.closest("[data-ga-ctx]");
    if (ctx) params = Object.assign(JSON.parse(ctx.getAttribute("data-ga-ctx")), params);
    // 配信サービスのボタンは、曲への直リンクか検索結果へのリンクかを添える（site.php の svc_link が付けるクラス）
    if (ga.classList.contains("c-svc")) params.link_type = ga.classList.contains("c-svcSearch") ? "search" : "direct";
    gaEvent(ga.getAttribute("data-ga"), params);
  }
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

// シェア文のテンプレート（差し替えやすいようにここにまとめる）。事実（日付・年数・曲名・アーティスト）だけを入れる。
// {date}=10月31日 {fullDate}=2018年10月31日 {year}=2018 {years}=8 {artist} {title}
// {work}=米津玄師「Flamingo」（アルバムは「レミオロメンのアルバム「朝顔」」）
// 押した日がリリース日（月日が同じ）なら debut → anniversary → today の順に当てはまるものを使い、それ以外の日は other
var SHARE_TEMPLATES = {
  debut: "今日は {artist} のデビュー記念日🎂 {years}年前の「{title}」から始まりました。",
  anniversary: "{years}年前の今日 {date} は、{work}のリリース日🎂 {years}周年です。当時、どこで誰と聴いていましたか？",
  today: "今日 {date} は {work}のリリース日。{year}年から{years}年。久しぶりに聴き直しませんか？",
  other: "{fullDate}リリースの {work}。あれから{years}年、久しぶりに聴き直しませんか？",
  thisYear: "{fullDate}リリースの {work}。"
};
// キリのいい周年（anniversary を使う年数）
var SHARE_ANNIVERSARIES = [5, 10, 15, 20, 25, 30, 40, 50];

// X の文字数の数え方（日本語・絵文字は2、ラテン文字などは1、URL は長さによらず23）。上限は280
function xLength(text) {
  var n = 0;
  Array.from(text).forEach(function (ch) {
    var cp = ch.codePointAt(0);
    n += cp <= 0x10ff || (cp >= 0x2000 && cp <= 0x200d) || (cp >= 0x2010 && cp <= 0x201f) || (cp >= 0x2032 && cp <= 0x2037) ? 1 : 2;
  });
  return n;
}

// 押した時点の日付でテンプレートを選んで文面を作る。X の上限を超えるときは曲名を「…」で縮める
function buildShareText(t, now, tags) {
  var y = parseInt(t.releaseDate.slice(0, 4), 10), m = parseInt(t.releaseDate.slice(5, 7), 10), d = parseInt(t.releaseDate.slice(8, 10), 10);
  var years = now.getFullYear() - y;
  var isReleaseDay = now.getMonth() + 1 === m && now.getDate() === d;
  var key = years <= 0 ? "thisYear"
    : !isReleaseDay ? "other"
    : t.debut ? "debut"
    : SHARE_ANNIVERSARIES.indexOf(years) >= 0 ? "anniversary" : "today";
  var url = "https://releasetune.com/track/" + t.id;
  var tagLine = tags.map(function (tag) { return "#" + tag; }).join(" ");
  var title = Array.from(t.title.replace(/ - Single$/, ""));
  for (var len = title.length; ; len--) {
    var shortTitle = title.slice(0, len).join("") + (len < title.length ? "…" : "");
    var vals = { date: m + "月" + d + "日", fullDate: y + "年" + m + "月" + d + "日", year: y, years: years, artist: t.artist, title: shortTitle,
      work: t.artist + (t.album ? "のアルバム" : "") + "「" + shortTitle + "」" };
    var body = SHARE_TEMPLATES[key].replace(/\{(\w+)\}/g, function (_, k) { return vals[k]; });
    var text = body + "\n\n" + tagLine + "\n";
    if (xLength(text) + 23 <= 280 || len <= 1) return text + url;
  }
}

(function () {
  var box = document.querySelector("[data-share-id]");
  if (!box) return;
  var track = {
    id: box.getAttribute("data-share-id"), title: box.getAttribute("data-share-title"), artist: box.getAttribute("data-share-artist"),
    releaseDate: box.getAttribute("data-share-date"), debut: box.hasAttribute("data-share-debut"),
    album: box.hasAttribute("data-share-album")
  };
  var title = track.title, artist = track.artist;
  var tag = artistHashtag(artist);

  function shareText(tags) {
    return buildShareText(track, new Date(), tags);
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
