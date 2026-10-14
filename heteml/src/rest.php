<?php
// 手元のスクリプト（scripts/notes/common.py の sb_*）が送る PostgREST 形式の条件を SQL に直す（api/db.php 用）。
// スクリプトが実際に使う書き方（eq / neq / gt / gte / lt / lte / like / ilike / is / in と not.、or、order、select、limit、offset）
// だけを受け付け、それ以外はエラーにする（推測で解釈しない）。
// テーブル名・列名は schema.php の許可リストで確かめ、値はすべてプレースホルダで渡す。

// PostgREST（Supabase）の1回あたりの最大行数と同じ。スクリプトはこれを前提にページングしている
const REST_MAX_ROWS = 1000;

const REST_RESERVED = ['select', 'order', 'limit', 'offset', 'or'];

function rest_select(string $table, array $params): array
{
    $cols = rest_columns($table, (string) ($params['select'] ?? '*'));
    [$where, $values] = rest_where($table, $params);
    $order = isset($params['order']) ? ' ORDER BY ' . rest_order($table, (string) $params['order']) : '';
    $limit = min(REST_MAX_ROWS, max(0, (int) ($params['limit'] ?? REST_MAX_ROWS)));
    $offset = max(0, (int) ($params['offset'] ?? 0));

    $sql = "SELECT {$cols} FROM `{$table}`{$where}{$order} LIMIT ? OFFSET ?";
    $stmt = db()->prepare($sql);
    $stmt->execute([...$values, $limit, $offset]);
    return array_map(fn($row) => decode_row($table, $row), $stmt->fetchAll());
}

// 主キーが同じ行があれば、送られてきた列だけ上書きする（PostgREST の resolution=merge-duplicates）
function rest_upsert(string $table, array $rows, string $onConflict): int
{
    $pk = table_def($table)['pk'];
    if ($onConflict !== $pk) {
        throw new InvalidArgumentException("on_conflict は主キー（{$pk}）だけに対応しています");
    }
    $pdo = db();
    $pdo->beginTransaction();
    try {
        foreach ($rows as $row) {
            $row = rest_object_to_array($row, '行');
            if (!array_key_exists($pk, $row)) {
                throw new InvalidArgumentException("行に {$pk} がありません");
            }
            $cols = array_keys($row);
            $values = [];
            foreach ($row as $col => $v) {
                $values[] = encode_value(column_type($table, $col), $v);
            }
            $updates = array_map(fn($c) => "`{$c}` = new.`{$c}`", array_values(array_diff($cols, [$pk])));
            if (!$updates) {
                $updates = ["`{$pk}` = new.`{$pk}`"];
            }
            $sql = "INSERT INTO `{$table}` (" . implode(', ', array_map(fn($c) => "`{$c}`", $cols)) . ')'
                . ' VALUES (' . implode(', ', array_fill(0, count($cols), '?')) . ') AS new'
                . ' ON DUPLICATE KEY UPDATE ' . implode(', ', $updates);
            $pdo->prepare($sql)->execute($values);
        }
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }
    return count($rows);
}

function rest_update(string $table, array $filters, $patch): int
{
    $patch = rest_object_to_array($patch, 'patch');
    if (!$patch) {
        throw new InvalidArgumentException('patch が空です');
    }
    [$where, $values] = rest_where($table, $filters);
    if ($where === '') {
        // 条件なしの更新（全行の書き換え）は受け付けない
        throw new InvalidArgumentException('更新には条件が必要です');
    }
    $sets = [];
    $setValues = [];
    foreach ($patch as $col => $v) {
        $sets[] = '`' . rest_column($table, $col) . '` = ?';
        $setValues[] = encode_value(column_type($table, $col), $v);
    }
    $stmt = db()->prepare("UPDATE `{$table}` SET " . implode(', ', $sets) . $where);
    $stmt->execute([...$setValues, ...$values]);
    return $stmt->rowCount();
}

// ── 条件の組み立て ──────────────────────────────────────────

function rest_where(string $table, array $params): array
{
    $parts = [];
    $values = [];
    foreach ($params as $key => $expr) {
        if (!is_string($expr)) {
            throw new InvalidArgumentException("条件は文字列で指定してください: {$key}");
        }
        if ($key === 'or') {
            [$sql, $v] = rest_or($table, $expr);
        } elseif (in_array($key, REST_RESERVED, true)) {
            continue;
        } else {
            [$sql, $v] = rest_condition($table, rest_column($table, $key), $expr);
        }
        $parts[] = $sql;
        array_push($values, ...$v);
    }
    return [$parts ? ' WHERE ' . implode(' AND ', $parts) : '', $values];
}

// "(spotify.is.null,spotify.not.like.*open.spotify.com/track/*)"
function rest_or(string $table, string $expr): array
{
    $terms = rest_split(rest_strip_parens($expr), false);
    $parts = [];
    $values = [];
    foreach ($terms as $term) {
        $dot = strpos($term, '.');
        if ($dot === false) {
            throw new InvalidArgumentException("or の条件の書き方が不正です: {$term}");
        }
        [$sql, $v] = rest_condition($table, rest_column($table, substr($term, 0, $dot)), substr($term, $dot + 1));
        $parts[] = $sql;
        array_push($values, ...$v);
    }
    if (!$parts) {
        throw new InvalidArgumentException('or の中が空です');
    }
    return ['(' . implode(' OR ', $parts) . ')', $values];
}

// "eq.X" / "not.is.null" / "in.(a,"b,c")" → [SQL, 値]
function rest_condition(string $table, string $column, string $expr): array
{
    $type = column_type($table, $column);
    $negate = false;
    if (strncmp($expr, 'not.', 4) === 0) {
        $negate = true;
        $expr = substr($expr, 4);
    }
    $dot = strpos($expr, '.');
    if ($dot === false) {
        throw new InvalidArgumentException("条件の書き方が不正です: {$column}={$expr}");
    }
    $op = substr($expr, 0, $dot);
    $val = substr($expr, $dot + 1);
    $col = "`{$column}`";

    $comparisons = ['eq' => '=', 'neq' => '<>', 'gt' => '>', 'gte' => '>=', 'lt' => '<', 'lte' => '<='];
    if (isset($comparisons[$op])) {
        $sql = "{$col} {$comparisons[$op]} ?";
        $values = [encode_value($type, $val)];
    } elseif ($op === 'like') {
        // PostgREST は * をワイルドカード（%）として扱う
        $sql = "{$col} LIKE ?";
        $values = [str_replace('*', '%', $val)];
    } elseif ($op === 'ilike') {
        $sql = "LOWER({$col}) LIKE LOWER(?)";
        $values = [str_replace('*', '%', $val)];
    } elseif ($op === 'is') {
        $is = ['null' => 'IS NULL', 'true' => '= 1', 'false' => '= 0'];
        if (!isset($is[$val])) {
            throw new InvalidArgumentException("is の値は null / true / false です: {$val}");
        }
        $sql = "{$col} {$is[$val]}";
        $values = [];
    } elseif ($op === 'in') {
        $list = rest_split(rest_strip_parens($val), true);
        if (!$list) {
            $sql = '0 = 1';
            $values = [];
        } else {
            $sql = "{$col} IN (" . implode(', ', array_fill(0, count($list), '?')) . ')';
            $values = array_map(fn($v) => encode_value($type, $v), $list);
        }
    } else {
        throw new InvalidArgumentException("使えない演算子です: {$op}");
    }
    return [$negate ? "NOT ({$sql})" : $sql, $values];
}

// "updated_at.asc,track_id.asc" → PostgreSQL と同じ並び（昇順は NULL が最後、降順は NULL が最初）
function rest_order(string $table, string $order): string
{
    $parts = [];
    foreach (explode(',', $order) as $item) {
        $bits = explode('.', trim($item));
        $col = rest_column($table, array_shift($bits));
        $dir = 'ASC';
        $nullsLast = null;
        foreach ($bits as $b) {
            if ($b === 'asc' || $b === 'desc') {
                $dir = strtoupper($b);
            } elseif ($b === 'nullsfirst' || $b === 'nullslast') {
                $nullsLast = $b === 'nullslast';
            } else {
                throw new InvalidArgumentException("order の書き方が不正です: {$item}");
            }
        }
        $nullsLast ??= $dir === 'ASC';
        // Supabase は文字列を辞書順（en_US）で並べていた（例: Fantasista → FEARS）。列の照合（utf8mb4_bin）の
        // ままだと文字コード順（FEARS → Fantasista）になるので、並べるときだけ辞書順の照合を使う
        $sortKey = column_type($table, $col) === 'text' ? "`{$col}` COLLATE utf8mb4_0900_ai_ci" : "`{$col}`";
        $parts[] = "(`{$col}` IS NULL) " . ($nullsLast ? 'ASC' : 'DESC') . ", {$sortKey} {$dir}";
    }
    return implode(', ', $parts);
}

function rest_columns(string $table, string $select): string
{
    if (trim($select) === '*') {
        $cols = array_keys(table_def($table)['columns']);
    } else {
        $cols = array_map(fn($c) => rest_column($table, trim($c)), explode(',', $select));
    }
    return implode(', ', array_map(fn($c) => "`{$c}`", $cols));
}

function rest_column(string $table, string $column): string
{
    column_type($table, $column); // 許可リストにない列はここでエラー
    return $column;
}

// ── 文字列の分解 ────────────────────────────────────────────

function rest_strip_parens(string $s): string
{
    if (strlen($s) < 2 || $s[0] !== '(' || substr($s, -1) !== ')') {
        throw new InvalidArgumentException("丸かっこで囲んでください: {$s}");
    }
    return substr($s, 1, -1);
}

// カンマで区切る。ダブルクォートと丸かっこの中のカンマでは区切らない。
// $unquote が true なら値を囲むダブルクォートとバックスラッシュのエスケープを外す（in の値用）
function rest_split(string $s, bool $unquote): array
{
    if ($s === '') {
        return [];
    }
    $out = [];
    $cur = '';
    $inQuote = false;
    $depth = 0;
    $len = strlen($s);
    for ($i = 0; $i < $len; $i++) {
        $ch = $s[$i];
        if ($inQuote) {
            if ($ch === '\\' && $i + 1 < $len) {
                $cur .= $unquote ? $s[++$i] : $ch . $s[++$i];
            } elseif ($ch === '"') {
                $inQuote = false;
                if (!$unquote) {
                    $cur .= $ch;
                }
            } else {
                $cur .= $ch;
            }
            continue;
        }
        if ($ch === '"') {
            $inQuote = true;
            if (!$unquote) {
                $cur .= $ch;
            }
            continue;
        }
        if ($ch === '(') {
            $depth++;
        } elseif ($ch === ')') {
            $depth--;
        } elseif ($ch === ',' && $depth === 0) {
            $out[] = $cur;
            $cur = '';
            continue;
        }
        $cur .= $ch;
    }
    $out[] = $cur;
    return $out;
}

function rest_object_to_array($v, string $label): array
{
    if ($v instanceof stdClass) {
        return get_object_vars($v);
    }
    if (is_array($v)) {
        return $v;
    }
    throw new InvalidArgumentException("{$label} はオブジェクトで指定してください");
}
