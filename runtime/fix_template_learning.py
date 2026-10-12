"""Learn generalized fix templates from mined edits and apply them to new statements.

Agglomerative clustering in the style of Getafix: edits with the same coarse shape are
merged pairwise while the anti-unified template stays executable and concrete enough.
A template records the projects and edits that support it. Suggestions are ranked by
cross-project support, then concreteness. No LLM and no project-specific rules.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass

from .fix_template_tree import anti_unify_edit, concrete_size, match, substitute

MIN_CONCRETE = 6


@dataclass
class Template:
    before: object
    after: object
    support: list           # edit indices
    projects: frozenset

    @property
    def concreteness(self) -> int:
        return concrete_size(self.before) + concrete_size(self.after)


def _shape(record):
    return record['before'].label, record['after'].label


def learn(records, *, min_concrete=MIN_CONCRETE, max_group=400):
    """Return templates supported by at least two edits."""
    groups = defaultdict(list)
    for index, record in enumerate(records):
        groups[_shape(record)].append(index)
    learned = []
    for indices in groups.values():
        if len(indices) < 2:
            continue
        clusters = [Template(records[i]['before'], records[i]['after'], [i], frozenset([records[i]['project']]))
                    for i in indices[:max_group]]
        learned.extend(_agglomerate(clusters, min_concrete))
    return [t for t in learned if len(t.support) >= 2]


def _merge(x, y, min_concrete):
    pair = anti_unify_edit((x.before, x.after), (y.before, y.after))
    if pair is None:
        return None
    merged = Template(pair[0], pair[1], x.support + y.support, x.projects | y.projects)
    return merged if concrete_size(pair[0]) >= min_concrete // 2 and merged.concreteness >= min_concrete else None


def _agglomerate(clusters, min_concrete):
    """Greedy: repeatedly merge the pair whose generalization keeps the most concrete structure.

    All intermediate merges are kept (template hierarchy). Candidate merges are cached in a max-heap; merging removes both parents and only
    the new cluster's merges are computed, so the cost is about O(n^2) anti-unifications.
    """
    alive = dict(enumerate(clusters))
    heap, counter = [], len(clusters)

    def push(i, j):
        merged = _merge(alive[i], alive[j], min_concrete)
        if merged:
            heapq.heappush(heap, (-merged.concreteness, i, j, merged))

    ids = list(alive)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            push(ids[a], ids[b])
    produced = []
    while heap:
        _, i, j, merged = heapq.heappop(heap)
        if i not in alive or j not in alive:
            continue
        produced.append(merged)  # every hierarchy level is a candidate template
        del alive[i], alive[j]
        alive[counter] = merged
        for other in list(alive):
            if other != counter:
                push(other, counter)
        counter += 1
    return produced


def rank_key(template):
    return (len(template.projects), len(template.support), template.concreteness)


def suggest(templates, statement, *, min_projects=1):
    """Best applicable template and its rewritten statement, or None. No-op rewrites are skipped."""
    for template in sorted(templates, key=rank_key, reverse=True):
        if len(template.projects) < min_projects:
            continue
        binding = match(template.before, statement)
        if binding is None:
            continue
        rewritten = substitute(template.after, binding)
        if rewritten.key != statement.key:
            return template, rewritten
    return None


def prune_by_clean_code(templates, clean_statements, *, max_ratio=1.0):
    """Drop templates whose 'before' matches unchanged code more often than fixes support it.

    Clean statements must come from training projects only (Getafix-style prevalence check).
    """
    kept = []
    for template in templates:
        hits = 0
        limit = max_ratio * len(template.support)
        for statement in clean_statements:
            if match(template.before, statement) is not None:
                hits += 1
                if hits > limit:
                    break
        if hits <= limit:
            kept.append(template)
    return kept
