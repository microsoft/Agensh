"""Apply native Code Mode defaults and the Codex model-request text budget."""

import json


def limit_tool_outputs(payload, budget):
    """Bound UTF-8 text across each Responses tool result, including its notice.

    Images, call IDs and other protocol fields stay intact. The native catalog
    remains useful for history management, but its approximate byte policy
    cannot supply this final model-request ceiling.
    """
    if budget <= 0 or not isinstance(payload.get('input'), list):
        return False
    changed = False
    notice = '\n[Tool output truncated to the configured byte budget.]\n'

    def bounded(text, allowance, marker=notice):
        raw = text.encode('utf-8')
        if len(raw) <= allowance:
            return text
        if allowance <= 0:
            return ''
        marker = marker if allowance >= len(marker.encode()) else '.'
        available = allowance - len(marker.encode())
        head = (available + 1) // 2
        tail = available // 2
        return (raw[:head].decode('utf-8', errors='ignore') + marker +
                (raw[-tail:].decode('utf-8', errors='ignore') if tail else ''))

    for item in payload['input']:
        if not isinstance(item, dict) or item.get('type') not in ('function_call_output', 'custom_tool_call_output'):
            continue
        result = item.get('output')
        if isinstance(result, str):
            value = bounded(result, budget)
            if value != result:
                item['output'] = value
                changed = True
        elif isinstance(result, list):
            texts = [part for part in result if isinstance(part, dict)
                     and part.get('type') in ('input_text', 'output_text', 'text')
                     and isinstance(part.get('text'), str)]
            if sum(len(part['text'].encode('utf-8')) for part in texts) <= budget:
                continue
            marker = notice if budget >= len(notice.encode()) else '.'
            remaining = budget - len(marker.encode())
            limited = []
            for part in result:
                if isinstance(part, dict) and part.get('type') in ('input_text', 'output_text', 'text') \
                        and isinstance(part.get('text'), str):
                    value = bounded(part['text'], remaining, '')
                    remaining -= len(value.encode('utf-8'))
                    if value != part['text']:
                        part = {**part, 'text': value}
                        changed = True
                limited.append(part)
            limited.append({'type': texts[0]['type'], 'text': marker})
            item['output'] = limited
    return changed


def _kind(item):
    namespace, name = item.get('namespace'), item.get('name')
    if item.get('type') == 'custom_tool_call' and name in ('exec', 'functions.exec') \
            and namespace in (None, 'functions'):
        return 'exec'
    if item.get('type') == 'function_call' and name in ('wait', 'functions.wait') \
            and namespace in (None, 'functions'):
        return 'wait'


def _default_input(item, tokens):
    kind = _kind(item)
    key = 'input' if kind == 'exec' else 'arguments'
    original = item.get(key)
    if not kind or not isinstance(original, str):
        return None
    if kind == 'wait':
        try:
            arguments = json.loads(original)
        except ValueError:
            return None
        if not isinstance(arguments, dict) or arguments.get('max_tokens') is not None:
            return None
        arguments['max_tokens'] = tokens
        return key, json.dumps(arguments, separators=(',', ':'))
    first, separator, source = original.partition('\n')
    if first.lstrip().startswith('// @exec:'):
        try:
            pragma = json.loads(first.split('// @exec:', 1)[1])
        except ValueError:
            return None
        if not isinstance(pragma, dict) or pragma.get('max_output_tokens') is not None:
            return None
        pragma['max_output_tokens'] = tokens
        return key, '// @exec: ' + json.dumps(pragma, separators=(',', ':')) + separator + source
    return key, '// @exec: ' + json.dumps({'max_output_tokens': tokens}) + '\n' + original


def advertise_defaults(payload, tokens):
    if tokens <= 0:
        return False
    changed = False

    def update(tools, namespace=''):
        nonlocal changed
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get('name', '')
            if tool.get('type') == 'namespace':
                update(tool.get('tools', []), name)
            elif namespace == 'functions' and name in ('exec', 'wait'):
                def descriptions(value):
                    nonlocal changed
                    if isinstance(value, dict):
                        for key, text in value.items():
                            if key == 'description' and isinstance(text, str):
                                updated = text.replace('Defaults to 10000 tokens', f'Defaults to {tokens} tokens')
                                if updated != text:
                                    value[key] = updated
                                    changed = True
                            elif isinstance(text, (dict, list)):
                                descriptions(text)
                    elif isinstance(value, list):
                        for item in value:
                            descriptions(item)
                descriptions(tool)
    update(payload.get('tools') or [])
    for item in payload.get('input') or []:
        if isinstance(item, dict) and item.get('type') == 'additional_tools':
            update(item.get('tools', []))
    return changed


def response_defaults(body, content_type, tokens):
    """Keep SSE argument fragments and final items consistent; explicit caps win."""
    if tokens <= 0:
        return body
    streaming = 'event-stream' in content_type.lower()
    try:
        if streaming:
            lines = body.decode('utf-8').splitlines(keepends=True)
            records = []
            for index, line in enumerate(lines):
                if line.startswith('data:'):
                    try:
                        records.append((index, json.loads(line[5:].strip())))
                    except ValueError:
                        pass
        else:
            records = [(0, json.loads(body))]
    except (ValueError, UnicodeError):
        return body
    calls, ids, delta_indexes = {}, {}, set()
    for _, record in records:
        if not isinstance(record, dict):
            continue
        if isinstance(record.get('item'), dict) and _kind(record['item']):
            item = record['item']
            index = record.get('output_index', item.get('id'))
            if item.get('id'):
                ids[item['id']] = index
            if item.get('input') or item.get('arguments'):
                calls[index] = item
        response = record.get('response', record)
        if isinstance(response, dict):
            output = response.get('output')
            for index, item in enumerate(output if isinstance(output, list) else []):
                if isinstance(item, dict) and _kind(item):
                    calls[index] = item
                    if item.get('id'):
                        ids[item['id']] = index
        if record.get('type') in ('response.custom_tool_call_input.delta', 'response.function_call_arguments.delta'):
            delta_indexes.add(record.get('output_index', ids.get(record.get('item_id'))))
    changes = {index: change for index, item in calls.items()
               if (change := _default_input(item, tokens)) is not None}
    if not changes:
        return body
    emitted = set()
    for line_index, record in records:
        if not isinstance(record, dict):
            continue
        index = record.get('output_index', ids.get(record.get('item_id')))
        event = record.get('type', '')
        if index in changes:
            key, value = changes[index]
            if event in ('response.custom_tool_call_input.delta', 'response.function_call_arguments.delta'):
                record['delta'] = value if index not in emitted else ''
                emitted.add(index)
            elif event in ('response.custom_tool_call_input.done', 'response.function_call_arguments.done'):
                record[key] = value
            elif event == 'response.output_item.done' and isinstance(record.get('item'), dict):
                record['item'][key] = value
            elif event == 'response.output_item.added' and isinstance(record.get('item'), dict):
                record['item'][key] = '' if index in delta_indexes else value
        response = record.get('response', record)
        if isinstance(response, dict):
            output = response.get('output')
            for output_index, item in enumerate(output if isinstance(output, list) else []):
                if output_index in changes and isinstance(item, dict) and _kind(item):
                    key, value = changes[output_index]
                    item[key] = value
        if streaming:
            ending = '\r\n' if lines[line_index].endswith('\r\n') else '\n'
            lines[line_index] = 'data: ' + json.dumps(record, ensure_ascii=False, separators=(',', ':')) + ending
    return ''.join(lines).encode() if streaming else json.dumps(records[0][1]).encode()
