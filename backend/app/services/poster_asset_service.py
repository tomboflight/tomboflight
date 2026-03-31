from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pymongo.collection import Collection

from app.config import settings
from app.database import get_database
from app.services.r2_storage_service import ZONE_POSTER, upload_bytes

ALLOWED_POSTER_STYLES = {
    "abstract_cover",
    "symbolic_cover",
    "approved_poster",
}

SVG_CONTENT_TYPE = "image/svg+xml"


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _poster_url(filename: str) -> str:
    base = settings.poster_base_url_clean
    return f"{base}/{filename}"


def _uploads_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["uploaded_files"])


def resolve_poster_policy(
    project_id: str,
    *,
    requested_style: str,
    approved_poster_opt_in: bool = False,
) -> dict[str, str]:
    del project_id

    style = _normalize(requested_style).lower()
    if style not in ALLOWED_POSTER_STYLES:
        style = "abstract_cover"

    if style == "approved_poster" and not approved_poster_opt_in:
        style = "abstract_cover"

    return {
        "poster_style": style,
    }


def _build_svg_cover(
    *,
    title: str,
    subtitle: str,
    accent_start: str,
    accent_end: str,
    token_label: str,
) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_subtitle = subtitle.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_token = token_label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1600" viewBox="0 0 1600 1600" fill="none">
  <defs>
    <linearGradient id="bg" x1="160" y1="80" x2="1440" y2="1520" gradientUnits="userSpaceOnUse">
      <stop stop-color="#07101B"/>
      <stop offset="0.5" stop-color="#0D1E2E"/>
      <stop offset="1" stop-color="#04080F"/>
    </linearGradient>
    <linearGradient id="ring" x1="420" y1="340" x2="1180" y2="1260" gradientUnits="userSpaceOnUse">
      <stop stop-color="{accent_start}"/>
      <stop offset="1" stop-color="{accent_end}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(800 760) rotate(90) scale(460)">
      <stop stop-color="{accent_start}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="{accent_end}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1600" height="1600" fill="url(#bg)"/>
  <circle cx="800" cy="760" r="460" fill="url(#glow)"/>
  <circle cx="800" cy="760" r="330" stroke="url(#ring)" stroke-opacity="0.3" stroke-width="2"/>
  <circle cx="800" cy="760" r="230" stroke="url(#ring)" stroke-opacity="0.6" stroke-width="3"/>
  <circle cx="800" cy="760" r="140" fill="#071320" stroke="url(#ring)" stroke-width="4"/>
  <path d="M800 604V916" stroke="url(#ring)" stroke-width="3" stroke-linecap="round"/>
  <path d="M644 760H956" stroke="url(#ring)" stroke-width="3" stroke-linecap="round"/>
  <text x="800" y="250" fill="#F3EFE7" font-size="62" font-family="Georgia, 'Times New Roman', serif" text-anchor="middle" letter-spacing="10">TOMB OF LIGHT</text>
  <text x="800" y="1160" fill="#FFFFFF" font-size="92" font-family="Georgia, 'Times New Roman', serif" text-anchor="middle">{safe_title}</text>
  <text x="800" y="1240" fill="#BFCBDD" font-size="34" font-family="Arial, sans-serif" text-anchor="middle" letter-spacing="2">{safe_subtitle}</text>
  <text x="800" y="1360" fill="{accent_start}" font-size="26" font-family="Arial, sans-serif" text-anchor="middle" letter-spacing="6">{safe_token}</text>
</svg>"""


def _upload_svg_poster(
    *,
    svg_text: str,
    filename: str,
    publish: bool,
) -> dict[str, Any]:
    uploaded = upload_bytes(
        zone=ZONE_POSTER,
        key=f"v1/{filename}",
        body=svg_text.encode("utf-8"),
        content_type=SVG_CONTENT_TYPE,
        cache_control="public, max-age=86400",
        publish=publish,
    )
    return {
        "poster_image_uri_public": _poster_url(filename),
        "poster_filename": filename,
        "poster_storage_key": uploaded["key"],
        "poster_storage_bucket": uploaded.get("bucket"),
        "poster_storage_provider": uploaded["storage_provider"],
    }


def generate_abstract_cover(
    project_id: str,
    version_number: int,
    public_token_id: str,
    *,
    publish: bool = True,
) -> dict[str, Any]:
    del project_id
    filename = f"{public_token_id}-abstract-cover.svg"
    svg_text = _build_svg_cover(
        title="Legacy Anchor",
        subtitle=f"Version {version_number}",
        accent_start="#E7A45A",
        accent_end="#7AC8FF",
        token_label=public_token_id,
    )
    return _upload_svg_poster(svg_text=svg_text, filename=filename, publish=publish)


def generate_symbolic_cover(
    project_id: str,
    version_number: int,
    public_token_id: str,
    *,
    publish: bool = True,
) -> dict[str, Any]:
    del project_id
    filename = f"{public_token_id}-symbolic-cover.svg"
    svg_text = _build_svg_cover(
        title="Protected Lineage",
        subtitle=f"Approved build version {version_number}",
        accent_start="#C8C0FF",
        accent_end="#7EE7C4",
        token_label=public_token_id,
    )
    return _upload_svg_poster(svg_text=svg_text, filename=filename, publish=publish)


def _best_uploaded_portrait(project_id: str) -> dict[str, Any] | None:
    return _uploads_collection().find_one(
        {
            "project_id": _normalize(project_id),
            "category": "member_photo",
        },
        sort=[("created_at", -1)],
    )


def _read_local_upload_bytes(upload_record: dict[str, Any]) -> tuple[bytes, str, str] | None:
    relative_path = _normalize(upload_record.get("relative_path"))
    if not relative_path:
        return None

    absolute_path = Path(settings.upload_root_path) / relative_path
    if not absolute_path.exists() or not absolute_path.is_file():
        return None

    content_type = _normalize(upload_record.get("content_type")) or "application/octet-stream"
    suffix = Path(_normalize(upload_record.get("stored_filename")) or absolute_path.name).suffix or ".bin"
    return absolute_path.read_bytes(), content_type, suffix


def export_approved_public_poster(
    project_id: str,
    version_number: int,
    public_token_id: str,
    *,
    publish: bool = True,
) -> dict[str, Any]:
    upload_record = _best_uploaded_portrait(project_id)
    if upload_record is None:
        return generate_abstract_cover(
            project_id,
            version_number,
            public_token_id,
            publish=publish,
        )

    source = _read_local_upload_bytes(upload_record)
    if source is None:
        return generate_abstract_cover(
            project_id,
            version_number,
            public_token_id,
            publish=publish,
        )

    body, content_type, suffix = source
    filename = f"{public_token_id}-approved-poster{suffix}"
    uploaded = upload_bytes(
        zone=ZONE_POSTER,
        key=f"v1/{filename}",
        body=body,
        content_type=content_type,
        cache_control="public, max-age=86400",
        publish=publish,
    )

    return {
        "poster_image_uri_public": _poster_url(filename),
        "poster_filename": filename,
        "poster_storage_key": uploaded["key"],
        "poster_storage_bucket": uploaded.get("bucket"),
        "poster_storage_provider": uploaded["storage_provider"],
    }


def build_poster_asset(
    *,
    project_id: str,
    version_number: int,
    public_token_id: str,
    requested_style: str,
    approved_poster_opt_in: bool = False,
    publish: bool = True,
) -> dict[str, Any]:
    policy = resolve_poster_policy(
        project_id,
        requested_style=requested_style,
        approved_poster_opt_in=approved_poster_opt_in,
    )
    poster_style = policy["poster_style"]

    if poster_style == "symbolic_cover":
        asset = generate_symbolic_cover(
            project_id,
            version_number,
            public_token_id,
            publish=publish,
        )
    elif poster_style == "approved_poster":
        asset = export_approved_public_poster(
            project_id,
            version_number,
            public_token_id,
            publish=publish,
        )
    else:
        asset = generate_abstract_cover(
            project_id,
            version_number,
            public_token_id,
            publish=publish,
        )

    return {
        "poster_style": poster_style,
        **asset,
    }
