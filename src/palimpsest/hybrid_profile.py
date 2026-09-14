"""Fixed local Hybrid runtime identity, shared without database dependencies."""

import re

from .pdf_raster import RENDER_PROFILE

HYBRID_PARSER = {
    'provider':'mineru', 'version':'3.4.5', 'backend':'hybrid-engine',
    'adapter_version':'mineru-hybrid-preproc-v1', 'effort':'high', 'engine':'transformers',
    'image_digest':'sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4',
    'models_manifest_sha256':'919d1cfc207e1dd3a97f9c9cbf3bd6b5c773aac841b8d33176b66bf6d2476f0d',
    'pipeline_models_manifest_sha256':'6e4ab8545ac654440671e551346bd1865d6f12181c7d9f48bfef042c92046408',
    'model_repository':'opendatalab/MinerU2.5-Pro-2605-1.2B',
    'model_revision':'bff20d4ae2bf202df9f45284b4d43681555a97ed',
    'model_weight_sha256':'abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0',
    'device':'cuda', 'network':'none', 'method':'auto', 'language':'ch',
    'image_analysis':False, 'formula':True, 'table':True,
}

DUAL_PARSER = {
    **HYBRID_PARSER,
    'adapter_version':'mineru-hybrid-dual200-v1',
    'transcription_mode':'native_plus_image200',
    'native_input_mode':'original_pdf_auto',
    'native_adapter_version':'mineru-hybrid-preproc-v1',
    'ocr_adapter_version':'mineru-hybrid-image200-v1',
    'renderer':dict(RENDER_PROFILE),
    'renderer_sha256':'3a845920bcaf1dd080343666f90b1935c769693ffa003e55e3c46cc3067c1fdc',
}

IMAGE_PARSER = {
    **HYBRID_PARSER,
    'adapter_version':'mineru-hybrid-image200-v1',
    'transcription_mode':'image200',
    'input_mode':'image_only_pdf',
    'renderer':dict(RENDER_PROFILE),
    'renderer_sha256':'3a845920bcaf1dd080343666f90b1935c769693ffa003e55e3c46cc3067c1fdc',
}


def matches_hybrid_parser(parser):
    return (isinstance(parser, dict)
            and all(parser.get(key) == value and type(parser.get(key)) is type(value)
                    for key, value in HYBRID_PARSER.items())
            and isinstance(parser.get("runner_sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", parser["runner_sha256"]) is not None
            and isinstance(parser.get("gpu_uuid"), str) and parser["gpu_uuid"].startswith("GPU-"))


def matches_dual_parser(parser):
    return (isinstance(parser, dict)
            and all(parser.get(key) == value and type(parser.get(key)) is type(value)
                    for key, value in DUAL_PARSER.items())
            and isinstance(parser.get("runner_sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", parser["runner_sha256"]) is not None
            and isinstance(parser.get("gpu_uuid"), str) and parser["gpu_uuid"].startswith("GPU-"))


def matches_image_parser(parser):
    return (isinstance(parser, dict)
            and all(parser.get(key) == value and type(parser.get(key)) is type(value)
                    for key, value in IMAGE_PARSER.items())
            and isinstance(parser.get("runner_sha256"), str)
            and re.fullmatch("[0-9a-f]{64}", parser["runner_sha256"]) is not None
            and isinstance(parser.get("gpu_uuid"), str) and parser["gpu_uuid"].startswith("GPU-"))
