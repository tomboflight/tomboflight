from pymongo import ASCENDING

from app.database import get_database
from app.schemas.db_bootstrap import BootstrapResponse, CollectionStatus


CORE_COLLECTIONS: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "users": [
        ([("email", ASCENDING)], {"unique": True, "name": "idx_users_email_unique"}),
        ([("role", ASCENDING)], {"name": "idx_users_role"}),
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
                    "member_id": {"$exists": True, "$type": "string", "$ne": ""}
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
                    "household_key": {"$exists": True, "$type": "string", "$ne": ""}
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
        ([("source_member_id", ASCENDING)], {"name": "idx_identity_links_source_member_id"}),
        ([("target_member_id", ASCENDING)], {"name": "idx_identity_links_target_member_id"}),
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
                    "node_id": {"$exists": True, "$type": "string", "$ne": ""}
                },
            },
        ),
    ],
    "relationships": [
        ([("family_id", ASCENDING)], {"name": "idx_relationships_family_id"}),
        ([("source_id", ASCENDING)], {"name": "idx_relationships_source_id"}),
        ([("target_id", ASCENDING)], {"name": "idx_relationships_target_id"}),
        ([("relationship_type", ASCENDING)], {"name": "idx_relationships_relationship_type"}),
    ],
    "projects": [
        ([("name", ASCENDING)], {"name": "idx_projects_name"}),
        ([("created_at", ASCENDING)], {"name": "idx_projects_created_at"}),
    ],
    "audit_logs": [
        ([("action", ASCENDING)], {"name": "idx_audit_logs_action"}),
        ([("created_at", ASCENDING)], {"name": "idx_audit_logs_created_at"}),
        ([("actor_email", ASCENDING)], {"name": "idx_audit_logs_actor_email"}),
    ],
    "verification_records": [
        ([("family_id", ASCENDING)], {"name": "idx_verification_records_family_id"}),
        ([("member_id", ASCENDING)], {"name": "idx_verification_records_member_id"}),
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
                    "certificate_id": {"$exists": True, "$type": "string", "$ne": ""}
                },
            },
        ),
        ([("family_id", ASCENDING)], {"name": "idx_issued_certificates_family_id"}),
    ],
    "certificate_versions": [
        ([("family_id", ASCENDING)], {"name": "idx_certificate_versions_family_id"}),
        ([("version", ASCENDING)], {"name": "idx_certificate_versions_version"}),
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

        for keys, options in index_definitions:
            index_name = options.get("name", "unnamed_index")
            collection.create_index(keys, **options)
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