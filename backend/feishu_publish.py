from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import time
from typing import Any, Callable
from xml.etree import ElementTree as ET

from .feishu_cli import LarkCli, LarkCommandError
from .feishu_render import render_feishu_document


FOLDER_NAME = "视频策划案生成中心"


@dataclass(frozen=True)
class PublicationRecord:
    status: str
    document_token: str = ""
    document_url: str = ""


ACTIVE_BOARD_KEYS = ("planning", "competitor")


class PublicationConflict(RuntimeError):
    pass


def _idempotent_token(request_id: str, stage: str) -> str:
    """Feishu validates a short idempotency field; node IDs can be very long."""
    digest = hashlib.sha256(f"{request_id}:{stage}".encode("utf-8")).hexdigest()[:40]
    label = re.sub(r"[^a-z0-9]+", "-", stage.lower()).strip("-")[:12] or "write"
    return f"prd-{label}-{digest}"


class ReviewApprovalConflict(PublicationConflict):
    """The pinned review revision is no longer export-ready."""


def _pick(data: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if data.get(name) not in (None, ""):
            return data[name]
    return default


def _token(value: Any) -> str:
    return "" if value in (None, "", "None") else str(value)


def _whiteboard_tokens(data: Any) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        kind = str(data.get("block_type") or data.get("type") or "").lower()
        if kind == "whiteboard" and isinstance(data.get("block_token"), str):
            found.append(data["block_token"])
        for key, value in data.items():
            if key in {"whiteboard_token", "board_token"} and isinstance(value, str):
                found.append(value)
            elif key == "whiteboard_tokens" and isinstance(value, list):
                found.extend(str(item) for item in value)
            else:
                found.extend(_whiteboard_tokens(value))
    elif isinstance(data, list):
        for value in data:
            found.extend(_whiteboard_tokens(value))
    elif isinstance(data, str) and "<whiteboard" in data:
        found.extend(re.findall(r'<whiteboard\b[^>]*\btoken=["\']([^"\']+)["\']', data))
    return found


def _content_values(data: Any) -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in {"content", "xml", "document_content"} and isinstance(value, str):
                values.append(value)
            else:
                values.extend(_content_values(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(_content_values(value))
    return values


def _document_chunks(xml: str, maximum: int = 20000) -> list[str]:
    """Split a long generated document at top-level chapter headings.

    The Feishu importer may accept an oversized create request while only
    retaining its title. Keeping each write below the importer limit also
    preserves the original XML/SVG bytes instead of reparsing them.
    """
    sections = [item for item in re.split(r"(?=<h1(?:\s|>))", xml) if item.strip()]
    chunks: list[str] = []
    current = ""
    for section in sections:
        if current and len(current) + len(section) > maximum:
            chunks.append(current)
            current = ""
        if len(section) <= maximum:
            current += section
            continue
        # A large chapter is split only between complete top-level blocks.
        blocks = [item for item in re.split(r"(?=<(?:h[1-9]|p|ul|ol|table|whiteboard|hr)(?:\s|>))", section) if item.strip()]
        for block in blocks:
            if current and len(current) + len(block) > maximum:
                chunks.append(current)
                current = ""
            current += block
    if current:
        chunks.append(current)
    return chunks


def _inline_image_placeholders(xml: str) -> str:
    """Use text anchors during overwrite; local paths are unsupported there."""
    return re.sub(
        r'<img\s+name="inline-figure-([^"]+)"\s+caption="[^"]*"\s+path="[^"]*"\s*/>',
        lambda match: f'<p>__INLINE_FIGURE_{match.group(1)}__</p>',
        xml,
    )


def _inline_placeholder_ids(data: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for content in _content_values(data):
        for block_id, frame_id in re.findall(
            r'<p\b[^>]*\bid="([^"]+)"[^>]*>\s*__INLINE_FIGURE_([^<]+)__\s*</p>',
            content,
        ):
            mapping[frame_id] = block_id
    return mapping


def _document_data(data: dict[str, Any]) -> dict[str, Any]:
    document = data.get("document")
    return document if isinstance(document, dict) else data


def _structured_whiteboard_identity(data: Any, titles: set[str]) -> tuple[list[str], dict[str, list[str]]]:
    tokens: list[str] = []
    mapping: dict[str, list[str]] = {}
    if isinstance(data, dict):
        token = _token(_pick(data, "whiteboard_token", "board_token", "block_token"))
        kind = str(_pick(data, "block_type", "type", default="")).lower()
        title = str(_pick(data, "title", "name", "heading", default=""))
        if token and ("whiteboard" in kind or "board" in kind):
            tokens.append(token)
            if title in titles:
                mapping.setdefault(title, []).append(token)
        for value in data.values():
            child_tokens, child_mapping = _structured_whiteboard_identity(value, titles)
            tokens.extend(child_tokens)
            for title, child_values in child_mapping.items():
                mapping.setdefault(title, []).extend(child_values)
    elif isinstance(data, list):
        for value in data:
            child_tokens, child_mapping = _structured_whiteboard_identity(value, titles)
            tokens.extend(child_tokens)
            for title, child_values in child_mapping.items():
                mapping.setdefault(title, []).extend(child_values)
    return tokens, mapping


def _document_whiteboard_identity(data: Any, board_titles: tuple[str, ...]) -> tuple[list[str], dict[str, list[str]]]:
    title_set = set(board_titles)
    for content in _content_values(data):
        if "<whiteboard" not in content or re.search(r"<!DOCTYPE|<!ENTITY", content, re.I):
            continue
        try:
            root = ET.fromstring(f"<document>{content}</document>")
        except ET.ParseError:
            continue
        heading = ""
        tokens: list[str] = []
        mapping: dict[str, list[str]] = {}
        for node in root.iter():
            name = node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""
            if re.fullmatch(r"h[1-9]", name):
                heading = "".join(node.itertext()).strip()
                if heading.startswith("图示："):
                    heading = heading.removeprefix("图示：").strip()
            elif name == "whiteboard":
                token = _token(node.attrib.get("token"))
                if token:
                    tokens.append(token)
                    if heading in title_set:
                        mapping.setdefault(heading, []).append(token)
        if tokens:
            return tokens, mapping
    structured_tokens, structured_mapping = _structured_whiteboard_identity(data, title_set)
    if structured_tokens:
        return structured_tokens, structured_mapping
    return _whiteboard_tokens(data), {}


def _safe_media_arg(path: Path) -> str:
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(Path.cwd().resolve())
        except ValueError as exc:
            raise ValueError("media path must stay inside the project") from exc
    if ".." in path.parts:
        raise ValueError("media path must stay inside the project")
    return path.as_posix()


def _openapi_id_map(*payloads: Any) -> dict[str, str]:
    """Map planner-readable ids to the typed ids required by Feishu raw nodes."""
    node_types: dict[str, str] = {}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            node_id = value.get("id")
            node_type = value.get("type")
            if isinstance(node_id, str) and isinstance(node_type, str):
                node_types[node_id] = node_type
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for payload in payloads:
        collect(payload)
    result: dict[str, str] = {}
    used: set[str] = set()
    for source_id, node_type in sorted(node_types.items()):
        prefix = "c" if node_type == "connector" else "a" if node_type == "text_shape" else "o"
        number = int(hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:12], 16) % 2_000_000_000 + 1
        target = f"{prefix}001:{number}"
        if target in used:
            raise ValueError("whiteboard node id hash collision")
        used.add(target)
        result[source_id] = target
    return result


def _normalize_openapi_ids(payload: Any, id_map: dict[str, str]) -> Any:
    if isinstance(payload, dict):
        return {
            key: id_map.get(value, value) if key == "id" and isinstance(value, str)
            else _normalize_openapi_ids(value, id_map)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [id_map.get(value, value) if isinstance(value, str) else _normalize_openapi_ids(value, id_map) for value in payload]
    return payload


def _structure_without_pending_images(structure: dict[str, Any], id_map: dict[str, str] | None = None) -> dict[str, Any]:
    """Images are added only after Feishu returns a media token."""
    image_ids = {
        str(node.get("id"))
        for node in structure.get("nodes") or []
        if isinstance(node, dict) and node.get("type") == "image" and node.get("id")
    }
    structure_nodes: list[Any] = []
    for node in structure.get("nodes") or []:
        if isinstance(node, dict) and node.get("type") == "image":
            continue
        if isinstance(node, dict) and isinstance(node.get("children"), list):
            node = {**node, "children": [child for child in node["children"] if str(child) not in image_ids]}
        structure_nodes.append(node)
    result = {
        **structure,
        "nodes": structure_nodes,
    }
    return _normalize_openapi_ids(result, id_map or _openapi_id_map(structure))


def _token_backed_image_node(node: dict[str, Any], media_token: str, id_map: dict[str, str] | None = None) -> dict[str, Any]:
    # Keep the complete board-layout identity. Real Feishu image nodes carry an
    # id and style alongside x/y/width/height; only the media token is injected
    # after upload. Payload revisions must also use a fresh idempotency key.
    allowed = {"id", "type", "x", "y", "width", "height", "locked", "z_index", "style"}
    result = {**{key: value for key, value in node.items() if key in allowed}, "image": {"token": media_token}}
    # Feishu may assign the first separately-created image z=0, below an
    # existing Section background, so the raw node exists while the preview is
    # blank.  Pin uploaded evidence above structural background nodes.
    result.setdefault("z_index", 1000)
    return _normalize_openapi_ids(result, id_map or _openapi_id_map(node))


def _preview_svg_fast_path_allowed(preview_svg: str, board: Any) -> bool:
    """Use direct SVG import only when it cannot silently drop screenshots.

    Feishu can accept a data-URI-rich SVG while stripping its raster images.
    A subsequent non-empty raw query then verifies only the vector shell.
    Screenshot-bearing boards must use token-backed native image nodes.
    """
    if not preview_svg or getattr(board, "images", None):
        return False
    svg_size = len(preview_svg.encode("utf-8"))
    svg_width_match = re.search(r'<svg\b[^>]*\bwidth="([0-9.]+)"', preview_svg)
    svg_width = float(svg_width_match.group(1)) if svg_width_match else 0
    return svg_size <= 900_000 and svg_width <= 4_096


def _image_create_node(node: dict[str, Any], media_token: str) -> dict[str, Any]:
    """Create first; Feishu rejects x/y on some image-node create paths."""
    return {
        "type": "image",
        # Use the API's known-safe creation size. The real size and position are
        # applied in the second update after Feishu returns a node ID.
        "width": 320,
        "height": 180,
        "image": {"token": media_token},
    }


def _created_node_id(data: dict[str, Any]) -> str:
    values = _pick(data, "created_node_ids", "createdNodeIds", default=[])
    if isinstance(values, str):
        return values
    if isinstance(values, list) and values:
        first = values[0]
        if isinstance(first, dict):
            return _token(_pick(first, "id", "node_id", "nodeId"))
        return str(first)
    if isinstance(values, dict) and values:
        first = next(iter(values.values()))
        if isinstance(first, dict):
            return _token(_pick(first, "id", "node_id", "nodeId"))
        return str(first)
    return ""


def _active_map(value: Any, board_keys: tuple[str, ...] = ACTIVE_BOARD_KEYS) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {key: source[key] for key in board_keys if key in source}


def _board_checkpoint(record: dict[str, Any], board_keys: tuple[str, ...] = ACTIVE_BOARD_KEYS) -> dict[str, Any]:
    """Normalize legacy checkpoints into the active delivery view."""
    tokens = dict(record.get("boardTokens") or {})
    if _token(record.get("boardToken")) and "planning" not in tokens:
        tokens["planning"] = _token(record["boardToken"])
    structure = dict(record.get("boardStructureRequestIds") or {})
    if record.get("boardStructureRequestId") and "planning" not in structure:
        structure["planning"] = str(record["boardStructureRequestId"])
    media = dict(record.get("boardMediaDone") or {})
    if media and not all(isinstance(value, dict) for value in media.values()):
        media = {"planning": media}
    media_nodes = dict(record.get("boardMediaNodesDone") or {})
    if media_nodes and not all(isinstance(value, dict) for value in media_nodes.values()):
        media_nodes = {"planning": media_nodes}
    verified = _active_map(record.get("boardVerified"), board_keys)
    return {
        "boardTokens": _active_map(tokens, board_keys),
        "boardStructureRequestIds": _active_map(structure, board_keys),
        "boardMediaDone": _active_map(media, board_keys),
        "boardMediaNodesDone": _active_map(media_nodes, board_keys),
        "boardVerified": {key: bool(verified.get(key)) for key in board_keys},
    }


def _checkpoint_changes(record: dict[str, Any], checkpoint: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge active work into storage without changing legacy board entries."""
    changes: dict[str, dict[str, Any]] = {}
    for field, active in checkpoint.items():
        stored = record.get(field)
        if field in {"boardMediaDone", "boardMediaNodesDone"} and isinstance(stored, dict) and stored and not all(
            isinstance(value, dict) for value in stored.values()
        ):
            stored = {"planning": stored}
        merged = dict(stored) if isinstance(stored, dict) else {}
        merged.update(active)
        changes[field] = merged
    return changes


def _clear_active_checkpoint(record: dict[str, Any], board_keys: tuple[str, ...] = ACTIVE_BOARD_KEYS) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for field in ("boardStructureRequestIds", "boardMediaDone", "boardMediaNodesDone", "boardVerified", "boardTokens"):
        values = record.get(field)
        if isinstance(values, dict):
            changes[field] = {
                key: value for key, value in values.items()
                if key not in board_keys and (field not in {"boardMediaDone", "boardMediaNodesDone"} or isinstance(value, dict))
            }
    return changes


def _raw_board_has_content(raw: dict[str, Any]) -> bool:
    nodes = raw.get("nodes")
    if not isinstance(nodes, list):
        data = raw.get("data")
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            nodes = data["nodes"]
    if isinstance(nodes, list):
        if not nodes:
            return False
        sections = [node for node in nodes if isinstance(node, dict) and node.get("type") == "section"]
        for image in (node for node in nodes if isinstance(node, dict) and node.get("type") == "image"):
            if not _token((image.get("image") or {}).get("token")):
                return False
            image_left = float(image.get("x") or 0)
            image_top = float(image.get("y") or 0)
            image_right = image_left + float(image.get("width") or 0)
            image_bottom = image_top + float(image.get("height") or 0)
            image_layer = int(image.get("z_index") or 0)
            for section in sections:
                section_left = float(section.get("x") or 0)
                section_top = float(section.get("y") or 0)
                section_right = section_left + float(section.get("width") or 0)
                section_bottom = section_top + float(section.get("height") or 0)
                overlaps = (
                    image_left < section_right
                    and image_right > section_left
                    and image_top < section_bottom
                    and image_bottom > section_top
                )
                if overlaps and image_layer <= int(section.get("z_index") or 0):
                    return False
        return True
    return bool(str(_pick(raw, "code", "content", "value", default="")).strip())


def _raw_board_has_expected_images(raw: dict[str, Any], expected_count: int) -> bool:
    if expected_count <= 0:
        return True
    nodes = raw.get("nodes")
    if not isinstance(nodes, list):
        data = raw.get("data")
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            nodes = data["nodes"]
    if not isinstance(nodes, list):
        return False
    visible_native_images = 0
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "image":
            continue
        token = _token((node.get("image") or {}).get("token"))
        if (
            float(node.get("width") or 0) > 0
            and float(node.get("height") or 0) > 0
            and token
            and not token.lstrip().startswith("<svg")
        ):
            visible_native_images += 1
    return visible_native_images >= expected_count


class FeishuPublisher:
    def __init__(
        self,
        cli: LarkCli,
        job_dir: Path,
        save: Callable[[dict[str, Any], list[dict[str, Any]] | None], dict[str, Any] | None] | None = None,
        wait: Callable[[float], None] = time.sleep,
        approval_guard: Callable[[], None] | None = None,
    ) -> None:
        self.cli = cli
        self.job_dir = job_dir
        self.save = save or (lambda publication, history=None: None)
        self.wait = wait
        self.approval_guard = approval_guard or (lambda: None)

    def _guard_write(self) -> None:
        self.approval_guard()

    @staticmethod
    def _requires_clean_board_rebuild(checkpoint: dict[str, Any], key: str, board: Any) -> bool:
        """Reject a false resume point after a complete media pass failed verification.

        Once every expected image node is recorded as written, a false
        ``boardVerified`` value means the remote composition itself failed.
        Reusing that structure/media checkpoint would only reproduce hidden or
        duplicate nodes, so the next attempt must start from a clean overwrite.
        """
        if checkpoint.get("boardVerified", {}).get(key) is True:
            return False
        expected_nodes = {
            str(image.node.get("id") or f"{image.frame_id}-{index}")
            for index, image in enumerate(board.images, 1)
        }
        completed_nodes = set((checkpoint.get("boardMediaNodesDone", {}).get(key) or {}).keys())
        return bool(expected_nodes) and expected_nodes.issubset(completed_nodes)

    def _query_ready_board(self, token: str) -> dict[str, Any]:
        args = ["whiteboard", "+query", "--whiteboard-token", token, "--output_as", "raw", "--as", "user", "--json"]
        for delay in (0, 1, 2, 4):
            if delay:
                self.wait(delay)
            try:
                self._guard_write()
                raw = self.cli.run(args).data
                # SVG/raw writes are eventually consistent.  A successful
                # query can briefly return an empty node list; do not turn
                # that transient state into a false delivery failure.
                if _raw_board_has_content(raw) or delay == 4:
                    return raw
            except LarkCommandError as exc:
                message = str(exc).lower()
                transient = "not ready" in message or ("unknown idtype" in message and "whiteboard" in message)
                if not transient or delay == 4:
                    raise
        raise LarkCommandError("command_failed", "UE flow whiteboard was not ready")

    @staticmethod
    def _is_transient_media_read_error(exc: LarkCommandError) -> bool:
        message = str(exc).lower()
        return "api call failed: get" in message and any(
            marker in message for marker in ("eof", "connection reset", "timed out")
        )

    def _upload_media_with_retry(self, args: list[str]) -> dict[str, Any]:
        for delay in (0, 1, 2):
            if delay:
                self.wait(delay)
            try:
                self._guard_write()
                return self.cli.run(args).data
            except LarkCommandError as exc:
                if not self._is_transient_media_read_error(exc) or delay == 2:
                    raise
        raise LarkCommandError("command_failed", "whiteboard media upload failed")

    def _persist(self, job: dict[str, Any], record: dict[str, Any], **changes: Any) -> None:
        record.update(changes, updatedAt=datetime.now(timezone.utc).isoformat())
        job["feishuPublication"] = record
        persisted = self.save(dict(record), job.get("feishuPublicationHistory"))
        if persisted is not None:
            record.clear()
            record.update(persisted)

    def _folder_token(self, job: dict[str, Any], record: dict[str, Any]) -> str:
        if record.get("folderToken"):
            return str(record["folderToken"])
        listing = self.cli.run(["drive", "files", "list", "--page-all", "--as", "user", "--json"]).data
        files = listing.get("files") or listing.get("items") or []
        match = next((item for item in files if item.get("name") == FOLDER_NAME and item.get("type") in {None, "folder"}), None)
        if match:
            token = _token(_pick(match, "token", "file_token", "folder_token"))
        else:
            self._guard_write()
            created = self.cli.run(["drive", "+create-folder", "--name", FOLDER_NAME, "--as", "user", "--json"]).data
            token = _token(_pick(created, "token", "file_token", "folder_token"))
        self._persist(job, record, folderToken=token, status="creating_document")
        return token

    def publish(self, job: dict[str, Any], request_id: str, mode: str) -> PublicationRecord:
        if mode not in {"update", "new_version"}:
            raise ValueError("mode must be update or new_version")
        if job.get("status") != "completed" or not job.get("planningModel"):
            raise ValueError("completed planning model required")
        current = job.get("feishuPublication") or {}
        rendered = render_feishu_document(job, self.job_dir)
        same_delivery = (
            current.get("requestId") == request_id
            and current.get("status") == "published"
            and current.get("fingerprint") == rendered.content_fingerprint
        )
        invalid_verified_boards: set[str] = set()
        if same_delivery:
            board_keys = tuple(board.key for board in rendered.native_boards)
            board_by_key = {board.key: board.board for board in rendered.native_boards}
            checkpoint = _board_checkpoint(current, board_keys)
            for key in board_keys:
                token = _token(checkpoint["boardTokens"].get(key))
                if not token or checkpoint["boardVerified"].get(key) is not True:
                    invalid_verified_boards.add(key)
                    continue
                queried = self._query_ready_board(token)
                if (
                    not _raw_board_has_content(queried)
                    or not _raw_board_has_expected_images(queried, len(board_by_key[key].images))
                ):
                    invalid_verified_boards.add(key)
            if not invalid_verified_boards:
                return PublicationRecord("published", current.get("documentToken", ""), current.get("documentUrl", ""))
        recover_partial = current.get("requestId") == request_id and (
            current.get("status") == "partial" or current.get("resumePartial") is True
        )
        if mode == "new_version" and current.get("documentToken"):
            job.setdefault("feishuPublicationHistory", []).append(dict(current))
            current = {
                "version": len(job["feishuPublicationHistory"]) + 1,
                "folderToken": current.get("folderToken", ""),
                "folderName": current.get("folderName", ""),
            }

        record = current
        self._persist(job, record, requestId=request_id, status="checking_auth")
        auth = self.cli.auth_status()
        user = (auth.get("identities") or {}).get("user") or {}
        if auth.get("identity") != "user" or user.get("status") in {"missing", "expired", "invalid"}:
            self._persist(job, record, status="failed", message="飞书登录已过期")
            raise LarkCommandError("not_authenticated", "Feishu user login is required")

        document_chunks = _document_chunks(_inline_image_placeholders(rendered.xml))
        if not document_chunks:
            raise LarkCommandError("command_failed", "Rendered Feishu document is empty")
        board_keys = tuple(board.key for board in rendered.native_boards)
        folder_token = self._folder_token(job, record)
        document_token = _token(record.get("documentToken"))
        expected_whiteboard_total = len(rendered.native_boards) + rendered.embedded_whiteboard_count
        document_content_complete = bool(
            (
                record.get("documentContentComplete") is True
                and len(set(record.get("whiteboardTokens") or [])) == expected_whiteboard_total
            )
            or (
                record.get("fingerprint") == rendered.content_fingerprint
                and (record.get("whiteboardTokens") or record.get("boardTokens") or record.get("boardToken"))
            )
        )
        if recover_partial and not document_token:
            listing = self.cli.run([
                "drive", "files", "list", "--folder-token", folder_token,
                "--page-all", "--as", "user", "--json",
            ]).data
            files = listing.get("files") or listing.get("items") or []
            match = next((item for item in files if item.get("name") == rendered.title and item.get("type") == "docx"), None)
            if match:
                document_token = _token(_pick(match, "token", "document_id", "document_token"))
                self._persist(
                    job, record, documentToken=document_token,
                    documentUrl=str(_pick(match, "url", "document_url", default="")),
                    status="creating_whiteboard",
                )
        if document_token and (
            record.get("fingerprint") != rendered.content_fingerprint or not document_content_complete
        ):
            fetched = self.cli.run(["docs", "+fetch", "--doc", document_token, "--scope", "full", "--detail", "full", "--as", "user", "--json"]).data
            fetched_document = _document_data(fetched)
            remote_revision = int(_pick(fetched_document, "revision_id", "revisionId", default=-1))
            if not recover_partial and remote_revision != int(record.get("revision", -2)):
                self._persist(job, record, status="conflict", message="飞书文档已有修改，不会自动覆盖")
                raise PublicationConflict(record["message"])
            self._guard_write()
            updated = self.cli.run([
                "docs", "+update", "--doc", document_token, "--command", "overwrite",
                "--revision-id", str(remote_revision), "--content", "-", "--as", "user", "--json",
            ], stdin=document_chunks[0]).data
            imported_tokens = _whiteboard_tokens(updated)
            updated_document = _document_data(updated)
            remote_revision = int(_pick(updated_document, "revision_id", "revisionId", default=remote_revision + 1))
            for chunk in document_chunks[1:]:
                appended = self.cli.run([
                    "docs", "+update", "--doc", document_token, "--command", "block_insert_after",
                    "--block-id", "-1",
                    "--revision-id", str(remote_revision), "--content", "-", "--as", "user", "--json",
                ], stdin=chunk).data
                imported_tokens.extend(_whiteboard_tokens(appended))
                appended_document = _document_data(appended)
                remote_revision = int(_pick(appended_document, "revision_id", "revisionId", default=remote_revision + 1))
            self._persist(
                job, record,
                revision=remote_revision, whiteboardTokens=list(dict.fromkeys(imported_tokens)),
                fingerprint=rendered.content_fingerprint,
                documentContentComplete=not bool(rendered.evidence_images),
                boardStructureRequestId="", **_clear_active_checkpoint(record, board_keys),
            )
        elif not document_token:
            self._guard_write()
            created = self.cli.run([
                "docs", "+create", "--parent-token", folder_token, "--content", "-", "--as", "user", "--json",
            ], stdin=document_chunks[0]).data
            created_document = _document_data(created)
            document_token = _token(_pick(created_document, "document_id", "document_token", "token"))
            document_url = str(_pick(created_document, "url", "document_url", default=""))
            if not document_token:
                listing = self.cli.run([
                    "drive", "files", "list", "--folder-token", folder_token,
                    "--page-all", "--as", "user", "--json",
                ]).data
                files = listing.get("files") or listing.get("items") or []
                match = next((item for item in files if item.get("name") == rendered.title and item.get("type") == "docx"), None)
                if not match:
                    raise LarkCommandError("command_failed", "Created Feishu document could not be located")
                document_token = _token(_pick(match, "token", "document_id", "document_token"))
                document_url = str(_pick(match, "url", "document_url", default=""))
            imported_tokens = _whiteboard_tokens(created)
            revision = int(_pick(created_document, "revision_id", "revisionId", default=0))
            for chunk in document_chunks[1:]:
                appended = self.cli.run([
                    "docs", "+update", "--doc", document_token, "--command", "block_insert_after",
                    "--block-id", "-1",
                    "--revision-id", str(revision), "--content", "-", "--as", "user", "--json",
                ], stdin=chunk).data
                imported_tokens.extend(_whiteboard_tokens(appended))
                appended_document = _document_data(appended)
                revision = int(_pick(appended_document, "revision_id", "revisionId", default=revision + 1))
            self._persist(
                job, record, documentToken=document_token,
                documentUrl=document_url,
                revision=revision,
                whiteboardTokens=list(dict.fromkeys(imported_tokens)), fingerprint=rendered.content_fingerprint,
                documentContentComplete=not bool(rendered.evidence_images),
                boardStructureRequestId="", **_clear_active_checkpoint(record, board_keys),
                status="creating_whiteboard",
            )

        completed_inline = set((record.get("inlineMediaDone") or {}).keys())
        expected_inline = {item.frame_id for item in rendered.evidence_images}
        if rendered.evidence_images and not (
            record.get("documentContentComplete") is True
            and completed_inline == expected_inline
        ):
            fetched_inline = self.cli.run([
                "docs", "+fetch", "--doc", document_token, "--scope", "full",
                "--detail", "with-ids", "--as", "user", "--json",
            ]).data
            placeholder_ids = _inline_placeholder_ids(fetched_inline)
            if set(placeholder_ids) != {item.frame_id for item in rendered.evidence_images}:
                raise LarkCommandError("command_failed", "inline screenshot anchors are missing or ambiguous")
            inline_media: dict[str, str] = {}
            for image in rendered.evidence_images:
                self._guard_write()
                inserted = self.cli.run([
                    "docs", "+media-insert", "--doc", document_token,
                    "--file", _safe_media_arg(image.path), "--type", "image",
                    "--align", "center", "--caption", image.caption, "--width", "560",
                    "--as", "user", "--json",
                ]).data
                image_block_id = _token(_pick(inserted, "block_id", "id"))
                media_token = _token(_pick(inserted, "file_token", "token"))
                if not image_block_id or not media_token:
                    raise LarkCommandError("command_failed", "inline screenshot insertion returned no block or token")
                self._guard_write()
                self.cli.run([
                    "docs", "+update", "--doc", document_token, "--command", "block_move_after",
                    "--block-id", placeholder_ids[image.frame_id], "--src-block-ids", image_block_id,
                    "--revision-id", "-1", "--as", "user", "--json",
                ])
                self._guard_write()
                self.cli.run([
                    "docs", "+update", "--doc", document_token, "--command", "block_delete",
                    "--block-id", placeholder_ids[image.frame_id], "--revision-id", "-1",
                    "--as", "user", "--json",
                ])
                inline_media[image.frame_id] = media_token
            self._persist(job, record, inlineMediaDone=inline_media, documentContentComplete=True)

        try:
            self._persist(job, record, status="creating_whiteboard")
            fetched = self.cli.run(["docs", "+fetch", "--doc", document_token, "--scope", "full", "--detail", "full", "--as", "user", "--json"]).data
            boards = rendered.native_boards
            board_titles = tuple(board.title for board in boards)
            tokens, semantic_tokens = _document_whiteboard_identity(fetched, board_titles)
            if not tokens:
                tokens = list(record.get("whiteboardTokens") or [])
            expected_total = len(boards) + rendered.embedded_whiteboard_count
            if len(tokens) != expected_total or len(set(tokens)) != len(tokens):
                expected_label = {2: "two", 3: "three"}.get(expected_total, str(expected_total))
                raise LarkCommandError(
                    "command_failed",
                    f"Feishu document must contain exactly {expected_label} distinct whiteboards",
                )
            matches = [semantic_tokens.get(title, []) for title in board_titles]
            fetched_contains_whiteboards = any("<whiteboard" in value for value in _content_values(fetched))
            if (
                all(not values for values in matches)
                and len(tokens) == expected_total
                and not fetched_contains_whiteboards
            ):
                semantic_tokens = {
                    board.title: [tokens[index]] for index, board in enumerate(boards)
                }
                matches = [semantic_tokens.get(title, []) for title in board_titles]
            if (
                any(len(values) != 1 for values in matches)
                or len({values[0] for values in matches if values}) != len(board_titles)
            ):
                raise LarkCommandError("command_failed", "UE whiteboard semantic identity is ambiguous")
            board_tokens = {board.key: semantic_tokens[board.title][0] for board in boards}
            native_token_set = set(board_tokens.values())
            embedded_tokens = [token for token in tokens if token not in native_token_set]
            if len(embedded_tokens) != len(rendered.embedded_whiteboards):
                raise LarkCommandError("command_failed", "gameplay diagram whiteboard identity is ambiguous")
            for index, ((_, svg), token) in enumerate(zip(rendered.embedded_whiteboards, embedded_tokens), 1):
                self._guard_write()
                self.cli.run([
                    "whiteboard", "+update", "--whiteboard-token", token,
                    "--input_format", "svg", "--source", "-", "--overwrite",
                    "--idempotent-token", _idempotent_token(request_id, f"gameplay-diagram-{index}-{token}-v1"),
                    "--as", "user", "--json",
                ], stdin=svg)
                if not _raw_board_has_content(self._query_ready_board(token)):
                    raise LarkCommandError("command_failed", f"gameplay diagram whiteboard {index} is empty")
            checkpoint = _board_checkpoint(record, board_keys)
            last_error = record.get("lastError") if isinstance(record.get("lastError"), dict) else {}
            if last_error.get("kind") == "invalid_parameters":
                for key in board_keys:
                    if not checkpoint["boardMediaNodesDone"].get(key):
                        checkpoint["boardStructureRequestIds"].pop(key, None)
            if "whiteboard" in str(last_error.get("message") or "").lower() and "empty" in str(last_error.get("message") or "").lower():
                for key in board_keys:
                    if checkpoint["boardVerified"].get(key) is not True:
                        checkpoint["boardStructureRequestIds"].pop(key, None)
                        checkpoint["boardMediaNodesDone"].pop(key, None)
            checkpoint["boardTokens"] = board_tokens
            self._persist(job, record, whiteboardTokens=tokens, status="creating_whiteboard", **_checkpoint_changes(record, checkpoint))

            preview_board_svgs = dict(rendered.preview_board_svgs)
            for named in boards:
                key, token, board = named.key, board_tokens[named.key], named.board
                id_map = _openapi_id_map(board.structure, board.overlay, [image.node for image in board.images])
                requires_clean_rebuild = (
                    key in invalid_verified_boards
                    or self._requires_clean_board_rebuild(checkpoint, key, board)
                )
                if requires_clean_rebuild:
                    checkpoint["boardVerified"][key] = False
                    # A clean structure overwrite removes hidden/duplicate
                    # image nodes. Media tokens are board-write scoped and are
                    # uploaded again only after the corrected structure lands.
                    checkpoint["boardStructureRequestIds"].pop(key, None)
                    checkpoint["boardMediaDone"][key] = {}
                    checkpoint["boardMediaNodesDone"][key] = {}
                    self._persist(job, record, status="repairing_board_media", **_checkpoint_changes(record, checkpoint))
                elif checkpoint["boardVerified"].get(key) is True:
                    continue
                preview_svg = preview_board_svgs.get(key, "")
                # Feishu rejects oversized SVG imports with a generic field
                # validation error.  Keep large screenshot-rich boards native:
                # write their raw nodes/connectors and upload images separately.
                # Small SVGs still use the exact preview-parity fast path.
                if not _preview_svg_fast_path_allowed(preview_svg, board):
                    preview_svg = ""
                if preview_svg:
                    self._guard_write()
                    self.cli.run([
                        "whiteboard", "+update", "--whiteboard-token", token,
                        "--input_format", "svg", "--source", "-", "--overwrite",
                        "--idempotent-token", _idempotent_token(request_id, f"{key}-{token}-preview-parity-v1"),
                        "--as", "user", "--json",
                    ], stdin=preview_svg)
                    queried = self._query_ready_board(token)
                    if not _raw_board_has_content(queried):
                        raise LarkCommandError("command_failed", f"preview-parity whiteboard {key} is empty")
                    checkpoint["boardStructureRequestIds"][key] = request_id
                    checkpoint["boardMediaDone"][key] = {}
                    checkpoint["boardMediaNodesDone"][key] = {}
                    checkpoint["boardVerified"][key] = True
                    self._persist(job, record, status="verifying", **_checkpoint_changes(record, checkpoint))
                    continue
                if checkpoint["boardStructureRequestIds"].get(key) != request_id:
                    self._guard_write()
                    self.cli.run([
                        "whiteboard", "+update", "--whiteboard-token", token,
                        "--input_format", "raw", "--source", "-", "--overwrite",
                        "--idempotent-token", _idempotent_token(request_id, f"{key}-{token}-structure-v4"), "--as", "user", "--json",
                    ], stdin=json.dumps(_structure_without_pending_images(board.structure, id_map), ensure_ascii=False))
                    checkpoint["boardStructureRequestIds"][key] = request_id
                    checkpoint["boardMediaDone"][key] = {}
                    checkpoint["boardMediaNodesDone"][key] = {}
                    self._persist(job, record, status="uploading_board_media", **_checkpoint_changes(record, checkpoint))

                media_tokens = checkpoint["boardMediaDone"].setdefault(key, {})
                completed_nodes = checkpoint["boardMediaNodesDone"].setdefault(key, {})
                for image_index, image in enumerate(board.images, 1):
                    node_id = str(image.node.get("id") or f"{image.frame_id}-{image_index}")
                    if node_id in completed_nodes:
                        continue
                    media_token = _token(media_tokens.get(image.frame_id))
                    if not media_token:
                        media = self._upload_media_with_retry([
                            "docs", "+media-upload", "--parent-type", "whiteboard",
                            "--parent-node", token, "--doc-id", document_token,
                            "--file", _safe_media_arg(self.job_dir / image.image_path),
                            "--as", "user", "--json",
                        ])
                        media_token = _token(_pick(media, "file_token", "token"))
                        if not media_token:
                            raise LarkCommandError("command_failed", "whiteboard media upload returned no token")
                        media_tokens[image.frame_id] = media_token
                        self._persist(job, record, status="uploading_board_media", **_checkpoint_changes(record, checkpoint))
                    image_node = _token_backed_image_node(image.node, media_token, id_map)
                    self._guard_write()
                    self.cli.run([
                        "whiteboard", "+update", "--whiteboard-token", token,
                        "--input_format", "raw", "--source", "-",
                        "--idempotent-token", _idempotent_token(request_id, f"{key}-{token}-{node_id}-image-v7"),
                        "--as", "user", "--json",
                    ], stdin=json.dumps({"nodes": [image_node]}, ensure_ascii=False))
                    completed_nodes[node_id] = media_token
                    self._persist(job, record, status="uploading_board_media", **_checkpoint_changes(record, checkpoint))

                normalized_overlay = _normalize_openapi_ids(board.overlay, id_map)
                if normalized_overlay.get("nodes"):
                    self._guard_write()
                    self.cli.run([
                        "whiteboard", "+update", "--whiteboard-token", token,
                        "--input_format", "raw", "--source", "-",
                        "--idempotent-token", _idempotent_token(request_id, f"{key}-{token}-overlay-v5"), "--as", "user", "--json",
                    ], stdin=json.dumps(normalized_overlay, ensure_ascii=False))
                queried = self._query_ready_board(token)
                if (
                    not _raw_board_has_content(queried)
                    or not _raw_board_has_expected_images(queried, len(board.images))
                ):
                    raise LarkCommandError("command_failed", f"UE flow whiteboard {key} is empty")
                checkpoint["boardVerified"][key] = True
                self._persist(job, record, status="verifying", **_checkpoint_changes(record, checkpoint))
            fetched_document = _document_data(fetched)
            revision = int(_pick(fetched_document, "revision_id", "revisionId", default=record.get("revision", 0)))
            self._persist(
                job, record, status="published", revision=revision, fingerprint=rendered.content_fingerprint,
                whiteboardTokens=tokens, resumePartial=False, **_checkpoint_changes(record, checkpoint),
                publishedAt=datetime.now(timezone.utc).isoformat(), message="已发布到飞书", lastError=None,
            )
        except (LarkCommandError, ValueError) as exc:
            self._persist(
                job, record, status="partial" if document_token else "failed",
                lastError={"kind": getattr(exc, "kind", "invalid_document"), "message": str(exc)},
                message="飞书文档已创建，但导出尚未完成；可继续重试" if document_token else "飞书导出失败，可以重试",
            )
            raise
        return PublicationRecord("published", document_token, str(record.get("documentUrl") or ""))
