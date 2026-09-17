"""U11 D2I: source-preserving format conversion, without model inference.

Semantic extraction starts at I2K. Historical semantic D2I code is retained in
legacy_semantic_d2i and is not imported by this active transformation module.
"""

from .source_units import build_source_units, verify_source_units, SOURCE_UNITS_VERSION
from .errors import PalimpsestError
from copy import deepcopy

SOURCE_GROUPS_VERSION = 'source-groups-v1'
SOURCE_GROUPS_V2_VERSION = 'source-groups-v2'
SOURCE_PAGE_GROUPS_VERSION = 'source-groups-pages-v1'
MARKDOWN_ALGORITHM = 'markdown-groups-v1'
CODE_ALGORITHM = 'python-code-groups-v1'
TEXT_ALGORITHMS = (MARKDOWN_ALGORITHM, CODE_ALGORITHM)
SOURCE_ALGORITHMS = (SOURCE_UNITS_VERSION, SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION, SOURCE_PAGE_GROUPS_VERSION)


def build_units(bundle, algorithm):
    if algorithm == CODE_ALGORITHM:
        from .code_adapter import build_code_units
        return build_code_units(bundle)
    if algorithm == SOURCE_PAGE_GROUPS_VERSION:
        from .source_pages import build_page_groups
        return build_page_groups(bundle)
    if algorithm == MARKDOWN_ALGORITHM:
        from .markdown_adapter import build_markdown_units
        return build_markdown_units(bundle)
    if algorithm == SOURCE_UNITS_VERSION:
        return build_source_units(bundle)
    if algorithm == SOURCE_GROUPS_VERSION:
        from .source_groups import build_source_groups
        return build_source_groups(bundle)
    if algorithm == SOURCE_GROUPS_V2_VERSION:
        from .source_groups import build_source_groups_v2
        return build_source_groups_v2(bundle)
    raise PalimpsestError('unsupported_source_algorithm', '지원하는 원문 조립 알고리즘을 선택하세요.', 2)


def verify_units(bundle, proposals, algorithm):
    if algorithm == CODE_ALGORITHM:
        from .code_adapter import verify_code_units
        return verify_code_units(bundle, proposals)
    if algorithm == SOURCE_PAGE_GROUPS_VERSION:
        from .source_pages import verify_page_groups
        return verify_page_groups(bundle, proposals)
    if algorithm == MARKDOWN_ALGORITHM:
        from .markdown_adapter import verify_markdown_units
        return verify_markdown_units(bundle, proposals)
    if algorithm == SOURCE_UNITS_VERSION:
        return verify_source_units(bundle, proposals)
    if algorithm == SOURCE_GROUPS_VERSION:
        from .source_groups import verify_source_groups
        return verify_source_groups(bundle, proposals)
    if algorithm == SOURCE_GROUPS_V2_VERSION:
        from .source_groups import verify_source_groups_v2
        return verify_source_groups_v2(bundle, proposals)
    raise PalimpsestError('unsupported_source_algorithm', '지원하는 원문 조립 알고리즘을 선택하세요.', 2)


def assembly_payload(bundle, proposal, algorithm):
    if algorithm == CODE_ALGORITHM:
        from .code_adapter import code_content_segments
        return {'source_assembly': {'algorithm': algorithm,
                'content_segments': code_content_segments(bundle, proposal)}}
    if algorithm == SOURCE_PAGE_GROUPS_VERSION:
        from .source_pages import page_content_segments
        return {'source_assembly': {'algorithm': algorithm,
                'content_segments': page_content_segments(bundle, proposal)}}
    if algorithm == MARKDOWN_ALGORITHM:
        from .markdown_adapter import markdown_content_segments
        return {'source_assembly': {'algorithm': algorithm,
                'content_segments': markdown_content_segments(bundle, proposal)}}
    if algorithm == SOURCE_UNITS_VERSION:
        return {}
    if algorithm == SOURCE_GROUPS_VERSION:
        from .source_groups import group_content_segments
        return {'source_assembly': {'algorithm': algorithm,
                'content_segments': group_content_segments(bundle, proposal)}}
    if algorithm == SOURCE_GROUPS_V2_VERSION:
        from .source_groups import group_content_segments
        return {'source_assembly': {'algorithm': algorithm,
                'content_segments': group_content_segments(bundle, proposal)}}
    raise PalimpsestError('unsupported_source_algorithm', '지원하는 원문 조립 알고리즘을 선택하세요.', 2)


def text_assemblies(bundle, proposals, algorithm):
    """Validate a whole text source once and reuse its exact unit manifest."""
    if algorithm not in TEXT_ALGORITHMS:
        raise PalimpsestError('unsupported_source_algorithm', '텍스트 원문 조립 알고리즘이 필요합니다.', 2)
    checks = verify_units(bundle, proposals, algorithm)
    payloads = {tuple(proposal['block_ids']): {'source_assembly': {
        'algorithm': algorithm, 'content_segments': deepcopy(entry['content_segments'])}}
        for proposal, entry in zip(proposals, checks['unit_manifest'], strict=True)}
    return checks, payloads


__all__ = ['build_source_units', 'verify_source_units', 'build_units', 'verify_units']
