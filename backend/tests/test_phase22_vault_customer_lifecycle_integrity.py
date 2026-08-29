from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def test_vault_accepts_every_supported_customer_asset_lane():
    page = _read("vault-upload.html")
    client = _read("vault-upload.js")

    for asset_type in (
        "vault_photo",
        "vault_document",
        "private_voice_message",
        "private_video_message",
    ):
        assert f'value="{asset_type}"' in page
        assert f'"{asset_type}"' in client

    for content_type in (
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "audio/mpeg",
        "video/mp4",
    ):
        assert content_type in page
        assert content_type in client


def test_vault_records_server_side_attestations_and_idempotency():
    page = _read("vault-upload.html")
    client = _read("vault-upload.js")

    assert 'name="authority_attested"' in page
    assert 'name="consent_attested"' in page
    assert 'formData.append("authority_attested", "true")' in client
    assert 'formData.append("consent_attested", "true")' in client
    assert '"Idempotency-Key"' in client


def test_vault_release_timing_is_submitted_atomically_with_the_upload():
    page = _read("vault-upload.html")
    client = _read("vault-upload.js")

    assert 'name="release_state"' in page
    assert 'name="reveal_at"' in page
    assert 'formData.append("release_state", releaseState)' in client
    assert 'formData.append("reveal_at", new Date(revealAtValue).toISOString())' in client
    assert "can_use_scheduled_reveal" in client
    assert "The reveal date must be in the future." in client


def test_vault_uses_authenticated_blob_previews_not_uncredentialed_image_urls():
    client = _read("vault-upload.js")

    assert "fetchProtectedUpload" in client
    assert "Authorization: `Bearer ${token}`" in client
    assert "window.URL.createObjectURL(blob)" in client
    assert 'preview ? uploadPreviewUrl(uploadId) : uploadDownloadUrl(uploadId)' in client
    assert "data-vault-secure-image-id" in client
    assert '<img\n                   src="' not in client


def test_vault_exposes_customer_file_lifecycle_controls():
    client = _read("vault-upload.js")

    assert "/uploads/${encodeURIComponent(uploadId)}/replace" in client
    assert "/uploads/${encodeURIComponent(uploadId)}/versions" in client
    assert "/uploads/${encodeURIComponent(uploadId)}/privacy" in client
    assert "data-delete-upload-id" in client
    assert "Replace with New Version" in client
    assert "Version History" in client
    assert "permissions.can_replace" in client
    assert "permissions.can_delete" in client


def test_portrait_and_verification_previews_attach_authentication():
    for name in ("portrait-upload.js", "verification-upload.js"):
        source = _read(name)
        assert "fetchProtectedUpload" in source
        assert "Authorization: `Bearer ${token}`" in source
        assert "window.URL.createObjectURL(blob)" in source
        assert "/replace" in source
        assert 'method: "DELETE"' in source


def test_vault_page_allows_every_purchased_vault_scope():
    auth = _read("auth.js")
    vault = _read("vault-upload.js")

    for capability in (
        "can_use_personal_vault",
        "can_use_household_vault",
        "can_use_linked_household_vault",
        "can_use_organization_records_vault",
    ):
        assert capability in auth
        assert capability in vault

    assert "/uploads/vault/project/" in vault
    assert 'formData.append("project_id", currentProjectId)' in vault
    assert 'formData.append("vault_scope", currentVaultScope)' in vault
    assert 'scope === "household"' in vault
    assert 'scope === "linked_family"' in vault
    assert 'data-vault-scope-select' in _read("vault-upload.html")
    assert '"organization"' in vault
    assert '"linked_family"' in vault
