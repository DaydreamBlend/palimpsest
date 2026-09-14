"""Policy/integrity checks for CLI/MinerU handoff docs; not runtime validation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re


def validate_release_policy(root: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    counts: dict = {}
    def load(name: str):
        try:
            return json.loads((root / name).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            errors.append(f'{name}: {exc}')
            return None
    def safe(name: str) -> Path:
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()):
            raise ValueError('unsafe relative path')
        return p
    cm = load('docs/canonical/current_map.json')
    if cm:
        try:
            raw = safe(cm['source_path']).read_bytes()
            lines = raw.decode('utf-8').splitlines(keepends=True)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != cm['source_sha256']:
                errors.append('current canonical hash mismatch')
            if len(lines) != cm['source_lines']:
                errors.append('current canonical line count mismatch')
            cursor, pieces = 1, []
            for p in cm['parts']:
                if p['start_line'] != cursor:
                    errors.append('current partition gap/overlap')
                data = safe(p['path']).read_bytes()
                expected = ''.join(lines[p['start_line']-1:p['end_line']]).encode('utf-8')
                if data != expected or hashlib.sha256(data).hexdigest() != p['sha256']:
                    errors.append('split hash/content mismatch: current ' + p['path'])
                pieces.append(data)
                cursor = p['end_line'] + 1
            if cursor != len(lines)+1 or b''.join(pieces) != raw:
                errors.append('current reconstruction mismatch')
            baseline = safe(cm['baseline_path']).read_bytes()
            if hashlib.sha256(baseline).hexdigest() != cm['baseline_sha256']:
                errors.append('current map baseline hash mismatch')
            snapshots = cm.get('history_snapshots', []) + [cm['previous_snapshot']]
            for snapshot in snapshots:
                if hashlib.sha256(safe(snapshot['path']).read_bytes()).hexdigest() != snapshot['sha256']:
                    errors.append('historical snapshot hash mismatch: ' + snapshot['path'])
            text = raw.decode('utf-8')
            if re.search(r'\b(?:Horreum|Bibliotheca|Scriptorium|horreum|bibliotheca|scriptorium)\b',text) or 'horreum_path' in text:
                errors.append('legacy component name in current canonical')
            if re.search(r'kq2w', text, re.IGNORECASE):
                errors.append('legacy operation name in current canonical')
            for required in ['Artifact Store','Canonical Store','Compiler Runtime','MinerU','CLI','GUI','artifact_path','K2W',
                             'U11', 'source-information-v1', 'source-d2i-v1', 'D2I_SOURCE_PRESERVATION.md']:
                if required not in text:
                    errors.append('current canonical missing required term: '+required)
            counts.update(current_canonical_lines=len(lines), current_canonical_parts=len(cm['parts']))
        except (KeyError, OSError, ValueError, TypeError) as exc:
            errors.append('current canonical validation: '+str(exc))
    doc = load('docs/decisions/user_overrides.json')
    us = {}
    if doc:
        try:
            us = {x['id']:x for x in doc['overrides']}
            if set(us) != {f'U{i:02d}' for i in range(1,12)} or len(doc['overrides']) != 11:
                errors.append('user override ID coverage mismatch')
            if not doc.get('approval_evidence',{}).get('text'):
                errors.append('missing user approval evidence')
            for x in us.values():
                if x['status']!='accepted' or not x.get('selected_details') or not x.get('approval_ref'):
                    errors.append('user override missing acceptance/details: '+x['id'])
                elif not safe(x['approval_ref']).is_file():
                    errors.append('missing override approval_ref: '+x['id'])
                if x['id'] in {'U04','U05','U06','U07','U08','U09','U10','U11'} and not x.get('approval_evidence',{}).get('text'):
                    errors.append('missing user approval evidence: '+x['id'])
            u1=us.get('U01',{}).get('selected_details',{})
            if u1.get('interface_priority')!='cli_first' or u1.get('cli_bootstrap_task')!='T02' or u1.get('gui_stage')!='T13':
                errors.append('CLI-first policy drift')
            u2=us.get('U02',{}).get('selected_details',{})
            if u2.get('pdf_parser')!='MinerU' or u2.get('silent_parser_fallback') is not False:
                errors.append('MinerU parser policy drift')
            u3=us.get('U03',{}).get('selected_details',{})
            for label,ident in [('Artifact Store','artifact_store'),('Canonical Store','canonical_store'),('Compiler Runtime','compiler_runtime')]:
                if u3.get(label)!=ident:
                    errors.append('component naming policy drift: '+label)
            u4=us.get('U04',{}).get('selected_details',{})
            for field,expected in [('embedding_model','BAAI/bge-m3'),('embedding_dense_dimensions',1024),
                                   ('reranker_model','BAAI/bge-m3'),('reranker_scoring','colbert_late_interaction')]:
                if u4.get(field)!=expected:
                    errors.append('BGE-M3 default policy drift: '+field)
            if not us.get('U04',{}).get('clarification_evidence',{}).get('text'):
                errors.append('missing reranker clarification evidence')
            if not us.get('U04',{}).get('extension_evidence',{}).get('text'):
                errors.append('missing model replacement evidence')
            replacement=us.get('U04',{}).get('replacement_policy',{})
            if any(replacement.get(field) is not True for field in
                   ['embedding_and_reranker_independent','embedding_space_isolation','canonical_history_preserved']):
                errors.append('model replacement policy drift')
            candidates=us.get('U04',{}).get('future_candidates',{})
            if candidates.get('active') is not False or candidates.get('implementation_status')!='not_implemented':
                errors.append('model replacement policy drift: future candidates are not active implementations')
            u5=us.get('U05',{}).get('selected_details',{})
            if (u5.get('pdf_parser')!='MinerU' or
                u5.get('version_selection')!='latest_stable_at_install_or_explicit_upgrade' or
                u5.get('resolved_exact_version_required') is not True or
                u5.get('runtime_profile_verification_required') is not True):
                errors.append('MinerU version selection policy drift')
            u6=us.get('U06',{}).get('selected_details',{})
            for field,expected in {
                'domain_modules':{'D':'data','I':'information','K':'knowledge','W':'wisdom','P':'parchment','B':'book'},
                'compiler_operation_modules':['d2i','i2k','n2e','k2k','k2w','w2k'],
                'publication_modules':['w2p','p2b'],
            }.items():
                if u6.get(field)!=expected:
                    errors.append('stage module coverage drift: '+field)
            for field,expected in {
                'deployment_boundary':'single_application', 'domain_independent_of_adapters':True,
                'shared_atomic_commit_boundary':True, 'operation_dispatch_through_shared_runtime':True,
                'independent_module_tests_required':True, 'w2k_llm_calls':0,
                'publication_adds_compiler_record_types':False,
                'contract_path':'docs/implementation/MODULE_BOUNDARIES.md',
            }.items():
                if u6.get(field)!=expected or type(u6.get(field)) is not type(expected):
                    errors.append('stage module boundary drift: '+field)
            if not (root/'docs/implementation/MODULE_BOUNDARIES.md').is_file():
                errors.append('missing stage module contract')
            u7=us.get('U07',{}).get('selected_details',{})
            if (u7.get('operation_name')!='K2W' or u7.get('module_name')!='k2w' or
                u7.get('semantics_changed') is not False or u7.get('historical_evidence_preserved') is not True):
                errors.append('K2W naming policy drift')
            u8=us.get('U08',{}).get('selected_details',{})
            if (u8.get('proposal_blanket_approval') is not False or
                u8.get('application_implemented') is not False or
                u8.get('contract_path')!='docs/decisions/ARCHITECTURE_FIXES.md' or
                u8.get('resolution_registry')!='docs/decisions/architecture_fixes.json'):
                errors.append('architecture repair scope drift')
            u9=us.get('U09',{}).get('selected_details',{})
            for field,expected in {
                'database':'PostgreSQL', 'minimum_major':18, 'initial_major':18,
                'major_upgrade':'explicit_validated_upgrade',
                'postgresql_minor_policy':'latest_stable_in_selected_major',
                'extension':'vector', 'pgvector_required':True,
                'exact_runtime_versions_required':True,
                'shared_database_schemas':['canonical_store','compiler_runtime'],
                'data_id':'sha256_raw_bytes', 'data_id_encoding':'lowercase_hex_64',
                'new_opaque_ids':'uuidv7', 'historical_ids_preserved':True,
                'duplicate_new_import':'reject_with_existing_data_id',
                'successful_request_retry':'replay_same_result',
                'duplicate_auto_acquisition':False, 'registration':'tool_managed_copy',
                'canonical_promotion':'validated_effects_atomic_commit',
                'durable_record_owner':'compiler_runtime', 'terminal_record_deleted':False,
                'contract_path':'docs/decisions/STORAGE_IDENTITY.md',
                'schema_draft_path':'docs/schema/T02_storage_draft.sql',
                'application_implemented':False,
            }.items():
                if u9.get(field)!=expected or type(u9.get(field)) is not type(expected):
                    errors.append('storage identity policy drift: '+field)
            for path in ['docs/decisions/STORAGE_IDENTITY.md', 'docs/schema/T02_STORAGE_SCHEMA.md',
                         'docs/schema/T02_storage_draft.sql', 'docs/schema/T02_storage_checks.sql']:
                if not safe(path).is_file():
                    errors.append('missing storage contract artifact: '+path)
            u10=us.get('U10',{}).get('selected_details',{})
            for field,expected in {'application_language':'Python','deployment_runtime':'Docker',
                                   'cli_first':True,'gui_deferred':True,
                                   'existing_domain_boundaries_preserved':True,
                                   'contract_path':'docs/implementation/ENVIRONMENT.md',
                                   'application_implemented':False}.items():
                if u10.get(field)!=expected or type(u10.get(field)) is not type(expected):
                    errors.append('Python Docker policy drift: '+field)
            u11=us.get('U11',{}).get('selected_details',{})
            for field,expected in {
                'd2i_mode':'deterministic_source_preservation', 'pdf_parser':'MinerU',
                'parser_execution':'local', 'd2i_llm_calls':0,
                'semantic_interpretation_starts_at':'i2k',
                'source_information_profile':'source-information-v1',
                'processing_profile':'source-d2i-v1', 'source_unit_type_required':True,
                'source_semantic_type':None, 'source_specific_identity':True,
                'new_opaque_ids':'uuidv7', 'arbitrary_summary_or_value_filter':False,
                'preserve_source_text_and_structure':True,
                'complete_page_and_block_coverage_required':True,
                'preserve_figures_panels_captions_continuations':True,
                'preserve_headers_footers_references':True,
                'exact_grounding_profiles_hashes_required':True,
                'structural_acceptance_is_semantic_approval':False,
                'known_structural_omission_fails':True, 'silent_parser_or_llm_fallback':False,
                'context_chunk_is_projection':True, 'model_change_rewrites_information':False,
                'legacy_semantic_history_preserved':True,
                'llm_output':'strict_structured_proposals',
                'application_controls_identity_and_commit':True,
                'structured_output_guarantees_semantic_determinism':False,
                'proposal_blanket_approval':False,
                'contract_path':'docs/decisions/D2I_SOURCE_PRESERVATION.md',
            }.items():
                if field not in u11 or u11[field]!=expected or type(u11[field]) is not type(expected):
                    errors.append('D2I source preservation policy drift: '+field)
            if not us.get('U11',{}).get('follow_up_evidence',{}).get('text'):
                errors.append('missing structured compilation user evidence: U11')
            if not safe('docs/decisions/D2I_SOURCE_PRESERVATION.md').is_file():
                errors.append('missing D2I source preservation contract')
            if cm and not any(s.get('path')=='docs/history/2026-09-09_pre_d2i_source_preservation.md'
                              and s.get('sha256')=='3bce40b044222f1e82e3e3d0e787a64107e8896fcc0775653e743f0cc7df59b5'
                              for s in cm.get('history_snapshots',[])+[cm.get('previous_snapshot',{})]):
                errors.append('D2I previous semantic canonical snapshot missing')
            if cm and (set(cm.get('effective_user_overrides',[]))!=set(us) or
                       len(cm.get('effective_user_overrides',[]))!=len(us)):
                errors.append('current map user override mismatch')
            counts['accepted_user_overrides']=len(us)
        except (KeyError, ValueError, OSError, TypeError) as exc:
            errors.append('user overrides validation: '+str(exc))
    fixes=load('docs/decisions/architecture_fixes.json')
    if fixes:
        try:
            rows=fixes['resolutions']
            by_id={r['id']:r for r in rows}
            if set(by_id)!={f'R{i:02d}' for i in range(1,10)} or len(rows)!=9:
                errors.append('architecture resolution coverage mismatch')
            previous=fixes['previous_snapshot']
            if hashlib.sha256(safe(previous['path']).read_bytes()).hexdigest()!=previous['sha256']:
                errors.append('architecture previous snapshot hash mismatch')
            if cm and previous not in cm.get('history_snapshots', []) + [cm.get('previous_snapshot')]:
                errors.append('architecture previous snapshot map mismatch')
            if not safe(fixes['contract_path']).is_file():
                errors.append('missing architecture repair contract')
            choices={'R07':{'reconfirm_stale','preserve_conflict'},
                     'R08':{'exact_scoped_only','retained_similarity'}}
            resolved,pending=set(),set()
            for rid,r in by_id.items():
                if r.get('implementation_status')!='not_implemented':
                    errors.append('architecture resolution is not an application implementation: '+rid)
                if r.get('status')=='awaiting_user':
                    pending.add(rid)
                    if rid not in choices or r.get('selected_option') is not None or r.get('approval_ref') is not None:
                        errors.append('architecture pending policy activated: '+rid)
                elif r.get('status')=='resolved_design':
                    resolved.add(rid)
                    if r.get('approval_ref')!='U08':
                        errors.append('architecture repair lacks approval reference: '+rid)
                    if rid in choices:
                        if r.get('selected_option') not in choices[rid] or not r.get('approval_evidence',{}).get('text'):
                            errors.append('architecture policy choice lacks user evidence: '+rid)
                        if rid=='R08' and r.get('selected_option')=='retained_similarity' and not r.get('retention_policy'):
                            errors.append('architecture retained similarity lacks retention policy')
                    elif r.get('selected_option')!='scoped_invariant_repair':
                        errors.append('architecture repair option drift: '+rid)
                else:
                    errors.append('invalid architecture resolution status: '+rid)
            details=us.get('U08',{}).get('selected_details',{})
            if (set(details.get('resolved_review_items',[]))!=resolved or
                set(details.get('pending_user_choices',[]))!=pending):
                errors.append('architecture override/resolution mismatch')
            counts.update(architecture_resolved_design=len(resolved),architecture_pending_choices=len(pending))
        except (KeyError, ValueError, OSError, TypeError) as exc:
            errors.append('architecture repairs validation: '+str(exc))
    graph=load('tasks/task_graph.json')
    catalog=load('tests/specs/acceptance_catalog.json')
    if graph:
        jobs={x['id']:x for x in graph['tasks']}
        if 'T13' not in jobs:
            errors.append('missing deferred GUI task')
        else:
            gui=jobs['T13']
            if gui.get('depends_on')!=['T12'] or not gui.get('start_gate'):
                errors.append('GUI deferred gate drift')
            if gui.get('status')!='deferred':
                approval = gui.get('gui_start_approval_ref')
                gate_ok = (jobs.get('T12',{}).get('status') == 'completed' and bool(approval))
                if gate_ok:
                    try:
                        gate_ok = safe(approval).is_file() and bool(safe(approval).read_text(encoding='utf-8').strip())
                    except (OSError, ValueError):
                        gate_ok = False
                if not gate_ok:
                    errors.append('GUI deferred gate drift')
        for job in jobs.values():
            for uid in job.get('required_user_overrides',[]):
                if uid not in us:
                    errors.append('unknown task user override: '+uid)
            if job['id']!='T13':
                if 'T13' in job.get('depends_on',[]) or job.get('interface_scope')!='cli_first_no_gui':
                    errors.append('GUI before CLI release: '+job['id'])
        if jobs.get('T02',{}).get('interface_scope')!='cli_first_no_gui':
            errors.append('CLI not bootstrapped at T02')
        if 'docs/interfaces/MINERU_ADAPTER.md' not in jobs.get('T03',{}).get('read_paths',[]):
            errors.append('T03 missing MinerU adapter contract')
        t03=jobs.get('T03',{})
        if (t03.get('d2i_policy')!='deterministic_source_preservation' or
            t03.get('semantic_model_stage')!='T04_I2K' or
            'U11' not in t03.get('required_user_overrides',[]) or
            'docs/decisions/D2I_SOURCE_PRESERVATION.md' not in t03.get('read_paths',[])):
            errors.append('T03 source preservation boundary drift')
    if catalog:
        tests=catalog.get('tests',[])
        ids={t['id'] for t in tests}
        for i in range(82,113):
            if f'AT{i:02d}' not in ids:
                errors.append('missing new user acceptance: '+str(i))
        used=set()
        for t in tests:
            for uid in t.get('user_override_dependencies',[]):
                used.add(uid)
                if uid not in us:
                    errors.append('unknown test user override: '+uid)
        if not {f'U{i:02d}' for i in range(1,12)}.issubset(used):
            errors.append('user override lacks acceptance coverage')
    return counts, errors
