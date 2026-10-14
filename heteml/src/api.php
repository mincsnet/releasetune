<?php
// api/ 以下の共通処理: POST のみ・トークン認証・JSON の受け渡し

// $handler の戻り値を JSON で返す。入力の誤りは 400、それ以外の失敗は 500
function api_run(string $expectedToken, callable $handler): void
{
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
        api_respond(['error' => 'POST only'], 405);
        return;
    }
    if ($expectedToken === '' || !hash_equals($expectedToken, api_request_token())) {
        api_respond(['error' => 'Unauthorized'], 401);
        return;
    }
    try {
        $body = json_decode(file_get_contents('php://input') ?: 'null', false, 512, JSON_THROW_ON_ERROR);
        if (!$body instanceof stdClass) {
            throw new InvalidArgumentException('本文は JSON のオブジェクトで送ってください');
        }
        api_respond($handler($body));
    } catch (InvalidArgumentException | JsonException $e) {
        api_respond(['error' => $e->getMessage()], 400);
    } catch (Throwable $e) {
        error_log('[api] ' . $e);
        // 認証済みの呼び出し元（手元のスクリプト・Vercel）にだけ返るので、原因を伝える
        api_respond(['error' => get_class($e) . ': ' . $e->getMessage()], 500);
    }
}

function api_respond($data, int $status = 200): void
{
    http_response_code($status);
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
}

// Authorization: Bearer <token>。PHP の動かし方によっては Authorization ヘッダーが PHP に渡らないため、
// .htaccess で HTTP_AUTHORIZATION に移した値と、X-Api-Token ヘッダーも見る
function api_request_token(): string
{
    $auth = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
    if ($auth === '' && function_exists('apache_request_headers')) {
        $headers = array_change_key_case(apache_request_headers() ?: [], CASE_LOWER);
        $auth = $headers['authorization'] ?? '';
    }
    if (preg_match('/^Bearer\s+(\S+)$/i', $auth, $m)) {
        return $m[1];
    }
    return (string) ($_SERVER['HTTP_X_API_TOKEN'] ?? '');
}
