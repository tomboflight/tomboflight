from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.database import get_database
from app.schemas.db_bootstrap import (
    BootstrapResponse,
    CollectionStatus,
    DropLegacyIndexesResponse,
    LegacyIndexDropResult,
)


CORE_COLLECTIONS: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "users": [
        ([("email", ASCENDING)], {"unique": True, "name": "idx_users_email_unique"}),
        ([("role", ASCENDING)], {"name": "idx_users_role"}),
    ],
    "roles": [
        (
            [("role_code", ASCENDING)],
            {"unique": True, "name": "idx_roles_role_code_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_roles_status"}),
        ([("updated_at", DESCENDING)], {"name": "idx_roles_updated_at"}),
    ],
    "permissions": [
        (
            [("permission_code", ASCENDING)],
            {"unique": True, "name": "idx_permissions_permission_code_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_permissions_status"}),
        ([("updated_at", DESCENDING)], {"name": "idx_permissions_updated_at"}),
    ],
    "role_permissions": [
        (
            [("role_code", ASCENDING), ("permission_code", ASCENDING)],
            {"unique": True, "name": "idx_role_permissions_role_permission_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_role_permissions_status"}),
    ],
    "role_capabilities": [
        (
            [("role_code", ASCENDING), ("capability_code", ASCENDING)],
            {"unique": True, "name": "idx_role_capabilities_role_capability_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_role_capabilities_status"}),
    ],
    "user_role_assignments": [
        (
            [("user_id", ASCENDING), ("role_code", ASCENDING)],
            {"unique": True, "name": "idx_user_role_assignments_user_role_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_user_role_assignments_status"}),
        ([("assigned_at", DESCENDING)], {"name": "idx_user_role_assignments_assigned_at"}),
    ],
    "families": [
        ([("family_name", ASCENDING)], {"name": "idx_families_family_name"}),
        ([("created_at", ASCENDING)], {"name": "idx_families_created_at"}),
    ],
    "family_members": [
        ([("family_id", ASCENDING)], {"name": "idx_family_members_family_id"}),
        (
            [("member_id", ASCENDING)],
            {
                "unique": True,
                "name": "idx_family_members_member_id_unique",
                "partialFilterExpression": {
                    "member_id": {"$type": "string"}
                },
            },
        ),
        ([("full_name", ASCENDING)], {"name": "idx_family_members_full_name"}),
    ],
    "households": [
        ([("family_id", ASCENDING)], {"name": "idx_households_family_id"}),
        (
            [("household_key", ASCENDING)],
            {
                "unique": True,
                "name": "idx_households_household_key_unique",
                "partialFilterExpression": {
                    "household_key": {"$type": "string"}
                },
            },
        ),
    ],
    "household_links": [
        ([("source_household_id", ASCENDING)], {"name": "idx_household_links_source_household_id"}),
        ([("target_household_id", ASCENDING)], {"name": "idx_household_links_target_household_id"}),
        ([("status", ASCENDING)], {"name": "idx_household_links_status"}),
    ],
    "identity_links": [
        ([("family_member_id", ASCENDING)], {"name": "idx_identity_links_family_member_id"}),
        ([("canonical_person_id", ASCENDING)], {"name": "idx_identity_links_canonical_person_id"}),
        (
            [("family_member_id", ASCENDING), ("canonical_person_id", ASCENDING)],
            {
                "unique": True,
                "name": "idx_identity_links_member_canonical_unique",
            },
        ),
        ([("status", ASCENDING)], {"name": "idx_identity_links_status"}),
    ],
    "lineage_nodes": [
        ([("family_id", ASCENDING)], {"name": "idx_lineage_nodes_family_id"}),
        (
            [("node_id", ASCENDING)],
            {
                "unique": True,
                "name": "idx_lineage_nodes_node_id_unique",
                "partialFilterExpression": {
                    "node_id": {"$type": "string"}
                },
            },
        ),
    ],
    "relationships": [
        ([("family_id", ASCENDING)], {"name": "idx_relationships_family_id"}),
        ([("source_member_id", ASCENDING)], {"name": "idx_relationships_source_member_id"}),
        ([("target_member_id", ASCENDING)], {"name": "idx_relationships_target_member_id"}),
        ([("relationship_type", ASCENDING)], {"name": "idx_relationships_relationship_type"}),
        (
            [
                ("family_id", ASCENDING),
                ("source_member_id", ASCENDING),
                ("target_member_id", ASCENDING),
                ("relationship_type", ASCENDING),
            ],
            {
                "unique": True,
                "name": "idx_relationships_edge_unique",
            },
        ),
    ],
    "projects": [
        ([("name", ASCENDING)], {"name": "idx_projects_name"}),
        ([("owner_user_id", ASCENDING)], {"name": "idx_projects_owner_user_id"}),
        ([("owner_email", ASCENDING)], {"name": "idx_projects_owner_email"}),
        ([("created_at", ASCENDING)], {"name": "idx_projects_created_at"}),
        ([("owner_user_id", ASCENDING)], {"name": "idx_projects_owner_user_id"}),
        ([("owner_email", ASCENDING)], {"name": "idx_projects_owner_email"}),
        ([("family_id", ASCENDING)], {"name": "idx_projects_family_id"}),
    ],
    "project_members": [
        ([("project_id", ASCENDING)], {"name": "idx_project_members_project_id"}),
        ([("user_id", ASCENDING)], {"name": "idx_project_members_user_id"}),
        ([("email", ASCENDING)], {"name": "idx_project_members_email"}),
        ([("member_role", ASCENDING)], {"name": "idx_project_members_member_role"}),
        ([("status", ASCENDING)], {"name": "idx_project_members_status"}),
        (
            [("project_id", ASCENDING), ("user_id", ASCENDING), ("email", ASCENDING)],
            {
                "unique": True,
                "name": "idx_project_members_project_identity_unique",
                "partialFilterExpression": {
                    "$or": [
                        {"user_id": {"$type": "string"}},
                        {"email": {"$type": "string"}},
                    ]
                },
            },
        ),
    ],
    "project_members": [
        (
            [("project_id", ASCENDING), ("user_id", ASCENDING)],
            {"unique": True, "name": "idx_project_members_project_user_unique"},
        ),
        ([("project_id", ASCENDING)], {"name": "idx_project_members_project_id"}),
        ([("user_id", ASCENDING)], {"name": "idx_project_members_user_id"}),
        ([("user_email", ASCENDING)], {"name": "idx_project_members_user_email"}),
        ([("status", ASCENDING)], {"name": "idx_project_members_status"}),
        ([("role", ASCENDING)], {"name": "idx_project_members_role"}),
    ],
    "project_entitlements": [
        (
            [("project_id", ASCENDING)],
            {"unique": True, "name": "idx_project_entitlements_project_id_unique"},
        ),
        ([("user_id", ASCENDING)], {"name": "idx_project_entitlements_user_id"}),
        ([("status", ASCENDING)], {"name": "idx_project_entitlements_status"}),
        ([("updated_at", DESCENDING)], {"name": "idx_project_entitlements_updated_at"}),
    ],
    "workflow_events": [
        ([("project_id", ASCENDING)], {"name": "idx_workflow_events_project_id"}),
        ([("from_state", ASCENDING)], {"name": "idx_workflow_events_from_state"}),
        ([("to_state", ASCENDING)], {"name": "idx_workflow_events_to_state"}),
        ([("created_at", DESCENDING)], {"name": "idx_workflow_events_created_at"}),
    ],
    "vaults": [
        (
            [("vault_code", ASCENDING)],
            {"unique": True, "name": "idx_vaults_vault_code_unique"},
        ),
        ([("project_id", ASCENDING)], {"name": "idx_vaults_project_id"}),
        ([("family_id", ASCENDING)], {"name": "idx_vaults_family_id"}),
        ([("organization_id", ASCENDING)], {"name": "idx_vaults_organization_id"}),
        ([("status", ASCENDING)], {"name": "idx_vaults_status"}),
    ],
    "vault_files": [
        (
            [("file_id", ASCENDING)],
            {"unique": True, "name": "idx_vault_files_file_id_unique"},
        ),
        ([("vault_id", ASCENDING)], {"name": "idx_vault_files_vault_id"}),
        ([("project_id", ASCENDING)], {"name": "idx_vault_files_project_id"}),
        ([("uploader_id", ASCENDING)], {"name": "idx_vault_files_uploader_id"}),
        ([("uploaded_at", DESCENDING)], {"name": "idx_vault_files_uploaded_at"}),
        ([("verification_status", ASCENDING)], {"name": "idx_vault_files_verification_status"}),
    ],
    "audit_logs": [
        ([("action", ASCENDING)], {"name": "idx_audit_logs_action"}),
        ([("timestamp", DESCENDING)], {"name": "idx_audit_logs_timestamp"}),
        ([("target_type", ASCENDING)], {"name": "idx_audit_logs_target_type"}),
        ([("target_id", ASCENDING)], {"name": "idx_audit_logs_target_id"}),
        ([("result", ASCENDING)], {"name": "idx_audit_logs_result"}),
        ([("actor_user_id", ASCENDING)], {"name": "idx_audit_logs_actor_user_id"}),
        ([("actor_email", ASCENDING)], {"name": "idx_audit_logs_actor_email"}),
    ],
    "tool_status": [
        (
            [("tool_code", ASCENDING)],
            {"unique": True, "name": "idx_tool_status_tool_code_unique"},
        ),
        ([("status", ASCENDING)], {"name": "idx_tool_status_status"}),
        ([("severity", ASCENDING)], {"name": "idx_tool_status_severity"}),
        ([("updated_at", DESCENDING)], {"name": "idx_tool_status_updated_at"}),
    ],
    "failed_workflow_queue": [
        (
            [("queue_item_id", ASCENDING)],
            {"unique": True, "name": "idx_failed_workflow_queue_queue_item_id_unique"},
        ),
        ([("project_id", ASCENDING)], {"name": "idx_failed_workflow_queue_project_id"}),
        ([("workflow_name", ASCENDING)], {"name": "idx_failed_workflow_queue_workflow_name"}),
        ([("status", ASCENDING)], {"name": "idx_failed_workflow_queue_status"}),
        ([("next_retry_at", ASCENDING)], {"name": "idx_failed_workflow_queue_next_retry_at"}),
        ([("created_at", DESCENDING)], {"name": "idx_failed_workflow_queue_created_at"}),
    ],
    "verification_records": [
        ([("family_id", ASCENDING)], {"name": "idx_verification_records_family_id"}),
        ([("member_id", ASCENDING)], {"name": "idx_verification_records_member_id"}),
        ([("verification_status", ASCENDING)], {"name": "idx_verification_records_status"}),
        ([("created_at", DESCENDING)], {"name": "idx_verification_records_created_at"}),
        ([("evidence_upload_ids", ASCENDING)], {"name": "idx_verification_records_evidence_upload_ids"}),
    ],
    "narrative_records": [
        ([("family_id", ASCENDING)], {"name": "idx_narrative_records_family_id"}),
        ([("member_id", ASCENDING)], {"name": "idx_narrative_records_member_id"}),
    ],
    "issued_certificates": [
        (
            [("certificate_id", ASCENDING)],
            {
                "unique": True,
                "name": "idx_issued_certificates_certificate_id_unique",
                "partialFilterExpression": {
                    "certificate_id": {"$type": "string"}
                },
            },
        ),
        ([("family_id", ASCENDING)], {"name": "idx_issued_certificates_family_id"}),
    ],
    "certificate_versions": [
        ([("family_id", ASCENDING)], {"name": "idx_certificate_versions_family_id"}),
        ([("version", ASCENDING)], {"name": "idx_certificate_versions_version"}),
    ],
    "mint_records": [
        (
            [("project_id", ASCENDING), ("version_number", DESCENDING)],
            {"name": "idx_mint_records_project_id_1_version_number_-1"},
        ),
        (
            [("mint_status", ASCENDING), ("created_at", DESCENDING)],
            {"name": "idx_mint_records_mint_status_1_created_at_-1"},
        ),
        ([("tx_hash", ASCENDING)], {"name": "idx_mint_records_tx_hash_1"}),
        (
            [("token_id", ASCENDING), ("contract_address", ASCENDING)],
            {"name": "idx_mint_records_token_id_1_contract_address_1"},
        ),
    ],
    "mint_jobs": [
        (
            [("status", ASCENDING), ("run_after", ASCENDING), ("priority", DESCENDING)],
            {"name": "idx_mint_jobs_status_1_run_after_1_priority_-1"},
        ),
        (
            [("project_id", ASCENDING), ("created_at", DESCENDING)],
            {"name": "idx_mint_jobs_project_id_1_created_at_-1"},
        ),
        (
            [("mint_record_id", ASCENDING)],
            {"name": "idx_mint_jobs_mint_record_id_1"},
        ),
    ],
    "public_metadata_manifests": [
        (
            [("project_id", ASCENDING), ("version_number", DESCENDING)],
            {"name": "idx_public_metadata_manifests_project_id_1_version_number_-1"},
        ),
        (
            [("public_token_id", ASCENDING)],
            {
                "name": "idx_public_metadata_manifests_public_token_id_1",
                "unique": True,
                "partialFilterExpression": {
                    "public_token_id": {"$type": "string"}
                },
            },
        ),
        (
            [("mint_record_id", ASCENDING)],
            {"name": "idx_public_metadata_manifests_mint_record_id_1"},
        ),
    ],
    "mint_approvals": [
        (
            [("project_id", ASCENDING), ("approval_type", ASCENDING), ("status", ASCENDING)],
            {"name": "idx_mint_approvals_project_id_1_approval_type_1_status_1"},
        ),
        (
            [("mint_record_id", ASCENDING)],
            {"name": "idx_mint_approvals_mint_record_id_1"},
        ),
    ],
}


def bootstrap_core_collections() -> BootstrapResponse:
    db = get_database()

    if db is None:
        raise ValueError("Database is not connected.")

    existing_collections = set(db.list_collection_names())
    results: list[CollectionStatus] = []

    for collection_name, index_definitions in CORE_COLLECTIONS.items():
        created = False
        created_indexes: list[str] = []

        if collection_name not in existing_collections:
            db.create_collection(collection_name)
            created = True

        collection = db[collection_name]
        existing_indexes = collection.index_information()

        for keys, options in index_definitions:
            index_name = options.get("name", "unnamed_index")

            if index_name in existing_indexes:
                created_indexes.append(index_name)
                continue

            try:
                collection.create_index(keys, **options)
                created_indexes.append(index_name)
            except OperationFailure:
                # Skip index conflicts safely so bootstrap does not crash startup
                created_indexes.append(index_name)

        results.append(
            CollectionStatus(
                name=collection_name,
                created=created,
                indexes_created=created_indexes,
            )
        )

    return BootstrapResponse(
        message="Core Tomb of Light collections and indexes processed successfully.",
        database_name=db.name,
        collections=results,
    )


_CANONICAL_INDEX_NAMES: dict[str, set[str]] = {
    collection_name: {opts.get("name", "") for _, opts in index_defs}
    for collection_name, index_defs in CORE_COLLECTIONS.items()
}


def drop_legacy_indexes() -> DropLegacyIndexesResponse:
    db = get_database()

    if db is None:
        raise ValueError("Database is not connected.")

    results: list[LegacyIndexDropResult] = []
    total_dropped = 0

    for collection_name, canonical_names in _CANONICAL_INDEX_NAMES.items():
        if collection_name not in set(db.list_collection_names()):
            continue

        collection = db[collection_name]
        existing_indexes = collection.index_information()

        dropped: list[str] = []
        skipped: list[str] = []

        for index_name in list(existing_indexes.keys()):
            if index_name == "_id_":
                continue
            if index_name in canonical_names:
                continue
            try:
                collection.drop_index(index_name)
                dropped.append(index_name)
            except OperationFailure:
                skipped.append(index_name)

        total_dropped += len(dropped)
        results.append(
            LegacyIndexDropResult(
                collection=collection_name,
                dropped=dropped,
                skipped=skipped,
            )
        )

    return DropLegacyIndexesResponse(
        message="Legacy index cleanup completed.",
        database_name=db.name,
        results=results,
        total_dropped=total_dropped,
    )
