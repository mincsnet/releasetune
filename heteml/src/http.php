<?php
// 外部 API を呼ぶための HTTP（curl）

// 戻り値: ['status' => int, 'headers' => [小文字の名前 => 値], 'body' => string]。通信自体の失敗は status 0
function http_request(string $method, string $url, array $headers = [], ?string $body = null, int $timeout = 20): array
{
    $responseHeaders = [];
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $method,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT        => $timeout,
        CURLOPT_ENCODING       => '', // gzip 等を受け付けて自動で展開する
        CURLOPT_USERAGENT      => 'ReleaseTune/1.0 (+https://releasetune.com/)',
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$responseHeaders) {
            $parts = explode(':', $line, 2);
            if (count($parts) === 2) {
                $responseHeaders[strtolower(trim($parts[0]))] = trim($parts[1]);
            }
            return strlen($line);
        },
    ]);
    if ($body !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
    }
    $resBody = curl_exec($ch);
    $status = $resBody === false ? 0 : (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    return ['status' => $status, 'headers' => $responseHeaders, 'body' => $resBody === false ? '' : $resBody];
}

function http_json(array $res)
{
    return json_decode($res['body'], true);
}
