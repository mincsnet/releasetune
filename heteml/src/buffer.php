<?php
// Buffer の API（GraphQL。https://developers.buffer.com/）。予約投稿に使う。
// 無料プランの上限: API キー1本、1日600回・15分150回、予約は1チャンネル10件まで（2026-11-02 時点）

require_once __DIR__ . '/http.php';

const BUFFER_API = 'https://api.buffer.com';

// 戻り値は応答の data。HTTP の失敗・GraphQL のエラーは例外にする
function buffer_graphql(string $query, array $variables = []): array
{
    $body = json_encode(['query' => $query, 'variables' => (object) $variables], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $res = http_request('POST', BUFFER_API, ['Content-Type: application/json', 'Authorization: Bearer ' . config('buffer_api_key')], $body, 30);
    $json = http_json($res);
    if ($res['status'] !== 200 || !empty($json['errors']) || !isset($json['data'])) {
        $detail = isset($json['errors']) ? implode(' / ', array_column($json['errors'], 'message')) : mb_substr($res['body'], 0, 300);
        throw new RuntimeException("Buffer API failed: {$res['status']} {$detail}");
    }
    return $json['data'];
}

// つないでいるチャンネルの一覧（config.php の buffer_channel_id を調べるため）。[['id', 'name', 'service', 'organization']]
function buffer_channels(): array
{
    $orgs = buffer_graphql('query { account { organizations { id name } } }')['account']['organizations'];
    $channels = [];
    foreach ($orgs as $org) {
        // ID は JSON の文字列としてそのまま埋める（GraphQL の文字列と同じ書き方）
        $data = buffer_graphql('query { channels(input: { organizationId: ' . json_encode($org['id']) . ' }) { id name service } }');
        foreach ($data['channels'] as $c) {
            $channels[] = $c + ['organization' => $org['name']];
        }
    }
    return $channels;
}

// $dueAt（Unix 時刻）に投稿する予約を作り、Buffer の投稿 ID を返す
function buffer_schedule_post(string $channelId, string $text, int $dueAt): string
{
    $query = 'mutation ($input: CreatePostInput!) { createPost(input: $input) {'
        . ' ... on PostActionSuccess { post { id dueAt } } ... on MutationError { message } } }';
    $data = buffer_graphql($query, ['input' => [
        'channelId'      => $channelId,
        'text'           => $text,
        'schedulingType' => 'automatic',
        'mode'           => 'customScheduled',
        'dueAt'          => gmdate('Y-m-d\TH:i:s.000\Z', $dueAt),
    ]]);
    $id = $data['createPost']['post']['id'] ?? null;
    if ($id === null) {
        throw new RuntimeException('Buffer createPost failed: ' . ($data['createPost']['message'] ?? json_encode($data, JSON_UNESCAPED_UNICODE)));
    }
    return $id;
}
