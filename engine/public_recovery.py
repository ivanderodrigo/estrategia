"""Recover a newer validated public snapshot after incomplete shard publication.

The public snapshot is a projection, not a replacement for internal research memory.
Only exact entity IDs are merged; internal clues and previous scalar observations survive.
"""
from copy import deepcopy
from .enrichment import merge_field
from .settings import SECTIONS
from .storage import read_json


def hydrate(value, registry):
    if isinstance(value, list):
        return [hydrate(x, registry) for x in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, item in value.items():
        if key == 'evidence_ids':
            # Broken references must not silently erase provenance.
            out['evidence'] = [deepcopy(registry[eid]) for eid in item]
        else:
            out[key] = hydrate(item, registry)
    return out


def merge_snapshot(data, public):
    stats = {'entities_restored': 0, 'fields_merged': 0, 'scalar_history_preserved': 0}
    for section in SECTIONS:
        current = data.setdefault(section, [])
        index = {r['id']: r for r in current}
        for incoming in public.get(section, []):
            if incoming['id'] not in index:
                current.append(deepcopy(incoming)); index[incoming['id']] = current[-1]
                stats['entities_restored'] += 1
                continue
            row = index[incoming['id']]
            for key, field in incoming.get('fields', {}).items():
                fields = row.setdefault('fields', {})
                old = fields.get(key)
                if not old:
                    fields[key] = deepcopy(field)
                elif isinstance(old.get('value'), list) or isinstance(field.get('value'), list) or old.get('value') == field.get('value'):
                    fields[key] = merge_field(old, field)
                elif field.get('value') not in (None, '', [], {}):
                    # Keep previous value AND its evidence; never assign old scalar
                    # support to the replacement claim.
                    replacement = deepcopy(field)
                    replacement['prior_observations'] = deepcopy(old.get('prior_observations', [])) + [deepcopy(old)]
                    fields[key] = replacement
                    stats['scalar_history_preserved'] += 1
                stats['fields_merged'] += 1
    return stats


def recover_newer_public(data):
    manifest = read_json('data/public/manifest.json', {})
    published = str(manifest.get('generated_at') or '')
    internal = str(data.get('meta', {}).get('generated_at') or '')
    if not published or published <= internal:
        return {'status': 'not-needed'}
    last_run = read_json('data/public/last_run.json', {})
    if last_run.get('status') != 'published':
        raise ValueError('Newer public snapshot is not validated; refusing recovery')
    public = {}
    for section in SECTIONS:
        info = manifest.get('sections', {}).get(section, {})
        path = info.get('file', '')
        if not path.startswith('data/public/sections/') or '..' in path:
            raise ValueError('Unexpected public recovery path')
        payload = read_json(path)
        public[section] = hydrate(payload['rows'], payload['evidence'])
        if len(public[section]) != manifest['counts'][section]:
            raise ValueError('Public recovery count mismatch: '+section)
    stats = merge_snapshot(data, public)
    stats.update(status='recovered', public_generated_at=published, internal_generated_at=internal)
    data.setdefault('meta', {})['public_snapshot_recovery'] = stats
    return stats
