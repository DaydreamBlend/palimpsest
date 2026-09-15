"""Deterministic, resumable provider delivery for full-source I2K.

Canonical I and the final Runtime response stay unchanged.  This module only
partitions what a model sees, then proves that the merged exchange covers the
frozen source-review manifest and is exactly derived from verified batch calls.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from . import multi_source_i2k as multi
from . import multi_source_prompts, source_review
from .errors import PalimpsestError
from .i2k import digest
from .knowledge import source_block_ranges
from .knowledge_requests import REVIEW_POLICY, _review_policy


PROFILE = "batched-i2k-delivery-v1"
MAX_SOURCE_CHARACTERS = 8_000
MAX_IMAGES = 3


def _fail(code="invalid_batched_i2k", status=4):
    raise PalimpsestError(code, "분할 I2K 입력·응답·coverage를 확인하세요.", status)


def implementation_sha256():
    return sha256(Path(__file__).read_bytes()).hexdigest()


def _snapshot(context, phase):
    if not isinstance(context, dict) or phase not in ("generator", "validator"):
        _fail()
    snapshot = context.get("input_snapshot")
    packet = snapshot.get("input") if isinstance(snapshot, dict) else None
    if not isinstance(packet, dict) or packet.get("schema_version") != multi.INPUT_SCHEMA:
        _fail("batched_i2k_full_source_required", 2)
    multi.check_input(packet)
    manifest = snapshot.get("source_review_manifest")
    if manifest != source_review.build_manifest(packet):
        _fail("source_review_manifest_changed", 6)
    expected = context.get("input_digest") if phase == "generator" else context.get("validation_context_sha")
    if not isinstance(expected, str) or len(expected) != 64:
        _fail()
    return snapshot, packet, manifest, expected


def _page(target):
    pages = [ref.get("page_index") for ref in target["source_refs"]
             if type(ref.get("page_index")) is int]
    return min(pages) if pages else None


def _split_range(content, start, end):
    result = []
    while end - start > MAX_SOURCE_CHARACTERS:
        stop = start + MAX_SOURCE_CHARACTERS
        boundary = max(content.rfind("\n", start, stop), content.rfind(" ", start, stop))
        if boundary <= start:
            boundary = stop
        result.append((start, boundary))
        start = boundary
    if start < end:
        result.append((start, end))
    return result


def _segments(packet, manifest):
    units = {unit["information_id"]: unit for unit in packet["model_input"]["information"]}
    source_order = {value: index for index, value in enumerate(packet["source_data_ids"])}
    result = []
    for ordinal, target in enumerate(manifest["targets"]):
        unit = units[target["information_id"]]
        ranges = [part for start, end in target["char_ranges"]
                  for part in _split_range(unit["content"], start, end)]
        if not ranges:
            ranges = [None]
        for part_index, span in enumerate(ranges):
            media = target["media_sha256s"] if part_index == 0 else []
            result.append({
                "target_id": target["target_id"],
                "target_ordinal": ordinal,
                "part_index": part_index,
                "information_id": target["information_id"],
                "data_id": target["data_id"],
                "source_execution_id": target["source_execution_id"],
                "source_block_id": target["source_block_id"],
                "mapping_status": target["mapping_status"],
                "page_index": _page(target),
                "char_ranges": [] if span is None else [list(span)],
                "full_char_ranges": deepcopy(target["char_ranges"]),
                "media_sha256s": list(media),
                "source_refs": [{key: ref[key] for key in
                    ("block_id", "page_index", "bbox", "raw_locator", "anchor_sha256", "text_range")
                    if key in ref} for ref in target["source_refs"]],
                "content_sha256": target["content_sha256"],
                "source_order": source_order[target["data_id"]],
            })
    return sorted(result, key=lambda item: (
        item["source_order"], item["page_index"] is None,
        item["page_index"] if item["page_index"] is not None else item["target_ordinal"],
        item["target_ordinal"], item["part_index"]))


def _partition(packet, manifest):
    units = {unit["information_id"]: unit for unit in packet["model_input"]["information"]}
    batches, current, characters, images = [], [], 0, set()
    for segment in _segments(packet, manifest):
        size = sum(end - start for start, end in segment["char_ranges"])
        added = set(segment["media_sha256s"]) - images
        if current and (characters + size > MAX_SOURCE_CHARACTERS or len(images | added) > MAX_IMAGES):
            batches.append(current)
            current, characters, images = [], 0, set()
        current.append(segment)
        characters += size
        images.update(segment["media_sha256s"])
    if current:
        batches.append(current)

    result = []
    for index, segments in enumerate(batches, 1):
        target_ids = list(dict.fromkeys(item["target_id"] for item in segments))
        information_ids = list(dict.fromkeys(item["information_id"] for item in segments))
        image_sha256s = list(dict.fromkeys(
            sha for item in segments for sha in item["media_sha256s"]))
        slices = []
        for item in segments:
            unit = units[item["information_id"]]
            slices.append({key: deepcopy(item[key]) for key in (
                "target_id", "information_id", "data_id", "source_execution_id",
                "source_block_id", "mapping_status", "page_index", "source_refs",
                "content_sha256", "char_ranges", "full_char_ranges", "media_sha256s")} | {
                "text": [{"char_start": start, "char_end": end,
                          "content": unit["content"][start:end]}
                         for start, end in item["char_ranges"]]})
        result.append({"batch_id": f"b{index:04d}", "target_ids": target_ids,
                       "information_ids": information_ids, "image_sha256s": image_sha256s,
                       "target_slices": slices})
    _check_plan(packet, manifest, result)
    return result


def _check_plan(packet, manifest, batches):
    expected_ranges = {target["target_id"]: target["char_ranges"] for target in manifest["targets"]}
    expected_media = {target["target_id"]: target["media_sha256s"] for target in manifest["targets"]}
    actual_ranges = {key: [] for key in expected_ranges}
    actual_media = {key: [] for key in expected_ranges}
    seen_ids = set()
    for batch in batches:
        if batch["batch_id"] in seen_ids:
            _fail("batched_i2k_plan_changed", 6)
        seen_ids.add(batch["batch_id"])
        if batch["target_ids"] != list(dict.fromkeys(row["target_id"] for row in batch["target_slices"])):
            _fail("batched_i2k_plan_changed", 6)
        if batch["information_ids"] != list(dict.fromkeys(row["information_id"] for row in batch["target_slices"])):
            _fail("batched_i2k_plan_changed", 6)
        for row in batch["target_slices"]:
            if row["target_id"] not in expected_ranges:
                _fail("batched_i2k_plan_changed", 6)
            if row["full_char_ranges"] != expected_ranges[row["target_id"]]:
                _fail("batched_i2k_plan_changed", 6)
            actual_ranges[row["target_id"]].extend(row["char_ranges"])
            actual_media[row["target_id"]].extend(row["media_sha256s"])
    if any(not _same_coverage(actual_ranges[key], expected_ranges[key])
           or sorted(actual_media[key]) != sorted(expected_media[key])
           for key in expected_ranges):
        _fail("batched_i2k_coverage_mismatch", 6)
    required = {asset["sha256"] for asset in packet["media_assets"]}
    if {sha for batch in batches for sha in batch["image_sha256s"]} != required:
        _fail("batched_i2k_media_coverage_mismatch", 6)


def _same_coverage(actual, expected):
    pending = sorted(tuple(span) for span in actual)
    for lo, hi in expected:
        cursor = lo
        while pending and pending[0][0] == cursor and pending[0][1] <= hi:
            cursor = pending.pop(0)[1]
        if cursor != hi:
            return False
    return not pending


def _subset_manifest(manifest, target_ids):
    selected = [deepcopy(target) for target in manifest["targets"] if target["target_id"] in set(target_ids)]
    value = {"schema_version": source_review.PROFILE, "targets": selected}
    return {**value, "manifest_sha256": digest(value)}


def _restrict_generation_schema(schema, batch):
    result = deepcopy(schema)
    ids, media = batch["information_ids"], batch["image_sha256s"]
    blocks = list(_fully_delivered_blocks(batch))
    evidence = result["properties"]["nodes"]["items"]["properties"]["evidence"]["items"]
    for branch in evidence.get("anyOf", [evidence]):
        branch["properties"]["information_id"]["enum"] = ids
        if "media_sha256" in branch["properties"]:
            branch["properties"]["media_sha256"]["enum"] = [*media, None]
        if "source_block_id" in branch["properties"]:
            branch["properties"]["source_block_id"]["enum"] = blocks
    result["properties"]["reviews"]["items"]["properties"]["information_id"]["enum"] = ids
    request = result["properties"]["source_requests"]["items"]["properties"]
    request["information_ids"]["items"]["enum"] = ids
    request["data_id"]["enum"] = list(dict.fromkeys(row["data_id"] for row in batch["target_slices"]))
    return result


def _generation_prompt(snapshot, batch, attachment_order):
    existing = {"nodes": snapshot["existing_nodes"], "edges": snapshot["existing_edges"],
                "previous_review": snapshot.get("selection_feedback")}
    source = {"batch_id": batch["batch_id"], "target_slices": batch["target_slices"],
              "image_attachment_order": attachment_order}
    return multi_source_prompts._policy(snapshot) + _review_policy(snapshot) + """
TASK: Batched I2K Generator. Review every delivered target slice and image. Return
one Information review for each information_id present in this batch and one
source_reviews row for each target_id present in this batch. Extract only explicit
source content. This batch is one resumable part of an exhaustive source review;
do not claim anything from omitted document ranges. Prefer source_block_id evidence
when the full addressed block is delivered. Keep labels, reasons, and coverage
notes concise. Candidate and item keys only need to be unique inside this batch.
EXISTING_K_JSON:
""" + json.dumps(existing, ensure_ascii=False, sort_keys=True, default=str) + \
        "\nBATCH_SOURCE_JSON:\n" + json.dumps(source, ensure_ascii=False, sort_keys=True)


def _restrict_validation_schema(schema, batch, candidate_keys):
    result = deepcopy(schema)
    assigned = [key for key in candidate_keys if key.startswith(batch["batch_id"] + ".")]
    result["properties"]["decisions"]["minItems"] = len(assigned)
    result["properties"]["decisions"]["maxItems"] = len(assigned)
    decision = result["properties"]["decisions"]["items"]
    for branch in decision.get("anyOf", [decision]):
        branch["properties"]["candidate_key"]["enum"] = assigned
        equivalent = branch["properties"].get("equivalent_candidate_key")
        if equivalent is not None and equivalent.get("enum") not in ([None], None):
            equivalent["enum"] = candidate_keys
    result["properties"]["reviews"]["items"]["properties"]["information_id"]["enum"] = batch["information_ids"]
    return result


def _candidate_summary(candidate):
    return {key: deepcopy(candidate.get(key)) for key in
            ("candidate_key", "kind", "statement", "semantic_payload", "identity_scope", "source_data_id")}


def _validation_prompt(snapshot, batch, context, assigned, attachment_order):
    source = {"batch_id": batch["batch_id"], "target_slices": batch["target_slices"],
              "image_attachment_order": attachment_order}
    catalog = [_candidate_summary(candidate) for candidate in context["candidates"]]
    return multi_source_prompts._policy(snapshot) + _review_policy(snapshot) + """
TASK: Batched independent I2K Validator. Re-read every delivered target slice and
image. Audit every assigned candidate against its source evidence and compare its
meaning with the complete candidate catalog and existing K. Return one decision
for each assigned candidate, one Information review for each information_id in
this batch, and exhaustive source-review decisions for the delivered target/items.
Use needs_review whenever evidence or batch coverage is insufficient. Keep reasons
concise and do not infer new knowledge.
BATCH_SOURCE_JSON:
""" + json.dumps(source, ensure_ascii=False, sort_keys=True) + \
        "\nASSIGNED_CANDIDATES_JSON:\n" + json.dumps(assigned, ensure_ascii=False, sort_keys=True, default=str) + \
        "\nALL_CANDIDATE_SUMMARIES_JSON:\n" + json.dumps(catalog, ensure_ascii=False, sort_keys=True, default=str) + \
        "\nEXISTING_K_JSON:\n" + json.dumps(snapshot["existing_nodes"], ensure_ascii=False, sort_keys=True, default=str)


def requests(context, phase):
    snapshot, packet, manifest, expected = _snapshot(context, phase)
    batches = _partition(packet, manifest)
    candidates = context.get("candidates", []) if phase == "validator" else []
    candidate_keys = [candidate["candidate_key"] for candidate in candidates]
    generator_reviews = {row["target_id"]: row for row in context.get("source_reviews", [])}
    result = []
    for batch in batches:
        subset = _subset_manifest(manifest, batch["target_ids"])
        attachment_order = [{"image_number": index + 1, "sha256": sha}
                            for index, sha in enumerate(batch["image_sha256s"])]
        if phase == "generator":
            schema = source_review.extend_generation(
                _restrict_generation_schema(multi.generation_schema(packet), batch), subset)
            prompt = _generation_prompt(snapshot, batch, attachment_order)
        else:
            assigned = [candidate for candidate in candidates
                        if candidate["candidate_key"].startswith(batch["batch_id"] + ".")]
            schema = _restrict_validation_schema(
                multi.validation_schema(candidate_keys,
                    [node["knode_revision_id"] for node in snapshot["existing_nodes"]], packet),
                batch, candidate_keys)
            reviews = []
            for target_id in batch["target_ids"]:
                row = generator_reviews.get(target_id)
                if row is None:
                    _fail("batched_i2k_generator_context_changed", 6)
                items = [deepcopy(item) for item in row["items"]
                         if item["item_key"].startswith(batch["batch_id"] + ".")]
                if not items:
                    _fail("batched_i2k_generator_context_changed", 6)
                reviews.append({"target_id": target_id, "items": items})
            schema = source_review.extend_validation(schema, subset, reviews)
            prompt = _validation_prompt(snapshot, batch, context, assigned, attachment_order)
        request = {"prompt": prompt, "schema": schema,
                   "image_sha256s": batch["image_sha256s"],
                   "input_sha256": digest({"profile": PROFILE, "phase": phase,
                                           "parent_input_sha256": expected, "batch": batch,
                                           "prompt_sha256": sha256(prompt.encode()).hexdigest(),
                                           "schema_sha256": digest(schema)}),
                   "delivered_information_ids": batch["information_ids"],
                   "delivered_source_target_ids": batch["target_ids"],
                   "batch_id": batch["batch_id"], "output_file": "response.json"}
        result.append({**batch, "request": request})
    return {"schema_version": PROFILE, "phase": phase, "parent_input_sha256": expected,
            "implementation_sha256": implementation_sha256(), "batches": result,
            "plan_sha256": digest([{key: batch[key] for key in
                ("batch_id", "target_ids", "information_ids", "image_sha256s", "target_slices")}
                for batch in result])}


def _check_exchange(batch, exchange, model):
    if not isinstance(exchange, dict) or set(exchange) != {"response", "receipt"}:
        _fail("invalid_batched_i2k_exchange")
    response, receipt, request = exchange["response"], exchange["receipt"], batch["request"]
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("profile"), dict)
            or any(receipt["profile"].get(key) != value for key, value in model.items())
            or receipt.get("actual_delivery") is not True
            or receipt.get("original_pdf_delivered") is not False
            or not isinstance(receipt.get("provider_ref"), str) or not receipt["provider_ref"]
            or receipt.get("input_sha256") != request["input_sha256"]
            or receipt.get("output_sha256") != digest(response)
            or receipt.get("prompt_sha256") != sha256(request["prompt"].encode()).hexdigest()
            or receipt.get("schema_sha256") != digest(request["schema"])
            or receipt.get("delivered_information_ids") != request["delivered_information_ids"]
            or receipt.get("delivered_source_target_ids") != request["delivered_source_target_ids"]
            or receipt.get("batch_id") != request["batch_id"]):
        _fail("batched_i2k_receipt_mismatch", 6)
    expected_images = [{"sha256": sha, "byte_size": next(
        asset["byte_size"] for asset in batch["packet_media"] if asset["sha256"] == sha)}
        for sha in request["image_sha256s"]]
    if receipt.get("image_attachments") != expected_images:
        _fail("batched_i2k_media_delivery_mismatch", 6)
    return response


def _fully_delivered_blocks(batch, information_id=None):
    by_target = {}
    for row in batch["target_slices"]:
        if information_id is not None and row["information_id"] != information_id:
            continue
        value = by_target.setdefault(row["target_id"], {
            "source_block_id": row["source_block_id"], "full": row["full_char_ranges"], "actual": []})
        value["actual"].extend(row["char_ranges"])
    return {value["source_block_id"] for value in by_target.values()
            if value["source_block_id"] is not None
            and _same_coverage(value["actual"], value["full"])}


def _anchor_delivered(batch, target_id, anchor):
    rows = [row for row in batch["target_slices"] if row["target_id"] == target_id]
    if not isinstance(anchor, dict):
        return False
    start, end, media = anchor.get("char_start"), anchor.get("char_end"), anchor.get("media_sha256")
    if media is not None:
        return start is None and end is None and any(media in row["media_sha256s"] for row in rows)
    return (type(start) is int and type(end) is int and start < end
            and any(lo <= start < end <= hi for row in rows for lo, hi in row["char_ranges"]))


def _validate_generator_response(batch, response):
    required = {"nodes", "reviews", "source_requests", "complete", "coverage_notes", "source_reviews"}
    if not isinstance(response, dict) or set(response) != required or type(response["complete"]) is not bool:
        _fail("invalid_batched_i2k_generator_response")
    info = set(batch["information_ids"])
    targets = set(batch["target_ids"])
    candidate_keys = []
    for node in response["nodes"]:
        key = node.get("candidate_key") if isinstance(node, dict) else None
        if not isinstance(key, str) or key in candidate_keys:
            _fail("invalid_batched_i2k_generator_response")
        candidate_keys.append(key)
        for citation in node.get("evidence", []):
            identifier = citation.get("information_id") if isinstance(citation, dict) else None
            if identifier not in info:
                _fail("batched_i2k_undelivered_evidence", 6)
            if "source_block_id" in citation:
                block = citation["source_block_id"]
                if block not in _fully_delivered_blocks(batch, identifier):
                    _fail("batched_i2k_undelivered_evidence", 6)
            else:
                media, quote = citation.get("media_sha256"), citation.get("quote")
                owned_media = {sha for row in batch["target_slices"]
                               if row["information_id"] == identifier for sha in row["media_sha256s"]}
                if media is not None and media not in owned_media:
                    _fail("batched_i2k_undelivered_evidence", 6)
                if quote:
                    texts = [row["content"] for target in batch["target_slices"]
                             if target["information_id"] == identifier for row in target["text"]]
                    if not any(quote in text for text in texts):
                        _fail("batched_i2k_undelivered_evidence", 6)
    if {row.get("information_id") for row in response["reviews"] if isinstance(row, dict)} != info \
            or len(response["reviews"]) != len(info):
        _fail("batched_i2k_information_coverage_mismatch", 6)
    if {row.get("target_id") for row in response["source_reviews"] if isinstance(row, dict)} != targets \
            or len(response["source_reviews"]) != len(targets):
        _fail("batched_i2k_target_coverage_mismatch", 6)
    for row in response["source_reviews"]:
        if not isinstance(row.get("items"), list) or not row["items"]:
            _fail("invalid_batched_i2k_generator_response")
        for item in row["items"]:
            keys = item.get("candidate_keys") if isinstance(item, dict) else None
            anchors = item.get("anchors") if isinstance(item, dict) else None
            if (not isinstance(keys, list) or any(key not in candidate_keys for key in keys)
                    or not isinstance(anchors, list)
                    or any(not _anchor_delivered(batch, row["target_id"], anchor) for anchor in anchors)):
                _fail("batched_i2k_undelivered_source_review", 6)
    data_ids = {row["data_id"] for row in batch["target_slices"]}
    for request in response["source_requests"]:
        if (not isinstance(request, dict) or request.get("data_id") not in data_ids
                or not isinstance(request.get("information_ids"), list)
                or any(identifier not in info for identifier in request["information_ids"])):
            _fail("batched_i2k_undelivered_source_request", 6)
    return candidate_keys


def _namespace_generator(batch, response):
    raw_keys = _validate_generator_response(batch, response)
    mapping = {key: f"{batch['batch_id']}.c{index:04d}" for index, key in enumerate(raw_keys, 1)}
    value = deepcopy(response)
    for node in value["nodes"]:
        node["candidate_key"] = mapping[node["candidate_key"]]
    for review in value["reviews"]:
        review["candidate_keys"] = [mapping[key] for key in review["candidate_keys"]]
    item_index = 0
    for row in value["source_reviews"]:
        for item in row["items"]:
            item_index += 1
            item["item_key"] = f"{batch['batch_id']}.i{item_index:04d}"
            item["candidate_keys"] = [mapping[key] for key in item["candidate_keys"]]
    return value


def _merge_generator(plan, responses):
    packet = plan["packet"]
    nodes, source_requests, notes = [], [], []
    by_info = {identifier: [] for identifier in packet["target_information_ids"]}
    by_target = {}
    complete = True
    for batch, raw in zip(plan["batches"], responses):
        value = _namespace_generator(batch, raw)
        nodes.extend(value["nodes"])
        source_requests.extend(value["source_requests"])
        notes.extend(f"{batch['batch_id']}: {note}" for note in value["coverage_notes"])
        complete = complete and value["complete"]
        for review in value["reviews"]:
            by_info[review["information_id"]].append(review)
        for row in value["source_reviews"]:
            by_target.setdefault(row["target_id"], []).extend(row["items"])
    actual = {identifier: [node["candidate_key"] for node in nodes
                           if any(citation["information_id"] == identifier for citation in node["evidence"])]
              for identifier in by_info}
    reviews = []
    for identifier in packet["target_information_ids"]:
        rows = by_info[identifier]
        if not rows:
            _fail("batched_i2k_information_coverage_mismatch", 6)
        if any(row["disposition"] == "needs_review" for row in rows):
            disposition = "needs_review"
        elif actual[identifier]:
            disposition = "selected"
        elif any(row["disposition"] == "context_only" for row in rows):
            disposition = "context_only"
        else:
            disposition = "not_selected"
        reviews.append({"information_id": identifier, "disposition": disposition,
                        "candidate_keys": actual[identifier],
                        "reason": "; ".join(dict.fromkeys(row["reason"] for row in rows))})
        complete = complete and disposition != "needs_review"
    source_rows = []
    for target in plan["manifest"]["targets"]:
        items = by_target.get(target["target_id"])
        if not items:
            _fail("batched_i2k_target_coverage_mismatch", 6)
        source_rows.append({"target_id": target["target_id"], "items": items})
    complete = complete and not source_requests
    return {"nodes": nodes, "reviews": reviews, "source_requests": source_requests,
            "complete": complete, "coverage_notes": notes, "source_reviews": source_rows}


def _validate_validator_response(batch, response, assigned, items):
    required = {"decisions", "reviews", "complete", "source_review_decisions"}
    if not isinstance(response, dict) or set(response) != required or type(response["complete"]) is not bool:
        _fail("invalid_batched_i2k_validator_response")
    if ({row.get("candidate_key") for row in response["decisions"]} != set(assigned)
            or len(response["decisions"]) != len(assigned)
            or {row.get("information_id") for row in response["reviews"]} != set(batch["information_ids"])
            or len(response["reviews"]) != len(set(batch["information_ids"]))):
        _fail("batched_i2k_validator_coverage_mismatch", 6)
    review = response["source_review_decisions"]
    if (not isinstance(review, dict) or set(review) != {"targets", "items"}
            or {row.get("target_id") for row in review["targets"]} != set(batch["target_ids"])
            or {row.get("item_key") for row in review["items"]} != set(items)):
        _fail("batched_i2k_validator_coverage_mismatch", 6)


def _merge_validator(plan, context, responses):
    decisions, complete = [], True
    info_rows = {identifier: [] for identifier in plan["packet"]["target_information_ids"]}
    target_rows, item_rows = {}, {}
    generator_reviews = {row["target_id"]: row for row in context["source_reviews"]}
    keys = [candidate["candidate_key"] for candidate in context["candidates"]]
    for batch, response in zip(plan["batches"], responses):
        assigned = [key for key in keys if key.startswith(batch["batch_id"] + ".")]
        items = [item["item_key"] for target in batch["target_ids"]
                 for item in generator_reviews[target]["items"]
                 if item["item_key"].startswith(batch["batch_id"] + ".")]
        _validate_validator_response(batch, response, assigned, items)
        by_key = {row["candidate_key"]: row for row in response["decisions"]}
        decisions.extend(deepcopy(by_key[key]) for key in assigned)
        complete = complete and response["complete"]
        for row in response["reviews"]:
            info_rows[row["information_id"]].append(row)
        for row in response["source_review_decisions"]["targets"]:
            target_rows.setdefault(row["target_id"], []).append(row)
        for row in response["source_review_decisions"]["items"]:
            if row["item_key"] in item_rows:
                _fail("batched_i2k_validator_coverage_mismatch", 6)
            item_rows[row["item_key"]] = deepcopy(row)
    reviews = []
    for identifier in plan["packet"]["target_information_ids"]:
        rows = info_rows[identifier]
        if not rows:
            _fail("batched_i2k_validator_coverage_mismatch", 6)
        verdict = "needs_review" if any(row["verdict"] == "needs_review" for row in rows) else "confirmed"
        reasons = list(dict.fromkeys(code for row in rows for code in row["reason_codes"]))
        reviews.append({"information_id": identifier, "verdict": verdict, "reason_codes": reasons,
                        "reason": "; ".join(dict.fromkeys(row["reason"] for row in rows))})
        complete = complete and verdict == "confirmed"
    targets = []
    for target in plan["manifest"]["targets"]:
        rows = target_rows.get(target["target_id"])
        if not rows:
            _fail("batched_i2k_validator_coverage_mismatch", 6)
        verdict = "needs_review" if any(row["verdict"] == "needs_review" for row in rows) else "confirmed"
        targets.append({"target_id": target["target_id"], "verdict": verdict,
                        "reason": "; ".join(dict.fromkeys(row["reason"] for row in rows))})
        complete = complete and verdict == "confirmed"
    expected_items = [item["item_key"] for row in context["source_reviews"] for item in row["items"]]
    if set(item_rows) != set(expected_items):
        _fail("batched_i2k_validator_coverage_mismatch", 6)
    return {"decisions": decisions, "reviews": reviews, "complete": complete,
            "source_review_decisions": {"targets": targets,
                "items": [item_rows[key] for key in expected_items]}}


def _prepared_plan(context, phase):
    snapshot, packet, manifest, _ = _snapshot(context, phase)
    result = requests(context, phase)
    for batch in result["batches"]:
        batch["packet_media"] = packet["media_assets"]
    result.update(packet=packet, manifest=manifest, snapshot=snapshot)
    return result


def aggregate(context, phase, exchanges, model):
    plan = _prepared_plan(context, phase)
    if not isinstance(exchanges, list) or len(exchanges) != len(plan["batches"]):
        _fail("batched_i2k_batch_coverage_mismatch", 6)
    responses, refs, usage = [], [], {}
    for batch, exchange in zip(plan["batches"], exchanges):
        response = _check_exchange(batch, exchange, model)
        responses.append(response)
        ref = exchange["receipt"]["provider_ref"]
        if ref in refs:
            _fail("batched_i2k_provider_ref_reused", 6)
        refs.append(ref)
        for key, value in exchange["receipt"].get("usage", {}).items():
            if type(value) is int and value >= 0:
                usage[key] = usage.get(key, 0) + value
    output = (_merge_generator(plan, responses) if phase == "generator"
              else _merge_validator(plan, context, responses))
    packet = plan["packet"]
    receipt = {"profile": deepcopy(model), "input_sha256": plan["parent_input_sha256"],
        "output_sha256": digest(output), "provider_ref": "batch:" + digest(refs),
        "actual_delivery": True, "usage": usage,
        "prompt_sha256": digest([sha256(batch["request"]["prompt"].encode()).hexdigest()
                                  for batch in plan["batches"]]),
        "schema_sha256": digest([digest(batch["request"]["schema"]) for batch in plan["batches"]]),
        "image_attachments": [{"sha256": asset["sha256"], "byte_size": asset["byte_size"]}
                              for asset in packet["media_assets"]],
        "delivered_information_ids": list(packet["target_information_ids"]),
        "original_pdf_delivered": False, "delivery_mode": PROFILE,
        "batch_plan_sha256": plan["plan_sha256"],
        "implementation_sha256": implementation_sha256(),
        "batch_exchanges": deepcopy(exchanges)}
    return {"response": output, "receipt": receipt}


def verify_aggregate(receipt, output, job, phase, validation_context=None):
    if receipt.get("delivery_mode") != PROFILE or receipt.get("implementation_sha256") != implementation_sha256():
        _fail("batched_i2k_implementation_changed", 6)
    context = ({"input_snapshot": job["input_snapshot"], "input_digest": job["input_digest"]}
               if phase == "generator" else
               {**(validation_context or {}), "validation_context_sha": job["validation_context_sha"]})
    expected = aggregate(context, phase, receipt.get("batch_exchanges"), job["profile"]["model"])
    check = expected["receipt"]
    for key in ("profile", "input_sha256", "output_sha256", "provider_ref", "actual_delivery",
                "usage", "prompt_sha256", "schema_sha256", "image_attachments",
                "delivered_information_ids", "original_pdf_delivered", "delivery_mode",
                "batch_plan_sha256", "implementation_sha256", "batch_exchanges"):
        if receipt.get(key) != check.get(key):
            _fail("batched_i2k_receipt_mismatch", 6)
    if output != expected["response"]:
        _fail("batched_i2k_merge_mismatch", 6)
    if phase == "validator":
        old = {item["receipt"]["provider_ref"] for item in
               job["generator_receipt"].get("batch_exchanges", [])}
        new = {item["receipt"]["provider_ref"] for item in receipt["batch_exchanges"]}
        if old & new:
            _fail("knowledge_validator_not_independent", 6)
    return True
