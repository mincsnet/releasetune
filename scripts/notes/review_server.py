"""
review_server.py — 紹介文のレビュー画面（ローカル専用）
======================================================
http://localhost:8787 で開く（環境変数 PORT で変更可）。本番サイト（Next.js）とは完全に別のプログラムで、デプロイされない。
127.0.0.1 にだけ待ち受け、他サイトからの書き込み要求（Origin/Host が違うもの）は拒否する。

- バッチ（取り込んだ日）ごとに、要確認の記事を表示
- 「承認して公開」: tracks の note・note_long・note_source_title・note_source_url を更新し note_verified=true
- 「書き直し依頼」: 次回の執筆で、コメントを踏まえて書き直す
- 「掲載しない」: 以後は執筆しない
- 要確認がすべて済んだら「残りを一括承認して公開」

使い方:
    python3 scripts/notes/review_server.py
"""

import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import revalidate_site
from review_ops import approve_rest, batch_articles, decide, list_batches

HOST, PORT = "127.0.0.1", int(os.getenv("PORT", "8787"))
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


# ── HTTP ─────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        # DNSリバインディング対策
        return self.headers.get("Host", "") in ALLOWED_HOSTS

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden", "text/plain")
        u = urlparse(self.path)
        try:
            if u.path == "/":
                return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            if u.path == "/api/batches":
                return self._json(200, list_batches())
            if u.path == "/api/batch":
                return self._json(200, batch_articles(parse_qs(u.query)["id"][0]))
            self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_POST(self):
        origin = self.headers.get("Origin", "")
        if not self._host_ok() or (origin and origin.split("://", 1)[-1] not in ALLOWED_HOSTS) \
                or not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send(403, b"forbidden", "text/plain")
        try:
            p = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            if self.path == "/api/decide":
                r = decide(p)
                if r["status"] == "published":
                    revalidate_site()
                return self._json(200, r)
            if self.path == "/api/approve_rest":
                r = approve_rest(p["batch_id"])
                if r["articles"]:
                    revalidate_site()
                return self._json(200, r)
            self._send(404, b"not found", "text/plain")
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        if self.command == "POST":
            sys.stderr.write(f"{self.command} {self.path}\n")


PAGE = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>紹介文レビュー</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--text:#1d1d1f;--mute:#6e6e73;--border:#e2e0db;--accent:#b8862b;--ok:#2f7d4f;--warn:#b54a2a;--chip:#efece6}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--card:#1c1c1e;--text:#f2f2f2;--mute:#9a9aa0;--border:#333;--accent:#d6a64b;--ok:#5fbf87;--warn:#e07a5a;--chip:#2a2a2d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.7 -apple-system,"Hiragino Sans",sans-serif}
header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:1rem;margin:0}select,button,textarea,input{font:inherit;color:inherit}
select{padding:4px 8px;border:1px solid var(--border);border-radius:6px;background:var(--card)}
main{max-width:920px;margin:0 auto;padding:16px}
.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.stats{color:var(--mute);font-size:.85rem}
.banner{background:#b54a2a22;border:1px solid var(--warn);padding:8px 12px;border-radius:8px;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:14px}
.card.done{opacity:.55}
.head{display:flex;gap:12px}.head img{width:64px;height:64px;border-radius:6px;object-fit:cover;flex:none;background:var(--chip)}
.title{font-weight:700}.title a{color:var(--accent)}
.tracks{font-size:.82rem;color:var(--mute)}
.badge{display:inline-block;font-size:.72rem;padding:1px 8px;border-radius:10px;background:var(--chip);margin-left:6px}
.badge.review{background:var(--accent);color:#fff}.badge.published{background:var(--ok);color:#fff}.badge.rewrite,.badge.rejected{background:var(--warn);color:#fff}
.issues{color:var(--warn);font-size:.85rem;margin:8px 0 0;padding-left:18px}
label{display:block;font-size:.8rem;color:var(--mute);margin-top:10px}
textarea{width:100%;border:1px solid var(--border);border-radius:6px;padding:8px;background:var(--bg);resize:vertical}
.count{float:right}.count.over{color:var(--warn);font-weight:700}
details{margin-top:8px;font-size:.85rem}summary{cursor:pointer;color:var(--mute)}
.facts li{margin-bottom:4px}.facts q{color:var(--mute)}
pre{white-space:pre-wrap;background:var(--bg);padding:8px;border-radius:6px;max-height:320px;overflow:auto;font:inherit;font-size:.82rem}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
.actions input{flex:1;min-width:200px;padding:6px 8px;border:1px solid var(--border);border-radius:6px;background:var(--bg)}
button{padding:6px 14px;border-radius:6px;border:1px solid var(--border);background:var(--card);cursor:pointer}
button.primary{background:var(--ok);border-color:var(--ok);color:#fff}button.danger{color:var(--warn)}
button:disabled{opacity:.4;cursor:default}
.msg{font-size:.85rem;color:var(--mute)}
</style></head><body>
<header><h1>ReleaseTune 紹介文レビュー</h1>
<select id="batch"></select>
<label style="margin:0"><input type="checkbox" id="all"> すべて表示</label>
<span class="stats" id="stats"></span></header>
<main><div id="banner"></div><div class="bar"><button id="rest" class="primary" disabled>残りを一括承認して公開</button><span class="msg" id="restmsg"></span></div><div id="list"></div></main>
<script>
const SHORT_MAX=60, LONG_MIN=150, LONG_MAX=400;
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let batches=[], articles=[];
async function api(path,body){const r=await fetch(path,body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
async function loadBatches(){batches=await api("/api/batches");const sel=$("#batch");const cur=sel.value;
 sel.innerHTML=batches.map(b=>`<option value="${esc(b.batch_id)}">${esc(b.batch_id)}（要確認 ${b.need_review||0} / 全 ${b.articles}）</option>`).join("")||"<option>バッチなし</option>";
 if(cur&&batches.some(b=>b.batch_id===cur))sel.value=cur}
async function loadBatch(){const id=$("#batch").value;if(!id||!batches.length){$("#list").innerHTML="<p class=msg>下書きはまだありません。</p>";return}
 articles=await api("/api/batch?id="+encodeURIComponent(id));render()}
function counter(el,min,max){const n=el.value.trim().length;const c=el.parentElement.querySelector(".count");c.textContent=n+"字";c.classList.toggle("over",n>max||(n>0&&n<min))}
function render(){const b=batches.find(x=>x.batch_id===$("#batch").value)||{};
 $("#stats").textContent=`公開 ${b.published||0} / 要確認 ${b.need_review||0} / 抜き取り外 ${b.unsampled||0} / 書き直し ${b.rewrite||0} / 掲載しない ${b.rejected||0} / 見送り ${b.insufficient||0}`;
 const sent=articles.filter(a=>a.status==="rewrite"||a.status==="rejected").length;
 $("#banner").innerHTML=sent?`<div class="banner">抜き取り分で差し戻しが ${sent} 件あります。「すべて表示」で残りも確認することをおすすめします。</div>`:"";
 const pending=articles.filter(a=>a.status==="drafted"&&a.review_required).length, rest=articles.filter(a=>a.status==="drafted"&&!a.review_required).length;
 $("#rest").disabled=pending>0||rest===0;$("#restmsg").textContent=rest?(pending?`要確認があと ${pending} 件`:`抜き取り外 ${rest} 件`):"";
 const all=$("#all").checked, shown=articles.filter(a=>all||a.review_required||a.status!=="drafted");
 $("#list").innerHTML=shown.map((a,i)=>card(a,articles.indexOf(a))).join("")||"<p class=msg>要確認の記事はありません。</p>";
 document.querySelectorAll("textarea[data-min]").forEach(t=>{counter(t,+t.dataset.min,+t.dataset.max);t.oninput=()=>counter(t,+t.dataset.min,+t.dataset.max)})}
function card(a,i){const t=a.tracks[0]||{};const done=a.status!=="drafted";
 const badge=done?`<span class="badge ${a.status}">${{published:"公開済み",rewrite:"書き直し依頼",rejected:"掲載しない",insufficient:"見送り"}[a.status]}</span>`:(a.review_required?`<span class="badge review">要確認</span>`:`<span class="badge">抜き取り外</span>`);
 const issues=(a.issues||[]).filter(x=>x.type!=="edited_by_reviewer");
 return `<div class="card ${done?"done":""}" id="a${i}"><div class="head">${t.jacket?`<img src="${esc(t.jacket)}" alt="">`:"<img alt=''>"}<div>
 <div class="title"><a href="${esc(a.wiki_url)}" target="_blank" rel="noopener">${esc(a.wiki_title)}</a>${badge}</div>
 <div class="tracks">${a.tracks.map(x=>`${esc(x.title)} / ${esc(x.artist)}（${esc(x.release_date)}）`).join("<br>")}</div></div></div>
 ${issues.length?`<ul class="issues">${issues.map(x=>`<li>${esc(x.detail)}</li>`).join("")}</ul>`:""}
 ${a.reviewer_comment?`<p class="msg">コメント: ${esc(a.reviewer_comment)}</p>`:""}
 <label>短文（カード・注目曲用、${SHORT_MAX}字以内）<span class="count"></span><textarea data-min="1" data-max="${SHORT_MAX}" rows="2" id="s${i}" ${done?"disabled":""}>${esc(a.note_short)}</textarea></label>
 <label>長文（楽曲詳細用、${LONG_MIN}〜${LONG_MAX}字、空でも可）<span class="count"></span><textarea data-min="${LONG_MIN}" data-max="${LONG_MAX}" rows="6" id="l${i}" ${done?"disabled":""}>${esc(a.note_long)}</textarea></label>
 <details><summary>根拠（${(a.facts||[]).length}件）</summary><ul class="facts">${(a.facts||[]).map(f=>`<li>${esc(f.claim)}<br><q>${esc(f.source)}</q></li>`).join("")}</ul></details>
 <details><summary>出典テキスト</summary><pre>${esc(a.source_text)}</pre></details>
 ${done?"":`<div class="actions"><input id="c${i}" placeholder="コメント（書き直し依頼では必須）"><button class="primary" onclick="act(${i},'approve')">承認して公開</button><button onclick="act(${i},'rewrite')">書き直し依頼</button><button class="danger" onclick="act(${i},'reject')">掲載しない</button></div>`}
 </div>`}
async function act(i,action){const a=articles[i];
 const body={batch_id:$("#batch").value,wiki_title:a.wiki_title,action,note_short:$("#s"+i).value,note_long:$("#l"+i).value,comment:$("#c"+i).value};
 if(action==="reject"&&!confirm("「"+a.wiki_title+"」を掲載しないにしますか？"))return;
 try{const r=await api("/api/decide",body);a.status=r.status;a.note_short=body.note_short;a.note_long=body.note_long;a.reviewer_comment=body.comment;await loadBatches();render()}catch(e){alert(e.message)}}
$("#rest").onclick=async()=>{const warn=articles.some(a=>a.status==="rewrite"||a.status==="rejected");
 if(!confirm((warn?"抜き取り分に差し戻しがあります。それでも":"")+"残りを一括承認して公開しますか？"))return;
 try{const r=await api("/api/approve_rest",{batch_id:$("#batch").value});alert(`${r.articles}記事（${r.tracks}曲）を公開しました`);await loadBatches();await loadBatch()}catch(e){alert(e.message)}};
$("#batch").onchange=loadBatch;$("#all").onchange=render;
(async()=>{try{await loadBatches();await loadBatch()}catch(e){$("#list").innerHTML="<p class=msg>読み込みに失敗しました: "+esc(e.message)+"</p>"}})();
</script></body></html>"""


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"レビュー画面: http://localhost:{PORT}  （Ctrl+C で終了）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
