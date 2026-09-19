"""Bounded source excerpts, preserving late functions and visible UI text."""
import ast
from html.parser import HTMLParser
import re


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        value = ' '.join(data.split())
        if value and not self.hidden:
            self.text.append(value)


def redact_literals(text):
    # Exclude literal credentials while retaining variable/env references and control flow.
    return re.sub(
        r'''(?im)((?:[\w]*?(?:api_key|token|secret|password)[\w]*)\s*[:=]\s*)(["'])([^\r\n]*?)\2''',
        lambda m: m[1] + m[2] + '[REDACTED]' + m[2], text,
    )


def behavior_anchors(tree, text):
    """Literal input formats and control predicates survive abbreviated function bodies."""
    rows = []
    calls = {'glob', 'rglob', 'add_argument', 'getenv', 'route', 'read_excel', 'read_csv'}
    for node in sorted(ast.walk(tree), key=lambda n: getattr(n, 'lineno', 0)):
        fragment = None
        if isinstance(node, ast.Call):
            name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
            if name in calls:
                fragment = ast.get_source_segment(text, node)
        elif isinstance(node, ast.If):
            test = ast.get_source_segment(text, node.test)
            fragment = f'if {test}:'
        if fragment:
            priority = 0 if isinstance(node, ast.Call) else 1
            rows.append((priority, node.lineno, f'line {node.lineno}: ' + ' '.join(fragment.split())[:280]))
    return '\n'.join(row[2] for row in sorted(rows))


def _fit(text, budget):
    """Mark every abbreviation and keep both ends, including late definitions."""
    if len(text) <= budget:
        return text
    marker = '\n[... omitted ...]\n'
    if budget < len(marker):
        return marker.strip()[:budget]
    head = (budget - len(marker)) // 2
    tail = budget - len(marker) - head
    return text[:head] + marker + (text[-tail:] if tail else '')


def _allocations(lengths, budget, weights):
    """Weighted shares with unused space redistributed before rendering sections."""
    result = [0] * len(lengths)
    pending = set(range(len(lengths)))
    while pending and budget:
        unit = budget / sum(weights[index] for index in pending)
        for index in sorted(pending):
            amount = min(max(1, int(unit * weights[index])), lengths[index] - result[index], budget)
            result[index] += amount
            budget -= amount
            if result[index] == lengths[index]:
                pending.remove(index)
    return result


def _fit_anchors(text, budget):
    """Never splice a condition in half and accidentally change its meaning."""
    if len(text) <= budget:
        return text
    rows = text.splitlines()
    marker = '[... syntax rows omitted ...]'
    selected = {}
    remaining = max(0, budget - len(marker) - 1)
    order = [i for pair in zip(range(len(rows)), reversed(range(len(rows)))) for i in pair]
    for index in dict.fromkeys(order):
        if len(rows[index]) + 1 <= remaining:
            selected[index] = rows[index]
            remaining -= len(rows[index]) + 1
    return ('\n'.join(selected[i] for i in sorted(selected)) + '\n' + marker)[:budget]


class ShortenLiterals(ast.NodeTransformer):
    def visit_Constant(self, node):
        if not isinstance(node.value, str) or len(node.value) <= 1600:
            return node
        parser = VisibleText()
        if '<html' in node.value.lower() or '<script' in node.value.lower():
            try:
                parser.feed(node.value)
            except Exception:
                pass
        content = '\n'.join(dict.fromkeys(parser.text)) if parser.text else node.value[:1000]
        return ast.copy_location(ast.Constant(value='[abbreviated literal]\n' + content[:3200]), node)


def excerpts(text, suffix, budget, *, focus_symbols=()):
    text = redact_literals(text)
    if len(text) <= budget:
        return text, False
    if suffix != '.py':
        half = (budget - 40) // 2
        return text[:half] + '\n[... middle omitted ...]\n' + text[-half:], True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text[:budget], True
    compact = ast.unparse(ShortenLiterals().visit(ast.parse(text)))
    label = '[Python syntax retained; oversized string literals abbreviated, not executable evidence]\n'
    if len(compact) + len(label) <= budget:
        return label + compact, True
    lines = text.splitlines()
    rows = [_fit('[module header]\n' + '\n'.join(lines[:60]), budget // 10)]
    ui = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and '<' in node.value:
            parser = VisibleText()
            try:
                parser.feed(node.value)
            except Exception:
                continue
            ui.extend(parser.text)
    if ui:
        rows.append(_fit('[visible interface text]\n' + '\n'.join(dict.fromkeys(ui)), budget // 6))
    nodes = sorted((n for n in ast.walk(tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), key=lambda n: n.lineno)
    blocks = []
    for node in nodes:
        start = min([node.lineno, *[d.lineno for d in node.decorator_list]])
        title = f'[lines {start}-{node.end_lineno}, {node.name}]\n'
        block = ast.unparse(ShortenLiterals().visit(ast.parse(ast.unparse(node))))
        blocks.append((title, block, behavior_anchors(node, text)))
    if not blocks:
        return _fit(text, budget), True
    remaining = max(0, budget - sum(map(len, rows)) - 2 * (len(rows) + len(blocks) - 1))
    weights = [8 if node.name in focus_symbols else 1 for node in nodes]
    shares = _allocations([len(title) + len(block) for title, block, _ in blocks], remaining, weights)
    for (title, block, anchors), share in zip(blocks, shares):
        if len(title) + len(block) <= share:
            rows.append(title + block)
            continue
        room = max(0, share - len(title))
        if anchors and room >= 160:
            label = '\n[selected conditions/calls]\n'
            anchor_budget = (room - len(label)) * 4 // 5
            block = (_fit(block, room - len(label) - anchor_budget) + label
                     + _fit_anchors(anchors, anchor_budget))
        else:
            block = _fit(block, room)
        rows.append(_fit(title + block, share))
    return '\n\n'.join(rows)[:budget], True
