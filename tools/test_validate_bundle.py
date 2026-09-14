"""Unit/mutation tests for bundle checks, not application acceptance tests."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from validate_bundle import inspect_markdown, validate
from reassemble_canonical import reassemble

ROOT = Path(__file__).resolve().parents[1]


class MarkdownChecks(unittest.TestCase):
    def test_valid_table(self):
        out = inspect_markdown('| A | B |\n|---|---|\n| x | y |\n')
        self.assertEqual(out['tables'], 1)
        self.assertEqual(out['errors'], [])

    def test_empty_cell(self):
        out = inspect_markdown('| A | B |\n|---|---|\n| x |   |\n')
        self.assertTrue(any('empty table cell' in x for x in out['errors']))

    def test_column_mismatch(self):
        out = inspect_markdown('| A | B |\n|---|---|\n| x | y | z |\n')
        self.assertTrue(any('column mismatch' in x for x in out['errors']))

    def test_escaped_pipe(self):
        out = inspect_markdown('| A | B |\n|---|---|\n| x\\|y | z |\n')
        self.assertEqual(out['errors'], [])

    def test_ignore_code_block(self):
        out = inspect_markdown('```text\n| broken |\n[bad](missing.md)\n```\n')
        self.assertEqual(out['tables'], 0)
        self.assertEqual(out['links'], [])
        self.assertEqual(out['errors'], [])

    def test_unclosed_fence(self):
        self.assertTrue(any('unclosed fence' in e for e in inspect_markdown('```\nx\n')['errors']))

    def test_missing_delimiter(self):
        self.assertTrue(any('delimiter' in e for e in inspect_markdown('| a | b |\n| x | y |\n')['errors']))


class BundleChecks(unittest.TestCase):
    def clone(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / 'bundle'

        def copy_fixture_file(source, destination):
            path = Path(source)
            # Generated non-Markdown artifacts are checked only for link existence.
            # Keep their paths without copying model weights/PDFs/raw outputs;
            # all Markdown and mutable source/config fixtures remain real copies.
            if path.relative_to(ROOT).parts[0] in {'output', 'tmp'} and path.suffix.lower() != '.md':
                Path(destination).touch()
                return destination
            return shutil.copy2(source, destination)

        shutil.copytree(ROOT, target, copy_function=copy_fixture_file,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        return target

    def assert_has_error(self, root: Path, phrase: str):
        out = validate(root)
        self.assertEqual(out['status'], 'failed')
        self.assertTrue(any(phrase in e for e in out['errors']), out['errors'])

    def test_current_bundle(self):
        out = validate(ROOT)
        self.assertEqual(out['status'], 'passed', out['errors'])
        self.assertEqual(out['counts']['baseline_invariants'], 45)
        self.assertEqual(out['counts']['accepted_user_overrides'], 11)

    def test_clone_preserves_checks_and_source_isolation(self):
        root = self.clone()
        self.assertEqual(validate(root), validate(ROOT))
        source = Path('docs/source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md')
        self.assertFalse((root / source).samefile(ROOT / source))

    def test_reassemble_exact(self):
        original = (ROOT / 'docs/source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md').read_bytes()
        self.assertEqual(reassemble(ROOT, baseline=True), original)

    def test_tampered_source(self):
        root = self.clone()
        p = root / 'docs/source/PALIMPSEST_CANONICAL_MODEL_INTEGRATED.md'
        p.write_bytes(p.read_bytes() + b'changed\n')
        self.assert_has_error(root, 'source hash mismatch')

    def test_tampered_slice(self):
        root = self.clone()
        p = root / 'docs/canonical/07_propagation.md'
        p.write_bytes(p.read_bytes() + b'changed\n')
        self.assert_has_error(root, 'split hash/content mismatch')

    def test_missing_task_dependency(self):
        root = self.clone()
        p = root / 'tasks/task_graph.json'
        data = json.loads(p.read_text())
        data['tasks'][0]['depends_on'] = ['T99']
        p.write_text(json.dumps(data))
        self.assert_has_error(root, 'unknown task dependency')

    def test_task_cycle(self):
        root = self.clone()
        p = root / 'tasks/task_graph.json'
        data = json.loads(p.read_text())
        data['tasks'][0]['depends_on'] = ['T01']
        p.write_text(json.dumps(data))
        self.assert_has_error(root, 'dependency cycle')

    def test_unmapped_invariant(self):
        root = self.clone()
        p = root / 'tests/specs/invariant_traceability.json'
        data = json.loads(p.read_text())
        data['invariants'][0]['test_ids'] = []
        p.write_text(json.dumps(data))
        self.assert_has_error(root, 'invariant without tests')

    def test_unsupported_approval(self):
        root = self.clone()
        p = root / 'docs/decisions/decisions.json'
        data = json.loads(p.read_text())
        data['proposals'][0]['status'] = 'accepted'
        p.write_text(json.dumps(data))
        self.assert_has_error(root, 'accepted proposal lacks approval')

    def test_broken_local_link(self):
        root = self.clone()
        p = root / 'README.md'
        p.write_text(p.read_text(encoding='utf-8') + '\n[missing](does-not-exist.md)\n', encoding='utf-8')
        self.assert_has_error(root, 'missing local link')


    def test_current_reassemble_exact(self):
        current = (ROOT / 'docs/canonical/PALIMPSEST_CANONICAL_MODEL.md').read_bytes()
        self.assertEqual(reassemble(ROOT), current)

    def test_current_differs_from_archived_only_as_versioned_source(self):
        self.assertNotEqual(reassemble(ROOT), reassemble(ROOT, baseline=True))

    def test_tampered_baseline_slice(self):
        root = self.clone()
        p = root / 'docs/source/baseline_parts/07_propagation.md'
        p.write_bytes(p.read_bytes() + b'changed\n')
        self.assert_has_error(root, 'split hash/content mismatch')

    def test_tampered_current_full(self):
        root = self.clone()
        p = root / 'docs/canonical/PALIMPSEST_CANONICAL_MODEL.md'
        p.write_bytes(p.read_bytes() + b'changed\n')
        self.assert_has_error(root, 'current canonical hash mismatch')

    def test_parser_policy_drift(self):
        root = self.clone()
        p = root / 'docs/decisions/user_overrides.json'
        d = json.loads(p.read_text())
        d['overrides'][1]['selected_details']['pdf_parser'] = 'OtherParser'
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'MinerU parser policy drift')

    def test_silent_fallback_policy(self):
        root = self.clone()
        p = root / 'docs/decisions/user_overrides.json'
        d = json.loads(p.read_text())
        d['overrides'][1]['selected_details']['silent_parser_fallback'] = True
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'MinerU parser policy drift')

    def test_gui_cannot_be_current_task(self):
        root = self.clone()
        p = root / 'tasks/task_graph.json'
        d = json.loads(p.read_text())
        d['tasks'][-1]['status'] = 'planned'
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'GUI deferred gate drift')

    def test_cli_cannot_depend_on_gui(self):
        root = self.clone()
        p = root / 'tasks/task_graph.json'
        d = json.loads(p.read_text())
        d['tasks'][2]['depends_on'].append('T13')
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'GUI before CLI release')

    def test_user_override_missing_approval(self):
        root = self.clone()
        p = root / 'docs/decisions/user_overrides.json'
        d = json.loads(p.read_text())
        d['approval_evidence'] = {}
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'missing user approval evidence')

    def test_component_name_drift(self):
        root = self.clone()
        p = root / 'docs/decisions/user_overrides.json'
        d = json.loads(p.read_text())
        d['overrides'][2]['selected_details']['Artifact Store'] = 'old_name'
        p.write_text(json.dumps(d))
        self.assert_has_error(root, 'component naming policy drift')

    def test_retrieval_default_drift(self):
        for field,value in [('embedding_model','other-model'),('embedding_dense_dimensions',768),
                            ('reranker_model','BAAI/bge-reranker-v2-m3'),('reranker_scoring','dense_similarity')]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in d['overrides'] if u['id']=='U04')['selected_details'][field] = value
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'BGE-M3 default policy drift')

    def test_new_user_override_missing_evidence(self):
        for uid,field in [('U04','approval_evidence'),('U04','clarification_evidence'),
                          ('U04','extension_evidence'),('U05','approval_evidence'),('U06','approval_evidence'),
                          ('U07','approval_evidence'),('U08','approval_evidence'),
                          ('U09','approval_evidence'),('U10','approval_evidence')]:
            with self.subTest(uid=uid,field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in d['overrides'] if u['id']==uid).pop(field)
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'evidence')

    def test_mineru_version_policy_drift(self):
        for field,value in [('version_selection','unverified_latest'),('resolved_exact_version_required',False),
                            ('runtime_profile_verification_required',False)]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in d['overrides'] if u['id']=='U05')['selected_details'][field] = value
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'MinerU version selection policy drift')

    def test_current_map_override_coverage(self):
        root = self.clone()
        p = root / 'docs/canonical/current_map.json'
        d = json.loads(p.read_text(encoding='utf-8'))
        d['effective_user_overrides'].remove('U05')
        p.write_text(json.dumps(d), encoding='utf-8')
        self.assert_has_error(root, 'current map user override mismatch')

    def test_model_replacement_policy_drift(self):
        for section,field,value in [('replacement_policy','embedding_and_reranker_independent',False),
                                    ('replacement_policy','embedding_space_isolation',False),
                                    ('replacement_policy','canonical_history_preserved',False),
                                    ('future_candidates','active',True),
                                    ('future_candidates','implementation_status','implemented')]:
            with self.subTest(section=section,field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in d['overrides'] if u['id']=='U04')[section][field] = value
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'model replacement policy drift')

    def test_stage_module_coverage(self):
        for field in ['domain_modules','compiler_operation_modules','publication_modules']:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                details = next(u for u in d['overrides'] if u['id']=='U06')['selected_details']
                details[field] = {} if field=='domain_modules' else []
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'stage module coverage drift')

    def test_architecture_choice_requires_evidence(self):
        for rid,option in [('R07','reconfirm_stale'),('R08','exact_scoped_only')]:
            with self.subTest(rid=rid):
                root = self.clone()
                p = root / 'docs/decisions/architecture_fixes.json'
                data = json.loads(p.read_text(encoding='utf-8'))
                row = next(r for r in data['resolutions'] if r['id']==rid)
                row.update(status='resolved_design', selected_option=option, approval_ref='U08')
                row.pop('approval_evidence', None)
                p.write_text(json.dumps(data), encoding='utf-8')
                # Even consistent resolution metadata cannot replace a user's choice.
                p = root / 'docs/decisions/user_overrides.json'
                data = json.loads(p.read_text(encoding='utf-8'))
                details = next(u for u in data['overrides'] if u['id']=='U08')['selected_details']
                if rid in details['pending_user_choices']:
                    details['pending_user_choices'].remove(rid)
                if rid not in details['resolved_review_items']:
                    details['resolved_review_items'].append(rid)
                p.write_text(json.dumps(data), encoding='utf-8')
                self.assert_has_error(root, 'architecture policy choice lacks user evidence')

    def test_architecture_pending_choice_cannot_have_active_option(self):
        root = self.clone()
        p = root / 'docs/decisions/architecture_fixes.json'
        data = json.loads(p.read_text(encoding='utf-8'))
        row = next(r for r in data['resolutions'] if r['id']=='R07')
        row.update(status='awaiting_user', selected_option='reconfirm_stale', approval_ref=None)
        p.write_text(json.dumps(data), encoding='utf-8')
        self.assert_has_error(root, 'architecture pending policy activated')

    def test_application_deployment_policy_drift(self):
        for field,value in [('application_language','TypeScript'),('deployment_runtime','native_only')]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                data = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in data['overrides'] if u['id']=='U10')['selected_details'][field] = value
                p.write_text(json.dumps(data), encoding='utf-8')
                self.assert_has_error(root, 'Python Docker policy drift: '+field)

    def test_storage_version_policy_drift(self):
        for field,value in [('initial_major',19),('pgvector_required',False),
                            ('major_upgrade','automatic_latest')]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                data = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in data['overrides'] if u['id']=='U09')['selected_details'][field] = value
                p.write_text(json.dumps(data), encoding='utf-8')
                self.assert_has_error(root, 'storage identity policy drift: '+field)

    def test_storage_identity_and_promotion_policy_drift(self):
        for field,value in [('data_id','normalized_text_hash'),('new_opaque_ids','uuidv4'),
                            ('duplicate_new_import','accept_again'),('duplicate_auto_acquisition',True),
                            ('successful_request_retry','duplicate_error'),('registration','folder_watch'),
                            ('durable_record_owner','canonical_store'),('terminal_record_deleted',True),
                            ('canonical_promotion','copy_then_separate_cleanup')]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                data = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in data['overrides'] if u['id']=='U09')['selected_details'][field] = value
                p.write_text(json.dumps(data), encoding='utf-8')
                self.assert_has_error(root, 'storage identity policy drift: '+field)

    def test_tampered_storage_history_snapshot(self):
        root = self.clone()
        p = root / 'docs/history/2026-09-09_pre_storage_identity.md'
        p.write_bytes(p.read_bytes() + b'changed\n')
        self.assert_has_error(root, 'historical snapshot hash mismatch')

    def test_stage_module_boundaries(self):
        for field,value in [('domain_independent_of_adapters',False),('shared_atomic_commit_boundary',False),
                            ('operation_dispatch_through_shared_runtime',False),('independent_module_tests_required',False),
                            ('w2k_llm_calls',1),('publication_adds_compiler_record_types',True),
                            ('deployment_boundary','microservices')]:
            with self.subTest(field=field):
                root = self.clone()
                p = root / 'docs/decisions/user_overrides.json'
                d = json.loads(p.read_text(encoding='utf-8'))
                next(u for u in d['overrides'] if u['id']=='U06')['selected_details'][field] = value
                p.write_text(json.dumps(d), encoding='utf-8')
                self.assert_has_error(root, 'stage module boundary drift')

    def test_source_preservation_policy_drift(self):
        root = self.clone()
        p = root / 'docs/decisions/user_overrides.json'
        original = p.read_text(encoding='utf-8')
        for field,value in [
            ('d2i_llm_calls',1), ('d2i_llm_calls',False),
            ('semantic_interpretation_starts_at','d2i'),
            ('source_semantic_type','proposition'),
            ('arbitrary_summary_or_value_filter',True),
            ('complete_page_and_block_coverage_required',False),
            ('preserve_figures_panels_captions_continuations',False),
            ('preserve_headers_footers_references',False),
            ('structural_acceptance_is_semantic_approval',True),
            ('known_structural_omission_fails',False),
            ('silent_parser_or_llm_fallback',True),
            ('context_chunk_is_projection',False),
            ('model_change_rewrites_information',True),
            ('legacy_semantic_history_preserved',False),
            ('application_controls_identity_and_commit',False),
            ('structured_output_guarantees_semantic_determinism',True),
        ]:
            with self.subTest(field=field,value=value):
                data=json.loads(original)
                next(u for u in data['overrides'] if u['id']=='U11')['selected_details'][field]=value
                p.write_text(json.dumps(data),encoding='utf-8')
                self.assert_has_error(root,'D2I source preservation policy drift: '+field)
        data=json.loads(original)
        next(u for u in data['overrides'] if u['id']=='U11')['selected_details'].pop('source_semantic_type')
        p.write_text(json.dumps(data),encoding='utf-8')
        self.assert_has_error(root,'D2I source preservation policy drift: source_semantic_type')

    def test_source_preservation_approval_evidence_required(self):
        root=self.clone()
        p=root / 'docs/decisions/user_overrides.json'
        original=p.read_text(encoding='utf-8')
        for field,error in [('approval_evidence','missing user approval evidence: U11'),
                            ('follow_up_evidence','missing structured compilation user evidence: U11')]:
            with self.subTest(field=field):
                data=json.loads(original)
                next(u for u in data['overrides'] if u['id']=='U11').pop(field)
                p.write_text(json.dumps(data),encoding='utf-8')
                self.assert_has_error(root,error)

    def test_source_preservation_task_boundary(self):
        root=self.clone()
        p=root / 'tasks/task_graph.json'
        original=p.read_text(encoding='utf-8')
        for field,value in [('d2i_policy','semantic_generation'),('semantic_model_stage','T03_D2I'),
                            ('required_user_overrides',[]),('read_paths',[])]:
            with self.subTest(field=field):
                data=json.loads(original)
                next(t for t in data['tasks'] if t['id']=='T03')[field]=value
                p.write_text(json.dumps(data),encoding='utf-8')
                self.assert_has_error(root,'T03 source preservation boundary drift')

    def test_source_preservation_history_is_immutable(self):
        root=self.clone()
        p=root / 'docs/history/2026-09-09_pre_d2i_source_preservation.md'
        p.write_bytes(p.read_bytes()+b'changed\n')
        self.assert_has_error(root,'historical snapshot hash mismatch')


if __name__ == '__main__':
    unittest.main()
