<?php
// cron の共通処理: 二重起動の防止、所要時間の計測、ログ（公開フォルダの外、月ごとのファイル）

require_once __DIR__ . '/http.php';

// $job(array $args) が返した結果（配列）に所要時間を足してログと標準出力に書く。例外なら終了コード1
function cron_main(string $name, callable $job): void
{
    if (PHP_SAPI !== 'cli') {
        exit(1);
    }
    $logDir = config('log_dir');
    if (!is_dir($logDir)) {
        mkdir($logDir, 0700, true);
    }
    // 前回の実行が終わっていなければ何もしない（ロックはプロセスが終われば自動で外れる）
    $lock = fopen("{$logDir}/{$name}.lock", 'c');
    if (!flock($lock, LOCK_EX | LOCK_NB)) {
        cron_log($name, ['message' => 'Skipped: previous run is still running']);
        exit(0);
    }
    $startedAt = microtime(true);
    $code = 0;
    try {
        $result = $job(array_slice($GLOBALS['argv'], 1));
    } catch (Throwable $e) {
        $result = ['error' => get_class($e) . ': ' . $e->getMessage()];
        $code = 1;
    }
    $result['elapsedMs'] = (int) round((microtime(true) - $startedAt) * 1000);
    cron_log($name, $result);
    exit($code);
}

function cron_log(string $name, array $data): void
{
    $logDir = config('log_dir');
    $line = json_encode(['at' => date('c')] + $data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    file_put_contents("{$logDir}/{$name}-" . date('Y-m') . '.log', $line . "\n", FILE_APPEND | LOCK_EX);
    echo $line, "\n";
    // 12か月より古いログは消す（ヘテムルの cron では rm が使えないので PHP で消す）
    $files = glob("{$logDir}/{$name}-*.log") ?: [];
    sort($files);
    foreach (array_slice($files, 0, max(0, count($files) - 12)) as $old) {
        unlink($old);
    }
}

// サイトのデータ取得キャッシュを消す（第1段階は Vercel の /api/revalidate。第2段階で revalidate_url を空にする）
function revalidate_site(): bool
{
    $url = config('revalidate_url');
    $secret = config('cron_secret');
    if ($url === '' || $secret === '') {
        return false;
    }
    $res = http_request('POST', $url, ["Authorization: Bearer {$secret}"], '', 30);
    return $res['status'] === 200;
}
