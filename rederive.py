"""Rederive-inspired decision rehearsal, independently implemented and offline.

Text is authored by humans/Agents, not semantically verified by this module.
JSON files are editable: this is a learning gate, not authentication or DRM.
"""
import copy
import hashlib
import json
import re
import workflow


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 20000:
        raise ValueError(name + ' must be a nonempty string of at most 20000 characters')
    return value.strip()


def _strings(value, name):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError(name + ' must be a list of at most 30 strings')
    return [_text(x, name) for x in value]


def _reference(report, ref):
    if not isinstance(ref, dict) or set(ref) != {'file', 'start', 'end'}:
        raise ValueError('Reference must contain only file, start, end')
    file, start, end = ref['file'], ref['start'], ref['end']
    if not isinstance(file, str) or file not in report['snapshot']['files']:
        raise ValueError('Reference file outside scanned sources')
    source = report['snapshot']['files'][file]
    lines = source['text'].splitlines()
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError('Invalid reference line range')
    return dict(ref, quote='\n'.join(lines[start-1:end]), sha256=source['sha256'])


def create_card(report, spec):
    """Validate authored fields; never accept authored test/acceptance status."""
    allowed = {'id', 'requirement_id', 'problem', 'hints', 'constraints', 'reveal'}
    if not isinstance(spec, dict) or set(spec) - allowed:
        raise ValueError('Unknown decision card fields')
    card_id = _text(spec.get('id'), 'id')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', card_id):
        raise ValueError('Card id must be a short safe identifier')
    rid = spec.get('requirement_id')
    if rid not in {r['id'] for r in report['requirements']}:
        raise ValueError('Unknown card requirement')
    hints = _strings(spec.get('hints', []), 'hints')
    constraints = _strings(spec.get('constraints', []), 'constraints')
    if len(constraints) > len(hints):
        raise ValueError('Each progressive constraint needs a hint stage')
    reveal = spec.get('reveal')
    if not isinstance(reveal, dict) or set(reveal) - {'explanation', 'references', 'tradeoffs', 'unknowns', 'acceptance_checks'}:
        raise ValueError('Invalid reveal fields; execution status is derived, never authored')
    references = reveal.get('references')
    if not isinstance(references, list) or not 1 <= len(references) <= 30:
        raise ValueError('Reveal requires 1-30 source references')
    # Validate location now; quotes are always reconstructed from snapshot on reveal.
    for ref in references:
        _reference(report, ref)
    payload = {'id': card_id, 'requirement_id': rid, 'problem': _text(spec.get('problem'), 'problem'),
               'hints': hints, 'constraints': constraints,
               'reveal': {'explanation': _text(reveal.get('explanation'), 'explanation'),
                          'references': copy.deepcopy(references),
                          **{name: _strings(reveal.get(name, []), name)
                             for name in ('tradeoffs', 'unknowns', 'acceptance_checks')}},
               'input_snapshot': report['snapshot']['id'],
               'origin': 'human/Agent-authored rehearsal; no model called; source location is not semantic proof'}
    payload['card_sha256'] = _hash(payload)
    return payload


def import_cards(report, specs):
    if not isinstance(specs, list) or len(specs) > 100:
        raise ValueError('Expected up to 100 decision cards')
    cards = [create_card(report, spec) for spec in specs]
    if len({c['id'] for c in cards}) != len(cards):
        raise ValueError('Duplicate card id')
    return cards


def _context(report):
    return _hash({k: report.get(k, []) for k in ('snapshot', 'requirements', 'claims', 'runs', 'reviews')})


def _check_card(report, card):
    if card.get('input_snapshot') != report['snapshot']['id']:
        raise ValueError('Card snapshot mismatch; regenerate the card')
    if card.get('card_sha256') != _hash({k:v for k,v in card.items() if k != 'card_sha256'}):
        raise ValueError('Card changed; regenerate card and start a new session')
    # Revalidate imported persisted card structure.
    create_card(report, {k: card[k] for k in ('id', 'requirement_id', 'problem', 'hints', 'constraints', 'reveal')})


def start_session(report, card):
    _check_card(report, card)
    return {'schema': 1, 'card_id': card['id'], 'card_sha256': card['card_sha256'],
            'input_snapshot': report['snapshot']['id'], 'context_sha256': _context(report),
            'first_answer': None, 'hint_count': 0, 'revealed': False,
            'answer_origin': 'local entered text; not authenticated human identity',
            'self_assessment': 'not_graded'}


def _check_session(report, card, session):
    _check_card(report, card)
    if any(session.get(key) != expected for key, expected in (
        ('schema', 1), ('card_id', card['id']), ('card_sha256', card['card_sha256']),
        ('input_snapshot', report['snapshot']['id']), ('context_sha256', _context(report)))):
        raise ValueError('Stale or mismatched rehearsal session; start a new session')
    count = session.get('hint_count')
    if type(count) is not int or not 0 <= count <= len(card['hints']) or type(session.get('revealed')) is not bool:
        raise ValueError('Invalid rehearsal progress')
    first = session.get('first_answer')
    if first is not None:
        _text(first, 'first_answer')
    elif count or session['revealed']:
        raise ValueError('First answer required before hints or reveal')


def answer(session, text):
    if session.get('first_answer') is not None:
        raise ValueError('First answer is immutable; start a separate session to try again')
    if session.get('hint_count') != 0 or session.get('revealed') is not False:
        raise ValueError('Cannot record a first answer after hints/reveal')
    result = copy.deepcopy(session)
    result['first_answer'] = _text(text, 'answer')
    return result


def hint(report, card, session):
    _check_session(report, card, session)
    if session['first_answer'] is None:
        raise ValueError('Write your first answer before requesting a hint')
    if session['revealed']:
        raise ValueError('Reveal already opened')
    if session['hint_count'] >= len(card['hints']):
        raise ValueError('No more hints')
    result = copy.deepcopy(session)
    result['hint_count'] += 1
    return result


def reveal(report, card, session):
    _check_session(report, card, session)
    if session['first_answer'] is None:
        raise ValueError('Write your first answer before revealing evidence')
    result = copy.deepcopy(session)
    result['revealed'] = True
    return result


def test_status(report, card):
    rid = card['requirement_id']
    runs = [copy.deepcopy(r) for r in report['runs'] if rid in r.get('requirement_ids', [])]
    # CLI also checks current repo/plan/runner. Direct Python consumers must do the same.
    for run in runs:
        if run.get('input_snapshot') != report['snapshot']['id']:
            run['status'] = 'error'
            run['freshness_error'] = 'Run is not bound to this input snapshot'
    reviews = report.get('reviews', [])
    variants = sorted({r.get('variant', 'unspecified') for r in runs})
    return {'state': workflow.derive_state(rid, report['claims'], runs, reviews)['state'],
            'runs': runs,
            'by_variant': {v: workflow.derive_state(rid, report['claims'],
                [r for r in runs if r.get('variant', 'unspecified') == v], reviews)
                for v in variants},
            'scope': 'Recorded checks only, not full acceptance; use CLI for live input/runner freshness check'}


def public_view(report, card, session):
    """Allowlist a view: no answer, source, run logs, or future hints before reveal."""
    _check_session(report, card, session)
    count = session['hint_count']
    phase = ('revealed' if session['revealed'] else 'hinting' if count else
             'answered' if session['first_answer'] is not None else 'question')
    view = {'id': card['id'], 'requirement_id': card['requirement_id'],
            'problem': card['problem'], 'phase': phase,
            'first_answer': session['first_answer'], 'hints': card['hints'][:count],
            'constraints': card['constraints'][:count], 'hint_count': count,
            'total_hints': len(card['hints'])}
    if session['revealed']:
        result = copy.deepcopy(card['reveal'])
        result['references'] = [_reference(report, ref) for ref in result['references']]
        result['test_status'] = test_status(report, card)
        result['business_acceptance'] = 'not_accepted'
        result['answer_assessment'] = 'not_graded; compare your reasoning with evidence, not a model score'
        result['authorship'] = card['origin']
        view['reveal'] = result
    return view
